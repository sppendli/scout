"""
Scout - Market Intelligence Dashboard
Entry point for Streamlit application.
"""

import streamlit as st
from core.config import get_set_names
from core.scraper import scraper
from core.database import db

st.set_page_config(
    page_title="Scout",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Scout")
st.caption("Market Intelligence")

with st.sidebar:
    st.header("Configuration")
    selected_set = st.selectbox(
        "Competitor Set",
        options=get_set_names(),
        index=0
    )

    st.divider()

    if st.button("🔄️ Refresh Data", type="primary", use_container_width=True):
        with st.spinner(f"Scraping {selected_set}..."):
            results = scraper.scrape_competitor_set(selected_set)
            st.success(f"✅ Found {results['new_articles']} new articles")
            st.json(results)

    st.divider()
    st.caption("Last updated: Manual trigger only")

st.header(f"📊 {selected_set} Intelligence")

competitors = db.get_competitors_by_set(selected_set)

if not competitors:
    st.warning("No competitors found. Run initialization script first.")
    st.code("python scripts/init_db.py", language="bash")
else:
    st.subheader("Recent Articles")

    for competitor in competitors:
        with st.expander(f"**{competitor['name']}** ({competitor['id']})", expanded=False):
            articles = db.get_articles_by_competitor(competitor['id'], limit=5)

            if not articles:
                st.info("No articles yet. Click 'Refresh Data' to scrape.")
            else:
                for article in articles:
                    st.markdown(f"**{article['title']}**")
                    st.caption(f"Source: {article['source_url']} | Fetched: {article['fetched_at']}")
                    st.text(article['content'][:200] + "...")
                    st.markdown(f"[Read ful article]({article['url']})")
                    st.divider()