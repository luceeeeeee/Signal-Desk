"""
LINE Messaging API webhook handler.
Receives user messages and replies with market intelligence.

Run alongside main.py:  python line_bot.py
Or mount into an existing Flask app.
"""
import os
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, abort

try:
    from linebot.v3.webhook import WebhookHandler
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi,
        ReplyMessageRequest, TextMessage,
    )
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

app = Flask(__name__)

CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

if LINE_SDK_AVAILABLE and CHANNEL_SECRET:
    handler = WebhookHandler(CHANNEL_SECRET)
else:
    handler = None


# ── Reply helper ──────────────────────────────────────────────────────────────

def _reply(reply_token: str, text: str):
    if not LINE_SDK_AVAILABLE:
        print(f"[LINE Bot] Would reply: {text[:80]}")
        return
    chunks = [text[i:i+4900] for i in range(0, len(text), 4900)]
    config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
    with ApiClient(config) as client:
        api = MessagingApi(client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(type="text", text=c) for c in chunks[:5]],
            )
        )


# ── Welcome message ───────────────────────────────────────────────────────────

WELCOME_MSG = """\
👋 Welcome to The Signal Desk

This is an automated market intelligence bot. It delivers daily briefings, live stock snapshots, AI-generated company analysis, and earnings alerts — designed to help you stay informed when making investment decisions.

⚠️ This bot provides information only. Nothing here is financial advice. We will never ask for money, personal details, or account access of any kind.

Type ALL to see everything this bot can do.

─────────────────────

👋 歡迎使用 The Signal Desk

這是一個自動化市場資訊機器人，提供每日市場簡報、即時股價快照、AI 生成的公司分析及財報提醒，協助您在投資決策時掌握最新資訊。

⚠️ 本機器人僅提供資訊，內容不構成任何投資建議。我們絕不會要求您提供金錢、個人資料或任何帳戶存取權限。

輸入 ALL 查看所有功能。"""


# ── ALL command ───────────────────────────────────────────────────────────────

ALL_MSG = """\
📋 The Signal Desk — All Commands

ALL        → Show this command list
BRIEF      → Today's market summary
MARKET     → VIX + 10Y yield + sector rotation
NEWS       → Top 5 headlines (last 24h)
CALENDAR   → This week's earnings
TOP        → Top Picks (conviction ≥ 75)
[TICKER]   → e.g. NVDA, AAPL, 0050 — price snapshot + conviction score
ADD [TICKER]    → Add stock to My Watchlist
REMOVE [TICKER] → Remove stock from My Watchlist
WATCHLIST  → Show your current watchlist
HELP       → Report a bot malfunction
FEEDBACK   → Send a suggestion

─────────────────────

📋 The Signal Desk — 所有指令

ALL        → 顯示指令列表
BRIEF      → 今日市場摘要
MARKET     → VIX + 10年期公債殖利率 + 板塊輪動
NEWS       → 最新5則財經新聞（過去24小時）
CALENDAR   → 本週財報行事曆
TOP        → 最強精選（信心分數 ≥ 75）
【股票代號】→ 如 NVDA、AAPL、0050 — 即時股價快照 + 信心分數
ADD 【代號】   → 加入我的自選股
REMOVE 【代號】→ 從自選股移除
WATCHLIST  → 顯示目前自選股清單
HELP       → 回報機器人異常
FEEDBACK   → 提供使用建議"""


# ── Command handlers ──────────────────────────────────────────────────────────

def _handle_brief() -> str:
    try:
        from src.fetchers.news import fetch_news, format_news_for_prompt
        from src.fetchers.prices import fetch_all_prices, format_prices_for_prompt
        from src.fetchers.earnings import fetch_earnings_calendar, format_earnings_for_prompt
        from src.fetchers.prices import fetch_market_sentiment, format_market_sentiment_for_prompt
        from src.analysis.claude_analyst import generate_briefing
        from src.utils.helpers import load_settings

        settings = load_settings()
        now = datetime.now(tz=TAIPEI_TZ)
        market = "TW" if 6 <= now.hour < 14 else "US"

        news_text     = format_news_for_prompt(fetch_news(hours_back=24, max_items=10))
        prices        = fetch_all_prices()
        prices_text   = format_prices_for_prompt(prices)
        earnings_text = format_earnings_for_prompt(fetch_earnings_calendar(days_ahead=7))
        sentiment_text = format_market_sentiment_for_prompt(fetch_market_sentiment())
        briefing = generate_briefing(market, news_text, prices_text, earnings_text, sentiment_text)
        # Trim to LINE-friendly length
        return briefing[:4800] + ("\n\n…（完整內容請見網頁）" if len(briefing) > 4800 else "")
    except Exception as e:
        return f"⚠️ Unable to generate briefing: {e}"


def _handle_market() -> str:
    try:
        from src.fetchers.prices import fetch_market_sentiment, format_market_sentiment_for_prompt
        sentiment = fetch_market_sentiment()
        return "📊 Market Snapshot / 市場快照\n\n" + format_market_sentiment_for_prompt(sentiment)
    except Exception as e:
        return f"⚠️ Market data unavailable: {e}"


