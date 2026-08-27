---
name: 13f-peer-matrix
description: >
  Build an interactive 13F Peer Matrix dashboard showing fund-level % of portfolio
  positions across a user-defined SuperFund and ticker list. Use this skill whenever
  the user asks for "13F peer matrix", "run the 13F matrix", "13F dashboard",
  "fund ownership matrix", "who owns my watchlist", "13F peer group", "show me fund
  positioning", or any request to see 13F holdings across a custom fund peer group.
  Always use this skill for 13F matrix or peer group positioning requests.
---

# 13F Peer Matrix

Builds an interactive React dashboard showing Q-over-Q 13F fund positioning across a
user-specified SuperFund and ticker universe. Includes 8-quarter bar-chart sparklines and
share-change color coding.

Nothing in this skill is tied to a particular SuperFund, ticker list, fund, or client. Every
run-specific value comes from the user at run time. Do not add defaults, examples drawn from a
prior run, or any named account to this file or the template.

## Step 1 — Gather user inputs (REQUIRED GATE)

This skill has two required inputs. **Do not call any data tool, and do not guess or substitute
a default, until both are known.** If either is missing or ambiguous, stop and ask, then wait
for the answer.

1. **SuperFund** — the fund peer group.
   - If not specified, call `superfund_list(only_self=true)` and present the list so the user
     can pick. Do not default to the most recent, largest, or previously used SF.
   - Record both the **SFID** and the SF's **name**. Once the user has defined the SF, use its
     real name on the dashboard — that is the one run-specific label that belongs there.

2. **Ticker universe** — the matrix rows.
   - Their primary watchlist → call `get_watchlist_tickers()`
   - A specific named watchlist, or a manual list → use as provided
   - A SuperFund's holdings as the universe → pull from SF holdings
   - If the user says only "my watchlist" and more than one exists, ask which.

Proceed without asking only when the user supplied **both** upfront (an SFID or SF name plus an
explicit ticker list or watchlist reference).

### Optional input (ask only if the user raises it; otherwise use the default)

- **Fund columns**: by default every fund in the SF gets a column. The user may instead want
  SF-level aggregates across *all* funds in the SF while restricting the individual fund columns
  to a named subset of `rptcik`s. Honor that split: aggregates stay full-SF, columns are
  filtered. Make the split visible in the header so the two blocks aren't read as the same fund
  set.

## Step 2 — Resolve the display quarter

```
superfund_overview(sfid=<SFID>)                → totals for the default quarter
superfund_overview(sfid=<SFID>, quarter=<Q>)   → totals for a specific quarter
```

The overview returns **no quarter field**, so probe candidate quarters rather than reading one
off the response. **Always use the most recent quarter that has holdings data — never fall back
to an earlier quarter because some funds haven't filed yet.**

- A short `numreported` relative to the SF's fund count is **expected and not a reason to fall
  back.** 13Fs are due 45 days after quarter end and funds file across the whole window, so the
  latest quarter is routinely partial. Build it anyway.
- **Exclude non-filers rather than changing quarter.** Funds with no filing for the display
  quarter get no column — see Step 6. The matrix shows who has filed, not a stale quarter that
  happens to be complete.
- State the coverage in the header so a partial quarter is never mistaken for a full one:
  `<numreported> of <SF fund count> funds filed`.
- The **only** valid reason to step back a quarter is that `superfund_holdings` returns nothing
  aggregated for it at all — that happens before the filing deadline passes, when no data exists
  yet rather than merely being incomplete. Confirm holdings are genuinely empty before falling
  back, and tell the user why.
- Calling with **no** `quarter` returns a rolling blend — each fund's latest filing, mixing
  quarters. Never build the matrix from it; always pass an explicit quarter.

Resolve this at run time; never hardcode a quarter.

Derive the prior quarter for share-change comparison: Q1 → Q4 of prior year, Q2 → Q1, Q3 → Q2,
Q4 → Q3.

