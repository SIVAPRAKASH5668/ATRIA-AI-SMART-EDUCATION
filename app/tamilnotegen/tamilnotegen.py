# File: tamilnotegen.py
from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter
from groq import Groq
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import fitz
import os
import json
import re
import uuid
import json5
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

class TamilTextProcessor:
    """Class for processing Tamil text from PDFs with enhanced error handling"""
    
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=500,
            separators=['\n\n', '।', '॥']
        )
        self.client = Groq(api_key=groq_api_key)

    def extract_text(self, pdf_paths):
        full_text = ""
        for path in pdf_paths:
            try:
                doc = fitz.open(path)
                for page in doc:
                    text = page.get_text("text")
                    full_text += re.sub(r'\s+', ' ', text).strip()
                doc.close()
            except Exception as e:
                current_app.logger.error(f"PDF read error: {str(e)}")
                raise RuntimeError(f"PDF பிழை: {os.path.basename(path)}")
        return full_text

    def clean_text(self, text):
        cleaned = re.sub(r'[^\u0B80-\u0BFF\s.,?!]', '', text)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def clean_json_response(self, json_str):
        json_str = re.sub(r'```json|```', '', json_str)
        fixes = [
            (r'(?<!\\)"', "'"),
            (r'\\{2,}"', '"'),
            (r',\s*([}\]])', r'\1'),
            (r'\u0bcd\\u200d', '\u0bcd')
        ]
        for pattern, replacement in fixes:
            json_str = re.sub(pattern, replacement, json_str)
        return json_str.strip()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_groq_api(self, prompt):
        return self.client.chat.completions.create(
            messages=[{
                "role": "system",
                "content": "Generate VALID JSON in Tamil with proper escaping"
            }, {
                "role": "user",
                "content": prompt
            }],
            model="mixtral-8x7b-32768",
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=2500,
            timeout=30
        )

    def process_content(self, text):
        try:
            cleaned_text = self.clean_text(text)
            chunks = self.text_splitter.split_text(cleaned_text)
            enhanced_topics = []

            for chunk in chunks[:3]:
                try:
                    prompt = f"""பின்வரும் உரையிலிருந்து JSON ஐ உருவாக்கவும்:

JSON வடிவம்:
{{
    "topics": [
        {{
            "id": 1,
            "title": "தலைப்பு (5-7 சொற்கள்)",
            "content": "சுருக்கமான விளக்கம் (3-5 வாக்கியங்கள்)"
        }}
    ]
}}

கட்டாய விதிகள்:
1. தமிழ் எழுத்துகள் மற்றும் அடிப்படை நிறுத்தக்குறிகள் மட்டுமே
2. JSON கட்டமைப்பை கண்டிப்பாக பின்பற்றவும்
3. 500 எழுத்துகளுக்குள் உள்ளடக்கம்
4. சிறப்பு எழுத்துகள் தவிர்க்கவும்

உரை:
{chunk}"""

                    response = self._call_groq_api(prompt)
                    json_str = self.clean_json_response(response.choices[0].message.content)
                    
                    try:
                        data = json5.loads(json_str)
                    except Exception as e:
                        current_app.logger.error(f"Invalid JSON: {json_str}")
                        raise RuntimeError(f"JSON பிழை: {str(e)}")

                    if 'topics' not in data:
                        raise ValueError("தலைப்புகள் கிடைக்கவில்லை")
                    
                    for topic in data['topics']:
                        topic['id'] = str(uuid.uuid4())
                        topic['title'] = self._validate_tamil_text(topic.get('title', ''), 50)
                        topic['content'] = self._validate_tamil_text(topic.get('content', ''), 500)
                    
                    enhanced_topics.extend(data['topics'])

                except Exception as e:
                    current_app.logger.warning(f"Chunk processing failed: {str(e)}")
                    if len(chunks) > 1:
                        return self.process_content(text[:len(text)//2])
                    raise

            return enhanced_topics[:5]

        except Exception as e:
            current_app.logger.error(f"Processing failed: {str(e)}")
            raise RuntimeError(f"செயலாக்க பிழை: {str(e)}")

    def _validate_tamil_text(self, text, max_length):
        text = re.sub(r'[^\u0B80-\u0BFF\s.,?!]', '', text)
        return text[:max_length].strip()


class TamilPDFGenerator:
    """Enhanced PDF generator with proper Tamil font support"""
    
    @classmethod
    def initialize_fonts(cls):
        """Initialize and register Tamil fonts"""
        try:
            # Register regular font
            regular_font_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'fonts',
                'NotoSansTamil-Regular.ttf'
            )
            pdfmetrics.registerFont(TTFont('TamilRegular', regular_font_path))
            
            # Register bold font
            bold_font_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'fonts',
                'NotoSansTamil-Bold.ttf'
            )
            pdfmetrics.registerFont(TTFont('TamilBold', bold_font_path))
            
            # Add font mapping
            addMapping('Tamil', 0, 0, 'TamilRegular')  # normal
            addMapping('Tamil', 1, 0, 'TamilBold')     # bold
            
        except Exception as e:
            current_app.logger.error(f"Font initialization error: {str(e)}")
            raise RuntimeError("எழுத்துரு பிழை")

    @classmethod
    def create_pdf(cls, topic):
        """Generate PDF with proper Tamil text handling"""
        try:
            cls.initialize_fonts()
            
            # Validate topic
            if not all(key in topic for key in ['id', 'title', 'content']):
                raise ValueError("தவறான தலைப்பு வடிவம்")
            
            # Generate filename
            filename = f"notes_{uuid.uuid4().hex[:8]}.pdf"
            filepath = os.path.join(current_app.config['NOTES_FOLDER'], filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            # Create custom styles
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'TamilTitle',
                fontName='Tamil',
                fontSize=18,
                spaceAfter=30,
                spaceBefore=30,
                alignment=1,  # Center alignment
                leading=24    # Line height
            )
            
            content_style = ParagraphStyle(
                'TamilContent',
                fontName='Tamil',
                fontSize=12,
                spaceAfter=12,
                spaceBefore=12,
                leading=18    # Line height
            )
            
            # Build PDF content
            elements = []
            
            # Add title
            elements.append(Paragraph(topic['title'], title_style))
            elements.append(Spacer(1, 20))
            
            # Add content - split into paragraphs
            paragraphs = topic['content'].split('.')
            for para in paragraphs:
                if para.strip():
                    elements.append(Paragraph(para.strip() + '.', content_style))
                    elements.append(Spacer(1, 10))
            
            # Build PDF
            doc.build(elements)
            return filename
            
        except Exception as e:
            current_app.logger.error(f"PDF generation error: {str(e)}")
            raise RuntimeError(f"PDF பிழை: {str(e)}")