"""
Daily Stock Alert System — Main Scheduler
Runs two daily briefings + intraday polling loop + LINE bot webhook.
"""
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from src.fetchers.news import fetch_news, format_news_for_prompt
from src.fetchers.prices import fetch_all_prices, fetch_ticker_data, fetch_ticker_technical, fetch_quarterly_data, format_prices_for_prompt, format_prices_for_briefing, fetch_market_sentiment, format_market_sentiment_for_prompt
from src.utils.signal_tracker import log_signal, update_outcomes
from src.fetchers.earnings import fetch_earnings_calendar, format_earnings_for_prompt
from src.analysis.claude_analyst import generate_briefing, generate_intraday_alert, generate_company_narrative
from src.notifications.email_sender import EmailChannel
from src.notifications.line_sender import LineChannel
from src.utils.helpers import load_settings, load_watchlist, now_taipei
from src.utils.page_generator import generate_news_sources_page, generate_monthly_overview_page, generate_company_page, generate_top_picks_page, generate_sector_leaders_page, generate_market_page, generate_earnings_calendar_page, generate_signal_log_page, _fetch_monthly_index_data, _load_scores_cache, _save_scores_cache, PAGES_DIR, TOP_PICKS_UNIVERSE, SECTOR_GROUPS
from src.fetchers.news import NEWS_FEEDS
from src.analysis.claude_analyst import generate_monthly_overview
from src.analysis.conviction_score import compute_conviction_score

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Per-ticker cooldown tracking: ticker -> last alert datetime
_last_alert_sent: dict = {}

# ── Narrative cache (hybrid: 7-day + earnings-day exception) ──────────────────
_NARRATIVE_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "narratives")
os.makedirs(_NARRATIVE_CACHE_DIR, exist_ok=True)


def _narrative_cache_path(ticker: str) -> str:
    return os.path.join(_NARRATIVE_CACHE_DIR, f"{ticker.lower()}.txt")


def _get_cached_narrative(ticker: str, recent_earnings_date: str = None) -> Optional[str]:
    """Return cached narrative if < 7 days old AND no recent earnings. Else None."""
    path = _narrative_cache_path(ticker)
    if not os.path.exists(path):
        return None
    age_days = (datetime.now().timestamp() - os.path.getmtime(path)) / 86400
    if age_days >= 7:
        return None
    # Force refresh if stock just reported earnings in the last 7 days
    if recent_earnings_date:
        try:
            from datetime import date
            ed = datetime.strptime(recent_earnings_date, "%Y-%m-%d").date()
            days_since = (date.today() - ed).days
            if 0 <= days_since <= 7:
                return None  # Fresh earnings → regenerate narrative
        except Exception:
            pass
    with open(path, encoding="utf-8") as f:
        return f.read()


def _save_narrative_cache(ticker: str, narrative: str):
    with open(_narrative_cache_path(ticker), "w", encoding="utf-8") as f:
        f.write(narrative)


def _write_score_to_cache(ticker: str, cs: dict):
    """Merge a single ticker's conviction score into the shared scores cache."""
    existing = _load_scores_cache(max_age_hours=36)
    existing[ticker] = cs
    _save_scores_cache(existing)


def _git_push_pages(label: str = ""):
    """Commit regenerated pages and push to GitHub → triggers GitHub Pages auto-deploy."""
    import subprocess
    repo = os.path.dirname(__file__)
    try:
        # Only push if a remote is configured
        result = subprocess.run(["git", "remote"], capture_output=True, text=True, cwd=repo)
        if not result.stdout.strip():
            return  # No remote configured yet — skip silently

        now = now_taipei()
        msg = f"auto: regenerate pages {now.strftime('%Y-%m-%d %H:%M')} Taipei" + (f" [{label}]" if label else "")
        subprocess.run(["git", "add", "pages/"], cwd=repo, check=True, capture_output=True)

        # Only commit if there are staged changes
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo)
        if diff.returncode == 0:
            return  # Nothing changed

        subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=repo, check=True, capture_output=True)
        print(f"  [Deploy] Pages pushed to GitHub → Netlify deploying...")
    except Exception as e:
        print(f"  [Deploy] Git push skipped: {e}")


def _generate_one_company_page(d: dict, recent_earnings_date: str = None, cached_cs: dict = None):
    """Generate a single company page, using narrative cache when fresh."""
    ticker = d.get("ticker", "")
    try:
        quarterly = fetch_quarterly_data(ticker)
        narrative = _get_cached_narrative(ticker, recent_earnings_date)
        if narrative is None:
            print(f"  [Company Page] {ticker} — generating narrative...")
            narrative = generate_company_narrative(ticker, d, quarterly)
            _save_narrative_cache(ticker, narrative)
        else:
            print(f"  [Company Page] {ticker} — using cached narrative")
        # Write-back: if no cached score, compute and persist so scores stay in sync across all pages
        if cached_cs is None:
            cached_cs = compute_conviction_score(d)
            _write_score_to_cache(ticker, cached_cs)
        generate_company_page(d, quarterly, narrative, cached_cs=cached_cs)
    except Exception as e:
        print(f"  [Company Page] {ticker} failed: {e}")


