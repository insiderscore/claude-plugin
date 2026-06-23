---
name: ltip-metrics
description: Screen a SET of public companies for names that introduced a NEW long-term incentive (LTIP) metric in their latest grant cycle versus the prior one, and render a sortable VerityData-styled HTML table (one row per hit — prior→latest cycle, count of new metrics, latest metric set with new ones highlighted). A metric is "new" if its normalized base name is in the latest metric-bearing cycle but absent from the prior. Use to find where management changed what its long-term plan rewards — trigger on "names with new LTIP metrics", "who added a new LTIP/PSU metric", "what changed in the long-term plans across [fund/watchlist/sector]", "did anyone add a [growth/FCF/TSR] metric", or a bare universe/list after a prior run. Accepts any universe — a fund/13F filer’s holdings, a watchlist, a sector, or a ticker list. This is the cross-cycle CHANGE screen; use incentive-orientation-table for the static metric-mix view and incentive-grid/incentive-tearsheet for single-company deep dives. Requires the Verity MCP connection.
---

# New LTIP Metrics Screen

Find companies that **just changed what their long-term plan rewards** — specifically, names whose latest LTIP grant cycle introduced a performance metric that was not in the prior cycle. Output is one self-contained sortable HTML table in the VerityData house style (the same visual language as `incentive-orientation-table`): one row per hit, prior→latest cycle, a count of new metrics, and the latest metric set with the **new** metrics as orange chips, carried-over as grey, dropped as struck-through.

A new metric is a real signal: it usually marks a deliberate pivot in what management wants to be judged on (e.g. adding an ARR or AI-product target, swapping bookings for FCF margin, layering absolute TSR onto relative). The screen's job is to surface those pivots across a whole universe at once.

This is the **cross-cycle change** screen. For the static "what does each plan optimize for" mix, use `incentive-orientation-table`. For one company in depth, use `incentive-grid` or `incentive-tearsheet`.

## Step 1 — Resolve the universe (accept any of four forms)

The user may give any of these; resolve to a ticker list first:

- **Fund / manager / 13F filer** → `Verity:get_fund_holdings(name=...)`; take the top N by `value` (default top 50 or as asked), common stock only (drop ETFs/ETNs, foreign ADRs, options, warrants, zero-value rows).
- **Watchlist** → `Verity:get_watchlist_tickers`.
- **Sector / industry** → `Verity:get_industry_tickers` (or pass `industry=` straight to the LTIP tool).
- **Explicit ticker list** → use as given.

