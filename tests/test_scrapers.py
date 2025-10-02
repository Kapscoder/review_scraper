"""
Unit tests for scraper classes with mocked responses.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.g2_scraper import G2Scraper
from scrapers.capterra_scraper import CapterraScraper
from scrapers.trustradius_scraper import TrustRadiusScraper
from scrapers.base_scraper import ScrapingError
from models.review import ScrapingConfig, Review


class TestBaseScraper:
    """Test base scraper functionality."""
    
    def test_scraper_initialization(self):
        """Test scraper initialization."""
        scraper = G2Scraper()
        
        assert scraper.source_name == "g2"
        assert scraper.base_url == "https://www.g2.com"
        assert scraper.session is not None
    
    def test_date_validation(self):
        """Test date range validation."""
        scraper = G2Scraper()
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        review_date = datetime(2024, 1, 15)
        
        assert scraper.validate_date_in_range(review_date, start_date, end_date) is True
        
        # Test date outside range
        old_date = datetime(2023, 12, 15)
        assert scraper.validate_date_in_range(old_date, start_date, end_date) is False


class TestG2Scraper:
    """Test G2 scraper functionality."""
    
    @pytest.fixture
    def g2_scraper(self):
        """Create G2 scraper instance."""
        return G2Scraper()
    
    @pytest.fixture
    def mock_search_response(self):
        """Mock HTML response for company search."""
        html = '''
        <html>
            <body>
                <div class="search-results">
                    <a href="/products/zoom" class="product-link">
                        <span class="product-name">Zoom Video Communications</span>
                    </a>
                    <a href="/products/slack" class="product-link">
                        <span class="product-name">Slack</span>
                    </a>
                </div>
            </body>
        </html>
        '''
        return html
    
    @pytest.fixture
    def mock_reviews_response(self):
        """Mock HTML response for reviews page."""
        html = '''
        <html>
            <body>
                <div class="reviews">
                    <div data-review-id="1" class="review-container">
                        <h3 class="review-title">Great software for video calls</h3>
                        <div class="review-text">Zoom works really well for our team meetings. Easy to use and reliable.</div>
                        <div class="reviewer-name">John Smith</div>
                        <div class="rating" data-rating="4.5">4.5 stars</div>
                        <time datetime="2024-01-15T10:30:00Z">January 15, 2024</time>
                    </div>
                    <div data-review-id="2" class="review-container">
                        <h3 class="review-title">Good value for money</h3>
                        <div class="review-text">The pricing is reasonable and it has all the features we need.</div>
                        <div class="reviewer-name">Jane Doe</div>
                        <div class="rating" data-rating="4.0">4 stars</div>
                        <time datetime="2024-01-20T14:15:00Z">January 20, 2024</time>
                    </div>
                </div>
                <div class="pagination">
                    <a href="?page=2" class="next">Next</a>
                </div>
            </body>
        </html>
        '''
        return html
    
    def test_company_search_success(self, g2_scraper, mock_search_response):
        """Test successful company search."""
        with patch.object(g2_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.content = mock_search_response.encode()
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = g2_scraper.search_company("Zoom")
            
            assert result is not None
            assert "/products/zoom" in result
    
    def test_company_search_not_found(self, g2_scraper):
        """Test company search when company is not found."""
        with patch.object(g2_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.content = b'<html><body><div class="no-results">No results found</div></body></html>'
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = g2_scraper.search_company("NonexistentCompany")
            
            assert result is None
    
    def test_get_reviews_page(self, g2_scraper, mock_reviews_response):
        """Test getting reviews page."""
        with patch.object(g2_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.content = mock_reviews_response.encode()
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = g2_scraper.get_reviews_page("https://www.g2.com/products/zoom", 1)
            
            assert 'reviews' in result
            assert 'has_next' in result
            assert len(result['reviews']) == 2
            assert result['has_next'] is True
    
    def test_parse_review(self, g2_scraper):
        """Test parsing individual review."""
        raw_review = {
            'title': 'Great product',
            'review_text': 'This is an excellent software solution.',
            'reviewer_name': 'Test User',
            'rating_text': '4.5',
            'date_text': '2024-01-15T10:30:00Z'
        }
        
        review = g2_scraper.parse_review(raw_review)
        
        assert isinstance(review, Review)
        assert review.title == 'Great product'
        assert review.rating == 4.5
        assert review.source == 'g2'
        assert review.date.year == 2024
    
    def test_company_match_logic(self, g2_scraper):
        """Test company matching logic."""
        # Exact match
        assert g2_scraper._is_company_match("Zoom", "Zoom Video Communications") is True
        
        # Partial match
        assert g2_scraper._is_company_match("Slack", "Slack Technologies") is True
        
        # No match
        assert g2_scraper._is_company_match("Zoom", "Microsoft Teams") is False
    
    def test_fuzzy_matching(self, g2_scraper):
        """Test fuzzy matching logic."""
        # Similar companies should match
        assert g2_scraper._fuzzy_match("Microsoft Corp", "Microsoft Corporation") is True
        
        # Different companies should not match
        assert g2_scraper._fuzzy_match("Google", "Apple") is False


class TestCapterraScraper:
    """Test Capterra scraper functionality."""
    
    @pytest.fixture
    def capterra_scraper(self):
        """Create Capterra scraper instance."""
        return CapterraScraper()
    
    def test_scraper_initialization(self, capterra_scraper):
        """Test Capterra scraper initialization."""
        assert capterra_scraper.source_name == "capterra"
        assert capterra_scraper.base_url == "https://www.capterra.com"
    
    def test_search_url_construction(self, capterra_scraper):
        """Test search URL construction for Capterra."""
        with patch.object(capterra_scraper.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.content = b'<html><body></body></html>'
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            capterra_scraper.search_company("TestCompany")
            
            # Check that the request was made to the correct URL
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == "https://www.capterra.com/search"


class TestTrustRadiusScraper:
    """Test TrustRadius scraper functionality."""
    
    @pytest.fixture
    def trustradius_scraper(self):
        """Create TrustRadius scraper instance."""
        return TrustRadiusScraper()
    
    def test_scraper_initialization(self, trustradius_scraper):
        """Test TrustRadius scraper initialization."""
        assert trustradius_scraper.source_name == "trustradius"
        assert trustradius_scraper.base_url == "https://www.trustradius.com"
    
    def test_rating_scale_conversion(self, trustradius_scraper):
        """Test 10-point to 5-point rating scale conversion."""
        # Mock a review with 10-point rating
        raw_review = {
            'title': 'Test Review',
            'review_text': 'Test content',
            'reviewer_name': 'Test User',
            'rating_text': '8.0',  # 10-point scale
            'date_text': '2024-01-15'
        }
        
        review = trustradius_scraper.parse_review(raw_review)
        
        # Should be converted to 5-point scale (8.0 / 2 = 4.0)
        assert review.rating == 4.0
        assert review.additional_fields['original_rating_scale'] == '10-point'


class TestScrapingIntegration:
    """Test complete scraping workflow."""
    
    def test_full_scraping_workflow(self):
        """Test complete scraping workflow with mocked responses."""
        scraper = G2Scraper()
        
        config = ScrapingConfig(
            company_name="TestCompany",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2"
        )
        
        # Mock company search
        with patch.object(scraper, 'search_company', return_value="https://www.g2.com/products/test"):
            # Mock reviews fetching
            with patch.object(scraper, 'get_reviews_page', return_value={
                'reviews': [
                    {
                        'title': 'Test Review',
                        'review_text': 'Test content',
                        'reviewer_name': 'Test User',
                        'rating_text': '4.0',
                        'date_text': '2024-01-15'
                    }
                ],
                'has_next': False
            }):
                # Mock review parsing
                with patch.object(scraper, 'parse_review', return_value=Review(
                    title='Test Review',
                    review='Test content',
                    date=datetime(2024, 1, 15),
                    reviewer_name='Test User',
                    rating=4.0,
                    source='g2'
                )):
                    reviews = scraper.scrape_reviews(config)
                    
                    assert len(reviews) == 1
                    assert reviews[0].title == 'Test Review'
    
    def test_scraping_with_company_not_found(self):
        """Test scraping when company is not found."""
        scraper = G2Scraper()
        
        config = ScrapingConfig(
            company_name="NonexistentCompany",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2"
        )
        
        # Mock company search returning None
        with patch.object(scraper, 'search_company', return_value=None):
            with pytest.raises(ScrapingError) as exc_info:
                scraper.scrape_reviews(config)
            
            assert "not found" in str(exc_info.value).lower()
    
    def test_scraping_with_date_filtering(self):
        """Test that scraping properly filters reviews by date."""
        scraper = G2Scraper()
        
        config = ScrapingConfig(
            company_name="TestCompany",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2"
        )
        
        # Mock company search
        with patch.object(scraper, 'search_company', return_value="https://www.g2.com/products/test"):
            # Mock reviews with different dates
            with patch.object(scraper, 'get_reviews_page', return_value={
                'reviews': [
                    {'title': 'Old Review', 'review_text': 'Old', 'reviewer_name': 'User1', 'rating_text': '4.0', 'date_text': '2023-12-15'},
                    {'title': 'Good Review', 'review_text': 'Good', 'reviewer_name': 'User2', 'rating_text': '4.0', 'date_text': '2024-01-15'},
                    {'title': 'New Review', 'review_text': 'New', 'reviewer_name': 'User3', 'rating_text': '4.0', 'date_text': '2024-02-15'}
                ],
                'has_next': False
            }):
                # Mock review parsing to return reviews with proper dates
                def mock_parse_review(raw_review):
                    date_map = {
                        'Old Review': datetime(2023, 12, 15),
                        'Good Review': datetime(2024, 1, 15),
                        'New Review': datetime(2024, 2, 15)
                    }
                    
                    return Review(
                        title=raw_review['title'],
                        review=raw_review['review_text'],
                        date=date_map[raw_review['title']],
                        reviewer_name=raw_review['reviewer_name'],
                        rating=4.0,
                        source='g2'
                    )
                
                with patch.object(scraper, 'parse_review', side_effect=mock_parse_review):
                    reviews = scraper.scrape_reviews(config)
                    
                    # Should only include the review within date range
                    assert len(reviews) == 1
                    assert reviews[0].title == 'Good Review'