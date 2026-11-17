#!/usr/bin/env python3
"""
OmniCall Inbound Memory Agent (inbound_memory_agent.py)
Listens on port 3003 (or called directly).
Processes incoming WhatsApp messages & voice notes from leads:
1. Filters protected personal numbers (decoy persona).
2. Transcribes voice notes via faster-whisper.
3. Retrieves entire past interaction timeline (calls + texts).
4. Formulates human-like contextual response via Moonmath DeepSeek.
5. Replies to lead via Baileys Gateway (:3001) as text or voice note.
6. Persists interaction into Omnichannel Memory & Supabase.
"""

import os
import json
import base64
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify

from omnichannel_memory import memory, normalize_phone, is_protected

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
PORT = int(os.environ.get("INBOUND_AGENT_PORT", 3003))

MOONMATH_API_KEY = os.environ.get("MOONMATH_API_KEY", "sk-aouefxQmocFFTlrraydMTQ")
MOONMATH_BASE_URL = os.environ.get("MOONMATH_BASE_URL", "https://zro.moonmath.ai/v1")
MOONMATH_MODEL = os.environ.get("MOONMATH_MODEL", "deepseek-v4.1-flash")

BAILEYS_GATEWAY_URL = os.environ.get("BAILEYS_GATEWAY_URL", "http://127.0.0.1:3001")

whisper_model = None

def get_whisper():
    global whisper_model
    if whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logging.info("⏳ Loading faster-whisper tiny.en model for instant voice note transcription...")
            whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logging.info("✅ Faster-whisper model ready!")
        except Exception as e:
            logging.error(f"❌ Failed to load faster-whisper: {e}")
    return whisper_model


def transcribe_audio_file(audio_path: str) -> str:
    """Transcribes incoming WhatsApp voice note into text."""
    wm = get_whisper()
    if not wm:
        return "[Voice note received]"
    try:
        segments, info = wm.transcribe(audio_path, beam_size=5)
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        logging.info(f"🎙️ Transcribed voice note ({info.language}): \"{text}\"")
        return text or "[Inaudible voice note]"
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        return "[Voice note could not be transcribed]"


def generate_sarah_reply(phone: str, user_message: str, is_voice: bool = False) -> str:
    """Generates a human-like, memory-aware reply using Moonmath DeepSeek."""
    clean = normalize_phone(phone)
    history_context = memory.build_llm_context(clean)

    system_prompt = (
        "You are Sarah, Senior Client Outreach Specialist at Digital Growth Partners.\n"
        "You are chatting directly with a prospective business lead on WhatsApp.\n\n"
        f"{history_context}\n\n"
        "RESPONSE RULES:\n"
        "1. Sound completely human, friendly, polite, and natural. Never sound robotic or generic.\n"
        "2. Directly answer their specific question or acknowledge what they said.\n"
        "3. Naturally reference prior context (e.g. the phone call you made earlier or previous messages) to demonstrate authentic relationship memory.\n"
        "4. Keep it concise: strictly 2 to 3 sentences maximum.\n"
        "5. Language: English ONLY. Never output non-English text.\n"
        "6. Never say you are an AI, language model, or virtual assistant."
    )

    url = f"{MOONMATH_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {MOONMATH_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OmniCall/1.0"
    }
    payload = {
        "model": MOONMATH_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 250
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            reply = data["choices"][0]["message"]["content"].strip()
            return reply
        else:
            logging.error(f"Moonmath API returned HTTP {res.status_code}: {res.text}")
    except Exception as e:
        logging.error(f"Error querying Moonmath LLM: {e}")

    # Fallback response if LLM API is temporarily unreachable
    return "Hi! Thanks for reaching out. Following up from our call earlier, our AI client acquisition systems start at $299/mo and automate both voice calls and WhatsApp follow-ups. Would you like me to send over a quick 2-minute overview video?"


def dispatch_whatsapp_reply(phone: str, text: str, as_voice_note: bool = False) -> bool:
    """Delivers the response back to the contact via Baileys Line 1."""
    clean = normalize_phone(phone)
    if as_voice_note:
        url = f"{BAILEYS_GATEWAY_URL}/api/send-voice"
        payload = {"to": clean, "text": text}
    else:
        url = f"{BAILEYS_GATEWAY_URL}/api/send-text"
        payload = {"to": clean, "text": text}

    try:
        res = requests.post(url, json=payload, timeout=20)
        if res.status_code == 200 and res.json().get("ok"):
            logging.info(f"🚀 Delivered reply to +{clean} via Line 1 (type={'voice_note' if as_voice_note else 'text'})")
            return True
        else:
            logging.error(f"Failed to dispatch via Baileys: {res.text}")
    except Exception as e:
        logging.error(f"Error calling Baileys dispatch: {e}")
    return False


@app.route("/api/inbound", methods=["POST"])
def handle_inbound():
    data = request.get_json(silent=True) or {}
    sender = data.get("from") or data.get("sender") or ""
    msg_type = data.get("type", "text")
    incoming_text = data.get("text", "")
    audio_base64 = data.get("audio_base64")

    if not sender:
        return jsonify({"ok": False, "error": "Missing 'from' parameter"}), 400

    clean_phone = normalize_phone(sender)

    # 1. Decoy safety check: NEVER auto-reply to protected personal numbers
    if is_protected(clean_phone):
        logging.info(f"🛡️ Protected contact {clean_phone} received message. Bypassing auto-reply.")
        return jsonify({"ok": True, "action": "ignored_protected"})

    # 2. Process voice note if received
    is_voice = (msg_type == "voice" or bool(audio_base64))
    if is_voice and audio_base64:
        temp_audio = f"/tmp/inbound_{int(datetime.now().timestamp())}.ogg"
        try:
            with open(temp_audio, "wb") as f:
                f.write(base64.b64decode(audio_base64))
            transcribed = transcribe_audio_file(temp_audio)
            incoming_text = transcribed
            try:
                os.remove(temp_audio)
            except Exception:
                pass
        except Exception as e:
            logging.error(f"Error decoding inbound audio: {e}")
            incoming_text = "[Voice Note]"

    if not incoming_text:
        return jsonify({"ok": False, "error": "No message text or audio provided"}), 400

    logging.info(f"📩 [Processing Inbound] From +{clean_phone} ({'Voice Note' if is_voice else 'Text'}): \"{incoming_text}\"")

    # 3. Save incoming turn to Omnichannel Memory
    memory.record_message(
        phone=clean_phone,
        direction="inbound",
        text=incoming_text,
        msg_type="voice_note" if is_voice else "text"
    )

    # 4. Generate Sarah's human-like response
    sarah_reply = generate_sarah_reply(phone=clean_phone, user_message=incoming_text, is_voice=is_voice)
    logging.info(f"✨ [Sarah Generated Reply for +{clean_phone}]: \"{sarah_reply}\"")

    # 5. Dispatch reply via WhatsApp Line 1
    reply_as_voice = is_voice
    dispatched = dispatch_whatsapp_reply(phone=clean_phone, text=sarah_reply, as_voice_note=reply_as_voice)

    # 6. Save outbound turn to Omnichannel Memory
    memory.record_message(
        phone=clean_phone,
        direction="outbound",
        text=sarah_reply,
        msg_type="voice_note" if reply_as_voice else "text"
    )

    return jsonify({
        "ok": True,
        "phone": clean_phone,
        "incoming": incoming_text,
        "reply": sarah_reply,
        "reply_type": "voice_note" if reply_as_voice else "text",
        "dispatched": dispatched
    })


if __name__ == "__main__":
    logging.info(f"🚀 Starting OmniCall Inbound Memory Agent on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
