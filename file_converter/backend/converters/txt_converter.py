# converts files to txt files
from pathlib import Path
from typing import Dict

class TxtConversionError(Exception):
    """Custom exception for TXT conversion errors"""
    pass

def convert_to_txt(article_data: Dict[str, str], output_path: Path) -> None:
    """
    Convert article data to a plain text file.
    
    Args:
        article_data: Dictionary with 'title' and 'text' keys
        output_path: Path object for the output file
    
    Raises:
        TxtConversionError: If conversion fails
    """
    try:
        title = article_data.get('title', 'Untitled')
        text = article_data.get('text', '')
        
        if not text:
            raise TxtConversionError("No text content to convert")
        
        # Format the content
        content = f"{title}\n"
        content += "=" * len(title) + "\n\n"
        content += text
        
        # Write to file with UTF-8 encoding
        output_path.write_text(content, encoding='utf-8')
        
    except TxtConversionError:
        raise
    
    except Exception as e:
        raise TxtConversionError(f"Failed to create TXT file: {str(e)}")