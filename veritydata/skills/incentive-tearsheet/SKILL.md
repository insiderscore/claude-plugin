---
name: incentive-tearsheet
description: Generate a single-page incentive-design tear sheet for one public company from Verity (InsiderScore) compensation data. Use whenever a user wants to understand, visualize, or compare how a company's executive pay plan is structured and how it has changed — its annual (AIP) and long-term (LTIP) incentive metrics, weights, targets vs. actual outcomes, pay mix, and realized bonus. Trigger on phrases like "incentive tear sheet for [ticker]", "how does [ticker] pay its executives", "what does [ticker] incentivize", "comp design for [ticker]", "are [ticker]'s targets sandbagged", "growth vs profitability in [ticker]'s pay", "how has [ticker]'s comp plan changed", or simply a ticker following a prior tear sheet ("now do [ticker]"). Produces an analyst-grade HTML tear sheet in the Canopy house style. Uses Verity tools: get_annual_incentive_plans, get_longterm_incentive_plans, get_peer_group, get_research, get_filing_list, get_filing_content.
---

# Incentive Design Tear Sheet

Build a dense, single-page HTML tear sheet showing how one public company's executive incentive plan is designed and how it has evolved. The audience is sophisticated (hedge-fund analysts); the register is an accountant's — state measured facts, let the data carry the story, never editorialize ("then bit", "finally", "disappointing" are banned; "FY25 actual 15.2% vs 17.5% max → 127% of target" is the correct voice).

The sheet has a **fixed structure** (always the same sections in the same order). Only data-driven details vary, and every variation follows a **stated rule** so the same ticker always renders the same sheet. The deterministic work — geometry, layout thresholds, colors, rendering — is owned entirely by `scripts/build_tearsheet.py`, which consumes a spec JSON. Your job is to fetch the data, **classify each metric** (the one judgment step), assemble the spec, and run the script.


## First-run setup (single-file distribution)

This skill is distributed as **one self-contained `SKILL.md`**. The Python builder, the
HTML templates, and the embedded Verity logo all live as fenced code blocks in the
**Appendix** at the bottom of this file. Before running the workflow the first time in a
session, materialize them to disk by extracting each block to its labeled path.

Quickest way — run this bootstrap, which parses THIS file and writes every embedded file:

```bash
python3 - "$SKILL_MD_PATH" << 'BOOT'
import sys, re, pathlib
src = pathlib.Path(sys.argv[1]).read_text()
base = pathlib.Path("incentive-tearsheet")
# Each embedded file is a fenced block immediately preceded by a line:  <!-- FILE: path -->
pat = re.compile(r'<!--\s*FILE:\s*(?P<path>[^\s]+)\s*-->\n```[a-zA-Z0-9]*\n(?P<body>.*?)\n```', re.S)
n = 0
for m in pat.finditer(src):
    p = base / m.group("path")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(m.group("body"))
    n += 1
    print("wrote", p)
print(f"materialized {n} files under {base}/")
BOOT
```

(`$SKILL_MD_PATH` = the path to this file. If you are an agent reading this in-context,
you can equivalently just write each Appendix block to its `FILE:` path directly.)

After materialization the layout is the normal skill folder
(`incentive-tearsheet/scripts/...`), and the workflow below runs unchanged. The logo is
embedded as base64 text at `scripts/verity_logo_b64.txt`; `build_tearsheet.py` reads it
automatically. A canonical worked example, **`dis_spec.json`**, is also embedded (it is the
most feature-complete: multi-CEO, three goalpost panels, an rTSR benchmark change, and a
special-award provenance block) — use it as the structural reference when the instructions
say "copy an existing worked spec." The other worked specs from development (PHR, AMD, NKE,
AVAV, CRUS, AMAT, SBUX) are not bundled to keep this one file light; `dis_spec.json` covers
the same patterns.

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


---

# Appendix — embedded skill files
Each block below is one file. The `<!-- FILE: path -->` comment immediately above a block names where it goes (relative to the skill root). The first-run bootstrap extracts them automatically; do not edit them by hand here.

