import os
import uuid
import threading
from flask import render_template, request, jsonify, send_from_directory
from . import bp
import PyPDF2
import docx
from app.content_to_ai_video.content_to_video_generator import ContentToVideoGenerator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Directory for storing output videos and uploaded files
OUTPUT_DIR = os.path.join(os.getcwd(), "app", "static", "output")
UPLOAD_DIR = os.path.join(os.getcwd(), "app", "static", "uploads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Global dictionary to track job status
job_status = {}

def extract_text_from_pdf(pdf_path):
    """Extract text content from a PDF file"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n\n"
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")
    return text

def extract_text_from_docx(docx_path):
    """Extract text content from a DOCX file"""
    text = ""
    try:
        doc = docx.Document(docx_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        raise Exception(f"Error extracting text from DOCX: {str(e)}")
    return text

def extract_text_from_file(file_path):
    """Extract text from various file formats"""
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_ext == '.docx':
        return extract_text_from_docx(file_path)
    elif file_ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        raise Exception(f"Unsupported file format: {file_ext}")

def process_video_creation(job_id, content, output_filename):
    """Background task to create video"""
    try:
        # Update job status to "processing"
        job_status[job_id] = {
            "status": "processing", 
            "message": "Starting video generation..."
        }
        
        # Create video generator
        generator = ContentToVideoGenerator(
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            pexels_api_key=os.environ.get("PEXELS_API_KEY")
        )
        
        # Generate video with corrected method call
        video_path = generator.generate_video(content, os.path.join(OUTPUT_DIR, output_filename))
        
        # Update job status to "completed" with video path
        job_status[job_id] = {
            "status": "completed",
            "message": "Video generation completed!",
            "video_path": f"/static/output/{output_filename}",
            "filename": output_filename
        }
    
    except Exception as e:
        # Update job status to "failed" with error message
        job_status[job_id] = {
            "status": "failed",
            "message": f"Error generating video: {str(e)}"
        }
        print(f"Error in job {job_id}: {str(e)}")

@bp.route('/')
def index():
    """Render the main page"""
    return render_template('content_to_ai_video.html')

@bp.route('/generate', methods=['POST'])
def generate_video():
    """API endpoint to generate a video from content or uploaded file"""
    try:
        input_type = request.form.get('inputType')
        content = None
        
        # Generate a unique job ID and filename
        job_id = str(uuid.uuid4())
        output_filename = f"video_{job_id}.mp4"
        
        # Process based on input type
        if input_type == 'text':
            # Get content directly from text input
            content = request.form.get('contentText')
            if not content or not content.strip():
                return jsonify({
                    "status": "error",
                    "message": "No content provided"
                }), 400
                
        elif input_type == 'file':
            # Get content from uploaded file
            if 'contentFile' not in request.files:
                return jsonify({
                    "status": "error",
                    "message": "No file uploaded"
                }), 400
                
            file = request.files['contentFile']
            if file.filename == '':
                return jsonify({
                    "status": "error",
                    "message": "No file selected"
                }), 400
                
            # Check file extension
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in ['.pdf', '.docx', '.txt']:
                return jsonify({
                    "status": "error",
                    "message": "Unsupported file format. Please upload PDF, DOCX, or TXT files."
                }), 400
                
            # Save uploaded file
            uploaded_file_path = os.path.join(UPLOAD_DIR, f"upload_{job_id}{file_ext}")
            file.save(uploaded_file_path)
            
            try:
                # Extract text from file
                content = extract_text_from_file(uploaded_file_path)
                
                # Clean up the uploaded file after extracting content
                os.remove(uploaded_file_path)
                
                if not content or not content.strip():
                    return jsonify({
                        "status": "error",
                        "message": "Could not extract any text from the uploaded file."
                    }), 400
                    
            except Exception as e:
                # If there's an error, clean up and return error message
                if os.path.exists(uploaded_file_path):
                    os.remove(uploaded_file_path)
                    
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 400
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid input type"
            }), 400
            
        # Set initial job status
        job_status[job_id] = {
            "status": "queued",
            "message": "Job queued, waiting to start..."
        }
        
        # Start video generation in a background thread
        thread = threading.Thread(
            target=process_video_creation,
            args=(job_id, content, output_filename)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": "Video generation started",
            "job_id": job_id
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500

@bp.route('/status/<job_id>')
def get_job_status(job_id):
    """API endpoint to check the status of a job"""
    if job_id in job_status:
        return jsonify(job_status[job_id])
    else:
        return jsonify({
            "status": "error",
            "message": "Job not found"
        }), 404

@bp.route('/download/<filename>')
def download_video(filename):
    """API endpoint to download the generated video"""
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)