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
            Database connection with Row factory enabled
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """
        Initialize database schema if tables don't exist.

        This function creates database tables with indexes if the tables do not exist.
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
        
        Parameters
        ----------
        name : str
            Competitor company name (must be unique)
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics")
            
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
        Retrieve all competitors in a specific set.

        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics")

        Returns
        -------
        list of dict
            List of competitor dictionaries that are active with keys:
                - id: Competitor ID
                - name: Competitor Name
                - set_name: Competitor Set Name
                - active: Active Flag (0, 1)
                - created_at: Event Creation Timestamp
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

        Parameters
        ----------
        competitor_id : int
            Competitor ID of the Source
        url : str
            URL of the Source
        source_type : str
            Type of the Source (e.g. "html", "rss")

        Returns
        -------
        int
            Last Row ID of the source (newly created or existing)
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
        Get all sources for a competitor.

        Parameters
        ----------
        competitor_id: int        
        
        Returns
        -------
        list of dict
            list of source dictionaries that are active with the keys:
                - id: Source ID
                - competitor_id: Competitor ID
                - url: URL of the Source
                - source_type: Type of the Source (e.g., "html", "css")
                - last_scraped: Timestamp of when the source was last scraped
                - status: Status of the Source
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
        Update the last_scraped timestamp for a source.

        This function updates the last_scrape_time to the current timestamp in the source table.

        Parameters
        ----------
        source_id: int
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
        Add an article with deduplication via content hash.
        Returns article_id if new, None if duplicate.
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
        Get recent articles for a competitor with source info.
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
        Add a classified event from LLM analysis.
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
        Drop all tables and reinitialize (use with caution).
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