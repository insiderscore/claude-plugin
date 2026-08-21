#!/usr/bin/env python3
"""to_pdf.py — export the risk-factor table HTML to a single-page PDF.

Uses headless Chromium (Playwright) so the inline logo, bar segments, and
fonts render exactly as in the browser. The page is sized to the table's
actual rendered width and height so nothing is clipped and there is no
pagination. Usage:
  python3 to_pdf.py --html table.html --output table.pdf
"""
import argparse, pathlib
from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--width", type=int, default=1360,
                    help="render viewport width in px (default 1360)")
    a = ap.parse_args()
    src = pathlib.Path(a.html).resolve()
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": a.width, "height": 900})
        pg.goto(f"file://{src}")
        pg.wait_for_timeout(1000)  # let the inline logo + layout settle
        # measure the true content box so wide tables aren't clipped
        dims = pg.evaluate(
            "() => ({w: document.body.scrollWidth, h: document.documentElement.scrollHeight})"
        )
        w_px = max(dims["w"], a.width)
        h_px = dims["h"] + 24
        w_in, h_in = w_px / 96.0, h_px / 96.0
        pg.pdf(path=a.output, width=f"{w_in}in", height=f"{h_in}in",
               print_background=True, page_ranges="1")
        b.close()
    print(f"PDF: {a.output} ({w_in:.1f}in x {h_in:.1f}in, single page)")


if __name__ == "__main__":
    main()
