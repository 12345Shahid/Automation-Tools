import urllib.parse
from pathlib import Path
import requests
from PIL import Image, ImageDraw
from content_engine import config

def generate_procedural_fallback(output_path: Path, prompt: str, seed: int = 1):
    """Generate a sleek, dark-mode tech background as an offline fallback."""
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    img = Image.new("RGB", (w, h), color=(10, 14, 26))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(h):
        r = int(10 + (y / h) * 15)
        g = int(14 + (y / h) * 20)
        b = int(26 + (y / h) * 45)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Tech grid
    grid_spacing = 80
    grid_color = (25, 40, 75, 40)
    for x in range(0, w, grid_spacing):
        draw.line([(x, 0), (x, h)], fill=grid_color[:3], width=1)
    for y in range(0, h, grid_spacing):
        draw.line([(0, y), (w, y)], fill=grid_color[:3], width=1)

    # Center glowing radial accent
    cx, cy = w // 2, h // 2
    for r in range(400, 0, -20):
        alpha = int((1 - r / 400) * 40)
        box = [cx - r, cy - r, cx + r, cy + r]
        draw.ellipse(box, outline=(0, 220, 255, alpha), width=2)

    img.save(output_path, "JPEG", quality=90)

def fetch_scene_visual(visual_prompt: str, output_path: str, scene_id: int) -> str:
    """Fetch high-res visual via free Pollinations AI or procedural fallback."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Clean & enhance prompt for 9:16 vertical shorts aesthetic
    enhanced_prompt = f"{visual_prompt}, vertical 9:16 composition, cinematic lighting, 8k wallpaper, photorealistic, dark modern tech aesthetic"
    encoded = urllib.parse.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={config.VIDEO_WIDTH}&height={config.VIDEO_HEIGHT}&nologo=true&seed={1000 + scene_id}"

    try:
        resp = requests.get(url, timeout=18)
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(out_file, "wb") as f:
                f.write(resp.content)
            # Verify valid image
            with Image.open(out_file) as im:
                im.verify()
            return str(out_file)
    except Exception as e:
        print(f"[Visuals] Pollinations fetch warning for scene {scene_id}: {e}")

    # Fallback to procedural high-tech canvas
    print(f"[Visuals] Using procedural tech visual fallback for scene {scene_id}")
    generate_procedural_fallback(out_file, visual_prompt, seed=scene_id)
    return str(out_file)

def prepare_visuals_for_scenes(scenes: list, work_dir: Path) -> list:
    """Fetch/generate visuals for all scenes in parallel or sequential order."""
    image_paths = []
    for s in scenes:
        sid = s["id"]
        path = work_dir / f"scene_{sid}_bg.jpg"
        img_path = fetch_scene_visual(s.get("visual_prompt", "AI technology"), str(path), sid)
        image_paths.append(img_path)
    return image_paths
