"""
Abstract base class for review scrapers to ensure consistent interface
and enable easy extension to new sources.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import time

from models.review import Review, ScrapingConfig


class ReviewScraper(ABC):
    """
    Abstract base class that defines the interface for all review scrapers.
    
    This class provides common functionality and defines the contract that
    all scraper implementations must follow.
    """
    
    def __init__(self, source_name: str):
        """
        Initialize the scraper with source name.
        
        Args:
            source_name: Name of the review source (e.g., 'g2', 'capterra')
        """
        self.source_name = source_name
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
        self.session = self._create_session()
        
    def _create_session(self):
        """Create and configure requests session with common settings."""
        import requests
        import random
        
        session = requests.Session()
        
        # Rotate between multiple realistic user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        # Additional headers to look more like a real browser
        session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        # Set reasonable timeouts
        session.timeout = 30
        
        # Establish session with homepage first to get cookies
        self._establish_session(session)
        
        return session
    
    def _establish_session(self, session):
        """Establish a session by visiting the homepage first to get cookies."""
        try:
            # Visit homepage first to establish a session
            homepage_url = getattr(self, 'base_url', 'https://www.g2.com')
            self.logger.debug(f"Establishing session with {homepage_url}")
            
            response = session.get(homepage_url, timeout=30)
            if response.status_code == 200:
                self.logger.debug("Session established successfully")
            else:
                self.logger.warning(f"Homepage returned status {response.status_code}")
        except Exception as e:
            self.logger.warning(f"Failed to establish session: {e}")
            if "403" in str(e) or "Forbidden" in str(e):
                self._handle_blocking_error()
    
    def _add_request_delay(self, min_delay: float = 0.5, max_delay: float = 2.0):
        """Add random delay between requests to avoid rate limiting."""
        import random
        delay = random.uniform(min_delay, max_delay)
        self.logger.debug(f"Adding request delay: {delay:.2f}s")
        time.sleep(delay)
    
    def _handle_blocking_error(self):
        """Handle anti-bot blocking with helpful user guidance."""
        source_name = getattr(self, 'source_name', 'this site')
        base_url = getattr(self, 'base_url', 'the website')
        
        self.logger.error(f"❌ {source_name.upper()} is blocking automated requests (403 Forbidden)")
        self.logger.info("\n🤖 Anti-bot measures detected. Here are your options:")
        self.logger.info("\n1. 🌐 Manual Approach:")
        self.logger.info(f"   • Visit {base_url} in your browser")
        self.logger.info(f"   • Search for your company manually")
        self.logger.info(f"   • Copy the product URL and use --direct-url parameter")
        self.logger.info("\n2. ⏰ Wait and Retry:")
        self.logger.info("   • Wait 10-15 minutes and try again")
        self.logger.info("   • Anti-bot measures may be temporary")
        self.logger.info("\n3. 🔄 Try Other Sources:")
        self.logger.info("   • Use --source capterra or --source trustradius")
        self.logger.info("   • Different sites may have different policies")
        self.logger.info("\n4. 🛠️ Advanced Options:")
        self.logger.info("   • Consider using a VPN with a different IP")
        self.logger.info("   • Try running from a different network")
    
    @abstractmethod
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for a company/product and return its unique identifier or URL.
        
        Args:
            company_name: Name of the company to search for
            
        Returns:
            Company identifier (URL, ID, etc.) if found, None otherwise
            
        Raises:
            ScrapingError: If search fails or company not found
        """
        pass
    
    @abstractmethod
    def get_reviews_page(self, company_id: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews for a specific page.
        
        Args:
            company_id: Company identifier from search_company
            page: Page number to retrieve
            
        Returns:
            Dictionary containing:
            - 'reviews': List of raw review data
            - 'has_next': Boolean indicating if more pages exist
            - 'total_pages': Total number of pages (if available)
            
        Raises:
            ScrapingError: If page retrieval fails
        """
        pass
    
    @abstractmethod
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """
        Parse raw review data into standardized Review model.
        
        Args:
            raw_review: Raw review data from get_reviews_page
            
        Returns:
            Parsed Review object
            
        Raises:
            ScrapingError: If review parsing fails
        """
        pass
    
    def scrape_reviews(self, config: ScrapingConfig) -> List[Review]:
        """
        Main scraping method that orchestrates the entire process.
        
        Args:
            config: ScrapingConfig object with scraping parameters
            
        Returns:
            List of Review objects within the specified date range
            
        Raises:
            ScrapingError: If scraping process fails
        """
        self.logger.info(f"Starting scrape for {config.company_name} on {self.source_name}")
        
        # Search for company
        company_id = self.search_company(config.company_name)
        if not company_id:
            raise ScrapingError(f"Company '{config.company_name}' not found on {self.source_name}")
        
        self.logger.info(f"Found company: {company_id}")
        
        all_reviews = []
        page = 1
        
        while True:
            # Check if we've reached max pages limit (skip this check for all-reviews mode unless explicitly set)
            if config.max_pages and page > config.max_pages:
                self.logger.info(f"Reached max pages limit: {config.max_pages}")
                break
            
            # Add progress logging for long scraping sessions
            if page % 10 == 0 and page > 1:
                self.logger.info(f"🔄 Progress: Scraped {page-1} pages, found {len(all_reviews)} reviews so far...")
            
            self.logger.info(f"Scraping page {page}")
            
            try:
                page_data = self.get_reviews_page(company_id, page)
                raw_reviews = page_data.get('reviews', [])
                
                if not raw_reviews:
                    self.logger.info("No more reviews found")
                    break
                
                # Parse reviews and filter by date
                page_reviews = []
                for raw_review in raw_reviews:
                    try:
                        review = self.parse_review(raw_review)
                        
                        # Filter by date range
                        if config.start_date <= review.date <= config.end_date:
                            page_reviews.append(review)
                        elif review.date < config.start_date and config.start_date.year > 2001:
                            # Only stop for date ranges if not in "all reviews" mode
                            # (all reviews mode uses 2000-01-01 as start date)
                            self.logger.info("Reached reviews older than start_date, stopping")
                            return all_reviews + page_reviews
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to parse review: {e}")
                        continue
                
                all_reviews.extend(page_reviews)
                self.logger.info(f"Found {len(page_reviews)} reviews in date range on page {page}")
                
                # Check if there are more pages
                if not page_data.get('has_next', False):
                    self.logger.info("No more pages available")
                    break
                
                page += 1
                
                # Add variable delay to be respectful and avoid detection
                import random
                delay = random.uniform(2.0, 4.0)  # Random delay between 2-4 seconds
                self.logger.debug(f"Waiting {delay:.2f} seconds before next page")
                time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"Error scraping page {page}: {e}")
                break
        
        self.logger.info(f"Scraping completed. Found {len(all_reviews)} reviews total")
        return all_reviews
    
    def scrape_reviews_from_url(self, config: ScrapingConfig, direct_url: str) -> List[Review]:
        """
        Scrape reviews directly from a provided URL, bypassing company search.
        
        Args:
            config: ScrapingConfig object with scraping parameters
            direct_url: Direct URL to the product page
            
        Returns:
            List of Review objects within the specified date range
            
        Raises:
            ScrapingError: If scraping process fails
        """
        self.logger.info(f"Starting direct URL scrape for {config.company_name} on {self.source_name}")
        self.logger.info(f"Using direct URL: {direct_url}")
        
        all_reviews = []
        page = 1
        
        while True:
            # Check if we've reached max pages limit
            if config.max_pages and page > config.max_pages:
                self.logger.info(f"Reached max pages limit: {config.max_pages}")
                break
            
            self.logger.info(f"Scraping page {page}")
            
            # Add progress logging for long scraping sessions
            if page % 10 == 0 and page > 1:
                self.logger.info(f"🔄 Progress: Scraped {page-1} pages, found {len(all_reviews)} reviews so far...")
            
            try:
                page_data = self.get_reviews_page(direct_url, page)
                raw_reviews = page_data.get('reviews', [])
                
                if not raw_reviews:
                    self.logger.info("No more reviews found")
                    break
                
                # Parse reviews and filter by date
                page_reviews = []
                for raw_review in raw_reviews:
                    try:
                        review = self.parse_review(raw_review)
                        
                        # Filter by date range
                        if config.start_date <= review.date <= config.end_date:
                            page_reviews.append(review)
                        elif review.date < config.start_date and config.start_date.year > 2001:
                            # Only stop for date ranges if not in "all reviews" mode
                            # (all reviews mode uses 2000-01-01 as start date)
                            self.logger.info("Reached reviews older than start_date, stopping")
                            return all_reviews + page_reviews
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to parse review: {e}")
                        continue
                
                all_reviews.extend(page_reviews)
                self.logger.info(f"Found {len(page_reviews)} reviews in date range on page {page}")
                
                # Check if there are more pages
                if not page_data.get('has_next', False):
                    self.logger.info("No more pages available")
                    break
                
                page += 1
                
                # Add variable delay to be respectful and avoid detection
                import random
                delay = random.uniform(2.0, 4.0)  # Random delay between 2-4 seconds
                self.logger.debug(f"Waiting {delay:.2f} seconds before next page")
                time.sleep(delay)
                
            except Exception as e:
                self.logger.error(f"Error scraping page {page}: {e}")
                break
        
        self.logger.info(f"Direct URL scraping completed. Found {len(all_reviews)} reviews total")
        return all_reviews
    
    def validate_date_in_range(self, review_date: datetime, start_date: datetime, end_date: datetime) -> bool:
        """
        Check if a review date falls within the specified range.
        
        Args:
            review_date: Date of the review
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            True if date is in range, False otherwise
        """
        return start_date <= review_date <= end_date


class ScrapingError(Exception):
    """Custom exception for scraping-related errors."""
    pass