# orchestration logic
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple
import uuid
import re

from backend.fetcher import fetch_article_html, FetchError
from backend.parser import parse_article, ParseError
from backend.converters.txt_converter import convert_to_txt, TxtConversionError
from backend.converters.pdf_converter import convert_to_pdf, PdfConversionError


class ProcessingError(Exception):
    """Custom exception for processing errors"""
    pass


def validate_url(url: str) -> bool:
    """Basic URL validation"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def sanitize_filename(title: str) -> str:
    """Convert article title to safe filename"""
    # Remove invalid characters
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace spaces with underscores
    safe_title = safe_title.replace(' ', '_')
    # Limit length
    safe_title = safe_title[:100]
    # Default if empty
    return safe_title if safe_title else 'article'


def process_single_article(url: str, output_format: str, temp_dir: Path) -> Tuple[Path, str]:
    """
    Process a single article URL and return the output file path.
    
    Args:
        url: Article URL
        output_format: 'txt' or 'pdf'
        temp_dir: Temporary directory for output
    
    Returns:
        Tuple of (output_file_path, article_title)
    
    Raises:
        ProcessingError: If any step fails
    """
    try:
        # Step 1: Fetch HTML
        html = fetch_article_html(url)
        
        # Step 2: Parse article
        article_data = parse_article(html, url)
        
        # Step 3: Create filename
        safe_filename = sanitize_filename(article_data['title'])
        output_filename = f"{safe_filename}.{output_format}"
        output_path = temp_dir / output_filename
        
        # Step 4: Convert to desired format
        if output_format == 'txt':
            convert_to_txt(article_data, output_path)
        elif output_format == 'pdf':
            convert_to_pdf(article_data, output_path)
        else:
            raise ProcessingError(f"Unsupported format: {output_format}")
        
        return output_path, article_data['title']
        
    except (FetchError, ParseError, TxtConversionError, PdfConversionError) as e:
        raise ProcessingError(f"Failed to process {url}: {str(e)}")
    except Exception as e:
        raise ProcessingError(f"Unexpected error processing {url}: {str(e)}")


def process_articles(urls: List[str], output_format: str) -> Path:
    """
    Process multiple article URLs and return path to output file or ZIP.
    
    Args:
        urls: List of article URLs
        output_format: 'txt' or 'pdf'
    
    Returns:
        Path to output file (single article) or ZIP file (multiple articles)
    
    Raises:
        ProcessingError: If processing fails
    """
    if not urls:
        raise ProcessingError("No URLs provided")
    
    # Validate format
    if output_format not in ['txt', 'pdf']:
        raise ProcessingError(f"Invalid format: {output_format}")
    
    # Create unique temporary directory
    temp_dir = Path(tempfile.gettempdir()) / f"article_converter_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Process each URL
        output_files = []
        errors = []
        
        for url in urls:
            url = url.strip()
            if not url:
                continue
                
            if not validate_url(url):
                errors.append(f"Invalid URL: {url}")
                continue
            
            try:
                output_path, title = process_single_article(url, output_format, temp_dir)
                output_files.append(output_path)
            except ProcessingError as e:
                errors.append(str(e))
        
        # Check if we got any successful conversions
        if not output_files:
            error_msg = "No articles could be processed."
            if errors:
                error_msg += " Errors: " + "; ".join(errors)
            raise ProcessingError(error_msg)
        
        # Single file - return directly
        if len(output_files) == 1:
            return output_files[0]
        
        # Multiple files - create ZIP
        zip_path = temp_dir / f"articles_{uuid.uuid4().hex[:8]}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_files:
                zipf.write(file_path, file_path.name)
        
        return zip_path
        
    except ProcessingError:
        raise
    except Exception as e:
        raise ProcessingError(f"Processing failed: {str(e)}")