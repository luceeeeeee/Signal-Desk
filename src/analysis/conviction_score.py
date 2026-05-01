"""
Deterministic 0-100 conviction score — computed from fundamentals, no AI.
Three pillars totaling 100 points:
  Quality (33 pts) : ROIC, FCF margin, gross margin
  Growth  (34 pts) : revenue growth, earnings growth
  Health  (33 pts) : cash vs debt, equity ratio, analyst upside

Thresholds (user-defined):
  ROIC ≥ 15%          strong quality
  Revenue growth ≥ 10% healthy growth
  FCF margin ≥ 20%    strong cash conversion
"""


def compute_conviction_score(price_data: dict) -> dict:
    # ── Quality pillar (33 pts) ─────────────────────────────────────────────
    q = 0
    if price_data.get("roic") is not None:
        r = price_data["roic"] * 100
        if r >= 20:   q += 13
        elif r >= 15: q += 10
        elif r >= 10: q += 5
    if price_data.get("fcf_margin") is not None:
        f = price_data["fcf_margin"] * 100
        if f >= 25:   q += 12
        elif f >= 20: q += 10
        elif f >= 10: q += 5
    if price_data.get("gross_margin") is not None:
        g = price_data["gross_margin"] * 100
        if g >= 60:   q += 8
        elif g >= 40: q += 6
        elif g >= 25: q += 3
    q = min(q, 33)

    # ── Growth pillar (34 pts) ──────────────────────────────────────────────
    g = 0
    if price_data.get("revenue_growth") is not None:
        rg = price_data["revenue_growth"] * 100
        if rg >= 20:   g += 17
        elif rg >= 15: g += 14
        elif rg >= 10: g += 10
        elif rg >= 5:  g += 5
    if price_data.get("earnings_growth") is not None:
        eg = price_data["earnings_growth"] * 100
        if eg >= 20:   g += 17
        elif eg >= 15: g += 14
        elif eg >= 10: g += 10
        elif eg >= 0:  g += 5
    g = min(g, 34)

    # ── Health pillar (33 pts) ──────────────────────────────────────────────
    h = 0
    cash = price_data.get("total_cash") or 0
    debt = price_data.get("total_debt") or 0
    if cash > 0:
        if debt == 0:             h += 11
        elif cash >= debt * 2:    h += 11
        elif cash >= debt:        h += 8
        elif cash >= debt * 0.5:  h += 4
    if price_data.get("equity_ratio") is not None:
        eq = price_data["equity_ratio"] * 100
        if eq >= 60:   h += 12
        elif eq >= 45: h += 8
        elif eq >= 30: h += 4
    if price_data.get("analyst_upside_pct") is not None:
        up = price_data["analyst_upside_pct"]
        if up >= 25:   h += 10
        elif up >= 15: h += 7
        elif up >= 5:  h += 4
    h = min(h, 33)

    total = q + g + h

    if total >= 75:
        label, color_cls = "Strong Conviction", "s-teal"
    elif total >= 55:
        label, color_cls = "Moderate", "s-amber"
    elif total >= 35:
        label, color_cls = "Weak", "s-red"
    else:
        label, color_cls = "Insufficient Data", "s-muted"

    # Key metric checks — (display_name, value_str, passing, threshold_label)
    checks = []
    _add_check(checks, price_data, "roic",           "ROIC",        lambda v: f"{v:.0f}%", lambda v: v >= 15, "≥15%")
    _add_check(checks, price_data, "revenue_growth",  "Rev Growth",  lambda v: f"{v:+.0f}%", lambda v: v >= 10, "≥10%")
    _add_check(checks, price_data, "fcf_margin",      "FCF Margin",  lambda v: f"{v:.0f}%", lambda v: v >= 20, "≥20%")
    _add_check(checks, price_data, "gross_margin",    "Gross Margin",lambda v: f"{v:.0f}%", lambda v: v >= 40, "≥40%")
    _add_check(checks, price_data, "return_on_equity","ROE",         lambda v: f"{v:.0f}%", lambda v: v >= 15, "≥15%")

    return {
        "score": total,
        "label": label,
        "color_cls": color_cls,
        "pillar_quality":     q,
        "pillar_quality_max": 33,
        "pillar_growth":      g,
        "pillar_growth_max":  34,
        "pillar_health":      h,
        "pillar_health_max":  33,
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
        + (f" | ✓ {', '.join(passing)}" if passing else "")
        + (f" | ⚠ {', '.join(flagged)}" if flagged else "")
    )
