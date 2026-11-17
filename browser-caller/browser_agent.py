#!/usr/bin/env python3
"""
WhatsApp Web Persistent Browser Calling Agent (browser_agent.py)
Automates Google Chrome on web.whatsapp.com:
1. Generates 8-digit pairing code via "Log in with phone number".
2. Uses a single dedicated background thread for 100% Playwright thread-safety.
3. Maintains persistent profile so login state is saved permanently.
4. Clicks the native WhatsApp Web Voice Call button and manages calls.
5. Injects Sarah's crystal-clear English voice into the call via Chromium fake audio capture.
6. Tracks call duration and answered status in real-time.
7. Automatically persists call logs and dispatches follow-ups to Omnichannel Memory.
"""

import os
import sys
import time
import queue
import logging
import threading
import requests
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright, BrowserContext, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

SARAH_AUDIO_WAV = os.path.join(BASE_DIR, "sarah_intro.wav")

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
        self.call_overlay_detected = False
        self.call_duration = 0.0
        
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._ready_event = threading.Event()

    def run(self):
        """Dedicated Playwright thread worker."""
        logging.info(f"🌐 Launching Chrome with persistent profile at {PROFILE_DIR}...")
        with sync_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={SARAH_AUDIO_WAV}",
                "--autoplay-policy=no-user-gesture-required",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]

            self.context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                executable_path="/usr/bin/google-chrome",
                headless=self.headless,
                viewport={"width": 1440, "height": 1200},
                args=launch_args
            )

            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.goto("https://web.whatsapp.com", timeout=60000, wait_until="domcontentloaded")
            time.sleep(8)

            # Check if already authenticated
            if self._check_if_logged_in():
                self.is_connected = True
                self.pairing_code = None
                logging.info("✅ WhatsApp Web already authenticated and logged in!")
            else:
                # Trigger pairing code request
                self._do_request_pairing_code()

            self._ready_event.set()

            # Main event loop for thread
            while True:
                try:
                    cmd, args, result_event, result_box = self.cmd_queue.get(timeout=2.0)
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
                    elif cmd == "check_call_status":
                        res = self._check_active_call_in_page()
                        result_box[0] = res
                        result_event.set()
                except queue.Empty:
                    # Periodic heartbeat: check if login completed
                    if not self.is_connected and self._check_if_logged_in():
                        self.is_connected = True
                        self.pairing_code = None
                        logging.info("🎉 Handshake complete! WhatsApp Web is now CONNECTED and saved to disk!")
                    
                    # If call is currently active, monitor its status
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

    def _do_request_pairing_code(self) -> Optional[str]:
        """Automates the 'Log in with phone number' flow on the Playwright thread."""
        logging.info(f"🔑 Requesting 8-digit pairing code for +880 {self.local_number}...")
        try:
            self.page.wait_for_selector("canvas", timeout=30000)
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
        self.call_overlay_detected = False
        self.call_duration = 0.0

        try:
            chat_url = f"https://web.whatsapp.com/send?phone={clean_target}"
            self.page.goto(chat_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(6)

            call_selectors = [
                "button[aria-label*=\"Audio call\" i]",
                "button[aria-label*=\"Voice call\" i]",
                "span[data-icon=\"phone\"]",
                "span[data-icon=\"phone-outline\"]",
                "button[title*=\"call\" i]"
            ]

            call_btn = None
            for sel in call_selectors:
                btn = self.page.locator(sel).first
                if btn.is_visible():
                    call_btn = btn
                    logging.info(f"Found call button via selector: {sel}")
                    break

            if not call_btn:
                header_buttons = self.page.locator("header button, header [role=\"button\"]").all()
                for hb in header_buttons:
                    html = hb.evaluate("el => el.outerHTML")
                    if "call" in html.lower() or "phone" in html.lower():
                        call_btn = hb
                        logging.info("Found call button in chat header!")
                        break

            if call_btn:
                call_btn.click()
                self.call_state = "ringing"
                logging.info(f"✅ Clicked WhatsApp Voice Call button! Calling +{clean_target}...")
                return {
                    "ok": True,
                    "status": "ringing",
                    "target": clean_target,
                    "message": f"Voice call initiated to +{clean_target}. Sarah will speak when answered!"
                }
            else:
                self.call_state = "idle"
                logging.warning(f"⚠️ Voice call button not found in chat header for +{clean_target}")
                return {
                    "ok": False,
                    "error": "Voice call button not present in this chat header."
                }
        except Exception as e:
            self.call_state = "idle"
            logging.error(f"❌ Error placing voice call: {e}")
            return {"ok": False, "error": str(e)}

    def _check_active_call_in_page(self) -> Dict[str, Any]:
        """Monitors the active in-call DOM status, duration timer, and call completion."""
        try:
            if not self.page:
                return {"state": self.call_state}

            status_info = self.page.evaluate("""() => {
                const endBtn = document.querySelector('[data-icon="x-circle"], [data-icon="x"], button[aria-label*="End call" i], button[title*="End call" i]');
                if (!endBtn) {
                    return { hasEndBtn: false, timer: null, isRinging: false, isCalling: false, isEnded: false };
                }

                // Scope strictly to the call container hosting the end button
                let container = endBtn.closest('[role="dialog"], [data-testid*="call"], [class*="call"]') || endBtn.parentElement.parentElement.parentElement;
                const textNodes = Array.from(container.querySelectorAll('span, div, p')).map(e => e.innerText || '').filter(t => t.length < 30);
                
                const timer = textNodes.find(t => /^\\d{1,2}:\\d{2}$/.test(t.trim()));
                const allText = textNodes.join(' ').toLowerCase();
                const isRinging = allText.includes('ringing');
                const isCalling = allText.includes('calling');
                const isEnded = allText.includes('ended');

                return { timer: timer || null, isRinging, isCalling, isEnded, hasEndBtn: true };
            }""")

            timer = status_info.get("timer")
            has_end_btn = status_info.get("hasEndBtn")
            is_ended = status_info.get("isEnded")
            is_ringing = status_info.get("isRinging")
            is_calling = status_info.get("isCalling")

            elapsed = time.time() - (self.call_start_time or time.time())

            if has_end_btn or is_ringing or is_calling or timer:
                self.call_overlay_detected = True

            if timer:
                if self.call_state != "connected":
                    logging.info(f"🎉 WhatsApp Voice Call ANSWERED by +{self.active_call_target}! Timer: {timer}. Sarah speaking...")
                self.call_state = "connected"
                # Parse timer string MM:SS
                parts = timer.split(":")
                if len(parts) == 2:
                    self.call_duration = int(parts[0]) * 60 + int(parts[1])

            elif is_ended or (self.call_overlay_detected and not has_end_btn) or (elapsed > 20 and not self.call_overlay_detected):
                logging.info(f"🛑 Call with +{self.active_call_target} has finished. Total duration: {self.call_duration}s")
                target = self.active_call_target
                answered = (self.call_duration > 0 or self.call_state == "connected")
                duration = self.call_duration
                
                # Reset state
                self.call_state = "idle"
                self.active_call_target = None
                self.call_overlay_detected = False
                
                # Trigger post-call actions in background thread
                if target:
                    threading.Thread(target=self._on_call_finished, args=(target, answered, duration), daemon=True).start()

            return {
                "state": self.call_state,
                "target": self.active_call_target,
                "duration": self.call_duration,
                "timer": timer
            }
        except Exception as e:
            return {"state": self.call_state, "error": str(e)}

    def _on_call_finished(self, target_phone: str, answered: bool, duration: float):
        """Persists call record and dispatches WhatsApp follow-up."""
        logging.info(f"💾 Post-call processing for +{target_phone}: answered={answered}, duration={duration}s")
        try:
            sys.path.insert(0, "/var/www/omnicall-ai")
            from omnichannel_memory import memory
            pitch = (
                "Sarah called and introduced Digital Growth Partners AI customer acquisition systems. "
                "Thanked lead and offered automated outreach demo."
            )
            memory.record_call(phone=target_phone, answered=answered, duration_seconds=duration, pitch_summary=pitch)

            # Send WhatsApp follow-up summary text via Line 1 (:3001)
            follow_up = (
                "Hi! Sarah here from Digital Growth Partners following up on our call just now. "
                "We help local businesses scale client acquisition and automate lead follow-ups with AI. "
                "Feel free to reply here if you have any questions or want to check out a quick demo!"
            )
            res = requests.post("http://127.0.0.1:3001/api/send-text", json={"to": target_phone, "text": follow_up}, timeout=15)
            if res.status_code == 200:
                memory.record_message(phone=target_phone, direction="outbound", text=follow_up, msg_type="text")
                logging.info(f"📨 WhatsApp follow-up delivered to +{target_phone}")

            # Also dispatch Voice Note summary
            voice_summary = (
                "Hi! Just leaving a quick voice note following our call. "
                "Whenever you have a moment, take a look at the message above. Have a great day!"
            )
            requests.post("http://127.0.0.1:3001/api/send-voice", json={"to": target_phone, "text": voice_summary}, timeout=20)
        except Exception as e:
            logging.error(f"Error during post-call follow-up: {e}")

    def _do_hangup(self) -> Dict[str, Any]:
        """Clicks the red end call button."""
        try:
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
