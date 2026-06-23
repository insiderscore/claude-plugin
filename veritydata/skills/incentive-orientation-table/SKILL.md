---
name: incentive-orientation-table
description: Build a self-contained, sortable HTML graphic-table comparing executive incentive ORIENTATION across a SET of public companies — a fund's holdings, a watchlist, a sector, or any ticker list. Each company is one row with a 100%-stacked bar of its weighted incentive-metric mix (profitability/returns, growth, shareholder-return, other objectives) blended 50/50 across AIP and LTIP, plus printed shares; columns are click-to-sort. Use whenever the user wants to see, across many names at once, what each management is paid to optimize — trigger on "incentive orientation for [fund/watchlist/sector]", "what are these managements paid to optimize", "growth vs profitability vs shareholder-return across [holdings]", "compare comp design across [list]", "sortable incentive table", "metric-mix table for [tickers]", or a bare fund/list name after a prior run. This is the cross-sectional many-company comparison; use incentive-grid or incentive-tearsheet for a single-company deep dive. Requires the Verity MCP connection.
---

# Incentive Orientation Table

Produce one self-contained HTML file: a sortable graphic-table that places a *set* of companies side by side by **what each management's pay plan optimizes for**. Every company is a row carrying a 100%-stacked bar split into four weighted-incentive buckets — profitability/returns, growth, shareholder-return, other objectives — with the AIP (annual) and LTIP (long-term) metric mixes blended 50/50. Printed shares sit beside the bar; column headers sort. The value is letting a reader scan 30–50 names at once and re-rank them by any bucket.

This is the **cross-sectional** sibling of the per-company comp skills. If the user wants one company in depth, use `incentive-grid` (plain tables) or `incentive-tearsheet` (styled one-pager) instead.

## When the universe is a fund or watchlist (resolve it first)

If the request names a fund, manager, or watchlist rather than an explicit ticker list, resolve it to tickers before pulling comp data:

- **Fund / manager / 13F filer** → `Verity:get_fund_holdings(name=...)`. Returns a holdings CSV. Take the **top N by `value`** (default top 50, or whatever the user asks), keeping only common stock — exclude ETFs/ETNs, ADRs of foreign filers, put/call options, warrants, and zero-value rows. Foreign ADRs, SPACs, and "Needs Processing" names will surface later as not-plotted.
- **Watchlist** → `Verity:get_watchlist_tickers`.
- **Sector / industry** → `Verity:get_industry_tickers`.
- **Explicit ticker list** → use as given.

Flag to the user if the resolved set is large (>30) — the table handles it, but density rises. There is no hard cap; ~50 is comfortable on one page.

## Data pulls (Verity MCP — tools are deferred, load via tool_search first)

For the resolved ticker list, in chunks of ~10 tickers:

1. `Verity:get_annual_incentive_plans(tickerlist=[...], year=2025)` — latest AIP year. If `year` returns `[]` for a name, retry that name with **no year** and take the latest available plan.
2. `Verity:get_longterm_incentive_plans(tickerlist=[...], year=2025)` — latest LTIP grant *with weighted metrics*. Multiple grant cycles come back; pick the most recent that has a real `metrics` array (skip 100%-RSU / "No LTIP" / "Needs Processing" cycles when an earlier metric-bearing grant exists).

Pull `mcap` from the records if you want it for context (not required by the renderer).

## Classification — the core judgment

For each plan (AIP and LTIP separately), take every **weighted** metric and assign its weight to one of four buckets by the *underlying measure*:

- **growth** — revenue, ARR/ACV/bookings, volume/units/production, product sales, occupancy, acquisition volume, backlog.
- **profitability / returns** — EBITDA (incl. "EBITDA growth"), operating income, EPS, FCF, AFFO, margins, ROIC/ROIIC/ROE/ROCE/CROIC/CROCE, cost/spend metrics, capex discipline, working-capital & leverage (net debt/EBITDA, DSO, coverage).
- **shareholder return** — *weighted* relative TSR, absolute TSR, absolute stock-price / VWAP hurdles. Dividend growth → here too (note it).
- **other objectives** — individual/strategic, pipeline/clinical, safety, ESG, NPS, customer, culture, operations scorecards.

