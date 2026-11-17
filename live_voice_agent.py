#!/usr/bin/env python3
"""
Real-Time Conversational Voice Agent (live_voice_agent.py)
Provides instant speech recognition, conversational reasoning, and voice synthesis
for live WhatsApp browser calls.
"""

import os
import time
import base64
import logging
import requests
import subprocess
import numpy as np
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MOONMATH_API_KEY = os.environ.get("MOONMATH_API_KEY", "sk-aouefxQmocFFTlrraydMTQ")
MOONMATH_BASE_URL = os.environ.get("MOONMATH_BASE_URL", "https://zro.moonmath.ai/v1")
MOONMATH_MODEL = os.environ.get("MOONMATH_MODEL", "deepseek-v4.1-flash")

VOICE_NAME = "en-US-AriaNeural"

_whisper_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logging.info("⏳ Initializing faster-whisper tiny.en model...")
            _whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logging.info("✅ Faster-whisper ready!")
        except Exception as e:
            logging.error(f"❌ Failed to load faster-whisper: {e}")
    return _whisper_model


def transcribe_caller_pcm(pcm_bytes: bytes) -> Optional[str]:
    """Transcribes caller's 16kHz 16-bit mono PCM bytes in memory."""
    try:
        if len(pcm_bytes) < 4800:  # Less than 0.15s of audio
            return None

        # Convert 16-bit int PCM to normalized float32 (-1.0 to 1.0)
        pcm_float = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        model = get_whisper()
        if not model:
            return None

        t0 = time.time()
        segments, _ = model.transcribe(pcm_float, beam_size=1, condition_on_previous_text=False)
        text = " ".join([s.text.strip() for s in segments]).strip()
        dur = round((time.time() - t0) * 1000, 1)

        # Ignore tiny non-speech artifacts
        if len(text) < 2 or text.lower() in ("you", "thank you.", "bye", "hmm", "yeah", "uh", "um"):
            if len(text) < 2:
                return None

        logging.info(f"🗣️ [Caller Spoke ({dur}ms)]: \"{text}\"")
        return text
    except Exception as e:
        logging.error(f"Error transcribing caller PCM: {e}")
        return None


def generate_conversational_reply(history: List[Dict[str, str]], user_utterance: str, company_name: str = "your company") -> str:
    """Generates natural Sarah conversational reply for the live phone call."""
    system_prompt = (
        "You are Sarah, a warm, professional, and friendly representative from Digital Growth Partners on a LIVE PHONE CALL with a business owner.\n"
        "GOAL: You are reaching out to offer a free custom 24/7 AI Lead Assistant package for their business.\n"
        "CRITICAL RULES:\n"
        "1. Spoken conversation pace: Keep your response strictly to 1 or 2 natural, concise sentences (under 30 words).\n"
        "2. Sound completely human, authentic, and attentive. Never sound robotic or scripted.\n"
        "3. Directly answer whatever the caller just asked or said.\n"
        "4. Language: English ONLY. Never output any other language.\n"
        "5. Never say you are an AI model or virtual assistant.\n"
        "6. If the user asks who is this, say you are Sarah calling from Digital Growth Partners."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-4:]:
        messages.append({"role": turn["role"], "content": turn["text"]})
    messages.append({"role": "user", "content": user_utterance})

    url = f"{MOONMATH_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {MOONMATH_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OmniCall/1.0"
    }
    payload = {
        "model": MOONMATH_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }

    try:
        t0 = time.time()
        r = requests.post(url, headers=headers, json=payload, timeout=12)
        dur = round((time.time() - t0) * 1000, 1)
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"].strip()
            # Clean markdown artifacts if any
            reply = reply.replace("**", "").replace('"', '').strip()
            logging.info(f"✨ [Sarah Reply ({dur}ms)]: \"{reply}\"")
            return reply
    except Exception as e:
        logging.error(f"Error querying LLM: {e}")

    return "We build automated AI systems that handle WhatsApp messages and customer calls 24/7. Would it be okay if I sent you a quick demo over WhatsApp?"


def synthesize_speech_to_wav(text: str, out_wav_path: Optional[str] = None) -> Optional[str]:
    """Synthesizes text to a 16kHz mono 16-bit PCM WAV file for PulseAudio playback."""
    if not out_wav_path:
        out_wav_path = f"/tmp/sarah_turn_{int(time.time() * 1000)}.wav"
    temp_mp3 = f"{out_wav_path}.mp3"

    try:
        t0 = time.time()
        # 1. Edge-TTS synthesis to mp3
        subprocess.run(
            ["edge-tts", "--voice", VOICE_NAME, "--text", text, "--write-media", temp_mp3],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 2. Convert to standard 16kHz mono 16-bit PCM WAV for VirtualMic
        subprocess.run(
            ["ffmpeg", "-y", "-i", temp_mp3, "-ar", "16000", "-ac", "1", out_wav_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        dur = round((time.time() - t0) * 1000, 1)
        logging.info(f"🔊 Synthesized speech WAV in {dur}ms: {out_wav_path}")

        try:
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
        except Exception:
            pass

        return out_wav_path
    except Exception as e:
        logging.error(f"Error synthesizing speech to WAV: {e}")
        return None
