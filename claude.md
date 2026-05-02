# The Signal Desk — Project Guidelines for Claude

## Project Overview
A personal daily stock alert system that generates bilingual (English + Traditional Chinese) market briefings, serves a static website via GitHub Pages, and runs an interactive LINE bot. The site lives at https://luceeeeeee.github.io/Signal-Desk. GitHub repo: luceeeeeee/Signal-Desk.

## Core Product Philosophy — TWO LAYERS, BOTH REQUIRED

**Layer 1 — Data (analyst-grade, never simplified):** Every metric shown must be accurate, current, and at full depth. A senior analyst can read raw ROIC, FCF margin, EV/EBITDA, conviction scores, and draw their own conclusions. Never remove or round data for the sake of simplicity.

**Layer 2 — Explanation (plain language, always alongside):** Every metric must also answer: *What is this? Why does it matter? What does good vs. bad look like?* Show both the number AND the plain-language interpretation. Example: "ROIC 120% — earns $1.20 for every $1 invested · excellent (threshold: ≥15%)". A beginner and a professional should both find value on the same page.

**Target user:** Non-professional, amateur, and beginner investors who want to make informed decisions without a finance background. They see "FCF margin" and don't know what it means. The site's job is to remove that confusion without dumbing down the data.

**AI persona:** Patient teacher + rigorous analyst. Write like a senior analyst explaining their reasoning to a smart friend with zero investing background — precise numbers, concrete analogies, no jargon without an immediate plain-language explanation. Bilingual: English block first, then Traditional Chinese (繁體中文).

---

---

## Architecture