**Known quirk:** the `tickerlist` filter on `superfund_holdings` works only for the most recent
quarter. For any historical quarter, omit `tickerlist`, page with `limit`, and filter locally.
Results are sorted by position value descending, so start with a generous `limit` and confirm
every requested ticker actually appeared before using the result.

## Step 3 — Pull SF holdings for the display quarter

```
superfund_holdings(sfid=<SFID>, quarter=<current>, include_details=true)
```

Split the tickers across several calls if the list is long.

**Equity only**: skip rows where `assettype` is in {put, call, warrant, right, note, debt,
other}. ETFs are included — they are legitimate watchlist rows.

Parse each result:
- Rows where `fund_name == "Superfund"` → SF aggregate per ticker: `numfunds`, `shares`,
  `value`, `pctoutstanding`. These span **every** fund in the SF, independent of how many fund
  columns are displayed.
- Rows where `fund_rptcik` is set → an individual fund position: `fund_name`, `pctportfolio`,
  `shares`, `prevshares`.

Each detail row carries both `shares` and `prevshares`, so this one pull supplies the current
quarter and the prior-quarter comparison for Step 4 — no separate prior-quarter detail pull is
needed.

## Step 4 — Compute share change per fund per ticker

Compare `shares` vs `prevshares` on each fund × ticker row:

| Condition | Type | Display |
|---|---|---|
| In current, not in prior | NEW | Green fill + green text |
| In prior, not in current | LIQUIDATED | Red fill + red "0.0%" |
| Current shares > prior by >0.1% | INCREASED | No fill + green text |
| Current shares < prior by >0.1% | DECREASED | No fill + red text |
| Within 0.1% | UNCHANGED | No fill + black text |

A position can be real but round to 0.0% of portfolio. Keep full precision in the payload and
let the template render sub-0.1% values as `<0.1%`; do not pre-round, or those cells render as
a colored fill with no number in it.

## Step 5 — Pull 8-quarter sparkline data

For each of the 7 quarters before the display quarter:

```
superfund_holdings(sfid=<SFID>, quarter=<Q>, include_details=false)
```

Take the Superfund-level equity `shares` per ticker → an 8-element array
`[oldest, ..., current]`, in thousands, `null` for quarters with no position.

**Build every bar from that quarter's own query.** Do not derive a bar from the next quarter's
`prevshares` field, even though it looks like a free extra quarter. The two can disagree: when a
fund files or amends late, the quarter's own aggregate is restated to include it while the next
quarter's comparison baseline is not. Deriving alternate bars from `prevshares` mixes two bases
in one sparkline and can put a step in the chart that isn't real.

If the two disagree for a ticker, prefer the quarter's own record — it is internally consistent
across `shares`, `value`, and `pctoutstanding`, which can be checked against each other. Then
tell the user, because the SF-level QoQ percentage in the current quarter's record will disagree
in sign or size with what the sparkline shows.

## Step 6 — Build the data payload

```javascript
DATA = {
  funds: [ /* fund column labels, in display order */ ],
  rows: [
    {
      ticker, name, sector, industry, mcap,
      sfHolders, sfShares, sfValue, sfPctOut,
      funds: {
        "<fund label>": { pct: <% of portfolio>, pctOut: <% of shares outstanding owned>, chg: "INCREASED" | "DECREASED" | "NEW" | "LIQUIDATED" | "UNCHANGED" },
        ...
      }
    },
    ...
  ]
}

SPARKDATA = {
  quarters: [ /* 8 quarter labels, oldest → current */ ],
  data: { "<TICKER>": [ /* 8 values in thousands, null where absent */ ], ... }
}
```

- `pct` — % of portfolio at full precision (e.g. `16.6`, not `0.166`); the template rounds
- `pctOut` — that fund's holding as a % of the company's shares outstanding, same full-precision
  convention (e.g. `2.45`, not `0.0245`). The dashboard has a **% Port / % Out toggle** on the
  fund columns; `pct` is the default view and `pctOut` powers the flip.

  The holdings rows don't carry a shares-outstanding figure, so derive it from the SF aggregate
  row for that ticker, which has both `shares` and `pctoutstanding`:

  ```
  sharesOutstanding = <SF aggregate raw shares> / (<SF raw pctoutstanding> / 100)
  pctOut            = <fund raw shares> / sharesOutstanding * 100
  ```

  Use the **raw** values from the API response, not the scaled `sfShares` / `sfPctOut` payload
  fields. Set `pctOut: null` when the SF row's `pctoutstanding` is missing or zero — some ETFs
  and foreign issuers have no share count — and never fall back to `pct`, which would silently
  show portfolio weights in the % Out view.
