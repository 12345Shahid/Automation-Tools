import subprocess
from pathlib import Path
from content_engine import config

def mix_audio_track(
    voice_audio_path: str,
    output_audio_path: str,
    total_duration: float,
    bgm_path: str = str(config.DEFAULT_BGM),
    bgm_volume: float = 0.12,
    voice_volume: float = 1.0,
    dry_punchline: bool = True,
    punchline_lead_sec: float = 2.0
) -> str:
    """
    Mix narration audio with auto-ducked background music, punchline dry cutout,
    and clean fade out.
    
    Jad MH / Editor V1 Technique:
    - BGM runs under voice
    - Mutes completely (dry drop) right before the punchline / final payoff (~2s before end)
    - Slams back or fades out smoothly for maximum punchline retention.
    """
    out_path = Path(output_audio_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fade_out_start = max(0.0, total_duration - 1.5)

    # If background music file does not exist, simply copy/re-encode voice
    if not Path(bgm_path).exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice_audio_path),
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return str(out_path)

    # Dry punchline cutout timing
    if dry_punchline and total_duration > 6.0:
        cut_start = max(1.0, total_duration - punchline_lead_sec)
        cut_end = max(cut_start + 0.1, total_duration - 0.4)
        # BGM volume is silenced between cut_start and cut_end
        bgm_filter = (
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},"
            f"volume='if(between(t,{cut_start:.2f},{cut_end:.2f}),0,{bgm_volume})':eval=frame,"
            f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.5[bgm];"
            f"[0:a]volume={voice_volume}[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        bgm_filter = (
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},"
            f"volume={bgm_volume},"
            f"afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.5[bgm];"
            f"[0:a]volume={voice_volume}[voice];"
            f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(voice_audio_path),
        "-i", str(bgm_path),
        "-filter_complex", bgm_filter,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path)
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(out_path)

