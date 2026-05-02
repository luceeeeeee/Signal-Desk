"""
Deterministic 0-100 conviction score — 4 pillars, no AI.

  Quality    (25 pts) : ROIC, FCF margin, gross margin
  Growth     (25 pts) : revenue growth, earnings growth
  Health     (25 pts) : cash vs debt, equity ratio, analyst upside
  Valuation  (25 pts) : FCF yield, Forward P/E — NEW: penalises overpriced stocks

Score ≥ 75 = Strong Conviction | 55–74 = Moderate | 35–54 = Weak | <35 = Avoid
"""


def compute_conviction_score(price_data: dict) -> dict:
    # ── Quality pillar (25 pts) ─────────────────────────────────────────────
    q = 0
    if price_data.get("roic") is not None:
        r = price_data["roic"] * 100
        if r >= 20:   q += 10
        elif r >= 15: q += 8
        elif r >= 10: q += 4
    if price_data.get("fcf_margin") is not None:
        f = price_data["fcf_margin"] * 100
        if f >= 25:   q += 9
        elif f >= 20: q += 7
        elif f >= 10: q += 4
    if price_data.get("gross_margin") is not None:
        g = price_data["gross_margin"] * 100
        if g >= 60:   q += 6
        elif g >= 40: q += 4
        elif g >= 25: q += 2
    q = min(q, 25)

    # ── Growth pillar (25 pts) ──────────────────────────────────────────────
    g = 0
    if price_data.get("revenue_growth") is not None:
        rg = price_data["revenue_growth"] * 100
        if rg >= 20:   g += 13
        elif rg >= 15: g += 10
        elif rg >= 10: g += 7
        elif rg >= 5:  g += 3
    if price_data.get("earnings_growth") is not None:
        eg = price_data["earnings_growth"] * 100
        if eg >= 20:   g += 12
        elif eg >= 15: g += 10
        elif eg >= 10: g += 7
        elif eg >= 0:  g += 3
    g = min(g, 25)

    # ── Health pillar (25 pts) ──────────────────────────────────────────────
    h = 0
    cash = price_data.get("total_cash") or 0
    debt = price_data.get("total_debt") or 0
    if cash > 0:
        if debt == 0:            h += 8
        elif cash >= debt * 2:   h += 8
        elif cash >= debt:       h += 6
        elif cash >= debt * 0.5: h += 3
    if price_data.get("equity_ratio") is not None:
        eq = price_data["equity_ratio"] * 100
        if eq >= 60:   h += 9
        elif eq >= 45: h += 6
        elif eq >= 30: h += 3
    if price_data.get("analyst_upside_pct") is not None:
        up = price_data["analyst_upside_pct"]
        if up >= 25:   h += 8
        elif up >= 15: h += 5
        elif up >= 5:  h += 2
    h = min(h, 25)

    # ── Valuation pillar (25 pts) — NEW ────────────────────────────────────
    # Prevents high-quality but overpriced stocks from scoring 100/100.
    v = 0

    # FCF yield: free cash flow ÷ market cap — how much cash the business
    # generates per dollar of market value. Compare to 10Y Treasury (~4.5%).
    fcf_yield = price_data.get("fcf_yield")
    if fcf_yield is None:
        # Compute from components if available
        fcf_margin = price_data.get("fcf_margin")
        market_cap = price_data.get("market_cap")
        total_rev = price_data.get("total_revenue") or price_data.get("revenue")
        if fcf_margin and market_cap and total_rev and market_cap > 0:
            fcf_yield = (fcf_margin * total_rev) / market_cap
    if fcf_yield is not None:
        fy = fcf_yield * 100
        if fy >= 6:    v += 12   # Excellent — well above bond yield
        elif fy >= 4:  v += 9    # Competitive with 10Y Treasury
        elif fy >= 2:  v += 5    # Positive but below bond yield
        elif fy >= 0:  v += 2    # Barely positive
        # Negative FCF yield: 0 pts

    # Forward P/E: how much investors pay for each $1 of expected profit.
    # Lower = cheaper. P/E >50 typically means extreme growth expectations baked in.
    fpe = price_data.get("forward_pe")
    if fpe is not None and fpe > 0:
        if fpe < 12:    v += 13  # Cheap — paying less than $12 per $1 of profit
        elif fpe < 18:  v += 10  # Fair value zone
        elif fpe < 25:  v += 6   # Moderate premium
        elif fpe < 40:  v += 3   # Expensive — needs strong growth to justify
        # P/E ≥ 40: 0 pts (priced for perfection)
    v = min(v, 25)

    total = q + g + h + v

    if total >= 75:
        label, color_cls = "Strong Conviction", "s-teal"
    elif total >= 55:
        label, color_cls = "Moderate", "s-amber"
    elif total >= 35:
        label, color_cls = "Weak", "s-red"
    else:
        label, color_cls = "Insufficient Data", "s-muted"

    # Plain-language verdict for the valuation pillar
    if fpe is not None and fpe > 0:
        if fpe < 18:
            val_verdict = f"P/E {fpe:.0f}x — fairly priced or cheap"
        elif fpe < 30:
            val_verdict = f"P/E {fpe:.0f}x — moderate premium"
        else:
            val_verdict = f"P/E {fpe:.0f}x — expensive, priced for high growth"
    else:
        val_verdict = "Valuation data unavailable"

    if fcf_yield is not None:
        fy_pct = fcf_yield * 100
        if fy_pct >= 4:
            fcf_verdict = f"FCF yield {fy_pct:.1f}% — competitive vs. bonds"
        elif fy_pct >= 0:
            fcf_verdict = f"FCF yield {fy_pct:.1f}% — below bond yield"
        else:
            fcf_verdict = f"FCF yield {fy_pct:.1f}% — negative free cash flow"
    else:
        fcf_verdict = "FCF yield — no data"

    # Key metric checks — (display_name, value_str, passing, threshold_label)
    checks = []
    _add_check(checks, price_data, "roic",           "ROIC",         lambda v: f"{v:.0f}%",  lambda v: v >= 15, "≥15%")
    _add_check(checks, price_data, "revenue_growth", "Rev Growth",   lambda v: f"{v:+.0f}%", lambda v: v >= 10, "≥10%")
    _add_check(checks, price_data, "fcf_margin",     "FCF Margin",   lambda v: f"{v:.0f}%",  lambda v: v >= 20, "≥20%")
    _add_check(checks, price_data, "gross_margin",   "Gross Margin", lambda v: f"{v:.0f}%",  lambda v: v >= 40, "≥40%")
    _add_check(checks, price_data, "return_on_equity","ROE",         lambda v: f"{v:.0f}%",  lambda v: v >= 15, "≥15%")
    if fcf_yield is not None:
        fy_pct = fcf_yield * 100
        checks.append(("FCF Yield", f"{fy_pct:.1f}%", fy_pct >= 4, "≥4%"))
    if fpe is not None and fpe > 0:
        checks.append(("Fwd P/E", f"{fpe:.1f}x", fpe < 25, "<25x"))

    return {
        "score": total,
        "label": label,
        "color_cls": color_cls,
        "pillar_quality":      q,
        "pillar_quality_max":  25,
        "pillar_growth":       g,
        "pillar_growth_max":   25,
        "pillar_health":       h,
        "pillar_health_max":   25,
        "pillar_valuation":    v,
        "pillar_valuation_max": 25,
        "val_verdict":         val_verdict,
        "fcf_verdict":         fcf_verdict,
        "checks": checks,
    }


def _add_check(checks, data, key, name, fmt, passing_fn, threshold):
    val = data.get(key)
    if val is None:
        return
    pct = val * 100
    checks.append((name, fmt(pct), passing_fn(pct), threshold))


def format_score_for_prompt(cs: dict) -> str:
    """One-line conviction summary for inclusion in the AI briefing prompt."""
    passing = [c[0] for c in cs["checks"] if c[2]]
    flagged = [c[0] for c in cs["checks"] if not c[2]]
    return (
        f"⭐ Conviction Score: {cs['score']}/100 — {cs['label']}"
        f" | Quality {cs['pillar_quality']}/{cs['pillar_quality_max']}"
        f" · Growth {cs['pillar_growth']}/{cs['pillar_growth_max']}"
        f" · Health {cs['pillar_health']}/{cs['pillar_health_max']}"
        f" · Valuation {cs['pillar_valuation']}/{cs['pillar_valuation_max']}"
        + (f" | ✓ {', '.join(passing)}" if passing else "")
        + (f" | ⚠ {', '.join(flagged)}" if flagged else "")
    )
