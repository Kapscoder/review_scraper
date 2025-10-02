"""
Capterra.com review scraper implementation.
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


class CapterraScraper(ReviewScraper):
    """
    Scraper for Capterra.com reviews.
    """
    
    def __init__(self):
        super().__init__("capterra")
        self.base_url = "https://www.capterra.com"
        
    @retry_with_backoff(max_retries=3)
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for a company on Capterra and return the product URL.
        
        Args:
            company_name: Name of the company to search for
            
        Returns:
            Product URL if found, None otherwise
        """
        # First try the standard search approach
        result = self._try_standard_search(company_name)
        if result:
            return result
        
        # If standard search fails, try fallback strategies
        result = self._try_fallback_search(company_name)
        if result:
            return result
        
        # Last resort: try direct product URL guessing for well-known companies
        result = self._try_direct_product_url(company_name)
        if result:
            return result
        
        # Final fallback: provide guidance for manual URL finding
        self.logger.error(f"Unable to automatically find '{company_name}' on Capterra due to anti-bot measures.")
        self.logger.info("To work around this, you can:")
        self.logger.info("1. Visit https://www.capterra.com manually in your browser")
        self.logger.info(f"2. Search for '{company_name}' and copy the product URL")
        self.logger.info("3. Use the direct URL approach (see documentation)")
        
        return None
    
    def _try_standard_search(self, company_name: str) -> Optional[str]:
        """Try the standard Capterra search approach."""
        search_url = f"{self.base_url}/search"
        
        # Try multiple variations of the company name
        for variation in extract_company_name_variations(company_name):
            params = {'query': variation}
            
            self.logger.info(f"Searching Capterra for: {variation}")
            
            try:
                # Add delay before request
                self._add_request_delay(0.5, 1.5)
                
                # Update session headers for this specific request
                self.session.headers.update({
                    'Referer': self.base_url,
                    'Sec-Fetch-Site': 'same-origin'
                })
                
                response = self.session.get(search_url, params=params, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for product links in search results
                # Capterra uses different URL patterns
                product_links = soup.select('a[href*="/software/"], a[href*="/directory/"]')
                
                for link in product_links:
                    product_url = link.get('href')
                    if product_url and not product_url.startswith('http'):
                        product_url = self.base_url + product_url
                    
                    # Get product name from link text or nearby elements
                    product_name = clean_text(link.get_text())
                    
                    # Also check parent/sibling elements for product name
                    if not product_name:
                        parent = link.parent
                        if parent:
                            product_name = clean_text(parent.get_text())
                    
                    # Check if this looks like a match
                    if self._is_company_match(variation, product_name):
                        self.logger.info(f"Found Capterra product via standard search: {product_url}")
                        return product_url
                        
            except Exception as e:
                self.logger.warning(f"Standard search failed for '{variation}': {e}")
                # Add longer delay after error
                self._add_request_delay(2.0, 4.0)
                continue
        
        return None
    
    def _try_fallback_search(self, company_name: str) -> Optional[str]:
        """Try alternative search methods when standard search fails."""
        # Try different category pages for video conferencing tools
        alternatives = [
            f"{self.base_url}/category/video-conferencing",
            f"{self.base_url}/category/web-conferencing", 
            f"{self.base_url}/category/collaboration-software",
            f"{self.base_url}/category/meeting-software"
        ]
        
        for alt_url in alternatives:
            try:
                self.logger.info(f"Trying fallback search at: {alt_url}")
                self._add_request_delay(1.0, 2.0)
                
                response = self.session.get(alt_url, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for product links that might match our company
                product_links = soup.select('a[href*="/software/"]')
                
                for link in product_links:
                    product_name = clean_text(link.get_text())
                    if self._is_company_match(company_name.lower(), product_name):
                        product_url = link.get('href')
                        if product_url and not product_url.startswith('http'):
                            product_url = self.base_url + product_url
                        self.logger.info(f"Found Capterra product via fallback search: {product_url}")
                        return product_url
                        
            except Exception as e:
                self.logger.warning(f"Fallback search failed for {alt_url}: {e}")
                continue
        
        return None
    
    def _try_direct_product_url(self, company_name: str) -> Optional[str]:
        """Try to guess direct product URLs for well-known companies."""
        # For well-known companies, try direct URL patterns
        company_lower = company_name.lower()
        
        # Common URL patterns for popular SaaS companies on Capterra
        url_patterns = [
            f"{self.base_url}/software/{company_lower}",
            f"{self.base_url}/software/{company_lower}-software",
            f"{self.base_url}/p/{company_lower}",
        ]
        
        # Add specific patterns for known companies
        if company_lower == 'zoom':
            url_patterns.extend([
                f"{self.base_url}/software/zoom-video-conferencing",
                f"{self.base_url}/software/zoom-meetings",
                f"{self.base_url}/p/zoom-video-communications",
                f"{self.base_url}/software/zoom-workplace"
            ])
        
        for url in url_patterns:
            try:
                self.logger.info(f"Trying direct Capterra URL: {url}")
                self._add_request_delay(1.0, 2.0)
                
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    # Check if this looks like a valid product page
                    soup = BeautifulSoup(response.content, 'html.parser')
                    if soup.select('.product-header, .software-header, h1, .title'):
                        self.logger.info(f"Found Capterra product via direct URL: {url}")
                        return url
                        
            except Exception as e:
                self.logger.debug(f"Direct URL failed for {url}: {e}")
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
        if not product_name:
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
        clean1 = re.sub(r'\b(the|inc|llc|corp|ltd|software)\b|[^\w\s]', '', term1).strip()
        clean2 = re.sub(r'\b(the|inc|llc|corp|ltd|software)\b|[^\w\s]', '', term2).strip()
        
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
        Get reviews for a specific page from Capterra.
        
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
        
        # Capterra uses different pagination patterns
        params = {}
        if page > 1:
            params['page'] = page
        
        self.logger.debug(f"Fetching Capterra reviews page {page}: {reviews_url}")
        
        try:
            # Add delay before request
            self._add_request_delay(1.0, 2.5)
            
            # Update headers for reviews page request
            self.session.headers.update({
                'Referer': product_url.replace('/reviews', '') if '/reviews' in product_url else product_url,
                'Sec-Fetch-Site': 'same-origin'
            })
            
            response = self.session.get(reviews_url, params=params, timeout=20)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find review containers - Capterra uses various CSS classes
            review_containers = soup.select(
                '.review-card, .review-item, [data-testid*="review"], '
                '.user-review, .review-block, .review-container'
            )
            
            if not review_containers:
                # Try more generic selectors
                review_containers = soup.select('[class*="review"], [id*="review"]')
                # Filter out likely false positives
                review_containers = [r for r in review_containers 
                                   if len(r.get_text().strip()) > 100]
            
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
            raise ScrapingError(f"Failed to get Capterra reviews page {page}: {e}")
    
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
                    safe_extract(container, '[data-testid*="title"], .headline') or
                    safe_extract(container, '.summary, .subject'))
            
            # Extract review text - look for main content
            review_text = (safe_extract(container, '.review-text, .content, .description') or
                          safe_extract(container, '[data-testid*="review-text"], .review-body') or
                          safe_extract(container, '.comment, .feedback, p'))
            
            # If review text is very short, try to get more content
            if len(review_text) < 50:
                all_text = clean_text(container.get_text())
                if len(all_text) > len(review_text) * 2:
                    review_text = all_text[:1000]  # Limit to reasonable length
            
            # Extract rating - Capterra often uses star systems
            rating_element = container.select_one('.rating, .stars, [data-rating]')
            rating_text = "0"
            
            if rating_element:
                # Try different ways to extract rating
                rating_text = (rating_element.get('data-rating') or
                             rating_element.get('title') or
                             rating_element.get_text())
            
            # Count filled stars if numeric rating not found
            if not rating_text or rating_text == "0":
                filled_stars = container.select('.star.filled, .fa-star:not(.fa-star-o), .icon-star-full')
                if filled_stars:
                    rating_text = str(len(filled_stars))
                else:
                    # Try to find rating in text
                    text_content = container.get_text()
                    rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:out of|/|\s+)?\s*5?\s*stars?', text_content, re.IGNORECASE)
                    if rating_match:
                        rating_text = rating_match.group(1)
            
            # Extract reviewer name
            reviewer_name = (safe_extract(container, '.reviewer, .author, .user-name') or
                           safe_extract(container, '[data-testid*="reviewer"], .reviewer-name') or
                           safe_extract(container, '.name, .by'))
            
            # Clean reviewer name (remove "by" prefix)
            if reviewer_name.lower().startswith('by '):
                reviewer_name = reviewer_name[3:]
            
            # Extract date
            date_element = container.select_one('time, .date, [data-date]')
            if date_element:
                date_text = (date_element.get('datetime') or
                           date_element.get('data-date') or
                           date_element.get_text())
            else:
                # Look for date patterns in text
                text_content = container.get_text()
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})', text_content)
                date_text = date_match.group(1) if date_match else ""
            
            # Only return if we have substantial content
            if len(review_text) < 10 and not title:
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
            if not link.get('disabled') and link.get('href'):
                return True
        
        # Check if there's a "Load more" button
        load_more = soup.select('.load-more, [data-testid*="load"], button:contains("Load")')
        if load_more:
            return True
        
        # Check pagination numbers
        page_links = soup.select('.pagination a, .page-numbers a, .pager a')
        if len(page_links) > 1:  # More than just current page
            return True
        
        return False
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """
        Parse raw Capterra review data into standardized Review model.
        
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
            
            # Parse rating
            rating = parse_rating(raw_review.get('rating_text', '0'))
            
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
                    'raw_date_text': raw_review.get('date_text')
                }
            )
            
        except Exception as e:
            raise ScrapingError(f"Failed to parse Capterra review: {e}")