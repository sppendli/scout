"""
SQLite database management.
Handles schema creation, CRUD operations, and query utilities.
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
    Database manaher for Scout with connection pooling and error handling.
    """

    def __init__(self, db_path: str="data/scout.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Create connection with row factory for dict-like access.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """
        Initialize database schema if tables don't exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                set_name TEXT NOT NULL
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
                FORIEGN KEY (competitor_id) REFERENCES competitors(id)           
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