<!-- FILE: scripts/build_tearsheet.py -->
```python
#!/usr/bin/env python3
"""
build_tearsheet.py — render an incentive-design tear sheet from a prepared spec.

This script owns every DETERMINISTIC decision so the sheet is reproducible
ticker-to-ticker: coordinate geometry (goalposts, quadrant), layout thresholds
(goalpost stacks <=3 / grids at 4+), color semantics (green>=max, gold in-band,
red miss), and the house style. The only NON-deterministic step — classifying
each metric into growth / profitability / shareholder-return / other — happens
upstream (in the SKILL workflow, by reading metric definitions) and arrives here
as explicit labels in the spec JSON. The script never guesses a classification.

Input: a spec JSON (see SKILL.md "Spec schema"). Output: a single self-contained
HTML file.

Usage:
  python3 build_tearsheet.py --spec /path/spec.json --output /path/PHR_tearsheet.html
"""
import argparse, json, html

# ----- house style tokens (the Canopy palette) -----
NAVY="#1a1a2e"; GOLD="#c9a84c"; PAGE="#f8f7f4"
GREEN="#2d6a4f"; GOLD_TXT="#9a7d2e"; RED="#a4343a"; LOWGREEN="#3d7a5f"
MUTE="#8a8578"; MUTE2="#9a958c"; BORDER="#e5e2db"
GROWTH="#1d6a4f"; PROFIT="#1a4a7a"; TSR="#7a3b1d"; OTHER="#9a7d2e"
ZERO="#b08968"

# achievement color: green >= max, gold in-band, red below threshold
def dot_color(actual, thr, mx):
    if mx is not None and actual is not None and actual >= mx: return GREEN
    if thr is not None and actual is not None and actual < thr: return RED
    return GOLD_TXT

def payout_color(p):
    if p is None: return MUTE2
    if p >= 150: return GREEN
    if p <= 0: return RED
    if p >= 100: return GREEN
    return GOLD_TXT  # below target

def esc(s): return html.escape(str(s)) if s is not None else ""

# ---------- geometry: goalpost row ----------
def goalpost_svg(metric, x0=70, x1=628):
    """One metric: bars across years on a shared per-metric axis (natural units
    when bands are in natural units; payout-curve space only if the spec says so).
    Sized for full-width, screen-first legibility: larger type, taller rows, bigger
    dots — goalposts always render full-width (no 2-col grid), so nothing shrinks."""
    vmin, vmax = metric["axis_min"], metric["axis_max"]
    def vx(v):
        if v is None: return None
        return round(x0 + (v - vmin)/(vmax - vmin)*(x1 - x0), 1)
    rows = metric["years"]
    ROW = 26                      # row pitch (was 20)
    h = 20 + len(rows)*ROW + 22
    parts = [f'<svg width="100%" viewBox="0 0 660 {h}" role="img" '
             f'aria-label="{esc(metric["name"])} targets vs actuals by year">']
    # axis baseline + min/max labels
    parts.append(f'<line x1="{x0}" y1="16" x2="{x0}" y2="{h-22}" stroke="#ddd9d0" stroke-width="0.5"/>')
    parts.append(f'<text x="{x0}" y="{h-7}" fill="#b5b0a5" font-size="12.6" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace">{esc(metric["axis_min_label"])}</text>')
    parts.append(f'<text x="{x1}" y="{h-7}" fill="#b5b0a5" font-size="12.6" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace">{esc(metric["axis_max_label"])}</text>')
    # optional zero line (for metrics crossing zero, e.g. EBITDA)
    if metric.get("show_zero") and vmin < 0 < vmax:
        zx = vx(0)
        parts.append(f'<line x1="{zx}" y1="16" x2="{zx}" y2="{h-22}" stroke="{ZERO}" '
                     f'stroke-width="1" stroke-dasharray="2 2"/>')
        parts.append(f'<text x="{zx}" y="13" fill="{ZERO}" font-size="10.9" text-anchor="middle" '
                     f'font-family="JetBrains Mono,monospace">0</text>')
    y = 32
    for r in rows:
        thr, tgt, mx, act = r.get("thr"), r.get("tgt"), r.get("max"), r.get("actual")
        parts.append(f'<text x="60" y="{y+5}" fill="#5a5750" font-size="13.8" text-anchor="end" '
                     f'font-family="JetBrains Mono,monospace">{esc(r["label"])}</text>')
        if thr is not None and mx is not None:
            bx, bw = vx(thr), vx(mx)-vx(thr)
            parts.append(f'<rect x="{bx}" y="{y-1}" width="{bw}" height="8" rx="2" fill="#e0ddd2"/>')
        if tgt is not None:
            op = "" if (thr is not None and mx is not None) else ' opacity="0.4"'
            parts.append(f'<rect x="{vx(tgt)-1}" y="{y-4}" width="2" height="13" fill="{NAVY}"{op}/>')
        if act is not None:
            c = dot_color(act, thr, mx)
            ax = vx(act)
            ax = max(x0, min(x1, ax))  # clamp to axis; overshoot handled by annotation
            parts.append(f'<circle cx="{ax}" cy="{y+3}" r="5" fill="{c}"/>')
        if thr is None or mx is None:
            parts.append(f'<text x="{(vx(act) or x0)+12}" y="{y+7}" fill="#c2bdb0" font-size="12.6">'
                         f'target only</text>')
        y += ROW
    parts.append("</svg>")
    return "".join(parts)

def goalpost_block(metric):
    sub = esc(metric.get("sub",""))
    return (f'<div class="metric-block"><div class="metric-head">'
            f'<span class="metric-name">{esc(metric["name"])}</span>'
            f'<span class="metric-wt">{esc(metric.get("weight_label",""))}</span>'
            f'<span class="metric-sub">{sub}</span></div>{goalpost_svg(metric)}</div>')

# ---------- geometry: orientation quadrant ----------
def quadrant_svg(points, modifiers=None):
    """Named quadrant. X: profitability(left,-1) <-> growth(right,+1) = g-p.
       Y: shareholder-return(top,+1) <-> other(bottom,-1) = sr-o.
       Position = net tilt (convex on a 100% pie).
       modifiers: optional list of {pole, swing, direction, label} drawn as force
       arrows from each dot toward the rewarded pole. Length = DESIGNED swing
       (a structural property of the plan), constant across years. direction:
       'toward' (single arrowhead) or 'both' (bidirectional, double-headed)."""
    import math
    W=680; cx=340; cy=170; halfx=270; halfy=130
    POLES={'growth':(610,170),'profitability':(70,170),'sr':(340,40),'other':(340,300)}
    POLES['tsr']=POLES['sr']  # accept either key for the shareholder-return pole
    def px(gp, sro): return round(cx+gp*halfx,1), round(cy-sro*halfy,1)
    p=[f'<svg width="100%" viewBox="0 0 {W} 360" role="img" '
       f'aria-label="Quadrant plot of incentive orientation">']
    # arrowhead markers
    p.append('<defs>'
             f'<marker id="modhead" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">'
             f'<path d="M0,0 L6,3 L0,6 Z" fill="{GOLD_TXT}"/></marker></defs>')
    p.append(f'<rect x="70" y="40" width="540" height="260" fill="#fbfaf7" stroke="#d8d4ca" stroke-width="1"/>')
    p.append(f'<rect x="70" y="40" width="270" height="130" fill="{PROFIT}" opacity="0.03"/>')
    p.append(f'<rect x="340" y="40" width="270" height="130" fill="{GROWTH}" opacity="0.03"/>')
    p.append(f'<line x1="340" y1="40" x2="340" y2="300" stroke="#d8d4ca" stroke-width="0.75" stroke-dasharray="3 3"/>')
    p.append(f'<line x1="70" y1="170" x2="610" y2="170" stroke="#d8d4ca" stroke-width="0.75" stroke-dasharray="3 3"/>')
    # quadrant names
    q=[("84","60","start",PROFIT,"Capital Discipline","profitability + shareholder return"),
       ("596","60","end",GROWTH,"Growth-to-Value","growth + shareholder return"),
       ("84","288","start",PROFIT,"Operating Quality","profitability + other objectives"),
       ("596","288","end",GROWTH,"Stakeholder Expansion","growth + other objectives")]
    for x,y,anc,col,name,desc in q:
        dy = "74" if y=="60" else "274"
        p.append(f'<text x="{x}" y="{y}" fill="{col}" font-size="13.8" font-weight="600" text-anchor="{anc}">{name}</text>')
        p.append(f'<text x="{x}" y="{dy}" fill="{MUTE2}" font-size="10.9" text-anchor="{anc}">{desc}</text>')
    # pole labels
    p.append(f'<text x="340" y="32" fill="{TSR}" font-size="12.1" font-weight="600" text-anchor="middle">&#9650; Shareholder return</text>')
    p.append(f'<text x="340" y="316" fill="{OTHER}" font-size="12.1" font-weight="600" text-anchor="middle">&#9660; Other objectives</text>')
    p.append(f'<text x="64" y="173" fill="{PROFIT}" font-size="12.1" font-weight="600" text-anchor="end">&#9664; Profitability</text>')
    p.append(f'<text x="616" y="173" fill="{GROWTH}" font-size="12.1" font-weight="600" text-anchor="start">Growth &#9654;</text>')
    # gap-aware compact label: ['FY22','FY23','FY24','FY26'] -> 'FY22–24, 26'
    def compact_years(labels):
        nums=[]
        for l in labels:
            d=''.join(c for c in str(l) if c.isdigit())
            if len(d)>=2: nums.append(int(d[-2:]))
            elif d: nums.append(int(d))
        nums=sorted(set(nums))
        if not nums: return ", ".join(labels)
        runs=[]; start=prev=nums[0]
        for n in nums[1:]:
            if n==prev+1: prev=n
            else: runs.append((start,prev)); start=prev=n
        runs.append((start,prev))
        parts=[]
        for i,(a,b) in enumerate(runs):
            if i==0: parts.append(f"FY{a:02d}" if a==b else f"FY{a:02d}\u2013{b:02d}")
            else: parts.append(f"{a:02d}" if a==b else f"{a:02d}\u2013{b:02d}")
        return ", ".join(parts)

    # chronological coords (for the trip path)
    coords=[]
    for pt in points:
        gp = pt["growth"]-pt["profitability"]; sro = pt["sr"]-pt["other"]
        coords.append((px(gp,sro), pt["label"]))
    # path follows chronological order (shows out-and-back motion)
    poly=" ".join(f"{xy[0]},{xy[1]}" for xy,_ in coords)
    p.append(f'<polyline points="{poly}" fill="none" stroke="#5a5750" stroke-width="1.3" opacity="0.45"/>')

    # group ALL years by unique position (not just consecutive) for dots + labels
    from collections import OrderedDict
    groups=OrderedDict()
    for idx,(xy,lab) in enumerate(coords):
        groups.setdefault(xy, []).append((idx,lab))
    last_idx=len(coords)-1
    # modifier force arrows: one per unique position, toward rewarded pole, designed length
    def arrow_pts(x0,y0,pole,swing,k=0.55,Lmax=78,Lmin=14,gap=8):
        tx,ty=POLES[pole]; dx,dy=tx-x0,ty-y0; d=math.hypot(dx,dy) or 1
        ux,uy=dx/d,dy/d; L=max(Lmin,min(Lmax,abs(swing)*k))
        return (round(x0+ux*gap,1),round(y0+uy*gap,1),
                round(x0+ux*(gap+L),1),round(y0+uy*(gap+L),1))
    # record arrow vertical direction per position (so labels avoid their own arrow)
    arrow_vy = {}   # xy -> sign of arrow's vertical component (+down / -up), and reach
    if modifiers:
        for xy in groups:
            for md in modifiers:
                x1,y1,x2,y2=arrow_pts(xy[0],xy[1],md["pole"],md.get("swing",40))
                p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                         f'stroke="{GOLD_TXT}" stroke-width="1.6" opacity="0.75" '
                         f'marker-end="url(#modhead)"/>')
                vy = y2 - xy[1]
                # keep the largest-magnitude vertical reach if multiple modifiers
                if xy not in arrow_vy or abs(vy) > abs(arrow_vy[xy]):
                    arrow_vy[xy] = vy
    # dots: concentric rings encode how many years stack at a position
    placed=[]  # (x_left, x_right, y) of placed label boxes for collision checks
    CHARW=5.4; LINEH=12; XPAD=10
    def overlaps(x,y,w):
        l,r=x-w/2,x+w/2
        for (pl,pr,py) in placed:
            if abs(py-y)<LINEH and not (r<pl-XPAD or l>pr+XPAD):
                return True
        return False
    # uniform label clearance: tallest ring stack in the whole plot, so top labels align
    max_n = max((len(m) for m in groups.values()), default=1)
    uni_outer = 4.5 + (max_n-1)*3.0 if max_n>1 else 5
    for xy, members in groups.items():
        n=len(members)
        is_current = any(idx==last_idx for idx,_ in members)
        base_col = NAVY if is_current else "#5a5750"
        labs=[lab for _,lab in members]
        # outer rings (one per extra year), drawn largest-first, then solid core
        for ring in range(n,1,-1):
            rr = 4.5 + (ring-1)*3.0
            p.append(f'<circle cx="{xy[0]}" cy="{xy[1]}" r="{rr:.1f}" fill="none" '
                     f'stroke="{base_col}" stroke-width="1" opacity="0.45"/>')
        core = 5 if is_current else 4.5
        p.append(f'<circle cx="{xy[0]}" cy="{xy[1]}" r="{core}" fill="{base_col}" '
                 f'stroke="#fff" stroke-width="1"/>')
        # label placement: clear the rings; avoid this dot's own arrow; avoid other labels
        text=compact_years(labs); w=len(text)*CHARW
        # arrow clearance: if an arrow points down (+), its tip is ~14px below; clear past it
        vy = arrow_vy.get(xy, 0)
        arrow_clear = abs(vy) + 12 if vy else 0
        y_above = xy[1] - uni_outer - 5
        y_below = xy[1] + max(uni_outer, arrow_clear) + 10
        # prefer the side OPPOSITE the arrow: arrow down -> label up, arrow up -> label down
        if vy > 0:        # arrow points down -> strongly prefer above
            order = [y_above, y_below]
        elif vy < 0:      # arrow points up -> prefer below
            order = [y_below, y_above]
        else:             # no arrow -> default above, flip below on collision
            order = [y_above, y_below]
        y_lab = next((y for y in order if not overlaps(xy[0], y, w)), order[0])
        guard=0
        while overlaps(xy[0],y_lab,w) and guard<6:
            y_lab += LINEH if y_lab>xy[1] else -LINEH; guard+=1
        placed.append((xy[0]-w/2,xy[0]+w/2,y_lab))
        p.append(f'<text x="{xy[0]}" y="{y_lab:.1f}" fill="{base_col}" font-size="10.3" '
                 f'text-anchor="middle" font-family="JetBrains Mono,monospace">{esc(text)}</text>')
    p.append("</svg>")
    return "".join(p)

# ---------- persistence matrix ----------
def matrix_html(spec):
    years = spec["years"]
    head = "".join(f"<th>{esc(y)}</th>" for y in years)

    def total_row():
        tot=spec.get("aip_total",{})
        tcells=[]
        for y in years:
            v=tot.get(y)
            if v is None: tcells.append('<td></td>'); continue
            cls = "p-max" if (isinstance(v,(int,float)) and v>=100) else \
                  ("p-miss" if (isinstance(v,(int,float)) and v<=0) else "p-mid")
            tcells.append(f'<td><span class="tot {cls}">{v:.0f}%</span></td>' if isinstance(v,(int,float))
                          else f'<td><span class="tot">{esc(v)}</span></td>')
        return (f'<tr class="totrow"><td class="lab">AIP total payout</td>'
                +"".join(tcells)+"</tr>")

    def is_ltip_group(g):
        g=(g or "").lower()
        return ("ltip" in g) or ("long-term" in g) or ("long term" in g)

    rows=[]
    cur_group=None
    total_emitted=False
    bench_notes=[]   # collected benchmark-change descriptions -> appended to the matrix note
    for m in spec["matrix_rows"]:
        if m.get("group") and m["group"]!=cur_group:
            # the AIP total is an AIP subtotal: emit it just before the first LTIP group
            if is_ltip_group(m["group"]) and not total_emitted and spec.get("aip_total"):
                rows.append(total_row()); total_emitted=True
            cur_group=m["group"]
            rows.append(f'<tr><td colspan="{len(years)+1}" class="grp">{esc(cur_group)}</td></tr>')
        # rTSR benchmark-change detection: a row may carry {benchmark:{year:"S&P 500", ...}}.
        # We mark the first year the benchmark differs from the prior disclosed year, and
        # record an old->new note. If the benchmark never changes, nothing extra renders.
        bench = m.get("benchmark") or {}
        change_year=None
        if bench:
            prev=None
            for y in years:
                b=bench.get(y)
                if b is None: continue
                if prev is not None and b!=prev:
                    change_year=y
                    bench_notes.append(f"{esc(m['name'])}: benchmark changed to {esc(b)} "
                                       f"in {esc(y)} (from {esc(prev)}).")
                prev=b
        cells=[]
        for y in years:
            cell=m["cells"].get(y)
            if cell is None:
                cells.append('<td><span class="empty">&middot;</span></td>')
            else:
                w=esc(cell.get("w","")); p=cell.get("p")
                mark = ('<sup class="bench-mark" title="benchmark change">&#9670;</sup>'
                        if y==change_year else "")
                if p=="open":
                    cells.append('<td><span class="cell"><span class="w">'+w+'</span>'
                                 '<span class="p p-open">open'+mark+'</span></span></td>')
                else:
                    cls = "p-max" if (isinstance(p,(int,float)) and p>=100) else \
                          ("p-miss" if (isinstance(p,(int,float)) and p<=0) else "p-mid")
                    ptxt = (f"{p:.0f}%" if isinstance(p,(int,float)) else esc(p))
                    cells.append(f'<td><span class="cell"><span class="w">{w}</span>'
                                 f'<span class="p {cls}">{ptxt}{mark}</span></span></td>')
        rows.append(f'<tr><td class="lab"><div class="mname">{esc(m["name"])}</div>'
                    f'<div class="mclass">{esc(m.get("cls",""))}</div></td>'+"".join(cells)+"</tr>")
    # if no LTIP group existed, the total still belongs at the end
    if spec.get("aip_total") and not total_emitted:
        rows.append(total_row())
    note_txt = spec.get("matrix_note","")
    if bench_notes:
        bench_line = ('<b>&#9670; rTSR benchmark change:</b> ' + " ".join(bench_notes))
        note_txt = (note_txt + " " + bench_line) if note_txt else bench_line
    note = f'<div class="foot-note">{note_txt}</div>' if note_txt else ""
    return (f'<table class="matrix"><thead><tr><th class="lab">Metric</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>{note}')

# ---------- modifiers & gates strip ----------
def modifiers_html(spec):
    """Thin strip of the non-weighted plan mechanics (gates and modifiers) that affect
    payout but are not weighted metrics. Empty -> returns '' (no strip rendered)."""
    mods = spec.get("modifiers_gates", [])
    if not mods:
        return ""
    chips=[]
    for m in mods:
        is_gate = m["type"]=="gate"
        tag_cls = "mg-gate" if is_gate else "mg-mod"
        tag_txt = "GATE" if is_gate else "MOD"
        scope = esc(m.get("scope",""))
        eff = esc(m.get("effect",""))
        outcome = m.get("outcome")
        out_html = f'<span class="mg-out">{esc(outcome)}</span>' if outcome else ""
        chips.append(
            f'<div class="mg-chip"><span class="mg-tag {tag_cls}">{tag_txt}</span>'
            f'<span class="mg-body"><span class="mg-name">{esc(m["name"])}</span>'
            f'<span class="mg-meta">{scope}{" \u00b7 " if scope and eff else ""}{eff}</span></span>'
            f'{out_html}</div>')
    note = f'<div class="foot-note">{esc(spec["modifiers_note"])}</div>' if spec.get("modifiers_note") else ""
    return ('<div class="sec-title" style="margin-top:6px">Modifiers &amp; gates '
            '<span class="note">non-weighted mechanics that adjust or unlock payout</span></div>'
            f'<div class="mg-strip">{"".join(chips)}</div>{note}')

# ---------- realization ----------
def realization_html(spec):
    r=spec["realization"]
    rows=[]
    for row in r["years"]:
        fill = row["realized_pct_of_cap"]
        over = "over" if row.get("at_or_above_target") else ""
        notch = row["target_pct_of_cap"]
        mult_cls = payout_color(row["payout"])
        mult_class = {GREEN:"p-max",GOLD_TXT:"p-mid",RED:"neg",MUTE2:""}.get(mult_cls,"")
        rows.append(
          f'<tr><td class="l yr">{esc(row["fy"])}</td>'
          f'<td class="dollar">{esc(row["base"])}</td>'
          f'<td class="dollar">{esc(row["target"])}</td>'
          f'<td class="mult {mult_class}">{row["payout"]:.0f}%</td>'
          f'<td class="dollar">{esc(row["realized"])}</td>'
          f'<td class="l" style="padding-left:14px"><span class="opp" style="width:120px">'
          f'<i class="{over}" style="width:{fill:.0f}%"></i>'
          f'<span class="tgt" style="left:{notch:.0f}%"></span></span></td>'
          f'<td class="mono">{esc(row["mult"])}</td></tr>')
    # --- Hard-coded four-slot delta aggregation (PHR format) ---
    # Computed deterministically from numeric fields; not author-supplied.
    yrs = r["years"]
    first, last = yrs[0], yrs[-1]
    def yr_short(fy):  # "FY22" -> "22"
        d = "".join(ch for ch in str(fy) if ch.isdigit())
        return d[-2:] if len(d) >= 2 else d
    span = f'{yr_short(first["fy"])}\u2192{yr_short(last["fy"])}'
    def pct_delta(a, b):
        if a in (None, 0): return "n/a"
        ch = (b - a) / a * 100.0
        if abs(ch) < 0.5: return "flat"
        return f'{"+" if ch >= 0 else "\u2212"}{abs(ch):.0f}%'
    def num(row, key):
        v = row.get(key)
        return float(v) if v is not None else None
    # multiples: prefer numeric realized/base; fall back to parsing the mult string
    def mult_val(row):
        b, rz = num(row,"base_num"), num(row,"realized_num")
        if b and rz is not None: return rz / b
        m = str(row.get("mult","")).replace("\u00d7","").replace("x","").strip()
        try: return float(m)
        except ValueError: return None
    base_d   = pct_delta(num(first,"base_num"),     num(last,"base_num"))
    target_d = pct_delta(num(first,"target_num"),   num(last,"target_num"))
    realiz_d = pct_delta(num(first,"realized_num"), num(last,"realized_num"))
    m0, m1 = mult_val(first), mult_val(last)
    mult_d = (f'{m0:.2f}\u2192{m1:.2f}\u00d7' if (m0 is not None and m1 is not None) else "n/a")
    slots = [
        ("Base", base_d),
        ("Target opp.", target_d),
        ("Realized bonus", realiz_d),
        ("Bonus/base", mult_d),
    ]
    def vclass(v):  # gold for "flat", default otherwise
        return "flat" if v == "flat" else ""
    deltas = "".join(
        f'<div>{esc(label)} {span}<span class="v {vclass(val)}">{esc(val)}</span></div>'
        for label, val in slots)
    note=f'<div class="foot-note">{r["note"]}</div>' if r.get("note") else ""
    return (f'<table class="real"><thead><tr><th class="l">FY</th><th>Base</th><th>Target</th>'
            f'<th>Payout</th><th>Realized&nbsp;$</th><th class="l" style="padding-left:14px">vs opportunity</th>'
            f'<th>&times;base</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
            f'<div class="delta">{deltas}</div>{note}')

# ---------- pay structure slopegraph ----------
def paystructure_svg(spec):
    ps=spec.get("pay_structure")
    if not ps: return ""
    years=ps["years"]; series=ps["series"]
    n=len(years); x0=42; x1=366; xs=[x0+ (x1-x0)*i/(n-1) for i in range(n)] if n>1 else [x0]
    def yv(p): return round(180 - p*1.58,1)
    p=[f'<svg width="100%" viewBox="0 0 420 210" role="img" aria-label="LTIP grant mix by year">']
    for i,y in enumerate(years):
        p.append(f'<text x="{xs[i]:.0f}" y="196" fill="{MUTE}" font-size="11.5" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace">{esc(y)}</text>')
    p.append(f'<line x1="{x0}" y1="22" x2="{x0}" y2="180" stroke="{BORDER}" stroke-width="0.5"/>')
    p.append(f'<line x1="{x1}" y1="22" x2="{x1}" y2="180" stroke="{BORDER}" stroke-width="0.5"/>')
    for s in series:
        col=s["color"]; vals=s["values"]
        pts=[]
        for i,v in enumerate(vals):
            if v is None: continue
            pts.append(f"{xs[i]:.0f},{yv(v):.0f}")
        if pts:
            p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>')
            # endpoints
            firsti=next(i for i,v in enumerate(vals) if v is not None)
            lasti=max(i for i,v in enumerate(vals) if vals[i] is not None)
            p.append(f'<circle cx="{xs[firsti]:.0f}" cy="{yv(vals[firsti]):.0f}" r="3" fill="{col}"/>')
            p.append(f'<circle cx="{xs[lasti]:.0f}" cy="{yv(vals[lasti]):.0f}" r="3" fill="{col}"/>')
            p.append(f'<text x="{x1+7}" y="{yv(vals[lasti])+3:.0f}" fill="{col}" font-size="11.5" '
                     f'font-family="JetBrains Mono,monospace">{vals[lasti]:.0f}</text>')
    p.append("</svg>")
    return "".join(p)

# ---------- graceful degradation: stub sheet ----------
def build_stub(spec):
    """Render a minimal, honest sheet when there is no chartable plan data.
    spec needs: ticker, company, meta (optional), mode ('no_coverage' | 'no_plan'),
    reason (HTML string), and optional 'disclosed' (list of {label,value} rows of
    whatever IS known, e.g. CEO name, base salary, pay vehicle)."""
    mode = spec["mode"]
    if mode == "no_coverage":
        headline = "No incentive-plan data available"
        body = ("Verity / InsiderScore does not have structured executive incentive-plan "
                "data for this ticker. This may mean the company is not covered, recently "
                "listed, foreign-domiciled, or filed under a different entity. "
                + spec.get("reason",""))
    else:  # no_plan
        headline = "No metric-based incentive plan disclosed"
        body = ("This company is covered, but its proxy does not express executive pay as a "
                "weighted, metric-driven annual or long-term incentive plan, so there is no "
                "target-vs-outcome structure to chart. " + spec.get("reason",""))
    disclosed = ""
    if spec.get("disclosed"):
        rows = "".join(f'<tr><td class="l">{esc(d["label"])}</td>'
                       f'<td class="dollar" style="text-align:right">{esc(d["value"])}</td></tr>'
                       for d in spec["disclosed"])
        disclosed = (f'<div class="sec-title" style="margin-top:22px">What is disclosed '
                     f'<span class="note">from the proxy</span></div>'
                     f'<table class="real" style="max-width:420px"><tbody>{rows}</tbody></table>')
    return STUB_TEMPLATE.format(
        title=esc(spec["ticker"]), ticker=esc(spec["ticker"]),
        company=esc(spec["company"]), meta=spec.get("meta",""), logo_b64=LOGO_B64,
        headline=esc(headline), body=body, disclosed=disclosed,
        footer=spec.get("footer",
            "<b>Source:</b> Verity / InsiderScore incentive-plan data. "
            "Absence of a metric-based plan is itself a disclosure fact, not an error. "
            "<b>Not investment advice.</b>"))

# ---------- full document ----------
import re as _re

# Raw-HTML fields passed through verbatim (NOT later escaped by the script). Bare "&"
# in these must be "&amp;" or output is malformed; this list drives the auto-sanitizer.
# IMPORTANT: this is exactly the set of fields the script does NOT run html.escape() on.
# Plain-text fields (captions, *_note, labels) are escaped by the script, so they take a
# LITERAL "&" and must NOT be sanitized here (doing so would double-escape to "&amp;amp;").
_RAW_HTML_FIELDS = ("meta", "takeaway", "thesis", "classification_rule",
                    "provenance_html", "pay_legend", "footer")
# Required top-level fields for a full (non-stub) sheet, each mapped to the workflow
# step that defines it, so a missing field fails with guidance instead of a KeyError.
_REQUIRED_FIELDS = {
    "ticker": "Step 5", "company": "Step 5", "meta": "Step 5",
    "takeaway": "Step 5b — the 'What it means' investment read (REQUIRED, leads the sheet)",
    "thesis": "Step 5", "years": "Step 5", "ceo": "Step 3/5",
    "orientation_caption": "Step 5", "orientation_points": "orientation step",
    "orientation_note": "Step 5", "goalpost_caption": "Step 5", "goalposts": "goalpost step",
    "matrix_rows": "matrix step", "aip_total": "matrix step", "matrix_note": "Step 5",
    "pay_structure_caption": "Step 5", "pay_legend": "Step 5", "pay_structure": "Step 5",
    "pay_structure_note": "Step 5", "realization": "realization step",
    "classification_rule": "Step 5", "provenance_html": "Step 4", "footer": "Step 5",
}

def _sanitize_ampersands(spec):
    """In raw-HTML fields, escape any bare '&' that is not already an entity.
    Turns 'S&P 500' -> 'S&amp;P 500' but leaves '&amp;', '&rarr;', '&#9650;' intact."""
    bare = _re.compile(r'&(?!(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#x[0-9A-Fa-f]+);)')
    for k in _RAW_HTML_FIELDS:
        v = spec.get(k)
        if isinstance(v, str):
            spec[k] = bare.sub('&amp;', v)

def validate_spec(spec):
    """Front gate: clear, actionable failures before any rendering.
    Stubs are validated lightly; full specs get the complete required-field check
    plus ampersand auto-sanitization of raw-HTML fields."""
    if spec.get("mode") in ("no_coverage", "no_plan"):
        for f in ("ticker", "company"):
            if f not in spec:
                raise ValueError(f"Stub spec missing required field '{f}'.")
        return spec
    missing = [f"'{f}' ({_REQUIRED_FIELDS[f]})" for f in _REQUIRED_FIELDS if f not in spec]
    if missing:
        raise ValueError("Spec is missing required field(s):\n  - " + "\n  - ".join(missing))
    # structural sanity that otherwise fails cryptically deep in rendering
    if not isinstance(spec["ceo"], list) or not spec["ceo"]:
        raise ValueError("'ceo' must be a non-empty list of {who, when}.")
    pts = spec.get("orientation_points", [])
    if len(pts) != len(spec["years"]):
        raise ValueError(f"orientation_points ({len(pts)}) must match years ({len(spec['years'])}).")
    for md in spec.get("orientation_modifiers", []):
        if md.get("pole") not in ("growth", "profitability", "tsr", "sr", "other"):
            raise ValueError(f"orientation_modifier pole '{md.get('pole')}' invalid "
                             "(use growth/profitability/tsr/other).")
    _sanitize_ampersands(spec)
    return spec

def build(spec):
    spec = validate_spec(spec)
    # graceful failure routing
    if spec.get("mode") in ("no_coverage", "no_plan"):
        return build_stub(spec)
    # goalpost layout: ALWAYS stack full-width (one panel per row). These are screen-
    # viewed; vertical space is free and legibility wins, so we never compress into a
    # 2-col grid (which shrank each SVG ~50% and made dots/labels hard to read).
    gps=spec["goalposts"]
    grid = False
    gp_html="".join(goalpost_block(m) for m in gps)

    # CEO strip
    ceo=spec["ceo"]
    if len(ceo)==1:
        ceo_html=(f'<div class="ceo-strip"><span class="lbl">CEO</span>'
                  f'<div class="ceo-seg curr" style="flex:1 1 auto"><span class="who">{esc(ceo[0]["who"])}</span>'
                  f'<span class="when">{esc(ceo[0]["when"])}</span></div></div>')
    else:
        segs=[]
        for i,c in enumerate(ceo):
            if i>0: segs.append('<div class="ceo-switch" title="CEO transition">&rarr;</div>')
            klass="prior" if i<len(ceo)-1 else "curr"
            segs.append(f'<div class="ceo-seg {klass}"><span class="who">{esc(c["who"])}</span>'
                        f'<span class="when">{esc(c["when"])}</span></div>')
        ceo_html=f'<div class="ceo-strip"><span class="lbl">CEO</span>{"".join(segs)}</div>'

    quad=quadrant_svg(spec["orientation_points"], spec.get("orientation_modifiers"))
    matrix=matrix_html(spec)
    modifiers=modifiers_html(spec)
    realization=realization_html(spec)
    paystruct=paystructure_svg(spec)

    return TEMPLATE.format(
        title=esc(spec["ticker"]),
        ticker=esc(spec["ticker"]), company=esc(spec["company"]),
        meta=spec["meta"], thesis=spec["thesis"],
        takeaway=spec["takeaway"], logo_b64=LOGO_B64,
        ceo_strip=ceo_html,
        orient_cap=esc(spec["orientation_caption"]),
        quadrant=quad, orient_note=esc(spec["orientation_note"]),
        goalpost_cap=esc(spec["goalpost_caption"]),
        goalposts=gp_html,
        matrix=matrix,
        modifiers=modifiers,
        paystruct_block=(f'<div class="block" style="margin-bottom:0"><div class="sec-title">Pay structure '
                         f'<span class="note">LTIP grant mix</span></div>'
                         f'<div class="cap">{esc(spec.get("pay_structure_caption",""))}</div>'
                         f'{spec.get("pay_legend","")}{paystruct}'
                         f'<div class="foot-note">{esc(spec.get("pay_structure_note",""))}</div></div>'
                         if paystruct else "<div></div>"),
        realization=realization,
        rule=spec["classification_rule"],
        provenance=spec["provenance_html"],
        footer=spec["footer"],
    )

# Templates loaded from sibling files
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "template.html")) as f:
    TEMPLATE=f.read()
with open(os.path.join(_HERE, "stub_template.html")) as f:
    STUB_TEMPLATE=f.read()
with open(os.path.join(_HERE, "verity_logo_b64.txt")) as f:
    LOGO_B64=f.read().strip()

def preflight(annual_rows, longterm_rows):
    """Classify the raw Verity response into one of: 'ok', 'no_coverage', 'no_plan'.
    Call this BEFORE attempting to build a full spec.
      no_coverage : both endpoints returned empty lists -> not covered.
      no_plan     : rows exist but none carry a usable plan (all status 'No AIP'/'No LTIP'
                    or 'Needs Processing' with no metrics, and no base salary / formula).
      ok          : at least one year/cycle has metrics or a formula to chart."""
    rows = (annual_rows or []) + (longterm_rows or [])
    if not rows:
        return "no_coverage"
    def usable(r):
        if r.get("metrics"):
            return True
        if r.get("formula") or r.get("formula_note","").strip() and "No " not in r.get("status",""):
            return bool(r.get("metrics"))
        return False
    if any(usable(r) for r in rows):
        return "ok"
    return "no_plan"

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--output", required=True)
    a=ap.parse_args()
    spec=json.load(open(a.spec))
    out=build(spec)
    open(a.output,"w").write(out)
    print(f"wrote {a.output} ({len(out)} bytes)")
    mode = spec.get("mode","ok")
    if mode in ("no_coverage","no_plan"):
        print(f"  ticker={spec['ticker']} mode={mode} (stub sheet)")
    else:
        print(f"  ticker={spec['ticker']} years={len(spec['years'])} "
              f"goalposts={len(spec['goalposts'])} (stack) "
              f"orientation_pts={len(spec['orientation_points'])} ceo_segs={len(spec['ceo'])}")

```

