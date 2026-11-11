import os
import re
import json
import urllib.parse
import urllib.request
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
from content_engine import config

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

def search_pixabay_video(query: str, api_key: str) -> Optional[str]:
    """
    Search Pixabay free Video API for a 1080p stock clip with intelligent query simplification.
    Returns direct MP4 download URL or None.
    """
    if not api_key:
        return None

    # Construct search attempts: full query -> simplified keywords -> tech fallback
    queries_to_try = [query]
    clean_words = [w for w in re.sub(r'[^a-zA-Z0-9 ]', ' ', query).split() if len(w) > 2]
    if len(clean_words) > 3:
        queries_to_try.append(" ".join(clean_words[:3]))
        queries_to_try.append(" ".join(clean_words[-3:]))
    queries_to_try.append("technology abstract")

    for q in queries_to_try:
        try:
            encoded_q = urllib.parse.quote(q)
            url = f"https://pixabay.com/api/videos/?key={api_key}&q={encoded_q}&video_type=film&per_page=5"
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                hits = data.get("hits", [])
                if hits:
                    videos = hits[0].get("videos", {})
                    for res_key in ("large", "medium", "small", "tiny"):
                        v_info = videos.get(res_key, {})
                        mp4_url = v_info.get("url")
                        if mp4_url:
                            print(f"[BRollAgent] Found Pixabay clip for query '{q}'")
                            return mp4_url
        except Exception as e:
            continue
    return None

def download_video_clip(url: str, dest_path: Path) -> bool:
    """Download a direct video URL to file."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as resp, open(dest_path, "wb") as f:
            f.write(resp.read())
        return dest_path.exists() and dest_path.stat().st_size > 50000
    except Exception as e:
        print(f"[BRollAgent] Failed to download {url}: {e}")
        return False

def generate_fallback_motion_clip(
    query_text: str,
    duration: float,
    output_clip_path: Path,
    scene_idx: int = 0
) -> Path:
    """
    Synthesize an ultra-high-definition 1080x1920 animated visual card
    when external stock download is unavailable.
    """
    output_clip_path.parent.mkdir(parents=True, exist_ok=True)
    temp_img = output_clip_path.parent / f"still_{scene_idx:02d}.png"
    
    # Modern dark tech gradients
    gradients = [
        ((11, 19, 43), (28, 37, 65)),     # Deep cyber navy
        ((15, 23, 42), (30, 41, 59)),     # Slate gunmetal
        ((24, 18, 43), (48, 25, 52)),     # Cyber amethyst
        ((10, 25, 47), (23, 42, 69)),     # Oceanic terminal
        ((18, 18, 18), (35, 35, 35))      # Stealth obsidian
    ]
    bg_top, bg_bottom = gradients[scene_idx % len(gradients)]
    
    img = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color=bg_top)
    draw = ImageDraw.Draw(img)

    # Vertical gradient
    for y in range(config.VIDEO_HEIGHT):
        ratio = y / config.VIDEO_HEIGHT
        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
        draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(r, g, b))

    # Grid lines (Editor V1 aesthetic)
    for x in range(0, config.VIDEO_WIDTH, 120):
        draw.line([(x, 0), (x, config.VIDEO_HEIGHT)], fill=(255, 255, 255, 12), width=1)
    for y in range(0, config.VIDEO_HEIGHT, 120):
        draw.line([(0, y), (config.VIDEO_WIDTH, y)], fill=(255, 255, 255, 12), width=1)

    # Decorative cyber card in center
    card_w, card_h = 880, 500
    card_x = (config.VIDEO_WIDTH - card_w) // 2
    card_y = (config.VIDEO_HEIGHT - card_h) // 2
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=30,
        fill=(15, 23, 42, 220),
        outline=(0, 240, 255),
        width=3
    )

    # Try loading font
    try:
        font_large = ImageFont.truetype(str(config.DEFAULT_FONT), 46)
        font_sub = ImageFont.truetype(str(config.DEFAULT_FONT), 30)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.text((card_x + 50, card_y + 80), f"PHASE {scene_idx + 1}", fill=(0, 240, 255), font=font_sub)
    
    # Word wrap query
    words = query_text.upper().split()
    line1 = " ".join(words[:4])
    line2 = " ".join(words[4:8]) if len(words) > 4 else ""
    draw.text((card_x + 50, card_y + 150), line1, fill=(255, 255, 255), font=font_large)
    if line2:
        draw.text((card_x + 50, card_y + 220), line2, fill=(148, 163, 184), font=font_large)

    img.save(temp_img)

    # Animate still with slow push/zoom
    zoom_dir = "in" if scene_idx % 2 == 0 else "out"
    if zoom_dir == "in":
        vf = (
            f"scale=8000:-1,zoompan=z='min(zoom+0.0015,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps={config.VIDEO_FPS}"
        )
    else:
        vf = (
            f"scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps={config.VIDEO_FPS}"
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(temp_img),
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        str(output_clip_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if temp_img.exists():
        temp_img.unlink()
    return output_clip_path

def prepare_broll_scene(
    scene_idx: int,
    query_text: str,
    duration: float,
    work_dir: Path,
    pixabay_key: Optional[str] = None
) -> Path:
    """
    Sourcing agent: fetches or creates a 9:16 vertical b-roll clip for a scene.
    1. Tries Pixabay Video API (if key configured)
    2. Falls back to generating high-definition branded motion clip
    """
    out_clip = work_dir / f"scene_{scene_idx:02d}.mp4"
    if out_clip.exists() and out_clip.stat().st_size > 10000:
        return out_clip

    # 1. Try Pixabay Video Search
    active_key = pixabay_key or os.getenv("PIXABAY_API_KEY") or config.PIXABAY_API_KEY
    if active_key:
        print(f"[BRollAgent] Searching Pixabay for: '{query_text}'...")
        mp4_url = search_pixabay_video(query_text, active_key)
        if mp4_url:
            raw_stock = work_dir / f"stock_raw_{scene_idx:02d}.mp4"
            if download_video_clip(mp4_url, raw_stock):
                print(f"[BRollAgent] Downloaded stock clip from Pixabay! Formatting to 9:16 vertical...")
                # Format to 9:16 vertical with blurred backdrop
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(raw_stock),
                    "-filter_complex",
                    f"[0:v]scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},boxblur=20:5[bg];"
                    f"[0:v]scale={config.VIDEO_WIDTH}:-1[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2,eq=contrast=1.06:saturation=1.1,vignette=PI/5[v]",
                    "-map", "[v]",
                    "-t", f"{duration:.3f}",
                    "-r", f"{config.VIDEO_FPS}",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-an",
                    str(out_clip)
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if raw_stock.exists():
                    raw_stock.unlink()
                return out_clip

    # 2. High-Quality Fallback Motion Clip
    print(f"[BRollAgent] Synthesizing 9:16 motion visual for Scene {scene_idx + 1} ('{query_text}')...")
    return generate_fallback_motion_clip(query_text, duration, out_clip, scene_idx)
