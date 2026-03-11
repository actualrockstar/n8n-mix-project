# n8n Video Mix Service

A lightweight, deterministic microservice designed to be called by n8n (or any automation tool). It downloads TikTok videos, mixes their audio with a provided song tracking, normalizes loudness, and exports final `mp4` files.

## Features
- **TikTok URL Handling**: Uses `yt-dlp` to correctly parse and download TikTok videos instead of failing with raw HTML responses.
- **Concurrent Processing**: Processes videos in parallel using Python thread execution (`asyncio.to_thread`) for faster batch completion.
- **Audio Mixing**:
  - Trims the song to match the video's exact duration.
  - Automatically fades out the song in the final 2 seconds.
  - Reduces the original video audio volume to ~25%.
  - Mixes the requested song at 100% volume.
  - Applies a loudness normalization standard (`loudnorm`) to ensure consistent, non-clipping output across different source materials.
- **Fallback Logic**: Works properly for videos completely missing an underlying audio track.
- **Resilient Batch Safety**: If a single video fails to process in a batch, it's flagged as an `error` in its status payload, while the rest are processed uninterrupted.
- **Flexible Endpoints**: Can consume standard direct remote `mp4`/`mp3` URLs as well as localized file paths.

## API Setup & Local Usage

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. You must have `ffmpeg` installed on your host system:
   - Mac: `brew install ffmpeg`
   - Debian/Ubuntu: `sudo apt install ffmpeg`

3. Start the FastAPI server:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```
   
## Docker Setup (Recommended)
You can deploy this immediately as a standalone Docker container, which bundles `ffmpeg` safely alongside Python.

1. Build the image:
   ```bash
   docker build -t video-mix-service .
   ```
2. Run the image:
   ```bash
   docker run -d -p 8000:8000 \
     -v $(pwd)/outputs:/outputs \
     video-mix-service
   ```
   *Note: Passing a volume `-v $(pwd)/outputs:/outputs` makes the output videos physically accessible on your host machine! Otherwise, they are saved locally within the Docker container.*

## Usage

**Endpoint:** `POST /mix`

**Payload:**
```json
{
  "song_url": "https://example.com/song.mp3",
  "song_start": 42,
  "videos": [
    {
      "id": "A",
      "keyword": "banana_clip",
      "source_url": "https://www.tiktok.com/@bruniela_/video/...123"
    },
    {
      "id": "C",
      "keyword": "falling_chair",
      "source_url": "https://www.tiktok.com/@user/video/..."
    }
  ]
}
```

**Response:**
```json
{
  "outputs": [
    {
      "id": "A",
      "keyword": "banana_clip",
      "file_path": "/outputs/banana_clip_A.mp4",
      "status": "success",
      "error": null
    },
    {
      "id": "C",
      "keyword": "falling_chair",
      "file_path": null,
      "status": "error",
      "error": "Command failed: ..."
    }
  ]
}
```

## Temporary Storage
- Temporary working files (download phases) are written to `/tmp` and automatically cleaned up upon conclusion.
- Exported outputs are written to `/outputs/{keyword}_{id}.mp4`.
