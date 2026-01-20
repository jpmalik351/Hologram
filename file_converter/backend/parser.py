# extract clean text
from newspaper import Article
from typing import Dict

class ParseError(Exception):
    """Custom exception for parsing-related errors"""
    pass

def parse_article(html: str, url: str) -> Dict[str, str]:
    """
    Extract clean article text and title from HTML.
    
    Args:
        html: Raw HTML content
        url: Original URL (used by newspaper3k for context)
    
    Returns:
        Dictionary with 'title' and 'text' keys
    
    Raises:
        ParseError: If parsing fails or content is empty
    """
    try:
        # Create article object
        article = Article(url)
        
        # Download step is skipped since we already have HTML
        article.set_html(html)
        
        # Parse the article
        article.parse()
        
        # Extract title and text
        title = article.title.strip() if article.title else "Untitled Article"
        text = article.text.strip()
        
        # Validate we got content
        if not text:
            raise ParseError("No article text could be extracted")
        
        if len(text) < 100:
            raise ParseError("Extracted text is too short (less than 100 characters)")
        
        return {
            'title': title,
            'text': text
        }
        
    except ParseError:
        raise  # Re-raise our custom errors
    
    except Exception as e:
        raise ParseError(f"Failed to parse article: {str(e)}")