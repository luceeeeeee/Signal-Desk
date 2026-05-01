import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _watchlist_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "config", "watchlist.json")


def load_watchlist() -> list:
    return load_config(_watchlist_path())["watchlist"]


def load_settings() -> dict:
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    path = os.path.join(base, "config", "settings.json")
    return load_config(path)


def now_taipei() -> datetime:
    return datetime.now(tz=TAIPEI_TZ)


def format_price(price: float, currency: str) -> str:
    if currency == "TWD":
        return f"NT${price:,.1f}"
    return f"${price:,.2f}"


def format_change(change_pct: float) -> str:
    sign = "+" if change_pct >= 0 else ""
    return f"{sign}{change_pct:.2f}%"


def truncate(text: str, max_chars: int = 300) -> str:
    if not text:
        return ""
    return text[:max_chars].rsplit(" ", 1)[0] + "..." if len(text) > max_chars else text
