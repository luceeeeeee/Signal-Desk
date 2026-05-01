"""
Logs every intraday alert and tracks whether the signal was correct.
After 30+ entries, accuracy stats print automatically so you know if
the signal has any real predictive value before trusting it with money.
"""
import json
import os
import warnings
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
TRACKER_FILE = os.path.join(DATA_DIR, "signal_log.json")


def log_signal(ticker: str, signal: str, price: float) -> None:
    """Record a fired alert. Call this whenever an alert is actually sent."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(TRACKER_FILE) as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log = []

    now = datetime.now(TAIPEI_TZ)
    log.append({
        "ticker": ticker,
        "signal": signal,           # "buy_zone" or "sell_zone"
        "price_at_alert": price,
        "fired_at": now.isoformat(),
        "check_1d_at": (now + timedelta(days=1)).isoformat(),
        "check_5d_at": (now + timedelta(days=5)).isoformat(),
        "check_10d_at": (now + timedelta(days=10)).isoformat(),
        "outcome_1d": None,         # % price change after 1 day
        "outcome_5d": None,
        "outcome_10d": None,
        "correct_1d": None,         # True if signal direction matched
        "correct_5d": None,
        "correct_10d": None,
    })

    with open(TRACKER_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)
    print(f"  [Tracker] Logged {signal} for {ticker} @ {price}")


def update_outcomes() -> None:
    """
    Fetch current prices for past signals whose check windows have passed,
    fill in outcome_Nd and correct_Nd, then print accuracy stats.
    Run this once daily.
    """
    if not os.path.exists(TRACKER_FILE):
        return

    try:
        with open(TRACKER_FILE) as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    now = datetime.now(TAIPEI_TZ)

    # Collect tickers that have pending outcome checks
    pending = set()
    for entry in log:
        for p in ["1d", "5d", "10d"]:
            if entry.get(f"outcome_{p}") is None:
                check_dt = datetime.fromisoformat(entry[f"check_{p}_at"])
                if now >= check_dt:
                    pending.add(entry["ticker"])

    if not pending:
        return

    # Fetch current prices
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import yfinance as yf

    prices: dict[str, float | None] = {}
    for ticker in pending:
        try:
            info = yf.Ticker(ticker).info
            p = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            prices[ticker] = float(p) if p else None
        except Exception:
            prices[ticker] = None

    # Fill outcomes
    changed = False
    for entry in log:
        current = prices.get(entry["ticker"])
        base = entry.get("price_at_alert")
        if current is None or not base:
            continue

        pct = (current - base) / base * 100

        for p in ["1d", "5d", "10d"]:
            if entry.get(f"outcome_{p}") is None:
                check_dt = datetime.fromisoformat(entry[f"check_{p}_at"])
                if now >= check_dt:
                    entry[f"outcome_{p}"] = round(pct, 2)
                    if entry["signal"] == "buy_zone":
                        entry[f"correct_{p}"] = pct > 0
                    else:
                        entry[f"correct_{p}"] = pct < 0
                    changed = True

    if changed:
        with open(TRACKER_FILE, "w") as f:
            json.dump(log, f, indent=2, default=str)
        _print_accuracy(log)


def _print_accuracy(log: list) -> None:
    print("\n  ── Signal Accuracy Report ─────────────────────")
    for p in ["1d", "5d", "10d"]:
        results = [e[f"correct_{p}"] for e in log if e.get(f"correct_{p}") is not None]
        if len(results) >= 5:
            acc = sum(results) / len(results) * 100
            avg_return = sum(
                e[f"outcome_{p}"] * (1 if e["signal"] == "buy_zone" else -1)
                for e in log if e.get(f"outcome_{p}") is not None
            ) / len(results)
            verdict = "✓ Edge detected" if acc >= 55 else "⚠ No edge — review signal"
            print(f"  {p:4s}: {acc:.0f}% correct over {len(results)} calls | avg return {avg_return:+.1f}% | {verdict}")
        else:
            filled = len(results)
            print(f"  {p:4s}: {filled} / 5 minimum results needed")
    print("  ────────────────────────────────────────────────\n")


def print_summary() -> None:
    """Print current accuracy stats on demand."""
    try:
        with open(TRACKER_FILE) as f:
            _print_accuracy(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        print("  [Tracker] No signal log found yet.")