Flag if the resolved set is large (>40) — the table handles it, but the more useful framing is usually "here are the N names that changed," so the not-a-hit names collapse into the two footer blocks. In practice a 50-name fund book yields a low-double-digit hit count; the value of the run is as much the *filtered-out* names (relabels, unchanged, can't-screen) as the hits, so surface all three groups.

## Step 2 — Pull LTIP history (Verity MCP — tools are deferred, load via tool_search first)

For the resolved list, in chunks of ~10 tickers, call `Verity:get_longterm_incentive_plans(tickerlist=[...])` **with no `year`** so you get the full set of grant cycles per company (the tool returns every cycle on file, not just one year). Do NOT pin a single year — you need at least two cycles to diff.

Each record is one grant cycle and carries:
- `startyear` / `endyear` — the cycle (use to order cycles and to label `prior_cycle` / `latest_cycle`, e.g. `FY24–26`).
- `status` — e.g. `Processed - Initial` (newest, forward-looking) vs `Processed - Complete`.
- `metrics[]` — each with `name`, `original_name`, `classification` (`Financial`, `rTSR`, `Operational`, `Strategic`, …), and `weight`.
- sometimes `forwardlookingmetricdetails` / `formula_note` — Verity's own prose, which often states outright that a metric was added ("PSUs added a new operating metric…"). Use it to corroborate and to write the per-name note, but base the hit on the metric-set diff, not the prose.

## Step 3 — The detection logic (the core judgment)

`scripts/diff_ltip_cycles.py` does the mechanical first pass: save each Verity pull to a JSON file (the auto-saved `{"type":"text","text":...}` wrapper is handled, as is a bare array), then run `python3 scripts/diff_ltip_cycles.py pull1.json pull2.json ...`. It orders metric-bearing cycles, tranche-normalizes, applies a canonical-synonym map, and prints per-company `candidate-new / carried / dropped`. Treat its `candidate-new` as exactly that — **candidates**; the relabel judgment in step 5 is yours, not the script's. The steps below are what the script implements (3–4, 6) plus the judgment it cannot (5).

For each company:

1. **Order the metric-bearing cycles by `startyear`.** A "metric-bearing" cycle has a non-empty `metrics[]` with at least one weighted performance metric. **Skip cycles that are 100% time-vested RSUs / "No LTIP" / "Needs Processing"** — they have nothing to diff. If after this filter a company has fewer than two metric-bearing cycles, it goes to `not_screened` ("only one metric-bearing cycle on file").

2. **Take the latest cycle and the immediately prior metric-bearing cycle.**

3. **Normalize each metric to a base name before comparing.** This is essential and the #1 source of false positives if skipped. Multi-year plans split one metric into tranches — `Non-GAAP Operating Margin - Year 1/2/3`, `Margin & Growth - Year 1/2` — which are the *same* metric, not new ones. Strip trailing tranche/year/period suffixes (`- Year N`, `- Yr N`, `(FY..)`, `Tranche N`, roman-numeral tails) and lower-case/trim, then dedupe. Compare on these base names. Prefer `original_name` when it is the un-suffixed form; otherwise strip `name`.

4. **Diff the normalized sets:**
   - **new** = base names in latest but not in prior → the *candidate* hit signal.
   - **carried** = in both.
   - **dropped** = in prior but not in latest (shown for context; a drop alone is not a hit).

5. **Filter candidate-new metrics for relabels — the single most important judgment.** Tranche-stripping (step 3) is mechanical; this step is not, and it is where a naive screen produces most of its false positives. A candidate-new metric that pairs with a dropped metric describing the *same underlying measure* is a **relabel, not a new metric** — move it to a note and treat the company as no-change unless a genuinely new measure remains. Apply a canonical-synonym map and watch for these recast patterns (all seen in real data):
   - **Abbreviation / spelling:** "Non-GAAP EPS" ↔ "Non-GAAP Earnings Per Share (EPS)"; "Adjusted EPS" ↔ "Earnings Per Share (EPS)"; "ABV Growth" ↔ "Adjusted Book Value Per Share Growth"; "OEPS" ↔ "EPS"; "rTSR"/"R-TSR"/"RTSR PSUs"/"Peer-relative TSR" ↔ "Relative TSR".
   - **Window prefix:** "ROA" ↔ "Three-Year Average ROA"; "Growth in Adjusted TBV" ↔ "3-Year Average Growth in Adjusted TBV". The proxy's `forwardlookingmetricdetails` often says outright "metrics remained the same" — trust it.
   - **"Relative" prefix added or dropped:** "Operating Margin" ↔ "Relative Operating Margin"; "Return on Equity" ↔ "Relative Return on Equity". This is a genuine *reframing of the same measure* (absolute→peer-relative), not a new metric — note it as "reframed: absolute→relative" but do NOT count it as new. (Optionally surface these as a distinct "reframed" class if the user asks.)
   - **Rate↔dollar / CAGR↔annual recast:** "Non-GAAP Operating Margin" → "Non-GAAP Operating Income"; "Revenue CAGR" → "Revenue Growth". These are borderline — the measure's *intent* is the same but the construction differs. Default to counting them as new (the plan now rewards a different number) but say so plainly in the note.
   - **Reversion:** a metric that was the company's long-standing measure, dropped for one cycle, then restored, is technically "absent prior / present latest" but is a *reversion*, not a fresh idea (e.g. a name that ran 100% rTSR for years, tried revenue PSUs for one cycle, then returned to rTSR). Keep it in the table but flag "reversion, not a new metric" in the note.

   The test: would a compensation analyst reading both proxies say the company *added a new thing to optimize*, or *renamed/recast something it already had*? Only the former is a hit. When the only candidate-new metrics are relabels/reframes, the company belongs in `no_change` with a reason like "relabel only — 'X' = prior 'Y'".

6. **Exclusions (do not count as metrics):**
   - **rTSR used only as a modifier** (scales an otherwise-decided payout via a +/- band, no explicit weight). In the Verity data these appear in the record's `modifiers[]` array, NOT `metrics[]` — so reading metrics only from `metrics[]` excludes them automatically. Note "rTSR modifier excluded." Count TSR only when it carries a weight inside `metrics[]`.
   - **Funding gates** (e.g. an EPS gate that only switches the plan on) — drop; note "gated."
   - A pure **weight change** on an already-present metric is **not** a new metric (that's the orientation table's job). This screen is about the *presence* of a metric name, per the spec: absent prior, present latest.

7. **A company is a hit (goes in `points`) iff a genuinely-new metric survives the relabel filter.** Comparable names whose only candidate-new metrics were relabels/reframes — or which had no candidate-new at all — go to `no_change` with a reason. Non-comparable names go to `not_screened` (one cycle only, foreign filer with no US proxy, no weighted-metric cycle / 100%-RSU both cycles, CEO takes no performance LTIP, or simply not returned by the provider in this run).

Worked example (real data, Salesforce/CRM): cycles by `startyear` are FY22 (100% rTSR) → FY23 (100% rTSR) → FY24 (rTSR + Non-GAAP Operating Margin ×3 tranches) → FY25 (same) → FY26 (rTSR + Margin & Growth ×3 + **Agentforce & Data 360 ARR**). Latest = FY26, prior = FY24/25. After tranche-normalization the new base names are **Agentforce & Data 360 ARR** and **Margin & Growth**; Relative TSR and Non-GAAP Operating Margin are carried. Two new metrics → CRM is a hit, and `forwardlookingmetricdetails` confirms the add.

## Step 4 — Build the spec, then render

Assemble a spec JSON. Two worked examples ship with the skill: `assets/example_spec.json` (a small illustrative set) and `assets/example_lsv_top50_spec.json` (a real fund-scale run — LSV Asset Management's top 50 13F holdings, with `assets/example_lsv_top50.html` as the rendered output). The LSV spec is the better reference for a fund/watchlist scan: it shows how 50 names resolve into ~13 genuine hits, a large `no_change` block (including the relabel exclusions, each with a "relabel only — 'X' = prior 'Y'" reason), and a `not_screened` block (no-LTIP CEOs, single-cycle names, a provider gap).

Only hits go in `points`; each needs `new` (genuinely-new base names, display-cased), and should include `carried`, `dropped`, `prior_cycle`, `latest_cycle`, and a one-line `note` saying what the new metric signals. Put comparable-but-unchanged names — and relabel/reframe-only names — in `no_change` with a reason; put non-comparable names in `not_screened` with a reason.

```bash
python3 scripts/build_new_ltip_table.py --spec SPEC.json --output /mnt/user-data/outputs/<universe>_new_ltip_metrics.html
```

Then `present_files` the HTML and give a short chat summary: how many names changed, the most notable adds (and what theme they point to — growth/AI, profitability/FCF, shareholder-return), and any pattern across the universe.

## What the renderer produces (don't rebuild it by hand)

`scripts/build_new_ltip_table.py` is the whole renderer — spec JSON in, one standalone HTML file out. It already handles:
- one row per company: ticker, company, `prior → latest` cycle, **# new** (orange), the latest metric set as chips (new = orange filled, carried = grey, dropped = dashed strike-through), and a "what it signals" note;
- **click-to-sort** headers — # new sorts descending-first then flips, ticker/company/cycle sort alphabetically, ties break by ticker, active header shows ▲/▼ in orange; default sort is # new descending (biggest design change on top);
- the two footer blocks (`no_change`, `not_screened`), the slim VerityData header logo (inlined base64), and mobile responsiveness.

Do not hand-write the HTML or add a build step — keep it a single dependency-free file. The only external asset is `scripts/verity_logo_b64.txt`, which the renderer inlines.

## Style discipline

- Self-contained HTML only — no SVG, no web fonts, no external JS/CSS, no localStorage. Opens by double-click, survives being emailed.
- Color is information, not decoration: **orange is reserved for the new metric** (the scarce signal) and the active-sort arrow — same convention as the orientation table, where orange marks the rare bucket. Everything else is greyscale.
- Dense beats pretty. Show the full latest metric set so the new chips read in context; analytic judgment lives in the one-line `takeaway` and the per-name notes, not prose.
- Honesty about gaps: tranche-normalization assumptions, excluded rTSR modifiers, gated plans, and one-cycle/foreign/RSU-only names all get surfaced — hits in the table with notes, non-hits in the two footer blocks with reasons. Never hide a name you couldn't screen.

## Not investment advice

This describes a change in incentive-plan *design*, not company quality or stock merit. Adding a growth metric is not a buy signal and dropping one is not a sell signal; the screen shows where management changed what it is paid to optimize, nothing more. Keep that framing in the summary.
