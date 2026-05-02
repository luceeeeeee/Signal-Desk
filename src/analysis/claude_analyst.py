import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from src.utils.helpers import load_settings, format_price, format_change

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Tried in order; first one that responds is used
FREE_MODELS = [
    "openai/gpt-oss-120b:free",          # best results in testing
    "google/gemma-4-31b-it:free",         # good multilingual fallback
    "google/gemma-3-27b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-coder:free",
]

ANALYST_SYSTEM_PROMPT = """You are a senior finance analyst and experienced stock trader with 20+ years of hands-on experience across US and Taiwan equity markets. You have deep expertise in fundamental analysis, earnings report interpretation, macroeconomic reading, and practical trading strategy. You have a strong track record of successful trades and have advised high-net-worth personal clients.

Your role is to generate comprehensive financial briefings and intraday trading alerts. Follow these rules strictly:

PERSONA
Write decisively as a senior analyst advising a personal client. Be precise, confident, and actionable. Experienced traders give real views — avoid excessive hedging like "on the other hand" or "it depends." Commit to a direction and explain why.

EXPERIENCED INVESTOR PERSPECTIVE — MANDATORY IN EVERY BRIEFING
Every briefing must include an "INVESTOR LENS" section written from the perspective of seasoned long-term value investors. Apply these principles:
  - Moat: Does the company have a lasting competitive advantage (brand, patents, network effects, switching costs, low-cost production)? State clearly: strong moat / narrow moat / no moat.
  - Long-term earnings power: Ignore short-term noise. What matters is whether the company will earn more in 5–10 years than it does today.
  - Price vs. value: A great company at a bad price is a bad investment. A fair company at a great price can be outstanding.
  - Circle of competence: Only comment on businesses that are simple enough to understand.
  - The long-term investor's test: "Would I still want to own this business if the stock market closed for 5 years?"
  Write this section plainly — as a veteran investor explaining it to a friend, not writing a research note.

PLAIN LANGUAGE — MANDATORY
Write as if explaining to a smart friend who does not follow stocks or finance. Assume zero prior knowledge.
  - Avoid all financial jargon. If you must use a technical term (e.g. "P/E ratio"), immediately explain it in plain words: "P/E ratio — this tells you how much investors are paying for each dollar of profit the company earns. A P/E of 20 means investors pay $20 for every $1 of yearly profit."
  - Never write abstract phrases like "valuation premium," "macro headwinds," or "risk-off sentiment" without explaining what they mean in everyday terms.
  - Use concrete, relatable comparisons. Example: "A 55% net margin means that for every $100 in sales, $55 is pure profit — that is exceptional, most companies keep $5–$15."
  - The same plain-language rule applies to the Traditional Chinese translation. Do not translate financial jargon word-for-word — explain it in everyday Chinese.

BILINGUAL — NON-NEGOTIABLE
Every single sentence, bullet point, number, label, table row, and section header MUST appear in BOTH English and Traditional Chinese (繁體中文). There are zero exceptions.

LAYOUT RULE: For each news item and each earnings entry, write ALL English content in a block first, then write ALL Chinese content in a block below it. Do NOT alternate line by line.

Correct format for a news item:
  [Source | Region] English headline
  📌 Market Impact: English analysis sentence 1. English sentence 2.

  [來源 | 地區] 繁體中文標題
  📌 市場影響：中文分析句1。中文句2。

Correct format for an earnings entry:
  ── COMPANY (TICKER) ──────────────────
  Date: [ET] / [TPE]
  [English block]
  - Company: what it does
  - Revenue: figures and meaning
  - Gross margin: X% — $X stays per $100
  - Net margin: X% — $X pure profit per $100
  - EPS: $X per share
  - 📈 Outlook: prediction

  [繁體中文]
  - 公司簡介：
  - 營收預估：
  - 毛利率：
  - 淨利率：
  - 每股盈餘：
  - 📈 走勢預判：

DATES AND TIMES — MANDATORY
Whenever you mention a date or time, always include BOTH US Eastern Time (ET) and Taipei Time (TPE) together. Example: "April 30 at 4:00 PM ET / 台北時間 4月30日 凌晨4:00 (TPE)"

MARKET IMPACT SIGNALS
Every news item you include MUST carry a market impact signal. Do not just summarize the event — tell the reader what it means for stocks, sectors, or broader markets. Use this format:
  📌 Market Impact / 市場影響: [your analysis in both EN and ZH, in plain language]

EARNINGS AND FINANCIAL STATEMENT ANALYSIS
When analyzing earnings reports, explain each metric in plain, everyday language:
  - Revenue growth rate → explain in simple terms: "Revenue is the total money a company collected from customers. Growing X% means..."
  - Gross margin → explain: "Gross margin is how much money is left after paying to make the product. A X% gross margin means for every $100 in sales, $X is left before paying salaries and other costs."
  - Operating margin → explain: "Operating margin is what's left after also paying for staff, offices, and running the business day to day."
  - Net margin → explain: "Net margin is the final profit — after paying everything including taxes. X% net margin means for every $100 in sales, $X is pure profit."
  - Beat / Miss → explain: "Wall Street analysts predicted the company would earn $X. It actually earned $Y, which is [higher/lower] — this is called [beating/missing] expectations."
  - YoY comparison → explain: "Year-over-year (YoY) compares this quarter to the same quarter last year — this removes seasonal effects and shows real growth."

DIRECTIONAL READS
When giving a directional read (Bullish / Neutral / Bearish):
  - State the primary reason in plain language — no jargon
  - Name one specific risk that could invalidate the call
  - Give a practical trader's observation (what to watch, when to act)
  - Be specific — never generic

VALUATION-BASED BUY/SELL ZONE ASSESSMENT
When assessing whether a stock is in a buy or sell zone:
  - Compare current forward P/E to the stock's 5-year historical average P/E — explain both numbers plainly
  - Assess analyst consensus target and % upside/downside — explain what "analyst target" means
  - Consider sector context
  - Factor in recent earnings trajectory
  - Give a clear verdict: Reasonable Buy Zone / Fair Value / Overpriced Sell Zone — with plain-language reasoning
  - Never use generic disclaimers. Write as the analyst you are.

OUTPUT LANGUAGE
All section headers, labels, and content must appear in both English and Traditional Chinese. No exceptions."""


