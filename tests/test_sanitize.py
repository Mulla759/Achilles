"""Adversarial tests for `achilles.sanitize`.

These are not happy-path tests. `sanitize.py` is the only thing standing
between an attacker-controlled paste and the prompt / PDF / scanner, so every
test here either (a) proves a known evasion technique is neutralized, or
(b) proves the normalizer is not so aggressive that it mangles legitimate
international text.
"""

from __future__ import annotations

import pytest

from achilles.errors import InputError
from achilles.sanitize import (
    MAX_FIELD_CHARS,
    MAX_JD_CHARS,
    MAX_RESUME_CHARS,
    clean_document,
    clean_field,
    clean_jd,
    clean_resume_text,
    clean_text,
    describe_removals,
)


def _alternating(n: int) -> str:
    """`n` characters alternating a/b -- no whitespace, no repeated-char runs,
    so clean_text is a no-op on it and length checks are exact."""
    return ("ab" * ((n + 1) // 2))[:n]


# --------------------------------------------------------------------------
# 1. Zero-width stripping -- invisible keyword stuffing / splitting
# --------------------------------------------------------------------------


def test_zero_width_splits_keyword_classic_evasion():
    # ATTACK: zero-width chars inserted mid-keyword so a naive substring/regex
    # filter never sees "SQL" as a contiguous token, while a human copy-pasting
    # or a downstream scanner reading raw bytes still reconstructs it.
    assert clean_text("S​Q​L") == "SQL"


def test_all_invisible_characters_removed():
    invisibles = "​‌‍﻿⁠­"
    assert clean_text("a" + invisibles + "b") == "ab"
    for ch in invisibles:
        assert ch not in clean_text("x" + ch + "y")


# --------------------------------------------------------------------------
# 2. Bidi controls -- rendered text vs parsed text mismatch
# --------------------------------------------------------------------------


def test_bidi_override_and_isolate_and_mark_chars_removed():
    bidi = (
        "".join(chr(c) for c in range(0x202A, 0x202F))  # LRE RLE PDF LRO RLO
        + "".join(chr(c) for c in range(0x2066, 0x206A))  # LRI RLI FSI PDI
        + "‎‏"  # LRM RLM
    )
    assert clean_text("a" + bidi + "b") == "ab"


def test_rlo_extension_spoof_removed():
    # ATTACK: RIGHT-TO-LEFT OVERRIDE can make a resume display a different
    # string than the one an ATS extracts (classic "cv<RLO>exe.gpj" filename
    # spoof pattern applied to body text). The override char must disappear
    # and leave the underlying characters in their logical (untouched) order.
    cleaned = clean_text("cv‮gpj.exe")
    assert "‮" not in cleaned
    assert cleaned == "cvgpj.exe"


# --------------------------------------------------------------------------
# 3. Control characters -- Typst/PDF breakage, but \n and \t are structural
# --------------------------------------------------------------------------


def test_control_characters_removed_newline_tab_survive():
    c1_range = "".join(chr(c) for c in range(0x80, 0xA0))
    s = "a\x00b\x07c\x1bd" + c1_range + "e\nf\tg"
    cleaned = clean_text(s)
    assert "\x00" not in cleaned  # NUL
    assert "\x07" not in cleaned  # BEL
    assert "\x1b" not in cleaned  # ESC
    for c in range(0x80, 0xA0):
        assert chr(c) not in cleaned
    assert "\n" in cleaned  # resume line structure preserved
    assert "\t" in cleaned


def test_del_character_removed():
    assert clean_text("x\x7fy") == "xy"


# --------------------------------------------------------------------------
# 4. Line-ending normalization
# --------------------------------------------------------------------------


def test_crlf_and_lone_cr_normalize_to_lf():
    assert clean_text("a\r\nb\rc") == "a\nb\nc"


# --------------------------------------------------------------------------
# 5. NFC normalization
# --------------------------------------------------------------------------


def test_nfc_composes_decomposed_accent():
    decomposed = "é"  # "e" + COMBINING ACUTE ACCENT
    cleaned = clean_text(decomposed)
    assert cleaned == "é"
    assert len(decomposed) == 2
    assert len(cleaned) == 1


# --------------------------------------------------------------------------
# 6. Character-run collapsing -- token-inflation / layout-confusion padding
# --------------------------------------------------------------------------


def test_char_run_at_40_is_left_alone():
    # Boundary: the collapsing regex requires a character plus 40 repeats of
    # itself (41 total) before it fires, so a run of exactly 40 must survive.
    run = "a" * 40
    assert clean_text(run) == run


def test_char_run_at_41_collapses_to_three():
    # ATTACK: padding a paste with tens of thousands of a repeated character
    # to run up token cost or defeat a naive length check.
    run = "a" * 41
    assert clean_text(run) == "aaa"


def test_long_repeated_run_collapses_to_three():
    assert clean_text("." * 5000) == "..."


# --------------------------------------------------------------------------
# 7. Blank-line collapsing
# --------------------------------------------------------------------------


def test_three_or_more_blank_lines_collapse_to_two():
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_two_newlines_are_left_alone():
    s = "a\n\nb"
    assert clean_text(s) == s


# --------------------------------------------------------------------------
# 8. Trailing whitespace, per line and overall
# --------------------------------------------------------------------------


def test_trailing_whitespace_per_line_and_overall_stripped():
    s = "  line one   \nline two\t\n  \n  final  "
    assert clean_text(s) == "line one\nline two\n\n  final"


# --------------------------------------------------------------------------
# 9. clean_field -- one-liner flattening and truncation
# --------------------------------------------------------------------------


def test_clean_field_flattens_newlines_collapses_spaces_and_truncates():
    s = "Senior   Engineer\n\nRemote,   avail  now"
    full = clean_field(s)
    assert "\n" not in full
    assert "  " not in full
    assert full == "Senior Engineer Remote, avail now"
    truncated = clean_field(s, limit=20)
    assert truncated == full[:20]
    assert len(truncated) == 20


def test_clean_field_default_limit_is_max_field_chars():
    huge = _alternating(MAX_FIELD_CHARS + 500)
    assert len(clean_field(huge)) == MAX_FIELD_CHARS


# --------------------------------------------------------------------------
# 10. Document length limits -- raise past limit, never at the limit exactly
# --------------------------------------------------------------------------


def test_clean_jd_exactly_at_limit_does_not_raise():
    s = _alternating(MAX_JD_CHARS)
    result = clean_jd(s)
    assert len(result) == MAX_JD_CHARS


def test_clean_jd_one_over_limit_raises_input_error():
    s = _alternating(MAX_JD_CHARS + 1)
    with pytest.raises(InputError) as exc:
        clean_jd(s)
    assert exc.value.http_status == 400


def test_clean_resume_text_exactly_at_limit_does_not_raise():
    s = _alternating(MAX_RESUME_CHARS)
    result = clean_resume_text(s)
    assert len(result) == MAX_RESUME_CHARS


def test_clean_resume_text_one_over_limit_raises_input_error():
    s = _alternating(MAX_RESUME_CHARS + 1)
    with pytest.raises(InputError) as exc:
        clean_resume_text(s)
    assert exc.value.http_status == 400


def test_clean_document_custom_limit_boundary():
    with pytest.raises(InputError) as exc:
        clean_document(_alternating(11), limit=10, label="Field")
    assert exc.value.http_status == 400
    assert len(clean_document(_alternating(10), limit=10, label="Field")) == 10


# --------------------------------------------------------------------------
# 11. describe_removals -- surfaces what was stripped, no false alarms
# --------------------------------------------------------------------------


def test_describe_removals_reports_all_three_categories():
    original = "a​b‮c\x07d"  # invisible + bidi + control
    cleaned = clean_text(original)
    notes = describe_removals(original, cleaned)
    assert len(notes) == 3
    assert all(notes)


def test_describe_removals_empty_for_ordinary_text():
    # No false alarms: accents, em-dashes, and bullets are legitimate content,
    # not attack surface, and must not trigger a removal notice.
    original = "Résumé — Senior Engineer • Team Lead\nBuilt APIs, shipped features."
    cleaned = clean_text(original)
    assert describe_removals(original, cleaned) == []


# --------------------------------------------------------------------------
# 12. Idempotence
# --------------------------------------------------------------------------


def test_clean_text_is_idempotent_on_nasty_input():
    nasty = "S​Q​L‮ injection\r\n\r\n\r\n" + "x" * 100 + "   trailing   "
    once = clean_text(nasty)
    twice = clean_text(once)
    assert once == twice


# --------------------------------------------------------------------------
# 13. Legitimate international text is not mangled
# --------------------------------------------------------------------------


def test_international_scripts_survive_intact():
    # Regression guard: an over-aggressive stripper would be a real-world
    # discrimination bug against non-Latin names.
    name = "李雷 محمد Владимир José Núñez"
    assert clean_text(name) == name


# --------------------------------------------------------------------------
# 14. Empty / whitespace-only input
# --------------------------------------------------------------------------


def test_empty_string_returns_empty_without_raising():
    assert clean_text("") == ""


def test_whitespace_only_string_returns_empty_without_raising():
    assert clean_text("   \n\t  \n  ") == ""
