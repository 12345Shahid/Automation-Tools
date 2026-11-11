import asyncio
from pathlib import Path
import edge_tts
from content_engine import config

async def synthesize_voice(
    text: str,
    output_audio_path: str,
    voice: str = config.DEFAULT_VOICE,
    rate: str = "+4%", # slightly faster for viral shorts pacing
    pitch: str = "+0Hz"
) -> dict:
    """
    Synthesize text into speech with millisecond word timestamps.
    Returns:
        {
            "audio_path": str,
            "duration": float,
            "words": [
                {"word": str, "start": float, "end": float}
            ]
        }
    """
    comm = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        boundary="WordBoundary"
    )

    words = []
    audio_data = bytearray()

    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start_sec = chunk["offset"] / 10_000_000.0
            dur_sec = chunk["duration"] / 10_000_000.0
            words.append({
                "word": chunk["text"].strip(),
                "start": round(start_sec, 3),
                "end": round(start_sec + dur_sec, 3)
            })

    output_path = Path(output_audio_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    total_duration = words[-1]["end"] + 0.3 if words else 0.0

    return {
        "audio_path": str(output_path),
        "duration": total_duration,
        "words": words
    }

def generate_voice_sync(text: str, output_path: str, voice: str = config.DEFAULT_VOICE) -> dict:
    """Synchronous wrapper for synthesize_voice."""
    return asyncio.run(synthesize_voice(text, output_path, voice))
