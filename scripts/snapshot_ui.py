"""Render the running dev server's UI to a PDF via PDFSpark.

pdfspark.dev cannot reach `localhost`, so `url_to_pdf` is not an option. Instead
we fetch the prerendered page ourselves, inline every stylesheet it links, drop
the scripts (the appearance is server-rendered; JS only adds interactivity), and
POST the resulting self-contained document to `from-html`.

    python scripts/snapshot_ui.py --url http://localhost:3000 --out out/ui.pdf

This is a visual smoke test: it proves the TUI's own CSS produces the intended
layout in a real Chromium, without needing a local browser install.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from achilles.pdfspark import html_to_pdf  # noqa: E402

_LINK_RE = re.compile(
    r"""<link\b[^>]*rel=["']?stylesheet["']?[^>]*>""", re.IGNORECASE
)
_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>", re.IGNORECASE | re.DOTALL)


def _fetch(url: str, *, timeout: float = 20.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def inline_page(url: str) -> str:
    html = _fetch(url)
    inlined = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal inlined
        href_match = _HREF_RE.search(match.group(0))
        if not href_match:
            return ""
        try:
            css = _fetch(urllib.parse.urljoin(url, href_match.group(1)))
        except Exception:
            return ""  # a stylesheet we cannot reach is better dropped than fatal
        inlined += 1
        return f"<style>\n{css}\n</style>"

    html = _LINK_RE.sub(replace, html)
    # Scripts would only re-hydrate; without them the render is deterministic.
    html = _SCRIPT_RE.sub("", html)
    print(f"  inlined {inlined} stylesheet(s), stripped scripts")
    return html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--out", default="out/ui.pdf")
    parser.add_argument("--format", dest="page_format", default="A3")
    parser.add_argument("--save-html", action="store_true")
    args = parser.parse_args()

    print(f"fetching {args.url}")
    try:
        html = inline_page(args.url)
    except Exception as exc:
        print(f"error: could not fetch {args.url}: {exc}", file=sys.stderr)
        print("Is the dev server running? `npm run dev`", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.save_html:
        out.with_suffix(".html").write_text(html, encoding="utf-8")

    print(f"rendering via PDFSpark ({len(html):,} chars of HTML)")
    out.write_bytes(html_to_pdf(html, page_format=args.page_format))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
