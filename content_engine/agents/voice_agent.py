from pathlib import Path
from typing import Dict, Any
from content_engine import config
from content_engine.core.voice import generate_voice_sync

def synthesize_narration(
    script_text: str,
    output_audio_path: str,
    voice_key: str = "christopher"
) -> Dict[str, Any]:
    """
    Voice Agent: Synthesizes studio-grade neural voiceover and extracts
    millisecond word timestamps for kinetic subtitles and foley sync.
    """
    selected_voice = config.AVAILABLE_VOICES.get(voice_key.lower(), config.DEFAULT_VOICE)
    print(f"[VoiceAgent] Synthesizing voice using {selected_voice} ({len(script_text.split())} words)...")
    
    res = generate_voice_sync(
        text=script_text,
        output_path=output_audio_path,
        voice=selected_voice
    )
    print(f"[VoiceAgent] Narration generated: {res['duration']:.2f}s ({len(res['words'])} words timestamped)")
    return res