def _generate(prompt: str, max_tokens: int = 8000) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/daily-stock-alert",
        "X-Title": "Daily Stock Alert",
    }

    last_error = None
    for model in FREE_MODELS:
        try:
            print(f"    Trying model: {model}...")
            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices")
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        print(f"    ✓ Success with {model}")
                        return content
                print(f"    Empty response from {model}, trying next...")
                last_error = f"{model}: empty content in response"
                continue
            elif response.status_code == 429:
                print(f"    Rate-limited, trying next...")
                last_error = f"{model}: 429 rate-limited"
                continue
            else:
                last_error = f"{model}: {response.status_code} {response.text[:200]}"
                print(f"    Error {response.status_code}, trying next...")
                continue
        except requests.Timeout:
            last_error = f"{model}: timeout"
            print(f"    Timeout, trying next...")
            continue

    raise RuntimeError(f"All models failed. Last error: {last_error}")


def _build_briefing_prompt(market: str, news_items_text: str, prices_text: str, earnings_text: str, sentiment_text: str = "") -> str:
    now = datetime.now(tz=TAIPEI_TZ)
    if market == "TW":
        session_label_en = "MORNING BRIEF — TW MARKET OPEN"
        session_label_zh = "早安市場簡報 — 台股開盤"
    else:
        session_label_en = "EVENING BRIEF — US MARKET OPEN"
        session_label_zh = "晚間市場簡報 — 美股開盤"

    return f"""Generate a complete pre-market briefing for the {market} market opening session.

CURRENT DATE/TIME: {now.strftime('%Y-%m-%d %H:%M Taipei (Asia/Taipei)')}
SESSION: {session_label_en} / {session_label_zh}

━━━━━━━━━━━━ INPUT DATA ━━━━━━━━━━━━

NEWS FROM THE PAST 24 HOURS (world + TW sources):
{news_items_text}

WATCHLIST PRICE DATA:
{prices_text}

EARNINGS CALENDAR (next 7 days + any recent releases):
{earnings_text}

MARKET SENTIMENT (VIX / 10Y Yield / Sector Rotation):
{sentiment_text}

━━━━━━━━━━━━ OUTPUT FORMAT ━━━━━━━━━━━━

Generate the briefing in EXACTLY this format. Fill every section. Do not skip any section.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📈 {session_label_en}
  {session_label_zh}
  {now.strftime('%Y-%m-%d | %H:%M Taipei')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

══════════════════════════════════════════════════
  MARKET OVERVIEW / 市場概況
══════════════════════════════════════════════════
[Use MARKET SENTIMENT DATA above. Lead with:
1. VIX level — explain in plain terms what it means (e.g. "VIX at 18 means markets are calm — investors are not pricing in big swings")
2. 10Y Treasury yield — explain what it means for stocks (higher yields = higher hurdle for growth stocks)
3. Top 3 sector movers from the sector rotation data — which sectors are leading or lagging today and why it matters
Then add 1-2 other key indicators (futures, USD/TWD, oil, gold) if relevant.
Each indicator: English sentence with the number and plain-language meaning, then Chinese sentence directly below.]

══════════════════════════════════════════════════
  TOP NEWS / 今日要聞
══════════════════════════════════════════════════
[Select 5 most market-moving stories. RANK by impact — biggest market mover goes first.
Draw from all regions: US, Europe (BBC, FT, Guardian), Asia-Pacific (CNA Singapore, SCMP, Nikkei), Taiwan.

Format each item EXACTLY like this — English block first, Chinese block second:

1. [Source | Region] Full English headline
   📌 Market Impact: English analysis, 2-3 sentences. Name specific stocks, sectors, or indices affected.

   [來源 | 地區] 完整繁體中文標題
   📌 市場影響：中文分析，2-3句。點名受影響的具體股票、板塊或指數。]

══════════════════════════════════════════════════
  EARNINGS SPOTLIGHT / 財報焦點
══════════════════════════════════════════════════
[SCOPE: Cover ONLY companies reporting TODAY and TOMORROW (within 48 hours of current date/time). Pick the 6 most important by global investor impact — prioritize mega-cap names (AAPL, MSFT, META, AMZN, GOOGL, NVDA, TSMC) over smaller names. The full list of all upcoming earnings is in the UPCOMING EVENTS section.

For EACH company in the spotlight, use this EXACT format:

── COMPANY NAME (TICKER) ──────────────────────
Reporting: [date, ET time] / [TPE date, time]

[English]
- What it does: one plain sentence about the business
- Revenue estimate: $X — this means the company expects to collect $X from customers
- Gross margin: X% — for every $100 of sales, $X remains after making the product
- Net margin: X% — for every $100 of sales, $X is the final pure profit
- EPS estimate: $X per share — this means each share of the company earns $X
- Prior quarter: EPS actual $X [beat/missed] estimate by X% — [1 sentence on what this beat/miss tells us about the company's momentum]
- 📈 Outlook: [Specific directional call — "Likely to beat/miss because..." with real reasons: recent news, AI trends, macro data, competitor signals, prior quarter momentum. Name the expected % stock move.]

📊 Analyst Insight / 分析師總結:
[English — 3-4 sentences synthesizing multiple perspectives:
  1. Trend view: How does this quarter compare to recent history? Is the company accelerating, decelerating, or holding steady?
  2. Bull case: What is the strongest reason to be optimistic about this report?
  3. Bear case: What is the one thing that could disappoint — name a specific risk (not generic "macro uncertainty")?
  4. Bottom line: Given all of this, what should an investor watch for the moment results drop? Name a specific number or guidance metric that will move the stock.]

[繁體中文 — 3-4句，綜合多方觀點：
  1. 趨勢觀察：與近幾季相比，公司是在加速、減速還是持平？
  2. 樂觀理由：對這份財報最有說服力的一個正面論點？
  3. 風險因素：最可能讓市場失望的一件具體事項（不要泛稱「總經不確定性」）？
  4. 投資結論：結果公布時，投資人最應該盯哪一個具體數字或業績指引？]

[繁體中文 — 財報資料]
- 公司簡介：一句話說明公司業務
- 營收預估：X億美元——代表公司預計從客戶收取X億美元
- 毛利率：X%——每賣出100元，扣除製造成本後剩X元
- 淨利率：X%——每賣出100元，最終純利X元
- 每股盈餘：X美元/股——即每持有一股可獲得X美元利潤
- 上季表現：實際EPS $X [超越/不及] 預期X%——[一句話說明對本季的動能意義]
- 📈 走勢預判：[具體判斷，含理由與預期漲跌幅]]

══════════════════════════════════════════════════
  WATCHLIST SNAPSHOT / 自選股快照
══════════════════════════════════════════════════
[Show ONLY stocks from WATCHLIST PRICE DATA. No other stocks.
Format as a clean table:
Ticker | Name | Price | Change | Conviction | Signal
Conviction: use the ⭐ score from WATCHLIST PRICE DATA (e.g. "72 Moderate")
Signal: 🟢 Bullish/偏多  🟡 Neutral/中性  🔴 Bearish/偏空]

══════════════════════════════════════════════════
  DIRECTIONAL READ / 方向性判斷
══════════════════════════════════════════════════
[Cover ONLY stocks in WATCHLIST PRICE DATA. For EACH:

[English]
- Reason: plain-language explanation of current situation (1-2 sentences)
- 📈 Prediction: "This stock is likely to [rise/fall/move sideways] because..." — specific call with reasoning
- Risk: one specific thing that could prove this prediction wrong
- Watch for: one practical action point with specific price or trigger

[繁體中文]
- 原因：用日常語言說明當前狀況（1-2句）
- 📈 走勢預判：「這支股票可能會……因為……」——具體判斷加上理由
- 風險：一件可能推翻此預判的具體事項
- 留意：一個具體的操作要點，附帶明確價位或觸發條件]

══════════════════════════════════════════════════
  UPCOMING EVENTS / 本週重要事件
══════════════════════════════════════════════════
[List ALL earnings from the EARNINGS CALENDAR. Consolidate same-time events onto one line.
Also include key macro events.

Format:
[Date, ET time / TPE time] — Earnings: TICK1, TICK2, TICK3 / 財報：公司1、公司2
[Date] — [Macro event in English] / [總經事件中文]

Keep it concise — one line per time slot, comma-separated tickers.]

══════════════════════════════════════════════════
  INVESTOR LENS / 投資人視角
══════════════════════════════════════════════════
[Write from the perspective of a seasoned long-term value investor.
Speak plainly, like explaining to a friend. No jargon. No hedging.

🏛️ Market Perspective / 市場視野
[English — 2-3 sentences: Is this a market where a patient long-term investor should be adding, holding, or sitting on cash? What is the single most important thing to watch right now from a long-term value lens?]
[繁體中文 — 同上]

🔍 Watchlist Value Check / 自選股價值檢視
[For EACH stock in WATCHLIST PRICE DATA, one block per stock:

TICKER / Company Name
[English]
- Moat: [strong / narrow / none] — [one sentence why: what keeps competitors out, or why there is no protection]
- Long-term earnings power: [one sentence: will this company earn more in 5 years? why or why not]
- Price check: [cheap / fair / expensive] for a 5-year holder — [one sentence comparing current price to intrinsic value simply]
- Value verdict: [one memorable sentence — would a long-term investor buy, hold, or pass? Plain and decisive.]

[繁體中文]
- 護城河：[寬廣／狹窄／無] — [一句話說明原因]
- 長期獲利能力：[一句話說明這間公司5年後會賺更多嗎？為什麼？]
- 價格判斷：[便宜／合理／偏貴]——以5年持有者角度評估
- 長期投資結論：[一句話，資深投資人平易近人的風格——會買入、持有，還是略過？]]]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Monthly Overview / 月度總覽 → [MONTHLY_PAGE_URL]
📚 Income Statement Guide / 財報指南 → [GUIDE_URL]
📅 Earnings Calendar / 財報日曆 → [CALENDAR_URL]
📡 News Sources / 新聞來源 → [SOURCES_URL]
🔗 SEC Filings / 美股申報 → https://www.sec.gov/cgi-bin/browse-edgar
🔗 TW Filings / 台股公開資訊 → https://mops.twse.com.tw
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def _build_alert_prompt(ticker: str, name: str, price_data: dict) -> str:
    currency = price_data.get("currency", "USD")
    price_str = format_price(price_data["price"], currency) if price_data.get("price") else "N/A"
    change_str = format_change(price_data.get("change_pct", 0))

    valuation_lines = []
    if price_data.get("forward_pe"):
        valuation_lines.append(f"Forward P/E: {price_data['forward_pe']:.1f}")
    if price_data.get("trailing_pe"):
        valuation_lines.append(f"Trailing P/E: {price_data['trailing_pe']:.1f}")
    if price_data.get("analyst_target") and price_data.get("analyst_upside_pct") is not None:
        sign = "+" if price_data["analyst_upside_pct"] >= 0 else ""
        valuation_lines.append(
            f"Analyst consensus target: {format_price(price_data['analyst_target'], currency)} "
            f"({sign}{price_data['analyst_upside_pct']}% from current)"
        )
    if price_data.get("week_52_high") and price_data.get("week_52_low"):
        valuation_lines.append(
            f"52-week range: {format_price(price_data['week_52_low'], currency)} — "
            f"{format_price(price_data['week_52_high'], currency)}"
        )
    if price_data.get("gross_margin"):
        valuation_lines.append(f"Gross margin: {price_data['gross_margin']*100:.1f}%")
    if price_data.get("net_margin"):
        valuation_lines.append(f"Net margin: {price_data['net_margin']*100:.1f}%")
    if price_data.get("roic") is not None:
        r = price_data["roic"] * 100
        flag = "STRONG ✓" if r >= 15 else "WEAK ⚠"
        valuation_lines.append(f"ROIC: {r:.1f}% — {flag} (threshold: >15% = high-quality capital allocator)")
    if price_data.get("revenue_growth") is not None:
        rg = price_data["revenue_growth"] * 100
        flag = "HEALTHY ✓" if rg >= 10 else "SLOW ⚠" if rg >= 0 else "DECLINING ⚠"
        valuation_lines.append(f"Revenue growth: {'+' if rg >= 0 else ''}{rg:.1f}% — {flag} (threshold: >10%)")
    if price_data.get("fcf_margin") is not None:
        fm = price_data["fcf_margin"] * 100
        flag = "STRONG ✓" if fm >= 20 else "LOW ⚠"
        valuation_lines.append(f"FCF margin: {fm:.1f}% — {flag} (threshold: >20% = strong cash conversion)")
    if price_data.get("total_cash") and price_data.get("total_debt"):
        cash_b = price_data["total_cash"] / 1e9
        debt_b = price_data["total_debt"] / 1e9
        ratio = cash_b / debt_b if debt_b > 0 else 99
        flag = "FORTRESS ✓" if ratio >= 3 else "HEALTHY ✓" if ratio >= 1.5 else "LEVERAGED ⚠"
        valuation_lines.append(f"Cash ${cash_b:.1f}B vs Debt ${debt_b:.1f}B ({ratio:.1f}x) — {flag}")
    elif price_data.get("total_cash"):
        cash_b = price_data["total_cash"] / 1e9
        valuation_lines.append(f"Cash ${cash_b:.1f}B, no debt — FORTRESS ✓")
    if price_data.get("equity_ratio") is not None:
        eq = price_data["equity_ratio"] * 100
        flag = "STRONG ✓" if eq >= 50 else "LEVERAGED ⚠"
        valuation_lines.append(f"Equity ratio: {eq:.1f}% — {flag} (higher = less reliance on debt financing)")
    if price_data.get("working_capital") is not None:
        wc_b = price_data["working_capital"] / 1e9
        flag = "POSITIVE ✓" if wc_b >= 0 else "NEGATIVE ⚠"
        valuation_lines.append(f"Working capital: ${wc_b:.1f}B — {flag} (the buffer between current assets and current liabilities)")
    if price_data.get("retained_earnings") is not None:
        re_b = price_data["retained_earnings"] / 1e9
        valuation_lines.append(f"Retained earnings: ${re_b:.1f}B (cumulative profits kept in the business)")

    valuation_text = "\n".join(f"  {v}" for v in valuation_lines) if valuation_lines else "  Valuation data unavailable"

    # Technical indicators
    tech_lines = []
    if price_data.get("rsi") is not None:
        rsi = price_data["rsi"]
        if rsi < 30:
            rsi_label = "OVERSOLD ⚠ — historically a buy signal"
        elif rsi > 70:
            rsi_label = "OVERBOUGHT ⚠ — historically a sell signal"
        elif rsi < 45:
            rsi_label = "Leaning oversold — mild buy bias"
        elif rsi > 55:
            rsi_label = "Leaning overbought — mild sell bias"
        else:
            rsi_label = "Neutral zone"
        tech_lines.append(f"  RSI-14: {rsi} — {rsi_label}")
    if price_data.get("ma50") and price_data.get("above_ma50") is not None:
        direction = "ABOVE ✓" if price_data["above_ma50"] else "BELOW ⚠"
        tech_lines.append(f"  50-day MA: {price_data['ma50']:.2f} — price is {direction} (trend: {'uptrend' if price_data['above_ma50'] else 'downtrend'})")
    if price_data.get("ma200") and price_data.get("above_ma200") is not None:
        direction = "ABOVE ✓" if price_data["above_ma200"] else "BELOW ⚠"
        tech_lines.append(f"  200-day MA: {price_data['ma200']:.2f} — price is {direction} (long-term: {'bullish' if price_data['above_ma200'] else 'bearish'})")
    if price_data.get("volume_ratio") is not None:
        vr = price_data["volume_ratio"]
        vol_label = f"HIGH VOLUME ({vr:.1f}x avg) — institutional activity" if vr >= 1.5 else f"{vr:.1f}x average — normal"
        tech_lines.append(f"  Volume: {vol_label}")
    tech_text = "\n".join(tech_lines) if tech_lines else "  Technical data unavailable"

    return f"""Assess whether {ticker} ({name}) is currently in a buy zone or sell zone, and generate an intraday LINE alert message.

