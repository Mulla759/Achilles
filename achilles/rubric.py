"""Deterministic hard-rubric grading. No LLM — every gate is a regex/heuristic
so `grade()` is cheap enough to call on every keystroke of a manual edit.

Each gate returns a `GateResult` with a 0-100 `score` and a `passed` bool
computed against its own threshold; `RubricReport.passed` is the AND of all
seven. Thresholds are named constants below so they can be retuned without
hunting through the gate bodies.
"""

from __future__ import annotations

import re

from .models import Entry, GateResult, Resume, RubricReport

# --------------------------------------------------------------------------
# Thresholds. Kept as module constants, not magic numbers in the gate bodies.
# --------------------------------------------------------------------------

SEMANTICS_PASS = 90  # one odd bullet on a short resume shouldn't fail the whole gate; two should
METRICS_PASS = 60  # not every bullet can honestly carry a metric (HANDOFF's grounding rule);
# demanding 100% here would push people toward inventing numbers
STORYLINE_PASS = 70
MAC_PASS = 80
ATS_PASS = 100  # binary hygiene: a single failed sub-check (e.g. no email) breaks a real parser

MIN_SELECTABLE_TEXT_CHARS = 200  # below this it's almost certainly an image-only PDF, not a thin resume
CONTEXT_MIN_WORDS = 12  # a bullet this long is describing scope even without a named tool/proper noun
TABLE_LINE_RUN = 3  # 3+ consecutive spaces is pdftotext's tell for a tab-stopped/column layout
TABLE_LINE_RATIO_MAX = 0.15  # allow a stray aligned line or two before calling the whole layout table-ish
BULLET_TRUNCATE = 80

# Past-tense verbs that read as ownership of an outcome, not a task on a list.
STRONG_VERBS = {
    "built", "shipped", "led", "designed", "launched", "migrated", "drove", "cut", "ran",
    "prototyped", "analyzed", "automated", "founded", "scaled", "architected", "implemented",
    "developed", "engineered", "created", "delivered", "reduced", "increased", "improved",
    "optimized", "streamlined", "spearheaded", "negotiated", "managed", "coordinated",
    "organized", "mentored", "trained", "presented", "authored", "deployed", "integrated",
    "refactored", "debugged", "resolved", "identified", "established", "initiated", "piloted",
    "tested", "validated", "surveyed", "interviewed", "synthesized", "modeled", "forecasted",
    "budgeted", "secured", "onboarded", "recruited", "facilitated", "directed", "owned",
    "grew", "expanded", "doubled", "tripled", "halved", "standardized", "consolidated",
    "modernized", "overhauled", "transformed", "pioneered", "championed", "accelerated",
    "boosted", "slashed", "trimmed", "curated", "crafted", "produced", "published",
    "tuned", "benchmarked", "instrumented", "clustered", "quantified", "diagnosed",
    "converted", "rearchitected", "wrote",
    # Verbs that showed up as false negatives on real resumes. The cost of a
    # missing verb is a student being told their good bullet is weak, so this
    # list errs toward inclusion; genuinely passive openers ("Selected for...")
    # are still caught by WEAK_OPENERS and by not appearing here.
    "documented", "segmented", "balanced", "served", "normalized", "streamed",
    "evaluated", "measured", "configured", "profiled", "refined", "mapped",
    "translated", "sourced", "hosted", "chaired", "assembled", "compiled",
    "extracted", "parsed", "indexed", "cached", "partitioned", "orchestrated",
    "simulated", "verified", "audited", "rewrote", "ported", "unified",
}

# Present tense is standard practice for a role you currently hold, so a
# current-role bullet opening "Lead academic programming for 100+ students" is
# correct resume writing, not a weak opener. Accept the present forms of verbs
# already considered strong rather than pushing students to mis-tense a job
# they still have.
PRESENT_TENSE_VERBS = {
    "build", "ship", "lead", "run", "drive", "own", "manage", "design", "write",
    "maintain", "mentor", "coordinate", "host", "analyze", "present", "deliver",
    "operate", "oversee", "scale", "grow",
}
STRONG_VERBS |= PRESENT_TENSE_VERBS

# Phrases that describe a task, not an outcome — the resume equivalent of a job description.
WEAK_OPENERS = [
    "responsible for", "helped", "assisted", "worked on", "participated in", "involved in",
    "tasked with", "duties included", "was a", "aimed to", "in charge of", "helped with",
    "worked with", "contributed to", "supported", "handled",
]

OUTCOME_CONNECTIVES = [
    "so ", "which ", "resulting in", "enabling", "cutting", "lifting", "adopted", "driving",
    "->", "reducing", "guiding",
]

