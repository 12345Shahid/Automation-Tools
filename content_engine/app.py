import os
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from content_engine import config
from content_engine.engine import create_short_video

app = FastAPI(title="ShortsEngine AI", description="Autonomous Looped-Arc Content Engine")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/outputs", StaticFiles(directory=str(config.OUTPUT_DIR)), name="outputs")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class GenerateRequest(BaseModel):
    topic: str
    voice: str = "christopher"

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
    """Trigger short video generation in threadpool to avoid event loop conflicts."""
    if not req.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    
    try:
        # Run in separate thread so asyncio.run in voice generator works seamlessly
        result = await asyncio.to_thread(create_short_video, req.topic.strip(), req.voice)
        result["video_url"] = f"/outputs/{result['filename']}"
        return {"status": "success", "video": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("content_engine.app:app", host="0.0.0.0", port=8000, reload=True)
