import os
import json
import time
import uuid
import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from content_engine import config
from content_engine.engine import create_short_video
from content_engine.core.director import generate_director_roadmap
from content_engine.core.raw_editor import transform_raw_video

app = FastAPI(title="ShortsEngine AI", description="Autonomous & Smart Editor Looped-Arc Content Engine")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path("/tmp/content_engine/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/outputs", StaticFiles(directory=str(config.OUTPUT_DIR)), name="outputs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class GenerateRequest(BaseModel):
    topic: str
    voice: str = "christopher"

class RoadmapRequest(BaseModel):
    source_input: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard UI not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/videos")
async def list_videos():
    """List all generated videos sorted by creation time."""
    videos = []
    for json_file in config.OUTPUT_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                mp4_file = json_file.with_suffix(".mp4")
                if mp4_file.exists():
                    data["video_url"] = f"/outputs/{mp4_file.name}"
                    videos.append(data)
        except Exception:
            continue
    
    videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"videos": videos}

@app.post("/api/generate")
async def generate_video_endpoint(req: GenerateRequest):
    """Mode 1: Generate 100% autonomous short from text topic."""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    try:
        result = await asyncio.to_thread(create_short_video, req.topic.strip(), req.voice)
        result["video_url"] = f"/outputs/{result['filename']}"
        return {"status": "success", "video": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/director/roadmap")
async def director_roadmap_endpoint(req: RoadmapRequest):
    """Mode 2 Step 1: Generate Director's Recording Roadmap from URL/transcript."""
    if not req.source_input.strip():
        raise HTTPException(status_code=400, detail="Source content or URL cannot be empty")
    
    try:
        roadmap = await asyncio.to_thread(generate_director_roadmap, req.source_input.strip())
        return {"status": "success", "roadmap": roadmap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transform/raw")
async def transform_raw_endpoint(
    video: UploadFile = File(...),
    script_text: str = Form(...),
    voice: str = Form("christopher"),
    title: str = Form(""),
    description: str = Form(""),
    hashtags: str = Form(""),
    pinned_comment: str = Form("")
):
    """Mode 2 Step 2: Ingest user's raw recording, strip voice, add studio voice & subtitles."""
    job_id = str(uuid.uuid4())[:8]
    raw_filename = f"raw_{job_id}_{video.filename}"
    raw_path = UPLOAD_DIR / raw_filename

    # Save uploaded raw file
    with open(raw_path, "wb") as f:
        f.write(await video.read())

    timestamp_slug = time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"short_{timestamp_slug}_{job_id}.mp4"
    final_output_path = config.OUTPUT_DIR / output_filename

    try:
        res = await asyncio.to_thread(
            transform_raw_video,
            str(raw_path),
            script_text.strip(),
            str(final_output_path),
            voice
        )
        
        tags_list = [t.strip() for t in hashtags.split() if t.strip()] if hashtags else ["#shorts", "#ai", "#tech", "#viral"]
        meta = {
            "id": job_id,
            "filename": output_filename,
            "video_path": str(final_output_path),
            "video_url": f"/outputs/{output_filename}",
            "topic": title or "Raw Video Transform",
            "voice": res["voice"],
            "duration": res["duration"],
            "title": title or "Automated Workflow Transformation 😲😲",
            "description": description or "Full workflow automated with AI.",
            "hashtags": tags_list,
            "pinned_comment": pinned_comment or "Comment 'TOOL' for the link 👇",
            "mode": "Mode 2: Smart Editor",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(final_output_path.with_suffix(".json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return {"status": "success", "video": meta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("content_engine.app:app", host="0.0.0.0", port=8000, reload=True)
