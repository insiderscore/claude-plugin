#!/usr/bin/env python3
"""Render a sortable "new LTIP metrics" screen from a spec JSON.

One self-contained HTML file in the VerityData orientation-table visual
language: each company is a row comparing its PRIOR LTIP grant cycle to its
LATEST cycle, surfacing metrics that are NEW (present in latest, absent in
prior). New metrics render as orange chips (orange = the scarce signal, same
convention as the orientation table); carried-over metrics are grey; dropped
metrics are struck-through and faint. Column headers are click-to-sort. No
build step, no dependencies, no external assets — the Verity logo is inlined.

Usage:
    python3 build_new_ltip_table.py --spec SPEC.json --output OUT.html

Spec JSON schema (see assets/example_spec.json for a full one):
{
  "group": "string — what universe this is (fund, watchlist, sector, list)",
  "asof": "Month Year",
  "takeaway": "1-3 sentence cross-sectional read",
  "classification_rule": "methodology line shown in footer",
  "footer": "source line shown in footer",
  "points": [
     {"ticker","company",
      "prior_cycle":"FY24-26", "latest_cycle":"FY26-28",
      "new":["Agentforce & Data 360 ARR","Margin & Growth"],   # base names, present latest / absent prior
      "carried":["Relative TSR","Non-GAAP Operating Margin"],  # in both
      "dropped":[],                                            # in prior, gone from latest
      "note"?: "free text — what the new metric signals" }
  ],
  "no_change": [ {"ticker","reason"}, ... ],   # optional: scanned, no new metric
  "not_screened": [ {"ticker","reason"}, ... ] # optional: couldn't compare
}

A company appears in `points` only if it has >=1 NEW metric (an actual hit).
`no_change` lists names that were comparable but introduced nothing new;
`not_screened` lists names with <2 metric-bearing cycles, foreign filers, etc.
"""
import argparse, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_logo():
    p = os.path.join(HERE, "verity_logo_b64.txt")
    return open(p).read().strip() if os.path.exists(p) else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec))

    pts = []
    for p in spec["points"]:
        new = p.get("new", [])
        if not new:
            raise SystemExit(f"{p['ticker']} is in points but has no new metrics; "
                             f"move it to no_change instead")
        pts.append({
            "ticker": p["ticker"], "company": p["company"],
            "prior_cycle": p.get("prior_cycle", ""), "latest_cycle": p.get("latest_cycle", ""),
            "new": new, "carried": p.get("carried", []), "dropped": p.get("dropped", []),
            "n_new": len(new), "note": p.get("note", ""),
        })

    data_json = json.dumps(pts)
    nc_json = json.dumps(spec.get("no_change", []))
    ns_json = json.dumps(spec.get("not_screened", []))
    logo = load_logo()

    doc = TEMPLATE
    repl = {
        "__GROUP__": html.escape(spec.get("group", "")),
        "__N__": str(len(pts)),
        "__LOGO__": logo,
        "__ASOF__": html.escape(spec.get("asof", "")),
        "__TAKE__": html.escape(spec.get("takeaway", "")),
        "__RULE__": html.escape(spec.get("classification_rule", "")),
        "__FOOT__": html.escape(spec.get("footer", "")),
        "__DATA__": data_json,
        "__NC__": nc_json,
        "__NS__": ns_json,
    }
    for k, v in repl.items():
        doc = doc.replace(k, v)
    open(a.output, "w").write(doc)
    print(f"OK: {len(pts)} hits, {len(spec.get('no_change', []))} no-change, "
          f"{len(spec.get('not_screened', []))} not-screened -> {a.output}")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>New LTIP Metrics &mdash; screen</title>
