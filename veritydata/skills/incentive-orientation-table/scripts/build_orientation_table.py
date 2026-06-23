#!/usr/bin/env python3
"""Render a sortable incentive-orientation table from a spec JSON.

One self-contained HTML file: a graphic table where each company is a row
carrying a 100%-stacked bar of its four weighted-incentive shares
(profitability / growth / shareholder-return / other) plus the printed
numbers and a per-name note. Column headers are click-to-sort (numeric
shares descending-first, ticker/company alphabetical). No build step, no
dependencies, no external assets — the Verity logo is inlined as base64.

Usage:
    python3 build_orientation_table.py --spec SPEC.json --output OUT.html

Spec JSON schema (see assets/example_aventail_spec.json for a full one):
{
  "group": "string — what universe this is (fund, watchlist, sector)",
  "asof": "Month Year",
  "takeaway": "1-3 sentence cross-sectional read",
  "classification_rule": "methodology line shown in footer",
  "footer": "source line shown in footer",
  "points": [
     {"ticker","company","profitability","growth","sr","other",
      "note"?, "scope"?}   # four shares are 0..1 and sum to ~1
  ],
  "not_plotted": [ {"ticker","reason"}, ... ]   # optional
}
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
        note = p.get("note", "")
        if p.get("scope"):
            note = p["scope"] + (" &mdash; " + note if note else "")
        pts.append({
            "ticker": p["ticker"], "company": p["company"],
            "profitability": round(p["profitability"], 4), "growth": round(p["growth"], 4),
            "sr": round(p["sr"], 4), "other": round(p["other"], 4), "note": note,
        })

    # validate shares sum to ~1
    for p in pts:
        tot = p["profitability"] + p["growth"] + p["sr"] + p["other"]
        if abs(tot - 1) > 0.03:
            raise SystemExit(f"shares for {p['ticker']} sum to {tot:.3f}, not ~1")

    data_json = json.dumps(pts)
    np_json = json.dumps(spec.get("not_plotted", []))
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
        "__NP__": np_json,
    }
    for k, v in repl.items():
        doc = doc.replace(k, v)
    open(a.output, "w").write(doc)
    print(f"OK: {len(pts)} rows, {len(spec.get('not_plotted', []))} not plotted -> {a.output}")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Incentive Orientation &mdash; sortable table</title>
<style>
 :root {
  --prof:#1a1a1a; --grow:#f14b25; --sr:#9a9a9a; --oth:#e6e6e6;
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
 .take { border-left:3px solid var(--grow); background:#fafafa; padding:10px 14px;
   margin:16px 0 6px; max-width:1000px; }
 .take .lbl { font-size:10px; letter-spacing:.08em; color:var(--faint); font-weight:700; }
 .legend { margin:12px 0 8px; font-size:11px; color:#444; }
 .legend .sw { display:inline-block; width:10px; height:10px; margin:0 4px 0 14px;
   vertical-align:-1px; border:1px solid #bbb; }
 .legend .sw:first-of-type { margin-left:6px; }
 table { border-collapse:collapse; width:100%; }
 thead th { font-size:10px; letter-spacing:.05em; text-transform:uppercase; color:#888;
   text-align:left; padding:7px 8px 5px 0; border-bottom:1px solid var(--rule);
   font-weight:600; cursor:pointer; user-select:none; white-space:nowrap; position:relative; }
 thead th.n { text-align:right; width:42px; }
 thead th.bc { cursor:default; width:300px; }
 thead th.nt { cursor:default; padding-left:14px; }
 thead th .ar { color:var(--grow); font-size:9px; margin-left:3px; }
 thead th:hover:not(.bc):not(.nt) { color:var(--ink); }
 tbody td { padding:3.5px 8px 3.5px 0; border-bottom:1px solid var(--line); vertical-align:middle; }
 td.tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; width:46px; }
 td.co { color:var(--mut); font-size:11.5px; width:172px; }
 td.bc { width:300px; }
 .bar { position:relative; height:13px; width:300px; font-size:0; border:1px solid #d8d8d8; }
 .bar .tick { position:absolute; left:50%; top:-3px; bottom:-3px; width:0; border-left:1px dotted #aaa; }
 .bar i { display:inline-block; height:100%; }
 td.n { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; color:#444;
   text-align:right; width:42px; }
 td.np { font-weight:700; color:var(--ink); }
 td.ng { color:var(--grow); }
 td.nt { color:var(--note); font-size:10.5px; padding-left:14px; }
 .npb { margin-top:18px; border-top:1px solid var(--rule); padding-top:8px; color:var(--mut); font-size:11px; }
 .npb b { color:var(--ink); }
 .npr { margin:2px 0; }
 .npr .tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; color:var(--ink); }
 .ft { margin-top:14px; color:var(--faint); font-size:10.5px; }
 @media (max-width:760px){ body{padding:18px;} td.co,th.co{display:none;} td.nt,th.nt{display:none;} .bar,td.bc,th.bc{width:160px;} .bar{width:160px;} }
</style></head><body>
<div class="hd">
 <div><h1>Incentive Orientation &mdash; sortable</h1>
  <div class="sub">__GROUP__ &nbsp;&middot;&nbsp; __N__ companies &nbsp;&middot;&nbsp; AIP + LTIP blended 50/50, latest disclosed fiscal year</div></div>
 <div class="meta"><img src="data:image/png;base64,__LOGO__"><br>As of __ASOF__</div>
</div>
<div class="take"><span class="lbl">WHAT IT MEANS&ensp;</span>__TAKE__</div>
<div class="legend">Share of weighted incentive metrics:
 <span class="sw" style="background:var(--prof)"></span>profitability / returns
 <span class="sw" style="background:var(--grow)"></span>growth
 <span class="sw" style="background:var(--sr)"></span>shareholder return
 <span class="sw" style="background:var(--oth)"></span>other objectives
 &nbsp;&nbsp;(dotted tick = 50%) &nbsp;&middot;&nbsp; click a column to sort</div>
<table>
 <thead><tr>
  <th data-k="ticker" data-t="str">Ticker<span class="ar"></span></th>
  <th class="co" data-k="company" data-t="str">Company<span class="ar"></span></th>
  <th class="bc">Metric mix</th>
  <th class="n" data-k="profitability" data-t="num" title="profitability / returns">P<span class="ar"></span></th>
  <th class="n" data-k="growth" data-t="num" title="growth">G<span class="ar"></span></th>
  <th class="n" data-k="sr" data-t="num" title="shareholder return">S<span class="ar"></span></th>
  <th class="n" data-k="other" data-t="num" title="other objectives">O<span class="ar"></span></th>
  <th class="nt">Notes</th>
 </tr></thead>
 <tbody id="tb"></tbody>
</table>
<div class="npb" id="npb"></div>
<div class="ft">__RULE__<br>__FOOT__</div>
<script>
const DATA = __DATA__;
const NP = __NP__;
const COL = {profitability:'var(--prof)', growth:'var(--grow)', sr:'var(--sr)', other:'var(--oth)'};
function pct(v){ return v < 0.005 ? '&middot;' : Math.round(v*100); }
function bar(p){
  let s = '<div class="bar"><div class="tick"></div>';
  for (const [k,c] of [['profitability',COL.profitability],['growth',COL.growth],['sr',COL.sr],['other',COL.other]]){
    if (p[k] > 0.002) s += `<i style="width:${(p[k]*100).toFixed(2)}%;background:${c}"></i>`;
  }
  return s + '</div>';
}
// default sort: shareholder-return tilt (sr minus other), descending — the cross-sectional headline
let sortKey='sr', sortDir=-1;
function render(){
  const rows = DATA.slice().sort((a,b)=>{
    let av=a[sortKey], bv=b[sortKey], d;
    if (typeof av === 'string') d = av.localeCompare(bv);
    else d = av - bv;
    if (d===0 && sortKey!=='ticker') d = a.ticker.localeCompare(b.ticker);
    return d*sortDir;
  });
  document.getElementById('tb').innerHTML = rows.map(p=>
    `<tr><td class="tk">${p.ticker}</td><td class="co">${p.company}</td>`+
    `<td class="bc">${bar(p)}</td>`+
    `<td class="n np">${pct(p.profitability)}</td>`+
    `<td class="n ng">${pct(p.growth)}</td>`+
    `<td class="n">${pct(p.sr)}</td>`+
    `<td class="n">${pct(p.other)}</td>`+
    `<td class="nt">${p.note||''}</td></tr>`).join('');
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
document.getElementById('npb').innerHTML =
  NP.length ? `<b>Not plotted (${NP.length}):</b>` +
    NP.map(x=>`<div class="npr"><span class="tk">${x.ticker}</span> ${x.reason}</div>`).join('') : '';
render();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
