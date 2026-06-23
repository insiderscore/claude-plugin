---
name: thirteenf-flow-map
description: Build a branded VerityData "13F flow map" — a four-quadrant bubble scatterplot showing institutional accumulation vs change in holder breadth across a SET of stocks for one quarter. Each stock is a bubble positioned by QoQ % change in institutional shares (x) and net new holders, initiations minus liquidations (y), sized by total 13F value, colored by quadrant (conviction buy, rotation in, conviction sell, concentration). Use whenever a user wants institutional flows across many names at once — trigger on "flow map", "13F flow map", "accumulation vs sponsorship", "quadrant chart of [index/sector/watchlist/fund book]", "plot institutional flows for [list]", "map my watchlist", or a bare index/universe name after a prior flow map ("now do the S&P 500", "do it for semis"). This is the cross-sectional many-name view; use insider-sell-grid or incentive-tearsheet for single-name deep dives. Produces an SVG (optional PNG) with the VerityData logo. Requires the Verity MCP connection.
---

# 13F Flow Map

Build a presentation-quality, VerityData-branded quadrant scatterplot of institutional flows across a set of stocks for a single quarter. This is **landscape/cross-sectional** work — the whole universe in one picture — not a single-name deep dive.

## What it shows

- **X axis** — QoQ % change in institutional equity shares held (`(eq_now − eq_prev) / eq_prev`)
- **Y axis** — net new holders = new initiations − liquidations
- **Bubble area** — total 13F value held by institutions (log-scaled)
- **Color / quadrant:**

| Quadrant | Sign (x, y) | Color | Meaning |
|---|---|---|---|
| Conviction buy | (+, +) | green | buying · holders adding |
| Rotation in | (−, +) | blue | net selling but new funds initiating |
| Conviction sell | (−, −) | red | selling · holders dropping |
| Concentration | (+, −) | amber | buying into a shrinking holder base |

Names whose % change blows out the x-axis (e.g. a reclassification spike) can be rendered as **off-scale callouts** pinned to the right edge with an arrow, so they don't compress everyone else.

## When to use

Use whenever the user wants institutional flows across **many names at once**: an index (NDX 100, S&P 500), a sector or sub-industry (semis, software), their watchlist, or a fund's entire book. If they want a single ticker analyzed in depth, this is the wrong skill — point to the sell-grid or tear-sheet skills instead. The trigger can be implicit: after one flow map, "now do the S&P 100" or "what about energy" means run it again on the new universe.

## Workflow

Four steps: resolve the universe → pull Verity stats for each name → assemble the input JSON → render.

### Step 1 — Resolve the universe to a ticker list

Depending on what the user asked for:

- **Watchlist / "my companies"** → `Verity:get_watchlist_tickers`
- **A fund's book** → `Verity:get_fund_holdings` (name or rptcik), then take the tickers
- **A sector / sub-industry** → use `Verity:get_industry_tickers` if available, or the user's provided list
- **An index** (NDX 100, S&P 500, Dow) → these are not a Verity endpoint; get the current constituent list via `web_search` + `web_fetch` (e.g. the Wikipedia constituents table), then sanity-check membership. Note index quirks: e.g. several mega-caps are **not** in the Nasdaq-100 (financials like JPM/V, and names not listed on Nasdaq).

Confirm the resolved count back to the user if it's ambiguous (e.g. "Found 100 NDX names — running the map now").

### Step 2 — Pull Q-over-Q fund stats for each name

For every ticker, call `Verity:company_fund_stats` with the target `quarter` (default to the most recent completed quarter; the user may specify like `Q1'26`). Call them in parallel batches — these are independent reads. Each response gives you the fields you need:

- `eq_now` — institutional equity shares held this quarter
- `eq_prev` — institutional equity shares held prior quarter
- `new` — number of funds initiating a position
- `liq` — number of funds fully liquidating
- `value_m` — total 13F value held, in **millions**

(Field names in the raw response may differ slightly; map them to these. The % change is computed from `eq_now`/`eq_prev`; net new holders from `new`/`liq`.)

If a name has essentially no institutional coverage (e.g. a single holder), drop it and note the exclusion.

### Step 3 — Assemble the input JSON

Write a JSON file matching the schema the renderer expects:

```json
{
  "title": "Q1'26 13F flow map — Nasdaq 100",
  "subtitle": "All NDX constituents plotted. Bubble area scales with total 13F value held by institutions.",
  "rows": [
    {"ticker":"AAPL","eq_now":9319994802,"eq_prev":9481008549,"new":198,"liq":104,"value_m":2365321}
  ],
  "offscale": [
    {"ticker":"TSLA","eq_now":2278755602,"eq_prev":1623147376,"new":185,"liq":274,"value_m":899470}
  ],
  "labels": "auto",
  "x_range": null,
  "y_range": null,
  "logo": "dark"
}
```

