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
from core.export import exporter

st.set_page_config(
    page_title="Scout",
    page_icon="🔍",
    layout="wide"
)

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .event-card {
        border-left: 4px solid #667eea;
        padding: 15px;
        margin: 10px 0;
        background: #f8f9fa;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

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
            else:
                st.info("No new articles to classify")

    st.divider()

    st.subheader("📄 Export Briefing")

    export_days = st.selectbox(
        "Report Period",
        options=[7, 14, 30, 90],
        format_func=lambda x: f"Last {x} days",
        index=0
    )

    include_charts = st.checkbox("Include Charts", value=True)

    if st.button("📥 Generate Report", use_container_width=True):
        with st.spinner("Generating briefing..."):
            html_content = exporter.generate_briefing(
                set_name=selected_set,
                days=export_days,
                include_charts=include_charts
            )

            st.download_button(
                label="⬇️ Download HTML",
                data=html_content,
                file_name=f"scout_briefing_{selected_set.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html",
                use_container_width=True
            )

            st.success("✅ Briefing ready for download!")
            st.info("💡 Tip: Open the HTML file and use 'Print to PDF' in your browser")
    
    st.divider()
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

st.header(f"📊 {selected_set} Intelligence")

events = db.get_events_by_set(selected_set, limit=100)
stats = db.get_event_stats_by_set(selected_set)

if not events or len(events) == 0:
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

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Event Timeline")

        timeline_data = []
        for event in events[:30]:
            timeline_data.append({
                "date": (event.get("publish_date") or event.get("created_at") or str(datetime.now()))[:10],
                "competitor": event['competitor_name'],
                "category": event['category'].replace('_', ' ').title(),
                "summary": event['summary'][:100] + '...',
                "confidence": event['confidence'],
                "impact": event['impact_level']
            })

        for item in timeline_data:
            impact_emoji = {"high": "🔥", "medium": "⚡", "low":"💡"}
            category_emoji = {
                "Feature Launch": "🚀",
                "Pricing Change": "💰",
                "Partnership": "🤝",
                "Other": "📰"
            }

            with st.expander(
                f"{impact_emoji.get(item['impact'], '📌')} {category_emoji.get(item['category'], '📰')} "
                f"**{item['competitor']}** - {item['summary'][:60]}...",
                expanded=False
            ):
                st.markdown(f"**Category**: {item['category']}")
                st.markdown(f"**Date**: {item['date']}")
                st.markdown(f"**Impact**: {item['impact'].capitalize()}")
                st.markdown(f"**Confidence**: {item['confidence']:.0%}")
                st.markdown(f"**Summary**: {item['summary']}")

    with col2:
        st.subheader("Category Breakdown")

        if stats['by_category']:
            fig = px.pie(
                values=list(stats['by_category'].values()),
                names=[k.replace('_', ' ').title() for k in stats['by_category'].keys()],
                color_discrete_sequence=px.colors.sequential.Purples_r
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Impact Distribution")
        impact_counts = {}
        for event in events:
            level = event['impact_level']
            impact_counts['level'] = impact_counts.get(level, 0) + 1

        if impact_counts:
            fig = go.Figure(data=[
                go.Bar(
                    x=list(impact_counts.keys()),
                    y=list(impact_counts.values()),
                    marker_color=['#ff6b6b', '#feca57', '#48dbfb']
                )
            ])
            fig.update_layout(
                showlegend=False,
                height=250,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

st.divider()

with st.expander("📋 View All Events (JSON)", expanded=False):
    st.json([dict(e) for e in events])