CURRENT DATA:
  Price: {price_str}
  Change today: {change_str}
  Market: {price_data.get('market', 'US')}

VALUATION METRICS:
{valuation_text}

TECHNICAL INDICATORS:
{tech_text}

SECTOR: {price_data.get('sector', 'N/A')} — {price_data.get('industry', 'N/A')}

Generate a LINE alert message in EXACTLY this format. Keep it concise — the whole message should be readable in under 60 seconds. Do NOT start with punctuation marks or box-drawing characters.

📊 Stock Alert / 股票提醒 — {ticker}
{name}
[🟢 Reasonable Buy Zone / 合理買入區間  OR  🔴 Overpriced Sell Zone / 超漲賣出區間  OR  🟡 Fair Value / 合理價位]

Current Price / 現價: {price_str} ({change_str})
Alert Time / 提醒時間: {datetime.now(tz=TAIPEI_TZ).strftime('%H:%M Taipei')}

Analysis / 分析:
[3-4 sentences MAX in plain English — use real numbers. Explain the verdict simply. Example: "The P/E is 18, which means investors pay $18 per $1 of profit. The historical average for this stock is $22, so it is cheaper than usual right now. Analysts expect the price to rise 15% to NT$2,508."]
[Same 3-4 sentences in plain Traditional Chinese]

📈 Outlook / 走勢預判:
[1-2 sentences: give a specific directional call with reason. Example: "Likely to rise in the short term — AI chip demand remains strong and the valuation discount provides a safety cushion. Watch for any earnings guidance update." / 中文版同上]

Signal / 訊號: [verdict EN + ZH]
Risk / 風險: [one specific risk, one line EN + ZH]

🏛️ Long-term Value / 長期價值觀點:
[1 sentence in plain investor style: does this company have a durable edge, and is the current price reasonable for a 5-year holder? Would a long-term value investor buy, hold, or pass right now?]
[1 sentence in 繁體中文]

🔗 SEC → https://www.sec.gov/cgi-bin/browse-edgar | TW → https://mops.twse.com.tw"""


def _build_monthly_overview_prompt(month_review: str, month_preview: str, index_data: str, upcoming_earnings: str) -> str:
    now = datetime.now(tz=TAIPEI_TZ)
    return f"""Generate a comprehensive monthly market overview page. Write as a senior analyst with a clear, engaging voice.

CURRENT DATE: {now.strftime('%Y-%m-%d %H:%M Taipei')}
MONTH BEING REVIEWED: {month_review}
MONTH BEING PREVIEWED: {month_preview}

MAJOR INDEX DATA (monthly performance):
{index_data}

UPCOMING EARNINGS THIS MONTH:
{upcoming_earnings}

Output in EXACTLY this markdown format. Write bilingual throughout — English content first in each block, then Traditional Chinese (繁體中文) directly below it. Do NOT use "English –" or "繁體中文 –" as prefix labels — just write the bilingual content naturally.

## MONTHLY REVIEW: {month_review} / {month_review} 市場回顧

2-3 sentences: What defined {month_review}? Dominant market theme and what drove it.
2-3 句：{month_review} 的主要特徵？主要市場主題及驅動因素。

### 📊 Index Performance / 指數表現

[Use the INDEX DATA above. Show as a table with one row per index:]
| Index / 指數 | Monthly Return / 月報酬 | Key Driver / 主要驅動 |
|-------------|------------------------|----------------------|
[Fill in from INDEX DATA. Key Driver: bilingual, concise — EN / 中文]

### 🔑 3 Events That Defined the Month / 定義本月的3件大事

1. **[Event Title EN]** / **[事件標題 ZH]**
[English: 2-3 sentences on what happened and why it mattered to investors]
[中文：同上 2-3 句]

2. **[Event Title EN]** / **[事件標題 ZH]**
[English: 2-3 sentences]
[中文：2-3 句]

3. **[Event Title EN]** / **[事件標題 ZH]**
[English: 2-3 sentences]
[中文：2-3 句]

### 📰 5 Key Market News / 5 則重要市場新聞

1. **[Headline EN]** / **[標題 ZH]**
📌 Market Impact / 市場影響: [1-2 sentences EN — name specific stocks, sectors, or indices affected]
📌 市場影響：[1-2 句中文衝擊說明]

2. **[Headline EN]** / **[標題 ZH]**
📌 Market Impact / 市場影響: [EN]
📌 市場影響：[ZH]

3. [repeat]
4. [repeat]
5. [repeat]

## MONTHLY PREVIEW: {month_preview} / {month_preview} 市場展望

2-3 sentences: Key question or tension heading into {month_preview}.
2-3 句中文：進入 {month_preview} 的核心問題或矛盾。

### 📅 Key Events & Earnings / 重要事件與財報

[List key macro events plus top earnings from the UPCOMING EARNINGS data. Format each as a bullet:]
- **[Date ET / TPE]** — [Event or Earnings: TICK1, TICK2] / [事件或財報名稱]

### 🎯 3 Themes to Watch / 本月3大觀察主題

1. **[Theme EN]** / **[主題 ZH]**
[English: 2-3 sentences on what to watch and why it matters for investors]
[中文：同上 2-3 句]

2. **[Theme EN]** / **[主題 ZH]**
[English: 2-3 sentences]
[中文：2-3 句]

3. **[Theme EN]** / **[主題 ZH]**
[English: 2-3 sentences]
[中文：2-3 句]

### 📈 Directional View / 方向性判斷

2-3 sentences: Bullish, neutral, or cautious for {month_preview}? Name one specific catalyst and one specific risk.
中文：同上 2-3 句。點名一個具體催化劑和一個風險。

## INVESTOR LENS / 投資人視角

### 🏛️ Long-term Market Perspective / 長期市場視野

[Write in plain, decisive investor language. 3-4 sentences: Is the overall market cheap, fair, or expensive right now? Would a patient long-term investor be adding to positions, holding steady, or sitting on more cash? What is the single most important thing to watch from a value perspective?]
[中文：同上 3-4 句，用資深價值投資人平易近人的口吻]

### 🔍 Sector Value Scan / 板塊價值掃描

[2-3 sectors worth watching from a value investor's lens. For each: 1-2 sentences EN then 1-2 sentences ZH.]
- **[Sector Name / 板塊名稱]**: [EN: moat or competitive position + current value verdict — cheap/fair/expensive]. [中文：同上]

## ANALYST CONSENSUS VIEW / 分析師共識觀點

### 📊 Market Sentiment & Positioning / 市場情緒與部位配置

[4-5 sentences: What is the current Wall Street consensus? Which sectors are analysts overweighting or underweighting? What do the bull and bear cases look like heading into {month_preview}?]
[中文：同上 4-5 句]

### ⚡ Key Risks to Monitor / 重要風險事項

[3 specific risks for {month_preview}, ranked by likelihood. For each: 1-2 sentences EN then 1-2 sentences ZH.]
1. **[Risk Title EN]** / **[風險標題 ZH]**: [EN: what could go wrong and market impact]. [中文：同上]
2. **[Risk Title EN]** / **[風險標題 ZH]**: [EN]. [中文]
3. **[Risk Title EN]** / **[風險標題 ZH]**: [EN]. [中文]"""


