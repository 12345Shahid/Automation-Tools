import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from content_engine import config
from content_engine.agents.scout_agent import scout_viral_angle
from content_engine.agents.story_architect import generate_looped_arc_story
from content_engine.agents.broll_agent import prepare_broll_scene
from content_engine.agents.voice_agent import synthesize_narration
from content_engine.agents.foley_agent import master_audio_track
from content_engine.agents.qc_assembler_agent import assemble_and_verify
from content_engine.core.director import generate_director_roadmap
from content_engine.core.raw_editor import transform_raw_video

def run_option_a_pipeline(
    topic: str,
    voice_key: str = "christopher",
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Executes the Complete Option A Agentic Pipeline:
    Scout -> Story Architect -> Voice Agent -> BRoll Agent -> Foley Agent -> QC Assembler
    """
    out_dir = output_dir or config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"optA_{timestamp}"
    work_dir = out_dir / f"work_{run_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n==========================================")
    print(f"🚀 Starting Option A Agentic Pipeline: '{topic}'")
    print(f"==========================================")

    # 1. Scout Agent
    print("\n[Step 1/6] Scout Agent finding viral angles...")
    scout_data = scout_viral_angle(topic)
    rec_angle = scout_data["angles"][scout_data.get("recommended_angle_index", 0)]

    # 2. Story Architect Agent
    print("\n[Step 2/6] Story Architect constructing 5-phase Looped Arc...")
    story_data = generate_looped_arc_story(topic, video_type="option_a")
    phases = story_data["phases"]
    full_narration = story_data["full_narration"]

    # 3. Voice Agent
    print("\n[Step 3/6] Voice Agent synthesizing neural studio voiceover...")
    voice_path = work_dir / "studio_narration.mp3"
    voice_res = synthesize_narration(full_narration, str(voice_path), voice_key=voice_key)
    total_duration = voice_res["duration"]
    words = voice_res["words"]

    # Calculate exact duration per phase proportional to narration length
    dur_per_phase = total_duration / len(phases)

    # 4. BRoll Agent
    print("\n[Step 4/6] BRoll Agent sourcing & preparing visual clips...")
    scene_clips = []
    for i, phase in enumerate(phases):
        query = phase.get("visual_query") or f"{topic} tech"
        clip_path = prepare_broll_scene(
            scene_idx=i,
            query_text=query,
            duration=dur_per_phase,
            work_dir=work_dir
        )
        scene_clips.append(clip_path)

    # 5. Foley & Sound Design Agent
    print("\n[Step 5/6] Foley Agent mastering audio bed and punchline dry cutout...")
    master_audio_path = work_dir / "mastered_audio.aac"
    master_audio = master_audio_track(
        voice_audio_path=str(voice_path),
        output_audio_path=str(master_audio_path),
        total_duration=total_duration,
        words=words,
        bgm_volume=0.12,
        dry_punchline=True
    )

    # 6. Master Assembler & QC Agent
    print("\n[Step 6/6] QC Assembler Agent compiling 9:16 Short with kinetic neon subtitles...")
    final_mp4 = out_dir / f"short_{run_id}.mp4"
    qc_res = assemble_and_verify(
        scene_clips=scene_clips,
        master_audio=Path(master_audio),
        words=words,
        output_mp4_path=final_mp4,
        work_dir=work_dir
    )

    # Save complete metadata
    meta_path = out_dir / f"short_{run_id}.json"
    metadata = {
        "title": story_data.get("title", f"{topic} ⚡"),
        "description": story_data.get("description", ""),
        "hashtags": story_data.get("hashtags", []),
        "pinned_comment": story_data.get("pinned_comment", ""),
        "duration": total_duration,
        "video_path": str(final_mp4),
        "filename": final_mp4.name,
        "phases": phases,
        "scout_angle": rec_angle
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Pipeline Complete! Output: {final_mp4.name}")
    return metadata

def run_option_b_roadmap(source_input: str) -> Dict[str, Any]:
    """Director Agent: Generates 5-step recording roadmap and studio script."""
    return generate_director_roadmap(source_input)

def run_option_b_transform(
    raw_video_path: str,
    script_text: str,
    output_path: str,
    voice_key: str = "christopher"
) -> Dict[str, Any]:
    """Smart Editor Agent: Transforms user's raw video into value-add Short."""
    return transform_raw_video(
        raw_video_path=raw_video_path,
        script_text=script_text,
        output_path=output_path,
        voice_key=voice_key
    )
