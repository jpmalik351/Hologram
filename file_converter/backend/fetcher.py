# fetch article HTML
import requests
from typing import Optional

class FetchError(Exception):
    """Custom exception for fetch-related errors"""
    pass

def fetch_article_html(url: str, timeout: int = 10) -> str:
    """
    Fetch raw HTML content from a given URL.
    
    Args:
        url: The article URL to fetch
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Raw HTML content as string
    
    Raises:
        FetchError: If the request fails for any reason
    """
    try:
        # Set user agent to avoid being blocked by some sites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raise exception for 4xx/5xx status codes
        
        return response.text
        
    except requests.exceptions.Timeout:
        raise FetchError(f"Request timed out after {timeout} seconds")
    
    except requests.exceptions.ConnectionError:
        raise FetchError(f"Could not connect to {url}")
    
    except requests.exceptions.HTTPError as e:
        raise FetchError(f"HTTP error {e.response.status_code}: {url}")
    
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Failed to fetch URL: {str(e)}")
    
    except Exception as e:
        raise FetchError(f"Unexpected error: {str(e)}")