def _build_company_narrative_prompt(ticker: str, name: str, price_data: dict, quarterly: list) -> str:
    currency = price_data.get("currency", "USD")
    lines = [f"{ticker} — {name}"]
    if price_data.get("price"):
        lines.append(f"Price: {format_price(price_data['price'], currency)} ({price_data.get('change_pct', 0):+.2f}%)")
    if price_data.get("market_cap"):
        lines.append(f"Market cap: ${price_data['market_cap']/1e9:.1f}B")
    if price_data.get("sector"):
        lines.append(f"Sector: {price_data['sector']} / {price_data.get('industry', '')}")
    lines += ["", "Valuation:"]
    if price_data.get("forward_pe"):
        lines.append(f"  Forward P/E: {price_data['forward_pe']:.1f}")
    if price_data.get("trailing_pe"):
        lines.append(f"  Trailing P/E: {price_data['trailing_pe']:.1f}")
    if price_data.get("analyst_target") and price_data.get("analyst_upside_pct") is not None:
        lines.append(
            f"  Analyst target: {format_price(price_data['analyst_target'], currency)}"
            f" ({price_data['analyst_upside_pct']:+.1f}% upside)"
            f" | Rec: {price_data.get('recommendation','').upper()}"
        )
    lines += ["", "Quality & Growth:"]
    if price_data.get("roic") is not None:
        r = price_data["roic"] * 100
        lines.append(f"  ROIC: {r:.1f}% ({'strong >15%' if r >= 15 else 'weak <15%'})")
    if price_data.get("revenue_growth") is not None:
        lines.append(f"  Revenue growth: {price_data['revenue_growth']*100:+.1f}%")
    if price_data.get("earnings_growth") is not None:
        lines.append(f"  Earnings growth: {price_data['earnings_growth']*100:+.1f}%")
    if price_data.get("fcf_margin") is not None:
        lines.append(f"  FCF margin: {price_data['fcf_margin']*100:.1f}%")
    if price_data.get("gross_margin") is not None:
        lines.append(f"  Gross margin: {price_data['gross_margin']*100:.1f}%")
    if price_data.get("net_margin") is not None:
        lines.append(f"  Net margin: {price_data['net_margin']*100:.1f}%")
    lines += ["", "Financial Health:"]
    if price_data.get("total_cash") and price_data.get("total_debt"):
        ratio = price_data["total_cash"] / max(price_data["total_debt"], 1)
        lines.append(
            f"  Cash ${price_data['total_cash']/1e9:.1f}B vs Debt ${price_data['total_debt']/1e9:.1f}B"
            f" ({ratio:.1f}x coverage)"
        )
    elif price_data.get("total_cash"):
        lines.append(f"  Cash ${price_data['total_cash']/1e9:.1f}B, no debt")
    if price_data.get("equity_ratio") is not None:
        lines.append(f"  Equity ratio: {price_data['equity_ratio']*100:.0f}%")
    if price_data.get("current_ratio") is not None:
        lines.append(f"  Current ratio: {price_data['current_ratio']:.1f}")
    snapshot_text = "\n".join(lines)

    if quarterly:
        q_lines = []
        for q in quarterly:
            rev_s = f"${q['revenue']/1e9:.2f}B" if q.get("revenue") else "N/A"
            gm_s = f"{q['gross_margin']*100:.1f}%" if q.get("gross_margin") else "N/A"
            net_s = f"${q['net_income']/1e9:.2f}B" if q.get("net_income") else "N/A"
            q_lines.append(f"  {q['period']:8s}: Revenue {rev_s} | Gross margin {gm_s} | Net income {net_s}")
        quarterly_text = "\n".join(q_lines)
    else:
        quarterly_text = "  Quarterly data unavailable."

    return f"""Write a bilingual company analysis for {ticker} ({name}). Every section must appear in BOTH English AND Traditional Chinese (繁體中文). Be specific, plain-language, and decisive. Write like a senior analyst briefing a sophisticated investor.

FINANCIAL SNAPSHOT:
{snapshot_text}

QUARTERLY TREND (most recent first):
{quarterly_text}

Write EXACTLY these 5 sections using ## headers. For each section, write all English content first, then a blank line, then all Traditional Chinese (繁體中文) content below it. No filler, no hedging. Explain any financial terms in plain language.

## BUSINESS OVERVIEW

English: 3-4 sentences. What does this company do in plain English? What is the moat — what prevents a well-funded competitor from taking share? Be concrete: "controls X% of market Y", "switching costs are high because...", "the brand commands a 40% price premium". If there is no durable moat, say so.

繁體中文：3-4句。用白話解釋這家公司做什麼？護城河是什麼——是什麼阻止有資金的競爭對手搶佔市場份額？要具體說明。

## RECENT DEVELOPMENTS

English: 2-3 sentences on the most important things that happened in the past 6 months. Reference specific numbers (e.g. "revenue grew 78% YoY").

繁體中文：2-3句。過去6個月最重要的事件。引用具體數字。

## CATALYSTS

English:
- [Catalyst title]: name the driver, explain the mechanism, give a sense of timing or magnitude.
- [Catalyst title]: explanation
- [Catalyst title]: explanation

繁體中文：
- 【催化劑標題】：說明驅動因素、機制及時機或規模。
- 【催化劑標題】：說明
- 【催化劑標題】：說明

## RISKS

English:
- [Risk title]: name the scenario, what triggers it, and realistic downside impact.
- [Risk title]: explanation
- [Risk title]: explanation

繁體中文：
- 【風險標題】：說明情境、觸發條件及合理的下行影響。
- 【風險標題】：說明
- 【風險標題】：說明

## CONCLUSION

English: 3-4 sentences. Give a final verdict — buy, hold, or avoid at today's price and why. Name one specific price level or catalyst that would change your view. End with a 5-year moat durability assessment.

繁體中文：3-4句。給出最終結論——以今日股價買入、持有或避免，並說明原因。指出一個會改變看法的具體價位或催化劑。以5年護城河耐久性評估作結。"""


