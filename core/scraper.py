"""
Multi-source web scraper for competitive intelligence.

This module provides robust web scraping capabilities for RSS feeds and HTML
blog pages with automatic deduplication, rate limiting, and error recovery.
It supports batch scraping across multiple competitors and data sources.


Classes
-------
ScoutScraper
    Multi-source scraper with rate limiting and error recovery

Functions
---------
scraper : ScoutScraper
    Global scraper instance
"""

import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse
import requests
import feedparser
from newspaper import Article, ArticleException
from html import unescape
import re
import sys

from core.config import SCRAPE_CONFIG, get_random_user_agent, get_set_names
from core.database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScoutScraper:
    """
    Multi-source scraper with rate limiting and error recovery.
    
    This class handles scraping of competitive intelligence content from
    both RSS feeds and HTML blog pages. It includes per-domain rate limiting,
    automatic content cleaning, date normalization, and integration with
    the database for deduplication.
    
    Attributes
    ----------
    session : requests.Session
        Persistent HTTP session for connection pooling
    last_request_time : dict
        Mapping of domain names to last request timestamps for rate limiting
    """

    def __init__(self):
        """
        Initialize scraper wiht HTTP session and rate limiting state.

        Create a persistant requests session for connection pooling and
        initializes per-domain rate limiting tracking dictionary.
        """
        self.session = requests.Session()
        self.last_request_time = {}

    def _rate_limit(self, url: str):
        """
        Enforce rate limiting per domain.
        
        Implements per-domain rate limiting with configurable delay to prevent
        overwhelming target servers. Uses domain-level tracking to allow
        parallel scraping of different domains while respecting rate limits
        for each individual domain.
        
        Parameters
        ----------
        url : str
            Full URL being scraped (domain is extracted automatically)
        """
        domain = urlparse(url).netloc
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < SCRAPE_CONFIG["rate_limit_delay"]:
                time.sleep(SCRAPE_CONFIG["rate_limit_delay"] - elapsed)
        self.last_request_time[domain] = time.time()

    def _clean_html_content(self, content: str) -> str:
        """
        Remove HTML tags and decode entities from text content.
        
        Strips all HTML markup and decodes HTML entities (e.g., &amp; → &,
        &lt; → <) to produce clean plain text suitable for LLM processing.
        
        Parameters
        ----------
        content : str
            Raw HTML content with markup and entities
        
        Returns
        -------
        str
            Cleaned plain text with whitespace normalized
        """
        content = unescape(content)
        content = re.sub('<[^<]+?>', '', content)
        return content.strip()
    
    def _parse_date(self, entry) -> Optional[str]:
        """
        Extract and normalize date from RSS entry.
        
        Attempts to parse publication date from RSS feed entries by checking
        multiple standard date fields (published_parsed, updated_parsed).
        Normalizes dates to ISO 8601 format for consistent database storage.
        
        Parameters
        ----------
        entry : feedparser.FeedParserDict
            RSS feed entry object from feedparser
        
        Returns
        -------
        str or None
            ISO 8601 formatted date string (YYYY-MM-DDTHH:MM:SS), or None
            if no valid date found
        """
        for date_field in ["published_parsed", "updated_parsed"]:
            if hasattr(entry, date_field):
                try:
                    date_tuple = getattr(entry, date_field)
                    if date_tuple:
                        return datetime(*date_tuple[:6]).isoformat()
                except Exception:
                    continue
        return None

    def scrape_rss(self, url: str) -> List[Dict]:
        """
        Scrape RSS feed and extract articles.
        
        Fetches and parses an RSS/Atom feed using feedparser, extracting
        article metadata and content. Automatically cleans HTML from content
        fields and normalizes dates. Limits to 20 most recent entries.
        
        Parameters
        ----------
        url : str
            Full URL of RSS/Atom feed (e.g., https://example.com/feed.xml)
        
        Returns
        -------
        list of dict
            List of article dictionaries with keys:
            - title : str
                Article headline (or "Untitled" if missing)
            - content : str
                Cleaned plain text content
            - url : str
                Direct link to full article
            - date : str or None
                ISO 8601 publication date
                
            Returns empty list if scraping fails or all articles are too short
        """
        articles = []
        try:
            logger.info(f"📡 Scraping RSS: {url}")
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.warning(f"RSS parse warning for {url}: {feed.bozo_exception}")

            for entry in feed.entries[:20]:
                try:
                    content = ""
                    if hasattr(entry, "content"):
                        content = entry.content[0].value
                    elif hasattr(entry, "summary"):
                        content = entry.summary
                    elif hasattr(entry, "description"):
                        content = entry.description
                    
                    content = self._clean_html_content(content)

                    if len(content) < SCRAPE_CONFIG["min_content_length"]:
                        logger.debug(f"Skipping short article: {entry.get('title', 'Untitled')}")
                        continue

                    articles.append({
                        "title": entry.get("title", "Untitled"),
                        "content": content.strip(),
                        "url": entry.get("link", url),
                        "date": self._parse_date(entry)
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse RSS entry: {e}")
                    continue

            logger.info(f"✅ Extracted {len(articles)} articles from RSS")
        except Exception as e:
            logger.error(f"RSS scraping failed for {url}: {e}")

        return articles
    
    def scrape_html(self, url: str) -> List[Dict]:
        """
        Scrape HTML blog page using newspaper3k.
        
        Downloads and extracts article content from HTML blog pages using
        the newspaper3k library. This method is designed for individual
        article pages rather than index/listing pages.
        
        Parameters
        ----------
        url : str
            Full URL of HTML article page
        
        Returns
        -------
        list of dict
            List containing single article dictionary with keys:
            - title : str
                Extracted article headline (or "Untitled")
            - content : str
                Cleaned article text content
            - url : str
                Original URL
            - date : str or None
                ISO 8601 publication date if detected
                
            Returns empty list if:
            - Scraping fails (network error, invalid URL)
            - Content extraction fails
            - Article is shorter than min_content_length
        """
        articles = []
        try:
            logger.info(f"🌐 Scraping HTML: {url}")

            article = Article(url)
            article.download()
            article.parse()

            if len(article.text) < SCRAPE_CONFIG["min_content_length"]:
                logger.warning(f"Article too short: {url}")
                return articles
            
            articles.append({
                "title": article.title or "Untitled",
                "content": article.text.strip(),
                "url": url,
                "date": article.publish_date.isoformat() if article.publish_date else None
            })

            logger.info(f"✅ Extracted article from HTML: {article.title[:50]}")
        except ArticleException as e:
            logger.error(f"Newspaper3k extraction failed for {url}: {e}")
        except Exception as e:
            logger.error(f"HTML scraping failed for {url}: {e}")

        return articles
    
    def scrape_source(self, source: Dict) -> Tuple[int, int]:
        """
        Scrape a single source and save to database.
        
        High-level method that routes to appropriate scraper (RSS or HTML)
        based on source type, then saves all extracted articles to the
        database with automatic deduplication. Updates the source's
        last_scraped timestamp.
        
        Parameters
        ----------
        source : dict
            Source dictionary from database with keys:
            - id : int
                Source database ID
            - url : str
                Source URL
            - source_type : str
                Either "rss" or "html"
            - competitor_id : int
                Foreign key to competitor
        
        Returns
        -------
        tuple of (int, int)
            - new_count : int
                Number of new articles saved to database
            - duplicate_count : int
                Number of duplicate articles skipped
        """
        source_id = source["id"]
        url = source["url"]
        source_type = source["source_type"]

        if source_type == "rss":
            raw_articles = self.scrape_rss(url)
        elif source_type == "html":
            raw_articles = self.scrape_html(url)
        else:
            logger.error(f"Unknown source type: {source_type}")
            return 0, 0
        
        new_count = 0
        duplicate_count = 0

        for article in raw_articles:
            article_id = db.add_article(
                source_id=source_id,
                title=article["title"],
                content=article["content"],
                url=article["url"],
                publish_date=article["date"]
            )

            if article_id:
                new_count += 1
            else:
                duplicate_count += 1

        db.update_source_scrape_time(source_id)
        
        return new_count, duplicate_count        
    
    def scrape_competitor(self, competitor_id: int):
        """
        Scrape all sources for a competitor.
        
        Processes all active sources (RSS feeds and HTML pages) for a single
        competitor, aggregating statistics across all sources. Continues
        processing remaining sources if individual sources fail.
        
        Parameters
        ----------
        competitor_id : int
            Database ID of competitor to scrape
        
        Returns
        -------
        dict
            Summary statistics dictionary with keys:
            - total_sources : int
                Number of sources processed
            - new_articles : int
                Total new articles across all sources
            - duplicates : int
                Total duplicate articles skipped
            - errors : int
                Number of sources that failed to scrape
        """
        sources = db.get_sources_by_competitor(competitor_id)

        total_new = 0
        total_duplicates = 0
        errors = 0

        for source in sources:
            try:
                new, duplicates = self.scrape_source(source)
                total_new += new
                total_duplicates += duplicates
            except Exception as e:
                logger.error(f"Failed to scrape source {source['url']}: {e}")
                errors += 1

        return {
            "total_sources": len(sources),
            "new_articles": total_new,
            "duplicates": total_duplicates,
            "errors": errors
        }
    
    def scrape_competitor_set(self, set_name: str) -> Dict:
        """
        Scrape all competitors in a set.
        
        High-level method for batch scraping an entire competitor set.
        Processes all competitors sequentially and aggregates statistics.
        This is the primary entry point for scheduled scraping jobs.
        
        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics", "Design Tools",
            "Project Management")
        
        Returns
        -------
        dict
            Aggregated statistics dictionary with keys:
            - set_name : str
                Name of competitor set processed
            - competitors : int
                Number of competitors in set
            - new_articles : int
                Total new articles across all competitors
            - duplicates : int
                Total duplicates skipped across all competitors
            - errors : int
                Total source failures across all competitors
            - elapsed_seconds : float
                Total processing time in seconds
            - per_competitor : dict
                Mapping of competitor names to their individual stats dicts
                (from scrape_competitor)
        """
        logger.info(f"🚀 Starting scrape for competitor set: {set_name}")
        start_time = time.time()

        competitors = db.get_competitors_by_set(set_name)
        results = {}

        for competitor in competitors:
            logger.info(f"📊 Scraping {competitor['name']}...")
            results[competitor['name']] = self.scrape_competitor(competitor['id'])
        
        elapsed = time.time() - start_time

        total_new = sum(r["new_articles"] for r in results.values())
        total_duplicates = sum(r["duplicates"] for r in results.values())
        total_errors = sum(r["errors"] for r in results.values())

        summary = {
            "set_name": set_name,
            "competitors": len(competitors),
            "new_articles": total_new,
            "duplicates": total_duplicates,
            "errors": total_errors,
            "elapsed_seconds": round(elapsed, 2),
            "per_competitor": results
        }

        logger.info(f"✅ Scrape complete: {total_new} new articles in {elapsed:.1f}s")
        return summary
    
scraper = ScoutScraper()

if __name__ =="__main__":
    if len(sys.argv) > 1:
        set_name = sys.argv[1]
    else:
        set_name = get_set_names()[0]
    
    print(f"/n 🧪 Testing scraper for: {set_name}\n")
    results = scraper.scrape_competitor_set(set_name)

    print(f"\n📊 Results:")
    print(f"    New articles: {results['new_articles']}")
    print(f"    Duplicates: {results['duplicates']}")
    print(f"    Errors: {results['errors']}")
    print(f"    Time: {results['elapsed_seconds']}s")