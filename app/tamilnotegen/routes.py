from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import os
from .tamilnotegen import TamilTextProcessor, TamilPDFGenerator

from . import bp

def allowed_file(filename):
    """Check if uploaded file has PDF extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

@bp.route('/')
def home():
    """Render the main page"""
    return render_template('tamilnotesgen.html')

@bp.route('/upload', methods=['POST'])
def handle_upload():
    """Handle file upload and process PDFs"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'கோப்புகள் இல்லை'}), 400
        
        files = request.files.getlist('files[]')
        if not files or not any(file.filename for file in files):
            return jsonify({'error': 'கோப்புகள் தேர்ந்தெடுக்கப்படவில்லை'}), 400
        
        saved_files = []
        
        # Save uploaded files
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                saved_files.append(path)
        
        if not saved_files:
            return jsonify({'error': 'செல்லுபடியாகும் PDF கோப்புகள் இல்லை'}), 400
        
        # Process files
        processor = TamilTextProcessor()
        text = processor.extract_text(saved_files)
        topics = processor.process_content(text)
        
        # Generate PDFs for each topic
        result_topics = []
        for topic in topics:
            pdf_filename = TamilPDFGenerator.create_pdf(topic)
            topic['pdf'] = pdf_filename
            result_topics.append(topic)
        
        # Cleanup uploaded files
        for path in saved_files:
            try:
                os.remove(path)
            except Exception as e:
                current_app.logger.error(f"Error removing file {path}: {str(e)}")
        
        return jsonify({'topics': result_topics})
    
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/download/<filename>')
def serve_pdf(filename):
    """Serve generated PDF files"""
    try:
        file_path = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError('கோப்பு கிடைக்கவில்லை')
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"notes_{filename}"
        )
    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 404

# Error handlers
@bp.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'கோப்பு கிடைக்கவில்லை'}), 404

@bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'சேவையகப் பிழை ஏற்பட்டது'}), 500