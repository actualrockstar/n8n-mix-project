import os
import shutil
import subprocess
import tempfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_command(cmd, check=True):
    logger.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and result.returncode != 0:
        stderr_tail = '\n'.join(result.stderr.splitlines()[-15:])
        logger.error(f"Command failed (last 15 lines):\n{stderr_tail}")
        raise RuntimeError(f"Command failed:\n{stderr_tail}")
    return result.stdout

def download_media(url: str, output_path: str):
    """
    Downloads media from a URL using yt-dlp to handle complex sites like TikTok.
    If it's a local file, simply copies it.
    """
    if url.startswith("http://") or url.startswith("https://"):
        cmd = [
            "yt-dlp",
            "-f", "best",
            "-o", output_path,
            url
        ]
        run_command(cmd)
    else:
        shutil.copy2(url, output_path)

def get_duration(file_path: str) -> float:
    """
    Gets the duration of a media file using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    output = run_command(cmd)
    return float(output.strip())

def has_audio(file_path: str) -> bool:
    """
    Checks if a media file has an audio stream.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        file_path
    ]
    output = run_command(cmd, check=False)
    return "audio" in output.strip()

def process_video_task(
    video_id: str,
    keyword: str,
    video_source_url: str,
    song_url: str,
    song_start: float,
    output_dir: str = "/outputs",
    tmp_dir: str = "/tmp"
) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir=tmp_dir) as temp_dir:
        # Use simple names without extension; yt-dlp will guess the extension but we can force it 
        # using output template, however we can just append a generic .mp4/.m4a extension and it will work 
        # or ffmpeg will figure it out.
        video_path = os.path.join(temp_dir, f"video_{video_id}.mp4")
        song_path = os.path.join(temp_dir, f"song_{video_id}.mp4")
        
        try:
            logger.info(f"[{video_id}] Downloading video from {video_source_url}")
            download_media(video_source_url, video_path)
            
            # Since yt-dlp might have changed the extension based on format, let's find the actual downloaded file.
            # Usually we pass -o {video_path} and yt-dlp might append ext. Let's force extension in yt-dlp instead.
            # Wait, our download_media passes `-o output_path`. yt-dlp *will* write to that exact path if there's no extension placeholder.
            
            logger.info(f"[{video_id}] Downloading song from {song_url}")
            download_media(song_url, song_path)
            
            video_duration = get_duration(video_path)
            logger.info(f"[{video_id}] Video duration: {video_duration}s")
            
            output_filename = f"{keyword}_{video_id}.mp4"
            output_filepath = os.path.join(output_dir, output_filename)
            
            # Calculate fade duration
            fade_duration = min(2.0, video_duration / 2.0)
            fade_start = video_duration - fade_duration
            
            # Build filter_complex based on whether the original video has audio
            if has_audio(video_path):
                # We have original audio: mix it
                filter_complex = (
                    f"[0:a]volume=0.25[orig_a];"
                    f"[1:a]atrim=start={song_start}:duration={video_duration},asetpts=PTS-STARTPTS,"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[song_a];"
                    f"[orig_a][song_a]amix=inputs=2:duration=first:dropout_transition=2[a_out]"
                )
            else:
                # No original audio: just use the song
                filter_complex = (
                    f"[1:a]atrim=start={song_start}:duration={video_duration},asetpts=PTS-STARTPTS,"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[a_out]"
                )

            logger.info(f"[{video_id}] Processing video with ffmpeg")
            temp_output_filepath = output_filepath.replace(".mp4", ".tmp.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", song_path,
                "-filter_complex", filter_complex,
                "-map", "0:v",       # keep original video
                "-map", "[a_out]",   # use new mixed audio
                "-c:v", "libx264",   # export h264
                "-c:a", "aac",       # export aac
                "-ar", "44100",      # normalize sample rate (loudnorm can change it to 96000 Hz)
                "-t", str(video_duration),  # explicit duration avoids -shortest deadlock with amix
                temp_output_filepath
            ]
            run_command(cmd)
            
            os.rename(temp_output_filepath, output_filepath)
            
            logger.info(f"[{video_id}] Finished successfully. Output: {output_filepath}")
            return {
                "id": video_id,
                "keyword": keyword,
                "file_path": output_filepath,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"[{video_id}] Processing failed: {str(e)}")
            return {
                "id": video_id,
                "keyword": keyword,
                "status": "error",
                "error": str(e)
            }
