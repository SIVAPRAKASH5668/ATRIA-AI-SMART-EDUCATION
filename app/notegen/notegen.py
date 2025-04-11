from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter
from groq import Groq
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
import os
import uuid
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=groq_api_key)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

class EnhancedTopicProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=300
        )

    def process_content(self, text):
        try:
            # Clean text before processing
            cleaned_text = re.sub(r'\\', r'\\\\', text)  # Escape backslashes
            cleaned_text = re.sub(r'"', r'\"', cleaned_text)  # Escape quotes
            
            chunks = self.text_splitter.split_text(cleaned_text)
            enhanced_topics = []
            
            for chunk in chunks[:3]:
                prompt = f"""Analyze this text and create detailed study notes:
                {chunk}
                
                For each main topic:
                1. Create a clear heading
                2. List 5-7 key concepts
                3. Add important definitions
                4. Include relevant examples
                5. Provide summary
                
                Format as JSON with PROPER ESCAPING:
                {{
                    "topics": [
                        {{
                            "id": "uuid",
                            "title": "Topic Title",
                            "key_concepts": ["concept1", "concept2"],
                            "definitions": ["term: definition"],
                            "examples": ["example1", "example2"],
                            "summary": "concise summary",
                            "subtopics": [
                                {{
                                    "heading": "Subtopic Title",
                                    "content": ["point1", "point2"]
                                }}
                            ]
                        }}
                    ]
                }}
                """
                
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.4,
                    response_format={"type": "json_object"},
                    max_tokens=4000
                )
                
                # Clean the response before parsing
                json_str = response.choices[0].message.content
                json_str = json_str.replace('\\', '\\\\')
                
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Attempt to fix common JSON issues
                    json_str = re.sub(r'(?<!\\)"', r'\"', json_str)
                    json_str = re.sub(r"'(?![tf\d])", '"', json_str)
                    data = json.loads(json_str)
                
                for topic in data['topics']:
                    topic['id'] = str(uuid.uuid4())
                    enhanced_topics.append(topic)
            
            return enhanced_topics[:5]

        except Exception as e:
            raise RuntimeError(f"Processing error: {str(e)}")

class EnhancedPDFGenerator:
    @staticmethod
    def create_pdf(topic):
        filename = f"notes_{topic['id']}.pdf"
        filepath = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom Styles
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=22,
            leading=24,
            spaceAfter=14,
            textColor='#2B6CB0'
        )
        
        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor='#2C5282',
            spaceAfter=8
        )
        
        bullet_style = ParagraphStyle(
            'Bullet',
            parent=styles['BodyText'],
            fontSize=12,
            leading=14,
            leftIndent=10,
            spaceAfter=6
        )
        
        # Add Content
        elements.append(Paragraph(topic['title'], title_style))
        
        # Key Concepts
        elements.append(Paragraph("Key Concepts:", heading_style))
        for concept in topic['key_concepts']:
            elements.append(Paragraph(f"• {concept}", bullet_style))
        elements.append(Spacer(1, 16))
        
        # Definitions
        if topic.get('definitions'):
            elements.append(Paragraph("Important Definitions:", heading_style))
            for definition in topic['definitions']:
                elements.append(Paragraph(f"‣ {definition}", bullet_style))
            elements.append(Spacer(1, 16))
        
        # Examples
        if topic.get('examples'):
            elements.append(Paragraph("Examples:", heading_style))
            for example in topic['examples']:
                elements.append(Paragraph(f"⁃ {example}", bullet_style))
            elements.append(Spacer(1, 16))
        
        # Subtopics
        for subtopic in topic.get('subtopics', []):
            elements.append(Paragraph(subtopic['heading'], heading_style))
            for point in subtopic['content']:
                elements.append(Paragraph(f"• {point}", bullet_style))
            elements.append(Spacer(1, 12))
        
        # Summary
        elements.append(Paragraph("Summary:", heading_style))
        elements.append(Paragraph(topic['summary'], bullet_style))
        
        doc.build(elements)
        return filename