"""
LLM-based event classification for Market Intelligence.
Uses OpenAI GPT-4o-Mini with structured outputs for reliable parsing.
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
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API Key not found in environment.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = LLM_CONFIG["model"]
        self.cache = {}
        self.request_times = []

    def _rate_limit(self):
        """
        Enforce rate limiting (3 requests per second).
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
        Classify an article using LLM.
        Returns classification dict or None if below confidence threshold.
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
            
            if result["confidence"] < LLM_CONFIG["confidence_threshold"]:
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
        Returns event_id if successful, None otherwise.
        """
        classification = self.classify_article(article)
        if not classification:
            return None
        
        if classification["category"] == "other":
            logger.debug(f"Skipping 'other' category fore: {article['title'][:50]}")
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
        Returns summary statistics.
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
        """
        logger.info(f"🎯 Classifying articles for set: {set_name}")

        articles = db.get_unclassified_articles_by_set(set_name)
        
        if not articles:
            logger.info("No unclassified articles found")
            return {"message": "No new articles to classify", "classifed": 0}
        
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