# What counts as a metric: %, currency, magnitude suffix, multiplier, "300+",
# a 2+ digit number, a number carrying a unit word, or a stated delta ("->").
#
# A bare single digit is deliberately NOT enough. "Built application with Python 3" contains a
# digit but reports no result, and counting it made both the metrics and
# storyline gates pass on pure duty statements. A number only counts when it
# carries a unit, a magnitude, a delta, or two or more digits.
_UNIT_WORDS = (
    r"min|mins|minute|minutes|hr|hrs|hour|hours|sec|secs|second|seconds|ms|"
    r"day|days|week|weeks|month|months|year|years|quarter|quarters|"
    r"user|users|customer|customers|client|clients|student|students|member|members|"
    r"people|team|teams|engineer|engineers|attendee|attendees|"
    r"query|queries|record|records|row|rows|file|files|page|pages|line|lines|"
    r"event|events|config|configs|question|questions|test|tests|run|runs|"
    r"location|locations|campaign|campaigns|restaurant|restaurants|audit|audits|"
    r"session|sessions|workshop|workshops|speaker|speakers|install|installs"
)
METRIC_RE = re.compile(
    r"""(
        \d[\d,.]*\s*%                     # 95%, ~12.5 %
      | [$€£]\s*\d                        # $5, £2.4
      | \d[\d,.]*\s*[kmb]\b               # 1.4K, 300M
      | \d[\d,.]*\s*x\b                   # 3x
      | \d[\d,.]*\+                       # 300+, 50+
      | \bsub-\d                          # sub-2s
      | \b\d{2,}\b                        # any number of 2+ digits
      | \d[\d,.]*\s*(?:""" + _UNIT_WORDS + r""")\b   # 2 days, 5 configs
      | ->|→                              # a stated delta
    )""",
    re.IGNORECASE | re.VERBOSE,
)

