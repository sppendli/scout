"""
LLM-based event classification for Market Intelligence.

This module provides AI-powered classification of competitive intelligence
articles using OpenAI's GPT-4o-Mini with structured JSON outputs. It includes
caching, rate limiting, and batch processing capabilities.

Classes
-------
EventClassifier
    LLM-based article classifier with caching and rate limiting

Functions
---------
classifier : EventClassifier
    Global classifier instances
"""

import os
import logging
import time
from typing import Dict, List, Optional, Tuple
import hashlib
from datetime import datetime
import json
import sys

from openai import OpenAI
from dotenv import load_dotenv

from core.config import LLM_CONFIG, EVENT_CATEGORIES, get_set_names
from core.database import db

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventClassifier:
    """
    LLM-based article classifier with caching and rate limiting.
    
    This class uses OpenAI's GPT-4o-Mini to classify competitive intelligence
    articles into categories (feature launches, pricing changes, partnerships).
    It includes built-in caching to avoid duplicate API calls and rate limiting
    to stay within API quotas.
    
    Attributes
    ----------
    client : OpenAI
        Authenticated OpenAI API client
    model : str
        Model identifier (e.g., "gpt-4o-mini")
    confidence_threshold : float
        Minimum confidence score to accept classification (0.0-1.0)
    cache : dict
        In-memory cache mapping content hashes to classification results
    request_times : list of float
        Timestamps of recent API requests for rate limiting
        
    Raises
    ------
    ValueError
        If OPENAI_API_KEY environment variable is not set
    """

    def __init__(self):
        """
        Initialize classifier with OpenAI API credentials.

        Raises
        ------
        ValueError
            If OPENAI_API_KEY environmenr variable is not found
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API Key not found in environment.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = LLM_CONFIG["model"]
        self.confidence_threshold = LLM_CONFIG["confidence_threshold"] 
        self.cache = {}
        self.request_times = []

    def _rate_limit(self):
        """
        Enforce rate limiting (3 requests per second).
        
        Blocks execution if more than 3 requests have been made in the
        last second. Uses sliding window algorithm to track request times.
        
        Notes
        -----
        This is a blocking operation. If the rate limit is exceeded, the
        method will sleep until it's safe to proceed. The 3 req/sec limit
        aligns with OpenAI's Tier 1 rate limits for GPT-4o-mini.
        """
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 1.0]

        if len(self.request_times) >= 3:
            sleep_time = 1.0 - (now - self.request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self.request_times.append(time.time())

    def _build_system_prompt(self) -> str:
        """
        Construct system prompt with category definitions and examples.
        
        Dynamically builds the system prompt from EVENT_CATEGORIES config,
        including descriptions, keywords, and examples for each category.
        Also includes classification rules, confidence scoring guidelines,
        and structured output requirements.
        
        Returns
        -------
        str
            Complete system prompt with category definitions, classification
            rules, and JSON schema requirements
            
        Notes
        -----
        The prompt uses few-shot learning principles with concrete examples
        and explicit instructions for JSON formatting. Temperature is set to 0
        in the API call for deterministic outputs.
        """
        categories_deec = "\n\n".join([
            f"**{cat}**: {info['description']}\n"
            f"Examples: {', '.join(info['examples'])}"
            for cat, info in EVENT_CATEGORIES.items()
        ])

        return f"""You are a competitive intelligence assistant specializing in SaaS, design tools, and project management software.
Your task is to analyze company blog posts and announcements to extract actionable competitive intelligence events.

## Event Categories

{categories_deec}

## Classification Rules

1. **Be selective**: Only classify articles that contain actual competitve intelligence (product changes, pricing, partnerships). Skip generic content, tutorials, or though leadership pieces.
2. **Confidence scoring**: Rate your confidence 0.0-1.0 based on:
    - 0.9-1.0: Explicit announcement with clear details
    - 0.7-0.9: Strong indicators but some ambiguity
    - 0.5-0.7: Indirect mentions or implications
    - Below 0.5: Uncertain or not relevant (classify as "other")
3. **Extract entities**: Identify mentioned products, features, pricing tiers, partner companies, or technologies.
4. **Impact assessment**: Rate potential competitive impact as "high", "medium", or "low":
    - High: Major feature launches, significant pricing changes, strategic acquisitions
    - Medium: Incremental features, minor pricing adjustments, standard integrations
    - Low: Bug fixes, UI improvements, general partnerships
