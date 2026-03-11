from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from processor import process_video_task

app = FastAPI(title="Video Mix Service")

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
    status: str
    error: Optional[str] = None

class MixResponse(BaseModel):
    outputs: List[MixOutput]

@app.post("/mix", response_model=MixResponse)
async def mix_videos(request: MixRequest):
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
    return MixResponse(outputs=results)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
