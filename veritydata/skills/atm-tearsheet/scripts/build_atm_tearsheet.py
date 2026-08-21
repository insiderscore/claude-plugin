#!/usr/bin/env python3
"""Render a single-ticker ATM issuance tear sheet from raw Verity client-tool CSVs.

One self-contained HTML file in the Verity house style. The headline is the
**capacity reservoir** -- authorized shelf capacity reconstructed as a step
series that drains with every disclosed sale and refills at each new or
enlarged program -- with the pace, the runway in quarters, and the refill
habit beside it. No market-data feed is used anywhere: every price on the
sheet is a disclosed print (a tranche's realized price per share, a row's
implied price remaining_dollars/remaining_shares, or an insider Form 4
print), and there is deliberately no price chart and no execution score.
Two diagnostic percentages (_diag_* in the metrics JSON) exist only to help
the caller choose accurate wording; they are never rendered and must never
be quoted as scores or grades.

Below the headline: the program-to-date strip (total raised, blended VWAP,
last disclosed print), the cadence & disclosure-lag record (how blind is the
public record right now), the insider cross-check (company printing vs.
insiders' own prints), program economics, and the plan ledger. Greyscale +
one orange accent, monospace numerics, inline SVG, no external JS.

Usage:
    python3 build_atm_tearsheet.py --announce A.csv --sales S.csv \
        [--insider I.csv] --meta meta.json --output OUT.html
    python3 build_atm_tearsheet.py --announce A.csv --sales S.csv \
        [--insider I.csv] --metrics-only        # print metrics JSON, no HTML

Inputs (raw tool output, saved verbatim -- the cleaning rules live here):
  --announce  CSV from Verity:atm_announce for one ticker (full history)
  --sales     CSV from Verity:atm_sales for one ticker (full history)
  --insider   CSV from Verity:get_insider_transactions (Buy/Sell/Exercise Sell,
              officers+directors) -- optional; powers the cross-check panel and
              the insider-spread stat. Omit cleanly if unavailable.
  --meta      JSON written by the caller AFTER reading --metrics-only output:
    {
      "ticker","company","sector","mcap_label","asof",
      "verdict":       "short chip text",
      "lead":          "<html> ~3-5 sentence issuance read (the 'so what')",
      "capacity_read": "one-line reading of the reservoir",
      "insider_read":  "one-line reading of the cross-check (optional)",
      "footer_extra":  "<html> appended to the methodology footer (optional)"
    }

All metric computation here is deterministic -- same CSVs in, same numbers out.
The caller supplies prose; it never supplies or edits a number.
"""
import argparse, csv, io, json, math, os, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = open(os.path.join(HERE, "verity_logo_b64.txt")).read().strip() if \
    os.path.exists(os.path.join(HERE, "verity_logo_b64.txt")) else ""

# ----------------------------- tiny helpers ------------------------------

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")) if s is not None else ""

def f2(v):
    try:
        s = str(v).strip()
        return float(s) if s not in ("", "None", "nan") else None
    except Exception:
        return None

def pdate(s):
    if not s: return None
    return dt.datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()

def dollars_label(v, dec=1):
    a = abs(v)
    if a >= 1e9:  return f"${v/1e9:,.{dec}f}B"
    if a >= 1e6:  return f"${v/1e6:,.0f}M"
    if a >= 1e3:  return f"${v/1e3:,.0f}K"
    return f"${v:,.0f}"

def qkey(d):
    return (d.year, (d.month-1)//3+1)

def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(io.StringIO(f.read())))

# ----------------------------- metric engine -----------------------------

