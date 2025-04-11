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

class TextToVideoGenerator:
    def __init__(self, topic: str, audio_file_name="audio_tts.wav", video_server="pexel"):
        """
        Initializes the TextToVideoGenerator with a topic and optional file parameters.
        :param topic: The topic for the video (e.g., 'cars')
        :param audio_file_name: Name of the generated audio file (default: 'audio_tts.wav')
        :param video_server: The video server to fetch background videos from (default: 'pexel')
        """
        self.topic = topic
        self.audio_file_name = audio_file_name
        self.video_server = video_server
        self.timed_captions = None
        self.background_video_urls = None

    def generate_script(self):
        """Generate a script using Groq or OpenAI."""
        response = generate_script(self.topic)
        print("Script generated:", response)
        return response

    def generate_audio(self, script: str):
        """Generate audio from the script."""
        asyncio.run(generate_audio(script, self.audio_file_name))
        print(f"Audio generated and saved to {self.audio_file_name}")

    def generate_timed_captions(self):
        """Generate timed captions from the audio file."""
        try:
            self.timed_captions = generate_timed_captions(self.audio_file_name)
            print("Timed captions generated:", self.timed_captions)

            if self.timed_captions and self.timed_captions[0][1].startswith("Error"):
                print("Caption generation failed. Please install FFmpeg and try again.")
                return False
            return True
        except Exception as e:
            print(f"Error generating captions: {e}")
            return False

    def generate_video_search_queries(self, script: str):
        """Generate search queries based on the script and captions."""
        search_terms = getVideoSearchQueriesTimed(script, self.timed_captions)
        print("Search terms generated:", search_terms)
        return search_terms

    def fetch_background_videos(self, search_terms):
        """Fetch background video URLs from the server."""
        if search_terms is not None:
            self.background_video_urls = generate_video_url(search_terms, self.video_server)
            print("Background videos fetched:", self.background_video_urls)
        else:
            print("No background video search terms were generated")

    def merge_empty_intervals_in_videos(self):
        """Merge empty intervals in the video URLs."""
        if self.background_video_urls:
            self.background_video_urls = merge_empty_intervals(self.background_video_urls)
            print("Merged background videos:", self.background_video_urls)

    def render_video(self):
        """Render the final video with audio, captions, and background videos."""
        if self.background_video_urls is not None:
            video_path = get_output_media(self.audio_file_name, self.timed_captions, self.background_video_urls, self.video_server)
            print(f"Video successfully rendered and saved to {video_path}")
            return video_path
        else:
            print("Could not render video due to missing background videos")
            return None

    def create_video(self):
        """Perform all the steps to generate the final video."""
        # Step 1: Generate script
        script = self.generate_script()

        # Step 2: Generate audio from script
        self.generate_audio(script)

        # Step 3: Generate timed captions from audio
        if not self.generate_timed_captions():
            return None

        # Step 4: Generate video search queries from script and captions
        search_terms = self.generate_video_search_queries(script)

        # Step 5: Fetch background video URLs
        self.fetch_background_videos(search_terms)

        # Step 6: Merge empty intervals in video URLs
        self.merge_empty_intervals_in_videos()

        # Step 7: Render final video
        return self.render_video()


# Example usage:
if __name__ == "__main__":
    # Define the topic
    topic = "cars"
    
    # Create an instance of the TextToVideoGenerator class
    video_generator = TextToVideoGenerator(topic)

    # Generate the video
    video_path = video_generator.create_video()
    if video_path:
        print(f"Video is ready at: {video_path}")
    else:
        print("Video creation failed.")
