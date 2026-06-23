---
name: riskfactor-change-table
description: Build a self-contained, sortable HTML table (plus a matching single-page PDF) showing how each company in a SET changed its SEC risk factors (Item 1A) in its latest 10-K/10-Q versus the prior annual filing. Each company is one row with a change-anatomy bar (new / major-rewrite / moderate / minor / unchanged segments), printed counts (new, deleted, major, moderate, total-changed, total), and a one-line plain-English read of what actually changed, pulled from the filing diffs. Columns are click-to-sort. Use whenever the user wants a cross-sectional view of risk-factor changes across a fund's holdings, a watchlist, a CIK's positions, a sector, or any ticker list — trigger on "risk factor changes for [list/fund/cik]", "what changed in the 10-Ks", "who rewrote their risk factors", "new risk factors across [holdings]", "risk factor diff table", "Item 1A changes", or a bare fund/CIK/list after a prior run. Produces both .html and .pdf. Requires the Verity MCP connection.
---

# Risk-Factor Change Table

Produce a sortable HTML table — and a matching single-page PDF — that places a *set* of companies side by side by **how much, and how, each one changed its Item 1A risk factors** in its most recent annual filing versus the prior year. Each row carries: a change-anatomy bar (what fraction of the current risk section is newly added, majorly rewritten, moderately changed, minorly tweaked, or carried forward unchanged), the printed counts, and a one-line annotation of what actually changed, written from the real filing diffs.

This is the cross-sectional risk-disclosure sibling of the incentive skills. It does not assess company quality — it summarizes disclosure movement.

## Step 1 — Resolve the universe to a ticker list

The input may be explicit tickers or a named entity. Resolve named entities to a ticker list first (Verity tools are deferred — load via tool_search):

- **Fund / manager / 13F filer by name** → `Verity:get_fund_holdings(name=...)`.
- **13F filer by CIK** → `Verity:get_fund_holdings(rptcik=<int>)`.
- **Watchlist** → `Verity:get_watchlist_tickers`.
- **Sector / industry** → `Verity:get_industry_tickers`.
- **Explicit tickers** → use as given.

For holdings, take the **top N by position value** (default 30) keeping only **common-stock long** positions — exclude put/call options, ETFs/ETNs, ADRs of foreign filers, and zero-value (exited) rows. Hedge-fund 13Fs are messy: a single ticker may appear as Common + Put + Call rows; keep only the Common long. Foreign filers and SPACs will surface later as not-plotted. Flag to the user if the resolved set exceeds ~35 (the table handles it; density rises).

## Step 2 — Pull risk-factor counts (one call per ~10 tickers)

`Verity:get_risk_factor_counts(tickers=[...], year=<current year>)` returns, per filing: `iacc`, `datefiled`, `formtype`, `new`, `deleted`, `total_changed`, `big_changed`, `medium_changed`, `small_changed`, `tiny_changed`, `total`, `unchanged`, `unusual`. Names that return nothing are foreign 20-F filers, recent spin-offs/IPOs with no prior filing to diff, or simply not covered — record them for the not-plotted block with a reason. Keep the `iacc` for each plotted name; it's the key for Step 3.

## Step 3 — Pull the diffs and write the annotations (ALL plotted names)

For every plotted name, fetch the actual changed text and condense it to one line. Pull in batches of ~8 iaccs:

```
Verity:get_filing_content(iacc_list=[...], change_type=["N","F"], tlitem_short="risk")
```

`change_type` `N`=new, `F`=major (the "F" major-change bucket). Each returned section has a `title` and `body` — read them and write a single sentence naming the *substantive* additions and rewrites (the merger, the new convertible notes, the drug-pricing factor, the spin-off, the new material weakness), not the boilerplate. Some names return an empty `sections` list — that means all their changes fell below the major threshold; annotate those honestly as a routine roll-forward rather than inventing significance. Do **not** pad: if only minor edits exist, say so.

