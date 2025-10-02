# Multi-Source SaaS Review Scraper

A robust, maintainable, and extensible tool for scraping product reviews from multiple SaaS review platforms including **G2**, **Capterra**, and **TrustRadius**.

## 🚀 Features

- **Multi-Platform Support**: Scrape reviews from G2, Capterra, and TrustRadius
- **Date Range Filtering**: Get reviews within specific time periods
- **Unified Data Model**: Consistent JSON output format across all sources
- **Extensible Architecture**: Easy to add new review sources
- **Robust Error Handling**: Retry logic, timeout handling, and graceful failure
- **CLI Interface**: User-friendly command-line interface
- **Comprehensive Logging**: Debug and monitor scraping operations
- **Rate Limiting**: Respectful scraping with built-in delays
- **Pagination Support**: Handle large numbers of reviews automatically

## 📋 Requirements

- Python 3.10+
- Internet connection
- See `requirements.txt` for Python dependencies

## 🛠️ Installation

1. **Clone or download the project**:
   ```bash
   git clone <repository-url>
   cd saas-review-scraper
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## 📖 Usage

### Basic Scraping

```bash
python main.py scrape --company "Zoom" --start-date 2024-01-01 --end-date 2024-03-01 --source g2
```

### Advanced Examples

**Scrape with custom output file**:
```bash
python main.py scrape -c "Slack" -s 2024-01-01 -e 2024-02-01 -r capterra -o slack_reviews.json
```

**Limit number of pages and enable verbose logging**:
```bash
python main.py scrape --company "Salesforce" --start-date 2024-01-01 --end-date 2024-01-31 --source trustradius --max-pages 5 --verbose
```

**Search for a company without scraping**:
```bash
python main.py search "HubSpot"
```

**List available sources**:
```bash
python main.py sources
```

**Validate a previously generated JSON file**:
```bash
python main.py validate zoom_g2_reviews_20240101_to_20240301.json
```

**Get ALL reviews (ignores date range)**:
```bash
# Scrape every single review for a company, regardless of date
python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r trustradius --all-reviews -v

# Combined with direct URL for G2 (when you have the product URL)
python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r g2 --all-reviews --direct-url "https://www.g2.com/products/zoom" -v
```

### Handling Anti-Bot Measures

Some review platforms (particularly G2) have implemented anti-bot measures that may block automated requests. If you encounter **403 Forbidden** errors, you have several options:

#### Option 1: Use Direct URLs
Manually find the product URL and use it directly:

```bash
# 1. Visit the review site in your browser
# 2. Search for your company manually
# 3. Copy the product URL
# 4. Use the --direct-url parameter
python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r g2 --direct-url "https://www.g2.com/products/zoom"
```

#### Option 2: Try Different Sources
Different platforms have different anti-bot policies:

```bash
# Try Capterra instead of G2
python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r capterra

# Try TrustRadius
python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r trustradius
```

#### Option 3: Wait and Retry
Anti-bot measures may be temporary:
- Wait 10-15 minutes and try again
- Try from a different network or IP address
- Use a VPN if necessary

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--company` | `-c` | Company/product name to search for (required) |
| `--start-date` | `-s` | Start date in YYYY-MM-DD format (required) |
| `--end-date` | `-e` | End date in YYYY-MM-DD format (required) |
| `--source` | `-r` | Review source: g2, capterra, or trustradius (required) |
| `--output` | `-o` | Output file path (auto-generated if not provided) |
| `--max-pages` | `-p` | Maximum number of pages to scrape |
| `--verbose` | `-v` | Enable verbose logging |
|| `--debug` | `-d` | Enable debug logging |
|| `--direct-url` | `-u` | Direct product URL (bypass search when blocked) |
|| `--all-reviews` | `-a` | Scrape ALL reviews (ignores date range) |

## 📊 Output Format

The scraper generates a JSON file with the following structure:

```json
{
  "config": {
    "company_name": "Zoom",
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-03-01T00:00:00",
    "source": "g2",
    "output_file": null,
    "max_pages": null
  },
  "reviews": [
    {
      "title": "Excellent video conferencing solution",
      "review": "Zoom has been fantastic for our remote team meetings. The audio and video quality is consistently high, and the interface is intuitive.",
      "date": "2024-01-15T10:30:00",
      "reviewer_name": "Sarah Johnson",
      "rating": 4.5,
      "source": "g2",
      "additional_fields": {
        "raw_rating_text": "4.5",
        "raw_date_text": "January 15, 2024"
      }
    }
  ],
  "total_reviews_found": 127,
  "pages_scraped": 13,
  "scraping_duration_seconds": 45.2,
  "timestamp": "2024-01-20T15:30:45"
}
```

### Review Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Review title/summary |
| `review` | string | Full review text content |
| `date` | ISO datetime | When the review was posted |
| `reviewer_name` | string | Name of the reviewer |
| `rating` | float | Numerical rating (0-5 scale, normalized) |
| `source` | string | Source platform (g2, capterra, trustradius) |
| `additional_fields` | object | Platform-specific metadata |

## 🏗️ Architecture

### Core Components

```
saas-review-scraper/
├── main.py                 # CLI application entry point
├── models/
│   ├── __init__.py
│   └── review.py          # Pydantic data models
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py    # Abstract base class
│   ├── g2_scraper.py      # G2.com implementation
│   ├── capterra_scraper.py # Capterra.com implementation
│   └── trustradius_scraper.py # TrustRadius.com implementation
├── utils/
│   ├── __init__.py
│   └── helpers.py         # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_models.py     # Model tests
│   ├── test_utils.py      # Utility tests
│   └── test_scrapers.py   # Scraper tests
├── requirements.txt
└── README.md
```

