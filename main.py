#!/usr/bin/env python3
"""
Multi-Source SaaS Review Scraper

A command-line tool to scrape product reviews from G2, Capterra, and TrustRadius.
"""
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from models.review import ScrapingConfig, ScrapingResult
from scrapers.g2_scraper import G2Scraper
from scrapers.g2_browser_scraper import G2BrowserScraper
from scrapers.g2_advanced_bypass import G2AdvancedBypassScraper
from scrapers.g2_wire_scraper import G2WireScraper
from scrapers.capterra_scraper import CapterraScraper
from scrapers.trustradius_scraper import TrustRadiusScraper
from scrapers.base_scraper import ScrapingError
from utils.helpers import setup_logging, generate_output_filename


# Scraper registry
SCRAPERS = {
    'g2': G2Scraper,
    'g2_browser': G2BrowserScraper,
    'g2_advanced': G2AdvancedBypassScraper,
    'g2_wire': G2WireScraper,
    'capterra': CapterraScraper,
    'trustradius': TrustRadiusScraper
}


@click.command()
@click.option('--company', '-c', required=True, help='Company/product name to search for')
@click.option('--start-date', '-s', required=True, help='Start date (YYYY-MM-DD format)')
@click.option('--end-date', '-e', required=True, help='End date (YYYY-MM-DD format)')
@click.option('--source', '-r', required=True, 
              type=click.Choice(['g2', 'g2_browser', 'g2_advanced', 'g2_wire', 'capterra', 'trustradius'], case_sensitive=False),
              help='Review source to scrape')
