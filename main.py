"""
Scout - Market Intelligence Dashboard
Entry point for Streamlit application.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json

from core.config import get_set_names
from core.scraper import scraper
from core.classifier import classifier
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

    st.subheader("Data Refresh")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📡 Scrape", use_container_width=True):
            with st.spinner(f"Scraping {selected_set}..."):
                results = scraper.scrape_competitor_set(selected_set)
                st.success(f"✅ Found {results['new_articles']} new articles")
                with st.expander("Details"):
                    st.json(results)

    with col2:
        if st.button("🤖 Classify", use_container_width=True):
            with st.spinner("Running AI classification..."):
                results = classifier.classify_competitor_set(selected_set)
                st.success(f"✅ {results.get('classified', 0)} events")
                with st.expander("Details"):
                    st.json(results)

    st.divider()

    if st.button("⚡Full Refresh", type="primary", use_container_width=True):
        with st.spinner("Running full refresh..."):
            scrape_results = scraper.scrape_competitor_set(selected_set)
            st.info(f"📡 Scraped: {scrape_results['new_articles']} articles")

            if scrape_results['new_articles'] > 0:
                classify_results = classifier.classify_competitor_set(selected_set)
                st.success(f"✅ ClassifiedL {classify_results.get('classified', 0)} events")

    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

st.header(f"📊 {selected_set} Intelligence")

events = db.get_events_by_set(selected_set, limit=100)
stats = db.get_event_stats_by_set(selected_set)

if not events:
    st.warning("No intelligence events found. Click 'Full Refresh' to scrape and classify articles.")

    competitors = db.get_competitors_by_set(selected_set)
    total_articles = sum(len(db.get_articles_by_competitor(c['id'], limit=1000)) for c in competitors)
    if total_articles > 0:
        st.info(f"📝 {total_articles} articles in database. Click '🤖 Classify' to extract events.")
    else:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Events", stats['total_events'])
        
        with col2:
            st.metric("Feature Launches", stats['by_category'].get('feature_launch', 0))

        with col3:
            st.metric("Pricing Changes", stats['by_category'].get('pricing_change', 0))
        
        with col4:
            st.metric("Partnerships", stats['by_category'].get('partnership', 0))

        st.divider()

    with st.expander("📋 View All Events (JSON)", expanded=False):
        st.json([dict(e) for e in events])