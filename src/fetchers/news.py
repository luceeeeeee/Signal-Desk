import feedparser
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

NEWS_FEEDS = [
    # ── US & Global (English) ─────────────────────────────────────────────
    {"name": "Bloomberg Markets",    "url": "https://feeds.bloomberg.com/markets/news.rss",                    "region": "GLOBAL", "lang": "en"},
    {"name": "Reuters Business",     "url": "https://feeds.reuters.com/reuters/businessNews",                  "region": "GLOBAL", "lang": "en"},
    {"name": "Reuters Finance",      "url": "https://feeds.reuters.com/reuters/financialsNews",                "region": "GLOBAL", "lang": "en"},
    {"name": "WSJ Markets",          "url": "https://feeds.wsj.com/wsj/xml/rss/3_7031.xml",                   "region": "US",     "lang": "en"},
    {"name": "FT Markets",           "url": "https://www.ft.com/markets?format=rss",                          "region": "GLOBAL", "lang": "en"},
    {"name": "CNBC Business",        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",           "region": "US",     "lang": "en"},
    {"name": "CNBC World Economy",   "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html",            "region": "GLOBAL", "lang": "en"},
    {"name": "MarketWatch",          "url": "https://feeds.marketwatch.com/marketwatch/marketpulse/",          "region": "US",     "lang": "en"},
    {"name": "Yahoo Finance",        "url": "https://finance.yahoo.com/news/rssindex",                        "region": "US",     "lang": "en"},
    {"name": "Fortune",              "url": "https://fortune.com/feed/fortune-feeds/",                        "region": "US",     "lang": "en"},
    {"name": "Barron's",             "url": "https://www.barrons.com/news/rss_news.xml",                      "region": "US",     "lang": "en"},
    {"name": "Seeking Alpha",        "url": "https://seekingalpha.com/market_currents.xml",                   "region": "US",     "lang": "en"},
    {"name": "AP Business",          "url": "https://apnews.com/hub/financial-markets",                       "region": "GLOBAL", "lang": "en"},
    {"name": "The Economist",        "url": "https://www.economist.com/finance-and-economics/rss.xml",         "region": "GLOBAL", "lang": "en"},
    {"name": "Forbes Business",      "url": "https://www.forbes.com/business/feed2/",                         "region": "US",     "lang": "en"},
    {"name": "Business Insider",     "url": "https://feeds.businessinsider.com/custom/all",                   "region": "US",     "lang": "en"},
    {"name": "NPR Business",         "url": "https://feeds.npr.org/1006/rss.xml",                             "region": "US",     "lang": "en"},
    {"name": "Benzinga",             "url": "https://www.benzinga.com/feed",                                   "region": "US",     "lang": "en"},
    {"name": "TheStreet",            "url": "https://www.thestreet.com/rss/index.xml",                        "region": "US",     "lang": "en"},
    {"name": "Motley Fool",          "url": "https://www.fool.com/feeds/index.aspx",                          "region": "US",     "lang": "en"},
    {"name": "Morningstar",          "url": "https://www.morningstar.com/rss/rss.aspx?section=articles",      "region": "US",     "lang": "en"},
    # ── UK & Europe ──────────────────────────────────────────────────────
    {"name": "BBC Business",         "url": "https://feeds.bbci.co.uk/news/business/rss.xml",                 "region": "UK",     "lang": "en"},
    {"name": "BBC Technology",       "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",               "region": "UK",     "lang": "en"},
    {"name": "The Guardian Business","url": "https://www.theguardian.com/uk/business/rss",                    "region": "UK",     "lang": "en"},
    {"name": "DW Business",          "url": "https://rss.dw.com/rdf/rss-en-bus",                              "region": "EUROPE", "lang": "en"},
    {"name": "Euronews Business",    "url": "https://www.euronews.com/rss?level=theme&name=business",         "region": "EUROPE", "lang": "en"},
    # ── Asia-Pacific ─────────────────────────────────────────────────────
    {"name": "Channel NewsAsia",     "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=10416", "region": "SG", "lang": "en"},
    {"name": "Business Times SG",    "url": "https://www.businesstimes.com.sg/rss/all",                       "region": "SG",     "lang": "en"},
    {"name": "SCMP Business",        "url": "https://www.scmp.com/rss/11/feed",                               "region": "HK",     "lang": "en"},
    {"name": "Nikkei Asia",          "url": "https://asia.nikkei.com/rss/feed/ixrss.aspx",                    "region": "ASIA",   "lang": "en"},
    {"name": "Japan Times Business", "url": "https://www.japantimes.co.jp/feed/",                             "region": "JP",     "lang": "en"},
    {"name": "Caixin Global",        "url": "https://www.caixinglobal.com/rss/index.xml",                     "region": "CN",     "lang": "en"},
    {"name": "Economic Times India", "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "region": "IN", "lang": "en"},
    {"name": "Mint Markets",         "url": "https://www.livemint.com/rss/markets",                           "region": "IN",     "lang": "en"},
    {"name": "SMH Business",         "url": "https://www.smh.com.au/rss/business.xml",                        "region": "AU",     "lang": "en"},
    {"name": "Korea Herald Business","url": "http://www.koreaherald.com/rss_business.xml",                    "region": "KR",     "lang": "en"},
    # ── Taiwan (Traditional Chinese) ─────────────────────────────────────
    {"name": "科技新報 TechNews",    "url": "https://technews.tw/feed/",                                       "region": "TW",     "lang": "zh-TW"},
    {"name": "鉅亨網台股",            "url": "https://news.cnyes.com/rss/news/cat/tw_stock",                   "region": "TW",     "lang": "zh-TW"},
    {"name": "鉅亨網美股",            "url": "https://news.cnyes.com/rss/news/cat/us_stock",                   "region": "TW",     "lang": "zh-TW"},
    {"name": "鉅亨網總經",            "url": "https://news.cnyes.com/rss/news/cat/macro",                      "region": "GLOBAL", "lang": "zh-TW"},
    {"name": "經濟日報",              "url": "https://money.udn.com/rssfeed/news/2/1003?ch=money",             "region": "TW",     "lang": "zh-TW"},
    {"name": "工商時報",              "url": "https://www.ctee.com.tw/rss/news.rss",                          "region": "TW",     "lang": "zh-TW"},
    {"name": "MoneyDJ",              "url": "https://www.moneydj.com/KMDJ/RSSFeed/RSSFeed.aspx?cat=ALLNEWS",  "region": "TW",     "lang": "zh-TW"},
    {"name": "中央社財經",            "url": "https://www.cna.com.tw/rss/aall.aspx",                           "region": "TW",     "lang": "zh-TW"},
    {"name": "數位時代",              "url": "https://www.bnext.com.tw/rss",                                   "region": "TW",     "lang": "zh-TW"},
    {"name": "自由財經",              "url": "https://ec.ltn.com.tw/rss/news.xml",                             "region": "TW",     "lang": "zh-TW"},
    {"name": "今周刊",                "url": "https://www.businesstoday.com.tw/rss/rss.aspx",                  "region": "TW",     "lang": "zh-TW"},
    {"name": "天下雜誌財經",          "url": "https://www.cw.com.tw/rss.action",                               "region": "TW",     "lang": "zh-TW"},
    {"name": "聯合財經網",            "url": "https://udn.com/rssfeed/news/2/6638?ch=news",                    "region": "TW",     "lang": "zh-TW"},
    {"name": "商業周刊",              "url": "https://www.businessweekly.com.tw/rss/index.rss",                "region": "TW",     "lang": "zh-TW"},
]


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ").strip()


def _fetch_feed(source: dict, hours_back: int = 24) -> list:
    cutoff = datetime.now(tz=TAIPEI_TZ) - timedelta(hours=hours_back)
    items = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:15]:
            title = _clean_html(getattr(entry, "title", ""))
            summary = _clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            link = getattr(entry, "link", "")

            # Parse published time
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=ZoneInfo("UTC")).astimezone(TAIPEI_TZ)
                except Exception:
                    pass
            if published is None:
                published = datetime.now(tz=TAIPEI_TZ)

            if published < cutoff:
                continue

            if not title:
                continue

            items.append({
                "title": title,
                "summary": summary[:400] if summary else "",
                "url": link,
                "source": source["name"],
                "region": source["region"],
                "lang": source["lang"],
                "published": published.strftime("%Y-%m-%d %H:%M Taipei"),
            })
    except Exception:
        pass
    return items


