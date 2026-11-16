#!/usr/bin/env python3
"""
WhatsApp Web Persistent Browser Calling Agent (browser_agent.py)
Automates Google Chrome on web.whatsapp.com:
1. Generates 8-digit pairing code via "Log in with phone number".
2. Uses a single dedicated background thread for 100% Playwright thread-safety.
3. Maintains persistent profile so login state is saved permanently.
4. Clicks the native WhatsApp Web Voice Call button and manages calls.
"""

import os
import sys
import time
import queue
import logging
import threading
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright, BrowserContext, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
                    cmd, args, result_event, result_box = self.cmd_queue.get(timeout=3.0)
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
                except queue.Empty:
                    # Periodic heartbeat: check if login completed
                    if not self.is_connected and self._check_if_logged_in():
                        self.is_connected = True
                        self.pairing_code = None
                        logging.info("🎉 Handshake complete! WhatsApp Web is now CONNECTED and saved to disk!")

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
            # 1. Wait for canvas or login elements
            self.page.wait_for_selector("canvas", timeout=30000)
            time.sleep(2)

            # 2. Click "Log in with phone number"
            btn = self.page.locator("text=Log in with phone number").first
            if btn.is_visible():
                box = btn.bounding_box()
                if box:
                    self.page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                else:
                    btn.click(force=True)
                time.sleep(3)

            # 3. Open country selector
            c_btn = self.page.locator("button, [role=\"button\"]").filter(has_text="Burma").first
            if not c_btn.is_visible():
                c_btn = self.page.locator("div").filter(has_text="Myanmar (Burma)").last
            
            c_box = c_btn.bounding_box()
            if c_box:
                self.page.mouse.click(c_box["x"] + c_box["width"]/2, c_box["y"] + c_box["height"]/2)
            else:
                c_btn.click(force=True)
            time.sleep(1.5)

            # 4. Search and select Bangladesh
            self.page.keyboard.type("Bangladesh", delay=40)
            time.sleep(1)
            bd_item = self.page.locator("text=Bangladesh").last
            bd_item.click(force=True)
            time.sleep(1.5)

            # 5. Type phone number
            inp = self.page.locator("[data-testid=\"phone-number-input\"]")
            inp.click()
            self.page.keyboard.type(self.local_number, delay=40)
            time.sleep(1)

            # 6. Click Next
            next_btn = self.page.locator("button:has-text(\"Next\")").first
            next_btn.click(force=True)
            time.sleep(5)

            # 7. Extract the 8-digit code from DOM
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
                logging.info(f"\n========================================================")
                logging.info(f"📱 WHATSAPP WEB 8-DIGIT PAIRING CODE FOR +880 {self.local_number}:")
                logging.info(f"👉   {formatted_code}   👈")
                logging.info(f"========================================================\n")
                return formatted_code
            else:
                logging.warning(f"Extracted incomplete code: '{code}'. Retrying...")
        except Exception as e:
            logging.error(f"❌ Error during pairing code request: {e}")
        return None

    def _do_make_call(self, target_phone: str) -> Dict[str, Any]:
        """Navigates to the recipient's chat and clicks the native WhatsApp Voice Call button."""
        clean_target = target_phone.replace("+", "").replace(" ", "").replace("-", "")
        if not self.is_connected:
            return {"ok": False, "error": "WhatsApp Web is not authenticated yet. Please pair first."}

        logging.info(f"📞 Opening chat with +{clean_target} to place voice call...")
        self.call_state = "calling"
        self.active_call_target = clean_target

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
                    "status": "calling",
                    "target": clean_target,
                    "message": f"Voice call initiated to +{clean_target}"
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

    # Public API called from Flask (thread-safe queue dispatch)
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