Rules that matter:
- **rTSR as a modifier is excluded** — if relative TSR only scales an otherwise-decided payout (a +/- band), it is not a weighted metric; drop it and note "rTSR modifier on PSUs excluded." Only count TSR when it carries an explicit weight.
- **Gates are excluded** (e.g. an EPS funding gate). Note when a plan is gated.
- **Multi-year tranche weights sum** into their bucket (e.g. three annual absolute-TSR tranches at 12.5% each → 37.5% shareholder-return).
- **Undisclosed weights** → split the category's weight equally across its metrics and note "weights undisclosed; equal split assumed."
- **One pot missing** → if a company has only an AIP or only a LTIP with weighted metrics, that pot gets 100% of the blend; set a `scope` note ("LTIP only (no AIP)").
- Normalize each pot to sum to 1, then **blend 50/50**: `share = (aip_share + ltip_share) / 2`. If one pot is absent, the present pot is the blend.

Each company's four blended shares must sum to ~1 (the renderer asserts within ±0.03).

**Not plotted.** Foreign filers (Canadian/UK names with no US proxy comp), SPACs, uncovered names, and genuine design absences (discretionary bonus + 100% time-vested RSUs, i.e. *no weighted metric anywhere*) cannot be placed. List them with a one-line reason in `not_plotted` — don't force them onto the chart.

## Build the spec, then render

Assemble a spec JSON (full worked example: `assets/example_aventail_spec.json`):

```json
{
  "group": "Aventail — top 50 holdings by position value (Q1'26 13F)",
  "asof": "June 2026",
  "takeaway": "1–3 sentence cross-sectional read — where the mass sits, the poles, the outliers.",
  "classification_rule": "methodology line (shown in footer)",
  "footer": "Source: Verity (InsiderScore) ... (shown in footer)",
  "points": [
    {"ticker":"PR","company":"Permian Resources",
     "profitability":0.0,"growth":0.0,"sr":1.0,"other":0.0,
     "scope":"LTIP only (no AIP)","note":"100% TSR PSUs: 50% relative + 50% absolute"}
  ],
  "not_plotted": [ {"ticker":"IMO","reason":"foreign filer (Canada) — no US proxy comp data"} ]
}
```

Then render:

```bash
python3 scripts/build_orientation_table.py --spec SPEC.json --output /mnt/user-data/outputs/<universe>_orientation_table.html
```

`present_files` the HTML and give a short chat summary of the cross-sectional findings (where the mass clusters, the poles, the named outliers, any specials worth flagging).

## What the renderer produces (don't rebuild it by hand)

`scripts/build_orientation_table.py` is the whole renderer — spec JSON in, one standalone HTML file out. It already handles:
- the 100%-stacked bars (profitability=near-black, **growth=Verity orange so the scarce signal pops**, shareholder-return=grey, other=pale), with a dotted 50% tick;
- printed P/G/S/O shares beside each bar (growth column inherits the orange);
- **click-to-sort** headers — numeric shares sort descending-first then flip; ticker/company sort alphabetically; ties break by ticker; the active header shows a ▲/▼ in orange;
- default sort by shareholder-return share (the usual headline), the per-name notes/scope column, the not-plotted block, the slim VerityData header logo (inlined base64), and mobile responsiveness.

Do not hand-write the HTML or add a build step — keep it a single dependency-free file. The renderer has no external assets beyond `scripts/verity_logo_b64.txt`, which it inlines.

## Style discipline

- Self-contained HTML only — no SVG chart, no web fonts, no external JS/CSS, no localStorage. It must open by double-click and survive being emailed.
- Color is information, not decoration: orange is reserved for growth (the rare bucket) and the active-sort arrow; everything else is greyscale.
- Dense beats pretty. Every disclosed share appears; analytic judgment lives in the one-line `takeaway` and the per-name notes, not prose.
- Honesty about gaps: gated plans, undisclosed weights, excluded rTSR modifiers, and one-pot-only companies all get a note; not-plottable names are listed with reasons rather than hidden.

## Relationship to the orientation quadrant map

A companion scatter ("orientation map") plots the same blended shares as one dot per company on a profitability↔growth × shareholder-return↔other plane. The quadrant map is the better form when a universe genuinely spreads across all four quadrants; **this sortable table is the better form when a universe clusters** (one axis nearly degenerate), because it avoids overplotting and lets the reader re-rank. When unsure, this table is the safe default for fund/watchlist scans. If the user explicitly wants the 2-D positioning view, build the quadrant map instead.

## Not investment advice

This describes incentive design, not company quality or stock merit. A profitability-tilted plan is not a buy and a growth-tilted plan is not a sell; the table shows what managements are *paid to optimize*, nothing more. Keep that framing in the summary.
