---
name: discovery-dashboard
description: Build the VerityData Idea Discovery Dashboard (VIDD) — an interactive React artifact showcasing VerityData research briefs through six curated Spotlight views for portfolio managers, analysts, and traders. Use this skill when the user asks for idea generation, what's important, what's new, what should I be paying attention to, what are insiders telling us, scan the market, what's actionable, show me insider themes, give me a rundown, what did I miss, morning briefing, or any broad request to surface insider sentiment patterns and research across the market. Also trigger for explicit requests like VIDD dashboard, research spotlight, sector themes, P2P themes, behavioral themes, or requests to see VerityData research briefs organized into thematic views. This replaces the verity-react-dashboard and verity-command-center skills for broad market-scanning views. Requires the VerityData MCP connection.
---

# VerityData Idea Discovery Dashboard (VIDD)

Build a React (.jsx) artifact that showcases VerityData research briefs through six curated Spotlight views. Briefs are the atomic unit — every tile, theme, and interaction traces back to a published research brief.

## Prerequisites

Read `/mnt/skills/public/frontend-design/SKILL.md` first for general frontend design principles. This skill layers VIDD-specific architecture on top.

## Architecture Overview

**Landing Page**: Mosaic grid of 6 equal Spotlight tiles with preview content. Click any tile to dive in.

**Six Spotlights**:
1. **Positive Sentiment / Valuation Signals** — Buying + Buyback briefs. Actionable section on top, Informational below. 7/30/90d lookback toggle.
2. **Negative Sentiment / Valuation Signals** — Selling + ATM briefs. Same Actionable/Informational split. 7/30/90d toggle.
3. **Unusual Compensation** — Comp briefs. 7/30/90d toggle. **No Actionable/Informational tab split** — all Comp briefs are Informational, so show a flat list. Description: "Off-cadence, stock-price targeted, and unusual executive grants/awards"
4. **Sector Themes** — Curated. Always 120d. Description: "Curated insider alignment patterns at the sector level". Theme boxes with narrative + ticker badges + theme prompt. Only sectors where one direction is dominant (2x+ ratio vs opposite).
5. **Behavioral Themes** — Curated. Always 120d. Theme boxes with narrative + ticker badges + theme prompt. Themes: CEO Buying, Multi-Insider Activity, Buying on Weakness, Sentiment Reversals, Selling on Strength, Notable 10b5-1 Plan Activity.
6. **P2P Themes** — Curated. Always 120d. Description: "Curated alignment or conflict among direct business peers". Direct peers only. Divergent (opposite signals) and aligned (same direction) themes. Each pair gets a narrative + theme prompt.

## Data Architecture

### MCP Calls — Exactly Two

```
get_research(begin_date=120_DAYS_AGO, limit=1000, sentiment="Actionable")
get_research(begin_date=120_DAYS_AGO, limit=1000, sentiment="Informational")
```

**Why 120 days**: Quarters are ~89-92 days; 90d risks cutting briefs that fell just outside the window due to calendar drift or earnings window lag. 120d provides a full quarter plus buffer.

**Why limit=1000**: At current publishing volume (~5 briefs/day), 120 days produces ~600 total briefs. 1000 provides headroom with no truncation risk. The tool returns however many exist — no pagination needed.

**No Comments**: Only Actionable and Informational briefs. Comments are excluded.

### Slim Brief Format

Convert each full brief to a slim object for embedding in the artifact:

```javascript
{
  t: ticker, m: mcap, se: sector, d: publish_date (YYYY-MM-DD),
  sn: sentiment, tp: type, ti: title (truncated 120 chars),
  tk: takeaway (truncated 325 chars), r: rating
}
```

**Do NOT include the `l` (link) field** — all interactions use inline prompt boxes, not website URLs. Omitting links saves significant space.

**Takeaway truncation**: Default to 325 chars. If the final artifact exceeds 450KB, reduce to 250 or 200 chars. Target ~400KB for the assembled artifact.

### Rating Fallback Rule

Some briefs have an empty `type` field (e.g., ANRO, INTU — briefs about plan cancellations or media statements that don't fit standard categories). Apply this fallback:

- If `type` is empty and `rating > 0` → set `type = "Buying"` (appears in Positive Sentiment)
- If `type` is empty and `rating < 0` → set `type = "Selling"` (appears in Negative Sentiment)
- If `type` is empty and `rating == 0` → remains unclassified (excluded from data spotlights)

### Type Classification for Tiles

| Tile | Types Included |
|------|---------------|
| Positive Sentiment | Buying, Buyback |
| Negative Sentiment | Selling, ATM |
| Unusual Compensation | Comp |

All three tiles partition the corpus with no overlap. Verify: Positive + Negative + Comp + Unclassified = Total.

## Theme Curation

### Narrative Requirements

All theme narratives must include **specific detail from the actual briefs** — insider names/titles, dollar amounts, price levels, plan mechanics, subsector breakdowns. Never write generic one-liners. The user is a 20+ year veteran of insider transaction research; narratives should read like a research summary, not a label. Target 200-500 characters for sector/behavioral themes, 150-260 characters for P2P themes.

**Never include brief counts** in narratives. Don't say "23 briefs" — say "broad-based selling across E&P, services, and drilling subsectors."

### Theme Prompts

Every theme (sector, behavioral, and P2P) must include a `prompt` field — a ready-made prompt string that asks for the right VerityData tools and names the key tickers for that theme. These prompts are surfaced to the user via the "Explore This Theme" button. Write them as if the user is pasting them into a Claude chat.

### Sector Themes (Tile 4)

Scan the 120-day corpus and group briefs by sector and direction:
- **Bullish**: types in [Buying, Buyback]
- **Bearish**: types in [Selling, ATM]

Only include a sector if the dominant direction has **2x+ the count** of the opposite direction AND at least 5 briefs. This ensures genuine sector-level alignment, not noise from balanced activity.

Present as theme boxes with narrative + ticker badges + "Explore This Theme" prompt button (not flat brief lists).

### Behavioral Themes (Tile 5)

Six fixed behavioral categories. For each, scan the corpus for briefs matching the pattern:

1. **CEO Buying** — Briefs where the CEO made a personal purchase
2. **Multi-Insider Activity** — Briefs mentioning 3+ insiders acting in concert
3. **Buying on Weakness** — Briefs where insiders bought as shares declined
4. **Sentiment Reversals** — Briefs describing a flip from selling to buying or vice versa
5. **Selling on Strength** — Briefs where insiders sold at/near highs
6. **Notable 10b5-1 Plan Activity** — Briefs highlighting price-triggered plans, plan acceleration, or plan termination

Classify by reading the brief title and takeaway text for pattern-matching keywords. For behavioral themes, only include **Actionable** briefs to keep the signal strong.

### P2P Themes (Tile 6)

Three-layer peer identification:

**Layer 1: Brief cross-references (highest confidence)**
Scan ALL full brief body text for `(TICKER)` patterns. When a brief explicitly mentions a peer ticker in parentheses, the analysts already made the connection. Extract these pairs.

**Layer 2: Claude's peer knowledge (medium confidence)**
For tickers without explicit cross-references, apply knowledge of well-known competitive pairs (HAS/MAT, CVX/COP, DAL/UAL, etc.).

**Layer 3: Quality filters (mandatory for both layers)**
- At least one ticker must have an Actionable brief
- If divergent: signals must genuinely diverge (not "one is negative, the other is not unusual")
- If aligned: both must have meaningfully strong signals
- Drop any pairing that requires qualifiers like "not currently unusual"
- Drop BAC/JPM-type pairings where one side is neutral

Present as theme boxes. Divergent themes in orange, bearish alignment in red, bullish alignment in green. Target: ~4 divergent, ~3 aligned bullish, ~3 aligned bearish. Deduplicate tickers across pairs (don't show the same ticker in multiple pairings).

## Design System

### Colors
```javascript
const V = {
  orange: "#E84C2A",  // Verity brand accent
  blue: "#0067B1",    // InsiderScore brand
  bg: "#ffffff",       // White background
  card: "#f8f9fb",
  green: "#0d7a3f",   // Buys, bullish
  red: "#c41e2a",     // Sells, bearish
  text: "#1a1d23",
  muted: "#5f6775",
  dim: "#9ca3af",
  border: "#e2e4e9",
  purple: "#6a1b9a",  // Compensation
};
```

### Typography
- **Headlines**: DM Serif Display (Google Fonts)
- **Body**: DM Sans
- **Tickers/Dates**: JetBrains Mono

Import via: `https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&family=JetBrains+Mono:wght@400;600;700&display=swap`

### Header
Warm gradient: `linear-gradient(135deg, #faf9f7 0%, #f5f0eb 40%, #E84C2A08 100%)`
- Left: VerityData logo + vertical divider + "Idea Discovery" title + "Research Spotlights" subtitle
- Right: "← All Spotlights" nav button (only when inside a spotlight) + Feedback mailto link + "Generated on [month] [day], [year]" date

**Date format**: Always "Generated on April 6, 2026" style — human-readable month name, no ISO format, no zero-padded day.

**Feedback link**: `mailto:bsilverman@verityplatform.com` — present in BOTH the header and the footer.

### Logos

Logos are bundled with this skill as pre-processed base64 PNG data. **Never ask the user to upload logos.**

**Bundled asset**: `assets/logos.json` (located relative to this SKILL.md file)

The file contains a JSON object with two keys:
- `VD_LOGO_B64` — VerityData logo, transparent background, original size (~237×62)
- `IS_LOGO_B64` — InsiderScore logo, transparent background, resized to half (~257×50)

Both logos have already had white backgrounds stripped and the IS logo has been resized for optimal file size. No image processing is needed at build time.

**How to load**: Read the JSON file and embed as `data:image/png;base64,...` constants in the artifact:

```python
import json

# Determine skill base path
skill_base = "/mnt/skills/user/verity-idea-discovery-dashboard"
with open(f"{skill_base}/assets/logos.json") as f:
    logos = json.load(f)

vd_b64 = logos["VD_LOGO_B64"]  # Use as: data:image/png;base64,{vd_b64}
is_b64 = logos["IS_LOGO_B64"]  # Use as: data:image/png;base64,{is_b64}
```

**Fallback order** (if the bundled file is missing or unreadable):
1. Check `/mnt/user-data/uploads/VD_Logo.png` and `/mnt/user-data/uploads/IS_Logo.png`
2. Check `/mnt/project/VD_Logo.png` and `/mnt/project/IS_Logo.png`
3. If found, strip white backgrounds and resize IS logo to half before base64 encoding:
```python
from PIL import Image
img = Image.open(path).convert("RGBA")
data = list(img.getdata())
new_data = [(r,g,b,0) if r>240 and g>240 and b>240 else (r,g,b,a) for r,g,b,a in data]
img.putdata(new_data)
```
4. If none found, proceed with SVG text fallbacks rather than blocking the build.

### Tiles
- Hover: `translateY(-4px)` with `box-shadow: 0 12px 32px rgba(0,0,0,0.08)`
- Top accent bar: 3px gradient in the spotlight's color
- Curated tiles show "120d Curated" badge and theme name previews
- Data tiles show 3 most recent briefs as preview
- Border radius: 12px

### Brief Rows
- Grid layout: ticker (64px) | title | badge | date
- Hover row background highlight
- Click to expand takeaway with accent-colored left border (3px)
- Expanded rows show "Full Brief" and "Deep Dive" PromptButton components
- Buttons toggle inline PromptBox on click (see Interactions section)

### Theme Boxes
- Left border in theme color (4px)
- Border radius: 0 10px 10px 0
- Narrative text (200-500 chars with specific detail) + ticker badges + "Explore This Theme" PromptButton
- Hover: subtle box-shadow lift
- Ticker badges are clickable — clicking one opens a PromptBox inline within the same ThemeBox
- Only one ticker badge active at a time per ThemeBox (activeTicker state)
- Active badge highlights in green

## Interactions — Inline Prompt Boxes

**CRITICAL: Do NOT use `sendPrompt()` or `navigator.clipboard`.** Both fail unreliably in the artifact iframe. `sendPrompt` doesn't execute in file preview mode. `navigator.clipboard.writeText()` may succeed on the first click but silently fail on subsequent clicks due to iframe permission scoping — the user ends up pasting stale content without knowing.

Instead, all interactions use an **inline PromptBox** pattern:

### PromptBox Component

A self-contained prompt display that appears inline below the clicked element:
- Bordered card with the theme color accent
- Header: "Select all and paste into chat" label + × close button
- Body: read-only `<input>` field containing the prompt text, auto-focused and auto-selected on open
- Footer: "Copy" button that uses `document.execCommand("copy")` after `.select()`
- After successful copy: button shows "Copied!" for 1.2s, then auto-closes the box

**Close triggers** (all must work):
- × button click
- "Copy" button (auto-closes after 1.2s delay)
- Clicking the same toggle that opened it (PromptButton toggles, TickerBadge toggles)
- Click outside the box (via `useEffect` with `mousedown` listener on `document`)

**IMPORTANT**: The click-outside handler MUST use `useEffect`, NOT `useCallback`. `useCallback` only memoizes a function — it does not execute the side effect. This was a validated bug in an earlier version.

```jsx
// CORRECT — runs the effect, attaches/detaches listener
useEffect(() => {
  const handleClickOutside = (e) => {
    if (boxRef.current && !boxRef.current.contains(e.target)) onClose();
  };
  document.addEventListener("mousedown", handleClickOutside);
  return () => document.removeEventListener("mousedown", handleClickOutside);
}, [onClose]);

// WRONG — never executes, listener never attached
useCallback(() => { /* ... */ }, [onClose]);
```

### PromptButton Component

A styled button that toggles a PromptBox on click:
- Shows a clipboard icon + label (e.g., "Full Brief", "Deep Dive", "Explore This Theme")
- When active (box open): filled background in theme color + white text
- When inactive: transparent background + theme color border/text
- Clicking toggles `open` state; PromptBox renders below when open

### TickerBadge Component (in ThemeBox context)

Ticker badges inside ThemeBox are interactive:
- Clicking a badge sets `activeTicker` state on the parent ThemeBox
- The ThemeBox renders a PromptBox below the badge row when `activeTicker` is set
- Clicking the same badge again closes it (toggle behavior)
- Clicking a different badge switches to that ticker's prompt
- Active badge gets green border + green fill
- Prompt text: "Pull up the latest VerityData research briefs for {TICKER}"

### PromptHint Component

A subtle instructional bar shown at the top of each spotlight view (not on the landing page):
- Orange-tinted background with clipboard icon
- Text: "Click any ticker or button to reveal a ready-made prompt. Copy it and paste into the chat to explore further."

### Prompt Text Templates

1. **Ticker badge** (ThemeBox): `"Pull up the latest VerityData research briefs for " + ticker`
2. **Full Brief** (BriefRow): `"Show me the full VerityData research brief for " + ticker + " published on " + date`
3. **Deep Dive** (BriefRow): `"Perform a deep dive insider sentiment analysis on " + ticker + " using all available VerityData tools"`
4. **Explore This Theme** (ThemeBox): Custom prompt per theme targeting the right tickers and VerityData tools

### Required React Imports

```javascript
import { useState, useMemo, useCallback, useRef } from "react";
```

`useRef` is required for the PromptBox input element (auto-select) and the click-outside detection. `useCallback` is used for the `selectAll` handler memoization.

## Disclaimer Popup

Footer contains a "Disclaimer" link that opens a modal overlay:
- Dimmed background overlay (rgba(0,0,0,0.45))
- Centered card with close button (×), border-radius 14px, box-shadow
- Shortened legal text with AI-curated disclosure and Morningstar attribution

## Footer

```
Data sourced from [VD logo] / [IS logo] · Some content is AI-curated · Disclaimer · Feedback
```

Right side: `Generated on [month] [day], [year]` in JetBrains Mono.

"Disclaimer" opens the popup. "Feedback" is a mailto link to bsilverman@verityplatform.com.

## Key Rules

- **No brief counts** anywhere in the dashboard — not on tiles, not in narratives
- **No "Claude-curated"** — always say "Curated"
- **Tile descriptions describe the signal**, not briefs (e.g., "Positive sentiment and valuation signaling indicated by insider behavior and/or buybacks")
- **Narratives include specific detail** — insider titles, dollar amounts, price targets, plan mechanics, subsector breakdowns. Not generic one-liners.
- **Every theme has a prompt** — a ready-made prompt string surfaced via "Explore This Theme" button
- **Sector Themes**: grouped theme boxes, not flat brief lists. Only narrative-worthy sectors.
- **White background** — never use dark/black backgrounds for VIDD
- **Actionable above Informational** in data spotlight sections (Positive and Negative tiles only)
- **Comp tile has NO Actionable/Informational split** — all Comp briefs are Informational, so show a flat list with 7/30/90d toggle only
- **No sendPrompt, no navigator.clipboard** — use inline PromptBox pattern exclusively

## Critical Build Rules

### Unicode and Special Characters

**NEVER build the JSX artifact as a Python string.** Python raw strings (`r'''...'''`) will produce literal `\u00b7` text in the output instead of actual `·` characters. This is a known, recurring issue.

Instead, write the JSX file directly using `create_file` or write it section-by-section using bash heredocs. If you must use Python to assemble the file (e.g., to embed the data blob), write the JSX template portions as separate files first, then concatenate them with the data. Any special characters (em dashes, middle dots, arrows, multiplication signs, copyright symbols, checkmarks) must be actual UTF-8 characters in the output file, never escape sequences.

**Verification step**: After building the artifact, `grep` for `\\u` in the output file. If any escaped unicode sequences are found, fix them before presenting to the user.

### Data Blob Assembly

The brief data is large (~240KB as compact JSON). The recommended approach:

1. Pull and process briefs in Python, save as `/home/claude/slim_data.json`
2. Write the JSX code (everything except the data constants) to template files using bash heredocs — one for the component layer (PromptBox, PromptButton, TickerBadge, ThemeBox, BriefRow, etc.), one for the main app layer (Header, Footer, Spotlights, VIDD export)
3. Write a top template file with placeholder strings for the data constants (VD_LOGO_PLACEHOLDER, DATA_PLACEHOLDER, SECTOR_PLACEHOLDER, etc.)
4. Use Python to read all parts, replace placeholders with actual JSON data, concatenate, and write the final `.jsx`
5. Verify the final file has no escaped unicode

### File Output

Output the final `.jsx` file to `/mnt/user-data/outputs/` and present it via `present_files`. The artifact renderer will handle React execution.

## File Size Management

The final .jsx artifact must stay under ~500KB to avoid "Failed to extract file contents" errors. Key optimizations:

- **Do NOT embed `TICKER_LINKS`** — all interactions use inline prompt boxes, not website URLs. Saves ~34KB.
- **Do NOT include the `l` (link) field** in slim briefs. Saves ~15KB.
- **Logos are pre-optimized** in the bundled `assets/logos.json` — no runtime resizing needed. Adds ~50KB.
- **Takeaway truncation**: Default 325 chars. Reduce to 250 or 200 if over 450KB.
- Target: ~400KB for the assembled artifact.

## Build Checklist

1. Load logos from bundled `assets/logos.json` (relative to this skill's directory). If missing, fall back to uploads/project paths, then SVG text fallbacks. **Never block the build waiting for logos.**
2. Calculate 120-day begin_date from current date
3. Pull Actionable briefs: `get_research(begin_date, limit=1000, sentiment="Actionable")`
4. Pull Informational briefs: `get_research(begin_date, limit=1000, sentiment="Informational")`
5. Build slim brief array (no `l` field), apply rating fallback for empty types, truncate takeaways to 325 chars
6. Verify: Positive + Negative + Comp + Unclassified = Total, zero duplicates
7. Embed logo base64 constants in the artifact (already processed — no PIL needed if using bundled asset)
8. Curate Sector Themes: group by sector/direction, apply 2x dominance + min 5 brief filter, write narratives with specific detail from briefs, write theme prompts
9. Curate Behavioral Themes: classify Actionable briefs by behavioral pattern keywords, write narratives with specific detail, write theme prompts
10. Curate P2P Themes: Layer 1 (cross-references) → Layer 2 (peer knowledge) → Layer 3 (quality filters), deduplicate tickers across pairs, write narratives with specific detail, write theme prompts
11. Write JSX component file via bash heredoc — include PromptBox (with useEffect for click-outside, NOT useCallback), PromptButton, TickerBadge, ThemeBox, BriefRow, DayToggle, TabSwitch
12. Write JSX main file via bash heredoc — include Header, Footer, PromptHint, DataSpotlight, SectorSpotlight, BehavioralSpotlight, P2PSpotlight, VIDD export
13. Assemble final .jsx via Python placeholder replacement — **do not use Python raw strings for JSX code**
14. Verify: no escaped unicode (`grep '\\u' output.jsx`), all theme tickers exist in corpus
15. Verify: no `sendPrompt` references, no `navigator.clipboard` references
16. Verify file size < 500KB. If over, trim takeaways.
17. Output to /mnt/user-data/outputs/ and present via present_files
