# flask route handlers
from flask import render_template, request, send_file, flash
from pathlib import Path
import os

from backend.processor import process_articles, ProcessingError

# Configuration
MAX_URLS = 10  # Maximum number of URLs per request
ALLOWED_FORMATS = ['txt', 'pdf']


def register_routes(app):
    """Register all application routes"""
    
    @app.route('/')
    def index():
        """Render the homepage"""
        return render_template('index.html')
    
    
    @app.route('/convert', methods=['POST'])
    def convert():
        """Handle article conversion requests"""
        try:
            # Get form data
            urls_text = request.form.get('urls', '').strip()
            output_format = request.form.get('format', '').strip().lower()
            
            # Validate inputs
            if not urls_text:
                return render_template('index.html', 
                                     error="Please provide at least one URL")
            
            if output_format not in ALLOWED_FORMATS:
                return render_template('index.html', 
                                     error=f"Invalid format. Choose from: {', '.join(ALLOWED_FORMATS)}")
            
            # Parse URLs (split by newlines)
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            
            if not urls:
                return render_template('index.html', 
                                     error="No valid URLs found")
            
            if len(urls) > MAX_URLS:
                return render_template('index.html', 
                                     error=f"Too many URLs. Maximum is {MAX_URLS}")
            
            # Process articles
            output_path = process_articles(urls, output_format)
            
            # Determine MIME type and filename
            if output_path.suffix == '.zip':
                mimetype = 'application/zip'
                download_name = 'articles.zip'
            elif output_format == 'txt':
                mimetype = 'text/plain'
                download_name = output_path.name
            elif output_format == 'pdf':
                mimetype = 'application/pdf'
                download_name = output_path.name
            else:
                mimetype = 'application/octet-stream'
                download_name = output_path.name
            
            # Send file and schedule cleanup
            response = send_file(
                output_path,
                mimetype=mimetype,
                as_attachment=True,
                download_name=download_name
            )
            
            # Schedule cleanup of temporary files after response is sent
            @response.call_on_close
            def cleanup():
                try:
                    # Delete the file
                    if output_path.exists():
                        output_path.unlink()
                    
                    # Delete parent directory if it's our temp directory
                    parent_dir = output_path.parent
                    if parent_dir.name.startswith('article_converter_'):
                        # Delete all files in the directory
                        for file in parent_dir.iterdir():
                            if file.is_file():
                                file.unlink()
                        # Remove the directory
                        parent_dir.rmdir()
                except Exception as e:
                    app.logger.error(f"Cleanup error: {e}")
            
            return response
            
        except ProcessingError as e:
            return render_template('index.html', 
                                 error=str(e))
        
        except Exception as e:
            app.logger.error(f"Unexpected error: {e}")
            return render_template('index.html', 
                                 error="An unexpected error occurred. Please try again.")