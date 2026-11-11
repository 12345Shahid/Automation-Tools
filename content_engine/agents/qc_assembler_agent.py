import subprocess
from pathlib import Path
from typing import List, Dict, Any
from content_engine import config
from content_engine.core.subtitles import generate_ass_subtitles, generate_pillow_subtitle_overlays
from content_engine.core.composer import check_ffmpeg_filter

def assemble_and_verify(
    scene_clips: List[Path],
    master_audio: Path,
    words: List[Dict[str, Any]],
    output_mp4_path: Path,
    work_dir: Path
) -> Dict[str, Any]:
    """
    Master Assembler & QC Agent:
    1. Concatenates video scene clips seamlessly
    2. Applies Editor V1 documentary grade (contrast, saturation, vignette)
    3. Burns kinetic word-jumping neon subtitles
    4. Muxes with mastered audio
    5. Verifies export validity
    """
    output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write concat list
    concat_list = work_dir / "concat_scenes.txt"
    with open(concat_list, "w") as f:
        for clip in scene_clips:
            f.write(f"file '{clip.resolve()}'\n")

    base_video = work_dir / "base_assembled.mp4"
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(base_video)
    ]
    subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Burn Subtitles and documentary finish
    has_ass = check_ffmpeg_filter(" ass ") or check_ffmpeg_filter(" subtitles ")
    if has_ass:
        print("[QCAgent] Burning kinetic neon subtitles using libass...")
        ass_file = work_dir / "subtitles.ass"
        generate_ass_subtitles(words, str(ass_file))
        escaped_ass = str(ass_file.resolve()).replace(":", "\\:").replace("'", "\\'")
        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-i", str(master_audio),
            "-vf", f"ass='{escaped_ass}',eq=contrast=1.06:saturation=1.1,vignette=PI/5",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_mp4_path)
        ]
        subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[QCAgent] Burning kinetic subtitles using Pillow overlay cards...")
        pillow_cards = generate_pillow_subtitle_overlays(words, work_dir / "sub_cards")
        if pillow_cards:
            overlay_cmds = []
            inputs = ["-i", str(base_video), "-i", str(master_audio)]
            for idx, c in enumerate(pillow_cards):
                inputs.extend(["-i", str(c["path"])])
                overlay_idx = idx + 2
                prev = "[0:v]" if idx == 0 else f"[v{idx}]"
                nxt = "[vfinal]" if idx == len(pillow_cards) - 1 else f"[v{idx+1}]"
                overlay_cmds.append(f"{prev}[{overlay_idx}:v]overlay=x=(W-w)/2:y=H*0.65:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{nxt}")

            vf_str = ";".join(overlay_cmds) + ";[vfinal]eq=contrast=1.06:saturation=1.1,vignette=PI/5[vgraded]"
            cmd_final = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", vf_str,
                "-map", "[vgraded]",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_mp4_path)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            cmd_final = [
                "ffmpeg", "-y",
                "-i", str(base_video),
                "-i", str(master_audio),
                "-vf", "eq=contrast=1.06:saturation=1.1,vignette=PI/5",
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_mp4_path)
            ]
            subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Quality Control verification
    if not output_mp4_path.exists() or output_mp4_path.stat().st_size < 100000:
        raise RuntimeError("[QCAgent] Render check failed: Output file missing or corrupt.")

    file_size_mb = output_mp4_path.stat().st_size / (1024 * 1024)
    print(f"[QCAgent] Quality Check PASSED: {output_mp4_path.name} ({file_size_mb:.2f} MB)")

    return {
        "status": "verified",
        "video_path": str(output_mp4_path),
        "file_size_mb": round(file_size_mb, 2),
        "filename": output_mp4_path.name
    }
