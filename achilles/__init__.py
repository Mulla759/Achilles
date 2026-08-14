"""Achilles — turn a job description plus your old resume into a tailored,
one-page, ATS-clean PDF.

Public surface:

    from achilles import build, Resume, JobDescription

    result = build(resume=my_resume, jd_text=jd, target_role="Product Manager Intern")
    result.ready          # bool: shippable?
    result.scan.score     # keyword coverage 0-100
    result.rubric.gates   # per-gate pass/fail
    result.pdf_b64        # the artifact
"""

from .errors import (
    AchillesError,
    GroundingError,
    InputError,
    MissingKeyError,
    RenderError,
    UpstreamError,
)
from .models import (
    BuildResult,
    Contact,
    Entry,
    GateResult,
    JobDescription,
    Keyword,
    Resume,
    RubricReport,
    ScanReport,
    SkillGroup,
)

__version__ = "0.1.0"

__all__ = [
    "AchillesError",
    "BuildResult",
    "Contact",
    "Entry",
    "GateResult",
    "GroundingError",
    "InputError",
    "JobDescription",
    "Keyword",
    "MissingKeyError",
    "RenderError",
    "Resume",
    "RubricReport",
    "ScanReport",
    "SkillGroup",
    "UpstreamError",
]


def __getattr__(name: str):
    # `build` pulls in the Anthropic client; keep import cost off the critical
    # path for callers that only want the models (e.g. the scan-only endpoint).
    if name == "build":
        from .pipeline import build

        return build
    raise AttributeError(name)
