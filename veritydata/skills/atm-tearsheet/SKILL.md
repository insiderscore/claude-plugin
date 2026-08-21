---
name: atm-tearsheet
description: Generate a single-page ATM (at-the-market) program tear sheet for one public company from Verity (InsiderScore) data, headlined by the capacity reservoir — authorized shelf capacity draining with each disclosed sale and refilling at each new program — with pace, runway in quarters, the refill habit, quarterly cadence with insider selling beneath it, agent fees, and the plan ledger. Client-accessible Verity tools only; every price is a disclosed print — no market feed, no price chart, no scores. Trigger on "ATM tear sheet for [ticker]", "how has [ticker] used its ATM", "how much ATM/shelf capacity is left", "when does the ATM run out", "ATM overhang", "how dilutive has the ATM been", "what did they raise and at what average price", "disciplined or serial diluter", or a bare ticker after a prior ATM tear sheet. Produces a self-contained HTML tear sheet plus a one-page PDF in the Verity house style. Single-name deep-dive, not a screen. Requires the Verity MCP connection.
---

# ATM Issuance Tear Sheet

Build a dense, single-page HTML tear sheet (plus a one-page PDF) that judges one public company's **at-the-market equity program** the way you'd judge an insider: as a **seller of its own stock**. The audience is sophisticated (PMs, analysts); the register is an accountant's — state measured facts, let the data carry the story, never editorialize.

The organizing idea: an ATM is a **revolving pipe**. The sheet answers, in order: how much more can be printed without asking anyone (live capacity), how fast it drains (pace, runway in quarters), whether "remaining" is a ceiling or a revolving figure (the refill habit and utilization of retired shelves), what it has cost and produced to date (raised, blended VWAP, fees, dilution), and whether insiders' own money behaves like the treasury's. Every price that appears is a *disclosed print* — a tranche's realized price per share, a filing's implied price (`remaining_dollars ÷ remaining_shares`), or an insider Form 4 transaction price. No market-data feed, no price chart, and deliberately no summary score: the program is described, not graded.

The deterministic work — every metric, the reservoir reconstruction, all SVG and CSS — is owned by `scripts/build_atm_tearsheet.py`, which consumes the **raw tool CSVs** directly. Your job is to fetch the data, read the computed metrics, write the prose (lead, verdict, panel reads), and run the renderer + PDF exporter. You supply words; you never supply or adjust a number.

**Client-tool discipline:** use only `atm_announce`, `atm_sales`, `get_insider_transactions`, `get_company_info`, and optionally `get_research`. Do **not** use `get_company_chart_raw` or `get_company_chart` — they are internal-only and unavailable to clients.

## Sheet anatomy (fixed)

1. **Header** — ticker, company, sector, mcap, as-of, Verity logo, one-line `verdict` chip.
2. **Issuance read** — the orange-railed lead paragraph: what kind of issuer this is and the one thing to watch. Written after the metrics are computed, grounded in them.
3. **Capacity — the reservoir** *(the headline)* — authorized capacity remaining across all live programs, reconstructed as a step series that drains with every disclosed sale and refills at each New/Increase; ▲ marks each new shelf. Sidebar: live capacity (the big number), trailing-4q pace and runway in quarters, program count and median refill interval, median utilization of retired plans, and the one-line `capacity_read`.
4. **Program to date** — a stat strip, no chart: total raised / shares issued / ≈ % of today's count, blended VWAP (lifetime and trailing-12m), trailing-12m dollars raised, and the date of the last reported sale (a plain recency fact — most filers report only in periodic filings, so recent selling may not yet be public).
5. **Cadence & insider cross-check** *(when insider data is passed)* — one full-width chart doing double duty: quarterly company issuance on top, officer/director open-market selling beneath it, independently scaled. No stats, no commentary — the ratio between the two rows is the message, and it speaks for itself.
6. **Program economics & ledger** — current commission, estimated cumulative agent fees, forward-sale dollars, and the plan-by-plan table (authorized, sold under, % used, fee, terminal event: terminated / replaced / exhausted / live).
7. **Footer** — sources, the no-market-feed statement, dedup/exclusion counts, caveats.

One answer-at-a-glance per sheet: the reservoir is it. Do not add a second summary grid above it.

## Workflow

### Step 1 — Pull (single ticker `T`)

Verity tools are deferred — load via `tool_search` first (`atm_announce`, `atm_sales`, `get_company_info`, `get_insider_transactions`). Then:

1. `Verity:get_company_info(tickerlist=[T])` — name, sector, industry, market cap.
2. `Verity:atm_announce(tickerlist=[T], begin_date="2015-01-01")` — the full program-event history. Save the CSV verbatim to `announce.csv`.
3. `Verity:atm_sales(tickerlist=[T], begin_date="2015-01-01")` — the full sales tape. Save verbatim to `sales.csv`.
4. `Verity:get_insider_transactions(tickerlist=[T], positions=["CEO","CFO","OFF","DIR"], txntypes=["Sell","Exercise Sell","Buy"], begin_date=<~6 months before the first ATM sale>)` — officer/director open-market prints. Save verbatim to `insider.csv`. This powers the cross-check chart. If the pull fails or returns nothing, proceed without it — the panel drops cleanly and sparse activity is itself a finding worth a line in the lead.
5. *(optional but cheap)* `Verity:get_research(ticker_list=[T], type="ATM", limit=3)` — Verity's own ATM notes; use to inform the prose and cite in `footer_extra` if genuinely relevant.

