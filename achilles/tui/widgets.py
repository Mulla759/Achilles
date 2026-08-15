"""Drawing primitives: boxes, meters, rows, and the width arithmetic they need.

Everything here works on *visible* width — the width after the escape sequences
are discounted. Padding a coloured string with `str.ljust` counts the invisible
bytes and the box's right edge walks off by however many codes the line
contained, which is the classic way hand-rolled terminal UIs come out crooked.
"""

from __future__ import annotations

import re
import unicodedata

from .term import DIM, FG, RESET, sgr

_ANSI = re.compile(r"\033\[[0-9;?]*[a-zA-Z]")

# Box drawing. Single-line for structure, so the two weights read as a hierarchy
# rather than as decoration.
TL, TR, BL, BR = "┌", "┐", "└", "┘"
H, V = "─", "│"
TEE_L, TEE_R = "├", "┤"


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def visible_len(text: str) -> int:
    """Printed width, counting double-width characters as two columns."""
    plain = strip_ansi(text)
    width = 0
    for ch in plain:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def truncate(text: str, width: int) -> str:
    """Cut to `width` visible columns, with an ellipsis when something is lost.

    Escape sequences are preserved as they are passed, and a RESET is appended
    when the cut might have severed one — cheaper and safer than tracking
    open attributes through the cut.
    """
    if width <= 0:
        return ""
    if visible_len(text) <= width:
        return text
    out, used = [], 0
    i = 0
    while i < len(text):
        match = _ANSI.match(text, i)
        if match:
            out.append(match.group(0))
            i = match.end()
            continue
        ch = text[i]
        step = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + step > width - 1:
            break
        out.append(ch)
        used += step
        i += 1
    return "".join(out) + "…" + RESET


def pad(text: str, width: int) -> str:
    """Pad or truncate to exactly `width` visible columns."""
    text = truncate(text, width)
    return text + " " * max(0, width - visible_len(text))


def rule(width: int, *, left: str = TEE_L, right: str = TEE_R) -> str:
    return sgr(f"{left}{H * max(0, width - 2)}{right}", DIM)


def box_top(title: str, width: int) -> str:
    """A top border with the title inlined, `┌ title ─────┐`."""
    label = f" {title} " if title else ""
    fill = max(0, width - 2 - visible_len(label) - 1)
    return sgr(f"{TL}{H}", DIM) + sgr(label, DIM) + sgr(f"{H * fill}{TR}", DIM)


def box_bottom(width: int) -> str:
    return sgr(f"{BL}{H * max(0, width - 2)}{BR}", DIM)


def row(content: str, width: int) -> str:
    """One line inside a box, borders included."""
    inner = width - 4
    return f"{sgr(V, DIM)} {pad(content, inner)} {sgr(V, DIM)}"


def meter(value: int, width: int, *, ok: int = 95, warn: int = 70) -> str:
    """A 0-100 bar.

    The numeral is always printed beside it. A bar alone is a picture of a
    number, and this one gets read by someone deciding whether to send the
    resume — they need the actual figure.
    """
    width = max(4, width)
    filled = round(width * max(0, min(100, value)) / 100)
    colour = FG["green"] if value >= ok else FG["yellow"] if value >= warn else FG["red"]
    return sgr("█" * filled, colour) + sgr("░" * (width - filled), DIM)


def status_glyph(state: str) -> str:
    """Stage markers. Distinct shapes, so colour is never load-bearing."""
    return {
        "pending": sgr("○", DIM),
        "active": sgr("◐", FG["cyan"]),
        "done": sgr("●", FG["green"]),
        "failed": sgr("✗", FG["red"]),
        "skipped": sgr("–", DIM),
    }.get(state, sgr("○", DIM))


def mark(passed: bool) -> str:
    return sgr("✓", FG["green"]) if passed else sgr("✗", FG["red"])


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap on visible width. Long words are hard-split."""
    if width <= 0:
        return []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            if not current:
                current = word
            elif visible_len(current) + 1 + visible_len(word) <= width:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
            while visible_len(current) > width:
                lines.append(truncate(current, width))
                current = current[width:]
        lines.append(current)
    return lines


def elapsed(seconds: float) -> str:
    """m:ss, or s.s under a minute — the resolution that matters at each scale."""
    if seconds < 60:
        return f"{seconds:4.1f}s"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
