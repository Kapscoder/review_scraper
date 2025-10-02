"""
Advanced G2 bypass scraper with multiple evasion techniques.
This scraper uses every possible method to bypass G2's restrictions.
"""
import time
import json
import random
import threading
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
import warnings
warnings.filterwarnings("ignore")

# Advanced bypass imports
import undetected_chromedriver as uc
import cloudscraper
from fake_useragent import UserAgent
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Selenium imports
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

# Base imports
from scrapers.base_scraper import ReviewScraper, ScrapingError
from models.review import Review
from utils.helpers import clean_text, parse_rating, parse_flexible_date


class G2AdvancedBypassScraper(ReviewScraper):
    """
    Advanced G2 bypass scraper using multiple evasion techniques:
    - Undetected Chrome WebDriver
    - CloudScraper for Cloudflare bypass
    - Rotating User Agents
    - Session management
    - Proxy rotation (if available)
    - API endpoint discovery
    """
    
    def __init__(self):
        super().__init__("g2_advanced")
        self.base_url = "https://www.g2.com"
        
        # Advanced bypass components
        self.driver = None
        self.cloudscraper = None
        self.user_agent = UserAgent()
        self.session_pool = []
        self.current_session = None
        
        # Anti-detection settings
        self.request_delays = {"min": 3, "max": 8}
        self.user_agents = self._get_user_agent_pool()
        
        # Initialize bypass methods
        self._setup_cloudscraper()
        self._setup_session_pool()
    
    def _get_user_agent_pool(self) -> List[str]:
        """Generate a pool of realistic user agents."""
        agents = []
        try:
            for _ in range(10):
                agents.append(self.user_agent.chrome)
                agents.append(self.user_agent.firefox)
                agents.append(self.user_agent.safari)
        except:
            # Fallback user agents
            agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
            ]
        return list(set(agents))
    
    def _setup_cloudscraper(self):
        """Setup CloudScraper for Cloudflare bypass."""
        try:
            self.cloudscraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                },
                debug=False
            )
            self.logger.info("☁️ CloudScraper initialized for Cloudflare bypass")
        except Exception as e:
            self.logger.warning(f"CloudScraper setup failed: {e}")
            self.cloudscraper = None
    
    def _setup_session_pool(self):
        """Create a pool of configured sessions."""
        for i in range(5):
            session = requests.Session()
            
            # Advanced headers
            session.headers.update({
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Sec-CH-UA': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"'
            })
            
            # Advanced retry strategy
            retry_strategy = Retry(
                total=5,
                backoff_factor=2,
                status_forcelist=[429, 500, 502, 503, 504, 403, 404],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            self.session_pool.append(session)
        
        self.current_session = self.session_pool[0]
        self.logger.info(f"🔄 Session pool created with {len(self.session_pool)} sessions")
    
    def _setup_undetected_driver(self):
        """Setup undetected Chrome driver."""
        if self.driver is not None:
            return True
            
        try:
            self.logger.info("🚗 Setting up undetected Chrome driver...")
            
            # Undetected Chrome options
            options = uc.ChromeOptions()
            
            # Stealth options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")
            options.add_argument("--disable-javascript")
            
            # Advanced fingerprint evasion
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-features=TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            
            # Memory and performance
            options.add_argument("--memory-pressure-off")
            options.add_argument("--max_old_space_size=4096")
            
            # User agent
            options.add_argument(f"--user-agent={random.choice(self.user_agents)}")
            
            # Create undetected driver
            self.driver = uc.Chrome(
                options=options,
                version_main=None,
                use_subprocess=True,
                headless=False  # Set to True for headless mode
            )
            
            # Advanced evasion scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            self.driver.execute_script("window.chrome = { runtime: {} }")
            
            self.logger.info("✅ Undetected Chrome driver ready")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup undetected driver: {e}")
            return False
    
    def _rotate_session(self):
        """Rotate to a new session to avoid tracking."""
        old_session = self.current_session
        self.current_session = random.choice(self.session_pool)
        
        # Update headers with new user agent
        self.current_session.headers.update({
            'User-Agent': random.choice(self.user_agents)
        })
        
        self.logger.debug("🔄 Rotated to new session")
    
    def _smart_delay(self, multiplier: float = 1.0):
        """Intelligent delay that mimics human behavior."""
        delay = random.uniform(
            self.request_delays["min"] * multiplier,
            self.request_delays["max"] * multiplier
        )
        self.logger.debug(f"⏳ Smart delay: {delay:.2f}s")
        time.sleep(delay)
    
    def _try_cloudscraper_request(self, url: str) -> Optional[requests.Response]:
        """Try request with CloudScraper to bypass Cloudflare."""
        if not self.cloudscraper:
            return None
            
        try:
            self.logger.info("☁️ Trying CloudScraper bypass...")
            self._smart_delay(0.5)
            
            response = self.cloudscraper.get(url, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("✅ CloudScraper bypass successful!")
                return response
            else:
                self.logger.warning(f"CloudScraper returned {response.status_code}")
                
        except Exception as e:
            self.logger.warning(f"CloudScraper failed: {e}")
            
        return None
    
    def _try_session_request(self, url: str) -> Optional[requests.Response]:
        """Try request with rotating sessions."""
        for attempt in range(len(self.session_pool)):
            try:
                self._rotate_session()
                self._smart_delay(0.3)
                
                self.logger.info(f"🔄 Trying session request (attempt {attempt + 1})...")
                
                response = self.current_session.get(url, timeout=30)
                
                if response.status_code == 200:
                    self.logger.info("✅ Session request successful!")
                    return response
                elif response.status_code == 403:
                    self.logger.warning("Session blocked, rotating...")
                    continue
                else:
                    self.logger.warning(f"Session returned {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"Session request failed: {e}")
                continue
                
        return None
    
    def _try_undetected_browser(self, url: str) -> bool:
        """Try accessing URL with undetected browser."""
        if not self._setup_undetected_driver():
            return False
            
        try:
            self.logger.info("🚗 Trying undetected browser access...")
            self._smart_delay(1.0)
            
            self.driver.get(url)
            
            # Wait for page load
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Check if we're blocked
            page_title = self.driver.title.lower()
            page_source = self.driver.page_source.lower()
            
            if any(blocked_indicator in page_title or blocked_indicator in page_source 
                   for blocked_indicator in ["blocked", "forbidden", "access denied", "cloudflare", "just a moment"]):
                self.logger.warning("🚫 Browser detected blocking page")
                return False
            
            self.logger.info("✅ Undetected browser access successful!")
            return True
            
        except Exception as e:
            self.logger.warning(f"Undetected browser failed: {e}")
            return False
    
    def _discover_api_endpoints(self, product_name: str) -> List[str]:
        """Discover G2's internal API endpoints for review data."""
        api_patterns = [
            f"{self.base_url}/api/v1/products/{product_name}/reviews",
            f"{self.base_url}/api/v2/products/{product_name}/reviews", 
            f"{self.base_url}/xhr/products/{product_name}/reviews",
            f"{self.base_url}/graphql",
            f"{self.base_url}/api/reviews?product={product_name}",
            f"{self.base_url}/api/products/{product_name}/reviews.json",
            f"{self.base_url}/products/{product_name}/reviews/data",
            f"{self.base_url}/products/{product_name}/reviews.json"
        ]
        
        working_endpoints = []
        
        for api_url in api_patterns:
            try:
                self.logger.info(f"🔍 Testing API endpoint: {api_url}")
                
                # Try with CloudScraper first
                response = self._try_cloudscraper_request(api_url)
                if not response:
                    response = self._try_session_request(api_url)
                
                if response and response.status_code == 200:
                    try:
                        # Check if response contains JSON data
                        data = response.json()
                        if isinstance(data, (dict, list)) and data:
                            working_endpoints.append(api_url)
                            self.logger.info(f"✅ Working API endpoint found: {api_url}")
                    except:
                        # Check if response contains review-like content
                        if any(indicator in response.text.lower() 
                               for indicator in ["review", "rating", "comment", "feedback"]):
                            working_endpoints.append(api_url)
                            self.logger.info(f"✅ Working endpoint found: {api_url}")
                
                self._smart_delay(0.2)
                
            except Exception as e:
                self.logger.debug(f"API endpoint {api_url} failed: {e}")
                continue
        
        return working_endpoints
    
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for company using all available bypass methods.
        """
        self.logger.info(f"🎯 Starting advanced bypass search for: {company_name}")
        
        # Method 1: Try undetected browser with known URLs first (most reliable)
        if company_name.lower() == "zoom":
            known_urls = [
                f"{self.base_url}/products/zoom-workplace",
                f"{self.base_url}/products/zoom-meetings",
                f"{self.base_url}/products/zoom",
                f"{self.base_url}/products/zoom-video-communications"
            ]
            
            for url in known_urls:
                if self._try_undetected_browser(url):
                    self.logger.info(f"✅ Found working URL via undetected browser: {url}")
                    return url
        
        # Method 2: Try API endpoint discovery
        api_endpoints = self._discover_api_endpoints(company_name.lower().replace(" ", "-"))
        if api_endpoints:
            # Convert API endpoint back to product URL
            for endpoint in api_endpoints:
                if "/products/" in endpoint:
                    product_url = endpoint.split("/reviews")[0]
                    if self._test_product_url(product_url):
                        return product_url
        
        # Method 3: Try undetected browser search
        if self._try_undetected_browser(f"{self.base_url}"):
            return self._browser_search_company(company_name)
        
        # Method 4: Try CloudScraper search
        search_url = f"{self.base_url}/search?query={company_name.replace(' ', '+')}"
        response = self._try_cloudscraper_request(search_url)
        if response:
            return self._extract_product_url_from_search(response.text, company_name)
        
        self.logger.error(f"❌ All bypass methods failed for: {company_name}")
        return None
    
    def _test_product_url(self, url: str) -> bool:
        """Test if a product URL is accessible."""
        # Try CloudScraper
        response = self._try_cloudscraper_request(url)
        if response and response.status_code == 200:
            return True
            
        # Try session request
        response = self._try_session_request(url)
        if response and response.status_code == 200:
            return True
            
        # Try undetected browser
        return self._try_undetected_browser(url)
    
    def _browser_search_company(self, company_name: str) -> Optional[str]:
        """Search for company using the browser."""
        try:
            # Navigate to search
            search_url = f"{self.base_url}/search?query={company_name.replace(' ', '+')}"
            self.driver.get(search_url)
            
            self._smart_delay(2.0)
            
            # Look for product links
            product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
            
            for link in product_links[:5]:
                try:
                    href = link.get_attribute('href')
                    text = link.text.lower()
                    
                    if company_name.lower() in text and 'zoom' in text:
                        self.logger.info(f"✅ Found product via browser: {href}")
                        return href
                        
                except Exception as e:
                    continue
            
        except Exception as e:
            self.logger.warning(f"Browser search failed: {e}")
            
        return None
    
    def _extract_product_url_from_search(self, html: str, company_name: str) -> Optional[str]:
        """Extract product URL from search results HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            product_links = soup.find_all('a', href=lambda x: x and '/products/' in x)
            
            for link in product_links:
                href = link.get('href')
                text = link.get_text().lower()
                
                if company_name.lower() in text:
                    if href.startswith('/'):
                        href = self.base_url + href
                    return href
                    
        except Exception as e:
            self.logger.warning(f"Failed to extract product URL: {e}")
            
        return None
    
    def get_reviews_page(self, product_url: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews using all available methods.
        """
        reviews_url = product_url.rstrip('/') + '/reviews'
        if page > 1:
            reviews_url += f"?page={page}"
        
        self.logger.info(f"📄 Getting reviews page {page}: {reviews_url}")
        
        # Method 1: Try API endpoints first
        api_endpoints = self._discover_api_endpoints(product_url.split('/')[-1])
        for endpoint in api_endpoints:
            try:
                response = self._try_cloudscraper_request(endpoint)
                if not response:
                    response = self._try_session_request(endpoint)
                
                if response and response.status_code == 200:
                    data = response.json()
                    if self._is_review_data(data):
                        return self._parse_api_response(data)
            except:
                continue
        
        # Method 2: Try undetected browser
        if self._try_undetected_browser(reviews_url):
            return self._extract_reviews_from_browser()
        
        # Method 3: Try CloudScraper
        response = self._try_cloudscraper_request(reviews_url)
        if response:
            return self._extract_reviews_from_html(response.text)
        
        # Method 4: Try session request
        response = self._try_session_request(reviews_url)
        if response:
            return self._extract_reviews_from_html(response.text)
        
        return {'reviews': [], 'has_next': False, 'total_pages': None}
    
    def _is_review_data(self, data: Any) -> bool:
        """Check if data contains review information."""
        if isinstance(data, dict):
            return any(key in str(data).lower() for key in ['review', 'rating', 'comment'])
        elif isinstance(data, list):
            return len(data) > 0 and any(key in str(data[0]).lower() for key in ['review', 'rating', 'comment'])
        return False
    
    def _parse_api_response(self, data: Any) -> Dict[str, Any]:
        """Parse API response to extract reviews."""
        reviews = []
        
        if isinstance(data, list):
            review_list = data
        elif isinstance(data, dict):
            # Try common API response patterns
            review_list = data.get('reviews', data.get('data', data.get('results', [data])))
        else:
            review_list = []
        
        for item in review_list:
            if isinstance(item, dict):
                review_data = {
                    'title': item.get('title', item.get('headline', 'No title')),
                    'review_text': item.get('review', item.get('comment', item.get('content', ''))),
                    'rating_text': str(item.get('rating', item.get('score', '0'))),
                    'reviewer_name': item.get('author', item.get('reviewer', item.get('user', 'Anonymous'))),
                    'date_text': item.get('date', item.get('created_at', item.get('timestamp', ''))),
                }
                
                if review_data['title'] or review_data['review_text']:
                    reviews.append(review_data)
        
        return {
            'reviews': reviews,
            'has_next': len(reviews) >= 10,  # Assume more if we got a full page
            'total_pages': None
        }
    
    def _extract_reviews_from_browser(self) -> Dict[str, Any]:
        """Extract reviews from browser DOM."""
        # Wait for content to load
        self._smart_delay(3.0)
        
        # Scroll to trigger lazy loading
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        self._smart_delay(2.0)
        
        # Execute comprehensive extraction script
        extraction_script = """
        function extractAllReviews() {
            const reviews = [];
            
            // Comprehensive selector list
            const selectors = [
                '[data-testid*="review"]',
                '.review', '.review-item', '.review-card',
                '.paper--white', '.paper--box',
                '[itemprop="review"]',
                'article', '.content-item',
                '[class*="review"]', '[id*="review"]'
            ];
            
            let allElements = [];
            selectors.forEach(sel => {
                const els = Array.from(document.querySelectorAll(sel));
                allElements = allElements.concat(els);
            });
            
            // Remove duplicates
            allElements = [...new Set(allElements)];
            
            allElements.forEach((el, index) => {
                try {
                    const text = el.textContent || '';
                    
                    // Skip if too short or too long
                    if (text.length < 50 || text.length > 5000) return;
                    
                    // Look for review indicators
                    const hasReviewIndicators = /review|rating|star|recommend/i.test(text);
                    if (!hasReviewIndicators) return;
                    
                    // Extract data
                    const titleEl = el.querySelector('h1, h2, h3, h4, h5, h6, .title, .headline') || 
                                   el.querySelector('[class*="title"], [class*="headline"]');
                    const title = titleEl ? titleEl.textContent.trim() : text.substring(0, 100);
                    
                    const ratingMatch = text.match(/(\\d+(?:\\.\\d+)?)\\s*(?:out of|\\/)\\s*5|★{1,5}|(\\d+)\\s*star/i);
                    const rating = ratingMatch ? (ratingMatch[1] || ratingMatch[2] || '0') : '0';
                    
                    const dateMatch = text.match(/(\\d{1,2}[\\/-]\\d{1,2}[\\/-]\\d{2,4}|\\w+ \\d{1,2},? \\d{4})/);
                    const date = dateMatch ? dateMatch[1] : '';
                    
                    // Extract reviewer name (look for patterns like "By John" or "- John Smith")
                    const nameMatch = text.match(/(?:by |reviewer:?\\s*|author:?\\s*|\\-\\s*)([A-Z][a-z]+ [A-Z][a-z]+|[A-Z][a-z]+)/i);
                    const reviewer = nameMatch ? nameMatch[1] : 'Anonymous';
                    
                    reviews.push({
                        title: title.substring(0, 200),
                        review_text: text.substring(0, 1000),
                        rating_text: rating,
                        reviewer_name: reviewer.substring(0, 100),
                        date_text: date,
                        element_index: index
                    });
                    
                } catch (e) {
                    console.log('Error extracting review:', e);
                }
            });
            
            console.log(`Extracted ${reviews.length} reviews`);
            return reviews;
        }
        
        return extractAllReviews();
        """
        
        try:
            reviews = self.driver.execute_script(extraction_script)
            self.logger.info(f"📋 Extracted {len(reviews)} reviews from browser")
            
            return {
                'reviews': reviews or [],
                'has_next': len(reviews) >= 10,
                'total_pages': None
            }
        except Exception as e:
            self.logger.warning(f"Browser extraction failed: {e}")
            return {'reviews': [], 'has_next': False, 'total_pages': None}
    
    def _extract_reviews_from_html(self, html: str) -> Dict[str, Any]:
        """Extract reviews from raw HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            reviews = []
            
            # Try multiple selectors
            selectors = [
                '[data-testid*="review"]',
                '.review', '.review-item', '.review-card',
                '.paper--white', '.paper--box',
                '[itemprop="review"]',
                'article'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    break
            
            for element in elements[:20]:  # Limit to 20 reviews per page
                try:
                    text = element.get_text() or ''
                    
                    if len(text) < 50:
                        continue
                    
                    # Basic extraction
                    title_el = element.select_one('h1, h2, h3, h4, h5, h6')
                    title = title_el.get_text().strip() if title_el else text[:100]
                    
                    rating_el = element.select_one('[data-rating]')
                    rating = rating_el.get('data-rating', '0') if rating_el else '0'
                    
                    reviews.append({
                        'title': clean_text(title),
                        'review_text': clean_text(text),
                        'rating_text': rating,
                        'reviewer_name': 'Anonymous',
                        'date_text': '',
                    })
                    
                except Exception as e:
                    continue
            
            return {
                'reviews': reviews,
                'has_next': len(reviews) >= 10,
                'total_pages': None
            }
            
        except Exception as e:
            self.logger.warning(f"HTML extraction failed: {e}")
            return {'reviews': [], 'has_next': False, 'total_pages': None}
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """Parse review data into Review model."""
        try:
            title = clean_text(raw_review.get('title', ''))
            review_text = clean_text(raw_review.get('review_text', ''))
            reviewer_name = clean_text(raw_review.get('reviewer_name', 'Anonymous'))
            
            rating = parse_rating(raw_review.get('rating_text', '0'))
            
            date = parse_flexible_date(raw_review.get('date_text', ''))
            if not date:
                from datetime import datetime
                date = datetime.now()
            
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
                    'element_index': raw_review.get('element_index')
                }
            )
            
        except Exception as e:
            raise ScrapingError(f"Failed to parse review: {e}")
    
    def __del__(self):
        """Cleanup resources."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass