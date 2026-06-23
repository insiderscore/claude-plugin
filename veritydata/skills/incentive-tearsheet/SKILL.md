---
name: incentive-tearsheet
description: >-
  Generate a single-page incentive-design tear sheet for one public company from Verity (InsiderScore) compensation data. Use whenever a user wants to understand, visualize, or compare how a company's executive pay plan is structured and how it has changed — its annual (AIP) and long-term (LTIP) incentive metrics, weights, targets vs. actual outcomes, pay mix, and realized bonus. Trigger on phrases like "incentive tear sheet for [ticker]", "how does [ticker] pay its executives", "what does [ticker] incentivize", "comp design for [ticker]", "are [ticker]'s targets sandbagged", "growth vs profitability in [ticker]'s pay", "how has [ticker]'s comp plan changed", or simply a ticker following a prior tear sheet ("now do [ticker]"). Produces an analyst-grade HTML tear sheet in the Canopy house style. Uses Verity tools: get_annual_incentive_plans, get_longterm_incentive_plans, get_peer_group, get_research, get_filing_list, get_filing_content.
---

# Incentive Design Tear Sheet

Build a dense, single-page HTML tear sheet showing how one public company's executive incentive plan is designed and how it has evolved. The audience is sophisticated (hedge-fund analysts); the register is an accountant's — state measured facts, let the data carry the story, never editorialize ("then bit", "finally", "disappointing" are banned; "FY25 actual 15.2% vs 17.5% max → 127% of target" is the correct voice).

The sheet has a **fixed structure** (always the same sections in the same order). Only data-driven details vary, and every variation follows a **stated rule** so the same ticker always renders the same sheet. The deterministic work — geometry, layout thresholds, colors, rendering — is owned entirely by `scripts/build_tearsheet.py`, which consumes a spec JSON. Your job is to fetch the data, **classify each metric** (the one judgment step), assemble the spec, and run the script.

---

## Sheet anatomy (fixed)

1. **Header** — ticker, company, sector, mcap, fiscal-year span, Verity logo (dark navy strip).
2. **"What it means"** — a prominent light-mode callout immediately below the header that answers the analyst's "so what?": what management is actually incentivized to do, and what to watch. This is the lead, before any panel. It is an investment read, NOT a restatement of the plan mechanics.
3. **Thesis line** — the factual one-paragraph description of what the plan measures and conspicuously does not (light mode, supporting the takeaway).
4. **CEO tenure strip** — one segment per CEO in the window; collapses to a single segment if no transition.
5. **Incentive orientation** (quadrant) + **Targets vs outcomes** (goalposts), side by side.
6. **Metric persistence** matrix — every metric × every year, weight + realized payout.
7. **Modifiers & gates** strip — the non-weighted plan mechanics (gates that unlock/zero payout, modifiers that multiply it) that affect payout but are not weighted metrics. Omitted entirely if the plan has none.
8. **Pay structure** (LTIP mix slopegraph) + **Bonus realization** table, side by side.
9. **Classification rule** box — states the bucketing rule so a reader can audit it.
10. **Filed since the proxy** — post-proxy comp 8-Ks (Item 5.02) confirmed against the source filing, or an explicit "none filed" note.
11. **Footer** — sources, caveats, "not investment advice".

## Workflow

### Step 1 — Fetch

Call in one turn (single ticker `T`):

- `Verity:get_annual_incentive_plans` with `tickerlist=[T]` — all AIP years.
- `Verity:get_longterm_incentive_plans` with `tickerlist=[T]` — all LTIP cycles.
- `Verity:get_research` with `ticker_list=[T]`, `type="Comp"` — **required, not optional.** This is where Verity surfaces board-discretion events the structured AIP/LTIP tables do NOT capture: one-time mega-grants, special retention/"value creation" awards, off-cadence grants, mid-cycle metric changes. These are first-order for a PM and are easy to miss because they never appear in the plan endpoints. Read every returned brief's `takeaway`/`body`; if the list is empty, also try a plain call (no `type`) and a `search_phrase` like `"special OR retention OR one-time OR value creation"`. Any material off-cadence award found here MUST be surfaced in BOTH the "Filed since the proxy" section AND the "What it means" takeaway (see Steps 4 and 5b).
- `Verity:get_filing_list` with `ticker=T`, `formtypes=["8-K"]`, `date_start=` ~1 month before the latest proxy date — to find post-proxy comp events.

`get_peer_group` is optional context (only if the user asks for peer benchmarking; it is not part of the default sheet).

### Step 1b — Preflight: is there a chartable plan?

Before doing any classification or spec work, check what the data actually contains. There are two graceful-failure cases that must NOT proceed to a full sheet — render a stub instead. The `preflight(annual_rows, longterm_rows)` helper in `build_tearsheet.py` returns `"ok"`, `"no_coverage"`, or `"no_plan"`:

- **`no_coverage`** — both endpoints return empty lists (`[]`). The ticker is not covered (unknown, recently listed, foreign, or filed under another entity). Build a stub spec with `"mode":"no_coverage"`.
- **`no_plan`** — records exist but none carry a usable plan: every year is `status:"No AIP"`/`"No LTIP"` (or `"Needs Processing"` with no `metrics`), `ceobasesalary` is 0, and there is no `formula`/`metrics`. This is a real company whose pay is not a weighted metric scorecard — typically alternative-asset managers paid via carried interest and fees (e.g. ARES), some controlled companies, some REITs/MLPs. Build a stub spec with `"mode":"no_plan"`, a `reason` explaining the pay vehicle, and a `disclosed[]` list of whatever IS known (CEO, base salary, status, pay vehicle).
- **`ok`** — at least one year/cycle has `metrics` or a chartable `formula`. Proceed to Step 2.

Stub spec fields: `ticker`, `company`, `mode`, `meta` (optional), `reason` (HTML), optional `disclosed[]` of `{label,value}`. The script routes `mode in (no_coverage,no_plan)` to a minimal house-style notice card — never a half-rendered sheet. Distinguish the two honestly: `no_coverage` = "we don't have it"; `no_plan` = "we have it, but there is no metric-based plan to chart, and here is why." Treat the absence as a disclosure fact, not an error or an apology.

### Step 2 — Classify every weighted metric (THE judgment step)

For each metric in every AIP year and LTIP cycle, assign exactly one bucket by reading its **`name` and `definition`** — classify on the *underlying measure*, not the verb. This is the only non-mechanical step and it must be auditable.

| Bucket | Underlying measure | Examples |
|---|---|---|
| `growth` | Top line / scale | revenue, comparable sales, ARR, net new ACV, bookings, units, net new openings, client/customer count, revenue-per-client, development pipeline (site assessments) |
| `profitability` | At or below the margin line | adjusted EBITDA (incl. "EBITDA growth" — the measured quantity is earnings), operating income, operating/cash-flow margin, EPS, free cash flow, ROIIC, return on capital, Rule-of-40 |
| `tsr` (shareholder return) | Market-relative equity return | relative TSR, TSR percentile vs an index/peer set, stock-price-percentile vesting |
| `other` | Non-financial / discretionary | individual objectives, talent/succession, people, culture, safety, ESG/environment, food safety |

Rules:
- **"EBITDA growth" → profitability.** The delta operator does not change the measured quantity. This is the highest-leverage call; it is stated in the on-sheet rule so a reader can disagree with the bucketing, not the chart.
- **Unclassifiable → mark `unclassified`, never guess.** If a metric has no disclosed definition and the name is ambiguous, exclude it from the orientation blend and footnote it. Do not invent a bucket.
- **No-band metrics** (target/actual only, no threshold or maximum — e.g. "Company Operating Performance Objectives", "Individual Objectives") are still classified and still appear in the persistence matrix, but they are **not plotted** in the goalpost panel. List them in a "not plotted — no band" note.

### Step 3 — Compute the spec values

