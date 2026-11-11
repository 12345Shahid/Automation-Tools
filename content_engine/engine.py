import json
import time
import uuid
from pathlib import Path
from content_engine import config
from content_engine.core.scriptwriter import generate_script
from content_engine.core.voice import generate_voice_sync
from content_engine.core.visuals import prepare_visuals_for_scenes
from content_engine.core.composer import compose_full_video

def create_short_video(
    topic: str = "How to automate video creation with free AI",
    voice_key: str = "christopher",
    progress_callback=None
) -> dict:
    """
    Autonomous End-to-End Content Generation Pipeline:
    Topic -> Looped Arc Script -> Neural Voiceover -> Visuals -> Kinetic Subtitles & Audio Ducking -> 1080x1920 MP4
    """
    job_id = str(uuid.uuid4())[:8]
    work_dir = Path("/tmp/content_engine") / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    
    selected_voice = config.AVAILABLE_VOICES.get(voice_key.lower(), config.DEFAULT_VOICE)

    def log(msg: str):
        print(f"[{job_id}] {msg}")
        if progress_callback:
            progress_callback(msg)

    # 1. Generate Viral Looped-Arc Script
    log(f"🧠 Generating viral Looped-Arc script for: '{topic}'...")
    script_data = generate_script(topic)
    
    # Concatenate all scene narrations into a coherent script
    full_narration = " ".join([s["narration"].strip() for s in script_data["scenes"]])

    # 2. Synthesize High-Speed Neural Audio & Word Timestamps
    log(f"🎙️ Synthesizing voiceover with {selected_voice} and extracting word timestamps...")
    raw_audio_path = work_dir / "voice.mp3"
    voice_res = generate_voice_sync(full_narration, str(raw_audio_path), voice=selected_voice)
    log(f"✅ Voice generated. Duration: {voice_res['duration']:.2f}s across {len(voice_res['words'])} words.")

    # 3. Collect Scene Visuals (Pollinations AI / Stock B-Roll)
    log(f"🎨 Generating 9:16 high-res visual assets for {len(script_data['scenes'])} scenes...")
    scene_images = prepare_visuals_for_scenes(script_data["scenes"], work_dir)

    # 4. Compose Motion, Kinetic Subtitles & Mixed Audio into MP4
    timestamp_slug = time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"short_{timestamp_slug}_{job_id}.mp4"
    final_output_path = config.OUTPUT_DIR / output_filename

    log(f"🎬 Assembling dynamic Ken Burns cuts, kinetic subtitles, and auto-ducked music...")
    compose_full_video(
        scene_images=scene_images,
        scenes_data=script_data["scenes"],
        voice_res=voice_res,
        work_dir=work_dir,
        output_mp4_path=str(final_output_path)
    )

    # 5. Save YouTube Metadata & Pinned Comment
    metadata = {
        "id": job_id,
        "filename": output_filename,
        "video_path": str(final_output_path),
        "topic": topic,
        "voice": selected_voice,
        "duration": voice_res["duration"],
        "title": script_data.get("title", ""),
        "description": script_data.get("description", ""),
        "hashtags": script_data.get("hashtags", []),
        "pinned_comment": script_data.get("pinned_comment", ""),
        "scenes": script_data.get("scenes", []),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    meta_file = final_output_path.with_suffix(".json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    log(f"🚀 Short video ready! Saved to: {final_output_path}")
    return metadata