- **main.py** — APScheduler orchestrator + LINE bot daemon thread
- **src/fetchers/** — yfinance price data, RSS news feeds, earnings calendar
- **src/analysis/claude_analyst.py** — Claude API calls for briefings, narratives, intraday alerts
- **src/analysis/conviction_score.py** — deterministic 4-pillar scoring (Quality 25 + Growth 25 + Health 25 + Valuation 25 = 100)
- **src/notifications/** — email_sender.py, line_sender.py, line_bot.py (Flask webhook)
- **src/utils/page_generator.py** — all HTML page generation (single source of truth for nav and CSS)
- **pages/** — output directory deployed to Netlify; push to GitHub triggers auto-deploy
- **config/settings.json** — schedule, notification channels, model, site base_url
- **config/watchlist.json** — shared watchlist (LINE bot has per-user watchlists keyed by user_id)

---

## Auto-Deploy Pipeline

Every page regeneration must call `_git_push_pages(label)` after writing HTML. This commits `pages/` and pushes to GitHub → GitHub Actions deploys to GitHub Pages automatically (~60 seconds). Never deploy manually.

---

## Refresh Schedule (Asia/Taipei timezone)

| Job | Time | Notes |
|-----|------|-------|
| Market page | 05:00 daily | Standalone job + called after each briefing |
| Top Picks screener | 05:30 daily | ~70-stock universe, ≥55 score, top 30 |
| Sector Leaders | 05:40 daily | 8 groups, top 5 per group |
| Monthly Overview | 1st & 15th, 05:00 | AI-generated, review + preview |
| TW Briefing | 08:30 daily | Email or LINE |
| US Briefing | 21:00 daily | Email or LINE |
| Intraday poll | Every N min | Only during market hours |
| Signal outcome update | 08:00 daily | Checks past signal outcomes |
| Company pages | 06:00 daily | yfinance data + AI narrative per stock |
| Earnings Calendar | Manual | Updated when quarterly dates are published |

---

## Navigation (6 items — order is fixed)

Earnings Calendar → Market → Top Picks → Sector Leaders → Statement Guide → News Sources

**My Watchlist page is DELETED** — do not re-add it.

**Critical:** `earnings-calendar-2026.html` and `income-statement-guide.html` are static hand-crafted files. They must be patched directly (Python regex on `<nav>`) whenever the nav changes — they do not use `_nav_html()`.

---

## Nav CSS Rules (enforced in SHARED_CSS and static files)

- `nav`: `padding: 0 40px; overflow: hidden;`
- `.nav-brand`: `flex-shrink: 0`
- `.nav-links`: `display: flex; gap: 4px; flex-shrink: 1; min-width: 0;`
- `.nav-links a`: `padding: 5px 10px; white-space: nowrap;`
- Mobile breakpoint: `max-width: 620px` (hide `.nav-links`)

---

## Bilingual Rules

**All content must be bilingual: English first, Traditional Chinese (繁體中文) second. Never Simplified Chinese.**

### Pages (hero sections)
```html
<h1>English Title <span style="font-size:16px;font-weight:400;color:var(--text-muted)">中文標題</span></h1>
<p class="hero-sub">English description.<br>
  <span style="font-size:13px;color:var(--text-muted)">中文說明。</span>
</p>
```

### Briefing emails / LINE messages
English block first, then a blank line, then Chinese block.

### LINE bot welcome message
English block, then `─────────────────────` divider, then Chinese block.

### Company page narratives (AI-generated)
Each of the 5 sections (Business Overview, Recent Developments, Catalysts, Risks, Conclusion) must have: English paragraph, blank line, Chinese paragraph.

---

## Top Picks Rules

- Universe: ~70 well-known US stocks (defined in `TOP_PICKS_UNIVERSE`)
- Score threshold: **≥ 55** (Moderate or better)
- Maximum shown: **top 30**, sorted by conviction score descending
- Strong Conviction (green): ≥ 75 | Moderate (amber): 55–74
- Every stock links to its individual company page
- Hero text must say "≥ 55 / 100" and "top 30"

---

## Sector Leaders Rules

- **8 groups** (ai-semis, big-tech, ev-mobility, financials, healthcare, defense, retail, energy)
- **Top 5 per group** only (`members[:5]`) — never more
- Each member links to its company page
- 👑 = group leader (rank 1, highest conviction score)
- Taiwan stocks should NOT be a separate group — categorize by sector

---

## Company Pages Rules

- Back link: `← Top Picks` (href: `top-picks.html`) — not Watchlist
- Narrative: bilingual, AI-generated, 5 sections
- Daily refresh at 06:00 for financial data + conviction score
- AI narrative is also regenerated daily (acceptable cost; can be optimized to weekly if API costs become a concern)

---

## Market Page Required Sections

1. VIX card (fear gauge)
2. 10Y / 2Y Treasury yield card
3. Global indices table (8 indices with % change)
4. Commodities table
5. Sector rotation bars (ETF performance)
6. Latest headlines — **top 15** (24h window) — each followed by bilingual AI impact sentence (EN + 繁體中文)
7. Today's Market Snapshot card (daily 1D index moves)
8. Upcoming events preview card (next 7 days of earnings)
9. **Warren Buffett-style macro outlook card** — AI-generated weekly, long-term fundamental view. Cached in `pages/data/buffett_cache.json`, regenerated when cache > 7 days old. Bilingual (EN paragraph then ZH paragraph).

---

## News Sources

- Target: **50 RSS feeds** for diversity and fairness
- Regions: GLOBAL, US, UK, EUROPE, ASIA, SG, HK, IN, AU, TW
- Languages: English + Traditional Chinese (zh-TW)
- `max_items` for briefing: 35 | for market page headlines: 15

---

## LINE Bot Rules

- **Per-user watchlists**: keyed by LINE `user_id` → `watchlist_<user_id>.json`
- Shared static site is single-user (no auth); LINE bot is the personalized layer
- Welcome message format: English block / `─────────────────────` / Chinese block
- Keywords: ALL, BRIEF, MARKET, NEWS, CALENDAR, TOP, WATCHLIST, ADD [ticker], REMOVE [ticker], HELP, FEEDBACK, [ticker]
- Runs as daemon thread on port 5001 (Oracle Cloud or local)

---

## Design System

All generated pages share `SHARED_CSS` from `page_generator.py`. Key variables:
- `--accent: #2e6b58` (teal-green)
- `--bg: #f2f5f1`
- `--surface: #ffffff`
- Font: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`
- Conviction colors: green `#2e6b58` (≥75), amber `#b87820` (55–74), red `#b84040` (<55)

Never change these without updating ALL pages consistently.

---

## Conviction Score (4 pillars, deterministic)

| Pillar | Max | Key signals |
|--------|-----|-------------|
| Quality | 25 | ROIC ≥ 15%, FCF margin, gross margin |
| Growth | 25 | Revenue growth ≥ 10%, earnings growth ≥ 10% |
| Health | 25 | Cash/debt ratio, equity ratio, analyst upside |
| Valuation | 25 | FCF yield vs bond rate, Forward P/E thresholds |

Score ≥ 75 = Strong Conviction | 55–74 = Moderate | 35–54 = Weak | <35 = Avoid

---

## Key Files — Do Not Delete

- `pages/earnings-calendar-2026.html` — static, manually curated, patch nav with regex
- `pages/income-statement-guide.html` — static, manually curated, patch nav with regex
- `config/settings.json` — base_url must be `https://luceeeeeee.github.io/Signal-Desk`
- `.gitignore` — `.env`, `signal_log.json`, logs excluded from git
