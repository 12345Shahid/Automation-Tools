import subprocess
from pathlib import Path
from content_engine import config

def mix_audio_track(
    voice_audio_path: str,
    output_audio_path: str,
    total_duration: float,
    bgm_path: str = str(config.DEFAULT_BGM),
    bgm_volume: float = 0.12,
    voice_volume: float = 1.0
) -> str:
    """
    Mix narration audio with auto-ducked background music and clean fade out.
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

    # Loop BGM to total duration, lower volume to 12%, add fade-in/fade-out, and mix with voice
    filter_complex = (
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},"
        f"volume={bgm_volume},"
        f"afade=t=in:st=0:d=1,afade=t=out:st={fade_out_start}:d=1.5[bgm];"
        f"[0:a]volume={voice_volume}[voice];"
        f"[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(voice_audio_path),
        "-i", str(bgm_path),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path)
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(out_path)
