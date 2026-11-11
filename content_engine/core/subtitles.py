from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from content_engine import config

def seconds_to_ass_time(sec: float) -> str:
    """Convert float seconds to ASS timestamp format: H:MM:SS.cs"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def group_words_into_chunks(words: list, max_words: int = 3, max_duration: float = 2.2) -> list:
    """Group consecutive words into short 2-3 word chunks for mobile shorts."""
    chunks = []
    current_chunk = []
    chunk_start = 0.0

    for w in words:
        if not current_chunk:
            chunk_start = w["start"]
            current_chunk.append(w)
        else:
            duration_if_added = w["end"] - chunk_start
            if len(current_chunk) >= max_words or duration_if_added > max_duration or (w["start"] - current_chunk[-1]["end"]) > 0.6:
                chunks.append(current_chunk)
                current_chunk = [w]
                chunk_start = w["start"]
            else:
                current_chunk.append(w)

    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def generate_ass_subtitles(words: list, output_ass_path: str, highlight_color_bgr: str = "&H00FFFF&") -> str:
    """
    Generate an Advanced SubStation Alpha (.ass) subtitle file with active word kinetic highlight.
    Colors in ASS are &HAABBGGRR& (e.g. &H0000FFFF& for Yellow, &H00FFFF00& for Cyan).
    """
    chunks = group_words_into_chunks(words, max_words=3, max_duration=2.0)
    ass_path = Path(output_ass_path)
    ass_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.VIDEO_WIDTH}
PlayResY: {config.VIDEO_HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kinetic,Arial Black,78,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,40,40,650,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues = []

    for chunk in chunks:
        # For each word in chunk, create a dialogue line spanning that word's duration
        for i, target_word in enumerate(chunk):
            start_str = seconds_to_ass_time(target_word["start"])
            end_str = seconds_to_ass_time(target_word["end"])

            # Build line: highlight target word in yellow/cyan, others white
            parts = []
            for j, w in enumerate(chunk):
                cleaned_word = w["word"].upper().replace("\\", "").replace("{", "").replace("}", "")
                if i == j:
                    # Active glowing word
                    parts.append(f"{{\\c{highlight_color_bgr}\\fscx108\\fscy108}}{cleaned_word}{{\\rKinetic}}")
                else:
                    parts.append(f"{{\\c&H00FFFFFF&}}{cleaned_word}")
            
            line_text = " ".join(parts)
            dialogues.append(f"Dialogue: 0,{start_str},{end_str},Kinetic,,0,0,0,,{line_text}")

    content = header + "\n".join(dialogues) + "\n"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(ass_path)

def generate_pillow_subtitle_overlays(words: list, output_dir: Path) -> list:
    """Fallback: Generate transparent PNG subtitle cards when libass is absent."""
    chunks = group_words_into_chunks(words, max_words=3, max_duration=2.0)
    output_dir.mkdir(parents=True, exist_ok=True)
    cards = []

    try:
        font = ImageFont.truetype(str(config.DEFAULT_FONT), 72)
    except Exception:
        font = ImageFont.load_default()

    card_idx = 0
    for chunk in chunks:
        for i, target_word in enumerate(chunk):
            img = Image.new("RGBA", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Compute phrase text
            words_text = [w["word"].upper() for w in chunk]
            phrase = " ".join(words_text)

            # Draw lower-third subtitle background pill
            bbox = draw.textbbox((0, 0), phrase, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            cx, cy = config.VIDEO_WIDTH // 2, 1300

            pill_x0 = cx - (tw // 2) - 30
            pill_y0 = cy - 20
            pill_x1 = cx + (tw // 2) + 30
            pill_y1 = cy + th + 20
            draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=25, fill=(0, 0, 0, 160))

            # Draw word by word with active highlight
            cur_x = cx - (tw // 2)
            for j, w in enumerate(chunk):
                w_str = w["word"].upper() + " "
                w_bbox = draw.textbbox((0, 0), w_str, font=font)
                w_w = w_bbox[2] - w_bbox[0]

                color = (0, 240, 255, 255) if i == j else (255, 255, 255, 255)
                # Text outline
                for ox in (-3, 3):
                    for oy in (-3, 3):
                        draw.text((cur_x + ox, cy + oy), w_str, font=font, fill=(0, 0, 0, 255))
                # Text fill
                draw.text((cur_x, cy), w_str, font=font, fill=color)
                cur_x += w_w

            card_path = output_dir / f"sub_{card_idx:04d}.png"
            img.save(card_path, "PNG")
            cards.append({
                "path": str(card_path),
                "start": target_word["start"],
                "end": target_word["end"]
            })
            card_idx += 1

    return cards
