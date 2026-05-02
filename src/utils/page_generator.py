"""Generates static HTML pages from live project data."""
import os
import re
import warnings
import json as _json_mod
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import yfinance as yf

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
PAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "pages")


def _save_scores_cache(scores: dict):
    """Save ticker->conviction_score dict to pages/data/scores_cache.json."""
    cache_dir = os.path.join(PAGES_DIR, "data")
    os.makedirs(cache_dir, exist_ok=True)
    payload = {"generated_at": datetime.now(tz=TAIPEI_TZ).isoformat(), "scores": scores}
    with open(os.path.join(cache_dir, "scores_cache.json"), "w") as f:
        _json_mod.dump(payload, f)


def _load_scores_cache(max_age_hours: int = 12) -> dict:
    """Load cached scores. Returns {} if missing or older than max_age_hours."""
    path = os.path.join(PAGES_DIR, "data", "scores_cache.json")
    try:
        with open(path) as f:
            data = _json_mod.load(f)
        age = (datetime.now(tz=TAIPEI_TZ) - datetime.fromisoformat(data["generated_at"])).total_seconds() / 3600
        return data["scores"] if age < max_age_hours else {}
    except Exception:
        return {}

REGION_META = {
    "US":     {"label": "United States",    "label_zh": "美國",         "flag": "🇺🇸"},
    "GLOBAL": {"label": "Global / Multi",   "label_zh": "全球／綜合",   "flag": "🌐"},
    "UK":     {"label": "UK & Europe",      "label_zh": "英國及歐洲",   "flag": "🇬🇧"},
    "SG":     {"label": "Singapore",        "label_zh": "新加坡",       "flag": "🇸🇬"},
    "HK":     {"label": "Hong Kong",        "label_zh": "香港",         "flag": "🇭🇰"},
    "ASIA":   {"label": "Asia-Pacific",     "label_zh": "亞太地區",     "flag": "🌏"},
    "TW":     {"label": "Taiwan",           "label_zh": "台灣",         "flag": "🇹🇼"},
}

REGION_COLORS = {
    "US":     {"color": "#3a72b0", "light": "#eaf2fb", "border": "#b8d4f0"},
    "GLOBAL": {"color": "#2e6b58", "light": "#eaf3f0", "border": "#c6ddd6"},
    "UK":     {"color": "#b87820", "light": "#fdf4e7", "border": "#e8c88a"},
    "SG":     {"color": "#5560a8", "light": "#f0f0fc", "border": "#c0c4ec"},
    "HK":     {"color": "#b84040", "light": "#fceaea", "border": "#e8aaaa"},
    "ASIA":   {"color": "#2a7a7a", "light": "#e8f5f5", "border": "#a8d8d8"},
    "TW":     {"color": "#7a5030", "light": "#f8f0e8", "border": "#d8bca0"},
}

REGION_ORDER = ["US", "GLOBAL", "UK", "ASIA", "SG", "HK", "TW"]

SHARED_CSS = """
:root {
  --bg:           #f2f5f1;
  --surface:      #ffffff;
  --surface-off:  #f8faf8;
  --border:       #d6dfd8;
  --border-light: #e8efea;
  --text:         #1a2820;
  --text-med:     #3d5449;
  --text-muted:   #6e8a7a;
  --accent:       #2e6b58;
  --accent-light: #c6ddd6;
  --accent-bg:    #eaf3f0;
  --shadow-sm:    0 1px 4px rgba(20,50,35,0.07);
  --shadow:       0 3px 12px rgba(20,50,35,0.09);
  --radius:       10px;
  --radius-sm:    6px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.7;
}
nav {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 0 40px; display: flex; align-items: center;
  justify-content: space-between; height: 56px;
  position: sticky; top: 0; z-index: 10; box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.nav-brand { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.nav-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }
.nav-name { font-size: 13px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text); }
.nav-links { display: flex; gap: 4px; list-style: none; flex-shrink: 1; min-width: 0; }
.nav-links a {
  font-size: 12px; color: var(--text-muted); text-decoration: none;
  padding: 5px 10px; border-radius: 20px; transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.nav-links a:hover { background: var(--accent-bg); color: var(--accent); }
.nav-links a.active { background: var(--accent-bg); color: var(--accent); font-weight: 600; }
.hero { max-width: 960px; margin: 0 auto; padding: 52px 48px 36px; border-bottom: 1px solid var(--border); }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--accent); background: var(--accent-bg); border: 1px solid var(--accent-light);
  padding: 4px 12px; border-radius: 20px; margin-bottom: 18px;
}
.pill::before { content: '●'; font-size: 8px; }
.hero h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2; margin-bottom: 10px; }
.hero-sub { font-size: 14px; color: var(--text-muted); max-width: 600px; line-height: 1.6; }
.content { max-width: 960px; margin: 0 auto; padding: 40px 48px 80px; }
footer {
  border-top: 1px solid var(--border); padding: 24px 48px;
  text-align: center; font-size: 12px; color: var(--text-muted); background: var(--surface);
}
.mk-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.mk-table tbody tr:hover { background: var(--bg); }
.news-title { word-break: break-word; }
@media (max-width: 620px) {
  nav, .hero, .content, footer { padding-left: 16px; padding-right: 16px; }
  .hero { padding: 32px 20px 24px; }
  .content { padding: 0 16px 60px; }
  .hero h1 { font-size: 22px; }
  .nav-links { display: none; }
  body { font-size: 14px; }
}
"""


_NAV_ITEMS = [
    ("market.html",              "Market"),
    ("top-picks.html",           "Top Picks"),
    ("sector-leaders.html",      "Sector Leaders"),
    ("earnings-calendar.html",   "Earnings Calendar"),
    ("news-sources.html",        "News Sources"),
]


def _nav_html(active: str = "") -> str:
    """Return the shared <nav> block. `active` is the filename of the current page."""
    links = ""
    for href, label in _NAV_ITEMS:
        cls = ' class="active"' if href == active else ""
        links += f'<li><a href="{href}"{cls}>{label}</a></li>\n    '
    return f"""<nav>
  <a href="index.html" class="nav-brand" style="text-decoration:none;">
    <div class="nav-dot"></div>
    <span class="nav-name">The Signal Desk</span>
  </a>
  <ul class="nav-links">
    {links.strip()}
  </ul>
</nav>"""


def _append_score_history(scores: dict):
    """Append today's scores to pages/data/scores_history.json. Keep last 90 days."""
    from datetime import date as _date
    path = os.path.join(PAGES_DIR, "data", "scores_history.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    today = str(_date.today())
    try:
        with open(path) as f:
            history = _json_mod.load(f)
    except Exception:
        history = {}
    cutoff = str(_date.today() - timedelta(days=90))
    for ticker, score in scores.items():
        entries = history.get(ticker, [])
        entries = [e for e in entries if e["date"] >= cutoff]
        if not entries or entries[-1]["date"] != today:
            entries.append({"date": today, "score": score if isinstance(score, int) else score.get("score", 0)})
        history[ticker] = entries
    with open(path, "w") as f:
        _json_mod.dump(history, f)


def _sparkline_svg(points: list, width=60, height=20) -> str:
    """Render a tiny SVG sparkline from a list of score values (0-100)."""
    if len(points) < 2:
        return '<span style="color:var(--text-muted);font-size:11px">—</span>'
    mn, mx = min(points), max(points)
    rng = mx - mn or 1
    step = width / (len(points) - 1)
    coords = " ".join(
        f"{i*step:.1f},{height - (v-mn)/rng*(height-2)-1:.1f}"
        for i, v in enumerate(points)
    )
    color = "#2e6b58" if points[-1] >= points[0] else "#b84040"
    delta = points[-1] - points[0]
    delta_str = f'<span style="font-size:10px;color:{color};font-weight:700">{delta:+.0f}</span>'
    svg = f'<svg width="{width}" height="{height}" style="vertical-align:middle"><polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'
    return svg + " " + delta_str


def generate_news_sources_page(feeds: list) -> None:
    """Write pages/news-sources.html from the current NEWS_FEEDS list."""
    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    # Group by region, preserving REGION_ORDER
    grouped = {r: [] for r in REGION_ORDER}
    for f in feeds:
        r = f.get("region", "GLOBAL")
        if r not in grouped:
            grouped[r] = []
        grouped[r].append(f)

    # Build region sections HTML
    sections_html = ""
    total = len(feeds)

    for region in REGION_ORDER:
        sources = grouped.get(region, [])
        if not sources:
            continue
        meta = REGION_META.get(region, {"label": region, "label_zh": region, "flag": "📰"})

        rows = ""
        for s in sources:
            lang_label = "繁體中文" if s.get("lang") == "zh-TW" else "English"
            lang_color = "color:#3d5449;" if s.get("lang") == "zh-TW" else "color:var(--text-muted);"
            rows += f"""
            <tr>
              <td class="src-name">{s['name']}</td>
              <td class="src-lang" style="{lang_color}">{lang_label}</td>
            </tr>"""

        rc = REGION_COLORS.get(region, {"color": "#2e6b58", "light": "#eaf3f0", "border": "#c6ddd6"})
        sections_html += f"""
  <div class="region-card" style="border-top:4px solid {rc['color']};">
    <div class="region-head" style="background:linear-gradient(135deg,{rc['light']} 0%,var(--surface) 65%);">
      <span class="region-flag">{meta['flag']}</span>
      <div class="region-title-block">
        <span class="region-title" style="color:{rc['color']}">{meta['label']}</span>
        <span class="region-zh">{meta['label_zh']}</span>
      </div>
      <span class="region-count" style="color:{rc['color']};background:{rc['light']};border-color:{rc['border']}">{len(sources)} source{"s" if len(sources) != 1 else ""}</span>
    </div>
    <table class="src-table">
      <thead>
        <tr style="background:linear-gradient(135deg,{rc['light']} 0%,var(--surface-off) 65%); border-bottom:1px solid {rc['border']};">
          <th style="color:{rc['color']}">Source</th>
          <th style="color:{rc['color']}">Language</th>
          <th style="color:{rc['color']}">Feed</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>News Sources · The Signal Desk</title>
<style>
{SHARED_CSS}

.stats-row {{
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 36px;
}}
.stat-tile {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px 22px;
  box-shadow: var(--shadow-sm);
  min-width: 130px;
}}
.stat-val {{
  font-size: 26px;
  font-weight: 800;
  color: var(--accent);
  font-family: 'Menlo', 'SF Mono', monospace;
  line-height: 1.1;
}}
.stat-label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-top: 4px;
}}

.region-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 20px;
}}
.region-head {{
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(135deg, var(--surface) 0%, var(--surface-off) 100%);
}}
.region-flag {{ font-size: 20px; line-height: 1; }}
.region-title-block {{ flex: 1; }}
.region-title {{
  font-size: 14px; font-weight: 700; color: var(--text); display: block;
}}
.region-zh {{
  font-size: 11px; color: var(--text-muted); display: block; margin-top: 1px;
}}
.region-count {{
  font-size: 11px; font-weight: 600; color: var(--accent);
  background: var(--accent-bg); border: 1px solid var(--accent-light);
  padding: 2px 10px; border-radius: 20px;
}}

.src-table {{ width: 100%; border-collapse: collapse; }}
.src-table thead tr {{ background: var(--surface-off); border-bottom: 1px solid var(--border-light); }}
.src-table th {{
  padding: 9px 20px; font-size: 10px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--text-muted); text-align: left;
}}
.src-table td {{
  padding: 11px 20px;
  border-bottom: 1px solid var(--border-light);
  font-size: 13px;
}}
.src-table tr:last-child td {{ border-bottom: none; }}
.src-table tbody tr:hover {{ background: var(--accent-bg); }}
.src-name {{ font-weight: 500; color: var(--text); }}
.src-lang {{ font-size: 12px; }}
.src-link a {{
  font-size: 11px; color: var(--accent); text-decoration: none;
  font-weight: 600; letter-spacing: 0.04em;
}}
.src-link a:hover {{ text-decoration: underline; }}

.note {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 16px 20px;
  font-size: 13px; color: var(--text-muted); margin-top: 28px;
  line-height: 1.6;
}}
</style>
</head>
<body>

{_nav_html("news-sources.html")}

<div class="hero">
  <div class="pill">Live Data · 即時資料 · Auto-updated</div>
  <h1>News Sources &nbsp;<span style="font-size:16px;font-weight:400;color:var(--text-muted)">新聞來源</span></h1>
  <p class="hero-sub">Every briefing draws from {total} RSS feeds across {len([r for r in REGION_ORDER if grouped.get(r)])} regions. Automatically regenerated whenever a new source is added.<br><span style="font-size:13px;color:var(--text-muted)">每份簡報從 {total} 個 RSS 來源抓取，涵蓋 {len([r for r in REGION_ORDER if grouped.get(r)])} 個地區。新增來源時自動更新。</span></p>
</div>

<div class="content">

  <div class="stats-row">
    <div class="stat-tile">
      <div class="stat-val">{total}</div>
      <div class="stat-label">Total Sources</div>
    </div>
    <div class="stat-tile">
      <div class="stat-val">{len([r for r in REGION_ORDER if grouped.get(r)])}</div>
      <div class="stat-label">Regions Covered</div>
    </div>
    <div class="stat-tile">
      <div class="stat-val">{sum(1 for f in feeds if f.get('lang') == 'en')}</div>
      <div class="stat-label">English Sources</div>
    </div>
    <div class="stat-tile">
      <div class="stat-val">{sum(1 for f in feeds if f.get('lang') == 'zh-TW')}</div>
      <div class="stat-label">Chinese Sources</div>
    </div>
  </div>

{sections_html}

  <div class="note">
    📡 &nbsp;This page is auto-generated from the live source list each time the briefing system starts. Adding a new RSS feed to the system will automatically appear here on the next run. Last updated: {updated}.
  </div>

</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; News Sources &nbsp;·&nbsp; Auto-generated {now.strftime('%Y-%m-%d')}
</footer>

</body>
</html>"""

    os.makedirs(PAGES_DIR, exist_ok=True)
    out_path = os.path.join(PAGES_DIR, "news-sources.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] news-sources.html updated — {total} sources across {len([r for r in REGION_ORDER if grouped.get(r)])} regions")


# ── Monthly overview ──────────────────────────────────────────────────────────

MAJOR_INDICES = [
    {"ticker": "^GSPC",  "name": "S&P 500",     "name_zh": "標普500"},
    {"ticker": "^IXIC",  "name": "Nasdaq",       "name_zh": "那斯達克"},
    {"ticker": "^DJI",   "name": "Dow Jones",    "name_zh": "道瓊工業"},
    {"ticker": "^TWII",  "name": "TWSE",         "name_zh": "台灣加權"},
    {"ticker": "^HSI",   "name": "Hang Seng",    "name_zh": "香港恒生"},
    {"ticker": "DX-Y.NYB","name": "USD Index",   "name_zh": "美元指數"},
    {"ticker": "GC=F",   "name": "Gold",         "name_zh": "黃金"},
    {"ticker": "CL=F",   "name": "WTI Oil",      "name_zh": "WTI原油"},
]


def _fetch_monthly_index_data() -> str:
    """Fetch monthly performance for major indices."""
    now = datetime.now(tz=TAIPEI_TZ)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    lines = []
    for idx in MAJOR_INDICES:
        try:
            t = yf.Ticker(idx["ticker"])
            hist = t.history(start=last_month_start.strftime("%Y-%m-%d"),
                             end=now.strftime("%Y-%m-%d"), interval="1mo")
            if hist.empty or len(hist) < 1:
                continue
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                curr_close = float(hist["Close"].iloc[-1])
            else:
                prev_close = float(hist["Open"].iloc[-1])
                curr_close = float(hist["Close"].iloc[-1])
            change_pct = (curr_close - prev_close) / prev_close * 100
            sign = "+" if change_pct >= 0 else ""
            lines.append(f"  {idx['name']:12s} ({idx['name_zh']:6s}): {sign}{change_pct:.1f}%  (current {curr_close:,.1f})")
        except Exception:
            lines.append(f"  {idx['name']:12s} ({idx['name_zh']:6s}): data unavailable")

    return "\n".join(lines) if lines else "Index data unavailable."


def _render_overview(raw: str) -> str:
    """Convert AI markdown overview text to styled HTML section cards."""
    def esc(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    def inline(s):
        s = esc(s)
        s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<em><strong>\1</strong></em>', s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        return s

    lines = raw.split('\n')
    out = []
    in_section = False
    in_ul = False
    in_table = False
    thead_done = False
    i = 0

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append('</ul>')
            in_ul = False

    def close_table():
        nonlocal in_table, thead_done
        if in_table:
            out.append('</tbody></table></div>')
            in_table = False
            thead_done = False

    def close_section():
        nonlocal in_section
        close_ul()
        close_table()
        if in_section:
            out.append('</div></div>')
            in_section = False

    while i < len(lines):
        stripped = lines[i].strip()

        # H2 → new section card
        if stripped.startswith('## '):
            title_raw = stripped[3:]
            # If >40% Chinese characters, fold into current section instead of new card
            zh_chars = sum(1 for c in title_raw if '一' <= c <= '鿿')
            if zh_chars > max(len(title_raw.strip()), 1) * 0.4 and in_section:
                out.append('<div class="zh-divider" style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.08em;margin:18px 0 10px;padding-top:14px;border-top:1px solid var(--border-light)">繁體中文</div>')
                i += 1
                continue
            close_section()
            title = inline(title_raw)
            su = stripped.upper()
            cls = 'sec-teal'
            if 'PREVIEW' in su or 'OUTLOOK' in su or 'RECENT' in su or 'DEVELOPMENT' in su or '近期' in su or '最新' in su:
                cls = 'sec-blue'
            elif 'INVESTOR' in su or 'CONCLUSION' in su or '結論' in su or '總結' in su:
                cls = 'sec-amber'
            elif 'ANALYST' in su or 'HAPPENED' in su or 'BUSINESS' in su or '業務' in su or '公司概覽' in su or '分析師' in su:
                cls = 'sec-indigo'
            elif 'RISK' in su or '風險' in su:
                cls = 'sec-rose'
            elif 'CATALYST' in su or '催化劑' in su:
                cls = 'sec-teal'
            elif 'WHY OWN' in su or 'INDEX' in su or '超額' in su or '指數' in su:
                cls = 'sec-indigo'
            out.append(
                f'<div class="section-card {cls}">'
                f'<h2 class="section-title">{title}</h2>'
                f'<div class="section-body">'
            )
            in_section = True
            i += 1
            continue

        # H3 → sub-heading
        if stripped.startswith('### '):
            close_ul()
            close_table()
            out.append(f'<h3 class="sub-heading">{inline(stripped[4:])}</h3>')
            i += 1
            continue

        # Skip separator lines (═══, ----, ━━━)
        if re.match(r'^[═=─━\-]{10,}$', stripped):
            i += 1
            continue

        # Impact callout line (📌)
        if stripped.startswith('📌'):
            close_ul()
            close_table()
            out.append(f'<p class="impact-line">{inline(stripped)}</p>')
            i += 1
            continue

        # Numbered item: N. text
        nm = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if nm:
            close_ul()
            close_table()
            j = i + 1
            body = []
            while j < len(lines):
                sub = lines[j].strip()
                if (not sub
                        or re.match(r'^\d+\.', sub)
                        or sub.startswith('##')
                        or sub.startswith('###')
                        or sub.startswith('|')
                        or re.match(r'^[-•*]\s', sub)
                        or re.match(r'^[═=─━\-]{10,}$', sub)):
                    break
                if sub.startswith('📌'):
                    body.append(f'<p class="impact-line">{inline(sub)}</p>')
                else:
                    body.append(f'<p>{inline(sub)}</p>')
                j += 1
            out.append(
                f'<div class="num-item">'
                f'<span class="num-badge">{nm.group(1)}</span>'
                f'<div class="num-body">'
                f'<p class="num-title">{inline(nm.group(2))}</p>'
                f'{"".join(body)}'
                f'</div></div>'
            )
            i = j
            continue

        # Table row
        if stripped.startswith('|'):
            close_ul()
            if not in_table:
                out.append('<div class="table-wrap"><table class="overview-table"><thead>')
                in_table = True
                thead_done = False
            # Separator row (|---|---|)
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                if not thead_done:
                    out.append('</thead><tbody>')
                    thead_done = True
                i += 1
                continue
            cells = [inline(c.strip()) for c in stripped.strip('|').split('|')]
            tag = 'td' if thead_done else 'th'
            out.append(f'<tr>{"".join(f"<{tag}>{c}</{tag}>" for c in cells)}</tr>')
            i += 1
            continue

        # Bullet list
        if re.match(r'^[-•*]\s+', stripped):
            close_table()
            if not in_ul:
                out.append('<ul class="overview-list">')
                in_ul = True
            content = inline(re.sub(r'^[-•*]\s+', '', stripped))
            out.append(f'<li>{content}</li>')
            i += 1
            continue

        # Empty line
        if not stripped:
            close_ul()
            close_table()
            i += 1
            continue

        # Regular paragraph
        close_ul()
        close_table()
        out.append(f'<p>{inline(stripped)}</p>')
        i += 1

    close_section()
    return '\n'.join(out)


def generate_monthly_overview_page(content: str, month_review: str, month_preview: str) -> str:
    """Write pages/monthly-YYYY-MM.html and return the filename."""
    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")
    filename = f"monthly-{now.strftime('%Y-%m')}.html"
    rendered = _render_overview(content)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Overview · {month_preview} · The Signal Desk</title>
<style>
{SHARED_CSS}

.hero-period {{
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 10px;
  letter-spacing: 0.03em;
}}
.meta-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 24px;
}}
.meta-label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}}