Field notes:

- **`rows`** (required) — one object per name. Only `ticker`, `eq_now`, `eq_prev`, `new`, `liq`, `value_m` are needed.
- **`offscale`** (optional) — names to pin to the right edge as callouts instead of plotting in-axis. Use this for any name whose % change is so large it would flatten the rest of the cloud (a good rule of thumb: more than ~2.5× the next most extreme value). Same field schema as a row.
- **`title` / `subtitle`** — keep the title in the `Q?'YY 13F flow map — <universe>` form.
- **`labels`** — `"auto"` (default; labels the axis extremes plus the biggest bubbles, ~30 names, with automatic collision avoidance), or `"all"` (label every name — only legible for ≤25 names), or an explicit list like `["AAPL","MSFT","NVDA"]` to force a specific set.
- **`label_overrides`** (optional) — force a specific label's position, e.g. `{"AAPL": [22, 4, "start"]}` where the array is `[dx, dy, anchor]` in pixel offsets from the bubble center (anchor is optional: `"start"`/`"end"`/`"mid"`). Use this only for a hero/marketing asset where you want a particular name placed just so; auto placement handles the general case.
- **`x_range` / `y_range`** — `null` for auto. Override with `[min,max]` only if you want to crop or zoom; off-scale names should be moved to `offscale` rather than handled by widening the range.
- **`logo`** — `"dark"` for the standard light chart background (default). `"white"` only if you later restyle the chart onto a dark background.

For a large universe (50+ names), prefer `"auto"` labels. Labeling all 100 names of an index is illegible — the population shape plus ~30 labeled extremes is the right call, and that's what `"auto"` delivers.

### Step 4 — Render

```bash
python3 /mnt/skills/user/thirteenf-flow-map/scripts/build_flow_map.py \
  --data /home/claude/<universe>_input.json \
  --out /home/claude/<universe>_flow_map.svg \
  --png /home/claude/<universe>_flow_map.png
```

The script prints quadrant counts to stdout. It writes an SVG; pass `--png` to also rasterize (needs `cairosvg`; `pip install cairosvg --break-system-packages` if missing). Default PNG width is 1800px; override with `--png-width`.

### Step 5 — Deliver and analyze

1. Copy the final SVG and PNG to `/mnt/user-data/outputs/` and present them with `present_files`.
2. Optionally render the SVG inline with the visualizer (`show_widget`) so the user sees it in chat — read the SVG file and pass its contents.
3. Write a short, substantive read of the map. Useful angles, each anchored to something visible:
   - **Population tilt** — which quadrant holds the plurality? (e.g. "40 of 100 names sit in rotation in")
   - **Cluster themes** — does a sector cluster in one quadrant? (e.g. semis stacking in the top-left)
   - **Axis extremes** — the biggest accumulation (x) and biggest sponsorship gains/losses (y), called out by name
   - **Single-name outliers** — anything alone in a corner, or any off-scale callout (and *why* it's off-scale — a reclassification spike is not the same as active accumulation)

## Design / brand notes

- The chart renders on a **light background** with VerityData quadrant colors (green/blue/red/amber) and the **VerityData logo** embedded bottom-right.
- **The renderer is fully self-contained and portable.** Both VerityData logos are embedded directly in `scripts/verity_logos.py` as base64, so `build_flow_map.py` needs no asset files and no PIL/Pillow at runtime — only the Python standard library (plus optional `cairosvg` if you want a PNG). The `assets/` directory holds the original trimmed PNGs for reference, but the script does not depend on them; if `verity_logos.py` is ever missing, the script falls back to reading `assets/`.
- To use the skill, only two files are strictly required: `scripts/build_flow_map.py` and `scripts/verity_logos.py`. Keep them together.
- `logo` defaults to `"dark"` (the navy-text mark, for the light chart background). `"white"` is available for restyling onto a dark background.
- Fonts use a system sans stack so the SVG renders identically with or without cairosvg.
- The renderer is data-driven: ranges, ticks, bubble scale, label placement, and quadrant counts are all computed from the input. You should not need to hand-tune positions — if labels look crowded, switch `labels` to `"auto"` or a curated list, or nudge a single name with `label_overrides`, rather than editing the script.

## Common pitfalls

- **Don't widen the axis to fit one blowout name** — move it to `offscale` instead, or the whole cloud compresses into a corner.
- **`value_m` is in millions.** A $2.3T holding is `2300000`, not `2300000000000`.
- **Index membership drifts and has surprises** — always pull a current constituent list rather than relying on memory, and watch for names that aren't actually in the index (exchange-listing quirks).
- **A reclassification or index-rebalance spike** in shares is not active accumulation — flag it in the analysis so the reader doesn't misread an off-scale callout as conviction.