**Save the tool CSVs byte-for-byte** — the renderer parses the raw headers. Do not reshape, re-type, or "clean" them; the cleaning rules live in the script so they are identical for every ticker.

### Step 1b — Coverage check

If `atm_announce` and `atm_sales` both return nothing for the ticker, the company has no covered ATM program — say so and stop; do not force a sheet from a shelf registration alone. If there are announcements but zero sales rows, that is itself the story (an authorized-but-unused pipe): the execution panel will be empty, so lead with capacity and say plainly that no sales have been disclosed.

### Step 2 — Compute the metrics (deterministic; no discretion)

```bash
python3 scripts/build_atm_tearsheet.py \
  --announce announce.csv --sales sales.csv --insider insider.csv --metrics-only
```

This prints the metrics JSON: blended VWAPs, totals, capacity, pace, runway, refill cadence, last reported sale date, fees, dedup/exclusion counts, quarterly issuance. **Read it before writing a word of prose** — the lead and reads must be grounded in these numbers, and the numbers on the sheet come only from here. Pass `--asof YYYY-MM-DD` only if the current date differs from the machine date; it anchors the trailing-12m windows and the current-quarter shading.

What the engine does (so you can explain it, not so you can re-do it):

- **Dedup**: sales rows are restated across plan replacements; exact `(dollars, shares, pps)` duplicates keep the earliest occurrence. The count of dropped rows is reported and printed in the footer.
- **Price facts**: blended VWAP (total dollars ÷ total shares across priced tranches, lifetime and trailing-12m). The metrics JSON also includes two `_diag_*` percentages (dollars printed above the program's running VWAP; dollars printed above the prior tranche) — these exist **only to help you choose accurate prose** ("realized prices stepped from the $70s to the $240s"), and must never appear on the sheet or be quoted to the user as a score, grade, or rating.
- **Split-artifact guard**: a print more than 2.5× above or below 0.4× the median of its neighboring prints (±2 tranches) is **excluded and counted**, never silently rescaled — reverse splits distort `pps` badly at micro-caps.
- **Capacity reservoir**: per-plan capacity from New/Increase/Decrease events, zeroed at Terminated/Replaced, drained by each sale. A plan first seen via a sale (its New predates coverage) is seeded from that row's `remaining_dollars + dollars`. Critical semantics inherited from the tool: **`dollars` means different things by `disclosure_type`** (New = full authorization, Increase/Decrease = the increment, Terminated/Replaced = empty with only `remaining_*` populated) — the script honors this; never sum announce `dollars` across types yourself.
- **Runway**: live capacity ÷ trailing-4-full-quarter pace. **Refill habit**: median days between New filings, and median utilization of retired plans — together these tell you whether "remaining capacity" is a ceiling or a revolving figure.
- **Fees**: Σ tranche dollars × the plan's stated commission; if any plan states the rate as a cap (`upto`), the total is shown as ≤.

### Step 3 — Write the meta and render

Write `meta.json` (schema in the script header; worked example: `assets/example_well_meta.json`):

- `verdict` — a short, factual chip ("DISCIPLINED PROGRAMMATIC ISSUER — PRINTS ABOVE ITS OWN AVERAGE, REFILLS ON SCHEDULE"), not a rating.
- `lead` — 3–5 sentences: what kind of issuer this is, realized-price and dilution facts in plain words, the state of the pipe (capacity, pace, runway), and the one thing to watch. Every figure in it must appear in the metrics JSON.
- `capacity_read` — one to two lines, naming the pattern *and its exception* (a refill that broke cadence, a shelf abandoned half-used). The exception is what makes the read credible.
- `footer_extra` — filer-specific caveats (disclosure channel habits, split history, what the latest implied print represents, research citations).

Then:

```bash
python3 scripts/build_atm_tearsheet.py --announce announce.csv --sales sales.csv \
  --insider insider.csv --meta meta.json --output /mnt/user-data/outputs/<T>_atm_tearsheet.html
python3 scripts/to_pdf.py --html /mnt/user-data/outputs/<T>_atm_tearsheet.html \
  --output /mnt/user-data/outputs/<T>_atm_tearsheet.pdf
```

`present_files` **both**. Then a short chat summary: live capacity and runway, the refill habit, total raised and the blended VWAP, how recent the last reported sale is, and the one thing to watch.

## Reading the tape honestly

- **Describe, don't grade.** A REIT issuing above NAV and a distressed biotech printing to survive are different situations that can produce similar-looking numbers; the *lead* explains which this is. Heavy issuance is not a sell signal and a full reservoir is not a threat in itself.
- **A quarter-VWAP is not a timed trade.** Most rows average a quarter of selling; only 8-K/PR-cadence filers disclose tranche-level timing. Don't over-read precision the data doesn't have.
- **Dilution vs. today's count.** Cumulative `pctout` sums per-row percentages of the then/current share count; label it as approximate ("≈ N% of today's count"), which the renderer does.
- **Micro-cap pathologies are the story, not noise.** `remaining_pct_out` above 100% (capacity exceeding the share count), raises approaching the market cap, and reverse-split-distorted `pps` (caught by the exclusion rule) should be stated flatly in the lead when present.
- **Concurrent programs are normal.** Some issuers run common and preferred programs simultaneously (`share_class`); the reservoir and ledger aggregate the stack. If preferred/Other classes are present, say so in the lead — common-share dilution and preferred issuance are different animals.

## Not investment advice

The sheet describes how a company has used its ATM, from its own disclosures. Keep that framing in the chat summary; never imply the score or the overhang is a recommendation.