<!-- FILE: scripts/template.html -->
```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Incentive Design Tear Sheet</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;600&family=Libre+Baskerville:ital@0;1&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',-apple-system,sans-serif;background:#f8f7f4;color:#2c2c2c;font-size:13.8px;line-height:1.5;-webkit-font-smoothing:antialiased}}
.sheet{{max-width:1180px;margin:0 auto;padding:0 20px 28px}}
.mono{{font-family:'JetBrains Mono',monospace}}
.hdr{{background:#1a1a2e;color:#e0ddd5;padding:13px 20px 12px;margin:0 -20px 0;border-bottom:1px solid #c9a84c}}
.hdr-top{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
.tk-big{{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:25.3px;letter-spacing:0.5px;color:#e8e4db}}
.co-name{{font-family:'Libre Baskerville',Georgia,serif;font-size:18.4px;color:#c9a84c}}
.hdr-logo{{margin-left:auto;height:26px;width:auto;display:block}}
.hdr-meta-line{{color:#8a8578;font-size:12.6px;margin-top:6px;line-height:1.5}}
.takeaway{{background:#fff;border:1px solid #e0ddd2;border-left:3px solid #c9a84c;border-radius:0 3px 3px 0;padding:12px 16px;margin:16px 0 14px}}
.takeaway-label{{font-family:'Inter',sans-serif;font-size:10.3px;font-weight:600;text-transform:uppercase;letter-spacing:1.2px;color:#9a7d2e;margin-bottom:5px}}
.takeaway-body{{font-family:'Libre Baskerville',Georgia,serif;font-size:16.7px;line-height:1.55;color:#1a1a2e}}
.takeaway-body b{{color:#1a1a2e;font-weight:700}}
.thesis-line{{font-size:13.8px;color:#5a5750;line-height:1.6;max-width:920px;margin:0 0 20px}}
.thesis-line b{{color:#1a1a2e;font-weight:600}}
.sec-title{{font-family:'Libre Baskerville',Georgia,serif;font-size:14.9px;color:#1a1a2e;text-transform:uppercase;letter-spacing:1px;margin:0 0 4px;padding-bottom:5px;border-bottom:2px solid #1a1a2e;display:flex;align-items:baseline;justify-content:space-between}}
.sec-title .note{{font-family:'Inter',sans-serif;font-size:12.1px;text-transform:none;letter-spacing:0;color:#9a958c;font-weight:400}}
.cap{{font-size:12.1px;color:#8a8578;margin:0 0 12px;line-height:1.5}}
.foot-note{{font-size:11.5px;color:#9a958c;margin-top:6px;line-height:1.5}}
.block{{margin-bottom:24px}}
.row{{display:grid;gap:22px;margin-bottom:24px}}
.row.split{{grid-template-columns:minmax(0,420px) minmax(0,1fr)}}
.row.orient-row{{display:grid;gap:22px;margin-bottom:24px;grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:start}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.legend{{display:flex;gap:14px;font-size:12.1px;color:#5a5750;margin:0 0 10px;flex-wrap:wrap;align-items:center}}
.legend span{{display:flex;align-items:center;gap:5px}}
.sw{{width:11px;height:11px;border-radius:2px;display:inline-block}}
svg text{{font-family:'Inter',sans-serif}}
.metric-block{{margin-bottom:20px}}
.metric-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}}
.metric-name{{font-size:16.1px;font-weight:600;color:#1a1a2e}}
.metric-wt{{font-family:'JetBrains Mono',monospace;font-size:13.2px;color:#8a8578}}
.metric-sub{{font-size:12.6px;color:#6b6860;margin-left:auto;font-family:'JetBrains Mono',monospace}}
table.matrix{{width:100%;border-collapse:collapse;font-size:13.8px}}
.matrix th{{padding:6px;border-bottom:2px solid #1a1a2e;font-size:11.5px;color:#6b6860;text-transform:uppercase;letter-spacing:0.6px;font-weight:600;text-align:center}}
.matrix th.lab{{text-align:left}}
.matrix td{{padding:0;border-bottom:1px solid #e9e6df;height:38px;text-align:center;vertical-align:middle}}
.matrix td.lab{{text-align:left;padding:5px 8px 5px 0}}
.matrix .mname{{font-size:13.2px;font-weight:500;color:#1a1a2e;line-height:1.2}}
.matrix .mclass{{font-size:10.3px;color:#9a958c;text-transform:uppercase;letter-spacing:0.4px}}
.matrix tbody tr:hover td{{background:#f3f1ea}}
.grp{{font-size:10.3px;text-transform:uppercase;letter-spacing:1px;color:#9a7d2e;font-weight:600;padding:10px 0 3px;text-align:left}}
.cell{{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;width:58px;height:30px;gap:1px}}
.cell .w{{font-family:'JetBrains Mono',monospace;font-size:10.3px;color:#8a8578}}
.cell .p{{font-family:'JetBrains Mono',monospace;font-size:13.8px;font-weight:600}}
.empty{{color:#d8d4ca;font-size:14.9px}}
.p-max{{color:#2d6a4f}}.p-mid{{color:#9a7d2e}}.p-low{{color:#3d7a5f}}.p-open{{color:#b5b0a5;font-size:11.5px}}.p-miss{{color:#a4343a}}.neg{{color:#a4343a}}
.bench-mark{{color:#c9a84c;font-size:10.3px;font-weight:700;line-height:0;margin-left:1px;vertical-align:super}}
.totrow td{{border-top:2px solid #1a1a2e;border-bottom:none;padding-top:7px;height:auto}}
.totrow .lab{{font-size:12.1px;font-weight:600;color:#1a1a2e;text-transform:uppercase;letter-spacing:0.5px}}
.tot{{font-family:'JetBrains Mono',monospace;font-size:14.9px;font-weight:600}}
table.real{{width:100%;border-collapse:collapse}}
.real th{{font-size:11.5px;color:#6b6860;text-transform:uppercase;letter-spacing:0.6px;font-weight:600;padding:5px 8px 6px;border-bottom:2px solid #1a1a2e;text-align:right}}
.real th.l{{text-align:left}}
.real td{{padding:8px;border-bottom:1px solid #e9e6df;text-align:right;vertical-align:middle}}
.real td.l{{text-align:left}}
.real tbody tr:hover td{{background:#f3f1ea}}
.yr{{font-family:'JetBrains Mono',monospace;font-weight:600;color:#1a1a2e;font-size:13.8px}}
.dollar{{font-family:'JetBrains Mono',monospace;font-size:13.2px}}
.mult{{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:13.8px}}
.opp{{position:relative;height:16px;width:150px;background:#ece9e1;border-radius:2px;display:inline-block;vertical-align:middle;overflow:hidden}}
.opp>i{{position:absolute;left:0;top:0;bottom:0;background:#9a7d2e;display:block}}
.opp>i.over{{background:#2d6a4f}}
.opp .tgt{{position:absolute;top:-2px;bottom:-2px;width:1.5px;background:#1a1a2e;z-index:2}}
.delta{{display:flex;gap:20px;margin-top:12px;padding-top:10px;border-top:1px solid #ddd9d0;flex-wrap:wrap}}
.delta div{{font-size:12.1px;color:#6b6860}}
.delta .v{{font-family:'JetBrains Mono',monospace;font-size:16.1px;color:#1a1a2e;font-weight:600;display:block;margin-top:2px}}
.delta .v.flat{{color:#9a7d2e}}
.rule{{font-size:11.5px;color:#6b6860;background:#f1efe8;border-left:2px solid #b8975a;padding:8px 12px;margin:6px 0 0;line-height:1.6}}
.rule b{{color:#1a1a2e;font-weight:600}}
.ceo-strip{{display:flex;align-items:stretch;gap:0;margin:0 0 22px;border:1px solid #e0ddd2;border-radius:3px;overflow:hidden}}
.ceo-strip .lbl{{background:#1a1a2e;color:#c9a84c;font-size:10.3px;text-transform:uppercase;letter-spacing:1px;font-weight:600;padding:0 12px;display:flex;align-items:center;white-space:nowrap}}
.ceo-seg{{padding:7px 12px;display:flex;flex-direction:column;justify-content:center;border-left:1px solid #e0ddd2}}
.ceo-seg .who{{font-size:13.8px;font-weight:600;color:#1a1a2e}}
.ceo-seg .when{{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:#8a8578;margin-top:1px}}
.ceo-seg.prior{{background:#f1efe8;flex:0 0 auto}}
.ceo-seg.curr{{background:#fff;flex:1 1 auto}}
.ceo-switch{{display:flex;align-items:center;padding:0 4px;background:#faf6ed;color:#9a7d2e;font-size:14.9px;border-left:1px solid #e0ddd2}}
.foot{{margin-top:14px;padding-top:9px;border-top:1px solid #ddd9d0;font-size:11.5px;color:#b5b0a5;line-height:1.6}}
.foot b{{color:#8a8578;font-weight:500}}
.mg-strip{{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}}
.mg-chip{{display:flex;align-items:center;gap:8px;border:1px solid #e0ddd2;border-radius:3px;padding:5px 9px 5px 5px;background:#fff}}
.mg-tag{{font-family:'JetBrains Mono',monospace;font-size:9.8px;font-weight:600;letter-spacing:0.5px;padding:2px 5px;border-radius:2px}}
.mg-gate{{background:#f4e7e7;color:#a4343a}}
.mg-mod{{background:#eef0e9;color:#5f7a3d}}
.mg-body{{display:flex;flex-direction:column;line-height:1.3}}
.mg-name{{font-size:12.6px;font-weight:500;color:#1a1a2e}}
.mg-meta{{font-size:10.9px;color:#9a958c;font-family:'JetBrains Mono',monospace}}
.mg-out{{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:#6b6860;padding-left:6px;border-left:1px solid #e5e2db;align-self:stretch;display:flex;align-items:center}}
@media(max-width:900px){{.row.split{{grid-template-columns:1fr}}.row.orient-row{{grid-template-columns:1fr}}.cols{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="sheet">

  <div class="hdr">
    <div class="hdr-top">
      <span class="tk-big">{ticker}</span>
      <span class="co-name">{company}</span>
      <img class="hdr-logo" src="data:image/png;base64,{logo_b64}" alt="Verity"/>
    </div>
    <div class="hdr-meta-line">{meta}</div>
  </div>

  <div class="takeaway">
    <div class="takeaway-label">What it means</div>
    <div class="takeaway-body">{takeaway}</div>
  </div>

  <div class="thesis-line">{thesis}</div>

  {ceo_strip}

  <div class="row orient-row">
    <div class="block" style="margin-bottom:0">
      <div class="sec-title">Incentive orientation <span class="note">strategic posture of the pay plan</span></div>
      <div class="cap">{orient_cap}</div>
      {quadrant}
      <div class="foot-note">{orient_note}</div>
    </div>
    <div class="block" style="margin-bottom:0">
      <div class="sec-title">Targets vs outcomes <span class="note">disclosed bands, by fiscal year</span></div>
      <div class="cap">{goalpost_cap}</div>
      <div class="legend">
        <span><svg width="46" height="12"><rect x="2" y="4" width="38" height="5" fill="#e0ddd2"/><rect x="18" y="2" width="1.5" height="9" fill="#1a1a2e"/></svg>thr&ndash;max, notch=target</span>
        <span><svg width="14" height="12"><circle cx="7" cy="6" r="4" fill="#2d6a4f"/></svg>&ge; max</span>
        <span><svg width="14" height="12"><circle cx="7" cy="6" r="4" fill="#9a7d2e"/></svg>in band</span>
        <span><svg width="14" height="12"><circle cx="7" cy="6" r="4" fill="#a4343a"/></svg>&lt; threshold</span>
      </div>
      {goalposts}
    </div>
  </div>

  <div class="block">
    <div class="sec-title">Metric persistence <span class="note">weight &middot; realized payout, % of target, by fiscal year</span></div>
    <div class="cap">Every metric used in any year is a row; the cell carries its weight (top) and realized payout (bottom). Gaps mark absence; &ldquo;open&rdquo; marks unfinished cycles.</div>
    {matrix}
    {modifiers}
  </div>

  <div class="row split">
    {paystruct_block}
    <div class="block" style="margin-bottom:0">
      <div class="sec-title">Bonus realization <span class="note">CEO annual cash incentive &middot; opportunity vs delivered</span></div>
      <div class="cap">Bar fills realized payout against each year&rsquo;s opportunity ceiling (the AIP maximum); notch is target.</div>
      {realization}
    </div>
  </div>

  <div class="rule">{rule}</div>

  <div class="block" style="margin-top:24px">
    <div class="sec-title">Filed since the proxy <span class="note">post-proxy compensation events</span></div>
    {provenance}
  </div>

  <div class="foot">{footer}</div>

</div></body></html>

```

