from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import os
import time
from fastapi.staticfiles import StaticFiles

from processor import process_video_task

app = FastAPI(title="Video Mix Service")

# Ensure /outputs exists and mount it as static files directory
os.makedirs("/outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="/outputs"), name="outputs")

BASE_URL = os.getenv("BASE_URL")
OUTPUT_TTL_HOURS = float(os.getenv("OUTPUT_TTL_HOURS", "6"))

def run_cleanup():
    """Delete files older than OUTPUT_TTL_HOURS from /outputs."""
    try:
        now = time.time()
        for filename in os.listdir("/outputs"):
            if filename.endswith(".tmp.mp4"):
                # Do not delete files currently being written
                continue
            
            filepath = os.path.join("/outputs", filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > OUTPUT_TTL_HOURS * 3600:
                    os.remove(filepath)
                    print(f"Cleaned up old file: {filepath}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

# Run cleanup at app startup
run_cleanup()

class VideoItem(BaseModel):
    id: str
    keyword: str
    source_url: str

class MixRequest(BaseModel):
    song_url: str
    song_start: float
    videos: List[VideoItem]

class MixOutput(BaseModel):
    id: str
    keyword: str
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    status: str
    error: Optional[str] = None

class MixResponse(BaseModel):
    outputs: List[MixOutput]

@app.post("/mix", response_model=MixResponse)
async def mix_videos(request: MixRequest):
    # Run cleanup before/after each mix request
    run_cleanup()
    
    # Process each video concurrently in separate threads to not block the event loop
    tasks = []
    for video in request.videos:
        tasks.append(
            asyncio.to_thread(
                process_video_task,
                video.id,
                video.keyword,
                video.source_url,
                request.song_url,
                request.song_start
            )
        )
    
    results = await asyncio.gather(*tasks)
    
    processed_results = []
    for res in results:
        if res.get("status") == "success" and res.get("file_path"):
            if BASE_URL:
                # file_path is like /outputs/file.mp4, avoiding double slashes
                res["download_url"] = f"{BASE_URL.rstrip('/')}{res['file_path']}"
            else:
                res["download_url"] = None
        processed_results.append(res)
        
    return MixResponse(outputs=processed_results)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
