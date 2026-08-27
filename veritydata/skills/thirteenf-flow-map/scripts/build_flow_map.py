#!/usr/bin/env python3
"""
Build a Q-over-Q 13F "flow map" quadrant scatterplot from Verity company_fund_stats data.

X axis  = QoQ % change in institutional equity shares held
Y axis  = net new holders (new initiations - liquidations)
Bubble  = total 13F value held (area-scaled)
Color   = quadrant (conviction buy / rotation in / conviction sell / concentration)

Input is a JSON file; output is an SVG (and optionally a PNG via cairosvg).
The VerityData logo is embedded in the bottom-right corner.

USAGE
-----
python3 build_flow_map.py --data universe.json --out flow_map.svg [--png flow_map.png]

INPUT JSON SCHEMA
-----------------
{
  "title": "Q1'26 13F flow map — Nasdaq 100",
  "subtitle": "All NDX constituents plotted. Bubble area scales with total 13F value held.",
  "rows": [
    {"ticker":"AAPL","eq_now":9319994802,"eq_prev":9481008549,"new":198,"liq":104,"value_m":2365321},
    ...
  ],
  "offscale": [   # optional - names whose %change blows out the x-axis; drawn as edge callouts
    {"ticker":"TSLA","eq_now":2278755602,"eq_prev":1623147376,"new":185,"liq":274,"value_m":899470}
  ],
  "labels": "auto",            # "auto" (default) | "all" | ["AAPL","MSFT",...]
  "label_overrides": {         # optional - force a label's position; pixel offsets from bubble center
    "AAPL": [22, 4, "start"]   # [dx, dy, anchor]; anchor optional ("start"|"end"|"mid")
  },
  "x_range": null,             # null = auto, or [min,max] in %
  "y_range": null,             # null = auto, or [min,max] in net holders
  "logo": "dark"               # "dark" (for light chart bg) | "white"
}

Only "rows" is required. Everything else has sensible defaults.
"""
import argparse, base64, json, math, os, sys

# Embedded VerityData logos make this script fully self-contained.
# Falls back to assets/ on disk if the embedded module isn't importable.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from verity_logos import (LOGO_DARK_B64, LOGO_WHITE_B64,
                              LOGO_DARK_SIZE, LOGO_WHITE_SIZE)
    _HAVE_EMBEDDED = True
except Exception:
    _HAVE_EMBEDDED = False

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

COLORS = {
    "Q1": {"fill": "#97C459", "stroke": "#3B6D11", "ink": "#173404"},  # conviction buy  (green)
    "Q2": {"fill": "#85B7EB", "stroke": "#185FA5", "ink": "#0C2C4D"},  # rotation in     (blue)
    "Q3": {"fill": "#F09595", "stroke": "#A32D2D", "ink": "#4D1414"},  # conviction sell (red)
    "Q4": {"fill": "#EF9F27", "stroke": "#854F0B", "ink": "#412402"},  # concentration   (amber)
}
QUAD_TINT = {"Q1": "#EAF3DE", "Q2": "#E6F1FB", "Q3": "#FCEBEB", "Q4": "#FAEEDA"}
QUAD_LABEL = {
    "Q1": ("Conviction buy", "buying · holders adding", "#3B6D11"),
    "Q2": ("Rotation in",    "selling · holders adding", "#185FA5"),
    "Q3": ("Conviction sell","selling · holders dropping","#A32D2D"),
    "Q4": ("Concentration",  "buying · holders dropping", "#854F0B"),
}


def quadrant(pct, hd):
    if pct >= 0 and hd >= 0: return "Q1"
    if pct <  0 and hd >= 0: return "Q2"
    if pct <  0 and hd <  0: return "Q3"
    return "Q4"


def nice_range(lo, hi, pad_frac=0.08):
    """Pad a data range a little and round to friendly bounds."""
    span = hi - lo
    if span <= 0:
        span = abs(hi) or 1.0
    pad = span * pad_frac
    return lo - pad, hi + pad


def compute_rows(rows):
    out = []
    for r in rows:
        eqp = r["eq_prev"]
        pct = (r["eq_now"] - eqp) / eqp * 100 if eqp else 0.0
        hd = r["new"] - r["liq"]
        out.append({
            "ticker": r["ticker"], "pct": pct, "hd": hd,
            "value_m": r.get("value_m", 1000), "qq": quadrant(pct, hd),
        })
    return out


