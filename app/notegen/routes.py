from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfReader
from .notegen import EnhancedTopicProcessor, EnhancedPDFGenerator, allowed_file

# Create blueprint
from . import bp

@bp.route('/')
def home():
    return render_template('notesprovider.html')

@bp.route('/upload', methods=['POST'])
def handle_upload():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files selected'}), 400
    
    files = request.files.getlist('files[]')
    if not files:
        return jsonify({'error': 'No valid files'}), 400
    
    try:
        # Process files
        saved_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                saved_files.append(path)
        
        # Extract text
        text = "\n".join(PdfReader(path).pages[0].extract_text() for path in saved_files)
        
        # Process content
        processor = EnhancedTopicProcessor()
        topics = processor.process_content(text)
        
        # Generate PDFs
        for topic in topics:
            topic['pdf'] = EnhancedPDFGenerator.create_pdf(topic)
        
        # Cleanup
        for path in saved_files:
            os.remove(path)
        
        return jsonify({'success': True, 'topics': topics})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Change the download route to include the blueprint prefix
@bp.route('/download/<filename>')
def serve_pdf(filename):
    try:
        # Add verification and logging
        file_path = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        if not os.path.exists(file_path):
            current_app.logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"StudyNotes_{filename}",
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500