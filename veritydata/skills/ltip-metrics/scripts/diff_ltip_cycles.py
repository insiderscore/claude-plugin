#!/usr/bin/env python3
"""First-pass cycle differ for the new-LTIP-metrics screen.

Reads one or more Verity get_longterm_incentive_plans JSON payloads, orders each
company's metric-bearing cycles by startyear, and prints the latest-vs-prior
metric-set diff (new / carried / dropped) using tranche-normalization and a
canonical-synonym map.

IMPORTANT: this is a FIRST PASS. The `new` list it prints is *candidate*-new.
You MUST still apply Step 5 of SKILL.md by hand -- filter out relabels and
reframes (abbreviations, window prefixes, "Relative" added/dropped, rate<->dollar
recasts, reversions) by checking each candidate-new metric against the `dropped`
list for the same underlying measure. Only genuinely-new measures become hits.

Input files may be either a bare JSON array of plan records, or the auto-saved
tool-result wrapper [{"type":"text","text":"<json>"}]. Both are handled.

Usage:
    python3 diff_ltip_cycles.py chunk1.json chunk2.json ...
"""
import json, re, sys

TRANCHE   = re.compile(r'\s*[-\u2013]\s*(year|yr|tranche)\s*\.?\s*[ivx0-9]+\s*$', re.I)
YEARPAREN = re.compile(r'\s*\((?:fy)?\s*\d{2,4}\)\s*$', re.I)
YEARTAIL  = re.compile(r'\s*\(\d{4}\)\s*$')
LEAD_YEAR = re.compile(r'^\s*\d{4}\s+')
MULTISPACE = re.compile(r'\s+')

SYN = {
    'relative total shareholder return': 'relative tsr',
    'relative total shareholder return (tsr)': 'relative tsr',
    'relative total shareholder return (rtsr)': 'relative tsr',
    'relative total stockholder return': 'relative tsr',
    'r-tsr': 'relative tsr', 'rtsr': 'relative tsr', 'rtsr psus': 'relative tsr',
    'peer-relative tsr': 'relative tsr', 'peer relative tsr': 'relative tsr',
    'tsr percentile vs. relative peer group': 'relative tsr',
    'relative percentile rank tsr': 'relative tsr',
    'tsr percentile': 'relative tsr', 'percentile measurement': 'relative tsr',
    '3-year relative tsr cagr': 'relative tsr cagr',
    'adj eps growth': 'adjusted eps growth', 'eps growth': 'adjusted eps growth',
    'earnings per share (eps) growth': 'adjusted eps growth',
    'eps psus': 'adjusted eps', 'earnings per share (eps)': 'adjusted eps',
    'non-gaap earnings per share (eps)': 'non-gaap eps',
    'average annual adjusted rotce': 'average adjusted rotce',
    'average annual adj. rotce': 'average adjusted rotce',
    'average annual rotce': 'average adjusted rotce',
    'oeps': 'eps',
    'non-gaap operating margin dollars': 'non-gaap operating margin',
}

def norm(name):
    s = name or ""
    prev = None
    while prev != s:
        prev = s
        s = TRANCHE.sub('', s); s = YEARPAREN.sub('', s); s = YEARTAIL.sub('', s)
    s = LEAD_YEAR.sub('', s)
    s = MULTISPACE.sub(' ', s).strip().lower()
    return SYN.get(s, s)

def load(path):
    raw = json.load(open(path))
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and raw[0].get('type') == 'text':
        return json.loads(raw[0]['text'])
    return raw

def weighted_metrics(plan):
    out = set()
    for m in plan.get('metrics', []) or []:
        w = m.get('weight')
        if w is not None and w <= 0:
            continue
        base = norm(m.get('original_name') or m.get('name'))
        if base:
            out.add(base)
    return out

def fy(p):
    a, b = p.get('startyear'), p.get('endyear')
    return f"FY{str(a)[2:]}\u2013{str(b)[2:]}" if a and b else str(a or '?')

def main(paths):
    recs = []
    for p in paths:
        recs.extend(load(p))
    by_t = {}
    for r in recs:
        by_t.setdefault(r['ticker'], []).append(r)

    hits, nochange, notscreened = [], [], []
    for tk, plans in by_t.items():
        cname = plans[0].get('companyname', tk)
        mb = [p for p in plans if weighted_metrics(p)]
        mb.sort(key=lambda p: (p.get('startyear') or 0))
        if len(mb) < 2:
            notscreened.append((tk, "only one metric-bearing cycle" if len(mb) == 1
                                    else "no weighted-metric LTIP cycle"))
            continue
        latest, prior = mb[-1], mb[-2]
        ls, ps = weighted_metrics(latest), weighted_metrics(prior)
        new, carried, dropped = sorted(ls - ps), sorted(ls & ps), sorted(ps - ls)
        if new:
            hits.append((tk, cname, fy(prior), fy(latest), new, carried, dropped))
        else:
            nochange.append((tk, carried, fy(prior), fy(latest)))

    print(f"=== {len(by_t)} tickers ===\n")
    print(f"CANDIDATE HITS ({len(hits)}) -- apply Step 5 relabel filter before finalizing:")
    for tk, cn, pc, lc, new, carr, drop in sorted(hits, key=lambda x: -len(x[4])):
        print(f"  {tk:6s} {pc}->{lc}  +{len(new)} candidate-new")
        print(f"         candidate-new: {new}")
        print(f"         carried:       {carr}")
        if drop: print(f"         dropped:       {drop}   <- check each candidate-new against these for relabels")
    print(f"\nNO CANDIDATE-NEW ({len(nochange)}): {[x[0] for x in nochange]}")
    print(f"\nNOT SCREENED ({len(notscreened)}):")
    for tk, why in notscreened:
        print(f"  {tk}: {why}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: diff_ltip_cycles.py <plan.json> [more.json ...]")
    main(sys.argv[1:])