def generate_company_narrative(ticker: str, price_data: dict, quarterly: list) -> str:
    """Generate AI narrative sections for a company analysis page."""
    name = price_data.get("name", ticker)
    prompt = _build_company_narrative_prompt(ticker, name, price_data, quarterly)
    return _generate(prompt, max_tokens=2000)


def generate_buffett_outlook(index_summary: str = "") -> dict:
    """Generate Warren Buffett-style weekly macro outlook. Returns {"en": "...", "zh": "..."}."""
    now = datetime.now(tz=TAIPEI_TZ)
    date_str = now.strftime("%Y-%m-%d")
    prompt = f"""You are a veteran long-term value investor with 50 years of experience. You have seen every market cycle — crashes, bubbles, recessions, and recoveries. You think in decades, not quarters. You only buy businesses you understand deeply, and only at prices that give you a margin of safety. You are writing the weekly macro outlook for a financial dashboard.

Date: {date_str}
{f"Index context: {index_summary}" if index_summary else ""}

Write your weekly view in 3-4 plain sentences (English), then 3-4 sentences (Traditional Chinese 繁體中文). Your voice is calm, unhurried, and decisive — like a seasoned investor explaining the market to a trusted friend. Cover:
- Is the overall market cheap, fair, or expensive right now? Give a concrete plain-language verdict.
- What single long-term macro force matters most for patient investors right now?
- Would you be deploying capital, sitting still, or quietly building cash? Be direct — no hedging.

Write as if speaking from personal conviction, not writing a research note. No jargon. No disclaimers. No mention of any specific investor by name.

Format: ALL English sentences first as one paragraph, blank line, then ALL Traditional Chinese as one paragraph. No headers, no bullets."""

    try:
        raw = _generate(prompt, max_tokens=600)
        parts = raw.strip().split("\n\n", 1)
        return {"en": parts[0].strip(), "zh": parts[1].strip() if len(parts) > 1 else ""}
    except Exception:
        return {"en": "", "zh": ""}