### Data Flow

1. **Configuration**: CLI parses input and creates `ScrapingConfig`
2. **Scraper Selection**: Appropriate scraper is instantiated based on source
3. **Company Search**: Scraper searches for the company on the platform
4. **Review Extraction**: Reviews are fetched page by page with pagination
5. **Data Parsing**: Raw HTML is parsed into structured `Review` objects
6. **Date Filtering**: Reviews are filtered by the specified date range
7. **Output Generation**: Results are serialized to JSON format

### Extensibility

Adding a new review source is straightforward:

1. **Create a new scraper class** inheriting from `ReviewScraper`
2. **Implement the abstract methods**:
   - `search_company()`: Find the company on the platform
   - `get_reviews_page()`: Fetch a page of reviews
   - `parse_review()`: Parse individual review data
3. **Add to the scraper registry** in `main.py`
4. **Update the source validation** in `models/review.py`

Example new scraper structure:
```python
class NewSourceScraper(ReviewScraper):
    def __init__(self):
        super().__init__("newsource")
        self.base_url = "https://www.newsource.com"
    
    def search_company(self, company_name: str) -> Optional[str]:
        # Implementation here
        pass
    
    def get_reviews_page(self, company_id: str, page: int = 1) -> Dict[str, Any]:
        # Implementation here
        pass
    
    def parse_review(self, raw_review: Dict[str, Any]) -> Review:
        # Implementation here
        pass
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

The test suite includes:
- **Unit tests** for all utility functions
- **Model validation tests** for Pydantic schemas
- **Scraper tests** with mocked HTTP responses
- **Integration tests** for complete workflows

## 🔧 Configuration

### Environment Variables

You can set the following environment variables to customize behavior:

```bash
# Set default log level
export SCRAPER_LOG_LEVEL=INFO

# Set request timeout (seconds)
export SCRAPER_TIMEOUT=30

# Set delay between requests (seconds)
export SCRAPER_DELAY=1
```

### Customization

The scrapers can be customized by modifying:

- **User-Agent strings** in `base_scraper.py`
- **Request timeouts** in individual scrapers
- **CSS selectors** for different website layouts
- **Retry parameters** in `utils/helpers.py`

## 🚨 Error Handling

The scraper handles various error scenarios gracefully:

- **Company not found**: Clear error message with suggestions
- **Network timeouts**: Automatic retry with exponential backoff
- **Rate limiting**: Built-in delays between requests
- **Invalid dates**: Validation with helpful error messages
- **Parsing failures**: Graceful degradation with logging

## 📝 Logging

The application provides comprehensive logging:

```bash
# Default (warnings and errors only)
python main.py scrape --company "Zoom" --start-date 2024-01-01 --end-date 2024-01-31 --source g2

# Verbose (info level)
python main.py scrape --company "Zoom" --start-date 2024-01-01 --end-date 2024-01-31 --source g2 --verbose

# Debug (all messages)
python main.py scrape --company "Zoom" --start-date 2024-01-01 --end-date 2024-01-31 --source g2 --debug
```

Log messages include:
- Search progress and results
- Page scraping status
- Review parsing details
- Error diagnostics
- Performance metrics

## ⚖️ Legal and Ethical Considerations

This tool is designed for legitimate research and analysis purposes. When using it:

- **Respect robots.txt** files and website terms of service
- **Use reasonable delays** between requests (built-in)
- **Don't overload servers** with excessive requests
- **Respect rate limits** and implement additional delays if needed
- **Use data responsibly** and in compliance with applicable laws

## 🤝 Contributing

To contribute to this project:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature-name`
3. **Make changes and add tests**
4. **Ensure tests pass**: `pytest`
5. **Submit a pull request**

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock

# Run tests before committing
pytest --cov=.

# Format code (optional)
black .
flake8 .
```

## 🔮 Future Enhancements

Potential improvements and features:

- **Additional Sources**: GetApp, Software Advice, Gartner Peer Insights
- **Authentication**: Support for logged-in scraping
- **Parallel Processing**: Multi-threaded scraping for better performance
- **Database Storage**: Direct database integration options
- **Web Interface**: Simple web UI for non-technical users
- **Scheduled Scraping**: Cron-like scheduling for regular updates
- **Data Analysis**: Built-in sentiment analysis and reporting
- **Export Formats**: CSV, Excel, and other export options

## 🐛 Troubleshooting

### Common Issues

**"Company not found" error**:
- Try different variations of the company name
- Use the `search` command to test company discovery
- Check if the company exists on the target platform

**Empty results**:
- Verify the date range includes the period when reviews were posted
- Check if the company has reviews on the selected platform
- Try expanding the date range

**Connection errors**:
- Check your internet connection
- Some sites may block requests from certain regions
- Try using a VPN if necessary

**Slow performance**:
- Use `--max-pages` to limit the number of pages scraped
- The built-in delays are necessary to be respectful to the servers
- Consider scraping during off-peak hours

### Getting Help

1. **Check the logs** with `--debug` flag for detailed information
2. **Review the test cases** for usage examples
3. **Open an issue** with detailed error information
4. **Provide sample data** when reporting parsing issues

## 📄 License

This project is provided for educational and research purposes. Please ensure compliance with the terms of service of the platforms you're scraping and applicable laws in your jurisdiction.

---

**Happy Scraping! 🚀**

For questions, suggestions, or issues, please refer to the project's issue tracker or documentation.