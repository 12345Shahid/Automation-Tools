import subprocess
import json
from pathlib import Path
from content_engine import config
from content_engine.core.voice import generate_voice_sync
from content_engine.core.subtitles import generate_ass_subtitles, generate_pillow_subtitle_overlays
from content_engine.core.audio_mixer import mix_audio_track
from content_engine.core.composer import check_ffmpeg_filter

def probe_video(video_path: str) -> dict:
    """Extract width, height, duration, and aspect ratio of input video."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate:format=duration",
        "-of", "json",
        str(video_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)
    
    stream = info.get("streams", [{}])[0]
    fmt = info.get("format", {})
    
    width = int(stream.get("width", 1920))
    height = int(stream.get("height", 1080))
    
    # Duration priority
    dur_str = stream.get("duration") or fmt.get("duration") or "30.0"
    duration = float(dur_str)

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "is_vertical": height > width
    }

def transform_raw_video(
    raw_video_path: str,
    script_text: str,
    output_path: str,
    voice_key: str = "christopher",
    bgm_volume: float = 0.12
) -> dict:
    """
    Transforms a user's raw video recording into a viral short:
    1. Transcribes & generates polished neural studio voiceover
    2. Strips raw user voice
    3. Auto-formats video to 9:16 vertical (blurred backdrop for 16:9 recordings)
    4. Syncs video pacing to studio audio duration
    5. Burns kinetic word-jumping neon subtitles
    6. Mixes auto-ducked lofi background music
    """
    raw_file = Path(raw_video_path)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    work_dir = out_file.parent / f"work_{out_file.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Probe input video
    v_info = probe_video(str(raw_file))
    raw_duration = v_info["duration"]
    print(f"[RawEditor] Input: {v_info['width']}x{v_info['height']}, duration: {raw_duration:.2f}s, vertical: {v_info['is_vertical']}")

    # 2. Synthesize Studio Voiceover
    selected_voice = config.AVAILABLE_VOICES.get(voice_key.lower(), config.DEFAULT_VOICE)
    studio_audio = work_dir / "studio_voice.mp3"
    voice_res = generate_voice_sync(script_text, str(studio_audio), voice=selected_voice)
    target_duration = voice_res["duration"]
    print(f"[RawEditor] Studio voice generated: {target_duration:.2f}s ({len(voice_res['words'])} words)")

    # 3. Calculate Speed Factor to sync video pacing with voiceover
    # e.g., if user recorded 50s and voice is 40s, speed up video 1.25x
    if raw_duration > 3.0 and target_duration > 3.0:
        speed_factor = raw_duration / target_duration
        # Constrain speed factor between 0.8x and 1.6x for natural motion
        speed_factor = max(0.8, min(1.6, speed_factor))
    else:
        speed_factor = 1.0

    pts_factor = 1.0 / speed_factor
    print(f"[RawEditor] Sync speed factor: {speed_factor:.2f}x (pts={pts_factor:.3f})")

    # 4. Format video to 9:16 vertical
    # If video is horizontal (16:9), create blurred top/bottom background with sharp centered video
    if not v_info["is_vertical"]:
        video_filter = (
            f"[0:v]setpts={pts_factor:.4f}*PTS,scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},boxblur=20:5[bg];"
            f"[0:v]setpts={pts_factor:.4f}*PTS,scale={config.VIDEO_WIDTH}:-1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[vbase]"
        )
    else:
        # Already vertical: scale and center crop
        video_filter = (
            f"[0:v]setpts={pts_factor:.4f}*PTS,scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}[vbase]"
        )

    base_formatted_video = work_dir / "base_formatted.mp4"
    cmd_format = [
        "ffmpeg", "-y",
        "-i", str(raw_file),
        "-filter_complex", video_filter,
        "-map", "[vbase]",
        "-t", f"{target_duration:.3f}",
        "-an", # WIPE OUT USER'S RAW AUDIO
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        str(base_formatted_video)
    ]
    subprocess.run(cmd_format, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 5. Mix Studio Voice + Auto-Ducked BGM
    mixed_audio = work_dir / "mixed_audio.aac"
    mix_audio_track(
        voice_audio_path=str(studio_audio),
        output_audio_path=str(mixed_audio),
        total_duration=target_duration,
        bgm_path=str(config.DEFAULT_BGM),
        bgm_volume=bgm_volume
    )

    # 6. Burn Kinetic Subtitles
    has_ass = check_ffmpeg_filter(" ass ") or check_ffmpeg_filter(" subtitles ")
    if has_ass:
        print("[RawEditor] Burning kinetic subtitles using libass...")
        ass_file = work_dir / "subtitles.ass"
        generate_ass_subtitles(voice_res["words"], str(ass_file))
        escaped_ass = str(ass_file.resolve()).replace(":", "\\:").replace("'", "\\'")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(base_formatted_video),
            "-i", str(mixed_audio),
            "-vf", f"ass='{escaped_ass}'",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_file)
        ]
        subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[RawEditor] Burning kinetic subtitles using Pillow overlay cards...")
        pillow_cards = generate_pillow_subtitle_overlays(voice_res["words"], work_dir / "sub_cards")
        if not pillow_cards:
            cmd_final = [
                "ffmpeg", "-y",
                "-i", str(base_formatted_video),
                "-i", str(mixed_audio),
                "-c:v", "copy",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_file)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            inputs = ["-i", str(base_formatted_video)]
            filter_parts = []
            last_stream = "0:v"
            for idx, card in enumerate(pillow_cards):
                inputs.extend(["-i", card["path"]])
                input_idx = idx + 1
                out_stream = f"v{idx}"
                s = card["start"]
                e = card["end"]
                filter_parts.append(
                    f"[{last_stream}][{input_idx}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[{out_stream}]"
                )
                last_stream = out_stream

            filter_complex = ";".join(filter_parts)
            cmd_final = [
                "ffmpeg", "-y",
                *inputs,
                "-i", str(mixed_audio),
                "-filter_complex", filter_complex,
                "-map", f"[{last_stream}]",
                "-map", f"{len(pillow_cards)+1}:a",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "veryfast",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_file)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[RawEditor] Transformed video exported: {out_file}")
    return {
        "video_path": str(out_file),
        "duration": target_duration,
        "voice": selected_voice,
        "filename": out_file.name
    }
