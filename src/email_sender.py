import datetime
import json
import os
import random
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "email_sent_history.json"


class EmailSender:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
    ):
        self.host = host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.port = int(port or os.getenv("SMTP_PORT", 587))
        self.user = user or os.getenv("SMTP_USER", "")
        self.password = (password or os.getenv("SMTP_PASSWORD", "")).replace(" ", "")
        self.sender_name = sender_name or os.getenv("SENDER_NAME", "Shahid Hasan")
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", self.user)
        self._ensure_history_file()

    def _ensure_history_file(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not HISTORY_FILE.exists():
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def test_connection(self) -> Tuple[bool, str]:
        """Test SMTP server connectivity and authentication."""
        if not self.user or not self.password:
            return False, "SMTP_USER or SMTP_PASSWORD is not configured in .env"

        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
            return True, f"Connected & authenticated successfully as {self.user}"
        except Exception as e:
            return False, f"SMTP Authentication failed: {str(e)}"

    def get_history(self) -> List[Dict[str, Any]]:
        """Return all sent email logs."""
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def is_already_sent(self, to_email: str) -> bool:
        """Check if an email has already been sent to this recipient."""
        email_clean = to_email.strip().lower()
        history = self.get_history()
        for entry in history:
            if entry.get("to", "").strip().lower() == email_clean and entry.get("status") == "sent":
                return True
        return False

    def record_sent(self, to_email: str, subject: str, status: str, details: Optional[str] = None):
        """Record an email sending event in history."""
        history = self.get_history()
        record = {
            "to": to_email.strip(),
            "subject": subject,
            "status": status,
            "timestamp": datetime.datetime.now().isoformat(),
            "details": details or ""
        }
        history.append(record)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Send an email via SMTP.
        If `force` is False and the email was already contacted, skips sending.
        """
        to_clean = to_email.strip()
        if not to_clean:
            return {"success": False, "error": "Recipient email address is empty"}

        if not force and self.is_already_sent(to_clean):
            return {
                "success": False,
                "skipped": True,
                "error": f"Recipient {to_clean} was already contacted previously (duplicate safety check)."
            }

        if not self.user or not self.password:
            return {"success": False, "error": "SMTP credentials missing. Please check .env file."}

        # Build MIME Message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = to_clean
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")

        # Attach text part
        part_text = MIMEText(body_text, "plain", "utf-8")
        msg.attach(part_text)

        # Attach HTML part if provided
        if body_html:
            part_html = MIMEText(body_html, "html", "utf-8")
            msg.attach(part_html)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=25) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.user, self.password)
                server.send_message(msg)

            self.record_sent(to_clean, subject, "sent")
            return {"success": True, "to": to_clean, "subject": subject}
        except Exception as e:
            error_msg = str(e)
            self.record_sent(to_clean, subject, "failed", error_msg)
            return {"success": False, "to": to_clean, "error": error_msg}

    def send_batch(
        self,
        recipients: List[Dict[str, Any]],
        delay_range: Tuple[int, int] = (6, 14),
        force: bool = False,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Send emails to a list of recipients with random delay between sends.
        Each recipient item is a dict with: 'email', 'subject', 'body_text', 'body_html'
        """
        results = {"sent": 0, "skipped": 0, "failed": 0, "details": []}

        for i, item in enumerate(recipients):
            email = item.get("email")
            subject = item.get("subject", "Quick question")
            body_text = item.get("body_text", "")
            body_html = item.get("body_html")

            status = self.send_email(email, subject, body_text, body_html, force=force)
            results["details"].append(status)

            if status.get("success"):
                results["sent"] += 1
            elif status.get("skipped"):
                results["skipped"] += 1
            else:
                results["failed"] += 1

            if on_progress:
                on_progress({
                    "current": i + 1,
                    "total": len(recipients),
                    "item": status
                })

            # Safe delay between emails if there are more to send
            if i < len(recipients) - 1:
                sleep_time = random.uniform(delay_range[0], delay_range[1])
                time.sleep(sleep_time)

        return results
