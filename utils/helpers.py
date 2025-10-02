"""
Utility functions for the SaaS review scraper.
"""
import re
import time
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps
from datetime import datetime
from dateutil.parser import parse as dateutil_parse
import requests


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 1.0, 
                      exceptions: tuple = (requests.RequestException,)):
    """
    Decorator that adds retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Failed after {max_retries} retries: {e}")
                        raise
                    
                    delay = backoff_factor * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            
        return wrapper
    return decorator


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    return text.strip()


def parse_rating(rating_text: str) -> float:
    """
    Parse rating from various text formats.
    
    Args:
        rating_text: Text containing rating information
        
    Returns:
        Numerical rating (0-5 scale)
    """
    if not rating_text:
        return 0.0
    
    # Extract numeric rating (including potential negative sign)
    rating_match = re.search(r'(-?\d+(?:\.\d+)?)', str(rating_text))
    if rating_match:
        rating = float(rating_match.group(1))
        
        # Normalize to 0-5 scale if needed
        if rating > 5:
            rating = rating / 2  # Assume 10-point scale
        
        return min(max(rating, 0.0), 5.0)
    
    return 0.0


def parse_flexible_date(date_text: str) -> Optional[datetime]:
    """
    Parse date from various formats commonly found on review sites.
    
    Args:
        date_text: Text containing date information
        
    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_text:
        return None
    
    try:
        # Clean the date text
        date_text = clean_text(date_text)
        
        # Handle relative dates
        if 'ago' in date_text.lower():
            return _parse_relative_date(date_text)
        
        # Try standard parsing
        return dateutil_parse(date_text)
        
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to parse date '{date_text}': {e}")
        return None


def _parse_relative_date(date_text: str) -> Optional[datetime]:
    """
    Parse relative dates like "2 days ago", "1 month ago", etc.
    
    Args:
        date_text: Text containing relative date
        
    Returns:
        Datetime object or None
    """
    from datetime import timedelta
    
    now = datetime.now()
    
    # Extract number and unit
    match = re.search(r'(\d+)\s+(day|week|month|year)s?\s+ago', date_text.lower())
    if not match:
        return None
    
    number = int(match.group(1))
    unit = match.group(2)
    
    if unit == 'day':
        return now - timedelta(days=number)
    elif unit == 'week':
        return now - timedelta(weeks=number)
    elif unit == 'month':
        return now - timedelta(days=number * 30)  # Approximate
    elif unit == 'year':
        return now - timedelta(days=number * 365)  # Approximate
    
    return None


def extract_company_name_variations(company_name: str) -> list[str]:
    """
    Generate variations of company name for better search matching.
    
    Args:
        company_name: Original company name
        
    Returns:
        List of name variations
    """
    variations = [company_name]
    
    # Add lowercase version
    variations.append(company_name.lower())
    
    # Add version without common suffixes
    cleaned = re.sub(r'\s+(inc|llc|corp|ltd|co)\.?$', '', company_name, flags=re.IGNORECASE)
    if cleaned != company_name:
        variations.append(cleaned)
        variations.append(cleaned.lower())
    
    # Add version with common abbreviations expanded
    expanded = company_name.replace('&', 'and')
    if expanded != company_name:
        variations.append(expanded)
        variations.append(expanded.lower())
    
    return list(set(variations))  # Remove duplicates


def generate_output_filename(company_name: str, source: str, start_date: datetime, 
                           end_date: datetime) -> str:
    """
    Generate a standardized output filename.
    
    Args:
        company_name: Name of the company
        source: Review source
        start_date: Start date for reviews
        end_date: End date for reviews
        
    Returns:
        Generated filename
    """
    # Clean company name for filename
    clean_company = re.sub(r'[^\w\s-]', '', company_name).strip()
    clean_company = re.sub(r'\s+', '_', clean_company)
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    return f"{clean_company}_{source}_reviews_{start_str}_to_{end_str}.json"


def validate_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid URL, False otherwise
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None


def safe_extract(element, selector: str, attribute: Optional[str] = None, 
                default: str = "") -> str:
    """
    Safely extract text or attribute from BeautifulSoup element.
    
    Args:
        element: BeautifulSoup element or None
        selector: CSS selector to find child element
        attribute: Attribute to extract (None for text)
        default: Default value if extraction fails
        
    Returns:
        Extracted value or default
    """
    if not element:
        return default
    
    try:
        target = element.select_one(selector)
        if not target:
            return default
        
        if attribute:
            return target.get(attribute, default)
        else:
            return clean_text(target.get_text())
    except Exception:
        return default


def setup_logging(level: str = 'INFO') -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )