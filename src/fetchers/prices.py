import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import yfinance as yf

from src.utils.helpers import load_watchlist, format_price, format_change
from src.analysis.conviction_score import compute_conviction_score, format_score_for_prompt


# ── Single ticker ──────────────────────────────────────────────────────────────

def fetch_ticker_data(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        change_pct = ((price - prev_close) / prev_close * 100) if price and prev_close and prev_close != 0 else 0.0

        analyst_target = info.get("targetMeanPrice")
        upside = ((analyst_target - price) / price * 100) if analyst_target and price and price != 0 else None

        # FCF margin
        free_cashflow = info.get("freeCashflow")
        total_revenue = info.get("totalRevenue")
        fcf_margin = (free_cashflow / total_revenue) if free_cashflow and total_revenue and total_revenue > 0 else None

        # Cash vs debt
        total_cash = info.get("totalCash")
        total_debt = info.get("totalDebt")

        # Balance sheet deep-fetch (retained earnings, equity ratio, working capital, ROIC)
        retained_earnings = None
        equity_ratio = None
        working_capital = None
        roic = None

        try:
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                col = bs.columns[0]

                def bsget(*keys):
                    for k in keys:
                        if k in bs.index:
                            try:
                                return float(bs.at[k, col])
                            except Exception:
                                pass
                    return None

                total_assets = bsget("Total Assets")
                curr_liab = bsget("Current Liabilities", "Total Current Liabilities")
                curr_assets = bsget("Current Assets", "Total Current Assets")
                stockholders_equity = bsget(
                    "Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity"
                )
                retained_earnings = bsget("Retained Earnings")

                if stockholders_equity and total_assets and total_assets > 0:
                    equity_ratio = stockholders_equity / total_assets
                if curr_assets and curr_liab:
                    working_capital = curr_assets - curr_liab

                # ROIC = EBIT * (1 - ~21% tax) / Invested Capital
                invested_capital = (total_assets or 0) - (curr_liab or 0)
                op_margin = info.get("operatingMargins") or 0
                operating_income = op_margin * (total_revenue or 0)
                if invested_capital > 0 and operating_income:
                    roic = operating_income * 0.79 / invested_capital
        except Exception:
            pass

        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "price": round(price, 2) if price else None,
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change_pct": round(change_pct, 2),
            "day_high": info.get("dayHigh"),
            "day_low": info.get("dayLow"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "USD"),
            # Valuation
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "analyst_target": analyst_target,
            "analyst_upside_pct": round(upside, 1) if upside is not None else None,
            "recommendation": info.get("recommendationKey", ""),
            # Margins
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "net_margin": info.get("profitMargins"),
            # Growth
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            # Quality metrics (items 5-6)
            "roic": roic,
            "fcf_margin": fcf_margin,
            "return_on_equity": info.get("returnOnEquity"),
            # Balance sheet
            "total_cash": total_cash,
            "total_debt": total_debt,
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "equity_ratio": equity_ratio,
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
            # Sector
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            # Analyst & ownership
            "beta": info.get("beta"),
            "insider_pct": info.get("heldPercentInsiders"),
            "institutional_pct": info.get("heldPercentInstitutions"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "recommendation_mean": info.get("recommendationMean"),
            "dividend_yield": info.get("dividendYield"),
            "peg_ratio": info.get("pegRatio"),
            "short_float": info.get("shortPercentOfFloat"),
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "name": ticker,
            "price": None,
            "change_pct": 0.0,
            "currency": "USD",
            "error": str(e),
        }


def fetch_all_prices() -> list:
    watchlist = load_watchlist()
    results = []
    for item in watchlist:
        data = fetch_ticker_data(item["ticker"])
        data["market"] = item.get("market", "US")
        data["note"] = item.get("note", "")
        results.append(data)
    return results


def _fmt_billions(val) -> str:
    if val is None:
        return "N/A"
    b = abs(val) / 1e9
    if b >= 1:
        return f"${b:.1f}B"
    m = abs(val) / 1e6
    return f"${m:.0f}M"


def format_prices_for_prompt(price_data: list) -> str:
    lines = []
    for d in price_data:
        if d.get("price") is None:
            lines.append(f"  {d['ticker']}: Data unavailable")
            continue

        currency = d.get("currency", "USD")
        price_str = format_price(d["price"], currency)
        change_str = format_change(d["change_pct"])

        pe_str = f"Forward P/E: {d['forward_pe']:.1f}" if d.get("forward_pe") else "Forward P/E: N/A"
        target_str = (
            f"Analyst target: {format_price(d['analyst_target'], currency)} "
            f"({'+' if d['analyst_upside_pct'] >= 0 else ''}{d['analyst_upside_pct']}% upside)"
            if d.get("analyst_target") and d.get("analyst_upside_pct") is not None
            else "Analyst target: N/A"
        )
        rec = d.get("recommendation", "").upper() or "N/A"

        # Quality metrics line
        quality_parts = []
        if d.get("roic") is not None:
            r = d["roic"] * 100
            flag = "✓" if r >= 15 else "⚠"
            quality_parts.append(f"ROIC {r:.0f}% {flag}")
        if d.get("revenue_growth") is not None:
            rg = d["revenue_growth"] * 100
            flag = "✓" if rg >= 10 else "⚠"
            quality_parts.append(f"Rev growth {'+' if rg >= 0 else ''}{rg:.0f}% {flag}")
        if d.get("fcf_margin") is not None:
            fm = d["fcf_margin"] * 100
            flag = "✓" if fm >= 20 else "⚠"
            quality_parts.append(f"FCF margin {fm:.0f}% {flag}")

        # Balance sheet line
        bs_parts = []
        if d.get("total_cash") and d.get("total_debt"):
            cash = d["total_cash"] / 1e9
            debt = d["total_debt"] / 1e9
            ratio = cash / debt if debt > 0 else 99
            bs_parts.append(f"Cash {_fmt_billions(d['total_cash'])} / Debt {_fmt_billions(d['total_debt'])} ({ratio:.1f}x)")
        elif d.get("total_cash"):
            bs_parts.append(f"Cash {_fmt_billions(d['total_cash'])} / Debt $0 (no debt)")
        if d.get("equity_ratio") is not None:
            bs_parts.append(f"Equity ratio {d['equity_ratio']*100:.0f}%")
        if d.get("working_capital") is not None:
            bs_parts.append(f"Working capital {_fmt_billions(d['working_capital'])}")
        if d.get("retained_earnings") is not None:
            bs_parts.append(f"Retained earnings {_fmt_billions(d['retained_earnings'])}")

        line = (
            f"  {d['ticker']} ({d.get('name', '')})\n"
            f"    Price: {price_str} | Change: {change_str}\n"
            f"    {pe_str} | {target_str}\n"
            f"    Recommendation: {rec} | Sector: {d.get('sector', 'N/A')}"
        )
        if quality_parts:
            line += f"\n    Quality: {' | '.join(quality_parts)}"
        if bs_parts:
            line += f"\n    Balance sheet: {' | '.join(bs_parts)}"
        cs = compute_conviction_score(d)
        line += f"\n    {format_score_for_prompt(cs)}"
        lines.append(line)
    return "\n\n".join(lines)


def format_prices_for_briefing(price_data: list, base_url: str = "") -> str:
    """Like format_prices_for_prompt but appends a company page link when base_url is set."""
    lines = []
    for d in price_data:
        if d.get("price") is None:
            lines.append(f"  {d['ticker']}: Data unavailable")
            continue

        currency = d.get("currency", "USD")
        price_str = format_price(d["price"], currency)
        change_str = format_change(d["change_pct"])

        pe_str = f"Forward P/E: {d['forward_pe']:.1f}" if d.get("forward_pe") else "Forward P/E: N/A"
        target_str = (
            f"Analyst target: {format_price(d['analyst_target'], currency)} "
            f"({'+' if d['analyst_upside_pct'] >= 0 else ''}{d['analyst_upside_pct']}% upside)"
            if d.get("analyst_target") and d.get("analyst_upside_pct") is not None
            else "Analyst target: N/A"
        )
        rec = d.get("recommendation", "").upper() or "N/A"

        quality_parts = []
        if d.get("roic") is not None:
            r = d["roic"] * 100
            quality_parts.append(f"ROIC {r:.0f}% {'✓' if r >= 15 else '⚠'}")
        if d.get("revenue_growth") is not None:
            rg = d["revenue_growth"] * 100
            quality_parts.append(f"Rev growth {'+' if rg >= 0 else ''}{rg:.0f}% {'✓' if rg >= 10 else '⚠'}")
        if d.get("fcf_margin") is not None:
            fm = d["fcf_margin"] * 100
            quality_parts.append(f"FCF margin {fm:.0f}% {'✓' if fm >= 20 else '⚠'}")

        bs_parts = []
        if d.get("total_cash") and d.get("total_debt"):
            cash = d["total_cash"] / 1e9
            debt = d["total_debt"] / 1e9
            ratio = cash / debt if debt > 0 else 99
            bs_parts.append(f"Cash {_fmt_billions(d['total_cash'])} / Debt {_fmt_billions(d['total_debt'])} ({ratio:.1f}x)")

        ticker = d["ticker"]
        line = (
            f"  {ticker} ({d.get('name', '')})\n"
            f"    Price: {price_str} | Change: {change_str}\n"
            f"    {pe_str} | {target_str}\n"
            f"    Recommendation: {rec} | Sector: {d.get('sector', 'N/A')}"
        )
        if quality_parts:
            line += f"\n    Quality: {' | '.join(quality_parts)}"
        if bs_parts:
            line += f"\n    Balance sheet: {' | '.join(bs_parts)}"
        cs = compute_conviction_score(d)
        line += f"\n    {format_score_for_prompt(cs)}"
        if base_url:
            line += f"\n    📊 Full analysis: {base_url}/stock-{ticker.lower()}.html"
        lines.append(line)
    return "\n\n".join(lines)


# ── Market-wide sentiment ──────────────────────────────────────────────────────

SECTOR_ETFS = [
    {"ticker": "XLK",  "name": "Technology",       "name_zh": "科技"},
    {"ticker": "XLF",  "name": "Financials",        "name_zh": "金融"},
    {"ticker": "XLE",  "name": "Energy",            "name_zh": "能源"},
    {"ticker": "XLV",  "name": "Healthcare",        "name_zh": "醫療"},
    {"ticker": "XLI",  "name": "Industrials",       "name_zh": "工業"},
    {"ticker": "XLP",  "name": "Cons. Staples",     "name_zh": "必需消費"},
    {"ticker": "XLY",  "name": "Cons. Disc.",       "name_zh": "非必需消費"},
    {"ticker": "XLC",  "name": "Comm. Services",    "name_zh": "通訊服務"},
    {"ticker": "XLB",  "name": "Materials",         "name_zh": "原材料"},
    {"ticker": "XLRE", "name": "Real Estate",       "name_zh": "房地產"},
]


def fetch_market_sentiment() -> dict:
    """Fetch VIX fear gauge, 10Y Treasury yield, and sector rotation data."""
    result = {"vix": None, "treasury_10y": None, "sectors": []}

    try:
        info = yf.Ticker("^VIX").info
        result["vix"] = info.get("regularMarketPrice") or info.get("previousClose")
    except Exception:
        pass

    try:
        info = yf.Ticker("^TNX").info
        result["treasury_10y"] = info.get("regularMarketPrice") or info.get("previousClose")
    except Exception:
        pass

    for s in SECTOR_ETFS:
        try:
            info = yf.Ticker(s["ticker"]).info
            price = info.get("regularMarketPrice") or info.get("currentPrice")
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            change = round((price - prev) / prev * 100, 2) if price and prev and prev > 0 else None
            result["sectors"].append({**s, "change_pct": change})
        except Exception:
            result["sectors"].append({**s, "change_pct": None})

    return result


def fetch_ticker_technical(ticker: str) -> dict:
    """Fetch RSI-14, 50/200-day MAs, and volume ratio for a ticker."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty or len(hist) < 14:
            return {}

        close = hist["Close"]
        current = float(close.iloc[-1])

        # RSI-14
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = float((100 - 100 / (1 + rs)).iloc[-1])

        # Moving averages
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(hist) >= 50 else None
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(hist) >= 200 else None

        # Volume vs 20-day average
        vol_today = float(hist["Volume"].iloc[-1])
        vol_avg20 = float(hist["Volume"].rolling(20).mean().iloc[-1])
        vol_ratio = round(vol_today / vol_avg20, 1) if vol_avg20 > 0 else 1.0

        return {
            "rsi": round(rsi, 1),
            "ma50": round(ma50, 2) if ma50 else None,
            "ma200": round(ma200, 2) if ma200 else None,
            "above_ma50": current > ma50 if ma50 else None,
            "above_ma200": current > ma200 if ma200 else None,
            "volume_ratio": vol_ratio,
        }
    except Exception:
        return {}


def fetch_quarterly_data(ticker: str) -> list:
    """Return last 4 quarters: [{period, revenue, gross_profit, net_income, gross_margin}]."""
    try:
        t = yf.Ticker(ticker)
        qf = t.quarterly_financials
        if qf is None or qf.empty:
            return []
        result = []
        for col in list(qf.columns)[:4]:
            try:
                label = col.strftime("%b '%y")
            except Exception:
                label = str(col)[:7]

            def qget(*names, _qf=qf, _col=col):
                for n in names:
                    if n in _qf.index:
                        try:
                            v = float(_qf.at[n, _col])
                            return None if (v != v) else v
                        except Exception:
                            pass
                return None

            rev = qget("Total Revenue")
            gross = qget("Gross Profit")
            net = qget("Net Income", "Net Income Common Stockholders")
            result.append({
                "period": label,
                "revenue": rev,
                "gross_profit": gross,
                "net_income": net,
                "gross_margin": (gross / rev) if (gross and rev and rev > 0) else None,
            })
        return result
    except Exception:
        return []


def format_market_sentiment_for_prompt(sentiment: dict) -> str:
    lines = []

    vix = sentiment.get("vix")
    if vix:
        if vix > 30:
            vix_label = "Extreme Fear — market in panic mode"
        elif vix > 20:
            vix_label = "Fear — elevated uncertainty"
        elif vix > 15:
            vix_label = "Neutral — calm conditions"
        else:
            vix_label = "Greed — very low fear, complacency risk"
        lines.append(f"  VIX (Fear Gauge): {vix:.1f} — {vix_label}")

    tnx = sentiment.get("treasury_10y")
    if tnx:
        lines.append(f"  10Y Treasury Yield: {tnx:.2f}% — the benchmark borrowing rate; higher yields pressure growth stocks")

    sectors = [s for s in sentiment.get("sectors", []) if s.get("change_pct") is not None]
    if sectors:
        sorted_s = sorted(sectors, key=lambda x: x["change_pct"], reverse=True)
        lines.append("  Sector Rotation (today's % change):")
        for s in sorted_s:
            sign = "+" if s["change_pct"] >= 0 else ""
            lines.append(f"    {s['name']:18s} ({s['name_zh']}): {sign}{s['change_pct']:.1f}%")

    return "\n".join(lines) if lines else "  Market sentiment data unavailable."