def compute(announce, sales, insider, asof=None):
    # ---- sales rows: parse, order, dedup restatements -------------------
    rows = []
    for r in sales:
        d = f2(r.get("dollars"))
        if d is None or d <= 0: continue
        rem_d, rem_s = f2(r.get("remaining_dollars")), f2(r.get("remaining_shares"))
        implied = (rem_d / rem_s) if (rem_d and rem_s and rem_s > 0) else None
        rows.append({
            "plan": r.get("plan_id"), "quarter": r.get("quarter"),
            "disc": pdate(r.get("disclosure_date")), "eff": pdate(r.get("effective_date")),
            "dollars": d, "shares": f2(r.get("shares")), "pps": f2(r.get("pps")),
            "form": (r.get("formtype") or "").strip(),
            "fwd": (r.get("forward_sale") or "").strip() == "True",
            "pctout": f2(r.get("pctout")), "rem": rem_d, "implied": implied,
        })
    rows.sort(key=lambda r: (r["eff"] or dt.date.min, r["disc"] or dt.date.min))
    seen, deduped, dropped = {}, [], 0
    for r in rows:
        k = (round(r["dollars"], 0), round(r["shares"] or 0, 0), r["pps"])
        if k in seen: dropped += 1; continue
        seen[k] = True; deduped.append(r)
    rows = deduped

    # ---- insider prints ---------------------------------------------------
    ins_rows = []
    for r in insider or []:
        sh, val = f2(r.get("shares")), f2(r.get("value"))
        d = pdate(r.get("txndate"))
        if not (sh and val and d and sh > 0): continue
        code = (r.get("code") or "").strip().lower()
        kind = "buy" if code == "buy" else "sell"
        ins_rows.append({"date": d, "px": val/sh, "shares": sh, "value": val,
                         "kind": kind, "who": r.get("insider"), "pos": r.get("pos_type")})
    ins_rows.sort(key=lambda r: r["date"])

    # ---- priced tranches, split-artifact guard ----------------------------
    priced = [r for r in rows if r["pps"] and r["shares"] and r["eff"]]
    excluded = 0
    if len(priced) >= 5:
        keep = []
        for i, r in enumerate(priced):
            nb = [priced[j]["pps"] for j in range(max(0, i-2), min(len(priced), i+3)) if j != i]
            med = sorted(nb)[len(nb)//2]
            if r["pps"] > med * 2.5 or r["pps"] < med * 0.4:
                excluded += 1
            else:
                keep.append(r)
        priced = keep

    # ---- headline: VWAP-accretion share -----------------------------------
    cum_d = cum_s = 0.0
    acc_num = acc_den = 0.0
    seq_num = seq_den = 0.0
    prev_px = None
    for r in priced:
        if cum_s > 0:
            rv = cum_d / cum_s
            r["run_vwap"] = rv
            acc_den += r["dollars"]
            if r["pps"] > rv: acc_num += r["dollars"]
        if prev_px is not None:
            seq_den += r["dollars"]
            if r["pps"] > prev_px: seq_num += r["dollars"]
        prev_px = r["pps"]
        cum_d += r["dollars"]; cum_s += r["shares"]
    accretion = 100.0 * acc_num / acc_den if acc_den else None
    seq_up    = 100.0 * seq_num / seq_den if seq_den else None
    vwap = cum_d / cum_s if cum_s else None

    last_eff_all = max((r["eff"] for r in rows if r["eff"]), default=None)
    last_disc    = max((r["disc"] for r in rows if r["disc"]), default=None)
    data_asof = max(d for d in [last_eff_all, last_disc,
                                ins_rows[-1]["date"] if ins_rows else None] if d)
    asof = asof or dt.date.today()
    if asof < data_asof: asof = data_asof

    cut12 = asof - dt.timedelta(days=365)
    pr12 = [r for r in priced if r["eff"] >= cut12 and "run_vwap" in r]
    a12d = sum(r["dollars"] for r in pr12)
    accretion_12m = 100.0 * sum(r["dollars"] for r in pr12 if r["pps"] > r["run_vwap"]) / a12d if a12d else None
    vw12r = [r for r in priced if r["eff"] >= cut12]
    vwap_12m = (sum(r["dollars"] for r in vw12r) / sum(r["shares"] for r in vw12r)) if vw12r else None

    # ---- price observations (all disclosed prints) ------------------------
    obs_last = max((r["eff"] for r in priced), default=None)

    ins_q_sell = {}
    for r in ins_rows:
        if r["kind"] == "sell":
            ins_q_sell[qkey(r["date"])] = ins_q_sell.get(qkey(r["date"]), 0.0) + r["value"]

    total_raised = sum(r["dollars"] for r in rows)
    total_shares = sum(r["shares"] or 0 for r in rows)
    total_pctout = sum(r["pctout"] or 0 for r in rows)
    raised_12m   = sum(r["dollars"] for r in rows if r["eff"] and r["eff"] >= cut12)

    # ---- announce events / capacity reservoir -----------------------------
    ev = []
    for r in announce:
        ev.append({
            "plan": r.get("plan_id"), "typ": (r.get("disclosure_type") or "").strip(),
            "disc": pdate(r.get("disclosure_date")), "eff": pdate(r.get("effective_date")),
            "dollars": f2(r.get("dollars")), "rem": f2(r.get("remaining_dollars")),
            "comm": f2(r.get("commission")), "upto": (r.get("upto") or "").strip() == "True",
            "form": (r.get("formtype") or "").strip(),
        })
    ev.sort(key=lambda e: (e["eff"] or e["disc"] or dt.date.min))
    plan_comm = {}
    for e in ev:
        if e["typ"] == "New" and e["comm"] is not None:
            plan_comm[e["plan"]] = (e["comm"], e["upto"])

    caps, steps, refills = {}, [], []
    items = [("E", e["eff"] or e["disc"], e) for e in ev if (e["eff"] or e["disc"])] + \
            [("S", r["eff"], r) for r in rows if r["eff"]]
    items.sort(key=lambda t: (t[1], 0 if t[0] == "E" else 1))
    for kind, d, o in items:
        if kind == "E":
            t = o["typ"]
            if t == "New":
                caps[o["plan"]] = o["dollars"] or 0; refills.append(d)
            elif t == "Increase":
                caps[o["plan"]] = caps.get(o["plan"], 0) + (o["dollars"] or 0)
            elif t == "Decrease":
                caps[o["plan"]] = max(0.0, caps.get(o["plan"], 0) - (o["dollars"] or 0))
            elif t in ("Terminated", "Replaced"):
                caps[o["plan"]] = 0.0
        else:
            if o["plan"] not in caps and o.get("rem") is not None:
                caps[o["plan"]] = o["rem"] + o["dollars"]   # pre-coverage plan: seed from disclosed remainder
            caps[o["plan"]] = max(0.0, caps.get(o["plan"], 0) - o["dollars"])
        steps.append((d, sum(caps.values()), kind))
    current_capacity = steps[-1][1] if steps else 0.0

    refill_gaps = [(b - a).days for a, b in zip(refills, refills[1:])]
    med_refill = sorted(refill_gaps)[len(refill_gaps)//2] if refill_gaps else None
    auth_by_plan = {}
    for e in ev:
        if e["typ"] == "New": auth_by_plan[e["plan"]] = e["dollars"] or 0
        elif e["typ"] == "Increase": auth_by_plan[e["plan"]] = auth_by_plan.get(e["plan"], 0) + (e["dollars"] or 0)
    utils = []
    for e in ev:
        if e["typ"] in ("Terminated", "Replaced") and e["rem"] is not None:
            a = auth_by_plan.get(e["plan"])
            if a: utils.append(max(0.0, min(1.0, 1 - e["rem"]/a)))
    med_util = sorted(utils)[len(utils)//2] if utils else None

    # ---- quarterly issuance & pace ---------------------------------------
    qsum = {}
    for r in rows:
        if not r["eff"]: continue
        qsum[qkey(r["eff"])] = qsum.get(qkey(r["eff"]), 0.0) + r["dollars"]
    qkeys = sorted(qsum)
    curq = qkey(asof)
    full_q = [k for k in qkeys if k < curq]
    trail4 = full_q[-4:]
    pace = sum(qsum[k] for k in trail4) / len(trail4) if trail4 else None
    qte = (current_capacity / pace) if (pace and pace > 0) else None

        # ---- fees -------------------------------------------------------------
    fee_total, fee_capped = 0.0, True
    for r in rows:
        c = plan_comm.get(r["plan"])
        if c:
            fee_total += r["dollars"] * c[0] / 100.0
            fee_capped = fee_capped and c[1]
    comm_series = sorted(((e["eff"] or e["disc"], e["comm"], e["upto"]) for e in ev
                          if e["typ"] == "New" and e["comm"] is not None))
    fwd_d = sum(r["dollars"] for r in rows if r["fwd"])

    # ---- plan ledger -------------------------------------------------------
    ledger = []
    new_plans = {e["plan"] for e in ev if e["typ"] == "New"}
    for p in sorted({r["plan"] for r in rows} - new_plans,
                    key=lambda p: min(r["eff"] or dt.date.max for r in rows if r["plan"] == p)):
        prs = [r for r in rows if r["plan"] == p]
        first = min((r for r in prs if r["eff"]), key=lambda r: r["eff"], default=None)
        seed = (first["rem"] + first["dollars"]) if (first and first["rem"] is not None) else None
        term = next((x for x in ev if x["plan"] == p and x["typ"] in ("Terminated", "Replaced")), None)
        cm = next((x["comm"] for x in ev if x["plan"] == p and x["comm"] is not None), None)
        ledger.append({"plan": p, "start": None, "auth": seed or 0,
                       "sold": sum(r["dollars"] for r in prs),
                       "end": (term["eff"] or term["disc"]) if term else None,
                       "endtyp": term["typ"] if term else "live",
                       "comm": (cm, term["upto"]) if (cm is not None and term) else None,
                       "form": "pre-coverage"})
    for e in ev:
        if e["typ"] != "New": continue
        p = e["plan"]
        sold = sum(r["dollars"] for r in rows if r["plan"] == p)
        term = next((x for x in ev if x["plan"] == p and x["typ"] in ("Terminated", "Replaced")), None)
        auth = auth_by_plan.get(p, e["dollars"] or 0)
        if term:
            endtyp, end = term["typ"], (term["eff"] or term["disc"])
        elif auth and sold >= auth * 0.995 and caps.get(p, auth) <= auth * 0.005:
            endtyp, end = "Exhausted", max((r["eff"] for r in rows if r["plan"] == p and r["eff"]), default=None)
        else:
            endtyp, end = "live", None
        ledger.append({"plan": p, "start": e["eff"] or e["disc"], "auth": auth,
                       "sold": sold, "end": end, "endtyp": endtyp,
                       "comm": plan_comm.get(p), "form": e["form"]})
    ledger.sort(key=lambda l: l["start"] or dt.date.min)

    return {
        "asof": asof, "rows": rows, "priced": priced, "ins_rows": ins_rows,
        "dropped_dupes": dropped, "excluded": excluded,
        "accretion": accretion, "accretion_12m": accretion_12m, "seq_up": seq_up,
        "vwap": vwap, "vwap_12m": vwap_12m, "ins_q_sell": ins_q_sell,
        "total_raised": total_raised, "raised_12m": raised_12m,
        "total_shares": total_shares, "total_pctout": total_pctout,
        "steps": steps, "current_capacity": current_capacity,
        "refills": refills, "med_refill_days": med_refill, "med_utilization": med_util,
        "_qsum": qsum, "pace_qtr": pace, "qtrs_to_exhaustion": qte,
        "last_eff": last_eff_all,
        "fee_total": fee_total, "fee_capped": fee_capped, "comm_series": comm_series,
        "fwd_dollars": fwd_d, "ledger": ledger,
    }

def metrics_public(m):
    rnd = lambda v, n=1: None if v is None else round(v, n)
    return {
        "as_of": str(m["asof"]),
        "_diag_pct_dollars_above_running_vwap": rnd(m["accretion"]),
        "_diag_pct_dollars_above_prior_tranche": rnd(m["seq_up"]),
        "blended_vwap": rnd(m["vwap"], 2), "blended_vwap_12m": rnd(m["vwap_12m"], 2),
        "total_raised": round(m["total_raised"]), "raised_12m": round(m["raised_12m"]),
        "total_shares_issued": round(m["total_shares"]),
        "cum_pct_of_shares_out": rnd(m["total_pctout"]),
        "current_remaining_capacity": round(m["current_capacity"]),
        "trailing4q_pace_per_qtr": None if m["pace_qtr"] is None else round(m["pace_qtr"]),
        "quarters_to_exhaustion": rnd(m["qtrs_to_exhaustion"]),
        "refill_count": len(m["refills"]), "median_refill_days": m["med_refill_days"],
        "median_plan_utilization_pct": None if m["med_utilization"] is None else round(m["med_utilization"]*100),
        "last_reported_sale_date": str(m["last_eff"]) if m["last_eff"] else None,
        "est_agent_fees": round(m["fee_total"]), "fees_are_cap": m["fee_capped"],
        "forward_sale_dollars": round(m["fwd_dollars"]),
        "tranches_scored": len(m["priced"]), "tranches_deduped": m["dropped_dupes"],
        "tranches_excluded_price_inconsistent": m["excluded"],
        "quarterly_issuance": {f"{y}Q{q}": round(v) for (y, q), v in sorted(m["_qsum"].items())},
    }

# ----------------------------- SVG panels --------------------------------

def _poly(pts, stroke, w, dash="", fill="none", op=1.0):
    s = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{op}"' if op != 1.0 else ""
    return f'<polyline points="{s}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"{d}{o} stroke-linejoin="round" stroke-linecap="round"/>'

def capacity_chart(m, W=1120, H=330):
    steps = m["steps"]
    if not steps: return ""
    x0, y0, pw, ph = 60, 12, W - 60 - 130, H - 12 - 34
    dmin, dmax = steps[0][0], m["asof"]
    span = max(1, (dmax - dmin).days)
    hi = max(v for _, v, _ in steps) * 1.08
    def X(d): return x0 + (d - dmin).days / span * pw
    def Y(v): return y0 + (1 - v/hi) * ph
    g = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    for v in (hi/1.08/2, hi/1.08):
        g.append(f'<line x1="{x0}" y1="{Y(v):.1f}" x2="{x0+pw}" y2="{Y(v):.1f}" stroke="#f0f0f0"/>' 
                 f'<text x="{x0-6}" y="{Y(v)+3:.1f}" class="ax" text-anchor="end">{dollars_label(v,1)}</text>')
    yr = dmin.year + 1
    while dt.date(yr, 1, 1) <= dmax:
        xx = X(dt.date(yr, 1, 1))
        g.append(f'<text x="{xx:.1f}" y="{y0+ph+14}" class="ax" text-anchor="middle">{yr}</text>')
        yr += 1
    pts, prev = [(X(steps[0][0]), Y(0))], 0.0
    for d, v, _ in steps:
        pts.append((X(d), Y(prev))); pts.append((X(d), Y(v))); prev = v
    pts.append((X(dmax), Y(prev)))
    area = pts + [(X(dmax), Y(0))]
    g.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in area)}" fill="#efefef"/>')
    g.append(_poly(pts, "#8a8a8a", 1.5))
    for d in m["refills"]:
        g.append(f'<path d="M {X(d):.1f} {y0+ph+2} l 4 6 l -8 0 z" fill="#f14b25"><title>new / replacement program {d}</title></path>')
    yv = Y(m["current_capacity"])
    g.append(f'<circle cx="{X(dmax):.1f}" cy="{yv:.1f}" r="3.2" fill="#f14b25"/>'
             f'<text x="{X(dmax)+6:.1f}" y="{yv+3:.1f}" class="axb">{dollars_label(m["current_capacity"],1)} live</text>')
    g.append(f'<text x="{x0}" y="{H-4}" class="ax">authorized capacity remaining across all live programs &mdash; &#9650; = new/replacement shelf filed</text>')
    g.append('</svg>')
    return "".join(g)

def insider_chart(m, W=1120, H=210, nq=20):
    iq = m["ins_q_sell"]
    ks = sorted(m["_qsum"])[-nq:]
    if not ks: return ""
    x0, y0, pw = 60, 12, W - 60 - 16
    ph = (H - 12 - 34)
    h1 = ph * 0.55; h2 = ph * 0.35; gap = ph*0.10
    hiA = max([m["_qsum"].get(k, 0) for k in ks] + [1])
    hiI = max([iq.get(k, 0) for k in ks] + [1])
    bw = pw / len(ks)
    g = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    g.append(f'<text x="{x0-6}" y="{y0+8}" class="ax" text-anchor="end">ATM</text>')
    g.append(f'<text x="{x0-6}" y="{y0+h1+gap+8}" class="ax" text-anchor="end">insiders</text>')
    for i, k in enumerate(ks):
        a = m["_qsum"].get(k, 0); s = iq.get(k, 0)
        ha = a/hiA*h1; hs = s/hiI*h2
        if a > 0:
            g.append(f'<rect x="{x0+i*bw+3:.1f}" y="{y0+h1-ha:.1f}" width="{bw-6:.1f}" height="{max(ha,0.8):.1f}" fill="#4a4a4a"><title>{dollars_label(a)}</title></rect>')
        if s > 0:
            g.append(f'<rect x="{x0+i*bw+3:.1f}" y="{y0+h1+gap:.1f}" width="{bw-6:.1f}" height="{max(hs,0.8):.1f}" fill="#f14b25" fill-opacity=".8"><title>{dollars_label(s)}</title></rect>')
        if i % 2 == (len(ks)+1) % 2:
            g.append(f'<text x="{x0+i*bw+bw/2:.1f}" y="{H-18}" class="ax" text-anchor="middle">Q{k[1]}\'{k[0]%100:02d}</text>')
    g.append(f'<line x1="{x0}" y1="{y0+h1+gap/2:.1f}" x2="{x0+pw}" y2="{y0+h1+gap/2:.1f}" stroke="#ddd"/>')
    g.append(f'<text x="{x0}" y="{H-4}" class="ax">company issuance (top, max {dollars_label(hiA)}) vs. insider open-market selling (bottom, max {dollars_label(hiI)}) &mdash; independently scaled</text>')
    g.append('</svg>')
    return "".join(g)

# ----------------------------- page assembly -----------------------------

CSS = """
 :root { --ink:#1a1a1a; --mut:#666; --faint:#999; --line:#f0f0f0; --rule:#ccc;
  --grow:#f14b25; --pos:#1f7a4d; --neg:#b23b2e; --warn:#b07a00; --warnbg:#fbf7ec; }
 * { box-sizing:border-box; }
 body { margin:0; padding:30px 40px 40px; background:#fff; color:var(--ink);
  font:13px/1.45 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; max-width:1200px; }
 .hd { display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid var(--ink); padding-bottom:10px; }
 h1 { font-size:19px; margin:0; letter-spacing:-.01em; } h1 .tk { font-family:ui-monospace,Menlo,Consolas,monospace; }
 .sub { color:var(--mut); margin-top:3px; font-size:12px; }
 .meta { text-align:right; color:var(--faint); font-size:11px; } .meta img { height:26px; }
 .verdict { display:inline-block; margin-top:6px; font-size:11px; font-weight:700; letter-spacing:.03em;
  color:var(--warn); background:var(--warnbg); border:1px solid #ecdca6; padding:3px 9px; border-radius:3px; }
 .take { border-left:3px solid var(--grow); background:#fafafa; padding:11px 15px; margin:16px 0 18px; }
 .take .lbl { font-size:10px; letter-spacing:.09em; color:var(--faint); font-weight:700; display:block; margin-bottom:3px; }
 .sech { font-size:10px; letter-spacing:.09em; text-transform:uppercase; color:#999; font-weight:700;
  margin:22px 0 9px; padding-bottom:4px; border-bottom:1px solid var(--rule); }
 .sech .hint { float:right; text-transform:none; letter-spacing:0; color:var(--faint); font-weight:400; }
 .row2 { display:flex; gap:26px; } .row2 > div { flex:1; min-width:0; }
 .headrow { display:flex; gap:26px; } .headrow .chart { flex:1 1 auto; min-width:0; } .headrow .side { flex:0 0 235px; }
 .pstat { margin-bottom:13px; } .pstat-l { font-size:11.5px; color:var(--mut); }
 .pstat-v { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:16px; font-weight:700; }
 .pstat-v .big { font-size:25px; } .pstat-v small { font-size:11px; color:var(--mut); font-weight:400; }
 .read { font-size:12px; line-height:1.55; margin-top:12px; padding-left:11px; border-left:3px solid var(--grow); }
 .ax  { font:10px ui-monospace,Menlo,Consolas,monospace; fill:#999; }
 .axb { font:700 10.5px ui-monospace,Menlo,Consolas,monospace; fill:#1a1a1a; }
 .stats-inline { display:flex; gap:34px; flex-wrap:wrap; margin:6px 0 2px; }
 table.ledger { border-collapse:collapse; width:100%; font-size:11.5px; }
 table.ledger th { text-align:left; font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:#999; border-bottom:1px solid var(--rule); padding:4px 10px 4px 0; }
 table.ledger td { border-bottom:1px solid var(--line); padding:4px 10px 4px 0; font-family:ui-monospace,Menlo,Consolas,monospace; white-space:nowrap; }
 table.ledger td.t { font-family:inherit; }
 .ft { margin-top:26px; padding-top:9px; border-top:1px solid var(--rule); color:var(--faint); font-size:10.5px; line-height:1.55; }
 @media print { body { padding:18px 24px; } }
"""

def build_html(meta, m):
    mp = metrics_public(m)
    tick, comp = meta["ticker"], meta.get("company", "")
    comm_now = m["comm_series"][-1] if m["comm_series"] else None
    comm_txt = (f'{"&le;" if comm_now[2] else ""}{comm_now[1]:g}%' if comm_now else "&mdash;")

    led = []
    for l in m["ledger"]:
        end = f'{l["end"]} ({l["endtyp"].lower()})' if l["end"] else '<b>live</b>'
        cm = (f'{"&le;" if l["comm"][1] else ""}{l["comm"][0]:g}%') if l["comm"] else "&mdash;"
        pctu = f'{min(1.0, l["sold"]/l["auth"])*100:.0f}%' if l["auth"] else "&mdash;"
        led.append(f'<tr><td>{esc(l["plan"])}</td><td>{l["start"] or "&mdash;"}</td><td class="t">{esc(l["form"])}</td>'
                   f'<td style="text-align:right">{dollars_label(l["auth"],2)}</td>'
                   f'<td style="text-align:right">{dollars_label(l["sold"],2)}</td>'
                   f'<td style="text-align:right">{pctu}</td><td>{cm}</td><td class="t">{end}</td></tr>')

    insider_html = ""
    if m["ins_rows"] or m["ins_q_sell"]:
        insider_html = f"""
<div class="sech">Cadence &amp; insider cross-check <span class="hint">quarterly company issuance, with insiders' own open-market selling beneath it</span></div>
{insider_chart(m, W=1120, H=210)}"""

    exhaust = f'{mp["quarters_to_exhaustion"]:.1f} qtrs' if mp["quarters_to_exhaustion"] is not None else "&mdash;"
    refill = f'{mp["median_refill_days"]}d' if mp["median_refill_days"] else "&mdash;"
    mutil = f'{mp["median_plan_utilization_pct"]}%' if mp["median_plan_utilization_pct"] is not None else "&mdash;"

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(tick)} &mdash; ATM issuance</title><style>{CSS}</style></head><body>
<div class="hd">
  <div><h1><span class="tk">{esc(tick)}</span> &middot; {esc(comp)} &mdash; ATM issuance tear sheet</h1>
  <div class="sub">{esc(meta.get("sector",""))} &middot; mcap {esc(meta.get("mcap_label",""))} &middot; as of {esc(meta.get("asof", str(m["asof"])))}</div>
  <div class="verdict">{meta.get("verdict","")}</div></div>
  <div class="meta">{f'<img src="data:image/png;base64,{LOGO}" alt="VerityData"/>' if LOGO else ''}<br/>data: Verity / InsiderScore</div>
