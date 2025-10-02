"""
Unit tests for utility functions.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from utils.helpers import (
    clean_text, parse_rating, parse_flexible_date, 
    extract_company_name_variations, generate_output_filename,
    validate_url, safe_extract, retry_with_backoff
)


class TestCleanText:
    """Test text cleaning utility."""
    
    def test_clean_basic_text(self):
        """Test basic text cleaning."""
        text = "  Hello   World  "
        result = clean_text(text)
        assert result == "Hello World"
    
    def test_clean_html_entities(self):
        """Test HTML entity cleaning."""
        text = "Price &amp; Features &lt;test&gt; &quot;quote&quot; &#39;single&#39;"
        result = clean_text(text)
        assert result == "Price & Features <test> \"quote\" 'single'"
    
    def test_clean_empty_text(self):
        """Test cleaning empty or None text."""
        assert clean_text("") == ""
        assert clean_text(None) == ""
        assert clean_text("   ") == ""


class TestParseRating:
    """Test rating parsing utility."""
    
    def test_parse_numeric_rating(self):
        """Test parsing numeric ratings."""
        assert parse_rating("4.5") == 4.5
        assert parse_rating("3") == 3.0
        assert parse_rating("5.0") == 5.0
    
    def test_parse_rating_from_text(self):
        """Test parsing ratings from text."""
        assert parse_rating("Rating: 4.2 out of 5") == 4.2
        assert parse_rating("3.7 stars") == 3.7
    
    def test_parse_10_point_scale(self):
        """Test parsing 10-point scale ratings."""
        assert parse_rating("8.5") == 4.25  # Should be normalized to 5-point scale
        assert parse_rating("10") == 5.0
    
    def test_parse_invalid_rating(self):
        """Test parsing invalid ratings."""
        assert parse_rating("") == 0.0
        assert parse_rating("invalid") == 0.0
        assert parse_rating(None) == 0.0
    
    def test_parse_rating_bounds(self):
        """Test rating bounds enforcement."""
        assert parse_rating("6") == 3.0  # Normalized from 10-point scale
        assert parse_rating("-1") == 0.0  # Clamped to minimum


class TestParseFlexibleDate:
    """Test flexible date parsing."""
    
    def test_parse_standard_dates(self):
        """Test parsing standard date formats."""
        date1 = parse_flexible_date("2024-01-15")
        assert date1.year == 2024
        assert date1.month == 1
        assert date1.day == 15
        
        date2 = parse_flexible_date("January 15, 2024")
        assert date2.year == 2024
        assert date2.month == 1
        assert date2.day == 15
    
    def test_parse_relative_dates(self):
        """Test parsing relative dates."""
        now = datetime.now()
        
        # Test days ago
        date_5_days = parse_flexible_date("5 days ago")
        expected = now - timedelta(days=5)
        assert abs((date_5_days - expected).total_seconds()) < 60  # Within 1 minute
        
        # Test weeks ago
        date_2_weeks = parse_flexible_date("2 weeks ago")
        expected = now - timedelta(weeks=2)
        assert abs((date_2_weeks - expected).total_seconds()) < 3600  # Within 1 hour
    
    def test_parse_invalid_date(self):
        """Test parsing invalid dates."""
        assert parse_flexible_date("") is None
        assert parse_flexible_date("invalid date") is None
        assert parse_flexible_date(None) is None


class TestCompanyNameVariations:
    """Test company name variation generation."""
    
    def test_basic_variations(self):
        """Test basic company name variations."""
        variations = extract_company_name_variations("Zoom Video Communications")
        
        assert "Zoom Video Communications" in variations
        assert "zoom video communications" in variations
        
        # Check that we get some variations
        assert len(variations) > 2
    
    def test_company_suffix_removal(self):
        """Test removal of company suffixes."""
        variations = extract_company_name_variations("Salesforce Inc.")
        
        # Should include version without suffix
        assert any("Salesforce" in v and "Inc" not in v for v in variations)
    
    def test_ampersand_expansion(self):
        """Test ampersand expansion."""
        variations = extract_company_name_variations("Johnson & Johnson")
        
        # Should include version with "and"
        assert any("Johnson and Johnson" in v for v in variations)


class TestGenerateOutputFilename:
    """Test output filename generation."""
    
    def test_basic_filename(self):
        """Test basic filename generation."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        filename = generate_output_filename("Zoom", "g2", start_date, end_date)
        
        assert "Zoom" in filename
        assert "g2" in filename
        assert "20240101" in filename
        assert "20240131" in filename
        assert filename.endswith(".json")
    
    def test_filename_cleaning(self):
        """Test filename cleaning for special characters."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        filename = generate_output_filename("Test & Company!", "g2", start_date, end_date)
        
        # Should remove special characters
        assert "&" not in filename
        assert "!" not in filename
        assert "Test_Company" in filename


class TestValidateUrl:
    """Test URL validation."""
    
    def test_valid_urls(self):
        """Test valid URL validation."""
        assert validate_url("https://www.example.com") is True
        assert validate_url("http://example.com") is True
        assert validate_url("https://subdomain.example.com/path") is True
    
    def test_invalid_urls(self):
        """Test invalid URL validation."""
        assert validate_url("not-a-url") is False
        assert validate_url("") is False
        assert validate_url("ftp://example.com") is False


class TestSafeExtract:
    """Test safe extraction from BeautifulSoup elements."""
    
    def test_safe_extract_text(self):
        """Test safe text extraction."""
        from bs4 import BeautifulSoup
        
        html = '<div><span class="title">Test Title</span></div>'
        soup = BeautifulSoup(html, 'html.parser')
        div = soup.find('div')
        
        result = safe_extract(div, '.title')
        assert result == "Test Title"
    
    def test_safe_extract_attribute(self):
        """Test safe attribute extraction."""
        from bs4 import BeautifulSoup
        
        html = '<div><a href="/test" class="link">Link</a></div>'
        soup = BeautifulSoup(html, 'html.parser')
        div = soup.find('div')
        
        result = safe_extract(div, '.link', 'href')
        assert result == "/test"
    
    def test_safe_extract_missing_element(self):
        """Test safe extraction with missing elements."""
        from bs4 import BeautifulSoup
        
        html = '<div><span>Test</span></div>'
        soup = BeautifulSoup(html, 'html.parser')
        div = soup.find('div')
        
        result = safe_extract(div, '.missing', default="Not Found")
        assert result == "Not Found"
    
    def test_safe_extract_none_element(self):
        """Test safe extraction with None element."""
        result = safe_extract(None, '.selector', default="Default")
        assert result == "Default"


class TestRetryWithBackoff:
    """Test retry decorator."""
    
    def test_successful_function(self):
        """Test retry with successful function."""
        @retry_with_backoff(max_retries=3)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_retry_on_failure(self):
        """Test retry mechanism on failures."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.RequestException("Network error")
            return "success"
        
        import requests
        result = failing_function()
        assert result == "success"
        assert call_count == 3  # Initial call + 2 retries
    
    def test_retry_exhausted(self):
        """Test behavior when retries are exhausted."""
        @retry_with_backoff(max_retries=2, backoff_factor=0.1)
        def always_failing_function():
            raise requests.RequestException("Persistent error")
        
        import requests
        with pytest.raises(requests.RequestException):
            always_failing_function()