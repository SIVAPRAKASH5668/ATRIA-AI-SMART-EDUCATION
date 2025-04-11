import os
import tempfile
import platform
import subprocess
import requests
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    TextClip,
    VideoFileClip
)
from moviepy.video.fx.loop import loop

def get_output_media(audio_file_path, timed_captions, background_video_data, video_server=None):
    """
    Creates a video with synchronized captions and background videos
    
    Parameters:
    - audio_file_path: Path to the audio file
    - timed_captions: List of [(start_time, end_time), "caption text"] pairs
    - background_video_data: List of [(start_time, end_time), "video_url"] pairs
    - video_server: Optional server information
    
    Returns:
    - Path to output video file
    """
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    OUTPUT_FILE_NAME = "output/Intro.mp4"
    TARGET_RESOLUTION = (1280, 720)
    TARGET_FPS = 30  # Increased from 24 for better quality
    TARGET_AUDIO_RATE = 44100
    TARGET_CODEC = 'libx264'
    TARGET_PRESET = 'medium'  # Good balance between quality and encoding speed
    TARGET_CRF = 23  # Lower values = higher quality (range: 0-51)

    def download_file(url, filename):
        """Download a file from URL to the specified filename"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"Download failed for {url}: {e}")
            return False

    def get_program_path(program_name):
        """Find the path of an executable program"""
        search_cmd = "where" if platform.system() == "Windows" else "which"
        try:
            return subprocess.check_output([search_cmd, program_name]).decode().strip()
        except subprocess.CalledProcessError:
            return None

    # Ensure ImageMagick path (required by TextClip)
    magick_path = get_program_path("magick") or get_program_path("convert")
    os.environ['IMAGEMAGICK_BINARY'] = magick_path or '/usr/bin/convert'

    # Get audio duration first to understand total timeline
    try:
        audio_duration = AudioFileClip(audio_file_path).duration
        print(f"Audio duration: {audio_duration} seconds")
    except Exception as e:
        print(f"Failed to get audio duration: {e}")
        audio_duration = max([t2 for (t1, t2), _ in timed_captions], default=60)
        print(f"Using fallback duration from captions: {audio_duration} seconds")

    # Sort background videos by start time
    background_video_data.sort(key=lambda x: x[0][0])
    
    # Process background videos
    visual_clips = []
    downloaded_video_paths = []
    valid_video_clips = []  # Store all valid clips for potential reuse
    current_video_end = 0  # Track the current end time of processed videos

    for (t1, t2), video_url in background_video_data:
        try:
            # Download the video
            video_filename = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            if not download_file(video_url, video_filename):
                continue
                
            downloaded_video_paths.append(video_filename)
            video_clip = VideoFileClip(video_filename)
            video_duration = video_clip.duration
            
            # Process the video timeframe
            clip_duration = t2 - t1
            
            # If video is shorter than needed segment, loop it
            if video_duration < clip_duration:
                video_clip = loop(video_clip, duration=clip_duration)
            else:
                # Take only what we need from the video
                video_clip = video_clip.subclip(0, min(video_duration, clip_duration))
            
            # Standardize video
            video_clip = video_clip.resize(TARGET_RESOLUTION).set_fps(TARGET_FPS)
            video_clip = video_clip.set_start(t1)  # Place at correct timeline position
            
            visual_clips.append(video_clip)
            valid_video_clips.append(video_clip)
            current_video_end = max(current_video_end, t2)
            
        except Exception as e:
            print(f"Error processing video {video_url}: {e}")
            continue

    # Fill gaps in the timeline
    if valid_video_clips:
        # Find uncovered segments in timeline
        timeline_segments = [(t1, t2) for (t1, t2), _ in background_video_data if any(clip.start <= t1 and clip.end >= t2 for clip in visual_clips)]
        
        # Fill any gaps with loops of existing videos
        if timeline_segments and current_video_end < audio_duration:
            # Pick a clip for filling (either the longest or the last)
            filler_clip = max(valid_video_clips, key=lambda clip: clip.duration)
            print(f"Using filler clip to cover timeline gaps from {current_video_end} to {audio_duration}")
            
            # Create a looped clip for the remaining duration
            looped_filler = loop(filler_clip, duration=(audio_duration - current_video_end))
            looped_filler = looped_filler.set_start(current_video_end)
            visual_clips.append(looped_filler)
    else:
        # No valid video clips - create a black background
        print("No valid video clips available. Creating black background.")
        from moviepy.editor import ColorClip
        black_bg = ColorClip(size=TARGET_RESOLUTION, color=(0, 0, 0), duration=audio_duration)
        visual_clips.append(black_bg)

    # Load and normalize audio
    audio_clips = []
    try:
        audio_file_clip = AudioFileClip(audio_file_path).set_fps(TARGET_AUDIO_RATE)
        audio_clips.append(audio_file_clip)
    except Exception as e:
        print(f"Failed to load audio: {e}")

    # Add captions with improved rendering
    for (t1, t2), text in timed_captions:
        try:
            # Create more professional-looking captions
            text_clip = TextClip(
                txt=text,
                fontsize=60,  # Slightly smaller for better readability
                font="Arial-Bold" if os.path.exists("/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf") else None,
                color="white",
                stroke_width=2,
                stroke_color="black",
                method="label",
                align="center"  # Center-align text
            ).set_start(t1).set_end(t2).set_position(("center", 600))
            
            visual_clips.append(text_clip)
            
        except Exception as e:
            print(f"TextClip error: {e}")
            # Try fallback method if the first fails
            try:
                text_clip = TextClip(
                    txt=text,
                    fontsize=60,
                    color="white",
                    stroke_color="black",
                    method="caption",  # Alternative method
                ).set_start(t1).set_end(t2).set_position(("center", 600))
                
                visual_clips.append(text_clip)
            except Exception as e2:
                print(f"Fallback TextClip also failed: {e2}")

    if not visual_clips:
        raise RuntimeError("No visual clips available to generate the intro video!")

    # Create and save the final video
    video = CompositeVideoClip(visual_clips, size=TARGET_RESOLUTION)

    if audio_clips:
        audio = CompositeAudioClip(audio_clips)
        video = video.set_audio(audio)
        # Use audio duration as the video duration to ensure sync
        video.duration = audio.duration if audio.duration > 0 else max([clip.end for clip in visual_clips])

    print(f"Rendering final video to {OUTPUT_FILE_NAME}")
    
    # Use better ffmpeg parameters for quality and compatibility
    video.write_videofile(
        OUTPUT_FILE_NAME,
        codec=TARGET_CODEC,
        audio_codec='aac',
        fps=TARGET_FPS,
        preset=TARGET_PRESET,
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",  # Standard pixel format for compatibility
            "-crf", str(TARGET_CRF),  # Quality control
            "-profile:v", "main",    # Common profile for compatibility
            "-level", "4.0",         # Common level for compatibility
            "-maxrate", "4M",        # Maximum bitrate
            "-bufsize", "8M",        # Buffer size
            "-movflags", "+faststart"  # Web optimization
        ]
    )

    # Clean up temporary files
    for path in downloaded_video_paths:
        try:
            os.remove(path)
            print(f"Removed temporary file: {path}")
        except Exception as e:
            print(f"Failed to remove temporary file {path}: {e}")

    return OUTPUT_FILE_NAME