</div>

<div class="take"><span class="lbl">ISSUANCE READ</span>{meta.get("lead","")}</div>

<div class="sech">Capacity &mdash; the reservoir <span class="hint">what remains authorized, the pace it drains, and the refill habit</span></div>
<div class="headrow">
  <div class="chart">{capacity_chart(m)}</div>
  <div class="side">
    <div class="pstat"><div class="pstat-l">Live capacity</div><div class="pstat-v"><span class="big">{dollars_label(mp["current_remaining_capacity"],1)}</span></div></div>
    <div class="pstat"><div class="pstat-l">Trailing-4q pace &middot; runway at that pace</div><div class="pstat-v">{dollars_label(mp["trailing4q_pace_per_qtr"],1) if mp["trailing4q_pace_per_qtr"] else "&mdash;"}<small>/qtr</small> &middot; {exhaust}</div></div>
    <div class="pstat"><div class="pstat-l">Programs filed</div><div class="pstat-v">{mp["refill_count"]}<small> &middot; median refill {refill}</small></div></div>
    <div class="pstat"><div class="pstat-l">Median utilization of retired plans</div><div class="pstat-v">{mutil}</div></div>
    <div class="read">{meta.get("capacity_read","")}</div>
  </div>
</div>

<div class="sech">Program to date <span class="hint">every price here is a disclosed print, not a quote</span></div>
<div class="stats-inline">
  <div class="pstat"><div class="pstat-l">Total raised / shares issued</div><div class="pstat-v">{dollars_label(mp["total_raised"],1)} <small>&middot; {mp["total_shares_issued"]/1e6:,.0f}M sh &asymp; {mp["cum_pct_of_shares_out"]:.0f}% of today's count</small></div></div>
  <div class="pstat"><div class="pstat-l">Blended VWAP (all priced tranches)</div><div class="pstat-v">${mp["blended_vwap"]:,.2f}</div></div>
  <div class="pstat"><div class="pstat-l">Trailing-12m blended VWAP</div><div class="pstat-v">{f'${mp["blended_vwap_12m"]:,.2f}' if mp["blended_vwap_12m"] else "&mdash;"}</div></div>
  <div class="pstat"><div class="pstat-l">Raised, trailing 12m</div><div class="pstat-v">{dollars_label(mp["raised_12m"],1)}</div></div>
  <div class="pstat"><div class="pstat-l">Last reported sale</div><div class="pstat-v">{esc(mp["last_reported_sale_date"])}</div></div>