Annotation discipline:
- Name the actual thing that changed, in plain English, in one sentence.
- Distinguish transactional/policy churn (M&A, leverage, spin-offs, tariffs, drug pricing, AI factors) from genuine red flags (newly disclosed material weakness, going-concern, covenant breach). Call red flags what they are; don't dress up housekeeping as deterioration.
- For empty-diff names, state the absence ("routine roll-forward — no new or major-rewritten factors above the threshold").
- These are compressions, not substitutes for the filing; the spec keeps each `iacc` so the full text is recoverable.

## Step 4 — Assemble the spec and render

Build a spec JSON (full worked example: `assets/example_rf_spec.json`). Per-point fields: `ticker`, `company`, `date`, `form`, `new`, `deleted`, `big`, `medium`, `small`, `tiny`, `unchanged`, `total`, `unusual`, and `note` (the one-line annotation). Top-level: `group`, `asof`, `filing_window`, `takeaway`, `footer`, `not_plotted` (list of `{ticker, reason}`).

```bash
python3 scripts/build_riskfactor_table.py --spec SPEC.json --output /mnt/user-data/outputs/<universe>_riskfactor_changes.html
python3 scripts/to_pdf.py --html /mnt/user-data/outputs/<universe>_riskfactor_changes.html --output /mnt/user-data/outputs/<universe>_riskfactor_changes.pdf
```

`present_files` **both** the HTML and the PDF. Then give a short chat summary of the cross-sectional themes (where the heavy rewrites cluster, the shared threads, the genuine red flags).

## The `takeaway` field — state findings, never process

The `takeaway` is the "WHAT IT MEANS" banner. It must read as analysis of the book, not narration of how the view was built. Never write meta-commentary like "every name now carries a one-line read…", "this table shows…", or "after pulling the diffs…". Open directly on the finding ("The movers cluster into clear themes: …"). State what the data shows; do not describe the assembling of it. This is a hard rule — the field tends to drift into self-description, so check it before rendering.

## What the renderer produces (don't rebuild it by hand)

`scripts/build_riskfactor_table.py` is the whole renderer — spec JSON in, one standalone HTML file out. It handles:
- the change-anatomy bar scaled to each company's total factors: new (orange), major rewrite (dark red), moderate (amber), minor (grey), unchanged (pale); deleted shown as a separate count left of the magnitude columns since deleted factors aren't in the current section;
- printed counts with new and major emphasized; a "Chg" (total changed) and "Tot" column;
- **click-to-sort** headers (numeric descending-first then flip; ticker/company/date alphabetical; ties break by ticker; active header shows ▲/▼ in orange); default sort is total-changed descending;
- the per-name annotation column, the not-plotted block, the inline VerityData logo, mobile responsiveness, and the methodology footer.

`scripts/to_pdf.py` renders the HTML to a single-page PDF sized to the table's true width and height (no clipping, no pagination) via headless Chromium. The table is wide (~14in); that's expected and prints on one landscape-ish page.

Keep both outputs self-contained — no external assets beyond `scripts/verity_logo_b64.txt`, which the renderer inlines.

## Reading the bar (analyst judgment)

- A long bar that is mostly grey/pale (e.g. high `total_changed` but all minor/tiny) is *churn without substance* — copy-edits, not new risk. Don't let a high "Chg" count read as alarming; the annotation should say "routine."
- New (orange) and major-rewrite (dark red) segments are the signal. A small bar that is mostly orange/dark-red (like a near-total rewrite around a launch or merger) is the real mover.
- `deleted` is informative too: large deletions usually mean a merger reset or a business-line exit, not reduced risk.
- `unusual` flags filings Verity considers anomalous; worth a closer read but not automatically meaningful.

## Not investment advice

This describes disclosure changes, not company merit. A heavy rewrite is often transactional (a merger, a financing, a spin-off) rather than bad news. Keep that framing in the summary and never imply that more change = worse stock.