def run_company_pages(prices: list = None):
    """Generate company pages for watchlist stocks with narrative cache."""
    if prices is None:
        prices = fetch_all_prices()
    # Build a map of recent earnings for cache invalidation
    try:
        recent = {e["ticker"]: e["earnings_date"] for e in fetch_earnings_calendar(days_ahead=0)}
    except Exception:
        recent = {}
    # Load shared daily scores cache written by fetch_top_picks_data()
    _scores_cache = _load_scores_cache()
    for d in prices:
        if not d.get("price"):
            continue
        ticker = d.get("ticker", "")
        _generate_one_company_page(d, recent.get(ticker), cached_cs=_scores_cache.get(ticker))
    _git_push_pages("company-pages")


def run_universe_company_pages(force: bool = False):
    """Generate company pages for the full Top Picks + Sector Leaders universe.
    Runs weekly — uses narrative cache so AI cost is ~once per week per stock.
    Set force=True to regenerate all pages even when HTML and narrative cache are both fresh."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import yfinance as yf

    all_tickers = list({t for g in SECTOR_GROUPS for t in g["tickers"]} | set(TOP_PICKS_UNIVERSE))
    print(f"\n[Universe Pages] Generating pages for {len(all_tickers)} universe stocks (force={force})...")

    try:
        recent = {e["ticker"]: e["earnings_date"] for e in fetch_earnings_calendar(days_ahead=0)}
    except Exception:
        recent = {}

    # Load shared daily scores cache written by fetch_top_picks_data()
    _scores_cache = _load_scores_cache()

    for ticker in all_tickers:
        page_path = os.path.join(PAGES_DIR, f"stock-{ticker.lower()}.html")
        # Skip only if page exists, narrative cache is fresh, AND not forced
        if not force and os.path.exists(page_path) and _get_cached_narrative(ticker, recent.get(ticker)) is not None:
            continue
        try:
            # Use fetch_ticker_data() to get the full data dict (all fields required by cards)
            d = fetch_ticker_data(ticker)
            if not d.get("price"):
                continue
            _generate_one_company_page(d, recent.get(ticker), cached_cs=_scores_cache.get(ticker))
        except Exception as e:
            print(f"  [Universe Page] {ticker} failed: {e}")

    _git_push_pages("universe-pages")


def run_monthly_overview():
    """Generate the monthly market overview page and return its filename."""
    from datetime import date
    import calendar
    now_dt = now_taipei()
    # "Review" = last month, "Preview" = current month
    first_of_month = now_dt.replace(day=1)
    last_month_dt = first_of_month - timedelta(days=1)
    month_review = last_month_dt.strftime("%B %Y")
    month_preview = now_dt.strftime("%B %Y")

    print(f"\n[{now_dt.strftime('%H:%M')}] Generating monthly overview ({month_review} review / {month_preview} preview)...")

    index_data = _fetch_monthly_index_data()

    earnings = fetch_earnings_calendar(days_ahead=31)
    earnings_text = format_earnings_for_prompt(earnings)

    content = generate_monthly_overview(month_review, month_preview, index_data, earnings_text)
    filename = generate_monthly_overview_page(content, month_review, month_preview)
    print(f"  Monthly overview page: pages/{filename}")
    _git_push_pages("monthly-overview")
    return filename


def run_briefing(market: str):
    print(f"\n[{now_taipei().strftime('%H:%M')}] Running {market} briefing...")
    settings = load_settings()

    print("  Fetching news...")
    news = fetch_news(hours_back=24, max_items=settings["analysis"]["max_news_items"])
    news_text = format_news_for_prompt(news)

    print("  Fetching prices...")
    prices = fetch_all_prices()
    base_url = settings.get("site", {}).get("base_url", "")
    if base_url == "FILL_IN_NETLIFY_URL":
        base_url = ""
    prices_text = format_prices_for_briefing(prices, base_url)

    print("  Fetching earnings calendar...")
    earnings = fetch_earnings_calendar(days_ahead=7)
    earnings_text = format_earnings_for_prompt(earnings)

    print("  Fetching market sentiment (VIX, 10Y, sectors)...")
    sentiment = fetch_market_sentiment()
    sentiment_text = format_market_sentiment_for_prompt(sentiment)

    print("  Generating briefing with Claude...")
    briefing = generate_briefing(market, news_text, prices_text, earnings_text, sentiment_text, base_url)

    now = now_taipei()
    subject = (
        f"📈 Morning Brief — TW Market | 早安市場簡報 {now.strftime('%Y-%m-%d')}"
        if market == "TW"
        else f"📈 Evening Brief — US Market | 晚間市場簡報 {now.strftime('%Y-%m-%d')}"
    )

    channel_cfg = settings["notifications"]["briefing"]
    channel_name = channel_cfg["channel"]

    if channel_name == "email":
        ch = EmailChannel()
        recipient = channel_cfg["recipient"]
    else:
        ch = LineChannel()
        # Use line_recipients array if present, otherwise fall back to single recipient
        recipient = channel_cfg.get("line_recipients", channel_cfg.get("recipient", ""))

    ch.send(subject=subject, body=briefing, recipient=recipient)
    print(f"  [{market}] Briefing sent via {channel_name}.")
    generate_market_page()
    _git_push_pages(f"{market}-briefing")


def run_intraday_check():
    settings = load_settings()
    cooldown_hours = settings["intraday"]["alert_cooldown_hours"]
    watchlist = load_watchlist()
    now = now_taipei()

    for item in watchlist:
        ticker = item["ticker"]
        last = _last_alert_sent.get(ticker)
        if last and (now - last).total_seconds() < cooldown_hours * 3600:
            continue

        price_data = fetch_ticker_data(ticker)
        price_data["market"] = item.get("market", "US")

        if not price_data.get("price"):
            continue

        # Merge technical indicators (RSI, MAs, volume) into price_data
        tech = fetch_ticker_technical(ticker)
        price_data.update(tech)

        # Ask Claude to assess the valuation zone
        alert_msg = generate_intraday_alert(ticker, price_data)
        if not alert_msg:
            continue

        # Only send if Claude flagged a buy or sell zone (not fair value / hold)
        lower = alert_msg.lower()
        is_actionable = "buy zone" in lower or "sell zone" in lower

        if is_actionable:
            channel_cfg = settings["notifications"]["intraday_alert"]
            ch = LineChannel() if channel_cfg["channel"] == "line" else EmailChannel()
            ch.send(
                subject=f"[STOCK ALERT] {ticker}",
                body=alert_msg,
                recipient=channel_cfg["recipient"],
            )
            _last_alert_sent[ticker] = now
            # Log for outcome tracking
            signal_type = "buy_zone" if "buy zone" in lower else "sell_zone"
            log_signal(ticker, signal_type, price_data["price"])
            print(f"  [Intraday] Alert sent for {ticker}")
        else:
            print(f"  [Intraday] {ticker}: Fair value — no alert")


def _is_tw_market_hours(now: datetime) -> bool:
    # TWSE: Mon–Fri 09:00–13:30 Taipei
    if now.weekday() >= 5:
        return False
    return now.hour == 9 or (10 <= now.hour <= 13) or (now.hour == 13 and now.minute <= 30)


def _is_us_market_hours(now: datetime) -> bool:
    # NYSE/Nasdaq in Taipei time: Mon–Fri 21:30–04:00 next day
    if now.weekday() >= 5:
        return False
    return now.hour >= 21 or now.hour < 4


def intraday_poll():
    now = now_taipei()
    if _is_tw_market_hours(now) or _is_us_market_hours(now):
        print(f"\n[{now.strftime('%H:%M')}] Intraday poll running...")
        run_intraday_check()
    else:
        print(f"[{now.strftime('%H:%M')}] Market closed — skipping intraday check.")


if __name__ == "__main__":
    settings = load_settings()
    tz = settings["schedule"]["timezone"]
    tw_time = settings["schedule"]["tw_briefing_time"]
    us_time = settings["schedule"]["us_briefing_time"]
    poll_interval = settings["intraday"]["polling_interval_minutes"]

    tw_h, tw_m = map(int, tw_time.split(":"))
    us_h, us_m = map(int, us_time.split(":"))

    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        lambda: run_briefing("TW"),
        CronTrigger(hour=tw_h, minute=tw_m, timezone=tz),
        id="tw_briefing",
        name="TW Pre-market Briefing",
    )
    scheduler.add_job(
        lambda: run_briefing("US"),
        CronTrigger(hour=us_h, minute=us_m, timezone=tz),
        id="us_briefing",
        name="US Pre-market Briefing",
    )
    scheduler.add_job(
        intraday_poll,
        "interval",
        minutes=poll_interval,
        id="intraday_poll",
        name="Intraday Price Poll",
    )
    # Daily outcome tracker: runs at 08:00 Taipei to check prices for past signals
    def run_signal_outcome_update():
        update_outcomes()
        from src.utils.page_generator import generate_signal_log_page
        generate_signal_log_page()
        _git_push_pages("signal-log")

    scheduler.add_job(
        run_signal_outcome_update,
        CronTrigger(hour=8, minute=0, timezone=tz),
        id="signal_outcome_update",
        name="Signal Outcome Tracker",
    )
    # Market page: daily at 05:00 Taipei (standalone, also runs after each briefing)
    scheduler.add_job(
        lambda: (generate_market_page(), _git_push_pages("market-daily")),
        CronTrigger(hour=5, minute=0, timezone=tz),
        id="market_daily",
        name="Market Page Daily Refresh",
    )
    # Top Picks screener: daily at 05:30 Taipei
    scheduler.add_job(
        lambda: (generate_top_picks_page(), _git_push_pages("top-picks")),
        CronTrigger(hour=5, minute=30, timezone=tz),
        id="top_picks",
        name="Top Picks Screener",
    )
    # Sector Leaders: daily at 05:40 Taipei
    scheduler.add_job(
        lambda: (generate_sector_leaders_page(), _git_push_pages("sector-leaders")),
        CronTrigger(hour=5, minute=40, timezone=tz),
        id="sector_leaders",
        name="Sector Leaders Page",
    )
    # Earnings Calendar: daily at 04:50 Taipei (before market page)
    scheduler.add_job(
        lambda: (generate_earnings_calendar_page(), _git_push_pages("earnings-calendar")),
        CronTrigger(hour=4, minute=50, timezone=tz),
        id="earnings_calendar",
        name="Earnings Calendar Auto-update",
    )
    # Company analysis pages (watchlist): daily at 06:00 Taipei
    scheduler.add_job(
        run_company_pages,
        CronTrigger(hour=6, minute=0, timezone=tz),
        id="company_pages",
        name="Company Analysis Pages",
    )
    # Universe company pages (top picks + sector leaders): weekly Sunday 04:00 Taipei
    scheduler.add_job(
        run_universe_company_pages,
        CronTrigger(day_of_week="sun", hour=4, minute=0, timezone=tz),
        id="universe_pages",
        name="Universe Company Pages (weekly)",
    )
    # Monthly overview: 1st of each month at 05:00 Taipei
    scheduler.add_job(
        run_monthly_overview,
        CronTrigger(day=1, hour=5, minute=0, timezone=tz),
        id="monthly_overview",
        name="Monthly Market Overview",
    )
    # Mid-month refresh: 15th of each month at 05:00 Taipei
    scheduler.add_job(
        run_monthly_overview,
        CronTrigger(day=15, hour=5, minute=0, timezone=tz),
        id="monthly_overview_refresh",
        name="Monthly Market Overview Refresh",
    )

    # Regenerate static pages on every startup
    generate_news_sources_page(NEWS_FEEDS)
    _git_push_pages("news-sources")

    # Generate earnings calendar on startup (always fresh)
    print("  Generating Earnings Calendar page...")
    generate_earnings_calendar_page()


    # Generate missing watchlist company pages at startup
    missing = [
        d for d in fetch_all_prices()
        if d.get("price") and not os.path.exists(
            os.path.join(PAGES_DIR, f"stock-{d.get('ticker','').lower()}.html")
        )
    ]
    if missing:
        print(f"  Generating {len(missing)} missing watchlist company page(s)...")
        run_company_pages(missing)

    # Generate monthly overview if this month's page doesn't exist yet
    import os
    monthly_filename = f"monthly-{now_taipei().strftime('%Y-%m')}.html"
    if not os.path.exists(os.path.join(PAGES_DIR, monthly_filename)):
        run_monthly_overview()

    # Generate top picks if page doesn't exist yet
    if not os.path.exists(os.path.join(PAGES_DIR, "top-picks.html")):
        print("  Generating Top Picks page...")
        generate_top_picks_page()

    # Generate sector leaders if page doesn't exist yet
    if not os.path.exists(os.path.join(PAGES_DIR, "sector-leaders.html")):
        print("  Generating Sector Leaders page...")
        generate_sector_leaders_page()

    # Always regenerate market page on startup (live data)
    print("  Generating Market page...")
    generate_market_page()

    # Start LINE bot webhook server in background thread
    line_bot_port = int(os.environ.get("LINE_BOT_PORT", 5001))
    try:
        from src.notifications.line_bot import app as line_app
        bot_thread = threading.Thread(
            target=lambda: line_app.run(host="0.0.0.0", port=line_bot_port, debug=False, use_reloader=False),
            daemon=True,
            name="line-bot-webhook",
        )
        bot_thread.start()
        print(f"  LINE bot webhook running on port {line_bot_port}")
    except Exception as e:
        print(f"  LINE bot webhook not started: {e}")

    print(f"Scheduler started (timezone: {tz})")
    print(f"  TW briefing: {tw_time} | US briefing: {us_time} | Intraday poll: every {poll_interval} min")
    print("  Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
