"""
SQLite database management for competitive intelligence.

This module handles all database operations including schema creation,
CRUD operations, and complex queries for competitive intelligence data.

Classes
-------
ScoutDB
    Main database manager with connection pooling and error handling
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import hashlib
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScoutDB:
    """
    Database manager for Scout with connection pooling and error handling.

    This class manages all interactions with the SQLite database including
    schema initialization, CRUD operations, and complex queries for
    retrieving competitive intelligence data.
    
    Parameters
    ----------
    db_path : str, optional
        Path to SQLite database file, default is "data/scout.db"
        
    Attributes
    ----------
    db_path : Path
        Resolved path to database file
    """

    def __init__(self, db_path: str="data/scout.db"):
        """
        Initialize database connection and schema.
        
        Parameters
        ----------
        db_path : str, optional
            Path to SQLite database file, default is "data/scout.db"
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Create database connection with row factory for dict-like access.
        
        Returns
        -------
        sqlite3.Connection
            Database connection with Row factory enabled for dict-like access
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """
        Initialize database schema if tables don't exist.

        Creates the following tables with appropriate foreign keys and indexes:
        - competitors: Company information and competitor sets
        - sources: Data sources (blogs, RSS feeds) for each competitor
        - articles: Scraped content with deduplication via content hash
        - events: Classified competitive intelligence events
        
        Also creates indexes on frequently queried columns for performance.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                set_name TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id INTEGER NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL,
                last_scraped TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (competitor_id) REFERENCES competitors(id)           
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                publish_date TEXT,
                url TEXT NOT NULL,
                content_hash TEXT UNIQUE,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES sources(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                confidence REAL,
                entities TEXT,
                impact_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles(id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_competitor ON sources(competitor_id)")

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def add_competitor(self, name: str, set_name: str) -> int:
        """
        Add a competitor to the database.
        
        If a competitor with the same name already exists, returns the
        existing competitor's ID instead of creating a duplicate.
        
        Parameters
        ----------
        name : str
            Competitor company name (must be unique)
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics", "Design Tools")
            
        Returns
        -------
        int
            Database ID of competitor (newly created or existing)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO competitors (name, set_name) VALUES (?, ?)",
                (name, set_name)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Competitor '{name}' already exists")
            cursor.execute("SELECT id FROM competitors WHERE name = ?", (name,))
            return cursor.fetchone()["id"]
        finally:
            conn.close()

    def get_competitors_by_set(self, set_name: str) -> List[Dict]:
        """
        Retrieve all active competitors in a specific set.

        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics")

        Returns
        -------
        list of dict
            List of competitor dictionaries with keys:
            - id : int
                Competitor database ID
            - name : str
                Competitor company name
            - set_name : str
                Competitor set name
            - active : int
                Active status flag (1 = active, 0 = inactive)
            - created_at : str
                ISO format timestamp of creation
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM competitors WHERE set_name = ? AND active = 1",
            (set_name,)
        )
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def add_source(self, competitor_id: int, url: str, source_type: str) -> int:
        """
        Add a data source for a competitor to the database.
        
        If a source with the same URL already exists, returns the existing
        source's ID instead of creating a duplicate.

        Parameters
        ----------
        competitor_id : int
            Foreign key reference to competitors table
        url : str
            Full URL of the data source (must be unique)
        source_type : str
            Type of source, either "html" or "rss"

        Returns
        -------
        int
            Database ID of source (newly created or existing)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sources (competitor_id, url, source_type) VALUES (?, ?, ?)",
                (competitor_id, url, source_type)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Source URL '{url}' already exists")
            cursor.execute(f"SELECT id FROM sources WHERE url = ?", (url,))
            return cursor.fetchone()["id"]
        finally:
            conn.close()

    def get_sources_by_competitor(self, competitor_id: int) -> List[Dict]:
        """
        Get all active sources for a competitor.

        Parameters
        ----------
        competitor_id : int
            Foreign key reference to competitors table
        
        Returns
        -------
        list of dict
            List of source dictionaries with keys:
            - id : int
                Source database ID
            - competitor_id : int
                Foreign key to competitor
            - url : str
                Source URL
            - source_type : str
                Type of source ("html" or "rss")
            - last_scraped : str or None
                ISO timestamp of last successful scrape
            - status : str
                Status flag ("active" or "inactive")
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM sources WHERE competitor_id = ? AND status = 'active'",
            (competitor_id,)
        )
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def update_source_scrape_time(self, source_id: int):
        """
        Update the last_scraped timestamp for a source to current time.

        This should be called after successfully scraping a source to track
        when data was last collected.

        Parameters
        ----------
        source_id : int
            Database ID of the source to update
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sources SET last_scraped = CURRENT_TIMESTAMP WHERE id = ?",
            (source_id,)
        )
        conn.commit()
        conn.close()

    def add_article(self, source_id: int, title: str, content : str, 
                    url:str, publish_date: Optional[str] = None) -> Optional[int]:
        """
        Add an article with automatic deduplication via content hash.
        
        Uses SHA-256 hash of article content to detect duplicates. If the
        content hash already exists, returns None instead of creating a duplicate.

        Parameters
        ----------
        source_id : int
            Foreign key reference to sources table
        title : str
            Article headline/title
        content : str
            Full text content of the article
        url : str
            Direct URL to the article
        publish_date : str, optional
            ISO format publication date (YYYY-MM-DD or full ISO timestamp)

        Returns
        -------
        int or None
            Database ID of newly created article, or None if duplicate detected
        """
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO articles
                (source_id, title, content, url, publish_date, content_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (source_id, title, content, url, publish_date, content_hash)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.debug(f"Duplicate article detected: {title[:50]}")
            return None
        finally:
            conn.close()

    def get_articles_by_competitor(self, competitor_id: int, limit: int = 50) -> List[Dict]:
        """
        Get recent articles for a competitor with source and competitor info.
        
        Performs a three-way join across articles, sources, and competitors
        to provide full context for each article.

        Parameters
        ----------
        competitor_id : int
            Foreign key reference to competitors table
        limit : int, optional
            Maximum number of articles to return, by default 50
        
        Returns
        -------
        list of dict
            List of article dictionaries sorted by fetch time (newest first) with keys:
            - id : int
                Article database ID
            - source_id : int
                Foreign key to source
            - title : str
                Article title
            - content : str
                Full article text
            - url : str
                Article URL
            - publish_date : str or None
                ISO publication date
            - content_hash : str
                SHA-256 hash for deduplication
            - fetched_at : str
                ISO timestamp of scrape
            - source_url : str
                URL of the source that provided this article
            - source_type : str
                Type of source ("html" or "rss")
            - competitor_name : str
                Name of the competitor
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.* , s.url as source_url, s.source_type, c.name as competitor_name 
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c ON s.competitor_id = c.id
            WHERE c.id = ?
            ORDER BY a.fetched_at DESC
            LIMIT ?
        """, (competitor_id, limit))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_unclassified_articles(self, limit: int = 100) -> List[Dict]:
        """
        Get articles that don't have associated events yet.
        
        Returns articles that have been scraped but not yet processed by
        the LLM classifier. Useful for batch classification workflows.

        Parameters
        ----------
        limit : int, optional
            Maximum number of articles to return, by default 100
            
        Returns
        -------
        list of dict
            List of unclassified article dictionaries with keys:
            - id : int
                Article database ID
            - source_id : int
                Foreign key to source
            - title : str
                Article title
            - content : str
                Full article text
            - url : str
                Article URL
            - publish_date : str or None
                ISO publication date
            - fetched_at : str
                ISO timestamp of scrape
            - source_url : str
                URL of the source
            - competitor_name : str
                Name of the competitor
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, s.url as source_url , c.name as competitor_name
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c ON s.competitor_id = c.id
            WHERE a.id NOT IN (SELECT article_id FROM events)
            ORDER BY a.fetched_at DESC
            LIMIT ?
        """, (limit,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def add_event(self, article_id: int, category: str, summary: str,
                  confidence: float, entities: Dict = None, 
                  impact_level: str = "medium") -> int:
        """
        Add a classified competitive intelligence event from LLM analysis.
        
        Stores the results of LLM classification including category, confidence
        score, extracted entities, and impact assessment.

        Parameters
        ----------
        article_id : int
            Foreign key reference to articles table
        category : str
            Event category: "feature_launch", "pricing_change", "partnership", or "other"
        summary : str
            1-2 sentence summary of the competitive intelligence insight
        confidence : float
            LLM confidence score between 0.0 and 1.0
        entities : dict, optional
            Dictionary of extracted entities (products, features, companies), by default None
        impact_level : str, optional
            Competitive impact rating: "high", "medium", or "low", by default "medium"

        Returns
        -------
        int
            Database ID of the newly created event
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        entities_json = json.dumps(entities) if entities else None

        cursor.execute("""
            INSERT INTO events
            (article_id, category, summary, confidence, entities, impact_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (article_id, category, summary, confidence, entities_json, impact_level))
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        return event_id
    
    def get_events_by_set(self, set_name: str, limit: int = 100) -> List[Dict]:
        """
        Get all events for a competitor set with full context.
        
        Performs a four-way join to provide complete article, source, and
        competitor information for each event. Sorted by creation time (newest first).

        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics")
        limit : int, optional
            Maximum number of events to return, by default 100
            
        Returns
        -------
        list of dict
            List of event dictionaries with keys:
            - id : int
                Event database ID
            - article_id : int
                Foreign key to article
            - category : str
                Event category
            - summary : str
                Event summary
            - confidence : float
                Confidence score (0.0-1.0)
            - entities : str
                JSON string of extracted entities
            - impact_level : str
                Impact rating
            - created_at : str
                ISO timestamp of classification
            - title : str
                Article title
            - url : str
                Article URL
            - publish_date : str or None
                Article publication date
            - competitor_name : str
                Competitor company name
            - set_name : str
                Competitor set name
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, a.title, a.url, a.publish_date,
                    c.name as competitor_name, c.set_name
            FROM events e
            JOIN articles a ON e.article_id = a.id
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c on s.competitor_id = c.id
            WHERE c.set_name = ?
            ORDER BY e.created_at DESC
            LIMIT ?
        """, (set_name, limit))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_unclassified_articles_by_set(self, set_name: str, limit: int = 100) -> List[Dict]:
        """
        Get articles from a competitor set that don't have events yet.
        
        Filters unclassified articles to a specific competitor set, useful
        for targeted batch classification workflows.

        Parameters
        ----------
        set_name : str
            Name of competitor set to filter by
        limit : int, optional
            Maximum number of articles to return, by default 100
            
        Returns
        -------
        list of dict
            List of unclassified article dictionaries with keys:
            - id : int
                Article database ID
            - source_id : int
                Foreign key to source
            - title : str
                Article title
            - content : str
                Full article text
            - url : str
                Article URL
            - publish_date : str or None
                ISO publication date
            - fetched_at : str
                ISO timestamp of scrape
            - source_url : str
                URL of the source
            - competitor_name : str
                Name of the competitor
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, s.url as source_url, c.name as competitor_name
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c ON s.competitor_id = c.id
            WHERE c.set_name = ?
            AND a.id NOT IN (SELECT article_id FROM events)
            ORDER BY a.fetched_at DESC
            LIMIT ?
        """, (set_name, limit))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_events_by_article_id(self, article_id: int) -> List[Dict]:
        """
        Get all events for a specific article.
        
        Useful for checking if an article has already been classified to
        avoid duplicate processing.

        Parameters
        ----------
        article_id : int
            Database ID of the article
            
        Returns
        -------
        list of dict
            List of event dictionaries (may be empty if unclassified) with keys:
            - id : int
                Event database ID
            - article_id : int
                Foreign key to article
            - category : str
                Event category
            - summary : str
                Event summary
            - confidence : float
                Confidence score
            - entities : str
                JSON string of entities
            - impact_level : str
                Impact rating
            - created_at : str
                ISO timestamp
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE article_id = ?", (article_id,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_event_stats_by_set(self, set_name: str) -> Dict:
        """
        Get aggregated statistics for a competitor set.
        
        Provides summary metrics including total event count and breakdown
        by category. Used for dashboard metrics and analytics.

        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "Project Management")
            
        Returns
        -------
        dict
            Statistics dictionary with keys:
            - total_events : int
                Total number of events in the set
            - by_category : dict
                Mapping of category names to counts, e.g.:
                {"feature_launch": 15, "pricing_change": 3, "partnership": 7}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total
            FROM events e
            JOIN articles a on e.article_id = a.id
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c ON s.competitor_id = c.id
            WHERE c.set_name = ?
        """, (set_name,))
        total = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT e.category, COUNT(*) as count
            FROM events e
            JOIN articles a ON e.article_id = a.id
            JOIN sources s ON a.source_id = s.id
            JOIN competitors c ON s.competitor_id = c.id
            WHERE c.set_name = ?
            GROUP BY e.category
        """, (set_name,))
        categories = {row["category"]: row["count"] for row in cursor.fetchall()}
        conn.close()
        return {
            "total_events": total,
            "by_category": categories
        }
    
    def reset_database(self):
        """
        Drop all tables and reinitialize schema.
        
        **WARNING**: This operation is destructive and irreversible. All data
        will be permanently deleted. Use only for testing or development.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS events")
        cursor.execute("DROP TABLE IF EXISTS articles")
        cursor.execute("DROP TABLE IF EXISTS sources")
        cursor.execute("DROP TABLE IF EXISTS competitors")
        conn.commit()
        conn.close()
        self._init_schema()
        logger.warning("Database reset complete")

db = ScoutDB()