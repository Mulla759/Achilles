"""Resume -> PDF -> extracted text, via one of two interchangeable backends.

`typst` (default) uses the `typst` PyPI package — Rust bindings, not a `typst`
binary — so it runs unchanged on a Vercel Python function with nothing but
`pip install`, fully offline. A one-page compile takes ~0.7s cold, ~0.1s warm.
Data reaches the template through `sys_inputs` as JSON, so nothing is
string-interpolated into Typst source and no user text ever needs escaping.

`pdfspark` renders `html_render`'s HTML through pdfspark.dev's headless
Chromium. Slower and network-dependent, but HTML/CSS is much easier to hand-tune
than Typst markup. Select with `ACHILLES_RENDERER=pdfspark`.

Both return the same `RenderOutput`, so the density ladder, the keyword scan,
and the rubric are all backend-agnostic.
"""

from __future__ import annotations

import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pypdf
import typst

from .config import DEFAULT_TEMPLATE
from .errors import RenderError
from .models import Resume

# One-page fitting ladder. We compile at 0.0 (roomy) and walk tighter only as
# needed — squeezing leading is free, cutting a real accomplishment is not.
DENSITY_LADDER = (0.0, 0.3, 0.55, 0.75, 1.0)

BACKEND_TYPST = "typst"
BACKEND_PDFSPARK = "pdfspark"
BACKENDS = (BACKEND_TYPST, BACKEND_PDFSPARK)


def active_backend() -> str:
    """Which renderer to use, from ACHILLES_RENDERER.

    Defaults to Typst: it is offline, has no per-request network cost, and is
    what the one-page geometry was tuned against. An unrecognised value falls
    back rather than raising, so a typo in an env var can never take the whole
    app down.
    """
    choice = (os.environ.get("ACHILLES_RENDERER") or BACKEND_TYPST).strip().lower()
    return choice if choice in BACKENDS else BACKEND_TYPST


@dataclass
class RenderOutput:
    pdf: bytes
    text: str
    pages: int
    density: float
    typst_source: str


def _extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = len(reader.pages)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, pages


def _standalone_source(template_text: str, payload: str, density: float) -> str:
    """Inline the data so the downloaded .typ compiles without --input flags.

    Only `\\` and `"` are special inside a Typst string literal, so this
    substitution is safe for arbitrary resume text.
    """
    literal = payload.replace("\\", "\\\\").replace('"', '\\"')
    # Pass replacements as functions, not strings: `re.sub` interprets escape
    # sequences in a *string* replacement, so a `\\` in the payload would be
    # collapsed back to `\` and a `\g<1>` in a bullet would be read as a group
    # reference. A callable replacement is substituted verbatim.
    src = re.sub(
        r"^#let\s+data\s*=.*$",
        lambda _: f'#let data = json(bytes("{literal}"))',
        template_text,
        count=1,
        flags=re.MULTILINE,
    )
    return re.sub(
        r"^#let\s+density\s*=.*$",
        lambda _: f"#let density = {density}",
        src,
        count=1,
        flags=re.MULTILINE,
    )


def _render_pdfspark(resume: Resume, density: float) -> RenderOutput:
    """HTML -> PDF via pdfspark.dev. Same contract as the Typst path.

    `typst_source` carries the generated HTML here, so the UI's "download
    source" button hands back the thing that actually produced this PDF.
    """
    from .html_render import render_html
    from .pdfspark import html_to_pdf

    html = render_html(resume, density=density)
    pdf = html_to_pdf(html)
    text, pages = _extract_text(pdf)
    return RenderOutput(
        pdf=pdf, text=text, pages=pages, density=density, typst_source=html
    )


def render(
    resume: Resume,
    *,
    density: float = 0.0,
    template: Path | None = None,
    backend: str | None = None,
) -> RenderOutput:
    """Compile one resume at one density.

    `backend` is "typst" (default, offline, deterministic) or "pdfspark"
    (HTML/CSS via headless Chromium). Everything downstream — the density
    ladder, the scan, the rubric — is backend-agnostic because both paths
    return the same `RenderOutput`.
    """
    if (backend or active_backend()) == BACKEND_PDFSPARK:
        return _render_pdfspark(resume, density)

    tpl = Path(template or DEFAULT_TEMPLATE)
    if not tpl.exists():
        raise RenderError(f"Template not found: {tpl}")

    payload = resume.model_dump_json(exclude_none=True)
    try:
        pdf = typst.compile(
            str(tpl),
            sys_inputs={"resume": payload, "density": str(density)},
        )
    except Exception as exc:  # typst raises its own TypstError type
        raise RenderError(f"Typst compile failed: {exc}") from exc

    # typst.compile returns bytes when `output` is None, but returns a list of
    # bytes for multi-output formats — normalize.
    if isinstance(pdf, list):
        pdf = pdf[0]

    text, pages = _extract_text(pdf)
    source = _standalone_source(tpl.read_text(encoding="utf-8"), payload, density)
    return RenderOutput(pdf=pdf, text=text, pages=pages, density=density, typst_source=source)


def render_one_page(
    resume: Resume,
    *,
    template: Path | None = None,
    backend: str | None = None,
) -> tuple[RenderOutput, list[str]]:
    """Compile, tightening density until it fits on one page.

    Returns the best attempt plus notes explaining any tightening, so the UI can
    say *why* the layout is dense rather than silently shipping 8.7pt type.
    """
    notes: list[str] = []
    last: RenderOutput | None = None

    for density in DENSITY_LADDER:
        out = render(resume, density=density, template=template, backend=backend)
        last = out
        if out.pages == 1:
            if density > 0:
                notes.append(
                    f"Tightened layout density to {density:g} to hold one page."
                )
            return out, notes

    assert last is not None
    notes.append(
        f"Still {last.pages} pages at maximum density — content needs to be cut, "
        "not just compressed."
    )
    return last, notes


def resume_to_typst(resume: Resume, *, density: float = 0.0, template: Path | None = None) -> str:
    tpl = Path(template or DEFAULT_TEMPLATE)
    return _standalone_source(
        tpl.read_text(encoding="utf-8"),
        resume.model_dump_json(exclude_none=True),
        density,
    )


def text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    return _extract_text(pdf_bytes)


def load_resume(path: str | Path) -> Resume:
    return Resume.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