- `sfShares` — thousands (raw shares ÷ 1,000)
- `sfValue` — $M (raw value ÷ 1,000,000)
- `sfPctOut` — decimal (raw `pctoutstanding` ÷ 100)
- Omit a fund key entirely when that fund has no current and no prior position
- **Drop the fund column entirely** when the fund has no filing for the display quarter. A
  non-filer is absent, not flat — leaving the column in renders it as a wall of LIQUIDATED or
  empty cells and reads as a fund that sold everything. `funds` should list only funds that
  filed for the display quarter.

Company names come from `get_company_info(tickerlist=[...])`; the holdings rows don't carry them.

Sanity check before building: the sparkline's last value must equal `sfShares` for that ticker,
and `sfHolders` will normally exceed the number of fund columns showing a position — the
aggregates cover the whole SF, not just the displayed columns.

## Step 7 — Build and present the dashboard

Read the template:
```
view dashboard_template.jsx
```

The template contains **no** hardcoded SuperFund name, SFID, date, or quarter — every
run-specific string is a placeholder. Replace all eleven:

| Placeholder | Value |
|---|---|
| `__IS_LOGO__` | `IS_LOGO_B64` from assets/logos.json |
| `__VD_LOGO__` | `VD_LOGO_B64` from assets/logos.json |
| `__WATCHLIST_DATA__` | `JSON.stringify(DATA)` — raw JS object literal, no surrounding quotes |
| `__SPARK_DATA__` | `JSON.stringify(SPARKDATA)` — same |
| `__SF_NAME__` | SuperFund name from Step 1 |
| `__SFID__` | SFID from Step 1 |
| `__QUARTER__` | Display quarter from Step 2 |
| `__PRIOR_QUARTER__` | Prior quarter from Step 2 |
| `__GEN_DATE__` | Today's date |
| `__SPARK_RANGE__` | Oldest–current sparkline quarters, en dash separated |
| `__XLSX_FILENAME__` | Export filename — slugify the SF name; no spaces, apostrophes, or slashes |

If the fund columns were filtered to an rptcik subset (Step 1), note the full fund count
alongside the aggregates header so the reader knows the two blocks cover different fund sets.

**Before saving, verify — these outputs go to clients:**

1. No `__` token survives anywhere in the file.
2. `grep` the output for the SF name, SFID, and quarter labels of any *previous* run. A hit
   means a placeholder was missed and someone else's identifiers would ship on the deliverable.

Save to: `/mnt/user-data/outputs/13F_Peer_Matrix_<SF name slug>_<quarter>.jsx`

Then call `present_files` with that path.

## Client-facing note

This output is designed to be sent to clients. It must carry no user IDs, account numbers,
account-manager or salesperson fields, or client names — only public 13F data, the SF name and
SFID for the run at hand, and the VerityData contact link in the template footer. Never write
account or user identifiers into the dashboard, and never carry a prior run's SF into a new one.

## Assets

Logos: `assets/logos.json`
Keys: `IS_LOGO_B64`, `VD_LOGO_B64`

## Design system (do not modify in template)

- Font: DM Sans everywhere
- Colors: orange=#E84C2A, blue=#0067B1, green=#0d7a3f, red=#c41e2a, text=#1a1d23, muted=#5f6775, card=#f8f9fb, border=#e2e4e9
- Row height: 22px
- Fund col width: 88px, horizontal text headers
- Sparklines: 8-bar SVG, IS blue (#3a6cc4), faint stub for null quarters
- Sticky Ticker + Company columns, sticky header, ghost scrollbar at top synced to table
- Export XLSX button with matching color coding baked in
