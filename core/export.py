"""
HTML/PDF export functionality for Market Intelligence Briefings.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import base64
import plotly.graph_objects as go
import plotly.express as px

from core.database import db

class ScoutExporter:
    """
    Generate HTML briefings for Market Intelligence Reports.
    """

    def __init__(self):
        pass

    def _get_css(self) -> str:
        """Return CSS styling for the report."""
        return """
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                line-height: 1.6;
                color: #333;
                background: #f8f9fa;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-radius: 10px;
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .header .subtitle {
                font-size: 1.2em;
                opacity: 0.9;
            }
            
            .header .meta {
                margin-top: 20px;
                font-size: 0.9em;
                opacity: 0.8;
            }
            
            .content {
                padding: 40px;
            }
            
            .section {
                margin-bottom: 40px;
            }
            
            .section-title {
                font-size: 1.8em;
                color: #667eea;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 3px solid #667eea;
            }
            
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .metric-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 10px;
                text-align: center;
            }
            
            .metric-value {
                font-size: 2.5em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            
            .metric-label {
                font-size: 1em;
                opacity: 0.9;
            }
            
            .event-card {
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 5px;
                page-break-inside: avoid;
            }
            
            .event-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 10px;
            }
            
            .event-title {
                font-size: 1.2em;
                font-weight: 600;
                color: #333;
            }
            
            .event-meta {
                display: flex;
                gap: 15px;
                font-size: 0.85em;
                color: #666;
                margin-bottom: 10px;
            }
            
            .event-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.8em;
                font-weight: 600;
            }
            
            .badge-high {
                background: #ff6b6b;
                color: white;
            }
            
            .badge-medium {
                background: #feca57;
                color: #333;
            }
            
            .badge-low {
                background: #48dbfb;
                color: white;
            }
            
            .category-feature {
                background: #a29bfe;
                color: white;
            }
            
            .category-pricing {
                background: #fdcb6e;
                color: #333;
            }
            
            .category-partnership {
                background: #6c5ce7;
                color: white;
            }
            
            .event-summary {
                margin: 15px 0;
                color: #555;
                line-height: 1.7;
            }
            
            .event-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 15px;
                padding-top: 15px;
                border-top: 1px solid #ddd;
            }
            
            .confidence-bar {
                flex-grow: 1;
                max-width: 200px;
                height: 8px;
                background: #e0e0e0;
                border-radius: 10px;
                overflow: hidden;
                margin-right: 15px;
            }
            
            .confidence-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                border-radius: 10px;
            }
            
            .source-link {
                color: #667eea;
                text-decoration: none;
                font-size: 0.9em;
            }
            
            .source-link:hover {
                text-decoration: underline;
            }
            
            .chart-container {
                margin: 30px 0;
                text-align: center;
            }
            
            .footer {
                background: #f8f9fa;
                padding: 30px 40px;
                text-align: center;
                border-top: 1px solid #ddd;
            }
            
            .footer-logo {
                font-size: 1.5em;
                font-weight: 700;
                color: #667eea;
                margin-bottom: 10px;
            }
            
            .footer-text {
                color: #666;
                font-size: 0.9em;
            }
            
            @media print {
                body {
                    background: white;
                    padding: 0;
                }
                
                .container {
                    box-shadow: none;
                    max-width: 100%;
                }
                
                .source-link {
                    color: #667eea;
                    text-decoration: underline;
                }
                
                .event-card {
                    page-break-inside: avoid;
                }
            }
        </style>
        """

    def _format_date(self, date_str: Optional[str]) -> str:
        """
        Format date string for display.
        """
        if not date_str:
            return "Unknown"
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%B %d, %Y')
        except:
            return date_str[:10] if len(date_str) >= 10 else date_str

    def _get_category_emoji(self, category: str) -> str:
        """
        Get emoji for category.
        """
        emojis = {
            "feature_launch": "🚀",
            "pricing_change": "💰",
            "partnership": "🤝",
            "other": "📰"
        }
        return emojis.get(category, "📌")

    def _get_impact_emoji(self, impact: str) -> str:
        """
        Get emoji for impact level.
        """
        emojis = {
            "high": "🔥",
            "medium": "⚡",
            "low": "💡"
        }
        return emojis.get(impact, "📌")

    def _generate_category_chart(self, stats: Dict) -> str:
        """
        Generate embedded category breakdown chart as base64 image.
        """
        if not stats.get('by_category'):
            return ""
        
        fig = px.pie(
            values=list(stats['by_category'].values()),
            names=[k.replace('_', ' ').title() for k in stats['by_category'].keys()],
            color_discrete_sequence=px.colors.sequential.Purples_r,
            title="Event Categories"
        )

        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            height=400,
            showlegend=True,
            title_font_size=20,
            title_x=0.5
        )

        img_bytes = fig.to_image(format="png", width=800, height=400)
        img_base64 = base64.b64encode(img_bytes).decode()
        
        return f'<img src="data:image/png;base64,{img_base64}" style="max-width: 100%; height: auto;" />'

    def _generate_impact_chart(self, events: List[Dict]) -> str:
        """
        Generate embedded impact distribution chart as base64 image.
        """
        if not events:
            return ""
        
        impact_counts = {"high": 0, "medium": 0, "low": 0}
        for event in events:
            level = event.get('impact_level', 'medium')
            impact_counts[level] = impact_counts.get(level, 0) + 1

        fig = go.Figure(data=[
            go.Bar(
                x=list(impact_counts.keys()),
                y=list(impact_counts.values()),
                marker_color=['#ff6b6b', '#feca57', '#48dbfb'],
                text=list(impact_counts.values()),
                textposition='auto'
            )
        ])

        fig.update_layout(
            title="Impact Distribution",
            height=350,
            showlegend=False,
            title_font_size=20,
            title_x=0.5,
            xaxis_title="Impact Level",
            yaxis_title="Count"
        )

        img_bytes = fig.to_image(format="png", width=600, height=350)
        img_base64 = base64.b64encode(img_bytes).decode()

        return f'<img src="data:image/png;base64,{img_base64}" style="max-width: 100%; height: auto;" />'

    def generate_briefing(self, set_name: str, days: int = 7, include_charts: bool = True):
        """
        Generate HTML briefing for a competitor set.
        """
        events = db.get_events_by_set(set_name, limit=100)
        stats = db.get_event_stats_by_set(set_name)

        events.sort(
            key = lambda x: x.get('publish_date') or x.get('created_at', ''),
            reverse=True
        )

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='en'>",

            "<head>",
            "   <meta charset='UTF-8'>",
            "   <meta name='viewport content='width=device-width, initial-scale=1.0'>",
            f"   <title>Scout Intelligence Briefing - {set_name}</title>",
            self._get_css(),
            "</head>",

            "<body>",
            "   <div class='container'>",

            "       <div class='header'>",
            "           <h1>🔍 Scout Intelligence Briefing</h1>",
            f"           <div class='subtitle>{set_name}</div>",
            "           <div class='meta'>",
            f"               Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>",
            f"               Report Period: Last {days} days | {len(events)} Events",
            "           </div>",
            "       </div>",
            
            "       <div class='content'>",
            "           <div class='section'>",
            "               <h2 class='section-title'>📊 Key Metrics</h2>",
            "                   <div class=''metric-card'>",
            f"                       <div class='metric-value'>{stats['total_events']}</div>",
            f"                       <div class='metric-label>Total Events</div>"
            "                   </div>",
            "               <div class='metrics-grid'>",
            "                   <div class=''metric-card'>",
            f"                       <div class='metric-value'>{stats['by_category'].get('feature_launch', 0)}</div>",
            f"                       <div class='metric-label>Feature Launches</div>"
            "                   </div>",
            "                   <div class=''metric-card'>",
            f"                       <div class='metric-value'>{stats['by_category'].get('pricing_change', 0)}</div>",
            f"                       <div class='metric-label>Pricing Changes</div>"
            "                   </div>",
            "                   <div class=''metric-card'>",
            f"                       <div class='metric-value'>{stats['by_category'].get('partnership', 0)}</div>",
            f"                       <div class='metric-label>Partnerships</div>"
            "                   </div>",
            "               </div>",
            "           </div>",
        ]

        if include_charts and events:
            html_parts.extend([
                "           <div class='section'>",
                "               <h2 class='section-title'>📈 Analytics</h2>",
                "               <div class='chart-container'>",
                self._generate_category_chart(stats),
                "               </div>",
                "               <div class='chart-container>",
                self._generate_impact_chart(events),
                "               </div>",
                "           </div>"
            ])
        
        html_parts.extend([
            "           <div class='section'>",
            "               <h2 class='section-title'>📅 Event Timeline</h2>",
        ])

        if not events:
            html_parts.append("                <p>No events found for the specified period.</p>")
        else:
            for event in events:
                category_badge_class = f"category-{event['category'].replace('_', '-')}"
                impact_badge_class = f"badge-{event['impact_level']}"

                html_parts.extend([
                    "               <div class='event-card'>",
                    "                   <div class='event-header'>",
                    "                       <div class='event-title'>",
                    f"                          {self._get_category_emoji(event['category'])} {event['competitor_name']}: {event['title'][:80]}",
                    "                       </div>",
                    f"                       <span class='event-badge {impact_badge_class}'>{self._get_impact_emoji(event['impact_level'])} {event['impact_level'].upper()}</span>",
                    "                   </div>",
                    "                   <div class='event-meta'>",
                    f"                       <span class='event-badge {category_badge_class}'>{event['category'].replace('_', '-').title()}</span>",
                    f"                       <span>📅 {self._format_date(event.get('publish_date'))}</span>",
                    "                   </div>",
                    "                   <div class='event-summary'>",
                    f"                       {event['summary']}",
                    "                   </div>",
                    "                   <div class='event-footer>",
                    "                       <div style='display: flex; align-items: center; flex-grow:1;'>",
                    "                           <div class='confidence-bar'>",
                    f"                               <div class='confidence-fill' style='width: {event['confidence']*100}%'></div>",
                    "                           </div>",
                    f"                           <span style='font-size: 0.85 em; color: #666;'>Confidence: {event['confidence']:.0%}</span>",
                    "                       </div>",
                    f"                       <a href='{event['url']}' class='source-link' target='_blank'>View Source -></a>"
                    "                   </div>",
                    "               </div>",
                ])
        
        html_parts.extend([
            "           </div>"
            "       </div>",

            "       <div class='footer'>",
            "           <div class='footer-logo'>🔍 Scout Market Intelligence</div>",
            "           <div class='footer-text'>",
            "               Competitive Intelligence Platform | Powered by AI<br>",
            f"               Report generated {datetime.now().strftime('%B %d, %Y')} | <a href='https://labs.pspverse.com' style='color: #667eea;'>psp-labs.com</a>",
            "           </div'>",
            "       </div>",

            "   </div>",
            "</body>",
            "</html>"
        ])

        return "\n".join(html_parts)
    
exporter = ScoutExporter()