def generate_monthly_overview(month_review: str, month_preview: str, index_data: str, upcoming_earnings: str) -> str:
    settings = load_settings()
    prompt = _build_monthly_overview_prompt(month_review, month_preview, index_data, upcoming_earnings)
    return _generate(prompt, max_tokens=5000)


def _site_url(settings: dict) -> str:
    """Return base site URL without trailing slash, or empty string if not configured."""
    url = settings.get("site", {}).get("base_url", "")
    if url == "FILL_IN_NETLIFY_URL" or not url:
        return ""
    return url.rstrip("/")


def _inject_site_links(briefing: str, settings: dict) -> str:
    """Replace placeholder URLs in the briefing footer with real Netlify URLs."""
    base = _site_url(settings)
    if not base:
        return briefing
    now = datetime.now(tz=TAIPEI_TZ)
    month_slug = now.strftime("%Y-%m")
    replacements = {
        "[MONTHLY_PAGE_URL]":  f"{base}/monthly-{month_slug}.html",
        "[GUIDE_URL]":         f"{base}/income-statement-guide.html",
        "[CALENDAR_URL]":      f"{base}/earnings-calendar-2026.html",
        "[SOURCES_URL]":       f"{base}/news-sources.html",
    }
    for placeholder, url in replacements.items():
        briefing = briefing.replace(placeholder, url)
    return briefing