<!-- FILE: scripts/stub_template.html -->
```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Incentive Design Tear Sheet</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500;600&family=Libre+Baskerville:ital@0;1&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',-apple-system,sans-serif;background:#f8f7f4;color:#2c2c2c;font-size:12px;line-height:1.5;-webkit-font-smoothing:antialiased}}
.sheet{{max-width:1180px;margin:0 auto;padding:0 20px 28px}}
.mono{{font-family:'JetBrains Mono',monospace}}
.hdr{{background:#1a1a2e;color:#e0ddd5;padding:14px 20px 12px;margin:0 -20px 18px;border-bottom:1px solid #c9a84c}}
.hdr-top{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
.tk-big{{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:22px;letter-spacing:0.5px;color:#e8e4db}}
.co-name{{font-family:'Libre Baskerville',Georgia,serif;font-size:16px;color:#c9a84c}}
.hdr-meta{{color:#8a8578;font-size:11px;margin-left:auto;text-align:right;line-height:1.6}}
.sec-title{{font-family:'Libre Baskerville',Georgia,serif;font-size:13px;color:#1a1a2e;text-transform:uppercase;letter-spacing:1px;margin:0 0 4px;padding-bottom:5px;border-bottom:2px solid #1a1a2e;display:flex;align-items:baseline;justify-content:space-between}}
.sec-title .note{{font-family:'Inter',sans-serif;font-size:10.5px;text-transform:none;letter-spacing:0;color:#9a958c;font-weight:400}}
.notice{{background:#fff;border:1px solid #e5e2db;border-left:3px solid #c9a84c;border-radius:3px;padding:18px 20px;margin-top:6px}}
.notice h2{{font-family:'Libre Baskerville',Georgia,serif;font-size:16px;font-weight:400;color:#1a1a2e;margin-bottom:8px}}
.notice p{{font-size:12.5px;color:#5a5750;line-height:1.6;max-width:760px}}
table.real{{width:100%;border-collapse:collapse;margin-top:4px}}
.real td{{padding:7px 8px;border-bottom:1px solid #e9e6df;font-size:12px}}
.real td.l{{text-align:left;color:#6b6860}}
.dollar{{font-family:'JetBrains Mono',monospace;font-size:11.5px}}
.foot{{margin-top:18px;padding-top:9px;border-top:1px solid #ddd9d0;font-size:10px;color:#b5b0a5;line-height:1.6}}
.foot b{{color:#8a8578;font-weight:500}}
</style></head>
<body><div class="sheet">
  <div class="hdr">
    <div class="hdr-top">
      <span class="tk-big">{ticker}</span>
      <span class="co-name">{company}</span>
      <img src="data:image/png;base64,{logo_b64}" alt="Verity" style="margin-left:auto;height:24px;width:auto"/>
    </div>
    <div class="hdr-meta" style="margin-left:0;text-align:left;margin-top:6px">{meta}</div>
  </div>
  <div class="notice">
    <h2>{headline}</h2>
    <p>{body}</p>
  </div>
  {disclosed}
  <div class="foot">{footer}</div>
</div></body></html>

```

