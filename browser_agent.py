#!/usr/bin/env python3
"""
WhatsApp Web Persistent Real-Time Conversational Browser Caller (browser_agent.py)
Automates Google Chrome on web.whatsapp.com:
1. Maintains persistent profile so login state is saved permanently.
2. Clicks the native WhatsApp Web Voice Call button to connect live audio.
3. Native PulseAudio Hardware Audio Architecture:
   - VirtualMicSource (Microphone): Streams Sarah's voice into the call (plays ONCE, zero looping).
   - CallSpeaker.monitor (Speaker): Captures incoming caller audio directly from PulseAudio.
4. Full Duplex Conversational Voice Agent:
   - VAD (Voice Activity Detection) on 16kHz PCM chunks.
   - Interrupts/barges in when caller speaks.
   - Transcribes caller speech via faster-whisper.
   - Generates 1-2 sentence human conversational reply via Moonmath DeepSeek.
   - Synthesizes speech via Edge-TTS and streams into VirtualMic in real time.
5. Saves complete call transcript to Omnichannel Memory and Supabase.
"""

import os
import sys
import time
import queue
import logging
import threading
import subprocess
import requests
import numpy as np
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, BrowserContext, Page

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import live_voice_agent
from omnichannel_memory import memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PROFILE_DIR = os.path.join(BASE_DIR, "profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

DEFAULT_PHONE = os.environ.get("WHATSAPP_LINE_1", "01746654426")


class WhatsAppBrowserCaller(threading.Thread):
    def __init__(self, phone_number: str = DEFAULT_PHONE, headless: bool = True):
        super().__init__(daemon=True)
        self.phone_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
        if self.phone_number.startswith("880"):
            self.local_number = self.phone_number[3:]
        elif self.phone_number.startswith("0"):
            self.local_number = self.phone_number[1:]
        else:
            self.local_number = self.phone_number

        self.headless = headless
        self.cmd_queue = queue.Queue()
        
        self.is_connected = False
        self.pairing_code: Optional[str] = None
        self.call_state = "idle"  # idle, calling, ringing, connected
        self.active_call_target = None
        self.call_start_time = None
        self.call_duration = 0.0
        self.intro_spoken = False
        self.active_call_transcript: List[Dict[str, Any]] = []
        
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._ready_event = threading.Event()

        # PulseAudio process handles
        self.player_proc: Optional[subprocess.Popen] = None
        self.audio_listener_thread: Optional[threading.Thread] = None
        self.stop_audio_listener = threading.Event()

    def run(self):
        """Dedicated Playwright thread worker."""
        logging.info(f"🌐 Launching Chrome with persistent profile at {PROFILE_DIR}...")
        
        # Configure PulseAudio environment for Chrome
        os.environ["PULSE_SERVER"] = "/var/run/pulse/native"
        os.environ["PULSE_SOURCE"] = "VirtualMicSource"
        os.environ["PULSE_SINK"] = "CallSpeaker"

        with sync_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-popup-blocking",
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]

            self.context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                executable_path="/usr/bin/google-chrome",
                headless=self.headless,
                viewport={"width": 1440, "height": 1200},
                args=launch_args,
                env=os.environ
            )

            # Monitor all pages and popups
            self.context.on("page", lambda new_page: logging.info(f"📑 Chrome page opened: {new_page.url} ({new_page.title()})"))

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

            # Log Chrome console output
            self.page.on("console", lambda msg: logging.info(f"🖥️ [Chrome {msg.type}]: {msg.text}"))
            self.page.on("pageerror", lambda err: logging.error(f"🖥️ [Chrome Error]: {err}"))

            self.page.goto("https://web.whatsapp.com", timeout=60000, wait_until="domcontentloaded")
            
            # Wait for WhatsApp Web session to restore from IndexedDB
            logging.info("⏳ Waiting for WhatsApp Web session to load...")
            for _ in range(15):
                if self._check_if_logged_in():
                    break
                time.sleep(2)

            if self._check_if_logged_in():
                self.is_connected = True
                self.pairing_code = None
                logging.info("✅ WhatsApp Web already authenticated and logged in!")
            else:
                logging.info("🟡 WhatsApp Web login required. Ready for pairing.")

            self._ready_event.set()

            # Main event loop for Playwright thread
            while True:
                try:
                    cmd, args, result_event, result_box = self.cmd_queue.get(timeout=1.5)
                    if cmd == "make_call":
                        res = self._do_make_call(args)
                        result_box[0] = res
                        result_event.set()
                    elif cmd == "hangup":
                        res = self._do_hangup()
                        result_box[0] = res
                        result_event.set()
                    elif cmd == "request_code":
                        res = self._do_request_pairing_code()
                        result_box[0] = res
                        result_event.set()
                    elif cmd == "show_qr":
                        res = self._do_show_qr_code()
                        result_box[0] = res
                        result_event.set()
                    elif cmd == "screenshot":
                        path = args or "/var/www/omnicall-ai/browser-caller/screen.png"
                        if self.page:
                            self.page.screenshot(path=path)
                        result_box[0] = path
                        result_event.set()
                except queue.Empty:
                    # Periodic heartbeat: check if login completed
                    if not self.is_connected and self._check_if_logged_in():
                        self.is_connected = True
                        self.pairing_code = None
                        logging.info("🎉 Handshake complete! WhatsApp Web is now CONNECTED and saved to disk!")
                    
                    # Monitor active call
                    if self.call_state in ("calling", "ringing", "connected"):
                        self._check_active_call_in_page()

    def _check_if_logged_in(self) -> bool:
        """Returns True if the home chat pane is visible."""
        try:
            if not self.page:
                return False
            chat_pane = self.page.locator("#pane-side, [data-testid=\"chat-list\"], [aria-label*=\"Chat list\" i]").first
            return chat_pane.is_visible()
        except Exception:
            return False

    def _do_show_qr_code(self) -> bool:
        """Dismisses any error modal and navigates to the QR code screen."""
        try:
            logging.info("Dismissing any modal and switching to QR code...")
            res = self.page.evaluate("""() => {
                let clickedOk = false;
                let clickedQr = false;

                // 1. Click OK on error popup
                const all = Array.from(document.querySelectorAll('button, [role="button"], div, span'));
                const okBtn = all.find(b => (b.innerText || '').trim() === 'OK');
                if (okBtn) {
                    okBtn.click();
                    clickedOk = true;
                }

                // 2. Click Log in with QR code
                setTimeout(() => {
                    const all2 = Array.from(document.querySelectorAll('*'));
                    const qrLink = all2.find(el => (el.innerText || '').includes('Log in with QR code'));
                    if (qrLink) {
                        qrLink.click();
                        clickedQr = true;
                    }
                }, 800);

                return { clickedOk, clickedQr };
            }""")
            time.sleep(2)
            return True
        except Exception as e:
            logging.error(f"Error returning to QR code: {e}")
        return False

    def _do_request_pairing_code(self) -> Optional[str]:
        """Automates the 'Log in with phone number' flow on the Playwright thread."""
        logging.info(f"🔑 Requesting 8-digit pairing code for +880 {self.local_number}...")
        try:
            # Handle rate limit modal if present
            ok_btn = self.page.locator("button:has-text(\"OK\")").first
            if ok_btn.is_visible():
                logging.info("Clicking OK on modal...")
                ok_btn.click()
                time.sleep(2)

            btn = self.page.locator("text=Log in with phone number").first
            if btn.is_visible():
                box = btn.bounding_box()
                if box:
                    self.page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                else:
                    btn.click(force=True)
                time.sleep(3)

            c_btn = self.page.locator("button, [role=\"button\"]").filter(has_text="Burma").first
            if not c_btn.is_visible():
                c_btn = self.page.locator("div").filter(has_text="Myanmar (Burma)").last
            
            c_box = c_btn.bounding_box()
            if c_box:
                self.page.mouse.click(c_box["x"] + c_box["width"]/2, c_box["y"] + c_box["height"]/2)
            else:
                c_btn.click(force=True)
            time.sleep(1.5)

            self.page.keyboard.type("Bangladesh", delay=40)
            time.sleep(1)
            bd_item = self.page.locator("text=Bangladesh").last
            bd_item.click(force=True)
            time.sleep(1.5)

            inp = self.page.locator("[data-testid=\"phone-number-input\"]")
            inp.click()
            self.page.keyboard.type(self.local_number, delay=40)
            time.sleep(1)

            next_btn = self.page.locator("button:has-text(\"Next\")").first
            next_btn.click(force=True)
            time.sleep(5)

            code = self.page.evaluate("""() => {
                const all = Array.from(document.querySelectorAll('*'));
                const matches = all.filter(el => {
                    const t = el.innerText ? el.innerText.trim() : '';
                    return el.children.length === 0 && t.length === 1 && /^[A-Z0-9]$/.test(t);
                });
                return matches.map(m => m.innerText.trim()).join('');
            }""")

            if code and len(code) >= 8:
                formatted_code = f"{code[:4]}-{code[4:8]}"
                self.pairing_code = formatted_code
                logging.info(f"📱 WHATSAPP WEB 8-DIGIT PAIRING CODE: {formatted_code}")
                return formatted_code
        except Exception as e:
            logging.error(f"❌ Error during pairing code request: {e}")
        return None

    def _do_make_call(self, target_phone: str) -> Dict[str, Any]:
        """Navigates to recipient's chat and clicks the native WhatsApp Voice Call button."""
        clean_target = target_phone.replace("+", "").replace(" ", "").replace("-", "")
        if not self.is_connected:
            return {"ok": False, "error": "WhatsApp Web is not authenticated yet. Please pair first."}

        logging.info(f"📞 Opening chat with +{clean_target} to place voice call...")
        self.call_state = "calling"
        self.active_call_target = clean_target
        self.call_start_time = time.time()
        self.call_duration = 0.0
        self.intro_spoken = False
        self.active_call_transcript = []

        try:
            # 0. Dismiss any greeting / "What's new" modal if blocking screen
            try:
                self.page.evaluate("""() => {
                    const contBtn = Array.from(document.querySelectorAll('button, [role="button"]')).find(b => (b.innerText || '').trim() === 'Continue');
                    if (contBtn) contBtn.click();
                    const closeBtn = document.querySelector('[data-icon="x"], button[aria-label="Close"]');
                    if (closeBtn) closeBtn.click();
                }""")
                time.sleep(1)
            except Exception:
                pass

            # 1. Switch back to Chats view if on Calls or another tab
            try:
                chats_btn = self.page.locator('button[aria-label="Chats"], [data-icon="chat"], [data-icon="chat-outline"]').first
                if chats_btn.is_visible():
                    chats_btn.click()
                    time.sleep(1)
            except Exception:
                pass

            main_header = None

            # 2. Check if target is already visible in chat list (#pane-side)
            target_short = clean_target[-8:]  # e.g. "17427815"
            try:
                chat_row = self.page.locator(f'#pane-side [role="row"]').filter(has_text=target_short).first
                if chat_row.is_visible():
                    logging.info(f"Target +{clean_target} found directly in chat list! Clicking row...")
                    chat_row.click()
                    time.sleep(2)
                    if self.page.locator("#main header").first.is_visible():
                        main_header = self.page.locator("#main header").first
            except Exception as e:
                logging.warning(f"Chat list direct click error: {e}")

            # 3. Check if chat is already open for target in #main
            if not main_header and self.page.locator("#main header").first.is_visible():
                header_text = self.page.locator("#main header").first.inner_text().replace(" ", "").replace("-", "")
                if clean_target in header_text or target_short in header_text:
                    main_header = self.page.locator("#main header").first

            # 4. Open chat via deep link if not opened yet
            if not main_header:
                logging.info(f"Opening chat via URL: https://web.whatsapp.com/send/?phone={clean_target}")
                self.page.goto(f"https://web.whatsapp.com/send/?phone={clean_target}", timeout=30000, wait_until="domcontentloaded")
                for _ in range(12):
                    if self.page.locator("#main header").first.is_visible():
                        main_header = self.page.locator("#main header").first
                        break
                    time.sleep(1)

            # 5. Fallback: Search box in #pane-side
            if not main_header:
                logging.info(f"Searching for {clean_target} in WhatsApp search bar...")
                search = self.page.locator('div[contenteditable="true"][data-tab="3"], [aria-label*="Search" i], #side [role="textbox"]').first
                if search.is_visible():
                    search.click()
                    self.page.keyboard.type(clean_target, delay=30)
                    time.sleep(2)
                    first_cell = self.page.locator('#pane-side [role="row"], #pane-side [data-testid="cell-frame-container"]').first
                    if first_cell.is_visible():
                        first_cell.click()
                        time.sleep(2)
                        if self.page.locator("#main header").first.is_visible():
                            main_header = self.page.locator("#main header").first

            if not main_header:
                self.call_state = "idle"
                logging.error(f"❌ Failed to open chat with +{clean_target}")
                return {"ok": False, "error": f"Could not open conversation with +{clean_target}."}

            logging.info("Chat conversation loaded! Locating Voice Call button strictly inside #main header...")
            time.sleep(1)

            # 5. Locate Voice Call button strictly inside #main header (avoiding video call)
            call_selectors = [
                '#main header button[aria-label*="voice call" i]',
                '#main header button[aria-label*="audio call" i]',
                '#main header button[title*="voice call" i]',
                '#main header button[title*="audio call" i]',
                '#main header span[data-icon="phone"]',
                '#main header button:has(span[data-icon="phone"])'
            ]

            call_btn = None
            for sel in call_selectors:
                el = self.page.locator(sel).first
                if el.is_visible():
                    call_btn = el
                    logging.info(f"Found voice call button in #main header: {sel}")
                    break

            if call_btn:
                call_btn.click()
                self.call_state = "ringing"
                logging.info(f"✅ Clicked WhatsApp Voice Call button in #main header! Calling +{clean_target}...")
                
                # Start hardware duplex listener immediately so we capture WebRTC audio and answer instantly
                self._start_audio_listener()

                return {
                    "ok": True,
                    "status": "ringing",
                    "target": clean_target,
                    "message": f"Voice call initiated to +{clean_target}. Sarah will speak when answered!"
                }
            else:
                self.call_state = "idle"
                logging.warning(f"⚠️ Voice call button not present in #main header for +{clean_target}")
                return {
                    "ok": False,
                    "error": "Voice call button not present in chat header."
                }
        except Exception as e:
            self.call_state = "idle"
            logging.error(f"❌ Error placing voice call: {e}")
            return {"ok": False, "error": str(e)}

    def _check_active_call_in_page(self) -> Dict[str, Any]:
        """Monitors in-call status, triggers intro greeting ONCE, and detects call end."""
        try:
            if not self.page:
                return {"state": self.call_state}

            # Check across all active pages (in case call opened in a popup)
            active_page = self.page
            if self.context and len(self.context.pages) > 1:
                active_page = self.context.pages[-1]

            status_info = active_page.evaluate("""() => {
                // 1. Scan all text nodes for in-call timer string (e.g. "00:05", "0:12", "1:23")
                const timers = [];
                const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let n;
                while(n = walk.nextNode()) {
                    const val = (n.nodeValue || '').trim();
                    if (/^\\d{1,2}:[0-5]\\d$/.test(val)) {
                        // Ensure not in chat history row
                        if (!n.parentElement.closest('[role="row"], [data-id*="false_"], [data-id*="true_"]')) {
                            timers.push(val);
                        }
                    }
                }

                // 2. Scan for call control buttons
                const endBtn = document.querySelector('[data-icon="x-circle"], [data-icon="x"], button[aria-label*="End call" i], button[title*="End call" i], [data-icon="phone-hangup"]');
                const muteBtn = document.querySelector('button[aria-label*="Mute" i], [data-icon="mic"], [data-icon="microphone"]');

                // 3. Scan for call status text
                const allText = document.body.innerText.toLowerCase();
                const isRinging = allText.includes('ringing');
                const isCalling = allText.includes('calling');
                const isEnded = allText.includes('call ended') || allText.includes('declined') || allText.includes('unavailable') || allText.includes('call missed');

                let snippet = '';
                if (endBtn) {
                    const bar = endBtn.closest('div[style*="position"], [role="region"], div');
                    snippet = bar ? (bar.innerText || '').slice(0, 100).replace(/\\n/g, ' ') : '';
                }

                return {
                    timer: timers.length > 0 ? timers[0] : null,
                    allTimers: timers,
                    hasEndBtn: !!endBtn,
                    hasMuteBtn: !!muteBtn,
                    isRinging: isRinging,
                    isCalling: isCalling,
                    isEnded: isEnded,
                    snippet: snippet
                };
            }""")

            timer = status_info.get("timer")
            has_end_btn = status_info.get("hasEndBtn")
            is_ringing = status_info.get("isRinging")
            is_calling = status_info.get("isCalling")
            is_ended = status_info.get("isEnded")
            snippet = status_info.get("snippet", "")
            elapsed = time.time() - (self.call_start_time or time.time())

            # Log status every check
            logging.info(f"📞 [Call Monitor] state={self.call_state}, elapsed={round(elapsed,1)}s, timer={timer}, hasEndBtn={has_end_btn}, isRinging={is_ringing}, isCalling={is_calling}, snippet={repr(snippet)}")

            # Detect call answer:
            # 1. Timer found (e.g. 00:01)
            # 2. OR End call button is visible, ringing/calling text is gone, and at least 3 seconds elapsed
            call_answered = False
            if timer:
                call_answered = True
            elif has_end_btn and not is_ringing and not is_calling and elapsed > 3:
                call_answered = True

            if call_answered:
                if not self.intro_spoken:
                    self.intro_spoken = True
                    self.call_state = "connected"
                    logging.info(f"🎉 WhatsApp Voice Call ANSWERED by +{self.active_call_target}! Timer: {timer or 'active'}.")

                    # Deliver Sarah's intro ONCE into VirtualMic
                    intro_text = (
                        "Hi there! This is Sarah calling from Digital Growth Partners. "
                        "I am reaching out because we help businesses scale customer acquisition and automate operations with AI. "
                        "How are you doing today?"
                    )
                    self.active_call_transcript.append({"role": "assistant", "text": intro_text, "timestamp": time.time()})

                    intro_wav = os.path.join(BASE_DIR, "sarah_intro.wav")
                    if not os.path.exists(intro_wav):
                        live_voice_agent.synthesize_speech_to_wav(intro_text, intro_wav)

                    logging.info("🗣️ Delivering Sarah's opening pitch ONCE (zero looping)...")
                    self._play_speech_file(intro_wav)

                self.call_state = "connected"
                if timer:
                    parts = timer.split(":")
                    if len(parts) == 2:
                        self.call_duration = int(parts[0]) * 60 + int(parts[1])

            # Detect call end:
            should_end = False
            if self.call_state == "connected" and (is_ended or not has_end_btn):
                should_end = True
                logging.info(f"🛑 Connected call ended after {self.call_duration}s.")
            elif self.call_state in ("calling", "ringing") and is_ended:
                should_end = True
                logging.info("🛑 Call declined or ended while ringing.")
            elif self.call_state in ("calling", "ringing") and elapsed > 55:
                should_end = True
                logging.info("⏱️ Call ring timeout (55s exceeded without answer).")

            if should_end:
                self._stop_audio_listener()

                target = self.active_call_target
                answered = (self.call_duration > 0 or self.call_state == "connected")
                duration = self.call_duration
                transcript = list(self.active_call_transcript)

                # Reset state
                self.call_state = "idle"
                self.active_call_target = None
                self.intro_spoken = False
                self.active_call_transcript = []

                if target:
                    threading.Thread(target=self._on_call_finished, args=(target, answered, duration, transcript), daemon=True).start()

            return {
                "state": self.call_state,
                "target": self.active_call_target,
                "duration": self.call_duration,
                "timer": timer
            }
        except Exception as e:
            return {"state": self.call_state, "error": str(e)}

    def _play_speech_file(self, wav_path: str):
        """Plays speech file into VirtualMic sink via paplay. Interruptible upon caller barge-in."""
        try:
            self._stop_current_speech()
            env = os.environ.copy()
            env["PULSE_SERVER"] = "/var/run/pulse/native"
            self.player_proc = subprocess.Popen(
                ["paplay", "-d", "VirtualMic", wav_path],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logging.error(f"Error playing speech into VirtualMic: {e}")

    def _stop_current_speech(self):
        """Instantly stops active playback if caller interrupts/barges in."""
        if self.player_proc and self.player_proc.poll() is None:
            try:
                self.player_proc.terminate()
                self.player_proc.wait(timeout=0.2)
                logging.info("⚡ Active AI speech stopped (caller barge-in)!")
            except Exception:
                try:
                    self.player_proc.kill()
                except Exception:
                    pass
            self.player_proc = None

    def _start_audio_listener(self):
        """Starts background thread recording CallSpeaker.monitor to detect caller speech."""
        self.stop_audio_listener.clear()
        self.audio_listener_thread = threading.Thread(target=self._audio_listener_worker, daemon=True)
        self.audio_listener_thread.start()

    def _stop_audio_listener(self):
        """Stops background recording thread."""
        self.stop_audio_listener.set()
        self._stop_current_speech()

    def _audio_listener_worker(self):
        """Captures 16kHz PCM from CallSpeaker.monitor, runs VAD, and generates live replies."""
        logging.info("🎙️ PulseAudio Duplex Listener active on CallSpeaker.monitor...")
        env = os.environ.copy()
        env["PULSE_SERVER"] = "/var/run/pulse/native"

        cmd = [
            "parec", "-d", "CallSpeaker.monitor",
            "--rate=16000", "--channels=1", "--format=s16le"
        ]

        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        # 100ms at 16000Hz 16-bit mono = 1600 samples = 3200 bytes
        chunk_bytes = 3200
        speech_chunks = []
        is_speaking = False
        silence_count = 0
        threshold = 500.0  # RMS speech threshold
        last_monitor_log = time.time()

        try:
            while not self.stop_audio_listener.is_set():
                raw = proc.stdout.read(chunk_bytes)
                if not raw or len(raw) < chunk_bytes:
                    break

                samples = np.frombuffer(raw, dtype=np.int16)
                rms = float(np.sqrt(np.mean(samples.astype(np.float32)**2)))

                # Periodic heartbeat log every 3 seconds
                if time.time() - last_monitor_log > 3.0:
                    last_monitor_log = time.time()
                    logging.info(f"🎙️ [In-Call Audio Heartbeat] RMS: {round(rms, 1)} (is_speaking={is_speaking}, intro_spoken={self.intro_spoken})")

                if rms > threshold:
                    if not is_speaking:
                        is_speaking = True
                        silence_count = 0
                        logging.info(f"🎙️ CALLER VOICE DETECTED! RMS: {round(rms, 1)}")

                        # If call was not yet marked connected, caller voice confirms answer!
                        if not self.intro_spoken:
                            self.intro_spoken = True
                            self.call_state = "connected"
                            logging.info(f"🎉 WhatsApp Voice Call ANSWERED by caller speech detection on CallSpeaker.monitor!")

                        # Caller spoke: immediately interrupt Sarah if she was speaking
                        self._stop_current_speech()
                        speech_chunks = [raw]
                    else:
                        speech_chunks.append(raw)
                        silence_count = 0
                else:
                    if is_speaking:
                        speech_chunks.append(raw)
                        silence_count += 1
                        # 600ms silence = 6 chunks of 100ms
                        if silence_count >= 6:
                            is_speaking = False
                            silence_count = 0
                            total_bytes = b"".join(speech_chunks)
                            speech_chunks = []

                            # Only process if caller spoke for at least 0.25s (4000 bytes)
                            if len(total_bytes) >= 4000:
                                threading.Thread(target=self._handle_caller_utterance, args=(total_bytes,), daemon=True).start()

        except Exception as e:
            logging.error(f"Error in audio listener loop: {e}")
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                pass
            logging.info("🛑 PulseAudio Duplex Listener stopped.")

    def _handle_caller_utterance(self, pcm_bytes: bytes):
        """Transcribes caller PCM, queries Moonmath DeepSeek, and speaks reply into call."""
        if not self.call_state in ("connected", "ringing"):
            return

        logging.info(f"🗣️ Transcribing caller speech chunk ({len(pcm_bytes)} bytes)...")
        user_text = live_voice_agent.transcribe_caller_pcm(pcm_bytes)
        if not user_text:
            logging.info("ℹ️ Whisper transcription returned no text (non-speech noise).")
            return

        logging.info(f"👤 CALLER SAID: \"{user_text}\"")
        self.active_call_transcript.append({"role": "user", "text": user_text, "timestamp": time.time()})

        # Generate intelligent contextual reply
        logging.info("🤖 Querying Moonmath DeepSeek for conversational reply...")
        reply_text = live_voice_agent.generate_conversational_reply(
            history=self.active_call_transcript,
            user_utterance=user_text,
            company_name="Target Business"
        )
        logging.info(f"🤖 SARAH GENERATED: \"{reply_text}\"")
        self.active_call_transcript.append({"role": "assistant", "text": reply_text, "timestamp": time.time()})

        # Synthesize speech to WAV
        wav_file = live_voice_agent.synthesize_speech_to_wav(reply_text)
        if wav_file and self.call_state in ("connected", "ringing"):
            logging.info(f"🔊 Playing Sarah's reply back into call ({wav_file})...")
            self._play_speech_file(wav_file)

    def _on_call_finished(self, target_phone: str, answered: bool, duration: float, transcript: List[Dict[str, Any]]):
        """Persists complete call transcript to Omnichannel Memory and dispatches follow-ups."""
        logging.info(f"💾 Post-call processing for +{target_phone}: answered={answered}, duration={duration}s")
        try:
            pitch = "Sarah conducted a live conversational voice call via WhatsApp Web."
            if transcript:
                summary_turns = [f"{t['role'].capitalize()}: {t['text']}" for t in transcript]
                pitch = " | ".join(summary_turns[:3])

            memory.record_call(phone=target_phone, answered=answered, duration_seconds=duration, pitch_summary=pitch)

            # Send WhatsApp follow-up summary text via Line 1 (:3001)
            follow_up = (
                "Hi! Sarah here from Digital Growth Partners following up on our call just now. "
                "We help local businesses scale client acquisition and automate lead follow-ups with AI. "
                "Feel free to reply here if you have any questions or want to check out a quick demo!"
            )
            requests.post("http://127.0.0.1:3001/api/send-text", json={"to": target_phone, "text": follow_up}, timeout=15)
            memory.record_message(phone=target_phone, direction="outbound", text=follow_up, msg_type="text")

            # Also dispatch Voice Note summary
            voice_summary = (
                "Hi! Just leaving a quick voice note following our call. "
                "Whenever you have a moment, take a look at the message above. Have a great day!"
            )
            requests.post("http://127.0.0.1:3001/api/send-voice", json={"to": target_phone, "text": voice_summary}, timeout=20)
            logging.info(f"📨 WhatsApp follow-up delivered to +{target_phone}")
        except Exception as e:
            logging.error(f"Error during post-call follow-up: {e}")

    def _do_hangup(self) -> Dict[str, Any]:
        """Clicks the red end call button."""
        try:
            self._stop_audio_listener()
            end_btn = self.page.locator("[data-icon=\"x-circle\"], [data-icon=\"x\"], button[aria-label*=\"End call\" i]").first
            if end_btn.is_visible():
                end_btn.click()
                logging.info("🛑 Call ended by agent.")
            self.call_state = "idle"
            self.active_call_target = None
            return {"ok": True, "status": "idle"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # Public APIs
    def show_qr_code(self) -> bool:
        evt = threading.Event()
        box = [False]
        self.cmd_queue.put(("show_qr", None, evt, box))
        evt.wait(timeout=10)
        return box[0]

    def request_pairing_code(self) -> Optional[str]:
        evt = threading.Event()
        box = [None]
        self.cmd_queue.put(("request_code", None, evt, box))
        evt.wait(timeout=30)
        return box[0]

    def make_voice_call(self, target_phone: str) -> Dict[str, Any]:
        evt = threading.Event()
        box = [None]
        self.cmd_queue.put(("make_call", target_phone, evt, box))
        evt.wait(timeout=45)
        return box[0] or {"ok": False, "error": "Call request timed out"}

    def hangup(self) -> Dict[str, Any]:
        evt = threading.Event()
        box = [None]
        self.cmd_queue.put(("hangup", None, evt, box))
        evt.wait(timeout=10)
        return box[0] or {"ok": False, "error": "Hangup timed out"}

    def take_screenshot(self, path: str = "/var/www/omnicall-ai/browser-caller/screen.png") -> Optional[str]:
        evt = threading.Event()
        box = [None]
        self.cmd_queue.put(("screenshot", path, evt, box))
        evt.wait(timeout=10)
        return box[0]
