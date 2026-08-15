"""The multi-pass loop: tailor -> render -> grade -> repair.

This is the automated version of the manual loop in docs/HANDOFF.md §1. Each pass
costs one Claude call, so we stop the moment the result is shippable rather
than always burning `max_passes`.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .config import Settings, load_settings
from .errors import InputError
from .keywords import extract
from .models import BuildResult, JobDescription, Resume, ScanReport
from .render import render_one_page
from .rubric import grade
from .sanitize import clean_field, clean_jd, clean_resume_text, describe_removals
from .scan import scan
from .tailor import audit_grounding, parse_resume, tailor

MIN_JD_CHARS = 40


def _validate(jd_text: str, target_role: str) -> None:
    if len(jd_text.strip()) < MIN_JD_CHARS:
        raise InputError(
            "That job description is too short to work from.",
            hint="Paste the full posting — responsibilities and qualifications included.",
        )
    if not target_role.strip():
        raise InputError(
            "Target role is required.",
            hint='The exact title from the posting, e.g. "Product Manager Intern".',
        )


def analyze_jd(jd_text: str, *, company: str = "", title: str = "") -> JobDescription:
    return JobDescription(
        company=company, title=title, raw=jd_text, keywords=extract(jd_text)
    )


def score_only(
    *,
    jd_text: str,
    resume: Resume | None = None,
    resume_text: str | None = None,
    template: Path | None = None,
) -> tuple[ScanReport, object, int]:
    """Grade without touching the LLM. Sub-second; powers the "just score it" path."""
    jd_text = clean_jd(jd_text)
    if resume_text:
        resume_text = clean_resume_text(resume_text)
    keywords = extract(jd_text)

    if resume is not None:
        out, _ = render_one_page(resume, template=template)
        text, pages = out.text, out.pages
    elif resume_text:
        # No structure to render, so grade the raw text. Gates that need the
        # structured resume degrade rather than crash.
        text, pages = resume_text, 1
        resume = Resume(contact={"name": ""})  # type: ignore[arg-type]
    else:
        raise InputError(
            "Nothing to score.", hint="Provide either a structured resume or resume text."
        )

    return scan(text, keywords), grade(resume, text, pages), pages


def build(
    *,
    jd_text: str,
    target_role: str,
    resume: Resume | None = None,
    resume_text: str | None = None,
    availability: str = "",
    api_key: str | None = None,
    provider: str | None = None,
    settings: Settings | None = None,
    max_passes: int | None = None,
    template: Path | None = None,
) -> BuildResult:
    """Full build. Returns the best attempt even if it never reaches `ready`."""
    settings = settings or load_settings()

    # Sanitize before anything else looks at the text: the prompt, the PDF, and
    # the keyword scan must all see the same normalized string, or a zero-width
    # character could make the scan credit a term the reader cannot see.
    raw_jd, raw_resume_text = jd_text, resume_text or ""
    jd_text = clean_jd(jd_text)
    resume_text = clean_resume_text(raw_resume_text) if raw_resume_text else resume_text
    target_role = clean_field(target_role)
    availability = clean_field(availability)

    # Validate the request before resolving credentials. Resolving first means a
    # caller who sent an empty JD *and* no key gets told about the key (401),
    # which is the less actionable of the two problems and contradicts
    # docs/API.md's 400 for bad input.
    _validate(jd_text, target_role)
    if resume is None and not (resume_text or "").strip():
        raise InputError(
            "No resume provided.",
            hint="Paste your current resume, or upload it as a .txt file.",
        )

    resolution = settings.resolve(api_key, provider=provider)
    passes_allowed = max(1, min(5, max_passes or settings.max_passes))

    notes: list[str] = []
    # Which model produced this draft is part of reading it — the rubric is
    # calibrated on Opus 5 and other models land differently against it.
    notes.append(f"Tailored with {resolution.provider.label} ({resolution.model}).")
    notes.extend(describe_removals(raw_jd, jd_text))
    if raw_resume_text:
        notes.extend(describe_removals(raw_resume_text, resume_text or ""))
    keywords = extract(jd_text)
    if not keywords:
        notes.append(
            "No known keywords matched this JD — coverage scoring will be thin. "
            "Check you pasted the qualifications section."
        )

    source = resume or parse_resume(resume_text or "", resolution=resolution)

    best: BuildResult | None = None
    prior_scan: ScanReport | None = None
    prior_rubric = None

    attempts_used = 0
    for attempt in range(1, passes_allowed + 1):
        attempts_used = attempt
        candidate = tailor(
            source,
            jd_text=jd_text,
            target_role=target_role,
            availability=availability,
            keywords=keywords,
            prior_scan=prior_scan,
            prior_rubric=prior_rubric,
            resolution=resolution,
        )

        rendered, render_notes = render_one_page(candidate, template=template)
        scan_report = scan(rendered.text, keywords)
        rubric_report = grade(candidate, rendered.text, rendered.pages)

        result = BuildResult(
            resume=candidate,
            source_resume=source,
            typst_source=rendered.typst_source,
            pdf_b64=base64.b64encode(rendered.pdf).decode("ascii"),
            text=rendered.text,
            pages=rendered.pages,
            scan=scan_report,
            rubric=rubric_report,
            passes=attempt,
            notes=[*notes, *render_notes, *audit_grounding(source, candidate)],
        )

        # Keep the strongest attempt, not merely the last one — a repair pass can
        # regress while chasing a stubborn gate.
        if best is None or _rank(result) > _rank(best):
            best = result
        if result.ready:
            break

        prior_scan, prior_rubric = scan_report, rubric_report

    assert best is not None
    # `passes` reports cycles actually spent, not which attempt happened to win.
    # When pass 1 ranks best and passes 2-3 regress, three LLM calls were still
    # made, and reporting `passes=1` would understate both cost and effort.
    best.passes = attempts_used
    if not best.ready:
        best.notes.append(
            f"Stopped after {attempts_used} pass(es) without clearing every gate. "
            "The remaining gaps are listed above — close them only where true."
        )
    return best


def _rank(result: BuildResult) -> tuple:
    """Ordering for 'which draft is better'.

    Required-qualification coverage outranks page count deliberately. A
    two-page draft that covers every required qual is a formatting problem
    with a known fix (tighten density, cut the weakest bullet); a one-page
    draft covering none of them is the wrong resume for the job. Ranking pages
    first would let an empty-but-tidy draft beat a correct one.
    """
    return (
        result.scan.required_score,
        result.pages == 1,
        result.rubric.passed,
        result.scan.score,
        result.rubric.score,
    )
