"""
G2.com review scraper implementation.
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


class G2Scraper(ReviewScraper):
    """
    Scraper for G2.com reviews.
    """
    
    def __init__(self):
        super().__init__("g2")
        self.base_url = "https://www.g2.com"
        
    @retry_with_backoff(max_retries=3)
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for a company on G2 and return the product URL.
        
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
        self.logger.error(f"Unable to automatically find '{company_name}' on G2 due to anti-bot measures.")
        self.logger.info("To work around this, you can:")
        self.logger.info("1. Visit https://www.g2.com manually in your browser")
        self.logger.info(f"2. Search for '{company_name}' and copy the product URL")
        self.logger.info("3. Use the direct URL approach (see documentation)")
        
        # Try some educated guesses for common product URLs
        if company_name.lower() == 'zoom':
            potential_urls = [
                "https://www.g2.com/products/zoom",
                "https://www.g2.com/products/zoom-meetings"
            ]
            self.logger.info(f"For Zoom, try these URLs manually: {potential_urls}")
        
        return None
    
    def _try_standard_search(self, company_name: str) -> Optional[str]:
        """Try the standard G2 search approach."""
        search_url = f"{self.base_url}/search"
        
        # Try multiple variations of the company name
        for variation in extract_company_name_variations(company_name):
            params = {
                'query': variation,
                'filters[content_type][]': 'product'
            }
            
            self.logger.info(f"Searching G2 for: {variation}")
            
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
                product_links = soup.select('a[href*="/products/"]')
                
                for link in product_links:
                    product_url = link.get('href')
                    if product_url and not product_url.startswith('http'):
                        product_url = self.base_url + product_url
                    
                    # Get product name from link text or nearby elements
                    product_name = clean_text(link.get_text())
                    
                    # Check if this looks like a match
                    if self._is_company_match(variation, product_name):
                        self.logger.info(f"Found G2 product via standard search: {product_url}")
                        return product_url
                        
            except Exception as e:
                self.logger.warning(f"Standard search failed for '{variation}': {e}")
                # Add longer delay after error
                self._add_request_delay(2.0, 4.0)
                continue
        
        return None
    
    def _try_fallback_search(self, company_name: str) -> Optional[str]:
        """Try alternative search methods when standard search fails."""
        # Try different search endpoints or methods
        alternatives = [
            f"{self.base_url}/categories/web-conferencing",  # For companies like Zoom
            f"{self.base_url}/categories/video-conferencing",
            f"{self.base_url}/categories/collaboration"
        ]
        
        for alt_url in alternatives:
            try:
                self.logger.info(f"Trying fallback search at: {alt_url}")
                self._add_request_delay(1.0, 2.0)
                
                response = self.session.get(alt_url, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for product links that might match our company
                product_links = soup.select('a[href*="/products/"]')
                
                for link in product_links:
                    product_name = clean_text(link.get_text())
                    if self._is_company_match(company_name.lower(), product_name):
                        product_url = link.get('href')
                        if product_url and not product_url.startswith('http'):
                            product_url = self.base_url + product_url
                        self.logger.info(f"Found G2 product via fallback search: {product_url}")
                        return product_url
                        
            except Exception as e:
                self.logger.warning(f"Fallback search failed for {alt_url}: {e}")
                continue
        
        return None
    
    def _try_direct_product_url(self, company_name: str) -> Optional[str]:
        """Try to guess direct product URLs for well-known companies."""
        # For well-known companies, try direct URL patterns
        company_lower = company_name.lower()
        
        # Common URL patterns for popular SaaS companies
        url_patterns = [
            f"{self.base_url}/products/{company_lower}",
            f"{self.base_url}/products/{company_lower}-{company_lower}",
            f"{self.base_url}/products/{company_lower}-video-conferencing",
            f"{self.base_url}/products/{company_lower}-meetings",
        ]
        
        # Add specific patterns for known companies
        if company_lower == 'zoom':
            url_patterns.extend([
                f"{self.base_url}/products/zoom",  # Most likely
                f"{self.base_url}/products/zoom-meetings",
                f"{self.base_url}/products/zoom-video-communications", 
                f"{self.base_url}/products/zoom-workplace",
                f"{self.base_url}/products/zoom-phone",
                f"{self.base_url}/products/zoom-webinar",
                f"{self.base_url}/products/zoom-video-conferencing"
            ])
        
        for url in url_patterns:
            try:
                self.logger.info(f"Trying direct URL: {url}")
                self._add_request_delay(1.0, 2.0)
                
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    # Check if this looks like a valid product page
                    soup = BeautifulSoup(response.content, 'html.parser')
                    if soup.select('.product-head, .product-title, [data-testid*="product"]'):
                        self.logger.info(f"Found G2 product via direct URL: {url}")
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
        search_lower = search_term.lower()
        product_lower = product_name.lower()
        
        # Simple substring matching
        return (search_lower in product_lower or 
                product_lower in search_lower or
                self._fuzzy_match(search_lower, product_lower))
    
    def _fuzzy_match(self, term1: str, term2: str) -> bool:
        """Simple fuzzy matching for company names."""
        # Remove common words and punctuation
        clean1 = re.sub(r'\b(the|inc|llc|corp|ltd|corporation)\b|[^\w\s]', '', term1, flags=re.IGNORECASE).strip()
        clean2 = re.sub(r'\b(the|inc|llc|corp|ltd|corporation)\b|[^\w\s]', '', term2, flags=re.IGNORECASE).strip()
        
        words1 = set(clean1.lower().split())
        words2 = set(clean2.lower().split())
        
        # Check for significant word overlap
        if len(words1) > 0 and len(words2) > 0:
            overlap = len(words1.intersection(words2))
            return overlap / max(len(words1), len(words2)) >= 0.5  # Changed from > to >=
        
        return False
    
    @retry_with_backoff(max_retries=3)
    def get_reviews_page(self, product_url: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews for a specific page from G2.
        
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
        
        params = {'page': page} if page > 1 else {}
        
        self.logger.debug(f"Fetching G2 reviews page {page}: {reviews_url}")
        
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
            
            # Find review containers - G2 uses various CSS classes
            review_containers = soup.select('[data-review-id], .paper.paper--white.paper--box, div[itemprop="review"]')
            
            if not review_containers:
                # Try alternative selectors
                review_containers = soup.select('.review-item, .review-card, [data-testid*="review"]')
            
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
                'total_pages': None  # G2 doesn't always show total pages
            }
            
        except Exception as e:
            raise ScrapingError(f"Failed to get G2 reviews page {page}: {e}")
    
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
            title = (safe_extract(container, 'h3, .review-title, [data-testid*="title"]') or
                    safe_extract(container, '[itemprop="name"]') or
                    "No title")
            
            # Extract review text
            review_text = (safe_extract(container, '.review-text, [data-testid*="review-text"], [itemprop="reviewBody"]') or
                          safe_extract(container, 'p, .description'))
            
            # Extract rating
            rating_element = container.select_one('[data-rating], .rating, [itemprop="ratingValue"]')
            if rating_element:
                rating_text = (rating_element.get('data-rating') or 
                             rating_element.get_text() or 
                             rating_element.get('content'))
            else:
                # Try to find stars or rating indicators
                stars = container.select('.star, .rating-star')
                rating_text = str(len([s for s in stars if 'filled' in s.get('class', [])]))
            
            # Extract reviewer name
            reviewer_name = (safe_extract(container, '.reviewer-name, [data-testid*="reviewer"], [itemprop="author"]') or
                           safe_extract(container, '.author, .user-name') or
                           "Anonymous")
            
            # Extract date
            date_element = container.select_one('[data-date], .review-date, time, [itemprop="datePublished"]')
            if date_element:
                date_text = (date_element.get('data-date') or
                           date_element.get('datetime') or
                           date_element.get('content') or
                           date_element.get_text())
            else:
                date_text = safe_extract(container, '.date, .published')
            
            return {
                'title': title,
                'review_text': review_text,
                'rating_text': rating_text,
                'reviewer_name': reviewer_name,
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
        next_links = soup.select('a[aria-label*="next"], .next, [data-testid*="next"]')
        
        for link in next_links:
            if not link.get('disabled') and link.get('href'):
                return True
        
        # Check pagination numbers
        page_links = soup.select('.pagination a, .page-numbers a')
        current_page = soup.select_one('.pagination .current, .page-numbers .current')
        
        if current_page and page_links:
            try:
                current_num = int(current_page.get_text().strip())
                max_num = max([int(re.search(r'\d+', link.get_text()).group()) 
                              for link in page_links 
                              if re.search(r'\d+', link.get_text())])
                return current_num < max_num
            except (ValueError, AttributeError):
                pass
        
        return False
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """
        Parse raw G2 review data into standardized Review model.
        
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
            raise ScrapingError(f"Failed to parse G2 review: {e}")