def _handle_news() -> str:
    try:
        from src.fetchers.news import fetch_news
        items = fetch_news(hours_back=24, max_items=5)
        if not items:
            return "No recent news found. / 未找到最新新聞。"
        lines = ["📰 Top Headlines / 最新頭條\n"]
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. [{item.get('source','')}] {item.get('title','')}")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ News unavailable: {e}"


def _handle_calendar() -> str:
    try:
        from src.fetchers.earnings import fetch_earnings_calendar, format_earnings_for_prompt
        earnings = fetch_earnings_calendar(days_ahead=7)
        text = format_earnings_for_prompt(earnings)
        return "📅 Earnings This Week / 本週財報\n\n" + (text or "No earnings this week.")
    except Exception as e:
        return f"⚠️ Earnings data unavailable: {e}"


def _handle_top() -> str:
    try:
        from src.fetchers.prices import fetch_ticker_data
        from src.analysis.conviction_score import compute_conviction_score, format_score_for_prompt
        from src.utils.page_generator import TOP_PICKS_UNIVERSE
        results = []
        for ticker in TOP_PICKS_UNIVERSE[:30]:  # limit to 30 for speed
            d = fetch_ticker_data(ticker)
            if not d.get("price"):
                continue
            cs = compute_conviction_score(d)
            if cs["score"] >= 75:
                results.append((cs["score"], ticker, d.get("name",""), d["price"], cs))
        results.sort(reverse=True)
        if not results:
            return "No stocks qualify for Top Picks today. / 今日暫無符合精選條件的股票。"
        lines = ["🏆 Top Picks / 今日精選（信心分數 ≥ 75）\n"]
        for score, ticker, name, price, cs in results[:10]:
            lines.append(f"  {ticker} ({name[:20]}) — {score}/100 · ${price:.2f}")
        lines.append("\n完整清單請見 top-picks.html")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Top Picks unavailable: {e}"


def _handle_ticker(ticker: str) -> str:
    try:
        from src.fetchers.prices import fetch_ticker_data
        from src.analysis.conviction_score import compute_conviction_score, format_score_for_prompt
        from src.utils.helpers import format_price, format_change
        d = fetch_ticker_data(ticker.upper())
        if not d.get("price"):
            return f"❌ Could not fetch data for {ticker.upper()}. Check the symbol and try again.\n無法取得 {ticker.upper()} 的資料，請確認代號後重試。"
        currency = d.get("currency","USD")
        cs = compute_conviction_score(d)
        price_str  = format_price(d["price"], currency)
        change_str = format_change(d["change_pct"])
        rec  = (d.get("recommendation") or "").upper() or "N/A"
        fpe  = f"{d['forward_pe']:.1f}x" if d.get("forward_pe") else "N/A"
        upside = f"+{d['analyst_upside_pct']:.1f}%" if d.get("analyst_upside_pct") and d["analyst_upside_pct"] >= 0 else (f"{d['analyst_upside_pct']:.1f}%" if d.get("analyst_upside_pct") else "N/A")
        score_line = format_score_for_prompt(cs)
        return (
            f"📈 {d['ticker']} — {d.get('name','')}\n"
            f"Price: {price_str}  {change_str}\n"
            f"Fwd P/E: {fpe}  |  Analyst upside: {upside}\n"
            f"Recommendation: {rec}\n"
            f"{score_line}\n\n"
            f"Full analysis → stock-{ticker.lower()}.html"
        )
    except Exception as e:
        return f"⚠️ Error fetching {ticker}: {e}"


def _handle_watchlist_show(user_id: str) -> str:
    from src.utils.helpers import load_watchlist
    wl = load_watchlist()
    if not wl:
        return "Your watchlist is empty. Type ADD [TICKER] to add stocks.\n您的自選股清單是空的。輸入 ADD [代號] 來新增股票。"
    tickers = [f"  • {w['ticker']}" + (f" ({w.get('note','')})" if w.get("note") else "") for w in wl]
    return "📋 My Watchlist / 我的自選股\n\n" + "\n".join(tickers)


