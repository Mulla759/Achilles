"""Deterministic grading. No LLM, no API key, sub-second."""

from __future__ import annotations

from typing import Any

from _guard import SCAN_LIMIT
from _lib import json_route, parse_resume_field, require_str, scan_payload

from achilles.pipeline import score_only


def _scan(body: dict[str, Any]) -> dict[str, Any]:
    jd_text = require_str(
        body,
        "jd_text",
        required=True,
        message="A job description is required.",
        hint="Paste the posting into the JD box.",
    )
    resume = parse_resume_field(body)
    resume_text = require_str(body, "resume_text")

    scan_report, rubric_report, pages = score_only(
        jd_text=jd_text, resume=resume, resume_text=resume_text or None
    )

    return {
        "scan": scan_payload(scan_report),
        "rubric": {
            **rubric_report.model_dump(),
            "passed": rubric_report.passed,
            "score": rubric_report.score,
        },
        "pages": pages,
    }


handler = json_route(_scan, limit_for=lambda _body: SCAN_LIMIT, route="scan")
