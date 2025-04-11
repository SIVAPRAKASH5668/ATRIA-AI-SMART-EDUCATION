from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from .rag_tamil import RagTamil

from . import bp
rag_tamil_processor = RagTamil()

# Create base directory for the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/')
def index():
    return render_template('ragtamil.html')

@bp.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'PDF கோப்பு கிடைக்கவில்லை'}), 400
    
    files = request.files.getlist('files[]')
    valid_files = [f for f in files if f and allowed_file(f.filename)]
    
    if not valid_files:
        return jsonify({'error': 'செல்லுபடியான PDF கோப்புகள் இல்லை'}), 400

    try:
        file_paths = []
        for file in valid_files:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            file_paths.append(file_path)
        
        raw_text = rag_tamil_processor.get_pdf_text(file_paths)
        if not raw_text.strip():
            return jsonify({'error': 'PDF இல் உரை கிடைக்கவில்லை'}), 400
            
        text_chunks = rag_tamil_processor.get_text_chunks(raw_text)
        if not text_chunks:
            return jsonify({'error': 'உரைப் பகுதிகள் உருவாக்கப்படவில்லை'}), 400
            
        rag_tamil_processor.get_vector_store(text_chunks)
        
        # Clean up uploaded files
        for file_path in file_paths:
            try:
                os.remove(file_path)
            except:
                pass
                
        return jsonify({'success': 'PDF வெற்றிகரமாக செயலாக்கப்பட்டது'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': 'கேள்வி கிடைக்கவில்லை'}), 400
        
        question = data['question'].strip()
        if not question:
            return jsonify({'error': 'கேள்வியை உள்ளிடவும்'}), 400
        
        response = rag_tamil_processor.process_question(question)
        return jsonify({'answer': response})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500