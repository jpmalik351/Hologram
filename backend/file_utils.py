"""
File Utilities - Hash calculation and versioning

Provides utility functions for:
- SHA256 hash calculation for duplicate detection
- Filename versioning (_v2, _v3, etc.)
- Filename sanitization
"""

import hashlib
import os
import re
from typing import Tuple


def calculate_file_hash(file_data: bytes) -> str:
    """
    Calculate SHA256 hash of file contents.
    
    Args:
        file_data: File contents as bytes
    
    Returns:
        str: Hexadecimal SHA256 hash string
    
    Note:
        - SHA256 provides good collision resistance
        - Same content = same hash, regardless of filename
        - Used for duplicate detection
    """
    return hashlib.sha256(file_data).hexdigest()


def extract_version_number(filename: str) -> Tuple[str, int]:
    """
    Extract version number from filename if it exists.
    
    Examples:
        "document.pdf" -> ("document.pdf", 0)
        "document_v2.pdf" -> ("document.pdf", 2)
        "document_v10.txt" -> ("document.txt", 10)
    
    Args:
        filename: Original filename
    
    Returns:
        Tuple[str, int]: (base_filename, version_number)
    """
    # Match pattern: filename_vN.ext
    pattern = r'^(.+?)_v(\d+)(\.[^.]+)$'
    match = re.match(pattern, filename)
    
    if match:
        base_name = match.group(1)
        version = int(match.group(2))
        extension = match.group(3)
        base_filename = f"{base_name}{extension}"
        return (base_filename, version)
    
    return (filename, 0)


def get_next_version_filename(filename: str, existing_filenames: list) -> str:
    """
    Generate next version filename based on existing files.
    
    Examples:
        filename="document.pdf", existing=["document.pdf"]
        -> "document_v2.pdf"
        
        filename="document.pdf", existing=["document.pdf", "document_v2.pdf"]
        -> "document_v3.pdf"
    
    Args:
        filename: Original filename
        existing_filenames: List of existing filenames in database
    
    Returns:
        str: Versioned filename (e.g., "document_v2.pdf")
    """
    # Get base name and extension
    name_without_ext, ext = os.path.splitext(filename)
    
    # Find all existing versions
    max_version = 1
    for existing in existing_filenames:
        base_name, version = extract_version_number(existing)
        # Check if it's the same base file (ignoring version)
        existing_base = os.path.splitext(base_name)[0]
        current_base = os.path.splitext(filename)[0]
        
        if existing_base == current_base:
            if version > max_version:
                max_version = version
    
    # Generate next version
    next_version = max_version + 1
    return f"{name_without_ext}_v{next_version}{ext}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename
    
    Note:
        - Removes path components (keeps only filename)
        - Removes or replaces invalid characters
        - Limits length to prevent issues
    """
    # Get just the filename (no path)
    filename = os.path.basename(filename)
    
    # Replace invalid characters with underscores
    # Keep alphanumeric, dots, underscores, hyphens
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length (max 255 chars is common filesystem limit)
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        name = name[:255-len(ext)]
        filename = name + ext
    
    return filename