</div>

{insider_html}

<div class="sech">Program economics &amp; ledger <span class="hint">what the pipe costs, plan by plan</span></div>
<div class="stats-inline">
  <div class="pstat"><div class="pstat-l">Agent commission (current plan)</div><div class="pstat-v">{comm_txt}</div></div>
  <div class="pstat"><div class="pstat-l">Est. cumulative agent fees</div><div class="pstat-v">{"&le;" if mp["fees_are_cap"] else ""}{dollars_label(mp["est_agent_fees"])}</div></div>
  <div class="pstat"><div class="pstat-l">Sold via forward sale</div><div class="pstat-v">{dollars_label(mp["forward_sale_dollars"],1)}<small> settles later; dilution precedes the share count</small></div></div>
</div>
<table class="ledger"><tr><th>plan</th><th>filed</th><th>via</th><th style="text-align:right">authorized*</th><th style="text-align:right">sold under</th><th style="text-align:right">used</th><th>fee</th><th>terminal event</th></tr>
{''.join(led)}</table>

<div class="ft"><b>Sources &amp; method.</b> Verity / InsiderScore ATM program announcements ({len(m['ledger'])} programs), periodic ATM sales disclosures ({len(m['rows'])} tranches after de-duplication of {m['dropped_dupes']} restated rows; {m['excluded']} excluded where the printed price is inconsistent with neighboring prints, typically split-adjustment artifacts), and insider Form 4 transactions ({len(m['ins_rows'])} open-market prints). <b>No market-data feed is used</b>: every price shown is a disclosed print &mdash; a tranche's realized price per share or an insider transaction price &mdash; never a quote. Quarter-VWAP tranches (10-Q/10-K rows) average a full quarter of selling; dated tranches (8-K/PR/424B5) cover tighter windows. "Authorized*" includes subsequent increases. Blended VWAP is total dollars &divide; total shares across priced tranches. Agent fees estimated as tranche dollars &times; the plan's stated commission rate{' (stated as a cap, so shown as an upper bound)' if mp['fees_are_cap'] else ''}. Capacity reservoir is reconstructed from plan events and sales draws and may differ modestly from prospectus-stated remainders due to fees and rounding. {meta.get("footer_extra","")} Descriptive, not investment advice.</div>
</body></html>"""
    return html

# ----------------------------- main --------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--announce", required=True)
    ap.add_argument("--sales", required=True)
    ap.add_argument("--insider")
    ap.add_argument("--meta")
    ap.add_argument("--output")
    ap.add_argument("--asof", help="run date YYYY-MM-DD (default: today); the blind window is measured to this date")
    ap.add_argument("--metrics-only", action="store_true")
    a = ap.parse_args()

    announce = load_csv(a.announce)
    sales = load_csv(a.sales)
    insider = load_csv(a.insider) if a.insider else []
    m = compute(announce, sales, insider, pdate(a.asof) if a.asof else None)

    if a.metrics_only or not a.meta:
        print(json.dumps(metrics_public(m), indent=1))
        return

    meta = json.load(open(a.meta))
    html = build_html(meta, m)
    with open(a.output, "w") as f:
        f.write(html)
    print(f"HTML: {a.output}")
    print(json.dumps(metrics_public(m), indent=1))

if __name__ == "__main__":
    main()