def generate_briefing(market: str, news_items_text: str, prices_text: str, earnings_text: str, sentiment_text: str = "", base_url: str = "") -> str:
    settings = load_settings()
    if not base_url:
        base_url = _site_url(settings)
    prompt = _build_briefing_prompt(market, news_items_text, prices_text, earnings_text, sentiment_text)
    briefing = _generate(prompt, max_tokens=settings["analysis"]["briefing_max_tokens"])
    briefing = _inject_site_links(briefing, settings)
    # Append company page links section if site is configured
    if base_url and prices_text:
        briefing += _build_company_links_footer(prices_text, base_url)
    return briefing


def _build_company_links_footer(prices_text: str, base_url: str) -> str:
    """Extract tickers from prices_text and append a direct-link footer."""
    import re
    tickers = re.findall(r'^\s{2}([A-Z0-9.\-]{1,10})\s+\(', prices_text, re.MULTILINE)
    if not tickers:
        return ""
    lines = ["\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             "📊 Company Analysis Pages / 公司分析頁面"]
    for t in tickers:
        lines.append(f"  {t} → {base_url}/stock-{t.lower()}.html")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def generate_intraday_alert(ticker: str, price_data: dict) -> Optional[str]:
    settings = load_settings()
    if not price_data.get("price"):
        return None
    name = price_data.get("name", ticker)
    prompt = _build_alert_prompt(ticker, name, price_data)
    return _generate(prompt, max_tokens=settings["analysis"]["alert_max_tokens"])
