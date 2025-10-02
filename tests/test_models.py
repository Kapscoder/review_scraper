"""
Unit tests for model classes.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from models.review import Review, ScrapingConfig, ScrapingResult


class TestReviewModel:
    """Test Review model validation and functionality."""
    
    def test_valid_review_creation(self):
        """Test creating a valid review."""
        review = Review(
            title="Great product",
            review="This software is excellent for our needs.",
            date=datetime(2024, 1, 15),
            reviewer_name="John Doe",
            rating=4.5,
            source="g2"
        )
        
        assert review.title == "Great product"
        assert review.rating == 4.5
        assert review.source == "g2"
    
    def test_review_with_additional_fields(self):
        """Test review with additional platform-specific fields."""
        additional_data = {
            "company_size": "50-100 employees",
            "industry": "Technology",
            "verified": True
        }
        
        review = Review(
            title="Good value",
            review="Worth the price",
            date=datetime(2024, 1, 15),
            reviewer_name="Jane Smith",
            rating=4.0,
            source="capterra",
            additional_fields=additional_data
        )
        
        assert review.additional_fields["company_size"] == "50-100 employees"
        assert review.additional_fields["verified"] is True
    
    def test_review_date_parsing(self):
        """Test automatic date parsing from strings."""
        review = Review(
            title="Test",
            review="Test review",
            date="2024-01-15T10:30:00",
            reviewer_name="Test User",
            rating=3.0,
            source="g2"
        )
        
        assert isinstance(review.date, datetime)
        assert review.date.year == 2024
        assert review.date.month == 1
        assert review.date.day == 15
    
    def test_invalid_rating_too_high(self):
        """Test validation for rating too high."""
        with pytest.raises(ValidationError):
            Review(
                title="Test",
                review="Test review",
                date=datetime.now(),
                reviewer_name="Test User",
                rating=6.0,  # Too high
                source="g2"
            )
    
    def test_invalid_rating_negative(self):
        """Test validation for negative rating."""
        with pytest.raises(ValidationError):
            Review(
                title="Test",
                review="Test review",
                date=datetime.now(),
                reviewer_name="Test User",
                rating=-1.0,  # Negative
                source="g2"
            )
    
    def test_json_serialization(self):
        """Test JSON serialization of review."""
        review = Review(
            title="Test Review",
            review="This is a test",
            date=datetime(2024, 1, 15, 10, 30),
            reviewer_name="Test User",
            rating=4.0,
            source="g2"
        )
        
        json_data = review.dict()
        
        # Check that datetime is properly serialized
        assert isinstance(json_data['date'], datetime)
        
        # Test JSON encoding
        import json
        json_str = json.dumps(json_data, default=str)
        assert "2024-01-15" in json_str


class TestScrapingConfig:
    """Test ScrapingConfig model validation."""
    
    def test_valid_config_creation(self):
        """Test creating valid scraping configuration."""
        config = ScrapingConfig(
            company_name="Zoom",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2"
        )
        
        assert config.company_name == "Zoom"
        assert config.source == "g2"
        assert isinstance(config.start_date, datetime)
        assert isinstance(config.end_date, datetime)
    
    def test_date_parsing(self):
        """Test automatic date parsing in config."""
        config = ScrapingConfig(
            company_name="Test Company",
            start_date="2024-01-01",
            end_date="2024-12-31",
            source="capterra"
        )
        
        assert config.start_date.year == 2024
        assert config.start_date.month == 1
        assert config.end_date.month == 12
    
    def test_invalid_date_range(self):
        """Test validation for invalid date range."""
        with pytest.raises(ValidationError):
            ScrapingConfig(
                company_name="Test",
                start_date="2024-12-31",
                end_date="2024-01-01",  # End before start
                source="g2"
            )
    
    def test_invalid_source(self):
        """Test validation for invalid source."""
        with pytest.raises(ValidationError):
            ScrapingConfig(
                company_name="Test",
                start_date="2024-01-01",
                end_date="2024-01-31",
                source="invalid_source"
            )
    
    def test_source_case_insensitive(self):
        """Test that source validation is case insensitive."""
        config = ScrapingConfig(
            company_name="Test",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="G2"  # Uppercase
        )
        
        # Should be normalized to lowercase
        assert config.source == "g2"
    
    def test_optional_fields(self):
        """Test optional fields in config."""
        config = ScrapingConfig(
            company_name="Test",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2",
            output_file="custom_output.json",
            max_pages=5
        )
        
        assert config.output_file == "custom_output.json"
        assert config.max_pages == 5


class TestScrapingResult:
    """Test ScrapingResult model."""
    
    def create_sample_config(self):
        """Helper to create sample config."""
        return ScrapingConfig(
            company_name="Test Company",
            start_date="2024-01-01",
            end_date="2024-01-31",
            source="g2"
        )
    
    def create_sample_reviews(self):
        """Helper to create sample reviews."""
        return [
            Review(
                title="Good product",
                review="Works well",
                date=datetime(2024, 1, 15),
                reviewer_name="User 1",
                rating=4.0,
                source="g2"
            ),
            Review(
                title="Excellent",
                review="Love it",
                date=datetime(2024, 1, 20),
                reviewer_name="User 2",
                rating=5.0,
                source="g2"
            )
        ]
    
    def test_scraping_result_creation(self):
        """Test creating scraping result."""
        config = self.create_sample_config()
        reviews = self.create_sample_reviews()
        
        result = ScrapingResult(
            config=config,
            reviews=reviews,
            total_reviews_found=2,
            pages_scraped=1,
            scraping_duration_seconds=15.5
        )
        
        assert len(result.reviews) == 2
        assert result.total_reviews_found == 2
        assert result.scraping_duration_seconds == 15.5
        assert isinstance(result.timestamp, datetime)
    
    def test_scraping_result_serialization(self):
        """Test serializing scraping result to dict."""
        config = self.create_sample_config()
        reviews = self.create_sample_reviews()
        
        result = ScrapingResult(
            config=config,
            reviews=reviews,
            total_reviews_found=2,
            pages_scraped=1,
            scraping_duration_seconds=15.5
        )
        
        result_dict = result.dict()
        
        assert "config" in result_dict
        assert "reviews" in result_dict
        assert len(result_dict["reviews"]) == 2
        assert result_dict["total_reviews_found"] == 2
    
    def test_empty_reviews_list(self):
        """Test scraping result with empty reviews."""
        config = self.create_sample_config()
        
        result = ScrapingResult(
            config=config,
            reviews=[],
            total_reviews_found=0,
            pages_scraped=0,
            scraping_duration_seconds=5.0
        )
        
        assert len(result.reviews) == 0
        assert result.total_reviews_found == 0