def _deduplicate(items: list, max_items: int = 20) -> list:
    seen_titles = set()
    result = []
    for item in items:
        key = item["title"][:60].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            result.append(item)
        if len(result) >= max_items:
            break
    return result


def fetch_news(hours_back: int = 24, max_items: int = 20) -> list:
    from collections import defaultdict
    all_items = []
    for source in NEWS_FEEDS:
        all_items.extend(_fetch_feed(source, hours_back=hours_back))

    # Sort newest first
    all_items.sort(key=lambda x: x["published"], reverse=True)

    # Cap at 2 items per source to prevent any one region dominating
    source_counts = defaultdict(int)
    capped = []
    for item in all_items:
        src = item["source"]
        if source_counts[src] < 2:
            capped.append(item)
            source_counts[src] += 1

    return _deduplicate(capped, max_items=max_items)


def format_news_for_prompt(news_items: list) -> str:
    if not news_items:
        return "No news items fetched. Proceed with macro context only."
    lines = []
    for i, item in enumerate(news_items, 1):
        lines.append(
            f"{i}. [{item['source']} | {item['region']}] {item['title']}\n"
            f"   {item['summary']}\n"
            f"   URL: {item['url']}\n"
            f"   Published: {item['published']}"
        )
    return "\n\n".join(lines)
