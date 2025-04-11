import os
import edge_tts
import json
import asyncio
from dotenv import load_dotenv
from app.content_to_ai_video.short_video_Gen.utility.script.script_generator import generate_script
from app.content_to_ai_video.short_video_Gen.utility.audio.audio_generator import generate_audio
from app.content_to_ai_video.short_video_Gen.utility.captions.timed_captions_generator import generate_timed_captions
from app.content_to_ai_video.short_video_Gen.utility.video.background_video_generator import generate_video_url
from app.content_to_ai_video.short_video_Gen.utility.render.render_engine import get_output_media
from app.content_to_ai_video.short_video_Gen.utility.video.video_search_query_generator import getVideoSearchQueriesTimed, merge_empty_intervals

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    # Manually define the topic here
    SAMPLE_TOPIC = "cars"
    SAMPLE_FILE_NAME = "Text-To-Video-Ai-main/audio_tts.wav"
    VIDEO_SERVER = "pexel"

    # Step 1: Generate script using Groq or OpenAI
    response = generate_script(SAMPLE_TOPIC)
    print("Script generated:", response)

    # Step 2: Generate audio from script
    asyncio.run(generate_audio(response, SAMPLE_FILE_NAME))
    print(f"Audio generated and saved to {SAMPLE_FILE_NAME}")

    # Step 3: Generate timed captions from audio
    try:
        timed_captions = generate_timed_captions(SAMPLE_FILE_NAME)
        print("Timed captions generated:", timed_captions)
        
        if timed_captions and timed_captions[0][1].startswith("Error"):
            print("Caption generation failed. Please install FFmpeg and try again.")
            exit(1)
    except Exception as e:
        print(f"Error generating captions: {e}")
        exit(1)

    # Step 4: Generate video search queries from script and captions
    search_terms = getVideoSearchQueriesTimed(response, timed_captions)
    print("Search terms generated:", search_terms)

    # Step 5: Fetch background video URLs
    background_video_urls = None
    if search_terms is not None:
        background_video_urls = generate_video_url(search_terms, VIDEO_SERVER)
        print("Background videos fetched:", background_video_urls)
    else:
        print("No background video search terms were generated")

    # Step 6: Merge empty intervals in video URLs
    if background_video_urls:
        background_video_urls = merge_empty_intervals(background_video_urls)
        print("Merged background videos:", background_video_urls)

    # Step 7: Render final video
    if background_video_urls is not None:
        video_path = get_output_media(SAMPLE_FILE_NAME, timed_captions, background_video_urls, VIDEO_SERVER)
        print(f"Video successfully rendered and saved to {video_path}")
    else:
        print("Could not render video due to missing background videos")