DEGREE_RE = re.compile(r"\b(b\.?s\.?|b\.?a\.?|bachelor|master|m\.?s\.?|mba|ph\.?d\.?|associate|degree)\b", re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
QUANTITY_RE = re.compile(
    r"\d+\+?\s*(users?|customers?|people|students|members|files|clients?|teams?|engineers?|"
    r"stakeholders?|partners?|attendees?|volunteers?)",
    re.I,
)


def _truncate(text: str, limit: int = BULLET_TRUNCATE) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _first_word(bullet: str) -> str:
    m = re.match(r"[A-Za-z'-]+", bullet.strip())
    return m.group(0).lower() if m else ""


def _opens_strong(bullet: str) -> bool:
    word = _first_word(bullet)
    if word in STRONG_VERBS:
        return True
    # Compound openers ("User-tested the concept", "Co-led the rollout") carry
    # their verb in the tail, so a plain set lookup on the whole token misses them.
    if "-" in word:
        return word.rsplit("-", 1)[-1] in STRONG_VERBS
    return False


def _opens_weak(bullet: str) -> bool:
    b = bullet.strip().lower()
    return any(b.startswith(w) for w in WEAK_OPENERS)


def _has_metric(bullet: str) -> bool:
    return bool(METRIC_RE.search(bullet))


def _has_outcome(bullet: str) -> bool:
    b = bullet.lower()
    return any(c in b for c in OUTCOME_CONNECTIVES)


def _has_strong_verb_near_start(bullet: str) -> bool:
    """MAC's Action check is looser than semantics' opener check: a strong verb
    in the first three words still reads as leading with action even behind a
    stray adverb ("Proactively led...")."""
    words = re.findall(r"[A-Za-z']+", bullet)[:3]
    return any(w.lower() in STRONG_VERBS for w in words)


def _has_context(bullet: str) -> bool:
    words = bullet.split()
    if len(words) >= CONTEXT_MIN_WORDS:
        return True
    if QUANTITY_RE.search(bullet):
        return True
    # a proper noun or tool/tech token beyond the opening verb — "React", "AWS", "Google"
    for token in words[1:]:
        clean = token.strip(",.();:\"'")
        if len(clean) > 1 and clean[0].isupper() and clean.isalpha():
            return True
    return False


def _empty_gate(name: str, detail: str) -> GateResult:
    return GateResult(name=name, passed=False, score=0, detail=detail, offenders=[])


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------


def _gate_graduation(resume: Resume) -> GateResult:
    education = resume.education
    if not education:
        return _empty_gate("graduation", "No education entries found.")

    ok: list[Entry] = []
    offenders: list[str] = []
    for e in education:
        has_degree = bool(DEGREE_RE.search(e.role))
        has_year = bool(YEAR_RE.search(e.date))
        # docs/API.md specifies degree, school, AND date. A degree with no
        # school parses as an unverifiable credential to a human reader.
        has_school = bool(e.org.strip())
        if has_degree and has_year and has_school:
            ok.append(e)
        else:
            missing = [
                name
                for name, present in (
                    ("degree title", has_degree),
                    ("school", has_school),
                    ("graduation year", has_year),
                )
                if not present
            ]
            offenders.append(f"{e.role or '(untitled entry)'} — missing {', '.join(missing)}")

    passed = bool(ok)
    detail = (
        f"{ok[0].role}, {ok[0].org} — {ok[0].date}." if passed
        else "No education entry has all of a degree title, a school, and a parseable graduation year."
    )
    return GateResult(name="graduation", passed=passed, score=100 if passed else 0, detail=detail, offenders=offenders)


def _gate_semantics(resume: Resume) -> GateResult:
    bullets = resume.achievement_bullets()
    if not bullets:
        return _empty_gate("semantics", "No bullets found to evaluate.")

    offenders = []
    good = 0
    for b in bullets:
        if _opens_strong(b) and not _opens_weak(b):
            good += 1
        else:
            offenders.append(_truncate(b))

    score = round(100 * good / len(bullets))
    passed = score >= SEMANTICS_PASS
    detail = f"{good}/{len(bullets)} bullets open with a strong, non-filler action verb."
    return GateResult(name="semantics", passed=passed, score=score, detail=detail, offenders=offenders)


def _gate_metrics(resume: Resume) -> GateResult:
    bullets = resume.achievement_bullets()
    if not bullets:
        return _empty_gate("metrics", "No bullets found to evaluate.")

    offenders = []
    good = 0
    for b in bullets:
        if _has_metric(b):
            good += 1
        else:
            offenders.append(_truncate(b))

    score = round(100 * good / len(bullets))
    passed = score >= METRICS_PASS
    detail = f"{good}/{len(bullets)} bullets carry a real number."
    return GateResult(name="metrics", passed=passed, score=score, detail=detail, offenders=offenders)


def _gate_storyline(resume: Resume) -> GateResult:
    bullets = resume.achievement_bullets()
    if not bullets:
        return _empty_gate("storyline", "No bullets found to evaluate.")

    offenders = []
    good = 0
    for b in bullets:
        if _opens_strong(b) and (_has_metric(b) or _has_outcome(b)):
            good += 1
        else:
            offenders.append(_truncate(b))

    score = round(100 * good / len(bullets))
    passed = score >= STORYLINE_PASS
    detail = f"{good}/{len(bullets)} bullets read as action -> outcome, not a duty list."
    return GateResult(name="storyline", passed=passed, score=score, detail=detail, offenders=offenders)


def _gate_one_page(pages: int) -> GateResult:
    passed = pages == 1
    detail = "Renders to 1 page." if passed else f"Renders to {pages} pages — must fit on 1."
    return GateResult(name="one_page", passed=passed, score=100 if passed else 0, detail=detail, offenders=[])


def _gate_mac(resume: Resume) -> GateResult:
    bullets = resume.achievement_bullets()
    if not bullets:
        return _empty_gate("mac", "No bullets found to evaluate.")

    offenders = []
    total_ratio = 0.0
    for b in bullets:
        m = _has_metric(b)
        a = _has_strong_verb_near_start(b)
        c = _has_context(b)
        total_ratio += (m + a + c) / 3
        missing = [n for n, present in (("metric", m), ("action", a), ("context", c)) if not present]
        if missing:
            offenders.append(f"MISSING {', '.join(missing)} — {_truncate(b)}")

    score = round(100 * total_ratio / len(bullets))
    passed = score >= MAC_PASS
    detail = f"Average Metric+Action+Context completeness: {score}% across {len(bullets)} bullets."
    return GateResult(name="mac", passed=passed, score=score, detail=detail, offenders=offenders)


def _gate_ats_parseable(resume: Resume, text: str) -> GateResult:
    text = text or ""
    offenders: list[str] = []

    selectable = len(text.strip()) >= MIN_SELECTABLE_TEXT_CHARS
    if not selectable:
        offenders.append("Extracted text is too short — likely an image-based PDF with no selectable text.")

    missing_headers = [
        h for h in ("EDUCATION",) if not re.search(rf"\b{h}\b", text, re.I)
    ]
    if not any(re.search(rf"\b{h}\b", text, re.I) for h in ("EXPERIENCE", "PROJECTS", "SKILLS")):
        missing_headers.append("EXPERIENCE/PROJECTS/SKILLS")
    headers_ok = not missing_headers
    if not headers_ok:
        offenders.append(f"Missing standard section header(s): {', '.join(missing_headers)}.")

    lines = text.splitlines() or [""]
    table_run_re = re.compile(r" {" + str(TABLE_LINE_RUN) + r",}")
    table_lines = sum(1 for ln in lines if table_run_re.search(ln))
    table_ratio = table_lines / len(lines)
    layout_ok = table_ratio <= TABLE_LINE_RATIO_MAX
    if not layout_ok:
        offenders.append(f"Layout looks table/column-based ({table_lines}/{len(lines)} lines have 3+ space gaps).")

    has_email = bool(EMAIL_RE.search(text)) or bool(resume.contact.email.strip())
    if not has_email:
        offenders.append("No contact email found in the extracted text.")

    checks = [selectable, headers_ok, layout_ok, has_email]
    score = round(100 * sum(checks) / len(checks))
    passed = score >= ATS_PASS
    detail = f"{sum(checks)}/{len(checks)} ATS-parseability checks passed."
    return GateResult(name="ats_parseable", passed=passed, score=score, detail=detail, offenders=offenders)


def grade(resume: Resume, text: str, pages: int) -> RubricReport:
    gates = [
        _gate_graduation(resume),
        _gate_semantics(resume),
        _gate_metrics(resume),
        _gate_storyline(resume),
        _gate_one_page(pages),
        _gate_mac(resume),
        _gate_ats_parseable(resume, text),
    ]
    return RubricReport(gates=gates)
