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


def decode_audio_bytes_to_pcm(audio_bytes: bytes) -> np.ndarray:
    """Uses ffmpeg to decode any audio container (WebM, OGG, WAV) into 16kHz float32 PCM."""
    cmd = [
        "ffmpeg", "-v", "quiet",
        "-i", "pipe:0",
        "-f", "f32le",
        "-ar", "16000",
        "-ac", "1",
        "pipe:1"
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate(input=audio_bytes)
    return np.frombuffer(out, np.float32)


def transcribe_caller_audio(base64_audio: str) -> Optional[str]:
    """Transcribes caller's recorded speech chunk from browser."""
    try:
        raw_bytes = base64.b64decode(base64_audio)
        if len(raw_bytes) < 1000:
            return None

        pcm = decode_audio_bytes_to_pcm(raw_bytes)
        if len(pcm) < 4000:  # Less than 0.25s of audio
            return None

        model = get_whisper()
        if not model:
            return None

        segments, _ = model.transcribe(pcm, beam_size=1, condition_on_previous_text=False)
        text = " ".join([s.text.strip() for s in segments]).strip()
        
        # Clean text
        if len(text) < 2 or text.lower() in ("you", "thank you.", "bye", "hmm", "yeah"):
            # Minimal filler, check length
            if len(text) < 2:
                return None

        logging.info(f"🗣️ [Caller Spoke]: \"{text}\"")
        return text
    except Exception as e:
        logging.error(f"Error transcribing caller audio: {e}")
        return None


def generate_conversational_reply(history: List[Dict[str, str]], user_utterance: str, company_name: str = "") -> str:
    """Generates natural Sarah conversational reply for the live phone call."""
    system_prompt = (
        "You are Sarah, a warm, professional, and friendly representative from Digital Growth Partners on a LIVE PHONE CALL with a business owner.\\n"
        "GOAL: You are reaching out to offer a free custom 24/7 AI Lead Assistant package for their business (handling WhatsApp text & voice, and calls so they never lose jobs).\\n"
        "CRITICAL RULES:\\n"
        "1. Spoken conversation pace: Keep your response strictly to 1 or 2 natural, concise sentences.\\n"
        "2. Sound completely human, authentic, and attentive. Never sound robotic or scripted.\\n"
        "3. Directly answer whatever the caller just asked or said.\\n"
        "4. Language: English ONLY. Never output any other language.\\n"
        "5. Never say you are an AI model or virtual assistant."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-4:]:  # Keep recent context
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
        "max_tokens": 120
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"].strip()
            # Clean markdown artifacts if any
            reply = reply.replace("**", "").replace('"', '').strip()
            logging.info(f"✨ [Sarah Spoke]: \"{reply}\"")
            return reply
    except Exception as e:
        logging.error(f"Error querying LLM: {e}")

    # Natural conversational fallback
    return "We build automated AI systems that handle WhatsApp messages and customer calls 24/7. Would it be okay if I sent you a quick 2-minute video over WhatsApp so you can take a look?"


def synthesize_speech_wav(text: str) -> Optional[str]:
    """Synthesizes text to 48kHz mono PCM WAV and returns base64 encoded audio."""
    temp_base = f"/tmp/sarah_turn_{int(time.time() * 1000)}"
    mp3_file = f"{temp_base}.mp3"
    wav_file = f"{temp_base}.wav"

    try:
        # 1. Edge-TTS synthesis
        subprocess.run(
            ["edge-tts", "--voice", VOICE_NAME, "--text", text, "--write-media", mp3_file],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 2. Convert to standard 48kHz mono 16-bit PCM WAV for Web Audio playback
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_file, "-ar", "48000", "-ac", "1", wav_file],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 3. Read and encode to base64
        with open(wav_file, "rb") as f:
            wav_bytes = f.read()

        # Cleanup temp files
        try:
            os.remove(mp3_file)
            os.remove(wav_file)
        except Exception:
            pass

        return base64.b64encode(wav_bytes).decode("utf-8")
    except Exception as e:
        logging.error(f"Error synthesizing speech: {e}")
        return None
