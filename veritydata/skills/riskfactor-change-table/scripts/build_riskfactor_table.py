#!/usr/bin/env python3
"""Render a sortable risk-factor change table from a spec JSON.

Same house style as the incentive-orientation table, but each company's bar
encodes the CHANGE ANATOMY of its latest 10-K/10-Q Item 1A risk section:
what fraction of risk factors were newly added, materially rewritten (major),
moderately changed, minorly changed, or carried forward unchanged. Deleted
factors are shown as a separate count (they aren't in the current section).
Columns are click-to-sort. Inline notes annotate what actually changed for
the biggest movers.

Usage:
    python3 build_riskfactor_table.py --spec SPEC.json --output OUT.html

Spec point fields:
  ticker, company, date, form, new, deleted, big, medium, small, tiny,
  unchanged, total, unusual, note?
The bar segments are: new, big(=major), medium(=moderate),
small+tiny(=minor), unchanged. They sum to `total` (current-section factors).
`deleted` is rendered as a separate left-of-bar marker, not part of the bar.
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
        total = p["total"]
        minor = p["small"] + p["tiny"]
        # changed = everything that moved (new + big + medium + minor); churn share
        changed = p["new"] + p["big"] + p["medium"] + minor
        pts.append({
            "ticker": p["ticker"], "company": p["company"],
            "date": p.get("date", ""), "form": p.get("form", ""),
            "new": p["new"], "deleted": p["deleted"], "big": p["big"],
            "medium": p["medium"], "minor": minor, "unchanged": p["unchanged"],
            "total": total, "changed": changed, "unusual": p.get("unusual", 0),
            "note": p.get("note", ""),
        })

    data_json = json.dumps(pts)
    np_json = json.dumps(spec.get("not_plotted", []))
    logo = load_logo()

    doc = TEMPLATE
    repl = {
        "__GROUP__": html.escape(spec.get("group", "")),
        "__N__": str(len(pts)),
        "__LOGO__": logo,
        "__ASOF__": html.escape(spec.get("asof", "")),
        "__WINDOW__": html.escape(spec.get("filing_window", "")),
        "__TAKE__": html.escape(spec.get("takeaway", "")),
        "__FOOT__": html.escape(spec.get("footer", "Source: Verity (InsiderScore) SEC filing risk-factor change data. Item 1A diffs vs. the prior annual filing; counts classify each factor as new, deleted, or changed by magnitude (major/moderate/minor). Annotations summarize the actual new and major-rewritten factors. Not investment advice.")),
        "__DATA__": data_json,
        "__NP__": np_json,
    }
    for k, v in repl.items():
        doc = doc.replace(k, v)
    open(a.output, "w").write(doc)
    print(f"OK: {len(pts)} rows, {len(spec.get('not_plotted', []))} not plotted -> {a.output}")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk-Factor Changes &mdash; sortable</title>
<style>
 :root {
  --new:#f14b25; --big:#c23616; --med:#e58e26; --minor:#cdd3d8; --unch:#eef1f3; --del:#8a8f96;
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
 .legend .sw { display:inline-block; width:10px; height:10px; margin:0 4px 0 14px;
   vertical-align:-1px; border:1px solid #bbb; }
 .legend .sw:first-of-type { margin-left:6px; }
 table { border-collapse:collapse; width:100%; }
 thead th { font-size:10px; letter-spacing:.05em; text-transform:uppercase; color:#888;
   text-align:left; padding:7px 8px 5px 0; border-bottom:1px solid var(--rule);
   font-weight:600; cursor:pointer; user-select:none; white-space:nowrap; position:relative; }
 thead th.n { text-align:right; width:34px; }
 thead th.bc { cursor:default; width:280px; }
 thead th.nt { cursor:default; padding-left:14px; }
 thead th .ar { color:var(--new); font-size:9px; margin-left:3px; }
 thead th:hover:not(.bc):not(.nt) { color:var(--ink); }
 tbody td { padding:3.5px 8px 3.5px 0; border-bottom:1px solid var(--line); vertical-align:middle; }
 td.tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; width:46px; }
 td.co { color:var(--mut); font-size:11.5px; width:150px; }
 td.dt { color:var(--faint); font-size:10.5px; width:74px; white-space:nowrap; }
 td.bc { width:280px; }
 .bar { position:relative; height:14px; width:280px; font-size:0; border:1px solid #d8d8d8;
   display:flex; }
 .bar i { display:inline-block; height:100%; }
 td.n { font-family:ui-monospace,Menlo,Consolas,monospace; font-size:11px; color:#444;
   text-align:right; width:34px; }
 td.nnew { color:var(--new); font-weight:700; }
 td.ndel { color:var(--del); }
 td.nbig { color:var(--big); font-weight:700; }
 td.nt { color:var(--note); font-size:10.5px; padding-left:14px; min-width:240px; }
 .npb { margin-top:18px; border-top:1px solid var(--rule); padding-top:8px; color:var(--mut); font-size:11px; }
 .npb b { color:var(--ink); }
 .npr { margin:2px 0; }
 .npr .tk { font-family:ui-monospace,Menlo,Consolas,monospace; font-weight:700; color:var(--ink); }
 .ft { margin-top:14px; color:var(--faint); font-size:10.5px; }
 @media (max-width:820px){ body{padding:18px;} td.co,th.co,td.dt,th.dt{display:none;} td.nt,th.nt{display:none;} .bar,td.bc,th.bc{width:150px;} .bar{width:150px;} }
</style></head><body>
<div class="hd">
 <div><h1>Risk-Factor Changes &mdash; sortable</h1>
  <div class="sub">__GROUP__ &nbsp;&middot;&nbsp; __N__ companies &nbsp;&middot;&nbsp; __WINDOW__</div></div>
 <div class="meta"><img src="data:image/png;base64,__LOGO__"><br>As of __ASOF__</div>
</div>
<div class="take"><span class="lbl">WHAT IT MEANS&ensp;</span>__TAKE__</div>
<div class="legend">Composition of the current risk section:
 <span class="sw" style="background:var(--new)"></span>new
 <span class="sw" style="background:var(--big)"></span>major rewrite
 <span class="sw" style="background:var(--med)"></span>moderate
 <span class="sw" style="background:var(--minor)"></span>minor
 <span class="sw" style="background:var(--unch)"></span>unchanged
 &nbsp;&middot;&nbsp; <b>D</b> = deleted (dropped from prior filing) &nbsp;&middot;&nbsp; click a column to sort</div>
<table>
 <thead><tr>
  <th data-k="ticker" data-t="str">Ticker<span class="ar"></span></th>
  <th class="co" data-k="company" data-t="str">Company<span class="ar"></span></th>
  <th class="dt" data-k="date" data-t="str">Filed<span class="ar"></span></th>
  <th class="bc">Change anatomy</th>
  <th class="n" data-k="new" data-t="num" title="new factors">New<span class="ar"></span></th>
  <th class="n" data-k="deleted" data-t="num" title="deleted factors">Del<span class="ar"></span></th>
  <th class="n" data-k="big" data-t="num" title="major rewrites">Maj<span class="ar"></span></th>
  <th class="n" data-k="medium" data-t="num" title="moderate changes">Mod<span class="ar"></span></th>
  <th class="n" data-k="changed" data-t="num" title="total changed">Chg<span class="ar"></span></th>
  <th class="n" data-k="total" data-t="num" title="total factors">Tot<span class="ar"></span></th>
  <th class="nt">What changed (top movers)</th>
 </tr></thead>
 <tbody id="tb"></tbody>
</table>
<div class="npb" id="npb"></div>
<div class="ft">__FOOT__</div>
<script>
const DATA = __DATA__;
const NP = __NP__;
const COL = {new:'var(--new)', big:'var(--big)', medium:'var(--med)', minor:'var(--minor)', unchanged:'var(--unch)'};
function bar(p){
  const tot = p.total || 1;
  let s = '<div class="bar" title="'+p.changed+' of '+p.total+' factors changed">';
  for (const [k,c] of [['new',COL.new],['big',COL.big],['medium',COL.medium],['minor',COL.minor],['unchanged',COL.unchanged]]){
    const v = p[k]||0;
    if (v>0) s += `<i style="width:${(v/tot*100).toFixed(2)}%;background:${c}"></i>`;
  }
  return s + '</div>';
}
function delMark(p){ return p.deleted>0 ? `<span style="color:var(--del)">${p.deleted}</span>` : '<span style="color:#ccc">&middot;</span>'; }
// default sort: total changed, descending — biggest rewrites first
let sortKey='changed', sortDir=-1;
function render(){
  const rows = DATA.slice().sort((a,b)=>{
    let av=a[sortKey], bv=b[sortKey], d;
    if (typeof av === 'string') d = (av||'').localeCompare(bv||'');
    else d = av - bv;
    if (d===0 && sortKey!=='ticker') d = a.ticker.localeCompare(b.ticker);
    return d*sortDir;
  });
  document.getElementById('tb').innerHTML = rows.map(p=>
    `<tr><td class="tk">${p.ticker}</td><td class="co">${p.company}</td>`+
    `<td class="dt">${p.date}</td>`+
    `<td class="bc">${bar(p)}</td>`+
    `<td class="n nnew">${p.new||'<span style=color:#ccc>&middot;</span>'}</td>`+
    `<td class="n ndel">${delMark(p)}</td>`+
    `<td class="n nbig">${p.big||'<span style=color:#ccc>&middot;</span>'}</td>`+
    `<td class="n">${p.medium||'<span style=color:#ccc>&middot;</span>'}</td>`+
    `<td class="n">${p.changed}</td>`+
    `<td class="n">${p.total}</td>`+
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
  NP.length ? `<b>Not shown (${NP.length}):</b>` +
    NP.map(x=>`<div class="npr"><span class="tk">${x.ticker}</span> ${x.reason}</div>`).join('') : '';
render();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
