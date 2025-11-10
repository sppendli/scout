# 🔍 Scout

**AI-Powered Competitive Intelligence for Moder Product Teams**

> Stop manually tracking competitors. Start getting intelligence briefings.

Scout automates competitive intelligence by scraping competitor sources, extracting strategic events with LLM classification, and delivering executive-ready briefings.

🌐 [**Launch the Demo**](https://psplabs-scout.streamlit.app/)

## 💡 What is Scout?

Executives and product teams waste hours tracking competitors across fragmented sources—blogs, changelogs, press releases, pricing pages. Scout solves this by:

1. **🔄 Automated Scraping**: Monitors pre-configured competitor sources (RSS feeds, HTML blogs)
2. **🤖 AI Classification**: Uses GPT-4o-mini to extract strategic events (feature launches, pricing changes, partnerships)
3. **📊 Intelligence Dashboard**: Displays trends, timelines, and impact-ranked events in a single view
4. **📄 One-Click Briefings**: Generates professional HTML reports for executive distribution

### Key Features

- **3 Pre-Configured Competitor Sets**: SaaS Analytics, Design Tools, Project Management
- **Smart Deduplication**: SHA-256 content hashing prevents duplicate articles
- **Confidence Scoring**: LLM assigns 0.0-1.0 confidence to every classification
- **Impact Levels**: High/Medium/Low prioritization for strategic decision-making
- **Export-Ready Reports**: HTML briefings with embedded charts (print to PDF)


## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────┐
│                  Streamlit Dashboard                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Metrics    │  │  Timeline    │  │  Export Briefing │  │
│  │  Cards      │  │  Visualizer  │  │  Generator       │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└───────────────────────┬───────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────┐              ┌─────────────────┐
│    Scraper    │              │   Classifier    │
│               │              │                 │
│ • RSS Feeds   │              │ • GPT-4o-mini   │
│ • HTML Blogs  │───────┐      │ • JSON Schema   │
│ • Rate Limit  │       │      │ • Caching       │
└───────────────┘       │      └─────────────────┘
                        ▼
                ┌────────────────┐
                │  SQLite DB     │
                │                │
                │ • Competitors  │
                │ • Sources      │
                │ • Articles     │
                │ • Events       │
                └────────────────┘
```

## 🛠️ Technology Stack
<table border="0">
<tr>
<td align="center">
<img src="assets/python-original.svg"width="40"/><br>Python</td>
<td align="center"><img src="assets/sqlite-original.svg" width="40"/><br>SQLite</td>
<td align="center"><img src="assets/openai.svg" width="40"/><br>OpenAI</td>
<td align="center"><img src="assets/plotly-original.svg" width="40"/><br>Plotly</td>
<td align="center"><img src="assets/streamlit-original.svg" width="40"/><br>Streamlit</td> 
</tr>
<table>

## 📂 Repository Structure

```
scout/
├── core/                   # Core business logic
│   ├── config.py           # Static competitor configurations
│   ├── database.py         # SQLite CRUD operations
│   ├── scraper.py          # Multi-source web scraping
│   ├── classifier.py       # LLM-based event extraction
│   └── export.py           # HTML briefing generation
├── scripts/                
│   └──init_db.py              # Database initialization script
├── data/                   # Database and cache
│   └── scout.db            # SQLite database (auto-generated)
├── main.py                 # Streamlit application entry point
├── requirements.txt        # Python dependencies
├── .env                    # Environment variable template
├── README.md               # This file
└── LICENSE                 # License
```

## 🎯 Usage Guide

### 1. Select a Competitor Set

Choose from three pre-configured industry verticals:
- **SaaS Analytics**: Mixpanel, Amplitude, Heap, Twilio, Pendo
- **Design Tools**: Figma, Sketch, Framer, Canva, Adobe XD
- **Project Management**: Asana, Monday.com, ClickUp, Notion, Airtable, Trello

### 2. Run Data Collection

**Option A: Full Refresh** (Recommended for first run)
- Click **⚡ Full Refresh** in the sidebar
- Scrapes all sources and classifies new articles (30-60 seconds)

**Option B: Incremental Updates**
- **🔡 Scrape**: Collect new articles only
- **🤖 Classify**: Process unclassified articles with AI

### 3. Explore Intelligence

The dashboard displays:
- **Key Metrics**: Total events, feature launches, pricing changes, partnerships
- **Category Breakdown**: Pie chart of event distribution
- **Impact Distribution**: Bar chart of high/medium/low priority events
- **Event Timeline**: Chronological feed with confidence scores and source links

### 4. Generate Reports

1. Select report period (7/14/30/90 days)
2. Toggle chart inclusion
3. Click **📥 Generate Report**
4. Download HTML file
5. Open in browser and use **Print → Save as PDF**

## 🤖 AI Classification System

### Event Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `feature_launch` | New products, capabilities, tools | "AI-powered analytics dashboard", "Mobile app v2.0" |
| `pricing_change` | Pricing updates, new tiers | "20% discount for annual plans", "Enterprise tier launch" |
| `partnership` | Integrations, acquisitions, collaborations | "Slack integration", "Acquired by BigCorp" |
| `other` | General announcements, blog posts | "Company culture post", "Conference attendance" |

### Classification Workflow

```
Article → LLM Prompt → Structured JSON Response
                           ↓
                    Confidence ≥ 0.5?
                    /              \
                 Yes               No
                  ↓                 ↓
          Save to Events DB    Discard as "other"
```

**Prompt Engineering Highlights**:
- Zero-temperature for deterministic results
- Strict JSON schema validation
- Few-shot examples for edge cases
- Confidence scoring on 0.0-1.0 scale
- Entity extraction (products, features, partners)

### Confidence Thresholds

- **0.9-1.0**: Explicit announcement with clear details
- **0.7-0.9**: Strong indicators but some ambiguity
- **0.5-0.7**: Indirect mentions or implications
- **<0.5**: Uncertain or irrelevant (filtered out)

## 🚧 Demo Limitations

This demo is intended to showcase the core capabilities of the competitive intelligence framework  and is **not a full-fledged platform**. To ensure clarity and focus, the current limitations include:

| Limitation | Reason |
|-----------|--------|
| **No real-time monitoring** | Requires background workers |
| **Manual refresh only** | Simplifies demo flow |
| **Pre-configured competitors** | Hardcoded in config.py |
| **No sentiment analysis** | Scope reduction for timeline |
| **Single-user database** | SQLite concurrency limits | 
| **Browser print-to-PDF** | Fastest export path |