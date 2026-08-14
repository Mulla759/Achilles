"""Deterministic keyword-coverage scan. No LLM, sub-millisecond.

The core trick — collapsing all whitespace (including newlines) to a single
space before matching — comes straight from `ats_scan.py`: real ATS parsers
extract PDF text as a stream, so a term that happens to wrap across a line
break in the rendered resume ("cross-\nfunctional") still reads as one
contiguous string to the parser, and this scan needs to see it the same way.
"""

from __future__ import annotations

import re

from .models import Keyword, KeywordHit, ScanReport

_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\w+")

# Matching is word-bounded, not plain substring. Bare `in` matching produces
# false positives that are actively harmful here: "storage" contains "rag",
# and "JavaScript" contains "java", so a JD mentioning either would invent a
# requirement the candidate then gets scored against — which pressures the
# tailoring pass to claim a skill nobody has. Boundaries are asserted only on
# alphanumeric edges so forms that legitimately start or end in punctuation
# ("a/b test", "c#", ".net", "node.js") still match.
_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.lower()).strip()


def _pattern(form_norm: str) -> re.Pattern[str]:
    cached = _BOUNDARY_CACHE.get(form_norm)
    if cached is None:
        left = r"\b" if form_norm[:1].isalnum() else ""
        # Allow a trailing inflection so one form covers its own plural and
        # participles: "a/b test" must still match "a/b tests", "dashboard"
        # must match "dashboards". The boundary still blocks the false
        # positives ("java" will not reach into "javascript").
        right = r"(?:s|es|ing|ed)?\b" if form_norm[-1:].isalnum() else ""
        cached = re.compile(left + re.escape(form_norm) + right)
        _BOUNDARY_CACHE[form_norm] = cached
    return cached


def contains(haystack: str, form: str) -> bool:
    """Word-bounded containment, the single matching rule for the whole engine.

    Shared with `keywords.extract` so a term is detected in the JD by exactly
    the same rule used to score it against the resume — otherwise a JD could
    raise a requirement the scan can never satisfy.
    """
    form_norm = _normalize(form)
    if not form_norm:
        return False
    return bool(_pattern(form_norm).search(_normalize(haystack or "")))


def scan(text: str, keywords: list[Keyword]) -> ScanReport:
    normalized = _normalize(text or "")

    hits: list[KeywordHit] = []
    for kw in keywords:
        matched_form = ""
        for form in kw.forms:
            form_norm = _normalize(form)
            if form_norm and _pattern(form_norm).search(normalized):
                matched_form = form
                break
        hits.append(
            KeywordHit(
                label=kw.label,
                group=kw.group,
                required=kw.required,
                hit=bool(matched_form),
                matched_form=matched_form,
            )
        )

    word_count = len(_WORD_RE.findall(normalized))
    return ScanReport(hits=hits, word_count=word_count)


def scan_pdf_text(text: str, keywords: list[Keyword]) -> ScanReport:
    """Convenience wrapper for text pulled straight out of a PDF.

    `pdftotext`/pypdf insert a form-feed (\\x0c) at page boundaries, which
    would otherwise glue the last word of one page to the first word of the
    next once whitespace is collapsed. Swap it for a space first.
    """
    return scan((text or "").replace("\x0c", " "), keywords)
