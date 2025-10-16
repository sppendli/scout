"""
Multi-source web scraper for competitive intelligence.
Supports RSS feeds and HTML content extraction with robust error handling.
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

from core.config import SCRAPE_CONFIG, get_random_user_agent
from core.database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScoutScraper:
    """
    Multi-source scraper with rate limiting and error recovery.
    """

    def __init__(self):
        self.session = requests.Session()
        self.last_request_time = {}

    def _rate_limit(self, url: str):
        """
        Enforce rate limiting per domain.
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
        """
        content = unescape(content)
        content = re.sub('<[^<]+?>', '', content)
        return content.strip()
    
    def _parse_date(self, entry) -> Optional[str]:
        """
        Extract and normalize date from RSS entry.
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
        Returns list of article dicts with title, content, url, date
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
        Return list of article dicts.
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