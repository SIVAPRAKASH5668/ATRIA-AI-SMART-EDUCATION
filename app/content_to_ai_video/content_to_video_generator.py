import os
import requests
import json
import base64
import time
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from gtts import gTTS
import textwrap
from groq import Groq
import argparse
import re
from moviepy.editor import concatenate_videoclips, VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip
from dotenv import load_dotenv
from app.content_to_ai_video.short_video_Gen.short_video import TextToVideoGenerator

# Load environment variables from the .env file
load_dotenv()

class ContentToVideoGenerator:
    def __init__(self, groq_api_key=None, pexels_api_key=None):
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.pexels_api_key = pexels_api_key or os.environ.get("PEXELS_API_KEY") or "qE0jhiA8wtho845ofbUNMiGVYvCInZ5NuXllFw5ccfKfF5FvAvff917m"
        self.output_dir = "output"
        self.font_dir = "fonts"
        self.images_dir = os.path.join(self.output_dir, "images")
        
        # Create necessary directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.font_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        
        # Download Roboto fonts if not exist
        self.title_font_path = os.path.join(self.font_dir, "Roboto-Bold.ttf")
        self.content_font_path = os.path.join(self.font_dir, "Roboto-Regular.ttf")
        self._ensure_fonts_exist()
        
        # Define slide design constants
        self.slide_width = 1280
        self.slide_height = 720
        self.content_area_width = 640  # Left half for content
        self.image_area_width = 640    # Right half for image
    
    def generate_short_video(self, topic):
        """Generate an intro short video based on a topic"""
        print(f"Generating short intro video for topic: {topic}")
        
        # Create an instance of the TextToVideoGenerator class
        video_generator = TextToVideoGenerator(topic)

        # Generate the video
        video_path = video_generator.create_video()
        if video_path:
            print(f"Intro video is ready at: {video_path}")
            return video_path
        else:
            print("Intro video creation failed.")
            return None

    def _ensure_fonts_exist(self):
        """Download Roboto fonts if they don't exist"""
        font_urls = {
            self.title_font_path: "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf",
            self.content_font_path: "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
        }
        
        for font_path, url in font_urls.items():
            if not os.path.exists(font_path):
                try:
                    print(f"Downloading font: {os.path.basename(font_path)}")
                    response = requests.get(url)
                    response.raise_for_status()
                    with open(font_path, 'wb') as f:
                        f.write(response.content)
                    print(f"Downloaded {os.path.basename(font_path)}")
                except Exception as e:
                    print(f"Error downloading font: {e}")
    
    def extract_keyword(self, content):
        """Extract a keyword or key phrase for image search using Groq API"""
        if not self.groq_api_key:
            print("Warning: No Groq API key provided. Using fallback keyword extraction.")
            # Simple keyword extraction as fallback
            words = content.split()
            if len(words) > 3:
                return " ".join(words[:3])
            return content
            
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
        Extract a relevant keyword or key phrase (1-3 words max) from the following content
        that would be good for finding a relevant image. Do not explain, just return the keyword.
        
        Content: {content}
        """
        
        data = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        try:
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                    headers=headers, 
                                    json=data)
            response.raise_for_status()
            keyword = response.json()["choices"][0]["message"]["content"].strip()
            return keyword
        except Exception as e:
            print(f"Error extracting keyword using Groq API: {e}")
            # Simple keyword extraction as fallback
            words = content.split()
            if len(words) > 3:
                return " ".join(words[:3])
            return content
    
    def generate_slide_content(self, content, model="llama3-8b-8192"):
        """Generate slide content with notes and explanations using Groq API"""
        if not self.groq_api_key:
            print("Warning: No Groq API key provided. Using simple content generation method.")
            # Simple splitting by paragraphs as fallback
            slides = []
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    title = para.strip().split('\n')[0].replace('#', '').strip()
                    content_text = para.replace(title, '').strip()
                    if title == content_text:
                        title = title.split('.')[0] if '.' in title else "Slide"
                    
                    # Create bullet points from content (simplified approach)
                    bullet_points = []
                    sentences = re.split(r'(?<=[.!?])\s+', content_text)
                    for sentence in sentences[:3]:  # Limit to first 3 sentences
                        if sentence.strip():
                            bullet_points.append(f"• {sentence.strip()}")
                    
                    # Full content for audio explanation
                    explanation = content_text
                    
                    keyword = self.extract_keyword(para)
                    slides.append({
                        "title": title,
                        "notes": bullet_points,  # Now a list of bullet points
                        "explanation": explanation,
                        "keyword": keyword
                    })
            return slides
            
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
        Convert the following content into a series of presentation slides.A overall Title and For each slide, provide:
        1. A concise title (5-7 words maximum)
        2. 5-8 bullet points with key information (each bullet point should be 10-15 words maximum)
        3. A detailed explanation (100-150 words) for audio narration that expands on the bullet points
        4. A relevant keyword (1-3 words) for finding an appropriate image
        
        Format your response as a JSON array with objects containing 'title', 'notes', 'explanation', and 'keyword' fields.
        The 'notes' should be a list of bullet points (strings) that are concise and easy to read on a slide.
        The 'explanation' should be more detailed for audio narration.
        
        Content to convert:
        {content}
        """
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        try:
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                    headers=headers, 
                                    json=data)
            response.raise_for_status()
            response_text = response.json()["choices"][0]["message"]["content"]
            
            # Extract JSON from response (sometimes AI adds explanatory text)
            json_match = re.search(r'(\[\s*\{.*?\}\s*\])', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
                
            slides = json.loads(response_text)
            print(f"Generated {len(slides)} slides with structured content")
            return slides
        except Exception as e:
            print(f"Error generating slide content using Groq API: {e}")
            print("Falling back to simple content generation method")
            
            # Simple splitting by paragraphs as fallback
            slides = []
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    title = para.strip().split('\n')[0].replace('#', '').strip()
                    content_text = para.replace(title, '').strip()
                    if title == content_text:
                        title = title.split('.')[0] if '.' in title else "Slide"
                    
                    # Create bullet points from content (simplified approach)
                    bullet_points = []
                    sentences = re.split(r'(?<=[.!?])\s+', content_text)
                    for sentence in sentences[:3]:  # Limit to first 3 sentences
                        if sentence.strip():
                            bullet_points.append(f"• {sentence.strip()}")
                    
                    # Full content for audio explanation
                    explanation = content_text
                    
                    keyword = self.extract_keyword(para)
                    slides.append({
                        "title": title,
                        "notes": bullet_points,  # Now a list of bullet points
                        "explanation": explanation,
                        "keyword": keyword
                    })
            return slides
    
    def get_image_for_slide(self, keyword, slide_num):
        """Fetch an image from Pexels API based on keyword"""
        base_url = 'https://api.pexels.com/v1/search'
        headers = {
            'Authorization': self.pexels_api_key
        }
        params = {
            'query': keyword,
            'per_page': 1,
            'size': 'large'  # Get larger images
        }
        
        image_path = os.path.join(self.images_dir, f"slide_{slide_num}_image.jpg")
        
        try:
            print(f"Fetching image for '{keyword}'...")
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('photos') and len(data['photos']) > 0:
                # Get the original image URL
                image_url = data['photos'][0]['src']['large']
                
                # Download the image
                img_response = requests.get(image_url)
                img_response.raise_for_status()
                
                with open(image_path, 'wb') as file:
                    file.write(img_response.content)
                print(f"Image for '{keyword}' saved as {image_path}")
                return image_path
            else:
                print(f"No images found for keyword: {keyword}")
                return None
        except Exception as e:
            print(f"Error fetching image: {e}")
            return None
    
    def crop_and_process_image(self, image_path):
        """Crop and process image to fit in the right half of slide"""
        if not image_path or not os.path.exists(image_path):
            return None
            
        try:
            img = Image.open(image_path)
            
            # Determine the aspect ratio of our image area
            image_area_aspect = self.image_area_width / self.slide_height
            
            # Get original image dimensions
            orig_width, orig_height = img.size
            orig_aspect = orig_width / orig_height
            
            # Determine whether to crop width or height
            if orig_aspect > image_area_aspect:
                # Image is wider than our area - crop the width
                new_width = int(orig_height * image_area_aspect)
                left = (orig_width - new_width) // 2
                img = img.crop((left, 0, left + new_width, orig_height))
            else:
                # Image is taller than our area - crop the height
                new_height = int(orig_width / image_area_aspect)
                top = (orig_height - new_height) // 2
                img = img.crop((0, top, orig_width, top + new_height))
            
            # Resize to fit our image area
            img = img.resize((self.image_area_width, self.slide_height), Image.LANCZOS)
            
            # Apply a slight vignette effect to focus attention
            img = self.apply_vignette(img)
            
            return img
        
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
    
    def apply_vignette(self, img):
        """Apply a subtle vignette effect to the image"""
        width, height = img.size
        
        # Create a transparent black image for the vignette
        vignette = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        
        # Calculate the radius for the vignette (slightly larger than image diagonal)
        radius = int(1.5 * ((width/2)**2 + (height/2)**2)**0.5)
        
        # Draw a radial gradient from transparent to semi-transparent black
        for i in range(radius, 0, -1):
            # Calculate alpha value (0=transparent, 255=opaque)
            alpha = int(60 * (1 - i/radius))
            if alpha <= 0:
                continue
                
            # Draw an ellipse with decreasing size and increasing alpha
            bbox = (
                width/2 - i, 
                height/2 - i * height/width, 
                width/2 + i, 
                height/2 + i * height/width
            )
            draw.ellipse(bbox, fill=(0, 0, 0, 0), outline=(0, 0, 0, alpha))
        
        # Composite the vignette onto the original image
        img = img.convert('RGBA')
        result = Image.alpha_composite(img, vignette)
        return result.convert('RGB')
    
    def create_modern_slide(self, title, notes, slide_num, total_slides, image_path=None):
        """Create a modern slide with bullet-point notes on left and image on right"""
        width, height = self.slide_width, self.slide_height
        
        # Create base slide with white background
        slide = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(slide)
        
        # Load fonts
        try:
            title_font = ImageFont.truetype(self.title_font_path, 48)
            subtitle_font = ImageFont.truetype(self.title_font_path, 32)
            content_font = ImageFont.truetype(self.content_font_path, 28)
            bullet_font = ImageFont.truetype(self.content_font_path, 26)
            footer_font = ImageFont.truetype(self.content_font_path, 22)
        except IOError as e:
            print(f"Font error: {e}. Using default fonts.")
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            content_font = ImageFont.load_default()
            bullet_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()
        
        # Define colors
        primary_color = (40, 86, 152)  # Deep blue
        accent_color = (64, 145, 220)  # Lighter blue
        dark_text = (33, 33, 33)
        light_text = (255, 255, 255)
        bullet_color = (29, 66, 137)   # Darker blue for bullets
        
        # Draw a modern header with accent bar
        draw.rectangle([(0, 0), (width, 90)], fill=primary_color)
        draw.rectangle([(0, 90), (width, 96)], fill=accent_color)
        
        # Draw title with shadow effect
        draw.text((42, 24), title, font=title_font, fill=(0, 0, 0, 70))
        draw.text((40, 22), title, font=title_font, fill=light_text)
        
        # Process and place the image on the right if available
        if image_path:
            processed_img = self.crop_and_process_image(image_path)
            if processed_img:
                # Place the image on the right side
                slide.paste(processed_img, (self.content_area_width, 96))
        
        # Draw a subtle vertical separator line
        draw.rectangle([(self.content_area_width - 2, 96), (self.content_area_width, height-60)], fill=accent_color)
        
        # Content area boundaries
        content_box_top = 120
        content_box_left = 40
        content_box_width = self.content_area_width - 80
        content_box_bottom = height - 80
        
        # Handle bullet points
        y_position = content_box_top + 15
        
        # Check if notes is a list (bullet points) or a string
        if isinstance(notes, list):
            # Draw each bullet point
            for bullet_point in notes:
                lines = textwrap.wrap(bullet_point, width=42)  # Wrap text for each bullet
                
                for i, line in enumerate(lines):
                    # Only draw the bullet symbol for the first line of each point
                    if i == 0:
                        # Draw colored bullet
                        draw.ellipse([(content_box_left, y_position + 10), 
                                     (content_box_left + 10, y_position + 20)], 
                                    fill=bullet_color)
                        # Draw text after bullet
                        draw.text((content_box_left + 20, y_position), line, font=bullet_font, fill=dark_text)
                    else:
                        # Continue text with proper indentation for wrapped lines
                        draw.text((content_box_left + 20, y_position), line, font=bullet_font, fill=dark_text)
                    
                    y_position += 36  # Space between lines
                
                y_position += 10  # Extra spacing between bullet points
        else:
            # Original behavior for string notes
            wrapped_notes = textwrap.fill(notes, width=45)
            notes_lines = wrapped_notes.split('\n')
            line_height = 38
            
            for line in notes_lines:
                draw.text((content_box_left, y_position), line, font=content_font, fill=dark_text)
                y_position += line_height
        
        # Add a modern footer
        draw.rectangle([(0, height-60), (width, height)], fill=primary_color)
        
        # Draw slide number
        slide_text = f"Slide {slide_num}/{total_slides}"
        text_width = draw.textlength(slide_text, font=footer_font)
        draw.text((width - text_width - 40, height - 40), 
                  slide_text, font=footer_font, fill=light_text)
        
        # Add a subtle logo or watermark
        draw.text((60, height - 40), "Content Video Generator", font=footer_font, fill=light_text)
        
        return slide
    
    def text_to_speech(self, text, filename, lang='en'):
        """Convert text to speech using gTTS"""
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filename)
            return True
        except Exception as e:
            print(f"Error generating speech: {e}")
            return False
    
    from moviepy.editor import AudioFileClip, concatenate_videoclips, ImageClip

    def create_video_from_slides(self, slides, output_filename="presentation.mp4"):
        print("Creating slides...")
        slide_durations = []
        slide_images = []
        audio_clips = []
        TARGET_RESOLUTION = (1280, 720)
        TARGET_FPS = 24

        total_slides = len(slides)

        for i, slide in enumerate(slides):
            slide_num = i + 1
            keyword = slide.get("keyword", slide["title"])
            image_path = self.get_image_for_slide(keyword, slide_num)

            slide_image = self.create_modern_slide(
                slide["title"],
                slide["notes"],
                slide_num,
                total_slides,
                image_path
            )

            slide_path = os.path.join(self.output_dir, f"slide_{slide_num}.png")
            slide_image.save(slide_path)
            slide_images.append(slide_path)

            print(f"Generating speech for slide {slide_num}...")
            audio_path = os.path.join(self.output_dir, f"audio_{slide_num}.mp3")
            narration_text = f"{slide['title']}. {slide['explanation']}"
            speech_success = self.text_to_speech(narration_text, audio_path)

            if speech_success:
                audio_clip = AudioFileClip(audio_path).set_fps(44100)
                duration = audio_clip.duration
                slide_durations.append(max(duration, 3))
                audio_clips.append(audio_clip)
            else:
                slide_durations.append(5)
                audio_clips.append(None)

        print("Creating video...")
        video_clips = []

        for i, (img_path, duration) in enumerate(zip(slide_images, slide_durations)):
            img_clip = ImageClip(img_path).set_duration(duration).resize(TARGET_RESOLUTION)
            if audio_clips[i] is not None:
                img_clip = img_clip.set_audio(audio_clips[i])
            video_clips.append(img_clip)

        final_clip = concatenate_videoclips(video_clips, method="compose")

        output_path = os.path.join(self.output_dir, output_filename)
        final_clip.write_videofile(
            output_path,
            fps=TARGET_FPS,
            codec='libx264',
            audio_codec='aac',
            ffmpeg_params=["-pix_fmt", "yuv420p"]
        )

        print(f"Video created successfully: {output_path}")
        return output_path

    def concatenate_videos(self, video_paths, output_filename="final_video.mp4"):
        from moviepy.editor import VideoFileClip, concatenate_videoclips

        if not video_paths:
            print("No videos to concatenate")
            return None

        print(f"Concatenating {len(video_paths)} videos...")
        video_clips = []

        for path in video_paths:
            if path and os.path.exists(path):
                clip = VideoFileClip(path).resize((1280, 720)).set_fps(24)
                video_clips.append(clip)
            else:
                print(f"Skipping invalid path: {path}")

        if not video_clips:
            return None

        final_clip = concatenate_videoclips(video_clips, method="compose")
        output_path = os.path.join(self.output_dir, output_filename)
        final_clip.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            ffmpeg_params=["-pix_fmt", "yuv420p"]
        )

        print(f"Final video created: {output_path}")
        return output_path



    def title_extraction_for_topic(self, content):
        """Extract a one-word title from the given content"""
        load_dotenv()  # Load environment variables
        
        # Initialize Groq client
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Prepare the prompt
        prompt = f"""Based on the content below, give me a one-word title for the text and return the result as Text.
        Text:
        {content}"""
        
        try:
            # Make API call with the correct parameters
            completion = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # Lower temperature for more focused responses
                max_tokens=1000,   # Limit the response length
                top_p=1,
                stream=False  # Changed to non-streaming for simplicity
            )
            
            # Extract response
            response_text = completion.choices[0].message.content
            print(response_text)
            # Extract and return the title
            return response_text
        
        except Exception as e:
            print(f"Error extracting title: {str(e)}")
            return ""  # Return an empty string if extraction fails


    def generate_video(self, content, output_filename="presentation.mp4"):
        """Main function to generate video from content"""
        try:
            # Extract topic from content
            print(content)
            topic = self.title_extraction_for_topic(content)
            print(f"Generated topic: {topic}")
            
            # Generate short intro video if possible
            intro_video_path = None
            if topic:
                try:
                    intro_video_path = self.generate_short_video(topic)
                except Exception as e:
                    print(f"Failed to generate intro video: {str(e)}")
            
            # Generate slide content with notes and explanations
            slides = self.generate_slide_content(content)
            
            # First create the main content video
            content_video_path = self.create_video_from_slides(slides, "content_video.mp4")

            # If we have both videos, concatenate them
            if intro_video_path and content_video_path:
                return self.concatenate_videos(
                    [intro_video_path, content_video_path], 
                    output_filename
                )
            # If only content video was created, return that
            elif content_video_path:
                return content_video_path
            # Fallback case
            else:
                raise Exception("Failed to generate any videos")
        except Exception as e:
            print(f"Error in generate_video: {str(e)}")
            raise