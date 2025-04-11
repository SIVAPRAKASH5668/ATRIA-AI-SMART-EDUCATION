from flask import render_template, request, send_file, current_app
from werkzeug.utils import secure_filename
import os
from .video_processor import VideoProcessor
from .pdf_generator import PDFGenerator,SlideProcessor
from . import bp

@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'video' in request.files:
        video_file = request.files['video']
        if video_file and video_file.filename:
            try:
                # Save uploaded video
                filename = secure_filename(video_file.filename)
                video_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                video_file.save(video_path)
                
                # Process video
                processor = VideoProcessor(video_path)
                slides_folder = processor.process_video()
                
                # Generate PDF
                pdf_output = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{os.path.splitext(filename)[0]}.pdf")
                slide_processor = SlideProcessor(slides_folder, pdf_output)
                pdf_path = slide_processor.process_slide_images()
                
                if not os.path.exists(os.path.dirname(pdf_output)):
                    os.makedirs(os.path.dirname(pdf_output))

                # Process and save the PDF output
                pdf_path = slide_processor.process_slide_images()

                # Ensure the path is correct
                print(f"PDF output path: {pdf_path}")

                return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
                
            except Exception as e:
                return f"Error processing video: {str(e)}", 500
                
    return render_template('video2pdf.html')