#!/usr/bin/env python3
"""
OmniCall Omnichannel Conversational Memory Engine (omnichannel_memory.py)
Maintains 100% persistent, human-like interaction history across:
- Browser Voice Calls (duration, status, intro pitch, transcript)
- WhatsApp Text Messages (inbound & outbound)
- WhatsApp Voice Notes (PTT audio recordings & transcripts)

Ensures that if a contact replies 30 minutes, 2 days, or 1 week later,
the agent recalls all context, previous conversations, and company details.
"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "omnichannel_memory.json")
LOCK = threading.Lock()

PROTECTED_NUMBERS = [
    "8801712394812",
    "01712394812",
    "+8801712394812"
]


def normalize_phone(phone: str) -> str:
    clean = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()
    if clean.endswith("@s.whatsapp.net"):
        clean = clean.replace("@s.whatsapp.net", "")
    if clean.startswith("0") and len(clean) == 11:
        clean = "88" + clean
    return clean


def is_protected(phone: str) -> bool:
    clean = normalize_phone(phone)
    for p in PROTECTED_NUMBERS:
        if normalize_phone(p) == clean:
            return True
    return False


class OmnichannelMemory:
    def __init__(self, filepath: str = MEMORY_FILE):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _read_all(self) -> Dict[str, Any]:
        with LOCK:
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error reading memory file: {e}")
                return {}

    def _save_all(self, data: Dict[str, Any]):
        with LOCK:
            try:
                temp_file = self.filepath + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, self.filepath)
            except Exception as e:
                logging.error(f"Error writing memory file: {e}")

    def get_contact_record(self, phone: str) -> Dict[str, Any]:
        clean = normalize_phone(phone)
        data = self._read_all()
        if clean in data:
            return data[clean]
        return {
            "phone": clean,
            "company_name": "Target Business",
            "contact_name": "Client",
            "status": "new",
            "created_at": datetime.now().isoformat(),
            "last_interaction_at": datetime.now().isoformat(),
            "history": []
        }

    def record_call(self, phone: str, answered: bool, duration_seconds: float, pitch_summary: str, company_name: str = "") -> Dict[str, Any]:
        clean = normalize_phone(phone)
        data = self._read_all()
        rec = data.get(clean, self.get_contact_record(clean))
        if company_name:
            rec["company_name"] = company_name

        now = datetime.now().isoformat()
        rec["last_interaction_at"] = now
        rec["status"] = "called_answered" if answered else "called_unanswered"

        event = {
            "id": f"call_{int(datetime.now().timestamp())}",
            "timestamp": now,
            "channel": "browser_voice_call",
            "direction": "outbound",
            "type": "call",
            "answered": answered,
            "duration_seconds": round(duration_seconds, 1),
            "pitch_summary": pitch_summary,
            "summary": f"Sarah placed a WhatsApp voice call ({'Answered' if answered else 'Unanswered'}, duration: {round(duration_seconds, 1)}s). Pitch: {pitch_summary}"
        }
        rec["history"].append(event)
        data[clean] = rec
        self._save_all(data)
        logging.info(f"💾 Recorded voice call for +{clean}: answered={answered}, duration={round(duration_seconds, 1)}s")

        # Sync to Supabase if available
        try:
            from supabase_db import sync_call_to_supabase
            sync_call_to_supabase(
                phone_number=f"+{clean}",
                company_name=rec.get("company_name", "Target Business"),
                picked_up=answered,
                duration_seconds=duration_seconds,
                outcome="answered" if answered else "unanswered",
                group_name="Browser Outreach",
                transcript=[{"role": "assistant", "text": pitch_summary, "timestamp": now}]
            )
        except Exception as e:
            logging.debug(f"Supabase sync notice: {e}")

        return event

    def record_message(self, phone: str, direction: str, text: str, msg_type: str = "text", company_name: str = "") -> Dict[str, Any]:
        clean = normalize_phone(phone)
        data = self._read_all()
        rec = data.get(clean, self.get_contact_record(clean))
        if company_name:
            rec["company_name"] = company_name

        now = datetime.now().isoformat()
        rec["last_interaction_at"] = now
        if direction == "inbound":
            rec["status"] = "in_conversation"

        event = {
            "id": f"msg_{int(datetime.now().timestamp())}_{direction}",
            "timestamp": now,
            "channel": "whatsapp_line_1",
            "direction": direction,
            "type": msg_type,
            "text": text,
            "summary": f"[{direction.upper()} {msg_type.upper()}] {text}"
        }
        rec["history"].append(event)
        data[clean] = rec
        self._save_all(data)
        logging.info(f"💾 Recorded {direction} message for +{clean}: \"{text[:40]}...\"")
        return event

    def build_llm_context(self, phone: str) -> str:
        clean = normalize_phone(phone)
        rec = self.get_contact_record(clean)
        history = rec.get("history", [])

        if not history:
            return "No previous interactions found for this contact. This is the start of the conversation."

        lines = [
            f"=== CONTACT INTERACTION HISTORY (+{clean}) ===",
            f"Company: {rec.get('company_name', 'Business Lead')}",
            f"Status: {rec.get('status', 'active')}",
            "Chronological Timeline of Past Events (Calls, Follow-ups, and Messages):"
        ]

        for idx, ev in enumerate(history, 1):
            ts = ev.get("timestamp", "").replace("T", " ")[:19]
            ch = ev.get("channel", "whatsapp")
            direction = ev.get("direction", "outbound")
            ev_type = ev.get("type", "message")

            if ev_type == "call":
                ans = "Answered" if ev.get("answered") else "Unanswered / Voicemail"
                dur = ev.get("duration_seconds", 0)
                pitch = ev.get("pitch_summary", "")
                lines.append(f"  {idx}. [{ts}] [OUTBOUND PHONE CALL] Outcome: {ans}, Duration: {dur}s | Pitch: {pitch}")
            elif direction == "outbound":
                txt = ev.get("text", "")
                lines.append(f"  {idx}. [{ts}] [SARAH OUTBOUND ({ev_type})]: \"{txt}\"")
            elif direction == "inbound":
                txt = ev.get("text", "")
                lines.append(f"  {idx}. [{ts}] [CLIENT INBOUND ({ev_type})]: \"{txt}\"")

        lines.append("=== END OF HISTORY ===")
        return "\n".join(lines)


memory = OmnichannelMemory()
