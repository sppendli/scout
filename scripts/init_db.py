"""
One-time database initialization script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import load_competitors_to_db
from core.database import db

if __name__ == "__main__":
    print("🚀 Initializing Scout database...")
    print(f"✅ Schema created at {db.db_path}")

    load_competitors_to_db()

    from core.config import get_set_names
    for set_name in get_set_names():
        competitors = db.get_competitors_by_set(set_name)
        print(f"\n📊 {set_name}: {len(competitors)} competitors")
        for comp in competitors:
            sources = db.get_sources_by_competitor(comp["id"])
            print(f"    - {comp['name']}: {len(sources)} sources")

    print("\n ✅ Database initialization complete!")