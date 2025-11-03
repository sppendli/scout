"""
HTML/PDF export functionality for Market Intelligence Briefings.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta

from core.database import db

class ScoutExporter:
    """
    Generate HTML briefings for Market Intelligence Reports.
    """

    def __init__(self):
        pass

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

    def _generate_category_chart(self):
        """
        Generate embedded category breakdown chart as base64 image.
        """
        pass

    def _generate_impact_chart(self):
        """
        Generate embedded impact distribution chart as base64 image.
        """
        pass

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