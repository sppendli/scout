"""
HTML/PDF export functionality for Market Intelligence Briefings.
"""

from datetime import datetime, timedelta

from core.database import db

class ScoutExporter:
    """
    Generate HTML briefings for Market Intelligence Reports.
    """

    def __init__(self):
        pass

    def generate_briefing(self, set_name: str, days: int = 7):
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

        #     "       </div>",
        #     "   </div>",
        #     "</body>",
        # ]