@click.option('--output', '-o', help='Output file path (auto-generated if not provided)')
@click.option('--max-pages', '-p', type=int, help='Maximum number of pages to scrape')
@click.option('--direct-url', '-u', help='Direct product URL (useful when search is blocked)')
@click.option('--all-reviews', '-a', is_flag=True, help='Scrape ALL reviews (ignores date range)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--debug', '-d', is_flag=True, help='Enable debug logging')
def main(company: str, start_date: str, end_date: str, source: str, 
         output: Optional[str], max_pages: Optional[int], direct_url: Optional[str], 
         all_reviews: bool, verbose: bool, debug: bool):
    """
    Scrape product reviews from various SaaS review platforms.
    
    Examples:
        python main.py scrape --company "Zoom" --start-date 2024-01-01 --end-date 2024-03-01 --source g2
        
        python main.py scrape -c "Slack" -s 2024-01-01 -e 2024-02-01 -r capterra -o slack_reviews.json
        
        python main.py scrape --company "Salesforce" --start-date 2024-01-01 --end-date 2024-01-31 --source trustradius --max-pages 5 --verbose
        
        # Use direct URL when automated search fails (e.g., due to anti-bot measures):
        python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r g2 --direct-url "https://www.g2.com/products/zoom"
        
        # Get ALL reviews (ignores date range):
        python main.py scrape -c "Zoom" -s 2024-01-01 -e 2024-03-01 -r g2 --all-reviews --direct-url "https://www.g2.com/products/zoom"
    """
    # Set up logging
    if debug:
        setup_logging('DEBUG')
    elif verbose:
        setup_logging('INFO')
    else:
        setup_logging('WARNING')
    
    logger = logging.getLogger(__name__)
    logger.info("Starting SaaS Review Scraper")
    
    try:
        # Handle all-reviews mode with flexible dates
        if all_reviews:
            # Use very broad date range to capture all reviews
            from datetime import datetime
            actual_start_date = "2000-01-01"  # Very old date
            actual_end_date = datetime.now().strftime("%Y-%m-%d")  # Today
            logger.info(f"🔄 ALL REVIEWS mode enabled - ignoring specified date range")
            logger.info(f"📅 Using broad date range: {actual_start_date} to {actual_end_date}")
        else:
            actual_start_date = start_date
            actual_end_date = end_date
        
        # Create and validate configuration
        config = ScrapingConfig(
            company_name=company,
            start_date=actual_start_date,
            end_date=actual_end_date,
            source=source.lower(),
            output_file=output,
            max_pages=max_pages
        )
        
        logger.info(f"Configuration: {config.company_name} from {config.start_date.date()} to {config.end_date.date()} on {config.source}")
        
        # Initialize scraper
        scraper_class = SCRAPERS[config.source]
        scraper = scraper_class()
        
        # If direct URL is provided, use it instead of searching
        if direct_url:
            logger.info(f"Using direct URL: {direct_url}")
            # Directly scrape without searching
            start_time = time.time()
            reviews = scraper.scrape_reviews_from_url(config, direct_url)
        else:
            # Run normal scraping with search
            start_time = time.time()
            reviews = scraper.scrape_reviews(config)
        duration = time.time() - start_time
        
        # Create result object
        result = ScrapingResult(
            config=config,
            reviews=reviews,
            total_reviews_found=len(reviews),
            pages_scraped=0,  # We don't track this precisely in the current implementation
            scraping_duration_seconds=duration
        )
        
        # Generate output filename if not provided
        if not config.output_file:
            output_path = generate_output_filename(
                config.company_name, 
                config.source, 
                config.start_date, 
                config.end_date
            )
        else:
            output_path = config.output_file
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write results to file
        with open(output_path, 'w', encoding='utf-8') as f:
            # Convert to dict and handle datetime serialization
            result_dict = result.dict()
            json.dump(result_dict, f, indent=2, ensure_ascii=False, default=str)
        
        # Print summary
        click.echo(f"\n✅ Scraping completed successfully!")
        click.echo(f"📊 Found {len(reviews)} reviews")
        click.echo(f"⏱️  Duration: {duration:.2f} seconds")
        click.echo(f"💾 Output saved to: {output_path}")
        
        if verbose:
            click.echo(f"\n📈 Review summary by rating:")
            ratings = {}
            for review in reviews:
                rating_key = f"{review.rating:.1f} stars"
                ratings[rating_key] = ratings.get(rating_key, 0) + 1
            
            for rating, count in sorted(ratings.items()):
                click.echo(f"   {rating}: {count} reviews")
        
    except ScrapingError as e:
        logger.error(f"Scraping error: {e}")
        
        # Check if this is a blocking/403 error and provide additional guidance
        if "403" in str(e) or "Forbidden" in str(e) or "not found" in str(e).lower():
            click.echo(f"\n❌ Scraping failed: {e}", err=True)
            click.echo("\n🤖 This appears to be due to anti-bot measures.", err=True)
            click.echo("\n💡 Workaround options:", err=True)
            click.echo(f"\n1. 🌐 Manual URL method:", err=True)
            click.echo(f"   • Visit the review site in your browser", err=True)
            click.echo(f"   • Search for '{company}' manually", err=True)
            click.echo(f"   • Copy the product URL", err=True)
            click.echo(f"   • Re-run with: --direct-url \"<copied-url>\"", err=True)
            click.echo(f"\n2. 🔄 Try different sources:", err=True)
            click.echo(f"   python main.py scrape -c \"{company}\" -s {start_date} -e {end_date} -r capterra", err=True)
            click.echo(f"   python main.py scrape -c \"{company}\" -s {start_date} -e {end_date} -r trustradius", err=True)
        else:
            click.echo(f"❌ Scraping failed: {e}", err=True)
        
        raise click.ClickException(str(e))
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        click.echo(f"❌ Configuration error: {e}", err=True)
        raise click.ClickException(str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(f"❌ Unexpected error occurred: {e}", err=True)
        raise click.ClickException("An unexpected error occurred. Check logs for details.")


@click.group()
def cli():
    """Multi-Source SaaS Review Scraper CLI"""
    pass


@cli.command()
def sources():
    """List available review sources"""
    click.echo("Available review sources:")
    for source in SCRAPERS.keys():
        click.echo(f"  • {source}")


@cli.command()
@click.argument('company')
@click.option('--source', '-r', 
              type=click.Choice(['g2', 'g2_browser', 'g2_advanced', 'capterra', 'trustradius'], case_sensitive=False),
              help='Specific source to search (searches all if not specified)')
def search(company: str, source: Optional[str]):
    """
    Search for a company across review sources without scraping.
    
    This is useful for testing if a company can be found before running a full scrape.
    """
    setup_logging('INFO')
    logger = logging.getLogger(__name__)
    
    sources_to_check = [source] if source else list(SCRAPERS.keys())
    
    click.echo(f"🔍 Searching for '{company}' on review sources...")
    
    found_any = False
    for source_name in sources_to_check:
        click.echo(f"\nChecking {source_name}...")
        
        try:
            scraper_class = SCRAPERS[source_name]
            scraper = scraper_class()
            
            result = scraper.search_company(company)
            if result:
                click.echo(f"✅ Found on {source_name}: {result}")
                found_any = True
            else:
                click.echo(f"❌ Not found on {source_name}")
                
        except Exception as e:
            logger.warning(f"Error searching {source_name}: {e}")
            click.echo(f"⚠️  Error searching {source_name}: {e}")
    
    if not found_any:
        click.echo(f"\n❌ '{company}' was not found on any of the searched sources.")
        click.echo("💡 Try different variations of the company name or check if the product exists on these platforms.")


@cli.command()
@click.argument('file_path')
def validate(file_path: str):
    """Validate a JSON output file from a previous scraping operation"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Try to parse as ScrapingResult
        result = ScrapingResult.parse_obj(data)
        
        click.echo(f"✅ File is valid!")
        click.echo(f"📊 Contains {len(result.reviews)} reviews")
        click.echo(f"🏢 Company: {result.config.company_name}")
        click.echo(f"📅 Date range: {result.config.start_date.date()} to {result.config.end_date.date()}")
        click.echo(f"🌐 Source: {result.config.source}")
        
    except FileNotFoundError:
        click.echo(f"❌ File not found: {file_path}", err=True)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ Validation failed: {e}", err=True)


# Add the main command to the CLI group
cli.add_command(main, name="scrape")


if __name__ == '__main__':
    cli()