def _handle_add(ticker: str) -> str:
    import json
    ticker = ticker.upper().strip()
    if not re.match(r'^[A-Z0-9.\-]{1,10}$', ticker):
        return f"❌ Invalid ticker: {ticker}\n無效的股票代號：{ticker}"
    try:
        from src.fetchers.prices import fetch_ticker_data
        d = fetch_ticker_data(ticker)
        if not d.get("price"):
            return f"❌ {ticker} not found on yfinance. Check the symbol.\n找不到 {ticker}，請確認代號。"
        # Load and update watchlist
        from src.utils.helpers import _watchlist_path
        wl_path = _watchlist_path()
        with open(wl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = [w["ticker"].upper() for w in data.get("watchlist", [])]
        if ticker in existing:
            return f"ℹ️ {ticker} is already in your watchlist.\n{ticker} 已在您的自選股清單中。"
        data["watchlist"].append({"ticker": ticker, "market": "US", "note": ""})
        with open(wl_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Trigger page regeneration in background
        threading.Thread(target=_regen_watchlist, daemon=True).start()
        return f"✅ {ticker} ({d.get('name','')}) added to your watchlist!\n已將 {ticker} 加入您的自選股清單！"
    except Exception as e:
        return f"⚠️ Error adding {ticker}: {e}"


def _handle_remove(ticker: str) -> str:
    import json
    ticker = ticker.upper().strip()
    try:
        from src.utils.helpers import _watchlist_path
        wl_path = _watchlist_path()
        with open(wl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        before = len(data.get("watchlist", []))
        data["watchlist"] = [w for w in data.get("watchlist", []) if w["ticker"].upper() != ticker]
        if len(data["watchlist"]) == before:
            return f"ℹ️ {ticker} was not found in your watchlist.\n{ticker} 不在您的自選股清單中。"
        with open(wl_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        threading.Thread(target=_regen_watchlist, daemon=True).start()
        return f"✅ {ticker} removed from your watchlist.\n已將 {ticker} 從自選股清單移除。"
    except Exception as e:
        return f"⚠️ Error removing {ticker}: {e}"


def _regen_watchlist():
    try:
        from src.fetchers.prices import fetch_all_prices
        from src.utils.page_generator import generate_watchlist_page
        prices = fetch_all_prices()
        generate_watchlist_page(prices)
    except Exception as e:
        print(f"[LINE Bot] Watchlist regen failed: {e}")


def _handle_help(user_id: str, msg: str) -> str:
    owner = os.environ.get("LINE_USER_ID", "")
    # Notify owner
    if owner and owner != user_id and LINE_SDK_AVAILABLE:
        try:
            config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
            with ApiClient(config) as client:
                from linebot.v3.messaging import PushMessageRequest
                MessagingApi(client).push_message(
                    PushMessageRequest(to=owner, messages=[
                        TextMessage(type="text", text=f"🚨 Bot malfunction report from {user_id}:\n{msg}")
                    ])
                )
        except Exception:
            pass
    return (
        "⚠️ Your malfunction report has been sent to the bot administrator. Thank you.\n"
        "We'll look into the issue as soon as possible.\n\n"
        "⚠️ 您的異常回報已傳送給管理員，感謝您的回饋。\n"
        "我們將盡快處理相關問題。"
    )


def _handle_feedback(msg: str) -> str:
    owner = os.environ.get("LINE_USER_ID", "")
    if owner and LINE_SDK_AVAILABLE:
        try:
            config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
            with ApiClient(config) as client:
                from linebot.v3.messaging import PushMessageRequest
                MessagingApi(client).push_message(
                    PushMessageRequest(to=owner, messages=[
                        TextMessage(type="text", text=f"💬 User feedback:\n{msg}")
                    ])
                )
        except Exception:
            pass
    return (
        "💬 Thank you for your feedback! It has been forwarded to the team.\n\n"
        "💬 感謝您的建議！已轉交給團隊參考。"
    )


# ── Message router ────────────────────────────────────────────────────────────

def route_message(user_id: str, text: str) -> str:
    t = text.strip()
    tu = t.upper()

    if tu == "ALL":
        return ALL_MSG
    if tu == "BRIEF":
        return _handle_brief()
    if tu == "MARKET":
        return _handle_market()
    if tu == "NEWS":
        return _handle_news()
    if tu == "CALENDAR":
        return _handle_calendar()
    if tu == "TOP":
        return _handle_top()
    if tu == "WATCHLIST":
        return _handle_watchlist_show(user_id)
    if tu.startswith("ADD "):
        return _handle_add(tu[4:].strip())
    if tu.startswith("REMOVE "):
        return _handle_remove(tu[7:].strip())
    if tu == "WHOAMI":
        return f"Your LINE User ID:\n{user_id}"
    if tu == "HELP":
        return _handle_help(user_id, t)
    if tu.startswith("FEEDBACK"):
        rest = t[8:].strip()
        return _handle_feedback(rest or "(no message)")

    # Ticker lookup: 1–10 chars, letters/digits/dot/hyphen
    if re.match(r'^[A-Z0-9.\-]{1,10}$', tu):
        return _handle_ticker(tu)

    return (
        "I didn't understand that. Type ALL to see available commands.\n"
        "我不理解您的輸入。輸入 ALL 查看可用指令。"
    )


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    if not handler:
        abort(500, "LINE SDK not configured")
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400, "Invalid signature")
    return "OK"


if LINE_SDK_AVAILABLE and handler:
    @handler.add(FollowEvent)
    def on_follow(event):
        _reply(event.reply_token, WELCOME_MSG)

    @handler.add(MessageEvent, message=TextMessageContent)
    def on_message(event):
        user_id = event.source.user_id
        text    = event.message.text
        reply   = route_message(user_id, text)
        _reply(event.reply_token, reply)


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("LINE_BOT_PORT", 5001))
    print(f"[LINE Bot] Starting webhook server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
