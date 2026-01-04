"""
Document Processor - File upload processing

Extracts text from PDFs and TXT files, then chunks them for vector storage.

Flow:
1. Receives file (PDF or TXT)
2. Extracts all text from file
3. Splits text into chunks (1000 chars with 200 overlap)
4. Returns chunks ready for vector storage

Why chunking?
- Large documents don't fit in single vector
- Chunking allows retrieving specific relevant sections
- Overlap ensures context isn't lost at chunk boundaries
"""

import os
import tempfile
from typing import List, Dict


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.
    
    Args:
        file_path: Path to PDF file
    
    Returns:
        str: Extracted text from all pages
    
    Raises:
        Exception: If PyPDF2/pypdf is not installed or extraction fails
    
    Note:
        - Requires PyPDF2 or pypdf library
        - Extracts text from all pages
        - Returns concatenated text with newlines between pages
    """
    try:
        import PyPDF2
    except ImportError:
        try:
            import pypdf as PyPDF2
        except ImportError:
            raise Exception("PDF processing requires PyPDF2 or pypdf. Install with: pip install PyPDF2")
    
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text from TXT file.
    
    Args:
        file_path: Path to TXT file
    
    Returns:
        str: File contents
    
    Note:
        - Assumes UTF-8 encoding
        - Returns full file contents
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read().strip()


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into chunks with overlap for better context preservation.
    
    Why overlap?
    - Prevents losing context at chunk boundaries
    - If a sentence spans two chunks, overlap ensures it's captured
    - Helps maintain semantic meaning across chunks
    
    Args:
        text: The text to chunk
        chunk_size: Target size of each chunk (in characters, default: 1000)
        overlap: Number of characters to overlap between chunks (default: 200)
    
    Returns:
        List[str]: List of text chunks
    
    Note:
        - Tries to break at sentence boundaries (better for context)
        - Last chunk may be smaller than chunk_size
        - Overlap ensures no information is lost
    """
    if len(text) <= chunk_size:
        return [text]  # Text is small enough, return as single chunk
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Get chunk end position
        end = start + chunk_size
        
        # Try to break at sentence boundary (better for context)
        if end < len(text):
            # Look for sentence endings near the chunk boundary
            # This prevents cutting sentences in half
            for punct in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
                last_punct = text.rfind(punct, start, end)
                if last_punct != -1:
                    end = last_punct + 2  # Include punctuation and space
                    break
        
        # Extract chunk
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start forward with overlap
        # Overlap ensures context isn't lost at boundaries
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


def process_uploaded_file(file, filename: str) -> List[Dict[str, str]]:
    """
    Process uploaded file and return chunks ready for vector storage.
    
    Flow:
    1. Save file to temporary location
    2. Extract text based on file type (PDF or TXT)
    3. Chunk the text
    4. Prepare chunks with metadata
    5. Clean up temp file
    6. Return chunks
    
    Args:
        file: File object from Flask request
        filename: Original filename
    
    Returns:
        List[Dict]: List of chunk dicts, each with:
            - "content": The chunk text
            - "metadata": Dict with filename, chunk_index, total_chunks, type, file_type
    
    Raises:
        ValueError: If file type is unsupported or extraction fails
    """
    # Save to temporary file
    file_ext = os.path.splitext(filename)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        file.save(tmp_file.name)
        tmp_path = tmp_file.name
    
    try:
        # Extract text based on file type
        if file_ext == '.pdf':
            text = extract_text_from_pdf(tmp_path)
        elif file_ext in ['.txt', '.text']:
            text = extract_text_from_txt(tmp_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text.strip():
            raise ValueError("File appears to be empty or text extraction failed")
        
        # Chunk the text (1000 chars with 200 overlap)
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        
        # Prepare chunks for storage
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            processed_chunks.append({
                "content": chunk,  # The actual text chunk
                "metadata": {
                    "filename": filename,
                    "chunk_index": i,  # Which chunk this is (0-indexed)
                    "total_chunks": len(chunks),  # Total number of chunks
                    "type": "document_chunk",  # Mark as document chunk
                    "file_type": file_ext  # Original file extension
                }
            })
        
        return processed_chunks
        
    finally:
        # Always clean up temp file, even on error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
