import yfinance as yf
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from typing import Optional
from src.utils.helpers import load_watchlist

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Broad coverage: major US names + TW names always tracked in the briefing
# regardless of personal watchlist
MAJOR_NAMES = [
    # US Mega-cap
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "AVGO",
    # US Semiconductors
    "AMD", "INTC", "QCOM", "MU", "AMAT", "LRCX", "KLAC", "TXN",
    # US Financials
    "JPM", "BAC", "GS", "MS", "V", "MA",
    # US Healthcare / Consumer
    "LLY", "UNH", "ABBV", "JNJ", "PG", "KO",
    # US Energy
    "XOM", "CVX",
    # TW majors (via US-listed ADRs or local tickers)
    "TSM", "UMC", "ASX",
    "2330.TW", "2303.TW", "2454.TW", "2317.TW", "2382.TW",
]


def _parse_calendar(cal) -> Optional[dict]:
    """Handle both dict (new yfinance) and DataFrame (old yfinance) calendar format."""
    if cal is None:
        return None

    # New yfinance returns a plain dict
    if isinstance(cal, dict):
        earnings_dates = cal.get("Earnings Date")
        if not earnings_dates:
            return None
        # It's a list of date objects
        if isinstance(earnings_dates, list):
            next_date = earnings_dates[0] if earnings_dates else None
        else:
            next_date = earnings_dates

        if next_date is None:
            return None

        if isinstance(next_date, datetime):
            next_date = next_date.date()

        return {
            "earnings_date": str(next_date),
            "eps_estimate": cal.get("Earnings Average"),
            "eps_high": cal.get("Earnings High"),
            "eps_low": cal.get("Earnings Low"),
            "revenue_estimate": cal.get("Revenue Average"),
        }

    # Old yfinance returns a DataFrame
    try:
        if cal.empty:
            return None
        if "Earnings Date" in cal.columns:
            dates = cal["Earnings Date"].dropna().tolist()
        elif "Earnings Date" in cal.index:
            dates = [cal.loc["Earnings Date"]]
        else:
            return None

        if not dates:
            return None

        next_date = dates[0]
        if isinstance(next_date, datetime):
            next_date = next_date.date()

        eps_est = cal.get("Earnings Average", [None])[0] if "Earnings Average" in cal else None
        rev_est = cal.get("Revenue Average", [None])[0] if "Revenue Average" in cal else None
        return {
            "earnings_date": str(next_date),
            "eps_estimate": float(eps_est) if eps_est and str(eps_est) != "nan" else None,
            "revenue_estimate": float(rev_est) if rev_est and str(rev_est) != "nan" else None,
        }
    except Exception:
        return None


def _get_earnings_info(ticker_str: str) -> Optional[dict]:
    try:
        t = yf.Ticker(ticker_str)
        info = t.info or {}
        name = info.get("shortName") or info.get("longName") or ticker_str

        parsed = _parse_calendar(t.calendar)
        if not parsed or not parsed.get("earnings_date"):
            return None

        parsed["ticker"] = ticker_str
        parsed["name"] = name

        # Fetch prior quarter actuals for Q-to-Q comparison
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                eh_sorted = eh.sort_index(ascending=False)
                last = eh_sorted.iloc[0]
                q_label = str(eh_sorted.index[0])
                parsed["prior_quarter"] = q_label[:10]
                eps_act = last.get("epsActual")
                if eps_act is not None and str(eps_act) != "nan":
                    parsed["prior_eps_actual"] = float(eps_act)
                eps_est = last.get("epsEstimate")
                if eps_est is not None and str(eps_est) != "nan":
                    parsed["prior_eps_estimate_q"] = float(eps_est)
                surprise = last.get("surprisePercent")
                if surprise is not None and str(surprise) != "nan":
                    parsed["prior_surprise_pct"] = round(float(surprise) * 100, 1)
        except Exception:
            pass

        return parsed
    except Exception:
        return None


def fetch_earnings_calendar(days_ahead: int = 7) -> list:
    """Fetch earnings for personal watchlist + all major market names."""
    watchlist = load_watchlist()
    watchlist_tickers = {item["ticker"] for item in watchlist}

    # Combine personal watchlist + broad market coverage
    all_tickers = list(watchlist_tickers | set(MAJOR_NAMES))

    today = date.today()
    cutoff_far = today + timedelta(days=days_ahead)

    upcoming = []
    for ticker in all_tickers:
        result = _get_earnings_info(ticker)
        if not result:
            continue
        try:
            ed = datetime.strptime(result["earnings_date"], "%Y-%m-%d").date()
            if today <= ed <= cutoff_far:
                result["days_until"] = (ed - today).days
                result["is_watchlist"] = ticker in watchlist_tickers
                upcoming.append(result)
        except Exception:
            continue

    upcoming.sort(key=lambda x: (x["earnings_date"], not x["is_watchlist"]))
    return upcoming


def format_earnings_for_prompt(earnings: list) -> str:
    if not earnings:
        return "No major earnings reports found in the next 7 days for tracked stocks."

    lines = []
    for e in earnings:
        watchlist_flag = " ★ [YOUR WATCHLIST]" if e.get("is_watchlist") else ""
        days_label = "TODAY" if e["days_until"] == 0 else (
            "TOMORROW" if e["days_until"] == 1 else f"in {e['days_until']} days"
        )

        parts = [f"  {e['ticker']} ({e['name']}) — {e['earnings_date']} ({days_label}){watchlist_flag}"]

        details = []
        if e.get("eps_estimate") is not None:
            details.append(f"EPS estimate: ${e['eps_estimate']:.2f}")
            if e.get("eps_low") and e.get("eps_high"):
                details.append(f"range ${e['eps_low']:.2f}–${e['eps_high']:.2f}")
        if e.get("revenue_estimate") is not None:
            details.append(f"Revenue estimate: ${e['revenue_estimate']/1e9:.1f}B")

        if e.get("prior_eps_actual") is not None:
            prior = f"Prior Q ({e.get('prior_quarter', 'last Q')}): EPS actual ${e['prior_eps_actual']:.2f}"
            if e.get("prior_eps_estimate_q") is not None:
                beat_miss = "beat" if e["prior_eps_actual"] >= e["prior_eps_estimate_q"] else "missed"
                prior += f" vs estimate ${e['prior_eps_estimate_q']:.2f} → {beat_miss}"
            if e.get("prior_surprise_pct") is not None:
                prior += f" ({e['prior_surprise_pct']:+.1f}% surprise)"
            details.append(prior)

        if details:
            parts.append(f"    {' | '.join(details)}")

        lines.append("\n".join(parts))

    return "\n".join(lines)
