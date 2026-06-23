#!/usr/bin/env python3
"""
to_pdf.py — render a tear-sheet HTML file to a SINGLE-PAGE (un-paginated) PDF.

Hedge-fund analysts forward these to PMs, who can't easily open an HTML artifact.
A normal PDF export would slice the dense sheet across letter pages and break panels
mid-figure. Instead this renders the whole sheet as ONE continuous page sized exactly
to the content — scroll/zoom in any viewer, nothing chopped.

Uses headless Chromium (Playwright) so SVG, web fonts, CSS grid, the quadrant arrows
and concentric rings all render exactly as in the browser.

Usage:
  python3 to_pdf.py --html /path/CRUS_tearsheet.html --output /path/CRUS_tearsheet.pdf
  # optional: --width-px 1180 (CSS px of the sheet; default matches .sheet max-width)
"""
import argparse, pathlib
from playwright.sync_api import sync_playwright

# CSS px per inch in the print box (Chromium uses 96).
PX_PER_IN = 96.0

def render(html_path, out_path, width_px=1180, margin_px=24, scale=1.0):
    url = pathlib.Path(html_path).resolve().as_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Fix the viewport width to the sheet width so layout matches the on-screen design;
        # height is arbitrary here — we measure the real content height after load.
        page = browser.new_page(viewport={"width": width_px, "height": 1400},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        # Ensure web fonts are done so height measurement is correct.
        try:
            page.evaluate("document.fonts && document.fonts.ready")
            page.wait_for_timeout(250)
        except Exception:
            pass
        # Full content box: the .sheet element if present, else the body scroll height.
        dims = page.evaluate(
            """() => {
                const el = document.querySelector('.sheet') || document.body;
                const r = el.getBoundingClientRect();
                const h = Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight,
                    Math.ceil(r.bottom)
                );
                return {w: Math.ceil(r.width), h: Math.ceil(h)};
            }"""
        )
        content_w = width_px
        content_h = dims["h"] + margin_px  # small bottom breathing room
        # One page exactly the size of the content -> no pagination.
        page.pdf(
            path=out_path,
            width=f"{content_w/PX_PER_IN:.3f}in",
            height=f"{content_h/PX_PER_IN:.3f}in",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            scale=scale,
            prefer_css_page_size=False,
        )
        browser.close()
    return content_w, content_h

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--width-px", type=int, default=1180,
                    help="CSS pixel width of the sheet (default 1180, matches .sheet max-width)")
    a = ap.parse_args()
    w, h = render(a.html, a.output, width_px=a.width_px)
    print(f"wrote {a.output}  ({w}px x {h}px single page, {w/PX_PER_IN:.1f}in x {h/PX_PER_IN:.1f}in)")