def make_radius_fn(values):
    """Area-ish scaling on log10(value). Calibrated to the data's value span."""
    logs = [math.log10(max(v, 1000)) for v in values]
    lo, hi = min(logs), max(logs)
    if hi - lo < 1e-6:
        hi = lo + 1.0
    def rad(v):
        lv = math.log10(max(v, 1000))
        t = (lv - lo) / (hi - lo)
        return 4 + 14 * t  # 4..18 px
    return rad


def auto_labels(pts, max_labels=32):
    """Pick the names worth labeling: extremes on each axis + biggest bubbles."""
    chosen = set()
    by_pct = sorted(pts, key=lambda p: p["pct"])
    by_hd  = sorted(pts, key=lambda p: p["hd"])
    by_val = sorted(pts, key=lambda p: -p["value_m"])
    for seq in (by_pct[:6], by_pct[-6:], by_hd[:6], by_hd[-6:], by_val[:10]):
        for p in seq:
            chosen.add(p["ticker"])
    return chosen


def place_labels(pts, labelset, px, py, plot):
    """
    Greedy label placement with collision avoidance.
    Tries candidate offsets at increasing distance around each bubble; picks the
    first that collides with neither a placed label box, another bubble, nor the
    plot edges.
    """
    placed_boxes = []
    results = {}
    CH_W, CH_H = 6.2, 11  # approx char width / line height at 10px
    base_dirs = [
        (1, 0, "start"), (-1, 0, "end"), (0, -1, "mid"), (0, 1, "mid"),
        (1, -1, "start"), (-1, -1, "end"), (1, 1, "start"), (-1, 1, "end"),
    ]
    all_bubbles = [(p["cx"], p["cy"], p["r"]) for p in pts]

    def hits_bubble(box, skip_cx, skip_cy):
        for bx, by, br in all_bubbles:
            if abs(bx - skip_cx) < 1e-6 and abs(by - skip_cy) < 1e-6:
                continue  # don't test against own bubble
            nx = max(box[0], min(bx, box[2]))
            ny = max(box[1], min(by, box[3]))
            if (nx - bx) ** 2 + (ny - by) ** 2 < (br * 0.9) ** 2:
                return True
        return False

    order = sorted([p for p in pts if p["ticker"] in labelset], key=lambda p: -p["value_m"])
    for p in order:
        cx, cy, r, tk = p["cx"], p["cy"], p["r"], p["ticker"]
        w = len(tk) * CH_W
        best = None
        for ring in (1.0, 1.6, 2.3):
            for ox, oy, anchor in base_dirs:
                gap = r + 4 + (ring - 1.0) * 14
                lx = cx + ox * gap * (0.6 if oy != 0 else 1.0)
                ly = cy + oy * gap + (4 if oy == 0 else (-2 if oy < 0 else 9))
                if anchor == "start":   box_x0 = lx
                elif anchor == "end":   box_x0 = lx - w
                else:                   box_x0 = lx - w/2
                box = (box_x0, ly - CH_H, box_x0 + w, ly)
                if box[0] < plot["x0"] or box[2] > plot["x1"] or box[1] < plot["y0"] or box[3] > plot["y1"]:
                    continue
                clash = any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed_boxes)
                if clash:
                    continue
                if hits_bubble(box, cx, cy):
                    continue
                best = (lx, ly, anchor, box)
                break
            if best:
                break
        if best is None:
            gap = r + 4
            lx, ly = cx + gap, cy + 4
            box = (lx, ly-CH_H, lx+w, ly)
            best = (lx, ly, "start", box)
        lx, ly, anchor, box = best
        placed_boxes.append(box)
        results[tk] = (lx, ly, anchor)
    return results


def logo_data_uri(which):
    """Return (data_uri, (width_px, height_px)) for the requested logo.
    Prefers the embedded base64 (portable); falls back to assets/ on disk."""
    want_white = (which == "white")
    if _HAVE_EMBEDDED:
        b64 = LOGO_WHITE_B64 if want_white else LOGO_DARK_B64
        size = LOGO_WHITE_SIZE if want_white else LOGO_DARK_SIZE
        return f"data:image/png;base64,{b64}", size
    # Fallback: read from disk
    path = os.path.join(ASSET_DIR, f"verity_logo_{'white' if want_white else 'dark'}.png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    try:
        from PIL import Image
        size = Image.open(path).size
    except Exception:
        size = (600, 145)  # known default aspect for these assets
    return f"data:image/png;base64,{b64}", size


def build_svg(cfg):
    rows = compute_rows(cfg["rows"])
    offs = compute_rows(cfg.get("offscale", []))

    W, H = 1100, 640
    PAD_L, PAD_R, PAD_T, PAD_B = 100, 100, 80, 110
    PLOT_W, PLOT_H = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    # Ranges
    if cfg.get("x_range"):
        X_MIN, X_MAX = cfg["x_range"]
    else:
        xs = [p["pct"] for p in rows]
        X_MIN, X_MAX = nice_range(min(xs), max(xs))
        X_MIN, X_MAX = min(X_MIN, -1), max(X_MAX, 1)
    if cfg.get("y_range"):
        Y_MIN, Y_MAX = cfg["y_range"]
    else:
        ys = [p["hd"] for p in rows]
        Y_MIN, Y_MAX = nice_range(min(ys), max(ys))

    def px(v): return PAD_L + (v - X_MIN) * PLOT_W / (X_MAX - X_MIN)
    def py(v): return PAD_T + (Y_MAX - v) * PLOT_H / (Y_MAX - Y_MIN)

    radf = make_radius_fn([p["value_m"] for p in rows] + [p["value_m"] for p in offs] or [1000])
    for p in rows:
        p["cx"], p["cy"], p["r"] = px(p["pct"]), py(p["hd"]), radf(p["value_m"])

    # Labels
    lab = cfg.get("labels", "auto")
    if lab == "all":
        labelset = {p["ticker"] for p in rows}
    elif isinstance(lab, list):
        labelset = set(lab)
    else:
        labelset = auto_labels(rows)
    plot_box = {"x0": PAD_L, "y0": PAD_T, "x1": PAD_L+PLOT_W, "y1": PAD_T+PLOT_H}
    label_pos = place_labels(rows, labelset, px, py, plot_box)

    # Optional manual label overrides: {"AAPL": [dx, dy, "start|end|mid"]}
    # dx/dy are pixel offsets from the bubble center; anchor is optional (default "start").
    for tk, ov in (cfg.get("label_overrides") or {}).items():
        p = next((q for q in rows if q["ticker"] == tk), None)
        if not p:
            continue
        dx = ov[0] if len(ov) > 0 else p["r"] + 4
        dy = ov[1] if len(ov) > 1 else 4
        anchor = ov[2] if len(ov) > 2 else "start"
        label_pos[tk] = (p["cx"] + dx, p["cy"] + dy, anchor)

    zx, zy = px(0), py(0)
    zx = max(PAD_L, min(PAD_L+PLOT_W, zx))
    zy = max(PAD_T, min(PAD_T+PLOT_H, zy))

    s = []
    s.append(f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{cfg.get("title","13F flow map")}">')
    s.append(f'<title>{cfg.get("title","13F flow map")}</title>')
    s.append('<desc>Quadrant scatterplot of institutional flows. X axis: QoQ percent change in institutional shares. Y axis: net new holders. Bubble size: total 13F value held.</desc>')

    # Quadrant tints
    s.append(f'<rect x="{zx}" y="{PAD_T}" width="{PAD_L+PLOT_W-zx}" height="{zy-PAD_T}" fill="{QUAD_TINT["Q1"]}" opacity="0.5"/>')
    s.append(f'<rect x="{PAD_L}" y="{PAD_T}" width="{zx-PAD_L}" height="{zy-PAD_T}" fill="{QUAD_TINT["Q2"]}" opacity="0.5"/>')
    s.append(f'<rect x="{PAD_L}" y="{zy}" width="{zx-PAD_L}" height="{PAD_T+PLOT_H-zy}" fill="{QUAD_TINT["Q3"]}" opacity="0.5"/>')
    s.append(f'<rect x="{zx}" y="{zy}" width="{PAD_L+PLOT_W-zx}" height="{PAD_T+PLOT_H-zy}" fill="{QUAD_TINT["Q4"]}" opacity="0.5"/>')

    # Frame + zero axes
    s.append(f'<rect x="{PAD_L}" y="{PAD_T}" width="{PLOT_W}" height="{PLOT_H}" fill="none" stroke="#CBD2D9" stroke-width="0.5"/>')
    s.append(f'<line x1="{zx}" y1="{PAD_T}" x2="{zx}" y2="{PAD_T+PLOT_H}" stroke="#9AA5B1" stroke-width="1" stroke-dasharray="3,3"/>')
    s.append(f'<line x1="{PAD_L}" y1="{zy}" x2="{PAD_L+PLOT_W}" y2="{zy}" stroke="#9AA5B1" stroke-width="1" stroke-dasharray="3,3"/>')

    # X ticks
    def tick_step(span, target=8):
        raw = span / target
        mag = 10 ** math.floor(math.log10(raw))
        for m in (1, 2, 2.5, 5, 10):
            if raw <= m * mag:
                return m * mag
        return 10 * mag
    xstep = tick_step(X_MAX - X_MIN)
    t = math.ceil(X_MIN / xstep) * xstep
    while t <= X_MAX + 1e-9:
        x = px(t)
        s.append(f'<line x1="{x:.1f}" y1="{PAD_T+PLOT_H}" x2="{x:.1f}" y2="{PAD_T+PLOT_H+4}" stroke="#CBD2D9" stroke-width="0.5"/>')
        lbl = f'+{t:g}%' if t > 0 else f'{t:g}%'
        s.append(f'<text x="{x:.1f}" y="{PAD_T+PLOT_H+16}" text-anchor="middle" fill="#52606D" style="font-size:10px;font-family:Arial,Helvetica,sans-serif">{lbl}</text>')
        t += xstep
    ystep = tick_step(Y_MAX - Y_MIN)
    t = math.ceil(Y_MIN / ystep) * ystep
    while t <= Y_MAX + 1e-9:
        y = py(t)
        s.append(f'<line x1="{PAD_L-4}" y1="{y:.1f}" x2="{PAD_L}" y2="{y:.1f}" stroke="#CBD2D9" stroke-width="0.5"/>')
        lbl = f'+{t:g}' if t > 0 else f'{t:g}'
        s.append(f'<text x="{PAD_L-7}" y="{y+3:.1f}" text-anchor="end" fill="#52606D" style="font-size:10px;font-family:Arial,Helvetica,sans-serif">{lbl}</text>')
        t += ystep

    # Axis titles
    s.append(f'<text x="{PAD_L+PLOT_W/2:.1f}" y="{H-44}" text-anchor="middle" fill="#1F2933" style="font-size:11px;font-weight:600;font-family:Arial,Helvetica,sans-serif">\u0394 institutional shares, QoQ (%)</text>')
    s.append(f'<text transform="translate(30,{PAD_T+PLOT_H/2:.1f}) rotate(-90)" text-anchor="middle" fill="#1F2933" style="font-size:11px;font-weight:600;font-family:Arial,Helvetica,sans-serif">Net new holders (initiations \u2212 liquidations)</text>')

    # Title / subtitle
    s.append(f'<text x="{PAD_L}" y="30" fill="#1F2933" style="font-size:18px;font-weight:600;font-family:Arial,Helvetica,sans-serif">{cfg.get("title","13F flow map")}</text>')
    if cfg.get("subtitle"):
        s.append(f'<text x="{PAD_L}" y="52" fill="#52606D" style="font-size:11px;font-family:Arial,Helvetica,sans-serif">{cfg["subtitle"]}</text>')

    # Quadrant corner labels
    for q, (corner_x, corner_y, anchor) in {
        "Q1": (PAD_L+PLOT_W-8, PAD_T+16, "end"),
        "Q2": (PAD_L+8, PAD_T+16, "start"),
        "Q3": (PAD_L+8, PAD_T+PLOT_H-22, "start"),
        "Q4": (PAD_L+PLOT_W-8, PAD_T+PLOT_H-22, "end"),
    }.items():
        title, sub, col = QUAD_LABEL[q]
        s.append(f'<text x="{corner_x}" y="{corner_y}" text-anchor="{anchor}" fill="{col}" style="font-size:11px;font-weight:600;font-family:Arial,Helvetica,sans-serif">{title}</text>')
        s.append(f'<text x="{corner_x}" y="{corner_y+14}" text-anchor="{anchor}" fill="{col}" opacity="0.85" style="font-size:10px;font-family:Arial,Helvetica,sans-serif">{sub}</text>')

    # Off-scale callouts (drawn at right edge)
    edge_x = PAD_L + PLOT_W - 10
    for p in offs:
        col = COLORS[p["qq"]]
        r = radf(p["value_m"])
        ey = py(max(Y_MIN, min(Y_MAX, p["hd"])))
        s.append('<g>')
        s.append(f'<circle cx="{edge_x:.1f}" cy="{ey:.1f}" r="{r:.1f}" fill="{col["fill"]}" stroke="{col["stroke"]}" stroke-width="1" opacity="0.72"/>')
        s.append(f'<polygon points="{edge_x+r+1:.1f},{ey-6:.1f} {edge_x+r+11:.1f},{ey:.1f} {edge_x+r+1:.1f},{ey+6:.1f}" fill="{col["stroke"]}"/>')
        s.append(f'<text x="{edge_x:.1f}" y="{ey-r-12:.1f}" text-anchor="middle" fill="{col["ink"]}" style="font-size:11px;font-weight:600;font-family:Arial,Helvetica,sans-serif">{p["ticker"]}</text>')
        s.append(f'<text x="{edge_x:.1f}" y="{ey-r-2:.1f}" text-anchor="middle" fill="{col["stroke"]}" style="font-size:9px;font-family:Arial,Helvetica,sans-serif">{p["pct"]:+.0f}% \u2192</text>')
        s.append('</g>')

    # Bubbles (largest first)
    for p in sorted(rows, key=lambda p: -p["r"]):
        col = COLORS[p["qq"]]
        s.append(f'<circle cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" r="{p["r"]:.1f}" fill="{col["fill"]}" stroke="{col["stroke"]}" stroke-width="0.8" opacity="0.7"/>')

    # Labels
    for p in rows:
        if p["ticker"] not in label_pos:
            continue
        lx, ly, anchor = label_pos[p["ticker"]]
        a = {"start": "start", "end": "end", "mid": "middle"}[anchor]
        s.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{a}" fill="#1F2933" style="font-size:10px;font-weight:600;font-family:Arial,Helvetica,sans-serif">{p["ticker"]}</text>')

    # Bubble size legend
    vmax = max(p["value_m"] for p in rows)
    legend_vals = [v for v in [50000, 200000, 1000000, 3000000] if v <= vmax*1.2][:4]
    if not legend_vals:
        legend_vals = [vmax]
    lx0, ly0 = PAD_L + 8, H - 30
    s.append(f'<text x="{lx0}" y="{ly0-20}" fill="#52606D" style="font-size:10px;font-family:Arial,Helvetica,sans-serif">13F value:</text>')
    xcursor = lx0 + 18
    for v in legend_vals:
        rr = radf(v)
        s.append(f'<circle cx="{xcursor+rr:.1f}" cy="{ly0-3:.1f}" r="{rr:.1f}" fill="none" stroke="#7B8794" stroke-width="1"/>')
        lab_v = f'${v/1000:.0f}B' if v < 1_000_000 else f'${v/1_000_000:.0f}T'
        s.append(f'<text x="{xcursor+2*rr+5:.1f}" y="{ly0:.1f}" fill="#52606D" style="font-size:10px;font-family:Arial,Helvetica,sans-serif">{lab_v}</text>')
        xcursor += 2*rr + 12 + len(lab_v)*6.5

    # Quadrant counts footer
    qc = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for p in rows: qc[p["qq"]] += 1
    for p in offs: qc[p["qq"]] += 1
    note = (f'Conviction buy {qc["Q1"]}  ·  Rotation in {qc["Q2"]}  ·  '
            f'Conviction sell {qc["Q3"]}  ·  Concentration {qc["Q4"]}')
    s.append(f'<text x="{PAD_L}" y="{H-12}" fill="#52606D" style="font-size:11px;font-family:Arial,Helvetica,sans-serif">{note}</text>')

    # VerityData logo, bottom-right
    uri, (lw_px, lh_px) = logo_data_uri(cfg.get("logo", "dark"))
    logo_w = 132
    logo_h = logo_w * lh_px / lw_px
    s.append(f'<image href="{uri}" x="{W-PAD_R-logo_w+90:.1f}" y="{H-logo_h-10:.1f}" width="{logo_w:.1f}" height="{logo_h:.1f}"/>')

    s.append('</svg>')
    return "\n".join(s), qc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Input JSON path")
    ap.add_argument("--out", required=True, help="Output SVG path")
    ap.add_argument("--png", default=None, help="Optional PNG output path")
    ap.add_argument("--png-width", type=int, default=1800)
    args = ap.parse_args()

    with open(args.data) as f:
        cfg = json.load(f)
    svg, qc = build_svg(cfg)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"Wrote {args.out} ({len(svg)} bytes)")
    print(f"Quadrant counts: {qc}  total={sum(qc.values())}")

    if args.png:
        try:
            import cairosvg
            cairosvg.svg2png(url=args.out, write_to=args.png, output_width=args.png_width)
            print(f"Wrote {args.png}")
        except Exception as e:
            print(f"PNG render failed ({e}). SVG is still valid.", file=sys.stderr)


if __name__ == "__main__":
    main()
