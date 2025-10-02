"""
TrustRadius.com review scraper implementation.
"""
import re
import urllib.parse
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup

from scrapers.base_scraper import ReviewScraper, ScrapingError
from models.review import Review
from utils.helpers import (
    retry_with_backoff, clean_text, parse_rating, 
    parse_flexible_date, safe_extract, extract_company_name_variations
)


class TrustRadiusScraper(ReviewScraper):
    """
    Scraper for TrustRadius.com reviews.
    """
    
    def __init__(self):
        super().__init__("trustradius")
        self.base_url = "https://www.trustradius.com"
        
    @retry_with_backoff(max_retries=3)
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for a company on TrustRadius and return the product URL.
        
        Args:
            company_name: Name of the company to search for
            
        Returns:
            Product URL if found, None otherwise
        """
        search_url = f"{self.base_url}/products"
        
        # Try multiple variations of the company name
        for variation in extract_company_name_variations(company_name):
            params = {'q': variation}
            
            self.logger.info(f"Searching TrustRadius for: {variation}")
            
            try:
                response = self.session.get(search_url, params=params, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for product links in search results
                # TrustRadius typically uses /products/{product-name} URLs
                product_links = soup.select('a[href*="/products/"]')
                
                for link in product_links:
                    product_url = link.get('href')
                    if product_url and not product_url.startswith('http'):
                        product_url = self.base_url + product_url
                    
                    # Get product name from link text or nearby elements
                    product_name = clean_text(link.get_text())
                    
                    # Also check for product name in parent containers
                    if not product_name:
                        parent = link.parent
                        while parent and not product_name:
                            product_name = clean_text(parent.get_text())
                            parent = parent.parent
                            if len(product_name) > 200:  # Avoid getting too much text
                                break
                    
                    # Check if this looks like a match
                    if self._is_company_match(variation, product_name):
                        self.logger.info(f"Found TrustRadius product: {product_url}")
                        return product_url
                        
            except Exception as e:
                self.logger.warning(f"Search failed for '{variation}': {e}")
                continue
        
        return None
    
    def _is_company_match(self, search_term: str, product_name: str) -> bool:
        """
        Check if a product name matches the search term.
        
        Args:
            search_term: Original search term
            product_name: Product name from search results
            
        Returns:
            True if it's likely a match
        """
        if not product_name or len(product_name) < 2:
            return False
            
        search_lower = search_term.lower()
        product_lower = product_name.lower()
        
        # Simple substring matching
        return (search_lower in product_lower or 
                product_lower in search_lower or
                self._fuzzy_match(search_lower, product_lower))
    
    def _fuzzy_match(self, term1: str, term2: str) -> bool:
        """Simple fuzzy matching for company names."""
        # Remove common words and punctuation
        clean1 = re.sub(r'\b(the|inc|llc|corp|ltd|software|reviews?)\b|[^\w\s]', '', term1).strip()
        clean2 = re.sub(r'\b(the|inc|llc|corp|ltd|software|reviews?)\b|[^\w\s]', '', term2).strip()
        
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        # Check for significant word overlap
        if len(words1) > 0 and len(words2) > 0:
            overlap = len(words1.intersection(words2))
            return overlap / max(len(words1), len(words2)) > 0.5
        
        return False
    
    @retry_with_backoff(max_retries=3)
    def get_reviews_page(self, product_url: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews for a specific page from TrustRadius.
        
        Args:
            product_url: Product URL from search_company
            page: Page number to retrieve
            
        Returns:
            Dictionary with reviews data and pagination info
        """
        # Construct reviews URL
        if '/reviews' not in product_url:
            reviews_url = product_url.rstrip('/') + '/reviews'
        else:
            reviews_url = product_url
        
        # TrustRadius pagination
        params = {}
        if page > 1:
            params['page'] = page
        
        self.logger.debug(f"Fetching TrustRadius reviews page {page}: {reviews_url}")
        
        try:
            response = self.session.get(reviews_url, params=params, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find review containers - TrustRadius uses various CSS classes
            review_containers = soup.select(
                '.review-item, .review-card, .user-review, '
                '[data-testid*="review"], .review-container, '
                '.trustradius-review, .tr-review'
            )
            
            if not review_containers:
                # Try more generic selectors
                review_containers = soup.select('[class*="review"]')
                # Filter out likely false positives
                review_containers = [r for r in review_containers 
                                   if len(r.get_text().strip()) > 100 and 
                                   'review' in r.get('class', [])[0].lower()]
            
            reviews = []
            for container in review_containers:
                review_data = self._extract_review_data(container)
                if review_data:
                    reviews.append(review_data)
            
            # Check for next page
            has_next = self._has_next_page(soup)
            
            return {
                'reviews': reviews,
                'has_next': has_next,
                'total_pages': None
            }
            
        except Exception as e:
            raise ScrapingError(f"Failed to get TrustRadius reviews page {page}: {e}")
    
    def _extract_review_data(self, container) -> Optional[Dict[str, Any]]:
        """
        Extract review data from a review container element.
        
        Args:
            container: BeautifulSoup element containing review
            
        Returns:
            Dictionary with raw review data or None
        """
        try:
            # Extract title
            title = (safe_extract(container, 'h3, h4, .review-title, .title') or
                    safe_extract(container, '.summary, .headline, .subject') or
                    safe_extract(container, '[data-testid*="title"]'))
            
            # Extract review text - TrustRadius often has detailed reviews
            review_text = (safe_extract(container, '.review-text, .review-content, .content') or
                          safe_extract(container, '.description, .review-body, .comment') or
                          safe_extract(container, '[data-testid*="review-text"], p'))
            
            # If review text is still short, try to get more comprehensive text
            if len(review_text) < 50:
                # Look for pros/cons sections which are common on TrustRadius
                pros = safe_extract(container, '.pros, .advantages, [data-testid*="pros"]')
                cons = safe_extract(container, '.cons, .disadvantages, [data-testid*="cons"]')
                
                if pros or cons:
                    review_text = f"Pros: {pros}\n\nCons: {cons}".strip()
                else:
                    # Fall back to general container text
                    all_text = clean_text(container.get_text())
                    if len(all_text) > len(review_text) * 2:
                        review_text = all_text[:1500]  # Limit to reasonable length
            
            # Extract rating - TrustRadius typically uses 1-10 scale
            rating_element = container.select_one('.rating, .score, [data-rating]')
            rating_text = "0"
            
            if rating_element:
                # Try different ways to extract rating
                rating_text = (rating_element.get('data-rating') or
                             rating_element.get('title') or
                             rating_element.get_text())
            
            # Look for star ratings
            if not rating_text or rating_text == "0":
                filled_stars = container.select('.star.filled, .fa-star:not(.fa-star-o)')
                if filled_stars:
                    rating_text = str(len(filled_stars))
                else:
                    # Try to find rating in text (TrustRadius often shows "X out of 10")
                    text_content = container.get_text()
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/)\s*(\d+)', text_content, re.IGNORECASE)
                    if rating_match:
                        score = float(rating_match.group(1))
                        scale = float(rating_match.group(2))
                        # Normalize to 5-point scale
                        if scale == 10:
                            rating_text = str(score / 2)
                        else:
                            rating_text = str(score)
            
            # Extract reviewer name
            reviewer_name = (safe_extract(container, '.reviewer, .author, .user-name') or
                           safe_extract(container, '[data-testid*="reviewer"], .reviewer-name') or
                           safe_extract(container, '.name, .user, .by'))
            
            # Clean reviewer name
            if reviewer_name.lower().startswith('by '):
                reviewer_name = reviewer_name[3:]
            if reviewer_name.lower().startswith('reviewed by '):
                reviewer_name = reviewer_name[12:]
            
            # Extract date
            date_element = container.select_one('time, .date, [data-date], .published')
            if date_element:
                date_text = (date_element.get('datetime') or
                           date_element.get('data-date') or
                           date_element.get('title') or
                           date_element.get_text())
            else:
                # Look for date patterns in text
                text_content = container.get_text()
                date_patterns = [
                    r'(\w+ \d{1,2}, \d{4})',  # "January 15, 2024"
                    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # "1/15/24" or "1-15-2024"
                    r'(\d{4}-\d{1,2}-\d{1,2})',  # "2024-01-15"
                ]
                
                date_text = ""
                for pattern in date_patterns:
                    match = re.search(pattern, text_content)
                    if match:
                        date_text = match.group(1)
                        break
            
            # Only return if we have substantial content
            if len(review_text) < 20 and not title:
                return None
            
            return {
                'title': title or "No title",
                'review_text': review_text,
                'rating_text': rating_text,
                'reviewer_name': reviewer_name or "Anonymous",
                'date_text': date_text,
                'raw_html': str(container)[:500]  # Keep snippet for debugging
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to extract review data: {e}")
            return None
    
    def _has_next_page(self, soup) -> bool:
        """
        Check if there's a next page of reviews.
        
        Args:
            soup: BeautifulSoup object of current page
            
        Returns:
            True if next page exists
        """
        # Look for next page indicators
        next_links = soup.select(
            'a[aria-label*="next"], .next, .pagination-next, '
            '[data-testid*="next"], a:contains("Next")'
        )
        
        for link in next_links:
            href = link.get('href')
            if href and not link.get('disabled'):
                return True
        
        # Check if there's a "Load more" or "Show more" button
        load_more = soup.select(
            '.load-more, .show-more, [data-testid*="load"], '
            'button:contains("Load"), button:contains("Show")'
        )
        if load_more:
            return True
        
        # Check pagination numbers
        page_links = soup.select('.pagination a, .page-numbers a, .pager a')
        current_page = soup.select_one('.pagination .current, .pagination .active')
        
        if current_page and page_links:
            try:
                current_num = int(re.search(r'\d+', current_page.get_text()).group())
                page_numbers = []
                for link in page_links:
                    match = re.search(r'\d+', link.get_text())
                    if match:
                        page_numbers.append(int(match.group()))
                
                if page_numbers:
                    return current_num < max(page_numbers)
                    
            except (ValueError, AttributeError):
                pass
        
        return False
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """
        Parse raw TrustRadius review data into standardized Review model.
        
        Args:
            raw_review: Raw review data from get_reviews_page
            
        Returns:
            Parsed Review object
        """
        try:
            # Clean and parse the data
            title = clean_text(raw_review.get('title', ''))
            review_text = clean_text(raw_review.get('review_text', ''))
            reviewer_name = clean_text(raw_review.get('reviewer_name', 'Anonymous'))
            
            # Parse rating - TrustRadius may use different scales
            rating_text = raw_review.get('rating_text', '0')
            rating = parse_rating(rating_text)
            
            # If rating seems to be on 10-point scale, convert to 5-point
            if rating > 5:
                rating = rating / 2
            
            # Parse date
            date = parse_flexible_date(raw_review.get('date_text', ''))
            if not date:
                # Fallback to current date if parsing fails
                from datetime import datetime
                date = datetime.now()
                self.logger.warning("Could not parse review date, using current date")
            
            return Review(
                title=title or "No title",
                review=review_text or "No content",
                date=date,
                reviewer_name=reviewer_name,
                rating=rating,
                source=self.source_name,
                additional_fields={
                    'raw_rating_text': raw_review.get('rating_text'),
                    'raw_date_text': raw_review.get('date_text'),
                    'original_rating_scale': '10-point' if parse_rating(rating_text) > 5 else '5-point'
                }
            )
            
        except Exception as e:
            raise ScrapingError(f"Failed to parse TrustRadius review: {e}")