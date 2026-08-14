"""PDFSpark HTML -> PDF backend (https://pdfspark.dev).

The alternative to the built-in Typst renderer. Typst stays the default because
it is offline, deterministic, and adds no network hop; PDFSpark is worth having
because HTML/CSS is a far more familiar thing to hand-tweak than Typst markup,
and because the resulting PDF is Chromium-rendered with selectable text.

We talk to the REST API directly rather than through `pdfspark-mcp`. Two
reasons: an MCP stdio server cannot be spawned from a Vercel Python function,
and as of 1.3.0 that package is broken as published — its `files` allowlist
ships only `mcp-server.js`, which then fails on `require('./mcp-tools')`. The
MCP server is still useful *interactively* (see .mcp.json); it is just not
something the engine can depend on.

Endpoints (discovered from pdfspark.dev, which publishes no OpenAPI document):
    POST /api/v1/pdf/from-html   {html, format, ...} -> application/pdf bytes
    POST /api/v1/pdf/from-url    {url, ...}
    POST /api/v1/pdf/merge       {pdfs: [base64, ...]}
    POST /api/v1/pdf/split       {pdf: base64, pages: "1-3,5"}
No API key is required.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .errors import RenderError

DEFAULT_BASE_URL = "https://pdfspark.dev"
FROM_HTML_PATH = "/api/v1/pdf/from-html"

# The service renders with headless Chromium; a resume takes ~1.2s. Allow
# generously for a cold browser pool without hanging a serverless request.
DEFAULT_TIMEOUT = 45.0


def base_url() -> str:
    return (os.environ.get("PDFSPARK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def html_to_pdf(
    html: str,
    *,
    page_format: str = "Letter",
    landscape: bool = False,
    scale: float | None = None,
    margin: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    """Convert an HTML document to PDF bytes.

    Margins and page size are already baked into the document's `@page` CSS by
    `html_render`, so `margin`/`scale` stay unset by default — passing them here
    would silently fight the stylesheet.
    """
    if not html.strip():
        raise RenderError("Refusing to send an empty document to PDFSpark.")

    payload: dict[str, object] = {"html": html, "format": page_format}
    if landscape:
        payload["landscape"] = True
    if scale is not None:
        payload["scale"] = scale
    if margin is not None:
        payload["margin"] = margin

    url = base_url() + FROM_HTML_PATH
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/pdf"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            content_type = (response.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise RenderError(
            f"PDFSpark returned HTTP {exc.code} for {url}. {detail}".strip(),
        ) from exc
    except urllib.error.URLError as exc:
        raise RenderError(
            f"Could not reach PDFSpark at {url}: {exc.reason}. "
            "Set ACHILLES_RENDERER=typst to render locally instead.",
        ) from exc
    except TimeoutError as exc:
        raise RenderError(f"PDFSpark timed out after {timeout:g}s.") from exc

    # A JSON error body with a 200 would otherwise be written out as a .pdf and
    # only fail later, inside pypdf, with a far less obvious message.
    if "application/pdf" not in content_type and not body.startswith(b"%PDF"):
        raise RenderError(
            f"PDFSpark did not return a PDF (content-type {content_type!r}): "
            f"{body[:200]!r}"
        )
    return body


def healthy(timeout: float = 10.0) -> bool:
    """Cheap liveness probe, for surfacing backend availability in the UI."""
    try:
        with urllib.request.urlopen(base_url() + "/health", timeout=timeout) as response:
            return json.loads(response.read()).get("status") == "ok"
    except Exception:
        return False