5. **Summarize concisely**: 1-2 sentences capturing the key competitive insight.

## Response Format

You must respond with valid JSON matching this structure:
{{
    "category": "feature_launch|pricing_change|partnership|other",
    "summary": "Brief description of the event(1-2 sentences)",
    "confidence": 0.85,
    "entities": ["Entity1", "Entity2"],
    "impact_level": "high|medium|low"
}}

REQUIREMENTS:
- "confidence" MUST be a NUMBER between 0.0 and 1.0 (NOT a string)
- "entities" MUST be an ARRAY of strings (NOT a string or object)
- "category" MUST be one of: feature_launch, pricing_change, partnership, other
- "impact_level" MUST be one of: high, medium, low

If the article contains no relevant competitive intelligence, return:
{{
    "category": "other",
    "summary": "General content or not actionable",
    "confidence" : 0.3,
    "entities": [],
    "impact_level": "low"
}}
"""
    
    def _build_user_prompt(self, article: Dict) -> str:
        """
        Format article content for classification.
        
        Constructs the user message with article metadata and truncated content.
        Content is limited to 3000 characters to stay within token limits while
        providing sufficient context for classification.
        
        Parameters
        ----------
        article : dict
            Article dictionary with keys:
            - title : str
                Article headline
            - content : str
                Full article text (will be truncated to 3000 chars)
            - competitor_name : str, optional
                Source company name
            - url : str
                Article URL
        
        Returns
        -------
        str
            Formatted user prompt with article details
            
        Notes
        -----
        The 3000 character limit is empirically chosen to balance context
        quality with API costs. Most blog post intros contain enough signal
        within the first 3000 characters for accurate classification.
        """
        return f"""Analyze this article and extract for competitve intelligence:

**Title**: {article['title']}

**Source**: {article.get('competitor_name', 'Unknown')}

**Content**:
{article['content'][:3000]}

**URL**: {article['url']}