/* ── Section color themes ── */
.sec-teal   {{ --sc: #2e6b58; --sc-light: #eaf3f0; --sc-border: #c6ddd6; }}
.sec-blue   {{ --sc: #3a72b0; --sc-light: #eaf2fb; --sc-border: #b8d4f0; }}
.sec-amber  {{ --sc: #b87820; --sc-light: #fdf4e7; --sc-border: #e8c88a; }}
.sec-indigo {{ --sc: #5560a8; --sc-light: #f0f0fc; --sc-border: #c0c4ec; }}
.sec-rose   {{ --sc: #b84040; --sc-light: #fceaea; --sc-border: #e8aaaa; }}

.section-card {{
  border: 1px solid var(--sc-border);
  border-top: 4px solid var(--sc);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
  overflow: hidden;
  background: var(--surface);
}}
.section-title {{
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--sc);
  background: linear-gradient(135deg, var(--sc-light) 0%, var(--surface) 65%);
  padding: 14px 24px;
  margin: 0;
  border-bottom: 1px solid var(--sc-border);
}}
.section-body {{
  padding: 24px 28px;
}}
.sub-heading {{
  font-size: 14px;
  font-weight: 700;
  color: var(--sc);
  margin: 22px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--sc-border);
}}
.sub-heading:first-child {{ margin-top: 0; }}
.section-body p {{
  margin-bottom: 12px;
  color: var(--text-med);
  font-size: 14px;
  line-height: 1.75;
}}
.section-body strong {{ color: var(--text); }}

/* Impact callout */
.impact-line {{
  background: var(--sc-light);
  border-left: 3px solid var(--sc);
  padding: 8px 14px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  margin: 4px 0 10px;
  font-size: 13.5px;
  color: var(--text-med);
  line-height: 1.6;
}}

/* Numbered items */
.num-item {{
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 20px;
}}
.num-badge {{
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--sc);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}}
.num-body {{ flex: 1; }}
.num-title {{
  font-weight: 700;
  color: var(--text);
  margin-bottom: 6px;
  font-size: 14px;
}}
.num-body p {{ margin-bottom: 6px; font-size: 13.5px; }}

/* Bullet lists */
.overview-list {{
  margin: 0 0 14px 0;
  padding-left: 20px;
}}
.overview-list li {{
  margin-bottom: 7px;
  color: var(--text-med);
  font-size: 14px;
  line-height: 1.65;
}}

/* Tables */
.table-wrap {{
  overflow-x: auto;
  margin: 10px 0 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--sc-border);
}}
.overview-table {{
  width: 100%;
  border-collapse: collapse;
}}
.overview-table thead tr {{
  background: linear-gradient(135deg, var(--sc-light) 0%, var(--surface-off) 65%);
  border-bottom: 1px solid var(--sc-border);
}}
.overview-table th {{
  padding: 9px 16px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--sc);
  text-align: left;
  white-space: nowrap;
}}
.overview-table td {{
  padding: 10px 16px;
  font-size: 13.5px;
  color: var(--text-med);
  border-bottom: 1px solid var(--border-light);
}}
.overview-table tr:last-child td {{ border-bottom: none; }}
.overview-table tbody tr:hover {{ background: var(--surface-off); }}
</style>
</head>
<body>

{_nav_html()}

<div class="hero">
  <div class="pill">Monthly Overview · Auto-generated</div>
  <p class="hero-period">{month_preview} Preview &nbsp;·&nbsp; {month_review} Review</p>
  <h1>Market Overview</h1>
  <p class="hero-sub">Monthly review of the past month and preview of what's ahead — key events, index performance, earnings, and directional views. Bilingual: English &amp; 繁體中文.</p>
</div>

<div class="content">
  <div class="meta-row">
    <span class="meta-label">Generated by The Signal Desk · AI-assisted analysis</span>
    <span class="meta-label">Last updated: {updated}</span>
  </div>

  {rendered}
</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Market Overview &nbsp;·&nbsp; {month_preview} Preview · {month_review} Review &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>

</body>
</html>"""

    os.makedirs(PAGES_DIR, exist_ok=True)
    out_path = os.path.join(PAGES_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] {filename} written")
    return filename


# ── Market overview page ──────────────────────────────────────────────────────

MAJOR_INDICES = [
    {"ticker": "^GSPC",  "name": "S&P 500",        "name_zh": "標普500",     "region": "US"},
    {"ticker": "^IXIC",  "name": "Nasdaq 100",      "name_zh": "納斯達克",    "region": "US"},
    {"ticker": "^DJI",   "name": "Dow Jones",       "name_zh": "道瓊工業",    "region": "US"},
    {"ticker": "^RUT",   "name": "Russell 2000",    "name_zh": "羅素2000",    "region": "US"},
    {"ticker": "^TWII",  "name": "TAIEX",           "name_zh": "台灣加權指數", "region": "TW"},
    {"ticker": "^HSI",   "name": "Hang Seng",       "name_zh": "恆生指數",    "region": "HK"},
    {"ticker": "^N225",  "name": "Nikkei 225",      "name_zh": "日經225",     "region": "JP"},
    {"ticker": "^FTSE",  "name": "FTSE 100",        "name_zh": "富時100",     "region": "UK"},
]

COMMODITY_TICKERS = [
    {"ticker": "GC=F",  "name": "Gold",       "name_zh": "黃金",     "unit": "$/oz"},
    {"ticker": "CL=F",  "name": "Crude Oil",  "name_zh": "原油",     "unit": "$/bbl"},
    {"ticker": "BTC-USD","name": "Bitcoin",   "name_zh": "比特幣",   "unit": "USD"},
    {"ticker": "DX-Y.NYB","name": "USD Index","name_zh": "美元指數", "unit": "pts"},
]


def fetch_market_page_data() -> dict:
    """Fetch all data needed for the market page."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import yfinance as yf

    result = {"indices": [], "commodities": [], "vix": None, "treasury_10y": None, "treasury_2y": None, "sectors": []}

    # VIX
    try:
        info = yf.Ticker("^VIX").info
        result["vix"] = info.get("regularMarketPrice") or info.get("previousClose")
    except Exception:
        pass

    # 10Y & 2Y Treasury
    for key, sym in [("treasury_10y", "^TNX"), ("treasury_2y", "^IRX")]:
        try:
            info = yf.Ticker(sym).info
            result[key] = info.get("regularMarketPrice") or info.get("previousClose")
        except Exception:
            pass

    # Major indices
    for idx in MAJOR_INDICES:
        try:
            info = yf.Ticker(idx["ticker"]).info
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            prev  = info.get("previousClose") or info.get("regularMarketPreviousClose")
            chg   = round((price - prev) / prev * 100, 2) if price and prev and prev > 0 else None
            result["indices"].append({**idx, "price": price, "change_pct": chg})
        except Exception:
            result["indices"].append({**idx, "price": None, "change_pct": None})

    # Commodities & crypto
    for c in COMMODITY_TICKERS:
        try:
            info = yf.Ticker(c["ticker"]).info
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            prev  = info.get("previousClose") or info.get("regularMarketPreviousClose")
            chg   = round((price - prev) / prev * 100, 2) if price and prev and prev > 0 else None
            result["commodities"].append({**c, "price": price, "change_pct": chg})
        except Exception:
            result["commodities"].append({**c, "price": None, "change_pct": None})

    # Sector ETFs (reuse existing)
    from src.fetchers.prices import fetch_market_sentiment
    sentiment = fetch_market_sentiment()
    result["sectors"] = sentiment.get("sectors", [])

    # Top news headlines
    try:
        from src.fetchers.news import fetch_news
        result["news"] = fetch_news(hours_back=24, max_items=15)
    except Exception:
        result["news"] = []

    return result


def _macro_events_next30() -> list:
    """Return hardcoded 2026 macro events falling within the next 30 days from today."""
    MACRO_EVENTS = [
        # FOMC Rate Decisions
        {"date": "2026-01-29", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-03-19", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-05-07", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-06-18", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-07-30", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-09-17", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-11-05", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        {"date": "2026-12-17", "event": "FOMC Rate Decision", "event_zh": "聯準會利率決議", "importance": "high"},
        # NFP (Non-Farm Payrolls) — first Friday of month
        {"date": "2026-01-09", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-02-06", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-03-06", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-04-03", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-05-01", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-06-05", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-07-10", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-08-07", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-09-04", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-10-02", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-11-06", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        {"date": "2026-12-04", "event": "Non-Farm Payrolls (NFP)", "event_zh": "非農就業報告", "importance": "high"},
        # CPI Releases — approx 2nd Wednesday of month
        {"date": "2026-01-15", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-02-12", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-03-12", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-04-10", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-05-13", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-06-11", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-07-15", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-08-12", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-09-10", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-10-14", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-11-12", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        {"date": "2026-12-10", "event": "CPI Inflation Report", "event_zh": "消費者物價指數 (CPI)", "importance": "high"},
        # PCE Releases — last business Friday of month
        {"date": "2026-01-31", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-02-28", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-03-27", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-04-30", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-05-29", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-06-26", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-07-31", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-08-28", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-09-25", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-10-30", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-11-25", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
        {"date": "2026-12-23", "event": "PCE Price Index", "event_zh": "個人消費支出物價指數 (PCE)", "importance": "high"},
    ]
    today = datetime.now(tz=TAIPEI_TZ).date()
    cutoff = today + timedelta(days=30)
    filtered = [
        e for e in MACRO_EVENTS
        if today <= datetime.strptime(e["date"], "%Y-%m-%d").date() <= cutoff
    ]
    return sorted(filtered, key=lambda e: e["date"])


def generate_market_page(data: dict = None) -> str:
    """Generate pages/market.html — live market dashboard."""
    if data is None:
        data = fetch_market_page_data()

    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    def _chg_color(v):
        if v is None: return "var(--text-muted)"
        return "#2e6b58" if v >= 0 else "#b84040"

    def _chg_str(v):
        if v is None: return "—"
        return f"{'+'if v>=0 else ''}{v:.2f}%"

    def _fmt_price(p, unit=""):
        if p is None: return "—"
        if p >= 10000: return f"{p:,.0f}"
        if p >= 100:   return f"{p:,.2f}"
        return f"{p:.4f}" if p < 1 else f"{p:.2f}"

    # ── VIX card ──
    vix = data.get("vix")
    if vix:
        if vix > 30:   vix_label, vix_color = "Extreme Fear / 極度恐慌", "#b84040"
        elif vix > 20: vix_label, vix_color = "Fear / 恐慌", "#e07820"
        elif vix > 15: vix_label, vix_color = "Neutral / 中性", "#b87820"
        else:          vix_label, vix_color = "Greed / 貪婪", "#2e6b58"
    else:
        vix_label, vix_color = "N/A", "var(--text-muted)"

    vix_html = f"""
  <div class="mk-card mk-fear">
    <div class="mk-card-title">Fear Gauge · 恐慌指數</div>
    <div class="mk-big" style="color:{vix_color}">{f'{vix:.1f}' if vix else '—'}</div>
    <div class="mk-label" style="color:{vix_color}">VIX — {vix_label}</div>
    <p class="mk-note">VIX measures expected market volatility over the next 30 days. Above 20 = fear; below 15 = complacency.<br>VIX衡量未來30天的預期市場波動性。高於20代表恐慌；低於15代表自滿。</p>
  </div>"""

    # ── Treasury yields card ──
    t10 = data.get("treasury_10y")
    t2  = data.get("treasury_2y")
    spread = round(t10 - t2, 2) if t10 and t2 else None
    spread_note = ""
    if spread is not None:
        if spread < 0:
            spread_note = "⚠️ Inverted yield curve — historically precedes recessions / 殖利率曲線倒掛——歷史上為衰退前兆"
        else:
            spread_note = "Normal yield curve / 正常殖利率曲線"

    yields_html = f"""
  <div class="mk-card mk-yields">
    <div class="mk-card-title">Treasury Yields · 美國公債殖利率</div>
    <div class="mk-yield-row">
      <div class="mk-yield-item">
        <span class="mk-yield-val">{f'{t10:.2f}%' if t10 else '—'}</span>
        <span class="mk-yield-label">10-Year / 10年期</span>
      </div>
      <div class="mk-yield-item">
        <span class="mk-yield-val">{f'{t2:.2f}%' if t2 else '—'}</span>
        <span class="mk-yield-label">2-Year / 2年期</span>
      </div>
      <div class="mk-yield-item">
        <span class="mk-yield-val" style="color:{'#b84040' if spread and spread < 0 else '#2e6b58'}">{f'{spread:+.2f}%' if spread is not None else '—'}</span>
        <span class="mk-yield-label">Spread / 利差</span>
      </div>
    </div>
    <p class="mk-note">{spread_note}<br>Higher 10Y yields raise borrowing costs and pressure growth stocks. / 10年期殖利率上升會提高借貸成本並壓縮成長股估值。</p>
  </div>"""

    # ── Index table ──
    idx_rows = ""
    for idx in data["indices"]:
        p = idx.get("price")
        c = idx.get("change_pct")
        idx_rows += f"""
    <tr>
      <td><strong>{idx['name']}</strong><br><span style="font-size:11px;color:var(--text-muted)">{idx['name_zh']} · {idx['region']}</span></td>
      <td style="text-align:right;font-weight:600">{_fmt_price(p)}</td>
      <td style="text-align:right;font-weight:600;color:{_chg_color(c)}">{_chg_str(c)}</td>
    </tr>"""

    indices_html = f"""
  <div class="mk-card mk-full">
    <div class="mk-card-title">Global Indices · 全球指數</div>
    <div class="mk-table-wrap">
    <table class="mk-table">
      <thead><tr><th>Index / 指數</th><th style="text-align:right">Price / 價格</th><th style="text-align:right">Change / 漲跌</th></tr></thead>
      <tbody>{idx_rows}</tbody>
    </table>
    </div>
  </div>"""

    # ── Commodities ──
    com_rows = ""
    for c in data["commodities"]:
        p = c.get("price")
        chg = c.get("change_pct")
        com_rows += f"""
    <tr>
      <td><strong>{c['name']}</strong><br><span style="font-size:11px;color:var(--text-muted)">{c['name_zh']} · {c['unit']}</span></td>
      <td style="text-align:right;font-weight:600">{_fmt_price(p)}</td>
      <td style="text-align:right;font-weight:600;color:{_chg_color(chg)}">{_chg_str(chg)}</td>
    </tr>"""

    commodities_html = f"""
  <div class="mk-card mk-half">
    <div class="mk-card-title">Commodities & Crypto · 大宗商品與加密貨幣</div>
    <div class="mk-table-wrap">
    <table class="mk-table">
      <thead><tr><th>Asset / 資產</th><th style="text-align:right">Price</th><th style="text-align:right">Change</th></tr></thead>
      <tbody>{com_rows}</tbody>
    </table>
    </div>
  </div>"""

    # ── Sector rotation ──
    sectors = [s for s in data.get("sectors", []) if s.get("change_pct") is not None]
    sectors_sorted = sorted(sectors, key=lambda x: x["change_pct"], reverse=True)
    sector_rows = ""
    for s in sectors_sorted:
        c = s["change_pct"]
        bar_w = min(abs(c) * 8, 100)
        bar_color = "#2e6b58" if c >= 0 else "#b84040"
        sector_rows += f"""
    <div class="sec-row">
      <span class="sec-name">{s['name']} <span style="color:var(--text-muted);font-size:11px">{s['name_zh']}</span></span>
      <div class="sec-bar-wrap">
        <div class="sec-bar" style="width:{bar_w}%;background:{bar_color};{'margin-left:auto' if c < 0 else ''}"></div>
      </div>
      <span class="sec-val" style="color:{bar_color}">{'+'if c>=0 else ''}{c:.1f}%</span>
    </div>"""

    sectors_html = f"""
  <div class="mk-card mk-half">
    <div class="mk-card-title">Sector Rotation · 板塊輪動</div>
    <div class="sec-list">{sector_rows}</div>
  </div>"""

    # ── News section ──
    news_items = data.get("news", [])
    if news_items:
        # AI-generated professional impact per headline (single batch call)
        impacts = {}
        try:
            import os, json, re, requests
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if api_key:
                items_text = "\n".join(
                    f"{i+1}. [{item.get('region','?')}] {item.get('title','')}"
                    for i, item in enumerate(news_items[:15])
                )
                prompt = (
                    "You are a senior market analyst. For each headline, write ONE sentence "
                    "(under 25 words) on its likely market impact: sectors/assets affected and "
                    "bullish/bearish/neutral verdict. Also add the Traditional Chinese translation "
                    "of your impact sentence.\n\n"
                    f"Headlines:\n{items_text}\n\n"
                    'Respond ONLY as valid JSON: {"1": {"en": "...", "zh": "..."}, "2": {...}, ...}'
                )
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "openai/gpt-oss-120b:free",
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 1200},
                    timeout=60,
                )
                if resp.status_code == 200:
                    raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    m = re.search(r'\{.*\}', raw, re.DOTALL)
                    if m:
                        impacts = json.loads(m.group())
        except Exception:
            pass

        news_rows = ""
        for i, item in enumerate(news_items):
            source    = item.get("source", "")
            title     = item.get("title", "")
            published = item.get("published", "")
            region    = item.get("region", "")
            pub_str   = published[:16] if published else ""
            impact    = impacts.get(str(i + 1), {})
            impact_en = impact.get("en", "") if isinstance(impact, dict) else str(impact)
            impact_zh = impact.get("zh", "") if isinstance(impact, dict) else ""
            impact_html = ""
            if impact_en:
                impact_html = (
                    f'<span class="news-impact">{impact_en}'
                    + (f' <span style="color:var(--text-muted)">／{impact_zh}</span>' if impact_zh else "")
                    + '</span>'
                )
            news_rows += f"""
      <div class="news-item">
        <span class="news-source">{source}{f' · {region}' if region else ''}{f' · {pub_str}' if pub_str else ''}</span>
        <span class="news-title">{title}</span>
        {impact_html}
      </div>"""
        news_html = f"""
  <div class="mk-card mk-full" style="margin-top:0;border-top:4px solid #5560a8;">
    <div class="mk-card-title">Latest Headlines · 最新頭條 (24h)</div>
    <div class="news-list">{news_rows}
    </div>
  </div>"""
    else:
        news_html = ""

    # ── Weekly review & preview ──
    month_label = now.strftime("%B %Y")
    week_num    = now.isocalendar()[1]

    # Review: today's index moves (daily snapshot)
    review_rows = ""
    today_label = now.strftime("%b %d")
    for idx in data["indices"][:5]:
        c = idx.get("change_pct")
        cc = "#2e6b58" if c and c >= 0 else "#b84040"
        cs = f'{"+" if c and c>=0 else ""}{c:.1f}%' if c is not None else "—"
        review_rows += f"""
      <div class="week-item">
        <div class="week-date">{idx['region']}</div>
        <strong>{idx['name']}</strong> &nbsp;
        <span style="color:{cc};font-weight:700">{cs}</span>
        <span style="color:var(--text-muted);font-size:11px"> 1D</span>
      </div>"""
    review_html = f"""
    <div class="week-card review">
      <div class="week-title">📊 Today's Market Snapshot · 今日市場概況 ({today_label})</div>
      {review_rows}
    </div>"""

    # Preview: upcoming earnings from calendar
    try:
        from src.fetchers.earnings import fetch_earnings_calendar
        upcoming = fetch_earnings_calendar(days_ahead=7)[:6]
    except Exception:
        upcoming = []

    preview_rows = ""
    for e in upcoming:
        date_str = e.get("earnings_date", e.get("date", ""))
        ticker   = e.get("ticker", "")
        name     = e.get("name", ticker)
        when     = e.get("time", "")
        preview_rows += f"""
      <div class="week-item">
        <div class="week-date">{date_str} {f'· {when}' if when else ''}</div>
        <strong>{ticker}</strong> — {name[:30]}
      </div>"""

    if not preview_rows:
        preview_rows = '<div class="week-item" style="color:var(--text-muted)">No major earnings this week.</div>'

    preview_html = f"""
    <div class="week-card preview">
      <div class="week-title">📅 Upcoming This Week · 本週重要事件</div>
      {preview_rows}
    </div>"""

    # ── Macro Events — next 30 days ──
    macro_events = _macro_events_next30()
    today_date = now.date()
    if macro_events:
        macro_rows = ""
        for ev in macro_events:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
            days_away = (ev_date - today_date).days
            days_label = "Today" if days_away == 0 else f"in {days_away}d"
            ev_name_en = ev["event"]
            ev_name_zh = ev["event_zh"]
            if ev.get("importance") == "high":
                name_cell = f'<strong>{ev_name_en}</strong> <span style="color:var(--text-muted);font-weight:400">/ {ev_name_zh}</span>'
            else:
                name_cell = f'{ev_name_en} <span style="color:var(--text-muted)">/ {ev_name_zh}</span>'
            macro_rows += f"""
        <tr>
          <td style="white-space:nowrap;padding-right:16px">{ev["date"]}</td>
          <td>{name_cell}</td>
          <td style="text-align:right;white-space:nowrap;color:var(--text-muted)">{days_label}</td>
        </tr>"""
        macro_html = f"""
  <div class="mk-card mk-full" style="margin-top:24px;border-top:4px solid #3a72b0;">
    <div class="mk-card-title">📅 Macro Events · 總經行事曆 (Next 30 Days)</div>
    <div class="mk-table-wrap">
    <table class="mk-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Event / 事件</th>
          <th style="text-align:right">Days Away</th>
        </tr>
      </thead>
      <tbody>{macro_rows}
      </tbody>
    </table>
    </div>
  </div>"""
    else:
        macro_html = f"""
  <div class="mk-card mk-full" style="margin-top:24px;border-top:4px solid #3a72b0;">
    <div class="mk-card-title">📅 Macro Events · 總經行事曆 (Next 30 Days)</div>
    <p style="font-size:13px;color:var(--text-muted);margin:0">No major macro events in the next 30 days.</p>
  </div>"""

    # ── Warren Buffett-style macro outlook (weekly, cached) ──
    buffett_html = ""
    try:
        import json as _json
        buffett_cache = os.path.join(PAGES_DIR, "data", "buffett_cache.json")
        os.makedirs(os.path.dirname(buffett_cache), exist_ok=True)
        cached = {}
        if os.path.exists(buffett_cache):
            with open(buffett_cache) as _f:
                cached = _json.load(_f)
        cache_age_days = (now - datetime.fromisoformat(cached.get("generated_at", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00"))).days if cached.get("generated_at") else 999
        if cache_age_days >= 7 or not cached.get("en"):
            idx_summary = " | ".join(
                f"{x['name']} {x.get('change_pct'):+.1f}%" if x.get('change_pct') is not None else x['name']
                for x in data["indices"][:5]
            )
            from src.analysis.claude_analyst import generate_buffett_outlook
            outlook = generate_buffett_outlook(idx_summary)
            cached = {**outlook, "generated_at": now.isoformat()}
            with open(buffett_cache, "w") as _f:
                _json.dump(cached, _f)
        if cached.get("en"):
            buffett_html = f"""
  <div class="mk-card mk-full" style="margin-top:24px;border-top:4px solid #b87820;">
    <div class="mk-card-title">🏛️ Long-Term Investor Macro View · 長線投資人宏觀視角 &nbsp;<span style="font-weight:400;text-transform:none">— Weekly fundamental lens for the patient investor</span></div>
    <p style="font-size:14px;line-height:1.8;color:var(--text-med);margin:0 0 12px">{cached["en"]}</p>
    <p style="font-size:13px;line-height:1.8;color:var(--text-muted);margin:0">{cached.get("zh","")}</p>
    <p style="font-size:11px;color:var(--text-muted);margin-top:12px">Regenerated weekly &nbsp;·&nbsp; AI-generated fundamental view, not financial advice.</p>
  </div>"""
    except Exception:
        pass

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market · The Signal Desk</title>
<style>
{SHARED_CSS}

.mk-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}}
.mk-card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px 28px;
}}
.mk-full {{ grid-column: 1 / -1; }}
.mk-half {{ grid-column: span 1; }}
.mk-fear {{ border-top: 4px solid #b84040; }}
.mk-yields {{ border-top: 4px solid #3a72b0; }}
.mk-card-title {{
  font-size: 11px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px;
}}
.mk-big {{ font-size: 52px; font-weight: 800; line-height: 1; margin-bottom: 6px; }}
.mk-label {{ font-size: 14px; font-weight: 600; margin-bottom: 12px; }}
.mk-note {{ font-size: 12px; color: var(--text-muted); line-height: 1.6; margin-top: 12px; }}
.mk-yield-row {{ display: flex; gap: 24px; margin-bottom: 8px; }}
.mk-yield-item {{ display: flex; flex-direction: column; gap: 3px; }}
.mk-yield-val {{ font-size: 26px; font-weight: 800; }}
.mk-yield-label {{ font-size: 11px; color: var(--text-muted); }}
.mk-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
.mk-table th {{
  font-size: 10px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.07em;
  padding: 6px 0 10px; border-bottom: 2px solid var(--border); text-align: left;
}}
.mk-table td {{
  padding: 10px 0; border-bottom: 1px solid var(--border-light); vertical-align: top;
}}
.mk-table tr:last-child td {{ border-bottom: none; }}
.sec-list {{ display: flex; flex-direction: column; gap: 8px; }}
.sec-row {{ display: grid; grid-template-columns: 140px 1fr 52px; gap: 8px; align-items: center; }}
.sec-name {{ font-size: 12px; font-weight: 600; }}
.sec-bar-wrap {{ height: 6px; background: var(--border-light); border-radius: 3px; overflow: hidden; }}
.sec-bar {{ height: 6px; border-radius: 3px; min-width: 2px; }}
.sec-val {{ font-size: 12px; font-weight: 700; text-align: right; }}
.last-updated {{ font-size: 12px; color: var(--text-muted); margin-bottom: 24px; }}
@media (max-width: 680px) {{
  .mk-grid {{ grid-template-columns: 1fr; }}
  .mk-full, .mk-half {{ grid-column: span 1; }}
}}
.news-list {{ display: flex; flex-direction: column; gap: 0; }}
.news-item {{
  padding: 16px 0; border-bottom: 1px solid var(--border-light);
  display: flex; flex-direction: column; gap: 5px;
}}
.news-item:last-child {{ border-bottom: none; }}
.news-source {{
  font-size: 10px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 0.07em;
}}
.news-title {{ font-size: 14px; font-weight: 600; color: var(--text); line-height: 1.4; }}
.news-impact {{ font-size: 12px; color: var(--text-med); line-height: 1.6; margin-top: 2px; }}
.news-time {{ font-size: 11px; color: var(--text-muted); }}
.week-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 24px;
}}
.week-card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 24px 28px;
}}
.week-card.review {{ border-top: 4px solid #3a72b0; }}
.week-card.preview {{ border-top: 4px solid #2e6b58; }}
.week-title {{
  font-size: 11px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 14px;
}}
.week-item {{ padding: 8px 0; border-bottom: 1px solid var(--border-light); font-size: 13px; }}
.week-item:last-child {{ border-bottom: none; }}
.week-date {{ font-size: 11px; color: var(--text-muted); margin-bottom: 2px; }}
@media (max-width: 680px) {{
  .week-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

{_nav_html("market.html")}

<div class="hero">
  <div class="pill">Live Data · 即時數據 · Auto-updated</div>
  <h1>Market Overview &nbsp;<span style="font-size:16px;font-weight:400;color:var(--text-muted)">市場總覽</span></h1>
  <p class="hero-sub">Real-time pulse on global markets — fear gauge, yields, major indices, sector rotation, key assets, and latest headlines. Refreshed with every briefing cycle.<br><span style="font-size:13px;color:var(--text-muted)">全球市場即時脈動——恐慌指數、殖利率、主要指數、板塊輪動、關鍵資產與最新頭條。每次簡報後同步更新。</span></p>
</div>

<div class="content">
  <p class="last-updated">Last updated: {updated}</p>

  <div class="mk-grid">
    {vix_html}
    {yields_html}
    {indices_html}
    {commodities_html}
    {sectors_html}
  </div>

  {news_html}

  {macro_html}

  <div class="week-grid">
    {review_html}
    {preview_html}
  </div>

  {buffett_html}
</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Market Overview &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>
</body>
</html>"""

    out_path = os.path.join(PAGES_DIR, "market.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] market.html updated")
    return "market.html"


# ── Top Picks screener ────────────────────────────────────────────────────────

TOP_PICKS_UNIVERSE = [
    # AI & Semiconductors (15)
    "NVDA","AMD","INTC","AVGO","TSM","QCOM","ASML","MU","AMAT","LRCX","KLAC","ARM","MRVL","TXN","ADI",
    # Big Tech, Cloud & AI Software (14)
    "AAPL","MSFT","GOOGL","META","AMZN","ORCL","CRM","ADBE","NOW","SNOW","PLTR","NET","DDOG","UBER",
    # EV & Mobility (5)
    "TSLA","BYDDY","RIVN","F","GM",
    # Financials & Payments (12)
    "JPM","BAC","GS","V","MA","PYPL","AXP","BLK","MS","SCHW","WFC","SPGI",
    # Healthcare & Biotech (13)
    "JNJ","UNH","PFE","ABBV","MRK","LLY","TMO","ISRG","DXCM","AMGN","GILD","CVS","BMY",
    # Defense & Aerospace (7)
    "LMT","RTX","NOC","BA","GD","HII","LHX",
    # Retail & Consumer Staples (13)
    "WMT","COST","TGT","HD","NKE","SBUX","MCD","NFLX","LULU","LOW","PG","KO","TJX",
    # Energy & Commodities (8)
    "XOM","CVX","COP","SLB","NEE","ENPH","OXY","PSX",
    # Real Estate & Infrastructure (6)
    "AMT","EQIX","PLD","CCI","O","WELL",
    # Media & Telecom (3)
    "DIS","VZ","ABNB",
    # Cybersecurity & E-commerce (4)
    "PANW","SHOP","COF","BX",
]
TOP_PICKS_UNIVERSE = list(dict.fromkeys(TOP_PICKS_UNIVERSE))  # deduplicate — target 100


def fetch_top_picks_data() -> list:
    """Fetch conviction scores for the broad universe; return top 30 with score ≥ 75."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import yfinance as yf
    from src.analysis.conviction_score import compute_conviction_score

    results = []
    for ticker in TOP_PICKS_UNIVERSE:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if not price:
                continue

            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            change_pct = ((price - prev_close) / prev_close * 100) if price and prev_close and prev_close != 0 else 0.0

            analyst_target = info.get("targetMeanPrice")
            upside = ((analyst_target - price) / price * 100) if analyst_target and price else None

            free_cashflow = info.get("freeCashflow")
            total_revenue = info.get("totalRevenue")
            fcf_margin = (free_cashflow / total_revenue) if free_cashflow and total_revenue and total_revenue > 0 else None

            total_cash  = info.get("totalCash")
            total_debt  = info.get("totalDebt")
            equity_ratio = None
            try:
                bs = t.balance_sheet
                if bs is not None and not bs.empty:
                    col = bs.columns[0]
                    def _g(*keys):
                        for k in keys:
                            if k in bs.index:
                                try: return float(bs.at[k, col])
                                except: pass
                        return None
                    ta = _g("Total Assets")
                    se = _g("Stockholders Equity","Total Stockholders Equity","Common Stock Equity")
                    if ta and se and ta > 0:
                        equity_ratio = se / ta
            except Exception:
                pass

            op_margin = info.get("operatingMargins") or 0
            op_income = op_margin * (total_revenue or 0)
            try:
                bs2 = t.balance_sheet
                col2 = bs2.columns[0] if bs2 is not None and not bs2.empty else None
                curr_liab = None
                if col2:
                    for k in ("Current Liabilities","Total Current Liabilities"):
                        if k in bs2.index:
                            try: curr_liab = float(bs2.at[k, col2]); break
                            except: pass
                ta2 = None
                for k in ("Total Assets",):
                    if bs2 is not None and k in bs2.index:
                        try: ta2 = float(bs2.at[k, col2]); break
                        except: pass
                inv_cap = (ta2 or 0) - (curr_liab or 0)
                roic = op_income * 0.79 / inv_cap if inv_cap > 0 and op_income else None
            except Exception:
                roic = None

            market_cap = info.get("marketCap")
            fcf_yield = (free_cashflow / market_cap) if free_cashflow and market_cap and market_cap > 0 else None

            d = {
                "ticker": ticker,
                "name": info.get("shortName") or info.get("longName") or ticker,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "currency": info.get("currency", "USD"),
                "sector": info.get("sector", ""),
                "market_cap": market_cap,
                "forward_pe": info.get("forwardPE"),
                "analyst_target": analyst_target,
                "analyst_upside_pct": round(upside, 1) if upside is not None else None,
                "recommendation": info.get("recommendationKey", ""),
                "gross_margin": info.get("grossMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "fcf_margin": fcf_margin,
                "fcf_yield": fcf_yield,
                "roic": roic,
                "return_on_equity": info.get("returnOnEquity"),
                "total_cash": total_cash,
                "total_debt": total_debt,
                "equity_ratio": equity_ratio,
            }
            cs = compute_conviction_score(d)
            d["_cs"] = cs
            results.append(d)
        except Exception:
            continue

    results.sort(key=lambda x: x["_cs"]["score"], reverse=True)
    # Save ALL scored tickers to cache (not just top 30)
    _save_scores_cache({r["ticker"]: r["_cs"] for r in results})
    # Append today's scores to the rolling 90-day history
    _append_score_history({r["ticker"]: r["_cs"]["score"] for r in results})
    # Take top 30 by score; include all ≥75 (Strong Conviction) plus fill to 30 with Moderate (≥55)
    strong = [r for r in results if r["_cs"]["score"] >= 75]
    moderate = [r for r in results if 55 <= r["_cs"]["score"] < 75]
    combined = (strong + moderate)[:30]
    return combined


def generate_top_picks_page(picks: list = None) -> str:
    """Generate pages/top-picks.html from the broad universe conviction screener."""
    if picks is None:
        picks = fetch_top_picks_data()

    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    def _score_bar(score, max_score):
        pct = round(score / max_score * 100)
        return (
            f'<div style="background:#e8efea;border-radius:4px;height:6px;width:100%;">'
            f'<div style="background:var(--accent);border-radius:4px;height:6px;width:{pct}%;"></div>'
            f'</div>'
        )

    def _fmt_val(val, mult=100, suffix="%", decimals=0):
        if val is None: return '<span style="color:var(--text-muted)">—</span>'
        v = val * mult
        sign = "+" if v > 0 else ""
        return f'{sign}{v:.{decimals}f}{suffix}'

    def _cap(val):
        if not val: return "—"
        b = val / 1e9
        return f"${b:.0f}B" if b >= 1 else f"${val/1e6:.0f}M"

    # Load 30-day score history for sparklines
    _history_path = os.path.join(PAGES_DIR, "data", "scores_history.json")
    try:
        with open(_history_path) as _hf:
            _score_history = _json_mod.load(_hf)
    except Exception:
        _score_history = {}
    from datetime import date as _date, timedelta as _td
    _cutoff_30 = str(_date.today() - _td(days=30))

    rows_html = ""
    for rank, d in enumerate(picks, 1):
        cs = d["_cs"]
        score = cs["score"]
        # Score color
        if score >= 75: sc = "#2e6b58"
        elif score >= 55: sc = "#b87820"
        else: sc = "#b84040"

        change = d.get("change_pct", 0)
        change_color = "#2e6b58" if change >= 0 else "#b84040"
        change_str = f'{"+" if change >= 0 else ""}{change:.2f}%'

        upside = d.get("analyst_upside_pct")
        upside_str = f'{"+" if upside and upside >= 0 else ""}{upside:.1f}%' if upside is not None else "—"
        upside_color = "#2e6b58" if upside and upside > 0 else "#b84040"

        ticker = d["ticker"]
        company_link = f'stock-{ticker.lower()}.html'

        # Build sparkline for this ticker (last 30 days)
        _entries = _score_history.get(ticker, [])
        _points = [e["score"] for e in _entries if e["date"] >= _cutoff_30]
        sparkline_html = _sparkline_svg(_points)

        rows_html += f"""
  <div class="tp-row">
    <div class="tp-rank">#{rank}</div>
    <div class="tp-identity">
      <a href="{company_link}" class="tp-ticker">{ticker}</a>
      <span class="tp-name">{d.get('name','')}</span>
      <span class="tp-sector">{d.get('sector','')}</span>
    </div>
    <div class="tp-score-col">
      <span class="tp-score" style="color:{sc}">{score}</span>
      <span class="tp-score-label">{cs['label']}</span>
      <div class="tp-pillars">
        <div class="tp-pillar-row">
          <span>Quality</span>
          {_score_bar(cs['pillar_quality'], cs['pillar_quality_max'])}
          <span>{cs['pillar_quality']}/{cs['pillar_quality_max']}</span>
        </div>
        <div class="tp-pillar-row">
          <span>Growth</span>
          {_score_bar(cs['pillar_growth'], cs['pillar_growth_max'])}
          <span>{cs['pillar_growth']}/{cs['pillar_growth_max']}</span>
        </div>
        <div class="tp-pillar-row">
          <span>Health</span>
          {_score_bar(cs['pillar_health'], cs['pillar_health_max'])}
          <span>{cs['pillar_health']}/{cs['pillar_health_max']}</span>
        </div>
      </div>
    </div>
    <div class="tp-metrics">
      <div class="tp-metric-item">
        <span class="tp-m-label">Rev Growth</span>
        <span class="tp-m-val">{_fmt_val(d.get('revenue_growth'))}</span>
      </div>
      <div class="tp-metric-item">
        <span class="tp-m-label">FCF Margin</span>
        <span class="tp-m-val">{_fmt_val(d.get('fcf_margin'))}</span>
      </div>
      <div class="tp-metric-item">
        <span class="tp-m-label">Fwd P/E</span>
        <span class="tp-m-val">{f"{d['forward_pe']:.1f}x" if d.get('forward_pe') else "—"}</span>
      </div>
      <div class="tp-metric-item">
        <span class="tp-m-label">Analyst Upside</span>
        <span class="tp-m-val" style="color:{upside_color}">{upside_str}</span>
      </div>
    </div>
    <div class="tp-trend-col">{sparkline_html}</div>
    <div class="tp-price-col">
      <span class="tp-price">${d['price']:.2f}</span>
      <span class="tp-change" style="color:{change_color}">{change_str}</span>
      <span class="tp-cap">{_cap(d.get('market_cap'))}</span>
    </div>
  </div>"""

    count = len(picks)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Top Picks · The Signal Desk</title>
<style>
{SHARED_CSS}

.tp-list {{
  display: flex; flex-direction: column; gap: 2px; margin-bottom: 48px;
}}
.tp-row {{
  display: grid;
  grid-template-columns: 36px 1fr 200px 180px 110px;
  gap: 16px; align-items: center;
  background: var(--surface); border: 1px solid var(--border-light);
  border-radius: var(--radius-sm); padding: 16px 20px;
  transition: box-shadow 0.15s;
}}
.tp-row:hover {{ box-shadow: var(--shadow); }}
.tp-rank {{
  font-size: 13px; font-weight: 700; color: var(--text-muted); text-align: center;
}}
.tp-identity {{ display: flex; flex-direction: column; gap: 2px; }}
.tp-ticker {{
  font-size: 16px; font-weight: 700; color: var(--accent);
  text-decoration: none; letter-spacing: 0.02em;
}}
.tp-ticker:hover {{ text-decoration: underline; }}
.tp-name {{ font-size: 12px; color: var(--text-med); }}
.tp-sector {{ font-size: 11px; color: var(--text-muted); }}
.tp-score-col {{ display: flex; flex-direction: column; gap: 4px; }}
.tp-score {{ font-size: 22px; font-weight: 800; line-height: 1; }}
.tp-score-label {{ font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }}
.tp-pillars {{ display: flex; flex-direction: column; gap: 3px; margin-top: 4px; }}
.tp-pillar-row {{
  display: grid; grid-template-columns: 44px 1fr 28px;
  gap: 4px; align-items: center;
  font-size: 10px; color: var(--text-muted);
}}
.tp-metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.tp-metric-item {{ display: flex; flex-direction: column; gap: 1px; }}
.tp-m-label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }}
.tp-m-val {{ font-size: 13px; font-weight: 600; color: var(--text); }}
.tp-price-col {{ display: flex; flex-direction: column; gap: 2px; text-align: right; }}
.tp-price {{ font-size: 16px; font-weight: 700; }}
.tp-change {{ font-size: 12px; font-weight: 600; }}
.tp-cap {{ font-size: 11px; color: var(--text-muted); }}
.tp-header {{
  display: grid; grid-template-columns: 36px 1fr 200px 180px 110px;
  gap: 16px; padding: 8px 20px;
  font-size: 10px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.07em;
  border-bottom: 2px solid var(--border); margin-bottom: 8px;
}}
.rationale-card {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 32px 36px; margin-bottom: 32px;
}}
.rationale-card h2 {{
  font-size: 16px; font-weight: 700; margin-bottom: 18px;
  color: var(--accent); letter-spacing: 0.02em;
}}
.rationale-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
.rationale-item h3 {{
  font-size: 13px; font-weight: 700; margin-bottom: 6px; color: var(--text);
}}
.rationale-item p {{
  font-size: 13px; line-height: 1.7; color: var(--text-med);
}}
.score-legend {{
  display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px;
}}
.legend-item {{
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--text-med);
}}
.legend-dot {{
  width: 10px; height: 10px; border-radius: 50%;
}}
@media (max-width: 760px) {{
  .tp-row, .tp-header {{ grid-template-columns: 1fr; }}
  .tp-rank {{ display: none; }}
  .rationale-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

{_nav_html("top-picks.html")}

<div class="hero">
  <div class="pill">Conviction Screener · 精選評分篩選 · Auto-updated nightly</div>
  <h1>Top Picks &nbsp;<span style="font-size:16px;font-weight:400;color:var(--text-muted)">精選標的</span></h1>
  <p class="hero-sub">The algorithm — not the editor — surfaces these {count} stocks from a universe of {len(TOP_PICKS_UNIVERSE)} companies. Stocks must score ≥ 55 / 100 on a three-pillar conviction model (Quality, Growth, Financial Health), ranked by score. Top 30 only — no human override.<br><span style="font-size:13px;color:var(--text-muted)">由演算法從 {len(TOP_PICKS_UNIVERSE)} 支股票中篩選，評分須達 55/100（品質、成長、財務健康三大支柱），依分數排序，最多顯示前 30 名。</span></p>
</div>

<div class="content">

  <div class="score-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#2e6b58"></div>Strong Conviction (75–100)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#b87820"></div>Moderate (55–74)</div>
    <div class="legend-item"><div class="legend-dot" style="background:#b84040"></div>Weak (35–54)</div>
  </div>

  <div class="tp-header">
    <div></div>
    <div>Company</div>
    <div>Conviction Score</div>
    <div>Key Metrics</div>
    <div style="text-align:right">Price</div>
  </div>

  <div class="tp-list">
{rows_html}
  </div>

  <div class="rationale-card">
    <h2>How the Score Works / 評分邏輯說明</h2>
    <div class="rationale-grid">
      <div class="rationale-item">
        <h3>🏆 Quality Pillar (33 pts)</h3>
        <p>Measures how efficiently the business converts capital into profit. High ROIC (Return on Invested Capital ≥ 15%) means every dollar reinvested earns strong returns — a hallmark of durable businesses. High FCF margin means the company generates real cash, not just accounting profit. High gross margin reflects pricing power.</p>
        <p style="margin-top:8px;font-size:12px;color:var(--text-muted)">衡量企業將資本轉化為利潤的效率。高投資資本回報率（ROIC ≥ 15%）代表每一美元再投資都能產生強勁回報——這是持久型企業的標誌。高自由現金流利潤率代表企業創造真實現金，而非僅有帳面利潤。高毛利率反映定價能力。</p>
      </div>
      <div class="rationale-item">
        <h3>📈 Growth Pillar (34 pts)</h3>
        <p>Tracks whether the business is expanding fast enough to justify investment. Revenue growth ≥ 10% signals real demand momentum, not just margin engineering. Earnings growth ≥ 10% confirms the top-line expansion is flowing through to shareholders — not being consumed by costs.</p>
        <p style="margin-top:8px;font-size:12px;color:var(--text-muted)">追蹤企業是否以足夠快的速度擴張以證明投資值得。營收增長 ≥ 10% 代表真實需求動能，而非單純靠利潤率工程。盈利增長 ≥ 10% 確認頂線擴張正在流向股東，而非被成本消耗。</p>
      </div>
      <div class="rationale-item">
        <h3>🏦 Health Pillar (33 pts)</h3>
        <p>Assesses balance sheet resilience. A strong cash-to-debt ratio means the company can survive downturns and invest through cycles. A high equity ratio means the business is largely self-funded. Analyst upside reflects Wall Street's collective view on whether the stock is fairly priced.</p>
        <p style="margin-top:8px;font-size:12px;color:var(--text-muted)">評估資產負債表韌性。強勁的現金對債務比率意味著公司能在低迷期存活並跨周期投資。高股東權益比率意味著企業主要依靠自有資金運營。分析師上行空間反映華爾街對股票是否合理定價的集體看法。</p>
      </div>
      <div class="rationale-item">
        <h3>⚠️ What this screen does NOT do</h3>
        <p>This is a fundamentals filter, not a buy signal. A high score means the business is financially sound — it does not account for valuation (a great company at a sky-high price can still be a poor investment), near-term catalysts, or macro risks. Always read the full company page and form your own view.</p>
        <p style="margin-top:8px;font-size:12px;color:var(--text-muted)">這是基本面篩選器，不是買入信號。高分意味著業務財務健康——但不考慮估值（高價買入優質公司仍可能是糟糕投資）、近期催化劑或宏觀風險。請閱讀完整公司頁面並自行判斷。</p>
      </div>
    </div>
  </div>

</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Top Picks &nbsp;·&nbsp; Algorithmically screened, not editorially selected &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>
</body>
</html>"""

    out_path = os.path.join(PAGES_DIR, "top-picks.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] top-picks.html updated — {count} stocks qualify (≥55 conviction, top 30)")
    return "top-picks.html"


# ── Sector Leaders page ───────────────────────────────────────────────────────

SECTOR_GROUPS = [
    {
        "id": "ai-semis",
        "name": "AI & Semiconductors",
        "name_zh": "AI 與半導體",
        "tickers": ["NVDA", "AMD", "INTC", "AVGO", "TSM", "QCOM", "ASML", "ARM", "AMAT", "MU"],
    },
    {
        "id": "big-tech",
        "name": "Big Tech & Cloud",
        "name_zh": "大型科技與雲端",
        "tickers": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "ORCL", "CRM", "ADBE", "NOW"],
    },
    {
        "id": "ev-mobility",
        "name": "EV & Mobility",
        "name_zh": "電動車與出行",
        "tickers": ["TSLA", "BYDDY", "RIVN", "GM", "F", "STLA"],
    },
    {
        "id": "financials",
        "name": "Financials & Payments",
        "name_zh": "金融與支付",
        "tickers": ["JPM", "BAC", "GS", "MS", "V", "MA", "AXP", "PYPL", "BLK", "SCHW"],
    },
    {
        "id": "healthcare",
        "name": "Healthcare & Biotech",
        "name_zh": "醫療與生技",
        "tickers": ["LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ISRG", "DXCM"],
    },
    {
        "id": "defense",
        "name": "Defense & Aerospace",
        "name_zh": "國防與航太",
        "tickers": ["LMT", "RTX", "NOC", "BA", "GD", "HII"],
    },
    {
        "id": "retail",
        "name": "Retail & Consumer",
        "name_zh": "零售與消費",
        "tickers": ["WMT", "COST", "TGT", "NKE", "SBUX", "MCD", "HD", "LOW"],
    },
    {
        "id": "energy",
        "name": "Energy & Utilities",
        "name_zh": "能源與公用事業",
        "tickers": ["XOM", "CVX", "COP", "SLB", "NEE", "ENPH", "D"],
    },
]

# Group color accents
_GROUP_COLORS = {
    "ai-semis":   "#5560a8",
    "big-tech":   "#2e6b58",
    "ev-mobility":"#2a7a7a",
    "financials": "#3a72b0",
    "healthcare": "#7a5030",
    "defense":    "#b84040",
    "retail":     "#b87820",
    "energy":     "#4a6030",
}


def fetch_sector_leaders_data() -> list:
    """Fetch conviction scores for all sector groups; return groups with ranked members."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import yfinance as yf
    from src.analysis.conviction_score import compute_conviction_score

    # Load shared daily scores cache written by fetch_top_picks_data()
    _scores_cache = _load_scores_cache()

    all_tickers = list({t for g in SECTOR_GROUPS for t in g["tickers"]})
    cache = {}
    for ticker in all_tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if not price:
                continue
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            change_pct = ((price - prev) / prev * 100) if price and prev and prev != 0 else 0.0
            analyst_target = info.get("targetMeanPrice")
            upside = ((analyst_target - price) / price * 100) if analyst_target and price else None
            fcf = info.get("freeCashflow")
            rev = info.get("totalRevenue")
            fcf_margin = (fcf / rev) if fcf and rev and rev > 0 else None
            total_cash = info.get("totalCash")
            total_debt = info.get("totalDebt")
            equity_ratio = None
            roic = None
            try:
                bs = t.balance_sheet
                if bs is not None and not bs.empty:
                    col = bs.columns[0]
                    def _g(*keys):
                        for k in keys:
                            if k in bs.index:
                                try: return float(bs.at[k, col])
                                except: pass
                        return None
                    ta = _g("Total Assets")
                    se = _g("Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity")
                    if ta and se and ta > 0:
                        equity_ratio = se / ta
                    op_margin = info.get("operatingMargins") or 0
                    op_income = op_margin * (rev or 0)
                    curr_liab = _g("Current Liabilities", "Total Current Liabilities")
                    inv_cap = (ta or 0) - (curr_liab or 0)
                    if inv_cap > 0 and op_income:
                        roic = op_income * 0.79 / inv_cap
            except Exception:
                pass
            d = {
                "ticker": ticker,
                "name": info.get("shortName") or info.get("longName") or ticker,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "currency": info.get("currency", "USD"),
                "market_cap": info.get("marketCap"),
                "forward_pe": info.get("forwardPE"),
                "analyst_upside_pct": round(upside, 1) if upside is not None else None,
                "gross_margin": info.get("grossMargins"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "fcf_margin": fcf_margin,
                "roic": roic,
                "return_on_equity": info.get("returnOnEquity"),
                "total_cash": total_cash,
                "total_debt": total_debt,
                "equity_ratio": equity_ratio,
            }
            # Use cached score if available, otherwise compute fresh
            d["_cs"] = _scores_cache.get(ticker) or compute_conviction_score(d)
            cache[ticker] = d
        except Exception:
            continue

    result = []
    for group in SECTOR_GROUPS:
        members = []
        for t in group["tickers"]:
            if t in cache:
                members.append(cache[t])
        members.sort(key=lambda x: x["_cs"]["score"], reverse=True)
        if members:
            result.append({**group, "members": members[:5]})
    return result


def generate_sector_leaders_page(groups: list = None) -> str:
    """Generate pages/sector-leaders.html."""
    if groups is None:
        groups = fetch_sector_leaders_data()

    now = datetime.now(tz=TAIPEI_TZ)

    def _bar(score):
        pct = min(score, 100)
        color = "#2e6b58" if score >= 75 else "#b87820" if score >= 55 else "#b84040"
        return (
            f'<div style="background:#e8efea;border-radius:3px;height:5px;flex:1;">'
            f'<div style="background:{color};border-radius:3px;height:5px;width:{pct}%;"></div>'
            f'</div>'
        )

    def _pct(val):
        if val is None: return "—"
        return f"{'+' if val*100 >= 0 else ''}{val*100:.0f}%"

    groups_html = ""
    for group in groups:
        gid = group["id"]
        color = _GROUP_COLORS.get(gid, "#2e6b58")
        members = group["members"]
        leader = members[0] if members else None

        rows = ""
        for rank, m in enumerate(members, 1):
            cs = m["_cs"]
            score = cs["score"]
            sc = "#2e6b58" if score >= 75 else "#b87820" if score >= 55 else "#b84040"
            chg = m.get("change_pct", 0)
            chg_color = "#2e6b58" if chg >= 0 else "#b84040"
            crown = " 👑" if rank == 1 else ""
            ticker = m["ticker"]
            rows += f"""
      <div class="sl-member{'  sl-leader' if rank == 1 else ''}">
        <div class="sl-m-rank" style="color:{color}">#{rank}{crown}</div>
        <div class="sl-m-identity">
          <a href="stock-{ticker.lower()}.html" class="sl-m-ticker" style="color:{color}">{ticker}</a>
          <span class="sl-m-name">{m.get('name','')}</span>
        </div>
        <div class="sl-m-score-wrap">
          <span class="sl-m-score" style="color:{sc}">{score}</span>
          {_bar(score)}
        </div>
        <div class="sl-m-metrics">
          <span>{_pct(m.get('revenue_growth'))} rev</span>
          <span>{_pct(m.get('fcf_margin'))} FCF</span>
        </div>
        <div class="sl-m-price">
          <span>${m['price']:.2f}</span>
          <span style="color:{chg_color};font-size:11px">{'+' if chg>=0 else ''}{chg:.2f}%</span>
        </div>
      </div>"""

        leader_note = ""
        if leader:
            lcs = leader["_cs"]
            leader_note = (
                f'<div class="sl-leader-note" style="border-left:3px solid {color}">'
                f'<strong>Leader:</strong> {leader["ticker"]} — '
                f'Score {lcs["score"]}/100 · '
                f'Quality {lcs["pillar_quality"]}/{lcs["pillar_quality_max"]} · '
                f'Growth {lcs["pillar_growth"]}/{lcs["pillar_growth_max"]} · '
                f'Health {lcs["pillar_health"]}/{lcs["pillar_health_max"]}'
                f'</div>'
            )

        groups_html += f"""
  <div class="sl-group" id="{gid}">
    <div class="sl-group-header" style="border-left:4px solid {color}">
      <div>
        <span class="sl-group-name" style="color:{color}">{group['name']}</span>
        <span class="sl-group-zh">{group['name_zh']}</span>
      </div>
      <span class="sl-group-count" style="color:{color}">{len(members)} companies</span>
    </div>
    {leader_note}
    <div class="sl-members">
      <div class="sl-members-header">
        <span></span><span>Company</span><span>Score</span><span>Metrics</span><span>Price</span>
      </div>
{rows}
    </div>
  </div>"""

    # Jump links
    jump_links = " ".join(
        f'<a href="#{g["id"]}" class="jump-link">{g["name"]}</a>'
        for g in groups
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sector Leaders · The Signal Desk</title>
<style>
{SHARED_CSS}

.jump-bar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 32px; }}
.jump-link {{
  font-size: 11px; font-weight: 600; color: var(--text-muted);
  background: var(--surface); border: 1px solid var(--border);
  padding: 5px 12px; border-radius: 20px; text-decoration: none;
  transition: background 0.15s, color 0.15s;
}}
.jump-link:hover {{ background: var(--accent-bg); color: var(--accent); }}

.sl-group {{
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 24px; overflow: hidden;
}}
.sl-group-header {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; background: var(--surface-off);
  border-bottom: 1px solid var(--border-light);
}}
.sl-group-name {{ font-size: 16px; font-weight: 700; display: block; }}
.sl-group-zh {{ font-size: 12px; color: var(--text-muted); display: block; }}
.sl-group-count {{ font-size: 11px; font-weight: 700; }}
.sl-leader-note {{
  margin: 12px 24px 0; padding: 10px 14px;
  background: var(--accent-bg); border-radius: var(--radius-sm);
  font-size: 12px; color: var(--text-med);
}}
.sl-members {{ padding: 12px 0 8px; }}
.sl-members-header {{
  display: grid; grid-template-columns: 56px 1fr 140px 120px 80px;
  gap: 12px; padding: 4px 24px 8px;
  font-size: 10px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.07em;
  border-bottom: 1px solid var(--border-light);
}}
.sl-member {{
  display: grid; grid-template-columns: 56px 1fr 140px 120px 80px;
  gap: 12px; align-items: center;
  padding: 10px 24px; border-bottom: 1px solid var(--border-light);
  transition: background 0.12s;
}}
.sl-member:last-child {{ border-bottom: none; }}
.sl-member:hover {{ background: var(--surface-off); }}
.sl-leader {{ background: linear-gradient(90deg, var(--accent-bg) 0%, var(--surface) 70%); }}
.sl-leader:hover {{ background: var(--accent-bg); }}
.sl-m-rank {{ font-size: 12px; font-weight: 700; }}
.sl-m-identity {{ display: flex; flex-direction: column; gap: 1px; }}
.sl-m-ticker {{
  font-size: 14px; font-weight: 700; text-decoration: none; letter-spacing: 0.02em;
}}
.sl-m-ticker:hover {{ text-decoration: underline; }}
.sl-m-name {{ font-size: 11px; color: var(--text-muted); }}
.sl-m-score-wrap {{ display: flex; align-items: center; gap: 8px; }}
.sl-m-score {{ font-size: 20px; font-weight: 800; width: 36px; flex-shrink: 0; }}
.sl-m-metrics {{ display: flex; flex-direction: column; gap: 2px; font-size: 11px; color: var(--text-muted); }}
.sl-m-price {{ display: flex; flex-direction: column; gap: 1px; font-size: 13px; font-weight: 600; text-align: right; }}

@media (max-width: 680px) {{
  .sl-member, .sl-members-header {{ grid-template-columns: 40px 1fr 100px; }}
  .sl-m-metrics, .sl-m-price {{ display: none; }}
}}
</style>
</head>
<body>

{_nav_html("sector-leaders.html")}

<div class="hero">
  <div class="pill">Peer Comparison · 同類比較 · Auto-updated nightly</div>
  <h1>Sector Leaders &nbsp;<span style="font-size:16px;font-weight:400;color:var(--text-muted)">產業領袖</span></h1>
  <p class="hero-sub">Within each sector, stocks are ranked by conviction score — Quality, Growth, and Financial Health combined. The 👑 leader is the most fundamentally sound stock in that peer group right now. Top 5 per group. Use this to compare, not to buy blind.<br><span style="font-size:13px;color:var(--text-muted)">各產業股票依評分排序——品質、成長、財務健康三項合計。👑 代表當前該同類中基本面最強的股票。每組最多顯示前 5 名。</span></p>
</div>

<div class="content">

  <div class="jump-bar">{jump_links}</div>

  {groups_html}

</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Sector Leaders &nbsp;·&nbsp; Ranked by conviction score within each peer group &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>
</body>
</html>"""

    out_path = os.path.join(PAGES_DIR, "sector-leaders.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    total_stocks = sum(len(g["members"]) for g in groups)
    print(f"[Pages] sector-leaders.html updated — {len(groups)} groups, {total_stocks} stocks")
    return "sector-leaders.html"


# ── Auto Earnings Calendar ────────────────────────────────────────────────────

def generate_earnings_calendar_page() -> str:
    """Generate pages/earnings-calendar.html — auto-fetched from yfinance."""
    from src.fetchers.earnings import fetch_earnings_calendar, MAJOR_NAMES
    from src.utils.helpers import load_watchlist
    from datetime import date, datetime

    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    watchlist_tickers = {item["ticker"] for item in load_watchlist()}

    # Upcoming: 90 days
    upcoming = fetch_earnings_calendar(days_ahead=90)

    # Group by month
    months = {}
    for e in upcoming:
        try:
            ed = datetime.strptime(e["earnings_date"], "%Y-%m-%d")
            key = ed.strftime("%B %Y")
            months.setdefault(key, []).append(e)
        except Exception:
            continue

    def _beat_badge(surprise):
        if surprise is None:
            return ""
        if surprise > 0:
            return f'<span style="background:#e8f5ee;color:#2a7a50;border:1px solid #a8d8bc;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700">BEAT +{surprise:.1f}%</span>'
        return f'<span style="background:#fceaea;color:#b84040;border:1px solid #e8aaaa;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700">MISS {surprise:.1f}%</span>'

    def _days_chip(days):
        if days == 0:
            return '<span style="background:#fdf4e7;color:#b87820;border:1px solid #e8c88a;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700">TODAY</span>'
        if days == 1:
            return '<span style="background:#eaf3f0;color:#2e6b58;border:1px solid #c6ddd6;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700">TOMORROW</span>'
        if days <= 7:
            return f'<span style="background:#f0f0fc;color:#5560a8;border:1px solid #c0c4ec;border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700">in {days}d</span>'
        return f'<span style="color:var(--text-muted);font-size:11px">in {days}d</span>'

    months_html = ""
    total_shown = 0
    for month_label, events in months.items():
        rows = ""
        for e in events:
            ticker = e["ticker"]
            is_wl = ticker in watchlist_tickers
            star = " ★" if is_wl else ""
            ticker_color = "var(--accent)" if is_wl else "var(--text)"
            company_page = f'stock-{ticker.lower()}.html'
            eps_est = f'${e["eps_estimate"]:.2f}' if e.get("eps_estimate") is not None else "—"
            rev_est = f'${e["revenue_estimate"]/1e9:.1f}B' if e.get("revenue_estimate") else "—"
            prior_eps = f'${e["prior_eps_actual"]:.2f}' if e.get("prior_eps_actual") is not None else "—"
            beat = _beat_badge(e.get("prior_surprise_pct"))
            chip = _days_chip(e.get("days_until", 99))
            rows += f"""
      <tr {'style="background:var(--accent-bg)"' if is_wl else ''}>
        <td style="width:100px;white-space:nowrap">{e['earnings_date']}</td>
        <td>{chip}</td>
        <td><a href="{company_page}" style="color:{ticker_color};font-weight:700;text-decoration:none">{ticker}{star}</a></td>
        <td style="color:var(--text-med)">{e.get('name','')[:30]}</td>
        <td style="text-align:right;font-weight:600">{eps_est}</td>
        <td style="text-align:right">{rev_est}</td>
        <td style="text-align:right">{prior_eps} {beat}</td>
      </tr>"""
            total_shown += 1

        months_html += f"""
  <div class="ec-month">
    <div class="ec-month-label">{month_label}</div>
    <table class="ec-table">
      <thead>
        <tr>
          <th>Date</th><th></th><th>Ticker</th><th>Company</th>
          <th style="text-align:right">EPS Est.</th>
          <th style="text-align:right">Rev Est.</th>
          <th style="text-align:right">Prior EPS · Surprise</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>
  </div>"""

    if not months_html:
        months_html = '<p style="color:var(--text-muted);padding:32px 0">No earnings data available for the next 90 days.</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Earnings Calendar · The Signal Desk</title>
<style>
{SHARED_CSS}
.ec-month {{ margin-bottom: 40px; }}
.ec-month-label {{
  font-size: 13px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 10px; padding-bottom: 6px;
  border-bottom: 2px solid var(--accent-light);
}}
.ec-table {{
  width: 100%; border-collapse: collapse; font-size: 13px;
  background: var(--surface); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow-sm);
}}
.ec-table th {{
  font-size: 10px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.07em;
  background: var(--surface-off); padding: 8px 12px; text-align: left;
  border-bottom: 2px solid var(--border);
}}
.ec-table td {{
  padding: 10px 12px; border-bottom: 1px solid var(--border-light);
  color: var(--text); vertical-align: middle;
}}
.ec-table tbody tr:hover {{ background: var(--surface-off); }}
.ec-table tbody tr:last-child td {{ border-bottom: none; }}
.legend {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 28px; font-size: 12px; color: var(--text-muted); }}
.legend-item {{ display: flex; align-items: center; gap: 6px; }}
@media (max-width: 680px) {{
  .ec-table th:nth-child(4), .ec-table td:nth-child(4),
  .ec-table th:nth-child(6), .ec-table td:nth-child(6) {{ display: none; }}
}}
</style>
</head>
<body>

{_nav_html("earnings-calendar.html")}

<div class="hero">
  <div class="pill">Auto-updated Daily · 自動每日更新</div>
  <h1>Earnings Calendar &nbsp;<span style="font-size:16px;font-weight:400;color:var(--text-muted)">財報日曆</span></h1>
  <p class="hero-sub">Upcoming earnings for major US stocks + your watchlist, auto-fetched from market data. Next 90 days shown. EPS &amp; revenue estimates from analyst consensus.<br>
  <span style="font-size:13px;color:var(--text-muted)">主要美股及個人觀察清單財報日期，自動從市場資料抓取，顯示未來 90 天。EPS 及營收預測來自分析師共識。</span></p>
</div>

<div class="content">
  <div class="legend">
    <div class="legend-item"><span style="color:var(--accent);font-weight:700">★ Highlighted rows</span> = your watchlist stocks</div>
    <div class="legend-item">EPS Est. = analyst EPS consensus for the upcoming quarter</div>
    <div class="legend-item">Prior EPS = most recent actual result + beat/miss vs estimate</div>
  </div>
  <p class="last-updated" style="margin-bottom:28px">Last updated: {updated} &nbsp;·&nbsp; {total_shown} events across 90 days</p>

  {months_html}
</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Earnings Calendar &nbsp;·&nbsp; Auto-fetched from yfinance &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>
</body>
</html>"""

    out_path = os.path.join(PAGES_DIR, "earnings-calendar.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] earnings-calendar.html updated — {total_shown} events")
    return "earnings-calendar.html"


# ── Watchlist conviction page ─────────────────────────────────────────────────

_COMPANY_PAGE_CSS = """
/* ── Hero ── */
.back-link {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; font-weight: 600; color: var(--accent);
  text-decoration: none; margin-bottom: 18px; letter-spacing: 0.03em;
}
.back-link:hover { text-decoration: underline; }
.co-ticker { font-size: 40px; font-weight: 900; letter-spacing: -0.03em; color: var(--text); line-height: 1; }
.co-name   { font-size: 15px; color: var(--text-muted); margin: 4px 0 12px; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.hero-badge {
  display: inline-flex; align-items: center; padding: 5px 14px; border-radius: 8px;
  font-size: 14px; font-weight: 700; font-family: 'Menlo','SF Mono',monospace; border: 1px solid transparent;
}
.badge-price { background: var(--surface); border-color: var(--border); color: var(--text); }
.badge-up    { background: #eaf3f0; border-color: #c6ddd6; color: #2e6b58; }
.badge-dn    { background: #fceaea; border-color: #e8aaaa; color: #b84040; }
.hero-tags   { display: flex; flex-wrap: wrap; gap: 6px; }
.hero-tag    { font-size: 11px; color: var(--text-muted); background: var(--surface-off); border: 1px solid var(--border-light); padding: 3px 10px; border-radius: 20px; }

/* ── KPI tiles ── */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px,1fr)); gap: 12px; margin-bottom: 24px; }
.kpi-tile { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow-sm); }
.kpi-val   { font-size: 22px; font-weight: 900; font-family: 'Menlo','SF Mono',monospace; line-height: 1.1; margin-bottom: 4px; }
.kpi-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); font-weight: 600; }
.kpi-sub   { font-size: 11px; color: var(--text-muted); margin-top: 3px; }

/* ── Conviction score card ── */
.cs-card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 24px; overflow: hidden; }
.cs-card-header { padding: 14px 24px; border-bottom: 1px solid var(--border-light); }
.cs-card-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
.cs-card-sub   { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.cs-body { display: flex; flex-wrap: wrap; gap: 32px; padding: 24px 28px; }
.cs-score-col { display: flex; flex-direction: column; align-items: center; min-width: 80px; }
.cs-score-num { font-size: 64px; font-weight: 900; line-height: 1; font-family: 'Menlo','SF Mono',monospace; }
.cs-score-denom { font-size: 12px; color: var(--text-muted); }
.cs-score-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 4px; text-align: center; }
.cs-pillars-col { flex: 1; min-width: 180px; }
.cs-pillar { margin-bottom: 18px; }
.cs-pillar:last-child { margin-bottom: 0; }
.cs-pillar-head { display: flex; justify-content: space-between; margin-bottom: 6px; }
.cs-pillar-name { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); }
.cs-pillar-pts  { font-size: 12px; font-weight: 700; color: var(--text); font-family: 'Menlo','SF Mono',monospace; }
.cs-bar-track { height: 8px; background: var(--border-light); border-radius: 4px; overflow: hidden; }
.cs-bar-fill  { height: 100%; border-radius: 4px; }
.cs-pillar-sub { font-size: 10px; color: var(--text-muted); margin-top: 4px; }
.cs-checks-col { min-width: 200px; }
.cs-check { display: flex; align-items: center; gap: 7px; margin-bottom: 8px; font-size: 12px; }
.cs-check:last-child { margin-bottom: 0; }
.cs-check-icon  { font-size: 11px; font-weight: 700; width: 14px; flex-shrink: 0; }
.cs-check-name  { flex: 1; color: var(--text-med); }
.cs-check-val   { font-weight: 700; font-family: 'Menlo','SF Mono',monospace; color: var(--text); min-width: 40px; text-align: right; }
.cs-check-thresh { font-size: 10px; color: var(--text-muted); }

/* ── Metrics grid ── */
.metrics-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 24px; }
@media(max-width:740px) { .metrics-grid { grid-template-columns: 1fr; } }
.m-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 22px; box-shadow: var(--shadow-sm); }
.mc-blue  { border-top: 4px solid #3a72b0; }
.mc-teal  { border-top: 4px solid #2e6b58; }
.mc-amber { border-top: 4px solid #b87820; }
.mc-blue .m-title  { color: #3a72b0; border-bottom-color: #b8d4f0; }
.mc-teal .m-title  { color: #2e6b58; border-bottom-color: #c6ddd6; }
.mc-amber .m-title { color: #b87820; border-bottom-color: #e8c88a; }
.m-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: var(--accent); margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border-light); }
.m-row  { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.m-label { font-size: 12px; color: var(--text-muted); flex: 1; line-height: 1.4; }
.m-val  { font-size: 14px; font-weight: 700; font-family: 'Menlo','SF Mono',monospace; color: var(--text); white-space: nowrap; }
.m-def  { font-size: 11px; color: var(--text-muted); line-height: 1.55; margin-bottom: 12px; padding: 5px 9px; background: var(--surface-off); border-radius: var(--radius-sm); border-left: 2px solid var(--border); }
.flag-pass { font-size: 10px; font-weight: 700; color: #2e6b58; background: #eaf3f0; border: 1px solid #c6ddd6; padding: 1px 6px; border-radius: 10px; margin-left: 4px; }
.flag-warn { font-size: 10px; font-weight: 700; color: #b87820; background: #fdf4e7; border: 1px solid #e8c88a; padding: 1px 6px; border-radius: 10px; margin-left: 4px; }

/* ── 52-week range ── */
.range-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 24px; box-shadow: var(--shadow-sm); margin-bottom: 24px; }
.range-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: var(--accent); margin-bottom: 16px; }
.range-bar-track { position: relative; height: 8px; background: var(--border-light); border-radius: 4px; margin-bottom: 12px; }
.range-bar-fill  { position: absolute; top: 0; left: 0; height: 100%; background: linear-gradient(90deg, #c6ddd6, var(--accent)); border-radius: 4px; }
.range-dot { position: absolute; top: 50%; width: 14px; height: 14px; background: var(--accent); border: 2px solid #fff; border-radius: 50%; transform: translate(-50%,-50%); box-shadow: 0 1px 4px rgba(0,0,0,.2); }
.range-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); }
.range-labels strong { color: var(--accent); }

/* ── Analyst & Ownership ── */
.ao-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 24px; box-shadow: var(--shadow-sm); margin-bottom: 24px; }
.ao-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 24px; }
@media(max-width:620px) { .ao-grid { grid-template-columns: 1fr; } }
.ao-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: var(--accent); margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border-light); }
.ao-row   { font-size: 13px; color: var(--text-med); margin-bottom: 7px; line-height: 1.5; }
.ao-row strong { color: var(--text); }
.rec-pill { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 20px; }
.rec-buy  { background: #eaf3f0; color: #2e6b58; border: 1px solid #c6ddd6; }
.rec-hold { background: #fdf4e7; color: #b87820; border: 1px solid #e8c88a; }
.rec-sell { background: #fceaea; color: #b84040; border: 1px solid #e8aaaa; }

/* ── Quarterly trend ── */
.q-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 24px; overflow: hidden; }
.q-card-head { padding: 13px 22px; border-bottom: 1px solid var(--border-light); background: var(--surface-off); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: var(--accent); }
.q-table { width: 100%; border-collapse: collapse; }
.q-table th { padding: 9px 16px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); text-align: left; border-bottom: 1px solid var(--border-light); }
.q-table td { padding: 11px 16px; font-size: 13px; border-bottom: 1px solid var(--border-light); color: var(--text-med); }
.q-table tr:last-child td { border-bottom: none; }
.q-table tbody tr:hover { background: var(--surface-off); }
.q-period { font-weight: 600; color: var(--text); font-size: 12px; white-space: nowrap; }
.q-mono   { font-family: 'Menlo','SF Mono',monospace; font-weight: 600; }
.q-bar-wrap { display: flex; align-items: center; gap: 8px; }
.q-bar-track { width: 70px; height: 6px; background: var(--border-light); border-radius: 3px; overflow: hidden; flex-shrink: 0; }
.q-bar-fill  { height: 100%; background: var(--accent); border-radius: 3px; }
.q-pos { color: #2e6b58; font-weight: 600; }
.q-neg { color: #b84040; font-weight: 600; }

/* ── Historical P/E Context card ── */
.pe-card { background: var(--surface); border: 1px solid var(--border); border-top: 4px solid #3a72b0; border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 24px; padding: 20px 24px; }
.pe-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 8px; }
.pe-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #3a72b0; }
.pe-verdict { font-size: 13px; font-weight: 700; margin-top: 3px; }
.pe-sub { font-size: 12px; color: var(--text-muted); line-height: 1.55; margin-bottom: 14px; }
.pe-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 8px; margin-bottom: 14px; }
.pe-stat { font-size: 20px; font-weight: 800; color: var(--text); }
.pe-lbl  { font-size: 10px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); }
.pe-bar-wrap { }
.pe-bar-track { position: relative; height: 10px; border-radius: 5px; overflow: visible; background: var(--border-light); }
.pe-bar-fill { position: absolute; inset: 0; border-radius: 5px; }
.pe-marker { position: absolute; top: 50%; transform: translate(-50%,-50%); width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; }
.pe-marker-avg { background: #b87820; }
.pe-marker-cur { background: #3a72b0; z-index: 1; }
.pe-bar-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); margin-top: 5px; }

/* ── Analyst Price Target Range card ── */
.tgt-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 24px; padding: 20px 24px; }
.tgt-header { margin-bottom: 14px; }
.tgt-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); }
.tgt-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
.tgt-labels { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.tgt-labels > div { display: flex; flex-direction: column; gap: 2px; }
.tgt-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-muted); }
.tgt-val { font-size: 13px; font-weight: 700; }
.tgt-track { position: relative; display: flex; height: 10px; border-radius: 5px; overflow: hidden; }
.tgt-fill-lo, .tgt-fill-hi { height: 100%; }
.tgt-pin { position: absolute; top: 50%; transform: translate(-50%,-50%); width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; }
.tgt-pin-cur  { background: #3a72b0; z-index: 2; }
.tgt-pin-mean { background: #b87820; z-index: 1; }
.tgt-axis { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); margin-top: 6px; }

/* ── Moat Trend card ── */
.mt-card { background: var(--surface); border: 1px solid var(--border); border-top: 4px solid #2e6b58; border-radius: var(--radius); box-shadow: var(--shadow-sm); margin-bottom: 24px; padding: 20px 24px; }
.mt-header { display: flex; align-items: baseline; gap: 16px; margin-bottom: 6px; }
.mt-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); }
.mt-verdict { font-size: 13px; font-weight: 700; margin-left: auto; }
.mt-sub { font-size: 12px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.5; }
.mt-row { display: grid; grid-template-columns: 38px 1fr 52px 56px; align-items: center; gap: 8px; margin-bottom: 8px; }
.mt-yr { font-size: 11px; font-weight: 600; color: var(--text-muted); }
.mt-bar-wrap { background: var(--border-light); border-radius: 3px; height: 8px; overflow: hidden; }
.mt-bar { height: 100%; border-radius: 3px; transition: width 0.3s; }
.mt-val { font-size: 12px; font-weight: 700; text-align: right; }
.mt-gm { font-size: 11px; color: var(--text-muted); }

/* ── Narrative section cards ── */
.sec-teal   { --sc: #2e6b58; --sc-light: #eaf3f0; --sc-border: #c6ddd6; }
.sec-blue   { --sc: #3a72b0; --sc-light: #eaf2fb; --sc-border: #b8d4f0; }
.sec-amber  { --sc: #b87820; --sc-light: #fdf4e7; --sc-border: #e8c88a; }
.sec-indigo { --sc: #5560a8; --sc-light: #f0f0fc; --sc-border: #c0c4ec; }
.sec-rose   { --sc: #b84040; --sc-light: #fceaea; --sc-border: #e8aaaa; }
.section-card {
  border: 1px solid var(--sc-border); border-top: 4px solid var(--sc);
  border-radius: var(--radius); box-shadow: var(--shadow-sm);
  margin-bottom: 28px; overflow: hidden; background: var(--surface);
}
.section-title {
  font-size: 11px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--sc); background: linear-gradient(135deg, var(--sc-light) 0%, var(--surface) 65%);
  padding: 14px 28px; margin: 0; border-bottom: 1px solid var(--sc-border);
}
.section-body { padding: 28px 32px; }
.section-body p { font-size: 15px; line-height: 1.85; color: var(--text-med); margin-bottom: 14px; }
.section-body p:last-child { margin-bottom: 0; }
.section-body strong { color: var(--text); }
.sub-heading { font-size: 14px; font-weight: 700; color: var(--sc); margin: 22px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--sc-border); }
.sub-heading:first-child { margin-top: 0; }
.impact-line { background: var(--sc-light); border-left: 3px solid var(--sc); padding: 10px 16px; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; margin: 4px 0 14px; font-size: 14.5px; color: var(--text-med); line-height: 1.7; }
.num-item  { display: flex; gap: 14px; align-items: flex-start; margin-bottom: 22px; }
.num-badge { width: 26px; height: 26px; border-radius: 50%; background: var(--sc); color: #fff; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
.num-body  { flex: 1; }
.num-title { font-weight: 700; color: var(--text); margin-bottom: 6px; font-size: 15px; }
.num-body p { margin-bottom: 8px; font-size: 14px; }
.overview-list { margin: 0 0 16px 0; padding-left: 20px; }
.overview-list li { margin-bottom: 11px; color: var(--text-med); font-size: 15px; line-height: 1.78; }
.table-wrap { overflow-x: auto; margin: 10px 0 18px; border-radius: var(--radius-sm); border: 1px solid var(--sc-border); }
.overview-table { width: 100%; border-collapse: collapse; }
.overview-table thead tr { background: linear-gradient(135deg, var(--sc-light) 0%, var(--surface-off) 65%); border-bottom: 1px solid var(--sc-border); }
.overview-table th { padding: 9px 16px; font-size: 10px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--sc); text-align: left; white-space: nowrap; }
.overview-table td { padding: 11px 16px; font-size: 14px; color: var(--text-med); border-bottom: 1px solid var(--border-light); }
.overview-table tr:last-child td { border-bottom: none; }
.overview-table tbody tr:hover { background: var(--surface-off); }

/* ── Narrative section label ── */
.narrative-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: var(--text-muted); margin-bottom: 20px; padding-bottom: 8px; border-bottom: 1px solid var(--border-light); }
"""

_SCORE_PALETTE = {
    "s-teal":  {"color": "#2e6b58", "light": "#eaf3f0", "border": "#c6ddd6"},
    "s-amber": {"color": "#b87820", "light": "#fdf4e7", "border": "#e8c88a"},
    "s-red":   {"color": "#b84040", "light": "#fceaea", "border": "#e8aaaa"},
    "s-muted": {"color": "#6e8a7a", "light": "#f5f7f5", "border": "#d6dfd8"},
}


def _fmt_wl_price(price, currency="USD"):
    if price is None:
        return "N/A"
    if currency == "TWD":
        return f"NT${price:,.0f}"
    return f"${price:,.2f}"


def _fmt_wl_change(pct):
    if pct is None:
        return ""
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def generate_watchlist_page(prices: list) -> str:
    """Write pages/watchlist.html with conviction score cards. Returns filename."""
    from src.analysis.conviction_score import compute_conviction_score

    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    cards_html = ""
    count = 0
    for d in prices:
        if d.get("price") is None:
            continue
        count += 1

        cs = compute_conviction_score(d)
        score = cs["score"]
        label = cs["label"]
        sc = _SCORE_PALETTE.get(cs["color_cls"], _SCORE_PALETTE["s-muted"])

        q, qm = cs["pillar_quality"], cs["pillar_quality_max"]
        g, gm = cs["pillar_growth"], cs["pillar_growth_max"]
        h, hm = cs["pillar_health"], cs["pillar_health_max"]

        currency = d.get("currency", "USD")
        price_str = _fmt_wl_price(d["price"], currency)
        change_pct = d.get("change_pct", 0)
        change_str = _fmt_wl_change(change_pct)
        change_color = "#2e6b58" if change_pct >= 0 else "#b84040"

        pillars_html = ""
        for pname, val, maxv in [("Quality", q, qm), ("Growth", g, gm), ("Health", h, hm)]:
            pct = int(val / maxv * 100) if maxv else 0
            pillars_html += (
                f'<div class="wl-pillar">'
                f'<span class="wl-pillar-name">{pname}</span>'
                f'<div class="wl-bar-track"><div class="wl-bar-fill" style="width:{pct}%;background:{sc["color"]}"></div></div>'
                f'<span class="wl-pillar-val">{val}/{maxv}</span>'
                f'</div>'
            )

        checks_html = ""
        for cname, cval, passing, threshold in cs["checks"]:
            icon = "✓" if passing else "⚠"
            ccolor = "#2e6b58" if passing else "#b87820"
            checks_html += (
                f'<div class="wl-check">'
                f'<span class="wl-check-icon" style="color:{ccolor}">{icon}</span>'
                f'<span class="wl-check-name">{cname}</span>'
                f'<span class="wl-check-val">{cval}</span>'
                f'<span class="wl-check-thresh">{threshold}</span>'
                f'</div>'
            )

        ticker = d.get("ticker", "")
        name = d.get("name", ticker)
        checks_section = f'<div class="wl-section wl-checks-wrap">{checks_html}</div>' if checks_html else ""

        analysis_link = f'stock-{ticker.lower()}.html'
        cards_html += f"""
    <div class="wl-card" style="border-top:4px solid {sc['color']};border:1px solid {sc['border']};border-top:4px solid {sc['color']}">
      <div class="wl-header">
        <div>
          <div class="wl-ticker">{ticker}</div>
          <div class="wl-name">{name}</div>
        </div>
        <div class="wl-price-block">
          <div class="wl-price">{price_str}</div>
          <div class="wl-change" style="color:{change_color}">{change_str}</div>
        </div>
      </div>
      <div class="wl-score-row" style="background:linear-gradient(135deg,{sc['light']} 0%,#ffffff 65%)">
        <span class="wl-score" style="color:{sc['color']}">{score}</span>
        <div class="wl-score-meta">
          <span class="wl-score-denom">/ 100</span>
          <span class="wl-score-label" style="color:{sc['color']}">{label}</span>
        </div>
      </div>
      <div class="wl-section">{pillars_html}</div>
      {checks_section}
      <a class="wl-analysis-link" href="{analysis_link}" style="color:{sc['color']};border-top:1px solid {sc['border']}">View Analysis →</a>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Watchlist · The Signal Desk</title>
<style>
{SHARED_CSS}

.watchlist-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}}
.wl-card {{
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}}
.wl-header {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 18px 12px;
}}
.wl-ticker {{
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -0.01em;
}}
.wl-name {{
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
  max-width: 130px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.wl-price-block {{ text-align: right; }}
.wl-price {{
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  font-family: 'Menlo', 'SF Mono', monospace;
}}
.wl-change {{
  font-size: 12px;
  font-weight: 600;
  font-family: 'Menlo', 'SF Mono', monospace;
}}
.wl-score-row {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
}}
.wl-score {{
  font-size: 42px;
  font-weight: 900;
  line-height: 1;
  font-family: 'Menlo', 'SF Mono', monospace;
}}
.wl-score-denom {{
  font-size: 13px;
  color: var(--text-muted);
  display: block;
}}
.wl-score-label {{
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  display: block;
  margin-top: 3px;
}}
.wl-section {{
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
}}
.wl-section:last-child {{ border-bottom: none; }}
.wl-pillar {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}}
.wl-pillar:last-child {{ margin-bottom: 0; }}
.wl-pillar-name {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
  width: 52px;
  flex-shrink: 0;
}}
.wl-bar-track {{
  flex: 1;
  height: 6px;
  background: var(--border-light);
  border-radius: 3px;
  overflow: hidden;
}}
.wl-bar-fill {{
  height: 100%;
  border-radius: 3px;
}}
.wl-pillar-val {{
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  width: 30px;
  text-align: right;
  font-family: 'Menlo', 'SF Mono', monospace;
}}
.wl-checks-wrap {{ padding-top: 10px; padding-bottom: 10px; }}
.wl-check {{
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  font-size: 12px;
}}
.wl-check:last-child {{ margin-bottom: 0; }}
.wl-check-icon {{ font-size: 11px; font-weight: 700; width: 14px; flex-shrink: 0; }}
.wl-check-name {{ flex: 1; color: var(--text-med); }}
.wl-check-val {{ font-weight: 600; color: var(--text); font-family: 'Menlo', 'SF Mono', monospace; min-width: 44px; text-align: right; }}
.wl-check-thresh {{ font-size: 10px; color: var(--text-muted); margin-left: 4px; }}
.last-updated {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.07em; text-align: right; margin-bottom: 24px; }}
.wl-analysis-link {{
  display: block; padding: 10px 18px;
  font-size: 12px; font-weight: 600; text-decoration: none;
  text-align: right; letter-spacing: 0.04em;
  background: var(--surface-off);
  transition: background 0.15s;
}}
.wl-analysis-link:hover {{ background: var(--accent-bg); }}
</style>
</head>
<body>

{_nav_html("watchlist.html")}

<div class="hero">
  <div class="pill">Live Data · Auto-updated</div>
  <h1>My Watchlist</h1>
  <p class="hero-sub">Conviction scores for each tracked stock — computed from fundamentals across three pillars: Quality, Growth, and Financial Health. Refreshed with every briefing.</p>
</div>

<div class="content">
  <p class="last-updated">Last updated: {updated}</p>
  <div class="watchlist-grid">
{cards_html}
  </div>
</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; Watchlist &nbsp;·&nbsp; Scores based on fundamentals, not AI &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}
</footer>

</body>
</html>"""

    os.makedirs(PAGES_DIR, exist_ok=True)
    out_path = os.path.join(PAGES_DIR, "watchlist.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] watchlist.html updated — {count} stocks")
    return "watchlist.html"


# ── Individual company analysis pages ─────────────────────────────────────────

def _b(val):
    """Format dollar value in billions/millions."""
    if val is None:
        return "N/A"
    b = abs(val) / 1e9
    if b >= 1:
        return f"${b:.1f}B"
    return f"${abs(val)/1e6:.0f}M"


def _mrow(label, val_html, def_text=""):
    """Render one metric row + optional definition line."""
    row = (
        f'<div class="m-row">'
        f'<span class="m-label">{label}</span>'
        f'<span class="m-val">{val_html}</span>'
        f'</div>'
    )
    if def_text:
        row += f'<p class="m-def">{def_text}</p>'
    return row


def _kpi_tile(label, value, sub, color):
    return (
        f'<div class="kpi-tile" style="border-top:3px solid {color}">'
        f'<div class="kpi-val" style="color:{color}">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )


def _fetch_roic_trend_html(ticker: str) -> str:
    """Return a 'Moat Trend' card HTML showing 4-year ROIC + gross margin history.
    Returns empty string on any failure so company page degrades gracefully."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        fin = t.financials          # annual income statement (columns = fiscal years)
        bs  = t.balance_sheet       # annual balance sheet

        if fin is None or fin.empty or bs is None or bs.empty:
            return ""

        years = sorted(fin.columns, reverse=True)[:4]  # up to 4 most-recent fiscal years
        if len(years) < 2:
            return ""

        rows = []
        for yr in years:
            label = str(yr)[:4]
            try:
                rev  = fin.loc["Total Revenue", yr]       if "Total Revenue"       in fin.index else None
                cogs = fin.loc["Cost Of Revenue", yr]     if "Cost Of Revenue"     in fin.index else None
                ebit = fin.loc["EBIT", yr]                if "EBIT"                in fin.index else None
                tax_rate = 0.21
                nopat = ebit * (1 - tax_rate) if ebit else None

                # Invested capital = total equity + total debt - cash
                eq    = bs.loc["Stockholders Equity", yr] if "Stockholders Equity" in bs.index else None
                td    = bs.loc["Long Term Debt", yr]      if "Long Term Debt"      in bs.index else 0
                std   = bs.loc["Current Debt", yr]        if "Current Debt"        in bs.index else 0
                cash  = bs.loc["Cash And Cash Equivalents", yr] if "Cash And Cash Equivalents" in bs.index else 0
                ic = (eq or 0) + (td or 0) + (std or 0) - (cash or 0)

                roic_pct = round(nopat / ic * 100, 1) if (nopat and ic and ic > 0) else None
                gm_pct   = round((rev - cogs) / rev * 100, 1) if (rev and cogs and rev > 0) else None
                rows.append({"year": label, "roic": roic_pct, "gm": gm_pct})
            except Exception:
                rows.append({"year": label, "roic": None, "gm": None})

        if all(r["roic"] is None for r in rows):
            return ""

        # Trend verdict based on most-recent vs oldest available ROIC
        roic_vals = [r["roic"] for r in rows if r["roic"] is not None]
        if len(roic_vals) >= 2:
            delta = roic_vals[0] - roic_vals[-1]
            if delta >= 3:    verdict, vc = "Widening moat ↑", "#2e6b58"
            elif delta <= -3: verdict, vc = "Eroding moat ↓",  "#b84040"
            else:             verdict, vc = "Stable moat →",   "#b87820"
        else:
            verdict, vc = "Insufficient data", "#888"

        # Build mini bar chart for ROIC
        max_roic = max((abs(r["roic"]) for r in rows if r["roic"] is not None), default=1)
        bar_rows = ""
        for r in rows:
            if r["roic"] is not None:
                pct = min(100, abs(r["roic"]) / max(max_roic, 1) * 100)
                color = "#2e6b58" if r["roic"] >= 15 else "#b87820" if r["roic"] >= 8 else "#b84040"
                gm_str = f'{r["gm"]:.0f}%' if r["gm"] is not None else "—"
                bar_rows += (
                    f'<div class="mt-row">'
                    f'  <div class="mt-yr">{r["year"]}</div>'
                    f'  <div class="mt-bar-wrap"><div class="mt-bar" style="width:{pct:.0f}%;background:{color}"></div></div>'
                    f'  <div class="mt-val" style="color:{color}">{r["roic"]:.1f}%</div>'
                    f'  <div class="mt-gm">GM {gm_str}</div>'
                    f'</div>'
                )

        return f"""
<div class="mt-card">
  <div class="mt-header">
    <div class="mt-title">Moat Trend — ROIC &amp; Gross Margin</div>
    <div class="mt-verdict" style="color:{vc}">{verdict}</div>
  </div>
  <div class="mt-sub">Return on Invested Capital measures how efficiently the business generates profit from the capital it uses.
    A rising ROIC over time signals a widening moat — the company is compounding its competitive advantage.</div>
  {bar_rows}
</div>"""
    except Exception:
        return ""


def _fetch_historical_pe_html(ticker: str, current_pe: float) -> str:
    """Return a Historical P/E Context card comparing today's P/E to its 5-year average.
    Uses monthly price history + annual EPS (interpolated). Returns '' on failure."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # Monthly closing prices for 5 years
        hist = t.history(period="5y", interval="1mo")
        if hist is None or hist.empty or len(hist) < 12:
            return ""

        # Annual EPS from t.earnings (index = year, columns include "Earnings")
        earnings = t.earnings
        if earnings is None or earnings.empty:
            return ""
        # Build a {year: eps} dict — yfinance returns annual earnings
        eps_by_year = {}
        for yr in earnings.index:
            try:
                val = float(earnings.at[yr, "Earnings"]) if "Earnings" in earnings.columns else None
                rev = float(earnings.at[yr, "Revenue"])  if "Revenue"  in earnings.columns else None
                # Use EPS from info if available; fallback: divide earnings / shares
                eps_by_year[int(yr)] = val
            except Exception:
                pass
        # Also try t.income_stmt for TTM EPS
        shares = t.info.get("sharesOutstanding") or t.info.get("impliedSharesOutstanding")
        if not eps_by_year or not shares:
            return ""

        # Compute trailing P/E for each month-end using the most recently available annual EPS
        import pandas as pd
        pe_series = []
        hist_sorted = hist.sort_index()
        years_sorted = sorted(eps_by_year.keys())
        for idx, row in hist_sorted.iterrows():
            month_year = idx.year if hasattr(idx, 'year') else int(str(idx)[:4])
            price_pt = float(row["Close"])
            # Use the most recent annual EPS on or before this date's year
            applicable_eps = None
            for yr in reversed(years_sorted):
                if yr <= month_year:
                    raw_eps = eps_by_year[yr]
                    if raw_eps and shares > 0:
                        applicable_eps = raw_eps / shares
                    break
            if applicable_eps and applicable_eps > 0 and price_pt > 0:
                pe = price_pt / applicable_eps
                if 0 < pe < 500:  # sanity filter
                    pe_series.append(pe)

        if len(pe_series) < 12:
            return ""

        avg_pe  = round(sum(pe_series) / len(pe_series), 1)
        min_pe  = round(min(pe_series), 1)
        max_pe  = round(max(pe_series), 1)
        cur_pe  = round(current_pe, 1)

        # Verdict
        pct_vs_avg = (cur_pe - avg_pe) / avg_pe * 100 if avg_pe else 0
        if pct_vs_avg <= -15:
            verdict, vc = f"{abs(pct_vs_avg):.0f}% discount to own history — historically cheap", "#2e6b58"
        elif pct_vs_avg <= -5:
            verdict, vc = f"{abs(pct_vs_avg):.0f}% below 5Y average — modestly cheap", "#2e6b58"
        elif pct_vs_avg <= 5:
            verdict, vc = "In line with 5Y average — fairly valued vs own history", "#3a72b0"
        elif pct_vs_avg <= 15:
            verdict, vc = f"{pct_vs_avg:.0f}% above 5Y average — modestly expensive vs history", "#b87820"
        else:
            verdict, vc = f"{pct_vs_avg:.0f}% premium to 5Y average — historically expensive", "#b84040"

        # Mini sparkline of P/E history using last 24 months (more readable)
        recent_pts = pe_series[-24:] if len(pe_series) >= 24 else pe_series
        sparkline = _sparkline_svg(recent_pts, width=120, height=28)

        # Bar showing current P/E position in historical range
        pe_range = (max_pe - min_pe) or 1
        cur_pos = max(2, min(98, (cur_pe - min_pe) / pe_range * 100))
        avg_pos = max(2, min(98, (avg_pe - min_pe) / pe_range * 100))

        return f"""
<div class="pe-card">
  <div class="pe-header">
    <div>
      <div class="pe-title">Historical P/E Context</div>
      <div class="pe-verdict" style="color:{vc}">{verdict}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:11px;color:var(--text-muted)">2Y P/E trend</div>
      {sparkline}
    </div>
  </div>
  <div class="pe-sub">A P/E of {cur_pe:.0f}x is {'cheap' if pct_vs_avg < -5 else 'expensive' if pct_vs_avg > 5 else 'fair'} relative to
    this company's own 5-year average of {avg_pe:.0f}x. Context matters — a growth company may always trade at a premium,
    but a premium above its own history often signals elevated risk.</div>
  <div class="pe-grid">
    <div><div class="pe-stat">{cur_pe:.1f}x</div><div class="pe-lbl">Current P/E</div></div>
    <div><div class="pe-stat">{avg_pe:.1f}x</div><div class="pe-lbl">5Y Average</div></div>
    <div><div class="pe-stat">{min_pe:.1f}x</div><div class="pe-lbl">5Y Low</div></div>
    <div><div class="pe-stat">{max_pe:.1f}x</div><div class="pe-lbl">5Y High</div></div>
  </div>
  <div class="pe-bar-wrap">
    <div class="pe-bar-track">
      <div class="pe-bar-fill" style="background:linear-gradient(90deg,#eaf3f0,#fdecea);width:100%"></div>
      <div class="pe-marker pe-marker-avg" style="left:{avg_pos:.0f}%" title="5Y average"></div>
      <div class="pe-marker pe-marker-cur" style="left:{cur_pos:.0f}%" title="Current"></div>
    </div>
    <div class="pe-bar-labels">
      <span>{min_pe:.0f}x</span>
      <span>← 5Y range →</span>
      <span>{max_pe:.0f}x</span>
    </div>
  </div>
</div>"""
    except Exception:
        return ""


def generate_company_page(d: dict, quarterly: list, narrative: str, cached_cs: dict = None) -> str:
    """Write pages/stock-{ticker}.html. Returns filename."""
    from src.analysis.conviction_score import compute_conviction_score

    ticker = d.get("ticker", "UNKN")
    name = d.get("name", ticker)
    currency = d.get("currency", "USD")
    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    # ── Price / change ─────────────────────────────────────────────────────────
    price = d.get("price")
    price_str = _fmt_wl_price(price, currency)
    change_pct = d.get("change_pct", 0) or 0
    change_str = _fmt_wl_change(change_pct)
    change_cls = "badge-up" if change_pct >= 0 else "badge-dn"

    # ── Conviction score ───────────────────────────────────────────────────────
    # Use cached_cs (from shared daily cache) if provided, otherwise compute fresh
    cs = cached_cs if cached_cs is not None else compute_conviction_score(d)
    score = cs["score"]
    label = cs["label"]
    sc = _SCORE_PALETTE.get(cs["color_cls"], _SCORE_PALETTE["s-muted"])
    sc_color, sc_light, sc_border = sc["color"], sc["light"], sc["border"]

    # ── Score sparkline (30-day trend from history) ────────────────────────────
    score_sparkline_html = ""
    try:
        _hist_path = os.path.join(PAGES_DIR, "data", "scores_history.json")
        with open(_hist_path) as _hf:
            _sh = _json_mod.load(_hf)
        from datetime import date as _date, timedelta as _td
        _cutoff = str(_date.today() - _td(days=30))
        _pts = [e["score"] for e in _sh.get(ticker, []) if e["date"] >= _cutoff]
        if len(_pts) >= 2:
            score_sparkline_html = (
                f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px">'
                f'<span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">30d trend</span>'
                f'{_sparkline_svg(_pts, width=80, height=22)}'
                f'</div>'
            )
    except Exception:
        pass

    pillars_html = ""
    for pname, val, maxv, desc in [
        ("Quality",   cs["pillar_quality"],    cs["pillar_quality_max"],    "ROIC · FCF Margin · Gross Margin — how efficiently the business earns"),
        ("Growth",    cs["pillar_growth"],     cs["pillar_growth_max"],     "Revenue Growth · Earnings Growth — is the business getting bigger?"),
        ("Health",    cs["pillar_health"],     cs["pillar_health_max"],     "Cash vs Debt · Equity Ratio · Analyst Upside — balance sheet strength"),
        ("Valuation", cs.get("pillar_valuation", 0), cs.get("pillar_valuation_max", 25), f"FCF Yield · Forward P/E — {cs.get('val_verdict','is the price reasonable?')}"),
    ]:
        pct = int(val / maxv * 100) if maxv else 0
        pillars_html += (
            f'<div class="cs-pillar">'
            f'<div class="cs-pillar-head">'
            f'<span class="cs-pillar-name">{pname}</span>'
            f'<span class="cs-pillar-pts">{val} / {maxv}</span>'
            f'</div>'
            f'<div class="cs-bar-track"><div class="cs-bar-fill" style="width:{pct}%;background:{sc_color}"></div></div>'
            f'<p class="cs-pillar-sub">{desc}</p>'
            f'</div>'
        )

    checks_html = ""
    for cname, cval, passing, threshold in cs["checks"]:
        icon, ccolor = ("✓", "#2e6b58") if passing else ("⚠", "#b87820")
        checks_html += (
            f'<div class="cs-check">'
            f'<span class="cs-check-icon" style="color:{ccolor}">{icon}</span>'
            f'<span class="cs-check-name">{cname}</span>'
            f'<span class="cs-check-val">{cval}</span>'
            f'<span class="cs-check-thresh">{threshold}</span>'
            f'</div>'
        )

    # ── KPI highlight tiles ───────────────────────────────────────────────────
    tiles = []
    if d.get("revenue_growth") is not None:
        rg = d["revenue_growth"] * 100
        c = "#2e6b58" if rg >= 10 else "#b87820" if rg >= 0 else "#b84040"
        lbl = "Healthy growth" if rg >= 10 else "Slow growth" if rg >= 0 else "Shrinking"
        tiles.append(_kpi_tile("Revenue Growth", f"{rg:+.1f}%", lbl + " · ≥10% is strong", c))
    if d.get("fcf_margin") is not None:
        fm = d["fcf_margin"] * 100
        c = "#2e6b58" if fm >= 20 else "#b87820" if fm >= 10 else "#b84040"
        lbl = "Strong cash converter" if fm >= 20 else "Moderate" if fm >= 10 else "Weak"
        tiles.append(_kpi_tile("FCF Margin", f"{fm:.1f}%", lbl + " · of every $100 revenue, keeps $" + f"{fm:.0f}" + " as cash", c))
    if d.get("fcf_yield") is not None:
        fy = d["fcf_yield"] * 100
        c = "#2e6b58" if fy >= 4 else "#b87820" if fy >= 2 else "#b84040"
        lbl = "Beats bond yield" if fy >= 4.5 else "Competitive" if fy >= 3 else "Below bond yield"
        tiles.append(_kpi_tile("FCF Yield", f"{fy:.1f}%", lbl + " · 10Y Treasury ~4.5%", c))
    if d.get("roic") is not None:
        r = d["roic"] * 100
        c = "#2e6b58" if r >= 15 else "#b87820" if r >= 10 else "#b84040"
        lbl = f"Earns ${r/100:.2f} per $1 invested"
        tiles.append(_kpi_tile("ROIC", f"{r:.1f}%", lbl + " · ≥15% is strong", c))
    if d.get("analyst_upside_pct") is not None:
        up = d["analyst_upside_pct"]
        c = "#2e6b58" if up >= 10 else "#b87820" if up >= 0 else "#b84040"
        rec = d.get("recommendation", "").upper().replace("_", " ") or "N/A"
        tiles.append(_kpi_tile("Analyst Target", f"{up:+.1f}%", f"Wall St consensus: {rec}", c))
    if d.get("forward_pe") is not None:
        fpe = d["forward_pe"]
        if fpe > 0:
            c = "#2e6b58" if fpe < 18 else "#b87820" if fpe < 30 else "#b84040"
            lbl = "Cheap" if fpe < 15 else "Fair value" if fpe < 22 else "Expensive"
            tiles.append(_kpi_tile("Fwd P/E", f"{fpe:.1f}x", f"{lbl} · pay ${fpe:.0f} per $1 of profit", c))
    if price and d.get("week_52_low") and d.get("week_52_high"):
        low52, high52 = d["week_52_low"], d["week_52_high"]
        pos52 = (price - low52) / (high52 - low52) * 100 if high52 > low52 else 50
        if pos52 >= 80:   pos_lbl, c = "Near 52-wk High", "#b87820"
        elif pos52 >= 60: pos_lbl, c = "Upper Range", "#2e6b58"
        elif pos52 >= 40: pos_lbl, c = "Mid Range", "#3a72b0"
        elif pos52 >= 20: pos_lbl, c = "Lower Range", "#b87820"
        else:             pos_lbl, c = "Near 52-wk Low", "#b84040"
        tiles.append(_kpi_tile("Price Position", pos_lbl, f"{pos52:.0f}% of 52-wk range", c))
    if d.get("beta") is not None:
        beta = d["beta"]
        if beta < 0.8:   b_lbl, c = "Less volatile than market", "#2e6b58"
        elif beta < 1.2: b_lbl, c = "Moves with the market", "#3a72b0"
        elif beta < 1.8: b_lbl, c = "More volatile than market", "#b87820"
        else:            b_lbl, c = "Highly volatile", "#b84040"
        tiles.append(_kpi_tile("Beta", f"{beta:.2f}", b_lbl, c))
    kpi_html = f'<div class="kpi-row">{"".join(tiles)}</div>' if tiles else ""

    # ── 5-year ROIC/margin trend + historical P/E context ─────────────────────
    roic_trend_html = _fetch_roic_trend_html(ticker)
    fpe = d.get("forward_pe") or d.get("trailing_pe")
    historical_pe_html = _fetch_historical_pe_html(ticker, fpe) if fpe and fpe > 0 else ""

    # ── 52-week range bar ──────────────────────────────────────────────────────
    range_html = ""
    if price and d.get("week_52_low") and d.get("week_52_high"):
        low52, high52 = d["week_52_low"], d["week_52_high"]
        pos52 = max(2, min(98, (price - low52) / (high52 - low52) * 100)) if high52 > low52 else 50
        range_html = f"""
<div class="range-card">
  <div class="range-title">52-Week Price Range</div>
  <div class="range-bar-track">
    <div class="range-bar-fill" style="width:{pos52:.1f}%"></div>
    <div class="range-dot" style="left:{pos52:.1f}%"></div>
  </div>
  <div class="range-labels">
    <span>Low: {_fmt_wl_price(low52, currency)}</span>
    <span><strong>Current: {price_str}</strong> &nbsp;({pos52:.0f}% of range)</span>
    <span>High: {_fmt_wl_price(high52, currency)}</span>
  </div>
</div>"""

    # ── Analyst & Ownership ────────────────────────────────────────────────────
    rec_mean = d.get("recommendation_mean")
    if rec_mean is not None:
        if rec_mean <= 1.5:   rec_lbl, rec_cls = "Strong Buy", "rec-buy"
        elif rec_mean <= 2.5: rec_lbl, rec_cls = "Buy",        "rec-buy"
        elif rec_mean <= 3.5: rec_lbl, rec_cls = "Hold",       "rec-hold"
        elif rec_mean <= 4.5: rec_lbl, rec_cls = "Sell",       "rec-sell"
        else:                 rec_lbl, rec_cls = "Strong Sell","rec-sell"
        n_analysts = d.get("analyst_count", "?")
        upside_str = ""
        if d.get("analyst_target") and d.get("analyst_upside_pct") is not None:
            sign = "+" if d["analyst_upside_pct"] >= 0 else ""
            upside_str = f'Target: <strong>{_fmt_wl_price(d["analyst_target"], currency)}</strong> ({sign}{d["analyst_upside_pct"]:.1f}% upside)'
        # Buy / Hold / Sell breakdown
        bhs_html = ""
        rb, rh, rs_cnt = d.get("rec_buy"), d.get("rec_hold"), d.get("rec_sell")
        if rb is not None and rh is not None and rs_cnt is not None:
            total_r = (rb + rh + rs_cnt) or 1
            bhs_html = (
                f'<div class="ao-row" style="margin-top:4px">'
                f'<span style="color:#2e6b58;font-weight:700">{rb} Buy</span>'
                f' &nbsp;·&nbsp; <span style="color:#b87820;font-weight:700">{rh} Hold</span>'
                f' &nbsp;·&nbsp; <span style="color:#b84040;font-weight:700">{rs_cnt} Sell</span>'
                f'</div>'
                f'<div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin:4px 0 6px">'
                f'<div style="width:{rb/total_r*100:.0f}%;background:#2e6b58"></div>'
                f'<div style="width:{rh/total_r*100:.0f}%;background:#b87820"></div>'
                f'<div style="width:{rs_cnt/total_r*100:.0f}%;background:#b84040"></div>'
                f'</div>'
            )
        analyst_col = (
            f'<div class="ao-title">Analyst Consensus</div>'
            f'<div class="ao-row"><strong>{n_analysts}</strong> analysts covering this stock</div>'
            f'<div class="ao-row">Consensus: <span class="rec-pill {rec_cls}">{rec_lbl}</span> (mean {rec_mean:.1f}/5)</div>'
            f'{bhs_html}'
            f'<div class="ao-row">{upside_str}</div>'
        )
    else:
        analyst_col = '<div class="ao-title">Analyst Consensus</div><div class="ao-row" style="color:var(--text-muted)">No analyst data</div>'

    own_parts = []
    if d.get("insider_pct") is not None:
        ins = d["insider_pct"] * 100
        note = "High" if ins >= 10 else "Low" if ins < 1 else ""
        own_parts.append(f'Insider ownership: <strong>{ins:.2f}%</strong>{f" — {note}" if note else ""}')
    if d.get("institutional_pct") is not None:
        inst = d["institutional_pct"] * 100
        own_parts.append(f'Institutional: <strong>{inst:.1f}%</strong>')
    if d.get("short_float") is not None:
        sf = d["short_float"] * 100
        flag = " — elevated short interest" if sf > 10 else ""
        own_parts.append(f'Short interest: <strong>{sf:.1f}%</strong>{flag}')
    ownership_col = (
        f'<div class="ao-title">Ownership</div>'
        + "".join(f'<div class="ao-row">{p}</div>' for p in own_parts)
        if own_parts else
        f'<div class="ao-title">Ownership</div><div class="ao-row" style="color:var(--text-muted)">No data</div>'
    )

    profile_parts = []
    if d.get("beta") is not None:
        b = d["beta"]
        note = "low-volatility" if b < 0.8 else "tracks market" if b < 1.2 else "higher-vol than market"
        profile_parts.append(f'Beta: <strong>{b:.2f}</strong> — {note}')
    if d.get("peg_ratio") is not None:
        pg = d["peg_ratio"]
        note = "attractive" if pg < 1 else "fair" if pg < 2 else "expensive vs growth"
        profile_parts.append(f'PEG ratio: <strong>{pg:.2f}</strong> — {note}')
    if d.get("dividend_yield") is not None:
        dy = d["dividend_yield"] * 100
        profile_parts.append(f'Dividend yield: <strong>{dy:.2f}%</strong>')
    else:
        profile_parts.append('Dividend: <strong>None</strong>')
    if d.get("market_cap"):
        profile_parts.append(f'Market cap: <strong>{_b(d["market_cap"])}</strong>')
    profile_col = (
        '<div class="ao-title">Market Profile</div>'
        + "".join(f'<div class="ao-row">{p}</div>' for p in profile_parts)
    )

    ao_html = f"""
<div class="ao-card">
  <div class="ao-grid">
    <div>{analyst_col}</div>
    <div>{ownership_col}</div>
    <div>{profile_col}</div>
  </div>
</div>"""

    # ── Bear / Base / Bull analyst price target range ─────────────────────────
    target_range_html = ""
    tgt_low  = d.get("target_low")
    tgt_mean = d.get("analyst_target")
    tgt_high = d.get("target_high")
    if tgt_low and tgt_mean and tgt_high and price and price > 0:
        def _tpct(t):
            return (t - price) / price * 100
        lo_pct, me_pct, hi_pct = _tpct(tgt_low), _tpct(tgt_mean), _tpct(tgt_high)
        lo_c = "#b84040" if lo_pct < 0 else "#2e6b58"
        me_c = "#b87820" if abs(me_pct) < 5 else "#2e6b58" if me_pct > 0 else "#b84040"
        hi_c = "#2e6b58"
        lo_sign, me_sign, hi_sign = ("+" if lo_pct >= 0 else ""), ("+" if me_pct >= 0 else ""), "+"
        # Bar: position current price at 0%, range from tgt_low to tgt_high
        span = (tgt_high - tgt_low) or 1
        cur_pos  = max(2, min(98, (price    - tgt_low) / span * 100))
        mean_pos = max(2, min(98, (tgt_mean - tgt_low) / span * 100))
        target_range_html = f"""
<div class="tgt-card">
  <div class="tgt-header">
    <div class="tgt-title">Analyst Price Target Range</div>
    <div class="tgt-sub">Where Wall Street analysts think the stock is headed — low, consensus, and high targets</div>
  </div>
  <div class="tgt-body">
    <div class="tgt-labels">
      <div><span class="tgt-lbl">Bear Target</span><span class="tgt-val" style="color:{lo_c}">{_fmt_wl_price(tgt_low,currency)} ({lo_sign}{lo_pct:.0f}%)</span></div>
      <div><span class="tgt-lbl">Consensus</span><span class="tgt-val" style="color:{me_c}">{_fmt_wl_price(tgt_mean,currency)} ({me_sign}{me_pct:.0f}%)</span></div>
      <div><span class="tgt-lbl">Bull Target</span><span class="tgt-val" style="color:{hi_c}">{_fmt_wl_price(tgt_high,currency)} (+{hi_pct:.0f}%)</span></div>
    </div>
    <div class="tgt-track">
      <div class="tgt-fill-lo"  style="width:{mean_pos:.0f}%;background:linear-gradient(90deg,#fceaea,#fef9ec)"></div>
      <div class="tgt-fill-hi"  style="width:{100-mean_pos:.0f}%;background:linear-gradient(90deg,#fef9ec,#eaf3f0)"></div>
      <div class="tgt-pin tgt-pin-cur"  style="left:{cur_pos:.0f}%" title="Current price"></div>
      <div class="tgt-pin tgt-pin-mean" style="left:{mean_pos:.0f}%" title="Consensus target"></div>
    </div>
    <div class="tgt-axis">
      <span>{_fmt_wl_price(tgt_low,currency)}</span>
      <span style="font-weight:600">▲ Current: {price_str}</span>
      <span>{_fmt_wl_price(tgt_high,currency)}</span>
    </div>
  </div>
</div>"""

    # ── Earnings surprise history ──────────────────────────────────────────────
    earnings_surprise_html = ""
    surprises = d.get("earnings_surprises", [])
    if surprises:
        s_rows = ""
        for s in surprises:
            sp = s.get("surprise_pct")
            if sp is not None:
                sc_s = "#2e6b58" if sp > 0 else "#b84040"
                verdict = f'<span style="color:{sc_s};font-weight:700">{"Beat" if sp > 0 else "Miss"} {sp:+.1f}%</span>'
            else:
                verdict = '<span style="color:var(--text-muted)">—</span>'
            est_str = f'${s["estimate"]:.2f}' if s.get("estimate") is not None else "—"
            act_str = f'${s["actual"]:.2f}'   if s.get("actual")   is not None else "—"
            s_rows += (
                f'<tr><td class="q-period">{s["period"]}</td>'
                f'<td class="q-mono">{est_str}</td>'
                f'<td class="q-mono">{act_str}</td>'
                f'<td>{verdict}</td></tr>'
            )
        earnings_surprise_html = f"""
<div class="q-card">
  <div class="q-card-head">Earnings Surprise History — Did the company beat or miss Wall Street's forecasts?</div>
  <table class="q-table">
    <thead><tr><th>Quarter</th><th>Est. EPS</th><th>Actual EPS</th><th>Result</th></tr></thead>
    <tbody>{s_rows}</tbody>
  </table>
</div>"""

    # ── Valuation card (blue) ──────────────────────────────────────────────────
    val_rows = ""
    if d.get("forward_pe"):
        flag = '<span class="flag-warn">Elevated</span>' if d["forward_pe"] > 30 else '<span class="flag-pass">Reasonable</span>' if d["forward_pe"] < 20 else ""
        val_rows += _mrow("Forward P/E", f'{d["forward_pe"]:.1f}{flag}',
            "Investors pay this many dollars for every $1 projected to be earned next year. Lower = cheaper relative to earnings.")
    if d.get("trailing_pe"):
        val_rows += _mrow("Trailing P/E", f'{d["trailing_pe"]:.1f}',
            "Same concept, but based on the last 12 months of actual reported earnings — no estimates involved.")
    if d.get("peg_ratio") is not None:
        pg = d["peg_ratio"]
        flag = '<span class="flag-pass">✓ Attractive</span>' if pg < 1 else '<span class="flag-warn">Expensive vs growth</span>' if pg > 2 else ""
        val_rows += _mrow("PEG Ratio", f'{pg:.2f}{flag}',
            "P/E divided by the growth rate. Below 1.0 often signals the stock is cheap relative to how fast it's growing.")
    if d.get("price_to_book"):
        val_rows += _mrow("Price / Book", f'{d["price_to_book"]:.1f}x',
            "Share price vs book value of company assets. Above 5x means a large premium — justified only if returns on equity are high.")
    if d.get("analyst_target") and d.get("analyst_upside_pct") is not None:
        sign = "+" if d["analyst_upside_pct"] >= 0 else ""
        upside_cls = "flag-pass" if d["analyst_upside_pct"] >= 10 else "flag-warn" if d["analyst_upside_pct"] < 0 else ""
        upside_flag = f'<span class="{upside_cls}">{sign}{d["analyst_upside_pct"]:.1f}%</span>' if upside_cls else f'{sign}{d["analyst_upside_pct"]:.1f}%'
        val_rows += _mrow("Analyst Target", f'{_fmt_wl_price(d["analyst_target"], currency)} {upside_flag}',
            f'Wall Street consensus price target. Current recommendation: <strong>{d.get("recommendation","").upper().replace("_"," ") or "N/A"}</strong>.')
    if d.get("eps_current") is not None:
        eps_dir = d.get("eps_revision_dir", "stable")
        if eps_dir == "rising":
            dir_flag = '<span class="flag-pass">↑ Rising — analysts more bullish</span>'
        elif eps_dir == "falling":
            dir_flag = '<span class="flag-warn">↓ Falling — analysts cutting forecasts</span>'
        else:
            dir_flag = "→ Stable"
        old_str = f' (was ${d["eps_60d_ago"]:.2f} 60d ago)' if d.get("eps_60d_ago") else ""
        val_rows += _mrow("EPS Est. Revision",
            f'${d["eps_current"]:.2f}{old_str} {dir_flag}',
            "Are Wall Street analysts raising or lowering their earnings forecasts over the past 60 days? "
            "Rising estimates = analysts see better results ahead (bullish signal). "
            "Falling estimates = forecasts being cut, increasing risk of an earnings miss.")
    if not val_rows:
        val_rows = '<p class="m-def">Valuation data unavailable.</p>'

    # ── Quality card (teal) ────────────────────────────────────────────────────
    qual_rows = ""
    if d.get("roic") is not None:
        r = d["roic"] * 100
        flag = '<span class="flag-pass">✓ Strong</span>' if r >= 15 else '<span class="flag-warn">⚠ Weak</span>'
        qual_rows += _mrow("ROIC", f'{r:.1f}%{flag}',
            "Return on Invested Capital — profit generated per dollar put to work. Above 15% separates great businesses from average ones.")
    if d.get("fcf_margin") is not None:
        fm = d["fcf_margin"] * 100
        flag = '<span class="flag-pass">✓ Strong</span>' if fm >= 20 else '<span class="flag-warn">⚠ Low</span>' if fm < 10 else ""
        qual_rows += _mrow("FCF Margin", f'{fm:.1f}%{flag}',
            "Free cash left after all operating costs as a % of revenue. Businesses above 20% generate cash even through downturns.")
    if d.get("gross_margin") is not None:
        gm2 = d["gross_margin"] * 100
        flag = '<span class="flag-pass">✓</span>' if gm2 >= 40 else ""
        qual_rows += _mrow("Gross Margin", f'{gm2:.1f}%{flag}',
            "Revenue minus cost of goods sold. Higher = more pricing power. Above 40% typically indicates a differentiated product.")
    if d.get("operating_margin") is not None:
        qual_rows += _mrow("Operating Margin", f'{d["operating_margin"]*100:.1f}%',
            "What remains after paying staff, rent, and all operating costs — before interest and taxes.")
    if d.get("net_margin") is not None:
        qual_rows += _mrow("Net Margin", f'{d["net_margin"]*100:.1f}%',
            "The bottom line: final profit as a % of revenue after every expense including taxes.")
    if d.get("return_on_equity") is not None:
        roe = d["return_on_equity"] * 100
        flag = '<span class="flag-pass">✓</span>' if roe >= 15 else ""
        qual_rows += _mrow("ROE", f'{roe:.1f}%{flag}',
            "Return on Equity — net income divided by shareholders' equity. Above 15% shows efficient use of investor capital.")
    if d.get("capex_ratio") is not None:
        cr = d["capex_ratio"] * 100
        if cr < 5:   cx_lbl, cx_c = "Capital-light ✓", "#2e6b58"
        elif cr < 15: cx_lbl, cx_c = "Moderate capex",  "#3a72b0"
        else:         cx_lbl, cx_c = "Capital-intensive", "#b87820"
        qual_rows += _mrow("Capex / Revenue", f'<span style="color:{cx_c}">{cr:.1f}% — {cx_lbl}</span>',
            "How much of each dollar of sales is reinvested in property and equipment. "
            "Below 5% = capital-light (software, brands) — cash flows freely. "
            "Above 15% = capital-intensive (factories, infrastructure) — heavy ongoing investment required.")
    if d.get("buyback_yield") is not None:
        by = d["buyback_yield"] * 100
        if by >= 3:   by_lbl, by_c = "Aggressive return to shareholders ✓", "#2e6b58"
        elif by >= 1: by_lbl, by_c = "Modest buyback program",             "#3a72b0"
        else:         by_lbl, by_c = "Minimal buybacks",                   "#888"
        qual_rows += _mrow("Buyback Yield", f'<span style="color:{by_c}">{by:.1f}% — {by_lbl}</span>',
            "How much of the company's market value is returned to shareholders via share repurchases each year. "
            "Buybacks reduce share count, boosting future earnings per share. "
            "Works like a tax-efficient dividend — a sign management believes shares are undervalued.")
    if d.get("rnd_ratio") is not None:
        rd = d["rnd_ratio"] * 100
        qual_rows += _mrow("R&amp;D / Revenue", f'{rd:.1f}%',
            "Research &amp; development spending as % of sales. "
            "High R&amp;D = investing aggressively in future products and competitive advantages. "
            "The trade-off: R&amp;D reduces current profit margins but may build tomorrow's moat.")
    if not qual_rows:
        qual_rows = '<p class="m-def">Quality data unavailable.</p>'

    # ── Health card (amber) ────────────────────────────────────────────────────
    health_rows = ""
    if d.get("total_cash"):
        health_rows += _mrow("Cash on Hand", _b(d["total_cash"]))
    if d.get("total_debt") is not None:
        debt_val = d["total_debt"] or 0
        health_rows += _mrow("Total Debt", _b(debt_val) if debt_val else '<span class="flag-pass">Debt-free</span>')
        if d.get("total_cash") and debt_val > 0:
            ratio = d["total_cash"] / debt_val
            flag = '<span class="flag-pass">✓ Covered</span>' if ratio >= 1 else '<span class="flag-warn">⚠ Leveraged</span>'
            health_rows += _mrow("Cash / Debt", f'{ratio:.1f}x{flag}',
                "Times cash covers total debt. Above 1x means the company can pay off all debt immediately from its cash pile.")
    if d.get("equity_ratio") is not None:
        eq = d["equity_ratio"] * 100
        flag = '<span class="flag-pass">✓ Strong</span>' if eq >= 45 else '<span class="flag-warn">⚠ Leveraged</span>' if eq < 30 else ""
        health_rows += _mrow("Equity Ratio", f'{eq:.0f}%{flag}',
            "Shareholders' equity as % of total assets. Higher = less reliance on borrowed money to fund the business.")
    if d.get("current_ratio") is not None:
        cr = d["current_ratio"]
        flag = '<span class="flag-pass">✓</span>' if cr >= 1.5 else '<span class="flag-warn">⚠</span>' if cr < 1 else ""
        health_rows += _mrow("Current Ratio", f'{cr:.1f}{flag}',
            "Short-term assets vs short-term liabilities. Above 1.5 = strong liquidity buffer; below 1.0 = potential cash crunch.")
    if d.get("working_capital") is not None:
        wc = d["working_capital"]
        flag = '<span class="flag-pass">Positive</span>' if wc >= 0 else '<span class="flag-warn">Negative</span>'
        health_rows += _mrow("Working Capital", f'{_b(wc)}&nbsp;{flag}',
            "Day-to-day cash buffer. Positive means the company can fund operations without tapping credit lines.")
    if d.get("retained_earnings") is not None:
        health_rows += _mrow("Retained Earnings", _b(d["retained_earnings"]),
            "Cumulative profits reinvested in the business over its lifetime — a proxy for long-term wealth creation.")
    if d.get("interest_coverage") is not None:
        ic = d["interest_coverage"]
        if ic >= 15:   ic_lbl, ic_c = f"Fortress ✓ — covers interest {ic:.0f}× over", "#2e6b58"
        elif ic >= 5:  ic_lbl, ic_c = f"Healthy — {ic:.1f}× coverage",                 "#3a72b0"
        elif ic >= 2:  ic_lbl, ic_c = f"Thin — {ic:.1f}× coverage ⚠",                  "#b87820"
        else:          ic_lbl, ic_c = f"Danger zone — only {ic:.1f}× ⚠",               "#b84040"
        health_rows += _mrow("Interest Coverage",
            f'<span style="color:{ic_c}">{ic_lbl}</span>',
            "Operating profit divided by annual interest payments. "
            "A ratio of 10× means the company earns 10 times more than it needs to service its debt — very safe. "
            "Below 2× is a warning: one bad quarter could create a liquidity crisis.")
    if not health_rows:
        health_rows = '<p class="m-def">Financial health data unavailable.</p>'

    # ── Quarterly trend ────────────────────────────────────────────────────────
    if quarterly:
        revenues = [q["revenue"] for q in quarterly if q.get("revenue")]
        max_rev = max(revenues) if revenues else 1
        q_rows = ""
        for i, q in enumerate(quarterly):
            rev = q.get("revenue")
            bar_pct = int(rev / max_rev * 100) if rev else 0
            rev_str = _b(rev) if rev else "N/A"
            gm_str = f'{q["gross_margin"]*100:.1f}%' if q.get("gross_margin") else "N/A"
            net_str = _b(q["net_income"]) if q.get("net_income") else "N/A"
            qoq = ""
            if i + 1 < len(quarterly) and rev and quarterly[i + 1].get("revenue"):
                prev_rev = quarterly[i + 1]["revenue"]
                pct = (rev - prev_rev) / abs(prev_rev) * 100
                sign = "+" if pct >= 0 else ""
                cls_qoq = "q-pos" if pct >= 0 else "q-neg"
                qoq = f'<span class="{cls_qoq}">{sign}{pct:.1f}%</span>'
            q_rows += (
                f'<tr><td><span class="q-period">{q["period"]}</span></td>'
                f'<td class="q-mono">{rev_str}</td>'
                f'<td><div class="q-bar-wrap">'
                f'<div class="q-bar-track"><div class="q-bar-fill" style="width:{bar_pct}%"></div></div>'
                f'{qoq}</div></td>'
                f'<td class="q-mono">{gm_str}</td>'
                f'<td class="q-mono">{net_str}</td></tr>'
            )
        quarterly_html = (
            f'<div class="q-card"><div class="q-card-head">Quarterly Trend · Last {len(quarterly)} Quarters</div>'
            f'<table class="q-table"><thead><tr>'
            f'<th>Quarter</th><th>Revenue</th><th>Trend / QoQ</th><th>Gross Margin</th><th>Net Income</th>'
            f'</tr></thead><tbody>{q_rows}</tbody></table></div>'
        )
    else:
        quarterly_html = ""

    # ── AI narrative ───────────────────────────────────────────────────────────
    narrative_html = _render_overview(narrative) if narrative else (
        '<p style="color:var(--text-muted);padding:20px 0">Analysis generating — check back after the next briefing run.</p>'
    )

    # ── Hero tags ──────────────────────────────────────────────────────────────
    tags_html = ""
    if d.get("market_cap"):
        tags_html += f'<span class="hero-tag">Market Cap: {_b(d["market_cap"])}</span>'
    if d.get("sector"):
        tags_html += f'<span class="hero-tag">{d["sector"]}</span>'
    if d.get("industry") and d.get("industry") != d.get("sector"):
        tags_html += f'<span class="hero-tag">{d["industry"]}</span>'
    if d.get("currency"):
        tags_html += f'<span class="hero-tag">{d["currency"]}</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ticker} · Company Analysis · The Signal Desk</title>
<style>
{SHARED_CSS}
{_COMPANY_PAGE_CSS}
</style>
</head>
<body>

{_nav_html()}

<div class="hero">
  <a class="back-link" href="top-picks.html">← Top Picks</a>
  <div class="co-ticker">{ticker}</div>
  <div class="co-name">{name}</div>
  <div class="hero-badges">
    <span class="hero-badge badge-price">{price_str}</span>
    <span class="hero-badge {change_cls}">{change_str}</span>
  </div>
  <div class="hero-tags">{tags_html}</div>
</div>

<div class="content">

  {kpi_html}

  <div class="cs-card" style="border-top:4px solid {sc_color};border:1px solid {sc_border};border-top:4px solid {sc_color}">
    <div class="cs-card-header" style="background:linear-gradient(135deg,{sc_light} 0%,var(--surface) 65%)">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <div class="cs-card-title" style="color:{sc_color}">Conviction Score</div>
          <div class="cs-card-sub">Deterministic score from fundamentals — no AI guesswork</div>
        </div>
        {score_sparkline_html}
      </div>
    </div>
    <div class="cs-body">
      <div class="cs-score-col">
        <div class="cs-score-num" style="color:{sc_color}">{score}</div>
        <div class="cs-score-denom">/ 100</div>
        <div class="cs-score-label" style="color:{sc_color}">{label}</div>
      </div>
      <div class="cs-pillars-col">{pillars_html}</div>
      <div class="cs-checks-col">{checks_html}</div>
    </div>
  </div>

  <div class="metrics-grid">
    <div class="m-card mc-blue">
      <div class="m-title">Valuation</div>
      {val_rows}
    </div>
    <div class="m-card mc-teal">
      <div class="m-title">Quality &amp; Profitability</div>
      {qual_rows}
    </div>
    <div class="m-card mc-amber">
      <div class="m-title">Financial Health</div>
      {health_rows}
    </div>
  </div>

  {range_html}

  {target_range_html}

  {ao_html}

  {quarterly_html}

  {earnings_surprise_html}

  {roic_trend_html}

  {historical_pe_html}

  <p class="narrative-label">Analyst Briefing · AI-generated · {updated}</p>
  {narrative_html}

</div>

<footer>
  The Signal Desk &nbsp;·&nbsp; {ticker} Company Analysis &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')} &nbsp;·&nbsp;
  <a href="top-picks.html" style="color:var(--accent);text-decoration:none">← Back to Top Picks</a>
</footer>

</body>
</html>"""

    os.makedirs(PAGES_DIR, exist_ok=True)
    filename = f"stock-{ticker.lower()}.html"
    with open(os.path.join(PAGES_DIR, filename), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] {filename} written — conviction {score}/100 ({label})")
    return filename


def generate_signal_log_page(signals: list = None) -> str:
    """Generate pages/signal-log.html — trade signal outcome tracker."""
    import json as _j
    now = datetime.now(tz=TAIPEI_TZ)
    updated = now.strftime("%B %d, %Y · %H:%M Taipei")

    if signals is None:
        log_path = os.path.join(os.path.dirname(PAGES_DIR), "signal_log.json")
        try:
            with open(log_path) as f:
                signals = _j.load(f)
        except Exception:
            signals = []

    wins   = [s for s in signals if s.get("outcome_label") == "WIN"]
    losses = [s for s in signals if s.get("outcome_label") == "LOSS"]
    pending = [s for s in signals if s.get("outcome_label") == "PENDING"]
    win_rate = round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0
    avg_win  = round(sum(s.get("outcome_pct", 0) for s in wins) / len(wins), 1) if wins else 0
    avg_loss = round(sum(s.get("outcome_pct", 0) for s in losses) / len(losses), 1) if losses else 0

    stats_html = ""
    if signals:
        stats_html = f"""
  <div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:28px;">
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 22px;min-width:110px;text-align:center;">
      <div style="font-size:26px;font-weight:800">{len(signals)}</div>
      <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">Total Signals</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid #2e6b58;border-radius:var(--radius);padding:16px 22px;min-width:110px;text-align:center;">
      <div style="font-size:26px;font-weight:800;color:#2e6b58">{win_rate}%</div>
      <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">Win Rate</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid #2e6b58;border-radius:var(--radius);padding:16px 22px;min-width:110px;text-align:center;">
      <div style="font-size:26px;font-weight:800;color:#2e6b58">+{avg_win}%</div>
      <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">Avg Win</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-top:3px solid #b84040;border-radius:var(--radius);padding:16px 22px;min-width:110px;text-align:center;">
      <div style="font-size:26px;font-weight:800;color:#b84040">{avg_loss}%</div>
      <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">Avg Loss</div>
    </div>
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 22px;min-width:110px;text-align:center;">
      <div style="font-size:26px;font-weight:800;color:#b87820">{len(pending)}</div>
      <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em">Pending</div>
    </div>
  </div>"""

    rows_html = ""
    for s in sorted(signals, key=lambda x: x.get("timestamp", ""), reverse=True):
        ol = s.get("outcome_label", "PENDING")
        op = s.get("outcome_pct")
        if ol == "WIN":
            row_color = "#2e6b58"; badge_bg = "#eaf3f0"
        elif ol == "LOSS":
            row_color = "#b84040"; badge_bg = "#fdecea"
        else:
            row_color = "#b87820"; badge_bg = "#fef9ec"
        op_str = f'{op:+.1f}%' if op is not None else "—"
        ts = s.get("timestamp", "")[:16].replace("T", " ")
        rows_html += f"""
    <tr>
      <td style="color:var(--text-muted);font-size:12px">{ts}</td>
      <td><strong>{s.get('ticker','')}</strong></td>
      <td><span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;background:{badge_bg};color:{row_color}">{s.get('action','')}</span></td>
      <td>${s.get('price', 0):.2f}</td>
      <td style="color:{row_color};font-weight:700">{op_str}</td>
      <td><span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;background:{badge_bg};color:{row_color}">{ol}</span></td>
    </tr>"""

    if not rows_html:
        table_html = '<p style="color:var(--text-muted);padding:24px 0">No signals recorded yet. Signals will appear here once the intraday alert system generates its first trade signal.<br><br>尚無訊號記錄。盤中警示系統產生第一筆交易訊號後，記錄將顯示於此。</p>'
    else:
        table_html = f"""
  <div style="overflow-x:auto">
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead><tr style="border-bottom:2px solid var(--border)">
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">Date / Time</th>
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">Ticker</th>
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">Action</th>
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">Entry</th>
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">P&L</th>
      <th style="padding:6px 0 10px;font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;text-align:left">Outcome</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Signal Log · The Signal Desk</title>
<style>
{SHARED_CSS}
</style>
</head>
<body>
{_nav_html("signal-log.html")}
<div class="hero">
  <div class="pill">Track Record · 訊號追蹤</div>
  <h1>Signal Log <span style="font-size:16px;font-weight:400;color:var(--text-muted)">訊號記錄</span></h1>
  <p class="hero-sub">Complete track record of all intraday buy/sell signals generated by The Signal Desk.<br>
  <span style="font-size:13px;color:var(--text-muted)">所有盤中買賣訊號的完整記錄與結果追蹤。</span></p>
</div>
<div class="content">
  <p style="font-size:12px;color:var(--text-muted);margin-bottom:24px">Last updated: {updated}</p>
  {stats_html}
  {table_html}
</div>
<footer>The Signal Desk &nbsp;·&nbsp; Signal Log &nbsp;·&nbsp; {now.strftime('%Y-%m-%d')}</footer>
</body>
</html>"""

    os.makedirs(PAGES_DIR, exist_ok=True)
    out_path = os.path.join(PAGES_DIR, "signal-log.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Pages] signal-log.html written ({len(signals)} signals)")
    return "signal-log.html"
