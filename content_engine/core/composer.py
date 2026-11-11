import os
import subprocess
from pathlib import Path
from content_engine import config
from content_engine.core.subtitles import generate_ass_subtitles, generate_pillow_subtitle_overlays
from content_engine.core.audio_mixer import mix_audio_track

def check_ffmpeg_filter(filter_name: str) -> bool:
    """Check if a specific filter is supported by the installed FFmpeg."""
    try:
        res = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True, check=True)
        return filter_name in res.stdout
    except Exception:
        return False

def render_scene_clip(image_path: str, duration: float, output_clip_path: str, zoom_in: bool = True) -> str:
    """
    Render a single scene image into a 1080x1920 30fps video clip with Ken Burns dynamic motion.
    """
    frames = int(duration * config.VIDEO_FPS)
    if frames < 15:
        frames = 15

    # Ken Burns slow cinematic zoom
    if zoom_in:
        zoom_expr = f"min(zoom+0.0018,1.22)"
    else:
        zoom_expr = f"if(eq(on,1),1.22,max(zoom-0.0018,1.0))"

    filter_str = (
        f"scale={config.VIDEO_WIDTH*2}:{config.VIDEO_HEIGHT*2}:force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH*2}:{config.VIDEO_HEIGHT*2},"
        f"zoompan=z='{zoom_expr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps={config.VIDEO_FPS}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", filter_str,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        str(output_clip_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return str(output_clip_path)

def compose_full_video(
    scene_images: list,
    scenes_data: list,
    voice_res: dict,
    work_dir: Path,
    output_mp4_path: str,
    bgm_volume: float = 0.12
) -> str:
    """
    Assemble the complete YouTube Short:
    1. Render scene motion clips
    2. Concatenate scene clips
    3. Mix narration voice with background music
    4. Burn kinetic animated subtitles
    5. Export final 1080x1920 MP4
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    total_duration = voice_res["duration"]
    num_scenes = len(scene_images)
    scene_dur = total_duration / num_scenes

    print(f"[Composer] Rendering {num_scenes} scene clips (duration ~{scene_dur:.2f}s each)...")
    clip_paths = []
    for i, img_path in enumerate(scene_images):
        clip_p = work_dir / f"clip_{i:02d}.mp4"
        # Alternate zoom in and zoom out for dynamic cuts
        zoom_in = (i % 2 == 0)
        render_scene_clip(img_path, scene_dur, str(clip_p), zoom_in=zoom_in)
        clip_paths.append(clip_p)

    # Concat clips
    concat_list = work_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve()}'\n")

    base_video = work_dir / "base_video.mp4"
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(base_video)
    ]
    subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Mix audio
    mixed_audio = work_dir / "mixed_audio.aac"
    print("[Composer] Mixing narration audio and background music...")
    mix_audio_track(
        voice_audio_path=voice_res["audio_path"],
        output_audio_path=str(mixed_audio),
        total_duration=total_duration,
        bgm_path=str(config.DEFAULT_BGM),
        bgm_volume=bgm_volume
    )

    # Subtitles
    out_mp4 = Path(output_mp4_path)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    has_ass = check_ffmpeg_filter(" ass ") or check_ffmpeg_filter(" subtitles ")
    if has_ass:
        print("[Composer] Burning kinetic subtitles using libass...")
        ass_file = work_dir / "subtitles.ass"
        generate_ass_subtitles(voice_res["words"], str(ass_file))
        # Burn ASS
        # Escape path for ffmpeg filter
        escaped_ass = str(ass_file.resolve()).replace(":", "\\:").replace("'", "\\'")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-i", str(mixed_audio),
            "-vf", f"ass='{escaped_ass}'",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out_mp4)
        ]
        subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[Composer] Using Pillow transparent PNG subtitle overlays...")
        pillow_cards = generate_pillow_subtitle_overlays(voice_res["words"], work_dir / "sub_cards")
        
        # Build overlay filter chain
        if not pillow_cards:
            # Just mux audio and video
            cmd_final = [
                "ffmpeg", "-y",
                "-i", str(base_video),
                "-i", str(mixed_audio),
                "-c:v", "copy",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_mp4)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            inputs = ["-i", str(base_video)]
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
                str(out_mp4)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[Composer] Video rendered successfully to: {out_mp4}")
    return str(out_mp4)