<!-- FILE: scripts/to_pdf.py -->
```python
#!/usr/bin/env python3
"""
to_pdf.py — render a tear-sheet HTML file to a SINGLE-PAGE (un-paginated) PDF.

Hedge-fund analysts forward these to PMs, who can't easily open an HTML artifact.
A normal PDF export would slice the dense sheet across letter pages and break panels
mid-figure. Instead this renders the whole sheet as ONE continuous page sized exactly
to the content — scroll/zoom in any viewer, nothing chopped.

Uses headless Chromium (Playwright) so SVG, web fonts, CSS grid, the quadrant arrows
and concentric rings all render exactly as in the browser.

Usage:
  python3 to_pdf.py --html /path/CRUS_tearsheet.html --output /path/CRUS_tearsheet.pdf
  # optional: --width-px 1180 (CSS px of the sheet; default matches .sheet max-width)
"""
import argparse, pathlib
from playwright.sync_api import sync_playwright

# CSS px per inch in the print box (Chromium uses 96).
PX_PER_IN = 96.0

def render(html_path, out_path, width_px=1180, margin_px=24, scale=1.0):
    url = pathlib.Path(html_path).resolve().as_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Fix the viewport width to the sheet width so layout matches the on-screen design;
        # height is arbitrary here — we measure the real content height after load.
        page = browser.new_page(viewport={"width": width_px, "height": 1400},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        # Ensure web fonts are done so height measurement is correct.
        try:
            page.evaluate("document.fonts && document.fonts.ready")
            page.wait_for_timeout(250)
        except Exception:
            pass
        # Full content box: the .sheet element if present, else the body scroll height.
        dims = page.evaluate(
            """() => {
                const el = document.querySelector('.sheet') || document.body;
                const r = el.getBoundingClientRect();
                const h = Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight,
                    Math.ceil(r.bottom)
                );
                return {w: Math.ceil(r.width), h: Math.ceil(h)};
            }"""
        )
        content_w = width_px
        content_h = dims["h"] + margin_px  # small bottom breathing room
        # One page exactly the size of the content -> no pagination.
        page.pdf(
            path=out_path,
            width=f"{content_w/PX_PER_IN:.3f}in",
            height=f"{content_h/PX_PER_IN:.3f}in",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            scale=scale,
            prefer_css_page_size=False,
        )
        browser.close()
    return content_w, content_h

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--width-px", type=int, default=1180,
                    help="CSS pixel width of the sheet (default 1180, matches .sheet max-width)")
    a = ap.parse_args()
    w, h = render(a.html, a.output, width_px=a.width_px)
    print(f"wrote {a.output}  ({w}px x {h}px single page, {w/PX_PER_IN:.1f}in x {h/PX_PER_IN:.1f}in)")

```

