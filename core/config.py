"""
Static configuration.
URLs validated as of October 2025.
"""

from typing import Dict, List
import random

COMPETITOR_SETS = {
    "SaaS Analytics": [
        {
            "name": "Mixpanel",
            "sources": [
                {"url": "https://mixpanel.com/blog/", "type": "html"},
                # {"url": "https://mixpanel.com/blog/feed/", "type": "rss"},
                # {"url": "https://mixpanel.com/changelog/", "type": "changelog"}
            ]
        },
        {
            "name": "Amplitude",
            "sources": [
                {"url": "https://amplitude.com/blog", "type": "html"},
                # {"url": "https://amplitude.com/releases", "type": "changelog"}
            ]
        },
        {
            "name": "Heap",
            "sources": [
                {"url": "https://www.heap.io/blog", "type": "html"},
                # {"url": "https://heap.io/changelog", "type": "changelog"}
            ]
        }
    ]
}

EVENT_CATEGORIES = {
    "feature_launch": {
        "description": "New product features, capabilities, tools, or major functionality additions",
        "keywords": ["launch", "release", "new feature","introducing", "announcing"],
        "examples": ["AI-powered analytics dashboard", "Mobile app update", "API v2.0 release"]
    },
    "pricing_change": {
        "description": "Pricing updates, new tiers, packaging changes, or promotional offers",
        "keywords": ["pricing", "price", "tier", "plan", "cost", "free trial"],
        "examples": ["20% discount", "Enterprise plan now available", "Free tier expansion"]
    },
    "partnership": {
        "description": "Collaborations, integrations, acquistions, or strategic alliances",
        "keywords": ["partnership", "integration", "acquisition", "collaboration", "joins forces"],
        "examples": ["Slack integration", "Acquired by BigCorp", "Partnership with Microsoft"]
    },
    "other": {
        "description": "General announcements, blog posts, events, hiring, or non-strategic updates",
        "keywords": [],
        "examples": ["Company culture post", "Industry trends article", "Conference attendance"]
    }
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36", # Chrome on Windows
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36", # Chrome on macOS
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0", # Edge on Windows
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0", # Edge on macOS
    # "Mozilla/5.0 (compatible; ScoutBot/1.0; +https://psp-labs.com)", # Scout Bot (fallback identifier)
]

def get_random_user_agent() -> str:
    """
    Return a random user agent to rotate requests.
    """
    return random.choice(USER_AGENTS)

SCRAPE_CONFIG = {
    "timeout" : 10,
    "max_retries": 3,
    "user_agent" : get_random_user_agent(),
    "rate_limit_delay": 1.0,
    "min_content_length": 100
}

LLM_CONFIG = {
    "model": "gpt-4o-mini",
    "temperature": 0,
    "max_tokens": 500,
    "batch_size": 5,
    "confidence_threshold": 0.1
}

def get_all_competitors() -> List[str]:
    """
    Return flat list of all competitor names across all sets.
    """
    competitors = []
    for set_name, competitors_list in COMPETITOR_SETS.items():
        competitors.extend([c["name"] for c in competitors_list])
    return competitors

def get_set_names() -> List[str]:
    """
    Return list of available competitor set names.
    """
    return list(COMPETITOR_SETS.keys())

def load_competitors_to_db():
    """
    Populate database with configured conpetitors and sources.
    Safe to run multiple times (idempotent due to UNIQUE constraints).
    """
    from core.database import db
    
    for set_name, competitors in COMPETITOR_SETS.items():
        for competitor in competitors:
            competitor_id = db.add_competitor(competitor["name"], set_name)
            for source in competitor["sources"]:
                db.add_source(competitor_id, source["url"], source["type"])

        print(f"✅ Loaded {len(get_all_competitors())} competitors into database")

if __name__ == "__main__":
    load_competitors_to_db()