Classify this article according to the system instructions.
"""
    
    def classify_article(self, article: Dict) -> Optional[Dict]:
        """
        Classify a single article using LLM.
        
        Sends article content to OpenAI API for structured classification.
        Results are cached by content hash to avoid redundant API calls.
        Returns None if confidence is below threshold or if API call fails.
        
        Parameters
        ----------
        article : dict
            Article dictionary with keys:
            - id : int
                Article database ID
            - title : str
                Article headline
            - content : str
                Full article text
            - url : str
                Article URL
            - competitor_name : str, optional
                Source company name
        
        Returns
        -------
        dict or None
            Classification result dictionary with keys:
            - category : str
                Event category (feature_launch, pricing_change, partnership, other)
            - summary : str
                1-2 sentence competitive insight summary
            - confidence : float
                Confidence score (0.0-1.0)
            - entities : list of str
                Extracted entities (products, features, companies)
            - impact_level : str
                Competitive impact (high, medium, low)
            
            Returns None if:
            - Confidence is below threshold (default 0.5)
            - API call fails
            - Response format is invalid
            - Cache hit returns None (previously failed)
        """
        content_hash = hashlib.sha256(article['content'].encode()).hexdigest()
        if content_hash in self.cache:
            logger.debug(f"Cache hit for article: {article['title'][:50]}")
            return self.cache[content_hash]
        
        self._rate_limit()

        try:
            logger.info(f"🤖 Classifying: {article['title'][:60]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role":"system", "content": self._build_system_prompt()},
                    {"role": "user", "content": self._build_user_prompt(article)}
                ],
                temperature=LLM_CONFIG["temperature"],
                max_tokens=LLM_CONFIG["max_tokens"],
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            required_fields = ["category", "summary", "confidence", "entities", "impact_level"]
            if not all(field in result for field in required_fields):
                logger.error(f"Invalid response format: {result}")
                return None

            if isinstance(result.get('confidence'), str):
                result['confidence'] = float(result['confidence'])

            if result["confidence"] < self.confidence_threshold:
                logger.info(f"⏭️ Skipping low confidence ({result['confidence']:.2f}): {article['title'][:50]}")
                return None
            
            self.cache[content_hash] = result

            logger.info(f"✅ Classified as {result['category']} ({result['confidence']:.2f})")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None
        except Exception as e:
            logger.error(f"Classification failed for {article['title'][:50]}: {e}")
            return None
        
    def classify_and_save(self, article: Dict) -> Optional[int]:
        """
        Classify article and save event to database.
        
        Combines classification and database persistence in a single operation.
        Automatically skips "other" category results (non-actionable content).
        
        Parameters
        ----------
        article : dict
            Article dictionary with required keys:
            - id : int
                Article database ID (used as foreign key)
            - title : str
                Article headline
            - content : str
                Full article text
            - url : str
                Article URL
            - competitor_name : str, optional
                Source company name
        
        Returns
        -------
        int or None
            Database ID of created event, or None if:
            - Classification fails or returns None
            - Category is "other" (non-actionable)
            - Database save operation fails
        """
        classification = self.classify_article(article)
        if not classification:
            return None
        
        if classification["category"] == "other":
            logger.debug(f"Skipping 'other' category for: {article['title'][:50]}")
            return None
        
        try:
            event_id = db.add_event(
                article_id=article['id'],
                category=classification['category'],
                summary=classification['summary'],
                confidence=classification['confidence'],
                entities={"items": classification['entities']},
                impact_level=classification['impact_level']
            )
            return event_id
        except Exception as e:
            logger.error(f"Failed to save event: {e}")
            return None
        
    def batch_classify(self, articles: List[Dict], max_articles: int = None) -> Dict:
        """
        Classify multiple articles with progress tracking.
        
        Processes a list of articles sequentially, skipping already-classified
        articles and tracking detailed statistics. Designed for ETL pipelines
        and scheduled refresh workflows.
        
        Parameters
        ----------
        articles : list of dict
            List of article dictionaries (see classify_article for schema)
        max_articles : int, optional
            Maximum number of articles to process (useful for testing),
            by default None (process all)
        
        Returns
        -------
        dict
            Summary statistics dictionary with keys:
            - total : int
                Total articles in input list
            - classified : int
                Successfully classified and saved events
            - skipped_low_confidence : int
                Articles below confidence threshold
            - skipped_other : int
                Articles already classified or "other" category
            - errors : int
                API failures or unexpected errors
            - cached : int
                Cache hits (not currently tracked, reserved for future)
            - elapsed_seconds : float
                Total processing time in seconds
            - avg_time_per_article : float
                Average processing time per article in seconds
        """
        if max_articles:
            articles = articles[:max_articles]
        
        logger.info(f"🚀 Starting batch classification of {len(articles)} articles")
        start_time = time.time()

        stats = {
            "total": len(articles),
            "classified": 0,
            "skipped_low_confidence": 0,
            "skipped_other": 0,
            "errors": 0,
            "cached": 0
        }

        for i, article in enumerate(articles, 1):
            logger.info(f"📊 Progress: {i}/{len(articles)}")

            existing_events = db.get_events_by_article_id(article['id'])
            if existing_events:
                logger.debug(f"Already classified: {article['title'][:50]}")
                stats["skipped_other"] += 1
                continue

            event_id = self.classify_and_save(article)
            if event_id:
                stats["classified"] += 1
            else:
                stats["skipped_low_confidence"] += 1

        elapsed = time.time() - start_time
        stats["elapsed_seconds"] = round(elapsed, 2)
        stats["avg_time_per_article"] = round(elapsed / len(articles), 2)

        logger.info(f"✅ Batch classification complete: {stats['classified']} events in {elapsed:.1f}s")
        return stats
    
    def classify_competitor_set(self, set_name: str) -> Dict:
        """
        Classify all unclassified articles for a competitor set.
        
        High-level convenience method that queries the database for
        unclassified articles in a specific competitor set and processes
        them in batch. This is the primary entry point for scheduled
        classification jobs.
        
        Parameters
        ----------
        set_name : str
            Name of competitor set (e.g., "SaaS Analytics", "Design Tools",
            "Project Management")
        
        Returns
        -------
        dict
            Statistics dictionary from batch_classify, or a message dict if
            no articles are found:
            - message : str
                "No new articles to classify"
            - classified : int
                0
        """
        logger.info(f"🎯 Classifying articles for set: {set_name}")

        articles = db.get_unclassified_articles_by_set(set_name)
        
        if not articles:
            logger.info("No unclassified articles found")
            return {"message": "No new articles to classify", "classified": 0}
        
        return self.batch_classify(articles)

classifier = EventClassifier()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        set_name = sys.argv[1]
    else:
        set_name = get_set_names()[0]

    print(f"\n🧪 Testing classifier for: {set_name}\n")
    results = classifier.classify_competitor_set(set_name)

    print(f"\n📊 Results:")
    print(json.dumps(results, indent=2))