<style>
 :root {
  --new:#f14b25; --carry:#9a9a9a; --drop:#bbb;
  --ink:#1a1a1a; --mut:#666; --faint:#999; --line:#f0f0f0; --rule:#ccc; --note:#5b7a99;
 }
 * { box-sizing:border-box; }
 body { margin:0; padding:30px 40px; background:#fff; color:var(--ink);
   font:13px/1.45 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }
 .hd { display:flex; justify-content:space-between; align-items:flex-start;
   border-bottom:2px solid var(--ink); padding-bottom:10px; }
 h1 { font-size:19px; margin:0; }
 .sub { color:var(--mut); margin-top:3px; }
 .meta { text-align:right; color:var(--faint); font-size:11px; white-space:nowrap; }
 .meta img { height:26px; }
 .take { border-left:3px solid var(--new); background:#fafafa; padding:10px 14px;
   margin:16px 0 6px; max-width:1000px; }
 .take .lbl { font-size:10px; letter-spacing:.08em; color:var(--faint); font-weight:700; }
 .legend { margin:12px 0 8px; font-size:11px; color:#444; }
 .legend .chip { display:inline-block; padding:1px 7px; margin:0 4px 0 14px; border-radius:9px;
   font-size:10px; vertical-align:1px; }
 .legend .chip:first-of-type { margin-left:6px; }
 table { border-collapse:collapse; width:100%; }
 thead th { font-size:10px; letter-spacing:.05em; text-transform:uppercase; color:#888;
   text-align:left; padding:7px 8px 5px 0; border-bottom:1px solid var(--rule);
   font-weight:600; cursor:pointer; user-select:none; white-space:nowrap; position:relative; }
 thead th.n { text-align:right; width:54px; }
 thead th.cyc { width:120px; }
 thead th.mx { cursor:default; }
 thead th.nt { cursor:default; padding-left:14px; }
 thead th .ar { color:var(--new); font-size:9px; margin-left:3px; }
 thead th:hover:not(.mx):not(.nt) { color:var(--ink); }
 tbody td { padding:5px 8px 5px 0; border-bottom:1px solid var(--line); vertical-align:top; }
 td.tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; width:46px; }
 td.co { color:var(--mut); font-size:11.5px; width:150px; }
 td.cyc { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:10.5px; color:var(--mut);
   white-space:nowrap; width:120px; }
 td.cyc .arw { color:var(--faint); margin:0 3px; }
 td.cyc .lt { color:var(--ink); font-weight:700; }
 td.n { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; font-size:13px;
   color:var(--new); text-align:right; width:54px; }
 td.mx { line-height:1.9; }
 .chip { display:inline-block; padding:1px 8px; margin:0 4px 3px 0; border-radius:9px;
   font-size:11px; white-space:nowrap; }
 .chip.new { background:var(--new); color:#fff; font-weight:600; }
 .chip.carry { background:#f0f0f0; color:#555; border:1px solid #e0e0e0; }
 .chip.drop { background:#fff; color:var(--drop); border:1px dashed #d8d8d8;
   text-decoration:line-through; }
 td.nt { color:var(--note); font-size:10.5px; padding-left:14px; max-width:240px; }
 .blk { margin-top:18px; border-top:1px solid var(--rule); padding-top:8px; color:var(--mut); font-size:11px; }
 .blk b { color:var(--ink); }
 .blk .row { margin:2px 0; }
 .blk .row .tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; color:var(--ink); }
 .ft { margin-top:14px; color:var(--faint); font-size:10.5px; }
 @media (max-width:760px){ body{padding:18px;} td.co,th.co{display:none;} td.nt,th.nt{display:none;} }
</style></head><body>
<div class="hd">
 <div><h1>New LTIP Metrics &mdash; screen</h1>
  <div class="sub">__GROUP__ &nbsp;&middot;&nbsp; __N__ names with a new metric &nbsp;&middot;&nbsp; latest grant cycle vs. prior, metric-set diff</div></div>
 <div class="meta"><img src="data:image/png;base64,__LOGO__"><br>As of __ASOF__</div>
</div>
<div class="take"><span class="lbl">WHAT IT MEANS&ensp;</span>__TAKE__</div>
<div class="legend">Metric vs. prior cycle:
 <span class="chip new">new</span>
 <span class="chip carry">carried over</span>
 <span class="chip drop">dropped</span>
 &nbsp;&middot;&nbsp; click a column to sort</div>
<table>
 <thead><tr>
  <th data-k="ticker" data-t="str">Ticker<span class="ar"></span></th>
  <th class="co" data-k="company" data-t="str">Company<span class="ar"></span></th>
  <th class="cyc" data-k="latest_cycle" data-t="str">Prior &rarr; latest<span class="ar"></span></th>
  <th class="n" data-k="n_new" data-t="num" title="count of new metrics"># new<span class="ar"></span></th>
  <th class="mx">Latest-cycle metric set (new highlighted)</th>
  <th class="nt">What it signals</th>
 </tr></thead>
 <tbody id="tb"></tbody>
</table>
<div class="blk" id="ncb"></div>
<div class="blk" id="nsb"></div>
<div class="ft">__RULE__<br>__FOOT__</div>
<script>
const DATA = __DATA__;
const NC = __NC__;
const NS = __NS__;
function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function chips(p){
  let s = '';
  p.new.forEach(m => s += `<span class="chip new">${esc(m)}</span>`);
  p.carried.forEach(m => s += `<span class="chip carry">${esc(m)}</span>`);
  p.dropped.forEach(m => s += `<span class="chip drop">${esc(m)}</span>`);
  return s;
}
function cyc(p){
  return `${esc(p.prior_cycle||'\\u2014')}<span class="arw">\\u2192</span>`+
         `<span class="lt">${esc(p.latest_cycle||'\\u2014')}</span>`;
}
// default sort: most new metrics first — the headline (biggest design change up top)
let sortKey='n_new', sortDir=-1;
function render(){
  const rows = DATA.slice().sort((a,b)=>{
    let av=a[sortKey], bv=b[sortKey], d;
    if (typeof av === 'string') d = av.localeCompare(bv);
    else d = av - bv;
    if (d===0 && sortKey!=='ticker') d = a.ticker.localeCompare(b.ticker);
    return d*sortDir;
  });
  document.getElementById('tb').innerHTML = rows.map(p=>
    `<tr><td class="tk">${esc(p.ticker)}</td><td class="co">${esc(p.company)}</td>`+
    `<td class="cyc">${cyc(p)}</td>`+
    `<td class="n">${p.n_new}</td>`+
    `<td class="mx">${chips(p)}</td>`+
    `<td class="nt">${esc(p.note||'')}</td></tr>`).join('');
  document.querySelectorAll('thead th[data-k]').forEach(th=>{
    th.querySelector('.ar').textContent =
      th.dataset.k===sortKey ? (sortDir<0?'\\u25BC':'\\u25B2') : '';
  });
}
document.querySelectorAll('thead th[data-k]').forEach(th=>{
  th.addEventListener('click',()=>{
    const k = th.dataset.k;
    if (k===sortKey){ sortDir = -sortDir; }
    else { sortKey = k; sortDir = (th.dataset.t==='num') ? -1 : 1; }
    render();
  });
});
document.getElementById('ncb').innerHTML =
  NC.length ? `<b>Comparable, no new metric (${NC.length}):</b>` +
    NC.map(x=>`<div class="row"><span class="tk">${esc(x.ticker)}</span> ${esc(x.reason)}</div>`).join('') : '';
document.getElementById('nsb').innerHTML =
  NS.length ? `<b>Not screened (${NS.length}):</b>` +
    NS.map(x=>`<div class="row"><span class="tk">${esc(x.ticker)}</span> ${esc(x.reason)}</div>`).join('') : '';
render();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
