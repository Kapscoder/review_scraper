"""
G2.com browser-based review scraper using Selenium WebDriver.
This scraper uses real browser automation to bypass anti-bot measures.
"""
import time
import json
import re
from typing import Optional, Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from scrapers.base_scraper import ReviewScraper, ScrapingError
from models.review import Review
from utils.helpers import clean_text, parse_rating, parse_flexible_date


class G2BrowserScraper(ReviewScraper):
    """
    Browser-based scraper for G2.com reviews using Selenium WebDriver.
    """
    
    def __init__(self):
        super().__init__("g2_browser")
        self.base_url = "https://www.g2.com"
        self.driver = None
        self.wait = None
        
    def _setup_driver(self):
        """Set up Chrome WebDriver with stealth options."""
        if self.driver is not None:
            return
            
        self.logger.info("🌐 Setting up Chrome WebDriver...")
        
        # Chrome options for stealth browsing
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Uncomment to run in headless mode (no browser window)
        # chrome_options.add_argument("--headless")
        
        try:
            # Use webdriver-manager to automatically handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            self.logger.info("✅ Chrome WebDriver setup complete")
            
        except Exception as e:
            raise ScrapingError(f"Failed to setup Chrome WebDriver: {e}")
    
    def _cleanup_driver(self):
        """Clean up the WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.wait = None
                self.logger.info("🧹 WebDriver cleanup complete")
            except Exception as e:
                self.logger.warning(f"Error during WebDriver cleanup: {e}")
    
    def search_company(self, company_name: str) -> Optional[str]:
        """
        Search for a company on G2 using browser automation.
        
        Args:
            company_name: Name of the company to search for
            
        Returns:
            Product URL if found, None otherwise
        """
        self._setup_driver()
        
        try:
            # Navigate to G2 homepage
            self.logger.info(f"🔍 Navigating to G2.com...")
            self.driver.get(self.base_url)
            time.sleep(3)  # Let page load
            
            # Look for search box and search for company
            self.logger.info(f"🔍 Searching for: {company_name}")
            
            try:
                # Try different search box selectors
                search_selectors = [
                    "input[name='query']",
                    "input[placeholder*='Search']",
                    "input[type='search']",
                    ".search-input",
                    "#search-query"
                ]
                
                search_box = None
                for selector in search_selectors:
                    try:
                        search_box = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        break
                    except TimeoutException:
                        continue
                
                if not search_box:
                    self.logger.warning("Could not find search box, trying direct URL approach")
                    return self._try_direct_zoom_urls()
                
                # Clear and type search query
                search_box.clear()
                search_box.send_keys(company_name)
                time.sleep(1)
                
                # Try to submit search
                try:
                    search_box.send_keys("\n")  # Press Enter
                    time.sleep(3)
                except:
                    # Try to find and click search button
                    search_buttons = ["button[type='submit']", ".search-button", "button:contains('Search')"]
                    for btn_selector in search_buttons:
                        try:
                            search_btn = self.driver.find_element(By.CSS_SELECTOR, btn_selector)
                            search_btn.click()
                            time.sleep(3)
                            break
                        except:
                            continue
                
                # Look for product results
                self.logger.info("📋 Looking for product results...")
                
                # Wait for results to load
                time.sleep(3)
                
                # Try different product link selectors
                product_selectors = [
                    "a[href*='/products/']",
                    ".product-listing a",
                    ".search-result a[href*='/products/']",
                    "a[href*='zoom']:not([href*='evolphin'])"
                ]
                
                for selector in product_selectors:
                    try:
                        product_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        for link in product_links[:5]:  # Check first 5 results
                            try:
                                href = link.get_attribute('href')
                                text = clean_text(link.text)
                                
                                self.logger.debug(f"Found link: {href} - {text}")
                                
                                if href and '/products/' in href:
                                    # Check if this looks like the right Zoom product
                                    if self._is_zoom_video_product(href, text, company_name):
                                        self.logger.info(f"✅ Found G2 product: {href}")
                                        return href
                                        
                            except Exception as e:
                                self.logger.debug(f"Error processing link: {e}")
                                continue
                                
                    except Exception as e:
                        self.logger.debug(f"Error with selector {selector}: {e}")
                        continue
                
                # If search didn't work, try direct URLs
                self.logger.info("🔗 Search didn't find results, trying direct URLs...")
                return self._try_direct_zoom_urls()
                
            except Exception as e:
                self.logger.warning(f"Search failed: {e}")
                return self._try_direct_zoom_urls()
                
        except Exception as e:
            self.logger.error(f"Browser search failed: {e}")
            return None
        
    def _is_zoom_video_product(self, url: str, text: str, search_term: str) -> bool:
        """Check if this is the correct Zoom Video Communications product."""
        url_lower = url.lower()
        text_lower = text.lower()
        search_lower = search_term.lower()
        
        # Look for Zoom Video Communications, not other Zoom products
        zoom_indicators = ['zoom-meetings', 'zoom-video', 'zoom-workplace', 'zoom']
        zoom_exclusions = ['evolphin', 'zoominfo', 'zoom-phone', 'zoomdata']
        
        # Check if URL contains Zoom indicators but not exclusions
        has_zoom_indicator = any(indicator in url_lower for indicator in zoom_indicators)
        has_exclusion = any(exclusion in url_lower for exclusion in zoom_exclusions)
        
        if has_zoom_indicator and not has_exclusion:
            return True
            
        # Check text content
        if search_lower in text_lower and not any(excl in text_lower for excl in zoom_exclusions):
            return True
            
        return False
    
    def _try_direct_zoom_urls(self) -> Optional[str]:
        """Try direct URLs for Zoom products."""
        zoom_urls = [
            f"{self.base_url}/products/zoom",
            f"{self.base_url}/products/zoom-meetings", 
            f"{self.base_url}/products/zoom-video-communications",
            f"{self.base_url}/products/zoom-workplace",
            f"{self.base_url}/products/zoom-video-conferencing"
        ]
        
        for url in zoom_urls:
            try:
                self.logger.info(f"🔗 Trying direct URL: {url}")
                self.driver.get(url)
                time.sleep(3)
                
                # Check if page loaded successfully and has product content
                if self._is_valid_product_page():
                    self.logger.info(f"✅ Found valid product page: {url}")
                    return url
                    
            except Exception as e:
                self.logger.debug(f"Direct URL failed {url}: {e}")
                continue
        
        return None
    
    def _is_valid_product_page(self) -> bool:
        """Check if current page is a valid G2 product page."""
        try:
            # Look for product page indicators
            indicators = [
                ".product-head",
                ".product-header", 
                "h1[data-testid='product-name']",
                ".breadcrumb",
                "[data-testid='reviews-section']"
            ]
            
            for indicator in indicators:
                if self.driver.find_elements(By.CSS_SELECTOR, indicator):
                    return True
            
            # Check URL structure
            current_url = self.driver.current_url
            return '/products/' in current_url and not '404' in self.driver.title.lower()
            
        except:
            return False
    
    def get_reviews_page(self, product_url: str, page: int = 1) -> Dict[str, Any]:
        """
        Get reviews from a G2 product page using browser automation.
        
        Args:
            product_url: Product URL
            page: Page number to retrieve
            
        Returns:
            Dictionary with reviews data and pagination info
        """
        if not self.driver:
            self._setup_driver()
        
        try:
            # Navigate to reviews page
            if '/reviews' not in product_url:
                reviews_url = product_url.rstrip('/') + '/reviews'
            else:
                reviews_url = product_url
            
            # Add pagination parameter if needed
            if page > 1:
                reviews_url += f"?page={page}"
            
            self.logger.info(f"📄 Loading reviews page {page}: {reviews_url}")
            self.driver.get(reviews_url)
            time.sleep(3)
            
            # Wait for reviews to load
            self._wait_for_reviews_to_load()
            
            # Extract reviews using JavaScript
            reviews = self._extract_reviews_from_dom()
            
            # Check for next page
            has_next = self._has_next_page()
            
            return {
                'reviews': reviews,
                'has_next': has_next,
                'total_pages': None
            }
            
        except Exception as e:
            raise ScrapingError(f"Failed to get G2 reviews page {page}: {e}")
    
    def _wait_for_reviews_to_load(self):
        """Wait for review elements to load on the page and handle dynamic loading."""
        self.logger.info("⏳ Waiting for reviews to load...")
        
        # First, wait for the page to stabilize
        time.sleep(5)
        
        # Try to scroll down to trigger lazy loading
        try:
            self.logger.info("📜 Scrolling to trigger dynamic content loading...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Scroll back up and down a few times to ensure all content loads
            for i in range(3):
                self.driver.execute_script(f"window.scrollTo(0, {i * 1000});")
                time.sleep(1)
        except Exception as e:
            self.logger.debug(f"Error during scrolling: {e}")
        
        # Wait for various possible review selectors
        review_selectors = [
            "[data-testid='review']",
            "[data-testid*='review']",
            ".review-item",
            ".paper--white",
            "[itemprop='review']",
            ".review-card",
            "div[class*='review']",
            ".review",
            "article"
        ]
        
        found_reviews = False
        for selector in review_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.logger.info(f"📋 Found {len(elements)} potential review elements with selector: {selector}")
                    found_reviews = True
                    break
            except Exception as e:
                self.logger.debug(f"Error checking selector {selector}: {e}")
                continue
        
        if not found_reviews:
            self.logger.warning("⚠️ No review elements found with standard selectors")
            # Log page source snippet for debugging
            try:
                page_source_snippet = self.driver.page_source[:2000]
                self.logger.debug(f"Page source snippet: {page_source_snippet}")
            except:
                pass
        
        # Wait a bit more for any remaining dynamic content
        time.sleep(3)
    
    def _extract_reviews_from_dom(self) -> List[Dict[str, Any]]:
        """Extract review data directly from the DOM."""
        reviews = []
        
        # JavaScript to extract review data
        js_script = """
        function extractReviews() {
            const reviews = [];
            console.log('Starting review extraction...');
            
            // Try multiple selectors for review containers
            const selectors = [
                '[data-testid="review"]',
                '[data-testid*="review"]',
                '.review-item',
                '.paper--white',
                '[itemprop="review"]',
                '.review-card',
                '[data-review-id]',
                'div[class*="review"]',
                '.review',
                'article',
                '[data-cy*="review"]',
                '.paper--box',
                '.review-list-item'
            ];
            
            let reviewElements = [];
            let foundSelector = null;
            
            for (const selector of selectors) {
                reviewElements = document.querySelectorAll(selector);
                if (reviewElements.length > 0) {
                    foundSelector = selector;
                    console.log(`Found ${reviewElements.length} elements with selector: ${selector}`);
                    break;
                }
            }
            
            if (reviewElements.length === 0) {
                // Fallback: look for any div that might contain review-like content
                console.log('No review elements found with selectors, trying fallback...');
                const allDivs = document.querySelectorAll('div');
                const potentialReviews = [];
                
                allDivs.forEach(div => {
                    const text = div.textContent || '';
                    // Look for divs that have substantial text and might be reviews
                    if (text.length > 200 && text.length < 2000) {
                        const hasRatingIndicators = text.includes('star') || text.includes('★') || text.includes('rating');
                        const hasReviewKeywords = text.includes('review') || text.includes('recommend') || text.includes('experience');
                        if (hasRatingIndicators || hasReviewKeywords) {
                            potentialReviews.push(div);
                        }
                    }
                });
                
                reviewElements = potentialReviews.slice(0, 20); // Limit to first 20 potential reviews
                console.log(`Found ${reviewElements.length} potential review divs via fallback`);
            }
            
            reviewElements.forEach((element, index) => {
                try {
                    // Extract title
                    const titleSelectors = ['h3', '.review-title', '[data-testid*="title"]', 'h4'];
                    let title = '';
                    for (const sel of titleSelectors) {
                        const titleEl = element.querySelector(sel);
                        if (titleEl && titleEl.textContent.trim()) {
                            title = titleEl.textContent.trim();
                            break;
                        }
                    }
                    
                    // Extract review text
                    const textSelectors = ['.review-text', '[data-testid*="review-text"]', '.content', 'p'];
                    let reviewText = '';
                    for (const sel of textSelectors) {
                        const textEl = element.querySelector(sel);
                        if (textEl && textEl.textContent.trim().length > 50) {
                            reviewText = textEl.textContent.trim();
                            break;
                        }
                    }
                    
                    // Extract rating
                    let rating = '0';
                    const ratingSelectors = ['[data-rating]', '.rating', '.stars'];
                    for (const sel of ratingSelectors) {
                        const ratingEl = element.querySelector(sel);
                        if (ratingEl) {
                            rating = ratingEl.getAttribute('data-rating') || 
                                    ratingEl.getAttribute('aria-label') || 
                                    ratingEl.textContent.trim();
                            if (rating) break;
                        }
                    }
                    
                    // Count stars if no explicit rating
                    if (!rating || rating === '0') {
                        const stars = element.querySelectorAll('.star.filled, .fa-star:not(.fa-star-o)');
                        if (stars.length > 0) {
                            rating = stars.length.toString();
                        }
                    }
                    
                    // Extract reviewer name
                    const nameSelectors = ['.reviewer-name', '.author', '.user-name', '[data-testid*="reviewer"]'];
                    let reviewerName = 'Anonymous';
                    for (const sel of nameSelectors) {
                        const nameEl = element.querySelector(sel);
                        if (nameEl && nameEl.textContent.trim()) {
                            reviewerName = nameEl.textContent.trim();
                            break;
                        }
                    }
                    
                    // Extract date
                    const dateSelectors = ['time', '.date', '[data-date]', '.review-date'];
                    let dateText = '';
                    for (const sel of dateSelectors) {
                        const dateEl = element.querySelector(sel);
                        if (dateEl) {
                            dateText = dateEl.getAttribute('datetime') || 
                                      dateEl.getAttribute('data-date') || 
                                      dateEl.textContent.trim();
                            if (dateText) break;
                        }
                    }
                    
                    // Only add if we have substantial content
                    if (title || (reviewText && reviewText.length > 20)) {
                        reviews.push({
                            title: title || 'No title',
                            review_text: reviewText || 'No content',
                            rating_text: rating,
                            reviewer_name: reviewerName,
                            date_text: dateText,
                            element_index: index
                        });
                    }
                } catch (e) {
                    console.log('Error extracting review:', e);
                }
            });
            
            return reviews;
        }
        
        return extractReviews();
        """
        
        try:
            extracted_reviews = self.driver.execute_script(js_script)
            self.logger.info(f"📋 Extracted {len(extracted_reviews)} reviews from DOM")
            return extracted_reviews or []
        
        except Exception as e:
            self.logger.warning(f"JavaScript extraction failed: {e}")
            return []
    
    def _has_next_page(self) -> bool:
        """Check if there's a next page of reviews using DOM inspection."""
        try:
            # JavaScript to check for next page
            js_script = """
            function hasNextPage() {
                // Look for next page indicators
                const nextSelectors = [
                    'a[aria-label*="next"]',
                    '.next:not(.disabled)',
                    '[data-testid*="next"]:not(.disabled)',
                    '.pagination a:last-child'
                ];
                
                for (const selector of nextSelectors) {
                    const nextEl = document.querySelector(selector);
                    if (nextEl && !nextEl.disabled && nextEl.href) {
                        return true;
                    }
                }
                
                // Check pagination numbers
                const pageLinks = document.querySelectorAll('.pagination a, .page-numbers a');
                if (pageLinks.length > 1) {
                    return true;
                }
                
                return false;
            }
            
            return hasNextPage();
            """
            
            return self.driver.execute_script(js_script) or False
        
        except Exception as e:
            self.logger.debug(f"Error checking for next page: {e}")
            return False
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        """
        Parse raw review data into standardized Review model.
        
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
                    'raw_date_text': raw_review.get('date_text'),
                    'element_index': raw_review.get('element_index')
                }
            )
            
        except Exception as e:
            raise ScrapingError(f"Failed to parse G2 browser review: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        self._cleanup_driver()