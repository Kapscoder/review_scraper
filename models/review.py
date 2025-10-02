"""
Data models for SaaS review scraper using Pydantic.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator


class Review(BaseModel):
    """
    Unified review model that represents a review from any source.
    """
    title: str = Field(..., description="Review title/summary")
    review: str = Field(..., description="Full review text content")
    date: datetime = Field(..., description="Review date in ISO format")
    reviewer_name: str = Field(..., description="Name of the reviewer")
    rating: float = Field(..., ge=0, le=5, description="Numerical rating (0-5 scale)")
    source: str = Field(..., description="Source platform (g2, capterra, trustradius)")
    additional_fields: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional platform-specific fields"
    )

    @validator('date', pre=True)
    def parse_date(cls, v):
        """Parse date from various string formats."""
        if isinstance(v, str):
            # Handle common date formats
            from dateutil.parser import parse
            return parse(v)
        return v

    @validator('rating')
    def validate_rating(cls, v):
        """Ensure rating is within valid range."""
        if v < 0 or v > 5:
            raise ValueError('Rating must be between 0 and 5')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ScrapingConfig(BaseModel):
    """
    Configuration model for scraping parameters.
    """
    company_name: str = Field(..., description="Company/product name to search for")
    start_date: datetime = Field(..., description="Start date for filtering reviews")
    end_date: datetime = Field(..., description="End date for filtering reviews")
    source: str = Field(..., description="Review source (g2, capterra, trustradius)")
    output_file: Optional[str] = Field(
        default=None,
        description="Output file path, auto-generated if not provided"
    )
    max_pages: Optional[int] = Field(
        default=None,
        description="Maximum number of pages to scrape (None for unlimited)"
    )

    @validator('start_date', 'end_date', pre=True)
    def parse_dates(cls, v):
        """Parse date strings into datetime objects."""
        if isinstance(v, str):
            from dateutil.parser import parse
            return parse(v)
        return v

    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Ensure end_date is after start_date."""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @validator('source')
    def validate_source(cls, v):
        """Validate source is supported."""
        supported_sources = {'g2', 'g2_browser', 'g2_advanced', 'g2_wire', 'capterra', 'trustradius'}
        if v.lower() not in supported_sources:
            raise ValueError(f'Source must be one of: {supported_sources}')
        return v.lower()


class ScrapingResult(BaseModel):
    """
    Model representing the result of a scraping operation.
    """
    config: ScrapingConfig
    reviews: List[Review]
    total_reviews_found: int
    pages_scraped: int
    scraping_duration_seconds: float
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }