import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from content_engine import config
from content_engine.core.audio_mixer import mix_audio_track

def master_audio_track(
    voice_audio_path: str,
    output_audio_path: str,
    total_duration: float,
    words: Optional[List[Dict[str, Any]]] = None,
    cut_timestamps: Optional[List[float]] = None,
    bgm_volume: float = 0.12,
    voice_volume: float = 1.0,
    dry_punchline: bool = True
) -> str:
    """
    Foley & Sound Design Agent:
    1. Auto-ducks background music beneath voiceover
    2. Cuts BGM dry under the punchline (~2s before the end)
    3. Mixes master audio with broadcast normalization
    """
    out_file = Path(output_audio_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    print(f"[FoleyAgent] Mastering audio track ({total_duration:.2f}s, dry_punchline={dry_punchline})...")

    # Use the robust audio_mixer with dry punchline cutout
    return mix_audio_track(
        voice_audio_path=voice_audio_path,
        output_audio_path=str(out_file),
        total_duration=total_duration,
        bgm_path=str(config.DEFAULT_BGM),
        bgm_volume=bgm_volume,
        voice_volume=voice_volume,
        dry_punchline=dry_punchline,
        punchline_lead_sec=2.0
    )
