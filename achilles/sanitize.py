"""Normalize untrusted text before it reaches the prompt, the PDF, or the scan.

Every string a user pastes — job description, resume, target role — passes
through here first. Four distinct problems, only one of which is cosmetic:

1. **Invisible keyword stuffing.** Zero-width characters let someone hide text
   that a scanner reads but a human never sees. Both directions matter: a
   resume could be stuffed to game the coverage score, and a job description
   could hide terms so the extracted requirement never matches what the
   candidate actually wrote. Stripping them makes what you see what gets graded.

2. **Bidi spoofing.** U+202E (RIGHT-TO-LEFT OVERRIDE) and friends reorder the
   *rendered* glyphs while leaving the underlying string untouched, so a PDF can
   display something different from what an ATS parses. That is a
   misrepresentation risk on a document whose whole purpose is being truthful.

3. **Control characters.** C0/C1 bytes break Typst compilation and PDF text
   extraction in ways that surface as a confusing render error rather than a
   clear "bad input".

4. **Cost.** Token spend scales with input length, so an unbounded paste is a
   billing attack when the deployment has a server-side key. Caps are enforced
   here rather than at each call site.

Deliberately NOT done: no HTML escaping (the renderers own their own escaping —
`html_render` escapes, and the Typst path never interpolates), and no attempt to
detect homoglyphs. Homoglyph "attacks" on a resume only hurt the person
submitting it, and a normalizer aggressive enough to catch them would mangle
legitimate non-English names.
"""

from __future__ import annotations

import re
import unicodedata

from .errors import InputError

# Generous enough for the longest real posting or resume, small enough that a
# single request cannot run up a meaningful bill. A dense one-page resume is
# ~4KB; a long JD is ~8KB.
MAX_JD_CHARS = 60_000
MAX_RESUME_CHARS = 60_000
MAX_FIELD_CHARS = 500  # target role, availability, and similar one-liners

# Zero-width and invisible formatting characters.
_INVISIBLE = (
    "​"  # zero width space
    "‌"  # zero width non-joiner
    "‍"  # zero width joiner
    "⁠"  # word joiner
    "⁡⁢⁣⁤"  # invisible math operators
    "﻿"  # zero width no-break space / BOM
    "­"  # soft hyphen
    "᠎"  # mongolian vowel separator
)

# Explicit bidirectional overrides and isolates.
_BIDI = (
    "‪‫‬‭‮"  # LRE RLE PDF LRO RLO
    "⁦⁧⁨⁩"  # LRI RLI FSI PDI
    "‎‏"  # LRM RLM
)

_STRIP_CHARS = _INVISIBLE + _BIDI
_STRIP_TABLE = {ord(c): None for c in _STRIP_CHARS}

# C0 and C1 control characters, keeping tab and newline. Carriage returns are
# normalized to newlines before this runs, so dropping \r here is intentional.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# More than two blank lines in a row is always noise, and it inflates tokens.
_BLANK_RUN_RE = re.compile(r"\n{3,}")

# Runs of the same character. Catches a paste of 50,000 dots used to pad a
# request past a length check or to confuse the layout.
_CHAR_RUN_RE = re.compile(r"(.)\1{40,}", re.DOTALL)


def clean_text(value: str) -> str:
    """Normalize one untrusted string. Never raises; length is checked separately."""
    if not value:
        return ""

    # NFC first: composes decomposed sequences so "é" is one code point, which
    # makes the substring matching in `scan.py` behave predictably regardless of
    # how the user's editor encoded their accents.
    text = unicodedata.normalize("NFC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_STRIP_TABLE)
    text = _CONTROL_RE.sub("", text)
    text = _CHAR_RUN_RE.sub(lambda m: m.group(1) * 3, text)
    text = _BLANK_RUN_RE.sub("\n\n", text)

    # Trailing whitespace per line: pure noise in extracted PDF text.
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def clean_field(value: str, *, limit: int = MAX_FIELD_CHARS) -> str:
    """A one-line field: cleaned, newlines flattened, hard-truncated."""
    text = clean_text(value).replace("\n", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text[:limit]


def clean_document(value: str, *, limit: int, label: str) -> str:
    """A long pasted document. Raises `InputError` past `limit` rather than
    silently truncating — quietly grading half a resume is worse than refusing."""
    text = clean_text(value)
    if len(text) > limit:
        raise InputError(
            f"{label} is too long ({len(text):,} characters; limit {limit:,}).",
            hint=f"Paste just the {label.lower()} itself, without extra attachments.",
        )
    return text


def clean_jd(value: str) -> str:
    return clean_document(value, limit=MAX_JD_CHARS, label="Job description")


def clean_resume_text(value: str) -> str:
    return clean_document(value, limit=MAX_RESUME_CHARS, label="Resume")


def describe_removals(original: str, cleaned: str) -> list[str]:
    """Human-readable notes about what was stripped, for the UI.

    Silently altering someone's document is its own problem, so anything removed
    gets surfaced rather than just fixed.
    """
    notes: list[str] = []
    invisible = sum(original.count(c) for c in _INVISIBLE)
    bidi = sum(original.count(c) for c in _BIDI)
    controls = len(_CONTROL_RE.findall(original.replace("\r\n", "\n").replace("\r", "\n")))
    if invisible:
        notes.append(
            f"Removed {invisible} invisible character(s) (zero-width). These can hide "
            "text from a reader while a keyword scanner still sees it."
        )
    if bidi:
        notes.append(
            f"Removed {bidi} bidirectional override character(s), which can make a PDF "
            "display text in a different order than it actually contains."
        )
    if controls:
        notes.append(f"Removed {controls} control character(s) that break PDF text extraction.")
    return notes