<!-- FILE: dis_spec.json -->
```json
{
  "ticker": "DIS",
  "company": "The Walt Disney Company",
  "meta": "Consumer Discretionary · Movies &amp; Entertainment · ~$173B mkt cap<br>Fiscal years 2021–2025 · annual &amp; long-term incentive plans",
  "thesis": "A profitability-disciplined plan whose stock-based half kept paying zero. The annual bonus is stable every year — 35% <b>segment operating income</b>, 17.5% <b>revenue</b>, 17.5% <b>after-tax free cash flow</b>, 30% <b>other factors</b> — and has paid 97–191% as parks and the streaming pivot recovered. The long-term plan is 50% <b>relative TSR</b> (vs. the S&amp;P 500) + 50% <b>return on invested capital</b>, but relative TSR paid <b>0% in all three completed cycles</b>, so the equity earned out only on ROIC (49–73%).",
  "years": [
    "FY21",
    "FY22",
    "FY23",
    "FY24",
    "FY25"
  ],
  "ceo": [
    {
      "who": "Robert A. Chapek",
      "when": "FY21–FY22"
    },
    {
      "who": "Robert A. Iger",
      "when": "FY23–FY25 · returned Nov 2022"
    }
  ],
  "orientation_caption": "Horizontal: profitability (left) to growth (right). Vertical: shareholder return (top) to other (bottom). Net weight tilt on each axis, AIP and LTIP blended equally. Relative TSR is a weighted LTIP metric here (not a modifier), so it places the dot rather than appearing as an arrow.",
  "orientation_points": [
    {
      "label": "FY21",
      "growth": 0.088,
      "profitability": 0.512,
      "sr": 0.25,
      "other": 0.15
    },
    {
      "label": "FY22",
      "growth": 0.088,
      "profitability": 0.512,
      "sr": 0.25,
      "other": 0.15
    },
    {
      "label": "FY23",
      "growth": 0.088,
      "profitability": 0.512,
      "sr": 0.25,
      "other": 0.15
    },
    {
      "label": "FY24",
      "growth": 0.088,
      "profitability": 0.512,
      "sr": 0.25,
      "other": 0.15
    },
    {
      "label": "FY25",
      "growth": 0.088,
      "profitability": 0.637,
      "sr": 0.125,
      "other": 0.15
    }
  ],
  "orientation_note": "DIS sits firmly in Capital Discipline (profitability + shareholder return), heavily profitability-led: segment operating income and free cash flow dominate the AIP, and ROIC is half the LTIP. FY21–24 cluster at one point; FY25 shifts further left as the new LTIP grant added Adjusted EPS Growth (50%) and cut the relative-TSR weight from 50% to 25% — more profitability emphasis, less market-relative. Growth weight is low because revenue is only 17.5% of the AIP and absent from the LTIP.",
  "goalpost_caption": "Bar spans threshold → maximum in reported dollars; notch is target; dot is actual. The three AIP financial metrics carry clean disclosed bands; segment operating income and free cash flow crossed from negative to positive over the period (the FY21 COVID trough), so the zero line is shown. Green ≥ max, gold in-band, red below threshold.",
  "goalposts": [
    {
      "name": "Adjusted segment operating income",
      "weight_label": "35% AIP · profitability",
      "axis_min": -5000,
      "axis_max": 20000,
      "axis_min_label": "-$5B",
      "axis_max_label": "$20B",
      "show_zero": true,
      "years": [
        {
          "label": "FY21",
          "thr": -3906,
          "tgt": -856,
          "max": 2194,
          "actual": 4055
        },
        {
          "label": "FY22",
          "thr": 6556,
          "tgt": 9856,
          "max": 12656,
          "actual": 12121
        },
        {
          "label": "FY23",
          "thr": 9957,
          "tgt": 13257,
          "max": 16300,
          "actual": 12863
        },
        {
          "label": "FY24",
          "thr": 11937,
          "tgt": 14469,
          "max": 16494,
          "actual": 15601
        },
        {
          "label": "FY25",
          "thr": 14043,
          "tgt": 16329,
          "max": 18615,
          "actual": 17472
        }
      ]
    },
    {
      "name": "Adjusted revenue",
      "weight_label": "17.5% AIP · growth",
      "axis_min": 50000,
      "axis_max": 100000,
      "axis_min_label": "$50B",
      "axis_max_label": "$100B",
      "years": [
        {
          "label": "FY21",
          "thr": 55030,
          "tgt": 60813,
          "max": 66596,
          "actual": 66736
        },
        {
          "label": "FY22",
          "thr": 71577,
          "tgt": 83527,
          "max": 89020,
          "actual": 82722
        },
        {
          "label": "FY23",
          "thr": 82857,
          "tgt": 91927,
          "max": 97973,
          "actual": 88898
        },
        {
          "label": "FY24",
          "thr": 82474,
          "tgt": 91502,
          "max": 97520,
          "actual": 91361
        },
        {
          "label": "FY25",
          "thr": 86106,
          "tgt": 92587,
          "max": 99068,
          "actual": 94199
        }
      ]
    },
    {
      "name": "Adjusted after-tax free cash flow",
      "weight_label": "17.5% AIP · profitability",
      "axis_min": -12000,
      "axis_max": 13000,
      "axis_min_label": "-$12B",
      "axis_max_label": "$13B",
      "show_zero": true,
      "years": [
        {
          "label": "FY21",
          "thr": -11871,
          "tgt": -8187,
          "max": -4503,
          "actual": -2188
        },
        {
          "label": "FY22",
          "thr": -2534,
          "tgt": -534,
          "max": 1466,
          "actual": 1043
        },
        {
          "label": "FY23",
          "thr": -1552,
          "tgt": 1448,
          "max": 4448,
          "actual": 2449
        },
        {
          "label": "FY24",
          "thr": 4425,
          "tgt": 8425,
          "max": 12425,
          "actual": 8657
        },
        {
          "label": "FY25",
          "thr": 3464,
          "tgt": 6464,
          "max": 9464,
          "actual": 8273
        }
      ]
    }
  ],
  "matrix_rows": [
    {
      "group": "Annual incentive (AIP) — stable four-factor structure every year",
      "name": "Adjusted segment operating income",
      "cls": "Profitability · financial",
      "cells": {
        "FY21": {
          "w": "35%",
          "p": 200
        },
        "FY22": {
          "w": "35%",
          "p": 181
        },
        "FY23": {
          "w": "35%",
          "p": 92
        },
        "FY24": {
          "w": "35%",
          "p": 156
        },
        "FY25": {
          "w": "35%",
          "p": 150
        }
      }
    },
    {
      "name": "Adjusted revenue",
      "cls": "Growth · financial",
      "cells": {
        "FY21": {
          "w": "17.5%",
          "p": 200
        },
        "FY22": {
          "w": "17.5%",
          "p": 96
        },
        "FY23": {
          "w": "17.5%",
          "p": 78
        },
        "FY24": {
          "w": "17.5%",
          "p": 99
        },
        "FY25": {
          "w": "17.5%",
          "p": 125
        }
      }
    },
    {
      "name": "Adjusted after-tax free cash flow",
      "cls": "Profitability · financial",
      "cells": {
        "FY21": {
          "w": "17.5%",
          "p": 200
        },
        "FY22": {
          "w": "17.5%",
          "p": 179
        },
        "FY23": {
          "w": "17.5%",
          "p": 133
        },
        "FY24": {
          "w": "17.5%",
          "p": 106
        },
        "FY25": {
          "w": "17.5%",
          "p": 160
        }
      }
    },
    {
      "name": "Other performance factors",
      "cls": "Other · non-financial",
      "cells": {
        "FY21": {
          "w": "30%",
          "p": 170
        },
        "FY22": {
          "w": "30%",
          "p": 114
        },
        "FY23": {
          "w": "30%",
          "p": 145
        },
        "FY24": {
          "w": "30%",
          "p": 180
        },
        "FY25": {
          "w": "30%",
          "p": 142
        }
      }
    },
    {
      "group": "Long-term incentive (LTIP) — 3-yr cycle, 50% rel. TSR + 50% ROIC (FY25 adds EPS growth)",
      "name": "Relative TSR (S&P 500)",
      "cls": "Shareholder return · market",
      "cells": {
        "FY21": {
          "w": "50%",
          "p": 0
        },
        "FY22": {
          "w": "50%",
          "p": 0
        },
        "FY23": {
          "w": "50%",
          "p": 0
        },
        "FY24": {
          "w": "50%",
          "p": "open"
        },
        "FY25": {
          "w": "25%",
          "p": "open"
        }
      },
      "benchmark": {
        "FY21": "S&P 500",
        "FY22": "S&P 500",
        "FY23": "S&P 500",
        "FY24": "S&P 500",
        "FY25": "S&P 500 Media & Entertainment Index"
      }
    },
    {
      "name": "Return on invested capital",
      "cls": "Profitability · financial",
      "cells": {
        "FY21": {
          "w": "50%",
          "p": 134
        },
        "FY22": {
          "w": "50%",
          "p": 147
        },
        "FY23": {
          "w": "50%",
          "p": 98
        },
        "FY24": {
          "w": "50%",
          "p": "open"
        },
        "FY25": {
          "w": "25%",
          "p": "open"
        }
      }
    },
    {
      "name": "Adjusted EPS growth",
      "cls": "Profitability · financial",
      "cells": {
        "FY25": {
          "w": "50%",
          "p": "open"
        }
      }
    }
  ],
  "aip_total": {
    "FY21": 191,
    "FY22": 97,
    "FY23": 113,
    "FY24": 144,
    "FY25": 145
  },
  "matrix_note": "Two CEOs span the window (Chapek FY21–22, Iger FY23–25), so the AIP series is not fully continuous. The AIP structure itself held constant: 35% segment operating income, 17.5% revenue, 17.5% free cash flow, 30% other factors. LTIP rows are shown in the grant-start year column: relative TSR paid 0% in all three completed cycles (Disney underperformed the S&amp;P 500 through the streaming-investment years), so the equity earned out on ROIC alone, completing at 66.9%, 73.4% and 48.9% of target. The FY25 grant restructured to 25% rel. TSR + 25% ROIC + 50% adjusted EPS growth and switched the TSR benchmark to a media-and-entertainment index.",
  "modifiers_gates": [],
  "modifiers_note": "",
  "pay_structure_caption": "Long-term award composition by grant year as % of target award. DIS dropped RSUs after FY22, moving to a PSU + options mix.",
  "pay_legend": "<div class=\"legend\"><span><span class=\"sw\" style=\"background:#534AB7\"></span>PSUs (TSR / ROIC / EPS)</span><span><span class=\"sw\" style=\"background:#7F77DD\"></span>RSUs</span><span><span class=\"sw\" style=\"background:#b4b2a9\"></span>Options</span></div>",
  "pay_structure": {
    "years": [
      "FY21",
      "FY22",
      "FY23",
      "FY24",
      "FY25"
    ],
    "series": [
      {
        "color": "#534AB7",
        "values": [
          50,
          50,
          60,
          60,
          60
        ]
      },
      {
        "color": "#7F77DD",
        "values": [
          25,
          25,
          0,
          0,
          0
        ]
      },
      {
        "color": "#b4b2a9",
        "values": [
          25,
          25,
          40,
          40,
          40
        ]
      }
    ]
  },
  "pay_structure_note": "FY21–22 grants split 50% PSU / 25% RSU / 25% options; from FY23 RSUs were dropped for a 60% PSU / 40% options mix. PSUs vest on relative TSR and ROIC (plus adjusted EPS growth from the FY25 grant). Regular CEO target award value rose to $30–35M for Iger. Excludes small ROIC-only special PSU grants and the additive annual cash bonus.",
  "realization": {
    "years": [
      {
        "fy": "FY21",
        "base": "$2.5M",
        "target": "$7.5M",
        "payout": 191,
        "realized": "$14.33M",
        "realized_pct_of_cap": 96,
        "target_pct_of_cap": 50,
        "at_or_above_target": true,
        "mult": "5.73×",
        "base_num": 2500000,
        "target_num": 7500000,
        "realized_num": 14330000
      },
      {
        "fy": "FY22",
        "base": "$2.5M",
        "target": "$7.5M",
        "payout": 97,
        "realized": "$7.29M",
        "realized_pct_of_cap": 49,
        "target_pct_of_cap": 50,
        "at_or_above_target": false,
        "mult": "2.92×",
        "base_num": 2500000,
        "target_num": 7500000,
        "realized_num": 7290000
      },
      {
        "fy": "FY23",
        "base": "$1.0M",
        "target": "$5.0M",
        "payout": 113,
        "realized": "$2.14M",
        "realized_pct_of_cap": 56,
        "target_pct_of_cap": 50,
        "at_or_above_target": true,
        "mult": "2.14×",
        "base_num": 1000000,
        "target_num": 5000000,
        "realized_num": 2140000
      },
      {
        "fy": "FY24",
        "base": "$1.0M",
        "target": "$5.0M",
        "payout": 144,
        "realized": "$7.22M",
        "realized_pct_of_cap": 72,
        "target_pct_of_cap": 50,
        "at_or_above_target": true,
        "mult": "7.22×",
        "base_num": 1000000,
        "target_num": 5000000,
        "realized_num": 7220000
      },
      {
        "fy": "FY25",
        "base": "$1.0M",
        "target": "$5.0M",
        "payout": 145,
        "realized": "$7.25M",
        "realized_pct_of_cap": 72,
        "target_pct_of_cap": 50,
        "at_or_above_target": true,
        "mult": "7.25×",
        "base_num": 1000000,
        "target_num": 5000000,
        "realized_num": 7250000
      }
    ],
    "note": "Targets differ by CEO: Chapek carried a $2.5M base / 300% target; Iger a $1.0M base / 500% target. Opportunity ceiling is 200% of target. The FY23 realized figure ($2.14M) is well below the others despite a 113% multiplier — Iger's first bonus was prorated for his partial (return) year — so it is not comparable to the full-year FY24/FY25 payouts. Bar fills shown as closeness-to-cap."
  },
  "classification_rule": "<b>Classification rule.</b> Metrics are bucketed by underlying measure, not verb. Segment operating income, free cash flow, ROIC and adjusted EPS growth &rarr; <b>profitability</b>. Revenue &rarr; <b>growth</b>. Relative TSR vs. the S&amp;P 500 &rarr; <b>shareholder return</b> (a weighted LTIP metric here, so it places the dot). The AIP “Other Performance Factors” (D&amp;I/talent, synergy, storytelling &amp; creativity) &rarr; <b>other</b>. AIP and LTIP weighted equally.",
  "provenance_html": "<div style=\"font-size:11.5px;color:#6b6860;background:#f4f2ec;border:1px solid #e5e2db;border-radius:3px;padding:10px 14px;line-height:1.5\"><b style=\"color:#1a1a2e\">CEO succession (March 18, 2026).</b> After the FY25 window, Robert Iger stepped down as CEO and became a senior adviser; <b style=\"color:#1a1a2e\">Josh D'Amaro</b> (former Chairman of Disney Experiences) was appointed CEO and to the Board (Item 5.02). At the same March 18 annual meeting, the say-on-pay vote drew a striking <b style=\"color:#1a1a2e\">~14% against</b> (1.09B for vs. 181.8M against) — the loudest pay dissent among large consumer names this cycle, consistent with the long-term plan's repeated zero TSR payouts. No special or off-cadence mega-grant was found in the research record (only minor ROIC-only PSU true-ups).</div>",
  "footer": "<b>Sources:</b> Verity / InsiderScore incentive-plan data (annual &amp; long-term), proxy statements, research, and SEC filings (8-K). Orientation classification is rules-based and auditable per the note above. AIP figures are CEO annual cash incentive across two CEOs (Chapek FY21–22, Iger FY23–25), not fully continuous. Three LTIP cycles complete (66.9%, 73.4%, 48.9%), each earning out on ROIC after relative TSR paid 0%; FY24–25 cycles open. Data current through run date. <b>Not investment advice.</b>",
  "takeaway": "The defining tension: Disney's leadership has been <b>paid solidly on operating results while the stock-based half of the plan repeatedly paid nothing</b> — relative TSR earned 0% in all three completed long-term cycles, so the equity vested only on ROIC. That gap (good fundamentals, market underperformance) is the story, and it now shows up as a loud <b>~14% say-on-pay dissent</b> at the March 2026 meeting. The plan itself is conservative and profitability-disciplined — segment operating income, free cash flow and ROIC dominate, with revenue a minor 17.5% and the FY25 grant tilting further toward <b>EPS growth and away from relative TSR</b>. The read: management is incentivized to <b>compound profit and capital efficiency</b>, and the board is quietly conceding the market-relative bar by cutting its weight. Watch the new CEO — Josh D'Amaro succeeded Iger in March 2026 — whose go-forward package will redefine the incentive against a still-skeptical tape."
}
```

<!-- FILE: scripts/verity_logo_b64.txt -->
```text
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
```
