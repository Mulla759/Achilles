"""Unit tests for the api/ HTTP layer -- pure functions only.

No network, no server. `api/tailor.py` and `api/scan.py` are Vercel
serverless functions: each file is loaded with its own directory on
`sys.path` (that's how `from _lib import ...` resolves at runtime), so these
tests replicate that by putting `api/` on `sys.path` before importing them.

Only the validation paths that raise *before* any Claude API call are
exercised here -- see docs/API.md's error table for the codes asserted
against.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import scan  # noqa: E402
import tailor  # noqa: E402

from achilles.errors import InputError  # noqa: E402

# --------------------------------------------------------------------------
# tailor._parse_max_passes -- defect 1
# --------------------------------------------------------------------------


def test_max_passes_absent_defaults_to_serverless_default():
    assert tailor._parse_max_passes(None) == tailor.SERVERLESS_DEFAULT_PASSES


def test_max_passes_accepts_int():
    assert tailor._parse_max_passes(3) == 3


def test_max_passes_accepts_digit_string():
    assert tailor._parse_max_passes("3") == 3


def test_max_passes_zero_is_rejected_not_silently_defaulted():
    # 0 must NOT reach build(), where `max_passes or settings.max_passes`
    # would treat it as falsy and silently substitute 3.
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(0)
    assert exc.value.http_status == 400


def test_max_passes_negative_is_rejected():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(-1)
    assert exc.value.http_status == 400


def test_max_passes_above_range_is_rejected():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(6)
    assert exc.value.http_status == 400


def test_max_passes_float_is_rejected():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(2.5)
    assert exc.value.http_status == 400


def test_max_passes_bool_is_rejected_even_though_bool_is_an_int_subclass():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(True)
    assert exc.value.http_status == 400


def test_max_passes_non_ascii_digit_is_rejected_not_500():
    # "²" (superscript two) passes str.isdigit() but int() raises
    # ValueError on it -- this must come back as InputError/400, not an
    # uncaught ValueError that turns into a 500.
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes("²")
    assert exc.value.http_status == 400


def test_max_passes_non_numeric_string_is_rejected():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes("abc")
    assert exc.value.http_status == 400


def test_max_passes_error_hint_names_the_valid_range():
    with pytest.raises(InputError) as exc:
        tailor._parse_max_passes(6)
    assert "1" in exc.value.hint
    assert "5" in exc.value.hint


# --------------------------------------------------------------------------
# tailor._tailor -- defect 2, input validated before any network call
# --------------------------------------------------------------------------


def test_tailor_rejects_non_string_jd_text_as_bad_input_not_500():
    with pytest.raises(InputError) as exc:
        tailor._tailor(
            {
                "jd_text": ["not", "a", "string"],
                "target_role": "Product Manager Intern",
                "resume_text": "some old resume text",
            }
        )
    assert exc.value.http_status == 400


def test_tailor_rejects_malformed_resume_as_bad_input_not_500():
    with pytest.raises(InputError) as exc:
        tailor._tailor(
            {
                "jd_text": "a job description long enough to pass validation checks",
                "target_role": "Product Manager Intern",
                "resume": {"contact": {}},  # missing required Contact.name
            }
        )
    assert exc.value.http_status == 400


def test_tailor_requires_resume_or_resume_text():
    with pytest.raises(InputError) as exc:
        tailor._tailor(
            {
                "jd_text": "a job description long enough to pass validation checks",
                "target_role": "Product Manager Intern",
            }
        )
    assert exc.value.http_status == 400


def test_tailor_rejects_bad_max_passes_before_touching_resume():
    with pytest.raises(InputError) as exc:
        tailor._tailor(
            {
                "jd_text": "a job description long enough to pass validation checks",
                "target_role": "Product Manager Intern",
                "resume_text": "some old resume text",
                "max_passes": "²",
            }
        )
    assert exc.value.http_status == 400


# --------------------------------------------------------------------------
# scan._scan -- defect 2, same helpers, no LLM involved at all
# --------------------------------------------------------------------------


def test_scan_rejects_non_string_jd_text_as_bad_input_not_500():
    with pytest.raises(InputError) as exc:
        scan._scan({"jd_text": ["not", "a", "string"], "resume_text": "resume text"})
    assert exc.value.http_status == 400


def test_scan_rejects_missing_jd_text():
    with pytest.raises(InputError) as exc:
        scan._scan({"resume_text": "resume text"})
    assert exc.value.http_status == 400


def test_scan_rejects_malformed_resume_as_bad_input_not_500():
    with pytest.raises(InputError) as exc:
        scan._scan({"jd_text": "some job description text", "resume": {"contact": {}}})
    assert exc.value.http_status == 400


# --------------------------------------------------------------------------
# _lib.require_str / _lib.parse_resume_field directly
# --------------------------------------------------------------------------


def test_require_str_rejects_non_string_type():
    from _lib import require_str

    with pytest.raises(InputError) as exc:
        require_str({"k": 123}, "k")
    assert exc.value.http_status == 400


def test_require_str_required_rejects_missing_key():
    from _lib import require_str

    with pytest.raises(InputError) as exc:
        require_str({}, "k", required=True)
    assert exc.value.http_status == 400


def test_require_str_strips_and_returns_plain_string():
    from _lib import require_str

    assert require_str({"k": "  hello  "}, "k") == "hello"


def test_parse_resume_field_returns_none_when_absent():
    from _lib import parse_resume_field

    assert parse_resume_field({}) is None


def test_parse_resume_field_rejects_non_object_resume():
    from _lib import parse_resume_field

    with pytest.raises(InputError) as exc:
        parse_resume_field({"resume": "not an object"})
    assert exc.value.http_status == 400


def test_parse_resume_field_error_message_includes_field_path():
    from _lib import parse_resume_field

    with pytest.raises(InputError) as exc:
        parse_resume_field({"resume": {"contact": {}}})
    assert "contact" in exc.value.message