**Orientation points (one per fiscal year).** For each year:
1. Compute the AIP bucket shares from weighted metrics (weights summed across H1/H2/FY sub-periods; a metric acting as a modifier rather than a weighted line is footnoted, not counted).
2. Compute the LTIP bucket shares for the grant cycle active that year (if no LTIP grant that cycle, the year is AIP-only).
3. **Blend AIP and LTIP equally (50/50)** — NOT by dollars (dollar-weighting swamps everything into the LTIP's metric). If a pot is absent, use the other at 100%.
The script places each point by net tilt: x = growth−profitability, y = tsr−other. Center = balanced. Companies with no TSR/other weight legitimately sit on the horizontal midline — that is informative, not a bug. The script handles three things automatically: (a) **concentric rings** — when several years share one position, it draws one ring per year (so dwell time at a posture is visible) with the current year's group in navy; (b) **gap-aware labels** — it collapses consecutive years to ranges but exposes gaps, e.g. four years at one spot reads `FY22–24, 26` (not a misleading `FY22–FY24`), making clear which year is the exception; (c) the chronological path still connects positions so an out-and-back excursion is drawn.

**Orientation modifiers (force arrows).** Modifiers do NOT enter the weighted blend — but a modifier whose performance condition rewards a particular pole IS part of the orientation story, so it is drawn as a gold **force arrow** from each dot toward **the pole its condition measures**. Populate `orientation_modifiers[]` with `{pole, swing, direction, label}`: `pole` is the category the modifier's condition rewards (CRUS's revenue-growth multiplier → `growth`; NKE's People & Planet ESG modifier → `other`); `swing` is the **maximum positive swing in percentage points** (a 1.0×→2.0× multiplier is `100`; a ±20% ESG modifier is `20`) — length encodes structural reach, constant across years, NOT the realized outcome (that lives in the strip); `direction` is always `"toward"` (single arrowhead). Key principle: a ± modifier is NOT bidirectional in the quadrant — it points toward the single pole it measures, where "+" applies the pull and "−" is merely its absence. So an ESG ±20% modifier is a `+20` arrow toward `other`, not a double-headed arrow. Gates that merely condition/unlock payout without rewarding a pole stay in the strip only (no arrow). The dot remains the pure weighted blend; the arrow is the non-weighted directional force on top of it.

**Goalposts.** One panel per metric that has a disclosed threshold/target/maximum band. Use the metric's **natural disclosed units** (dollars, %, counts) — give each metric its own axis spanning its full multi-year envelope so rising targets and threshold-crossings (e.g. EBITDA through $0; set `show_zero:true`) are visible. Only fall back to **payout-curve space** (% of target payout) if the plan discloses *only* payout percentages and no underlying band (rare — e.g. a metric expressed purely as a payout curve). Expose sub-periods (H1, FY) as separate panels; do not collapse them.

*Layout rule (deterministic):* the script always stacks goalpost panels single-column, full-width — one metric per row — regardless of count. These sheets are screen-viewed and vertical space is free, so panels are never compressed into a multi-column grid (which shrank each panel and hurt legibility). You do not decide layout; you just pass the panels and the script renders them full-width with screen-legible type.

**Persistence matrix.** One row per distinct metric (group H1/H2/FY sub-periods of the same metric under one row, weights summed, payout = sub-period weighted average marked with "~"). Columns = fiscal years. Cell = weight (as `N%`) over realized payout (`N%`, or `open` for unfinished cycles, or `0%` for a completed-but-zero cycle). Include the AIP-total row.

**Realization.** CEO annual cash incentive per year: base, target bonus, payout %, realized $, a bar filling realized-payout as % of **that year's** AIP maximum (the cap can change year to year — never hardcode 200%), target notch, and bonus/base multiple. Each realization year row needs both display strings (`base`, `target`, `realized`, `mult` — e.g. `"$515K"`, `"1.44×"`) for the table AND numeric fields (`base_num`, `target_num`, `realized_num` in dollars) for the aggregation. The four summary deltas below the table are **hard-coded and computed by the script** — always, in this order: **Base, Target opportunity, Realized bonus, Bonus/base** — spanning first→last year. Do NOT author a `deltas[]` array; it is ignored. The script computes each as a first-vs-last comparison: Base/Target/Realized show "flat" if unchanged else a signed percent; Bonus/base shows the first and last multiples (`1.44→1.61×`). Note this is a strict endpoint comparison: a company with a $0 or near-zero first or last year will show "n/a" or an extreme percent — that is accepted, intended behavior, not a bug to patch.

**Pay structure.** LTIP grant mix (PSU/RSU/option %) by grant year as a slopegraph.

**Modifiers & gates.** The Verity rows carry a `modifiers` array separate from `metrics`. These are the non-weighted mechanics — gates (binary thresholds that unlock or zero payout, e.g. "payout only if revenue ≥96.7% of goal", or "metrics measured only if EBITDA goal met") and modifiers (multipliers within a band, e.g. an ESG modifier of ±20%, or a "−20%/0%" food-safety reducer). Collect each into the `modifiers_gates[]` spec list with `scope` (AIP/LTIP), `name`, `type` (`gate` or `modifier`), `effect` (the range/condition as a short string), and optional `outcome` (where it landed, e.g. "100% (neutral)", "cleared all years"). Distinguish gate vs modifier by function: a gate can zero or unlock the whole payout; a modifier scales it within a band. These NEVER enter the orientation blend or the weighted matrix — the strip is their home. If the plan has none, omit the list and the strip does not render.

### Step 4 — Confirm post-proxy events against the source

Proxy data lags, and the structured plan tables miss board-discretion awards entirely. Two sources feed the "Filed since the proxy" section:

1. **`get_research` (Comp briefs)** — the primary place special/off-cadence awards surface. A one-time mega-grant, a "value creation" or special-retention award, an off-cycle PRSU grant, or a mid-cycle metric change will appear here and nowhere in the AIP/LTIP endpoints. State the award's terms (target value, vesting hurdles, performance period, retention lockups) from the brief. These are often the single most important thing on the sheet — a special CEO award can dwarf and reframe the entire annual plan.
2. **`get_filing_list` 8-Ks** — if any 8-Ks post-date the latest proxy, fetch the relevant one with `get_filing_content` (`tlitem_short="item5.02"`) and **state award terms from the filing text, never inferred from plan data**. Item 5.02 covers exec changes, new-hire/retention grants, and equity-plan amendments; distinguish a genuine comp event from a financing 8-K (Items 1.01/2.03) or an earnings release (Item 2.02).

Put both in the "Filed since the proxy" box, leading with the most material (a special award outranks a plan-share-count amendment). If genuinely nothing comp-related exists in either source, say so explicitly — that is a valid, common state. **If a material off-cadence award exists, it must ALSO lead or feature in the "What it means" takeaway** — it is usually the dominant go-forward incentive and the first thing a PM needs to know.

### Step 5 — Assemble spec and render

Write the spec JSON (schema below) and run:

```bash
python3 scripts/build_tearsheet.py --spec /home/claude/<ticker>_spec.json --output /mnt/user-data/outputs/<ticker>_tearsheet.html
```

**The builder validates the spec before rendering** (`validate_spec`): it fails fast with a clear message naming any missing required field and the step that defines it, checks `orientation_points` count matches `years`, and rejects invalid modifier poles. It also **auto-sanitizes bare `&`** in raw-HTML fields (so `S&P 500` becomes `S&amp;P 500` automatically) — you no longer need to hand-escape ampersands in those fields, and a slip there can't reach the output. So the two historically-recurring mistakes (forgetting `takeaway`, bare ampersands) now surface as an instant, actionable error or are fixed silently rather than producing a cryptic crash or malformed HTML.

Two things the validator canNOT supply for you, so write them deliberately the first time: (1) the **`takeaway`** (Step 5b) — it is required and leads the sheet; (2) correct **per-field encoding** of `<b>`/entities in raw-HTML fields vs. literal characters in plain-text fields (the sanitizer only fixes ampersands, not missing `<b>` tags or wrongly-entity-encoded plain-text fields). When in doubt, copy the structure of an existing worked spec (`amd_spec.json`, `dis_spec.json`).

The script then prints an integrity line (year count, goalpost count + layout chosen, orientation points, CEO segments). Verify it matches the data, then present the file.

### Step 5c — Export a single-page PDF (for forwarding)

Analysts forward these to a PM, who can't easily open an HTML artifact — so always also produce a PDF. Pagination would slice the dense sheet across letter pages and break panels mid-figure, so the PDF is rendered as ONE continuous page sized exactly to the content:

```bash
python3 scripts/to_pdf.py --html /mnt/user-data/outputs/<ticker>_tearsheet.html --output /mnt/user-data/outputs/<ticker>_tearsheet.pdf
```

This uses headless Chromium (Playwright) so the SVG quadrant (arrows, concentric rings), web fonts, and CSS grid render exactly as in the browser; it measures the rendered content height and emits a single un-paginated page. Present BOTH the `.html` (interactive) and the `.pdf` (forwardable). The script prints the page dimensions; a tall single page (e.g. ~12in × ~21in) is expected and correct.

### Step 5b — Write the "What it means" takeaway (THE lead)

This is the first thing the analyst reads and the thing they will ask for if it's missing ("so what does it mean?"). Write it AFTER the sheet is built, when you can see the whole picture. Rules:
- It is an **investment read**, not a description. Answer: what is management actually incentivized to do, and what should an analyst watch? A reader should finish it knowing the *implication*, not the mechanics.
- Do NOT restate the thesis. The thesis says what the plan measures; the takeaway says what that means for management behavior and the stock.
- Stay grounded — every claim must trace to something on the sheet (the orientation, the pay/no-pay record, the gates, the modifier). The register is an analyst's, slightly more interpretive than the rest of the sheet but never hype, never a recommendation.
- 3–5 sentences. Good moves: name the central tension (e.g. "paid well operationally while delivering nothing to shareholders"), say whether targets genuinely bind or are routinely cleared, and end on the single thing to watch (the lever, the open cycle, the discretionary block).
- **If Step 4 surfaced a material off-cadence award (special/retention/value-creation grant), lead with it.** Such a grant is usually the CEO's dominant go-forward incentive and reframes everything else — a PM needs it first. State the magnitude and what it actually rewards (e.g. "only pays in full if the stock roughly triples to a sustained ~$600"), then place the ordinary plan beneath it.
- Put it in the `takeaway` spec field (raw HTML — use `<b>` for the one or two phrases that carry the point).

### Step 6 — Brief analysis

After presenting, write 3-5 sentences anchored only in what the sheet shows. Good angles, all factual: the orientation quadrant the company occupies and any migration across it; whether targets are routinely cleared at max (sandbag signature: dots past the band every year) or actually bind (dots in-band or below threshold); divergence between operating payout and TSR/LTIP outcomes; metric-set stability vs churn; realized-dollar trend vs target-opportunity trend. No editorializing about intent.

## Spec schema

See `scripts/build_tearsheet.py` docstring and the worked example `phr_spec.json` in the skill root. Key fields: `ticker`, `company`, `meta`, `takeaway` (the "What it means" lead — see Step 5b), `thesis`, `years`, `ceo[]`, `orientation_points[]` (`growth`/`profitability`/`sr`/`other` shares summing to 1 per year; `orientation_modifiers` may target the shareholder-return pole as either `sr` or `tsr` — both resolve to the same pole), `orientation_modifiers[]` (force arrows — see orientation section), `goalposts[]` (each with `axis_min/max`, `axis_min_label/max_label`, optional `show_zero`, and `years[]` of `thr/tgt/max/actual` in the axis's units), `matrix_rows[]` + `aip_total` (the AIP-total row is auto-placed as a subtotal — it renders directly after the AIP metrics and *before* the first LTIP group header, not at the very bottom; a relative-TSR row may carry an optional `benchmark` field, a `{year: "S&P 500", ...}` map, and when the benchmark changes across years the script marks the change year's cell with a gold ◆ and adds a footnote naming the old and new benchmark — see "rTSR benchmark changes" below), `modifiers_gates[]`, `realization` (rows need numeric `base_num`/`target_num`/`realized_num`; see realization note), `pay_structure`, `classification_rule`, `provenance_html`, `footer`. The script handles all geometry, color, layout, and the embedded Verity logo from these values — the logo lives at `scripts/verity_logo_b64.txt` and is inserted automatically; specs never reference it.

**Field encoding (important — avoids double-escaping).** Two classes of string field, by how the script treats them:
- **Plain-text fields** (the script runs `html.escape()` on them): all short display labels — `company`, every `name`/`cls`/`scope`/`effect`/`outcome`/`label`/`weight_label`/`sub`, axis labels, `ceo[].who/when`, captions, and the `*_note` footnote strings. Write these with **literal characters** (`&`, `±`, `≥`, `·`, `—`, `×`, `→`), NOT HTML entities. Writing `&amp;` here renders as the literal text `&amp;`. The escape pass safely neutralizes any genuine `&`/`<` from company data, so a metric like "AT&T revenue" or a "<10% churn" target cannot break the layout.
- **Raw-HTML fields** (passed through verbatim, may contain tags/entities): `meta` (use `<br>` for the line break), `takeaway`, `thesis`, `classification_rule`, `provenance_html`, `pay_legend`, `footer`. Here, use `<b>…</b>` for emphasis as the examples do. Bare ampersands are auto-escaped by `validate_spec` (so `S&P 500` is fixed to `S&amp;P 500` for you, while existing `&amp;`/`&rarr;`/`&#9650;` entities are left intact) — but still use `<b>` and named entities deliberately, since the sanitizer only handles ampersands.

## Color semantics (fixed, do not change)

- Achievement: **green ≥ max**, **gold in-band**, **red below threshold**. Same scale for goalpost dots, matrix payout numbers, AIP-total, and the realization bar fill.
- Orientation poles: growth `#1d6a4f`, profitability `#1a4a7a`, shareholder return `#7a3b1d`, other `#9a7d2e`.

## Data quirks to handle (seen across test tickers)

- **Forgone/restructured bonus**: a computed company multiplier but a disclosed actual cash bonus of $0 (e.g. INTA FY23). Treat realized as 0%, color red, footnote the discrepancy. Never silently drop it.
- **Completed-at-zero LTIP cycle**: relative-TSR or other LTIP finishing below threshold pays 0% (e.g. PHR FY23 grant). Show as a red `0%` cell, distinct from `open` cycles.
- **Metric rename**: when the disclosed measure changes (e.g. INTA "Company Operating Performance" → "Net New ACV"), show as separate rows — the measured thing changed.
- **Year-varying AIP cap** (e.g. PHR 166.7% → 150% → 200%): the realization bar fills against each year's own cap; footnote that widths are comparable in closeness-to-cap, not absolute payout.
- **Metric-set churn / sub-periods** (e.g. PHR's 4→8→4 with H1/H2/FY): group sub-periods under parent rows in the matrix; expose them as separate goalpost panels.
- **Missing early years / IPO**: a company public only part of the window simply has fewer year columns. No FY21 ≠ broken.
- **Open cycles**: young companies (e.g. INTA) may have all LTIP cycles still open — the LTIP is prospective. Show `open`; the long-term story is the weights and targets, not yet outcomes.
- **rTSR classification**: relative TSR is `tsr` (shareholder return), never `other` — it is a financial market metric, not a soft goal.
- **rTSR benchmark changes**: the relative-TSR comparator (the `peer_group_normalized` field in `get_longterm_incentive_plans`) is a material plan attribute — beating a sector index is a very different bar than beating the S&P 500. When a company changes its benchmark mid-history (e.g. DIS moved from `S&P 500` to `S&P 500 Media & Entertainment` in the FY25 grant), capture it: put a `benchmark` map on that metric's matrix row (`{"FY21":"S&P 500", ... ,"FY25":"S&P 500 Media & Entertainment Index"}`, keyed by the grant-start year used for the LTIP rows). The script auto-detects the change, marks the change-year cell with a gold ◆, and writes the old→new footnote — you do not write the footnote. If the benchmark never changes, you can still include the map (harmless) or omit it. Always read `peer_group_normalized` across cycles when building an LTIP with relative TSR, specifically to catch this.
- **No coverage** (empty `[]` from both endpoints): not an error — render the `no_coverage` stub. Verify the ticker first; a typo is the most common cause.
- **Covered but no metric plan** (all `status:"No AIP"/"No LTIP"`, $0 base, no metrics — e.g. ARES): render the `no_plan` stub explaining the pay vehicle (carry/fees, controlled-company, etc.). Do not force a blank quadrant or empty goalposts; there is genuinely nothing to plot, and saying so plainly is the correct output.

## Notes

- Single ticker per sheet. For a multi-ticker request, generate one sheet each.
- Figures are CEO/PEO-level unless the user asks otherwise.
- The sheet is a design/structure view; it is not a comp-dollar audit and not investment advice — the footer says so.


