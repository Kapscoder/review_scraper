"""
G2.com scraper using Selenium Wire to intercept network requests and bypass restrictions.
This scraper monitors all network traffic to find G2's actual API endpoints.
"""
import time
import json
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import warnings
warnings.filterwarnings("ignore")

# Selenium Wire imports
from seleniumwire import webdriver
from seleniumwire.utils import decode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

# Base imports
from scrapers.base_scraper import ReviewScraper, ScrapingError
from models.review import Review
from utils.helpers import clean_text, parse_rating, parse_flexible_date


class G2WireScraper(ReviewScraper):
    """
    Advanced G2 scraper using Selenium Wire to intercept network requests.
    This bypasses G2's restrictions by:
    1. Using real browser with network interception
    2. Finding actual API endpoints used by G2
    3. Extracting review data from intercepted responses
    4. Using stealth techniques to avoid detection
    """
    
    def __init__(self):
        super().__init__("g2_wire")
        self.base_url = "https://www.g2.com"
        self.driver = None
        self.intercepted_data = {}
        self.api_endpoints = []
        
    def _setup_wire_driver(self):
        """Set up Selenium Wire driver with stealth options."""
        if self.driver is not None:
            return True
            
        try:
            self.logger.info("🕸️ Setting up Selenium Wire driver...")
            
            # Selenium Wire options for network interception
            seleniumwire_options = {
                'addr': '127.0.0.1',  # Address to bind the proxy to
                'port': 0,  # Use any available port
                'auto_config': False,  # Don't auto configure the browser
                'suppress_connection_errors': True,  # Suppress connection errors
            }
            
            # Chrome options for stealth
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Speed up loading
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Advanced user agent
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Create Selenium Wire driver
            self.driver = webdriver.Chrome(
                options=chrome_options,
                seleniumwire_options=seleniumwire_options
            )
            
            # Advanced evasion scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            self.driver.execute_script("window.chrome = { runtime: {} }")
            
            # Set up request interceptor
            self._setup_request_interceptor()
            
            self.logger.info("✅ Selenium Wire driver ready with network interception")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup Selenium Wire driver: {e}")
            return False
    
    def _setup_request_interceptor(self):
        """Set up request/response interceptor to capture API calls."""
        
        def request_interceptor(request):
            """Intercept outgoing requests."""
            # Log interesting requests
            if 'g2.com' in request.url and any(keyword in request.url.lower() for keyword in ['api', 'reviews', 'xhr', 'json']):
                self.logger.info(f"🔍 Intercepted REQUEST: {request.method} {request.url}")
                
                # Store potentially useful endpoints
                if request.url not in self.api_endpoints:
                    self.api_endpoints.append(request.url)
        
        def response_interceptor(request, response):
            """Intercept incoming responses."""
            # Only process responses from G2
            if 'g2.com' not in request.url:
                return
                
            # Look for review-related responses
            content_type = response.headers.get('content-type', '').lower()
            
            if any(keyword in request.url.lower() for keyword in ['review', 'api', 'xhr', 'json']):
                try:
                    # Decode response body
                    body = decode(response.body, response.headers.get('content-encoding', 'identity'))
                    
                    if body:
                        self.logger.info(f"📨 Intercepted RESPONSE: {request.method} {request.url} [{response.status_code}]")
                        
                        # Try to parse as JSON
                        try:
                            if 'json' in content_type:
                                data = json.loads(body)
                                if self._is_review_data(data):
                                    self.logger.info("🎯 FOUND REVIEW DATA in intercepted response!")
                                    self.intercepted_data[request.url] = {
                                        'url': request.url,
                                        'method': request.method,
                                        'status': response.status_code,
                                        'data': data,
                                        'headers': dict(response.headers)
                                    }
                        except json.JSONDecodeError:
                            # Check if response contains review-like content
                            body_str = body.decode('utf-8', errors='ignore')
                            if any(keyword in body_str.lower() for keyword in ['review', 'rating', 'comment', 'feedback']):
                                self.intercepted_data[request.url] = {
                                    'url': request.url,
                                    'method': request.method,
                                    'status': response.status_code,
                                    'content': body_str[:2000],  # Store first 2000 chars
                                    'headers': dict(response.headers)
                                }
                                
                except Exception as e:
                    self.logger.debug(f"Error processing response: {e}")
        
        # Set interceptors
        self.driver.request_interceptor = request_interceptor
        self.driver.response_interceptor = response_interceptor
    
    def _is_review_data(self, data: Any) -> bool:
        """Check if data contains review information."""
        if isinstance(data, dict):
            # Check for common review data patterns
            keys = str(data.keys()).lower()
            values = str(data.values()).lower()
            return any(keyword in keys or keyword in values 
                      for keyword in ['review', 'rating', 'comment', 'feedback', 'author', 'title'])
        elif isinstance(data, list) and data:
            # Check first item in list
            first_item = str(data[0]).lower()
            return any(keyword in first_item for keyword in ['review', 'rating', 'comment', 'feedback'])
        return False
    
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for company using Selenium Wire to monitor network traffic.
        """
        if not self._setup_wire_driver():
            return None
            
        self.logger.info(f"🎯 Starting wire-intercepted search for: {company_name}")
        
        try:
            # Clear previous data
            self.intercepted_data.clear()
            self.api_endpoints.clear()
            
            # For Zoom, try known URL first
            if company_name.lower() == "zoom":
                test_url = f"{self.base_url}/products/zoom-workplace"
                self.logger.info(f"🔗 Testing known Zoom URL: {test_url}")
                
                self.driver.get(test_url)
                time.sleep(8)  # Wait for page and network requests
                
                # Check if we got to a valid page
                title = self.driver.title.lower()
                if "zoom" in title and "blocked" not in title:
                    self.logger.info(f"✅ Successfully accessed: {test_url}")
                    self.logger.info(f"📄 Page title: {self.driver.title}")
                    
                    # Trigger more network requests by scrolling
                    self._trigger_network_activity()
                    
                    return test_url
            
            # If direct URL didn't work, try search
            return self._search_via_wire(company_name)
            
        except Exception as e:
            self.logger.error(f"Wire search failed: {e}")
            return None
    
    def _trigger_network_activity(self):
        """Trigger additional network requests to find API endpoints."""
        try:
            self.logger.info("🌊 Triggering network activity to discover APIs...")
            
            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Look for and click "Load more" or pagination buttons
            load_more_selectors = [
                "button:contains('Load more')",
                "button:contains('See more')",
                ".load-more",
                ".pagination a",
                "[data-testid*='load']",
                "[data-testid*='more']"
            ]
            
            for selector in load_more_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        self.logger.info(f"📌 Clicking element: {selector}")
                        elements[0].click()
                        time.sleep(3)
                        break
                except:
                    continue
            
            # Scroll more to trigger lazy loading of reviews
            for i in range(3):  # Multiple scrolls to load more reviews
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
            # Try to click any "Show more reviews" or similar buttons
            try:
                show_more_selectors = [
                    "button:contains('Show more')",
                    "button:contains('Load more')", 
                    "[data-testid*='show-more']",
                    ".show-more-reviews",
                    "button[class*='more']"
                ]
                for selector in show_more_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].is_displayed():
                        elements[0].click()
                        time.sleep(3)
                        break
            except:
                pass
            
        except Exception as e:
            self.logger.debug(f"Error triggering network activity: {e}")
    
    def _search_via_wire(self, company_name: str) -> Optional[str]:
        """Search using G2's search with network monitoring."""
        try:
            search_url = f"{self.base_url}/search?query={company_name.replace(' ', '+')}"
            self.logger.info(f"🔍 Searching via: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(5)
            
            # Look for product links
            product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/products/']")
            
            for link in product_links[:5]:
                try:
                    href = link.get_attribute('href')
                    text = link.text.lower()
                    
                    if company_name.lower() in text:
                        self.logger.info(f"✅ Found product link: {href}")
                        # Click the link to trigger more network requests
                        link.click()
                        time.sleep(5)
                        return href
                        
                except Exception:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Search via wire failed: {e}")
            
        return None
    
    def get_reviews_page(self, product_url: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews using wire interception to capture API responses.
        """
        if not self.driver:
            if not self._setup_wire_driver():
                return {'reviews': [], 'has_next': False, 'total_pages': None}
        
        self.logger.info(f"📄 Getting reviews page {page} with wire interception...")
        
        # Clear previous intercepted data
        self.intercepted_data.clear()
        
        try:
            # For G2, reviews are on the main product page, not /reviews page
            # So use the main product URL directly
            if product_url.endswith('/reviews'):
                # If already a reviews URL, use as-is
                reviews_url = product_url
                if page > 1:
                    reviews_url += f"?page={page}"
            else:
                # Use main product page where reviews are displayed
                reviews_url = product_url.rstrip('/')
                if page > 1:
                    reviews_url += f"?page={page}"
            
            self.logger.info(f"🔗 Loading: {reviews_url}")
            self.driver.get(reviews_url)
            time.sleep(8)  # Wait for network requests
            
            # Trigger more network activity
            self._trigger_network_activity()
            
            # Wait a bit more for all requests to complete
            time.sleep(5)
            
            # Check intercepted data first
            if self.intercepted_data:
                self.logger.info(f"📨 Found {len(self.intercepted_data)} intercepted responses")
                return self._process_intercepted_data()
            
            # Fallback to DOM extraction
            self.logger.info("📄 No intercepted data, falling back to DOM extraction...")
            return self._extract_from_dom()
            
        except Exception as e:
            self.logger.error(f"Error getting reviews page: {e}")
            return {'reviews': [], 'has_next': False, 'total_pages': None}
    
    def _process_intercepted_data(self) -> Dict[str, Any]:
        """Process intercepted network responses to extract reviews."""
        all_reviews = []
        
        for url, response_data in self.intercepted_data.items():
            try:
                self.logger.info(f"🔍 Processing intercepted response from: {url}")
                
                if 'data' in response_data:
                    # JSON data
                    reviews = self._extract_reviews_from_json(response_data['data'])
                    all_reviews.extend(reviews)
                    self.logger.info(f"📋 Extracted {len(reviews)} reviews from JSON response")
                    
                elif 'content' in response_data:
                    # HTML/text content
                    reviews = self._extract_reviews_from_content(response_data['content'])
                    all_reviews.extend(reviews)
                    self.logger.info(f"📋 Extracted {len(reviews)} reviews from content response")
                    
            except Exception as e:
                self.logger.debug(f"Error processing response: {e}")
                continue
        
        return {
            'reviews': all_reviews,
            'has_next': len(all_reviews) >= 10,  # Assume more if we got a full page
            'total_pages': None
        }
    
    def _extract_reviews_from_json(self, data: Any) -> List[Dict[str, Any]]:
        """Extract reviews from JSON API response."""
        reviews = []
        
        try:
            # Handle different JSON structures
            if isinstance(data, list):
                review_list = data
            elif isinstance(data, dict):
                # Try common API response patterns
                review_list = (data.get('reviews') or 
                             data.get('data') or 
                             data.get('results') or 
                             data.get('items') or
                             [data])
            else:
                return reviews
            
            for item in review_list:
                if isinstance(item, dict):
                    # Extract review fields from various possible key names
                    review_data = {
                        'title': (item.get('title') or 
                                item.get('headline') or 
                                item.get('summary') or 
                                'No title'),
                        'review_text': (item.get('review') or 
                                      item.get('comment') or 
                                      item.get('content') or 
                                      item.get('text') or 
                                      item.get('body') or ''),
                        'rating_text': str(item.get('rating') or 
                                         item.get('score') or 
                                         item.get('stars') or '0'),
                        'reviewer_name': (item.get('author') or 
                                        item.get('reviewer') or 
                                        item.get('user') or 
                                        item.get('username') or 
                                        'Anonymous'),
                        'date_text': (item.get('date') or 
                                    item.get('created_at') or 
                                    item.get('published_at') or 
                                    item.get('timestamp') or ''),
                    }
                    
                    if review_data['title'] or review_data['review_text']:
                        reviews.append(review_data)
                        
        except Exception as e:
            self.logger.debug(f"Error extracting from JSON: {e}")
            
        return reviews
    
    def _extract_reviews_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract reviews from HTML/text content."""
        reviews = []
        
        try:
            # Look for JSON embedded in content
            json_pattern = r'(\{[^{}]*"review"[^{}]*\})'
            json_matches = re.findall(json_pattern, content, re.IGNORECASE | re.DOTALL)
            
            for match in json_matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict):
                        reviews.extend(self._extract_reviews_from_json([data]))
                except:
                    continue
            
            # If no JSON found, try text patterns
            if not reviews:
                # Simple pattern matching for review-like content
                review_patterns = [
                    r'"title":\s*"([^"]+)"',
                    r'"review":\s*"([^"]+)"',
                    r'"rating":\s*(\d+(?:\.\d+)?)',
                    r'"author":\s*"([^"]+)"'
                ]
                
                titles = re.findall(review_patterns[0], content)
                review_texts = re.findall(review_patterns[1], content)
                ratings = re.findall(review_patterns[2], content)
                authors = re.findall(review_patterns[3], content)
                
                # Combine extracted data
                max_len = max(len(titles), len(review_texts), len(ratings), len(authors))
                for i in range(max_len):
                    review_data = {
                        'title': titles[i] if i < len(titles) else 'No title',
                        'review_text': review_texts[i] if i < len(review_texts) else '',
                        'rating_text': ratings[i] if i < len(ratings) else '0',
                        'reviewer_name': authors[i] if i < len(authors) else 'Anonymous',
                        'date_text': '',
                    }
                    reviews.append(review_data)
                    
        except Exception as e:
            self.logger.debug(f"Error extracting from content: {e}")
            
        return reviews
    
    def _extract_from_dom(self) -> Dict[str, Any]:
        """Fallback DOM extraction when no network data is intercepted."""
        try:
            # Wait for content to load
            time.sleep(3)
            
            # Scroll to ensure all content is loaded
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extract using comprehensive JavaScript
            extraction_script = """
            function extractReviewsFromDOM() {
                const reviews = [];
                
                // Multiple selector strategies
                const selectors = [
                    '[data-testid*="review"]',
                    '.review', '.review-item', '.review-card',
                    '.paper--white', '.paper--box',
                    '[itemprop="review"]',
                    'article', '.content-item'
                ];
                
                let elements = [];
                for (const selector of selectors) {
                    elements = elements.concat(Array.from(document.querySelectorAll(selector)));
                }
                
                // Remove duplicates
                elements = [...new Set(elements)];
                
                elements.forEach((el, index) => {
                    try {
                        const text = el.textContent || '';
                        
                        // Skip if too short or doesn't contain review indicators
                        if (text.length < 100 || !/(review|rating|star|recommend)/i.test(text)) return;
                        
                        // Extract title
                        const titleEl = el.querySelector('h1, h2, h3, h4, h5, h6, .title, .headline');
                        const title = titleEl ? titleEl.textContent.trim() : text.substring(0, 100);
                        
                        // Extract rating
                        const ratingMatch = text.match(/(\\d+(?:\\.\\d+)?)\\s*(?:out of|\\/)\\s*5|★{1,5}|(\\d+)\\s*star/i);
                        const rating = ratingMatch ? (ratingMatch[1] || ratingMatch[2] || '0') : '0';
                        
                        // Extract date
                        const dateMatch = text.match(/(\\d{1,2}[\\/-]\\d{1,2}[\\/-]\\d{2,4}|\\w+ \\d{1,2},? \\d{4})/);
                        const date = dateMatch ? dateMatch[1] : '';
                        
                        // Extract reviewer name
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
                
                return reviews;
            }
            
            return extractReviewsFromDOM();
            """
            
            reviews = self.driver.execute_script(extraction_script)
            self.logger.info(f"📋 DOM extraction found {len(reviews)} reviews")
            
            return {
                'reviews': reviews or [],
                'has_next': len(reviews) >= 10,
                'total_pages': None
            }
            
        except Exception as e:
            self.logger.warning(f"DOM extraction failed: {e}")
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
                    'element_index': raw_review.get('element_index'),
                    'intercepted_data': bool(raw_review.get('from_api', False))
                }
            )
            
        except Exception as e:
            raise ScrapingError(f"Failed to parse review: {e}")
    
    def get_intercepted_endpoints(self) -> List[str]:
        """Get list of intercepted API endpoints for debugging."""
        return self.api_endpoints.copy()
    
    def get_intercepted_data_summary(self) -> Dict[str, Any]:
        """Get summary of intercepted data for debugging."""
        return {
            'total_responses': len(self.intercepted_data),
            'endpoints': list(self.intercepted_data.keys()),
            'api_endpoints_found': len(self.api_endpoints)
        }
    
    def __del__(self):
        """Cleanup resources."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass