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
