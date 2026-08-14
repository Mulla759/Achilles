"""The data contract.

Every stage of the pipeline speaks `Resume`. The JD goes in as text, the LLM
produces a `Resume`, the renderer turns it into a PDF, and the scanners grade
the PDF's extracted text. Nothing downstream parses Typst source.

Schemas here are also handed to the Claude API as structured-output schemas, so
they stay deliberately flat: no recursion, no unions beyond optional strings,
every object closed with `extra="forbid"`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SectionName = Literal["experience", "projects", "leadership"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contact(_Strict):
    name: str
    phone: str = ""
    email: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""


class SkillGroup(_Strict):
    """One line in the Skills block, e.g. 'Product & Analytics: SQL, Tableau…'.

    `items` is a single pre-joined string rather than a list because the exact
    separator (comma vs. middot) is a typographic choice the template owns, and
    round-tripping it through a list loses the author's grouping.
    """

    label: str
    items: str


class Entry(_Strict):
    """One school, role, project, or leadership position.

    These are *semantic* slots, not positions on the page. The template decides
    where each one lands, and that differs per section: Education puts location
    top-right and the date under it, while Work Experience puts the date
    top-right and the location under it.
    """

    role: str  # degree, job title, or project name
    org: str = ""  # school, employer, or (for projects) omitted
    date: str = ""
    location: str = ""
    # Projects only: the "| Python, LangChain, FAISS" tech tag beside the name.
    stack: str = ""
    bullets: list[str] = Field(default_factory=list)


class Resume(_Strict):
    contact: Contact
    # Optional header line. The reference format has no such line, so it renders
    # only when set — some internship postings require stated availability.
    target_role: str = ""
    availability: str = ""

    # Section headings. Defaults match the reference resumes; override for a
    # Jake's-resume ordering ("Experience", "Technical Skills") or any other
    # house style without touching the template.
    education_title: str = "Education"
    skills_title: str = "Technical Skills"
    experience_title: str = "Work Experience"
    projects_title: str = "Projects"
    leadership_title: str = "Leadership & Awards"

    # Which line leads a Work Experience entry. "role" is the standard typist
    # ordering (job title bold, employer italic beneath); "org" flips it, which is
    # what some individual resumes do. Education always leads with the school.
    lead_with: Literal["org", "role"] = "role"
    education: list[Entry] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    experience: list[Entry] = Field(default_factory=list)
    projects: list[Entry] = Field(default_factory=list)
    leadership: list[Entry] = Field(default_factory=list)

    def all_bullets(self) -> list[str]:
        out: list[str] = []
        for section in (self.education, self.experience, self.projects, self.leadership):
            for entry in section:
                out.extend(entry.bullets)
        return out

    def achievement_bullets(self) -> list[str]:
        """Bullets the hard rubric grades.

        Education bullets are excluded on purpose: a coursework line ("Coursework:
        Data Structures, Machine Learning, ...") is a factual list, not an
        accomplishment. Grading it for a metric and an action verb fails four
        gates at once and pushes the model to dress it up as something it isn't.
        """
        out: list[str] = []
        for section in (self.experience, self.projects, self.leadership):
            for entry in section:
                out.extend(entry.bullets)
        return out

    def entries(self) -> list[Entry]:
        return [*self.education, *self.experience, *self.projects, *self.leadership]


# --------------------------------------------------------------------------
# Job description
# --------------------------------------------------------------------------


class Keyword(_Strict):
    """One JD requirement plus the surface forms that count as covering it.

    `forms` exists because ATS parsers match strings, not concepts: "A/B
    testing" and "a/b test" are the same requirement. Coverage is scored by
    substring match against the PDF's extracted text, lowercased.
    """

    label: str
    forms: list[str]
    required: bool = True
    group: str = "core"


class JobDescription(_Strict):
    company: str = ""
    title: str = ""
    raw: str = ""
    keywords: list[Keyword] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------


class KeywordHit(_Strict):
    label: str
    group: str
    required: bool
    hit: bool
    matched_form: str = ""


class ScanReport(_Strict):
    hits: list[KeywordHit] = Field(default_factory=list)
    word_count: int = 0

    @property
    def total(self) -> int:
        return len(self.hits)

    @property
    def matched(self) -> int:
        return sum(1 for h in self.hits if h.hit)

    @property
    def score(self) -> int:
        """Overall coverage, 0-100."""
        return round(100 * self.matched / self.total) if self.total else 100

    @property
    def required_score(self) -> int:
        """Coverage of required quals only. The gate that actually matters."""
        req = [h for h in self.hits if h.required]
        if not req:
            return 100
        return round(100 * sum(1 for h in req if h.hit) / len(req))

    @property
    def gaps(self) -> list[str]:
        return [h.label for h in self.hits if not h.hit]


class GateResult(_Strict):
    """One hard-rubric gate."""

    name: str
    passed: bool
    score: int  # 0-100
    detail: str = ""
    offenders: list[str] = Field(default_factory=list)


class RubricReport(_Strict):
    gates: list[GateResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def score(self) -> int:
        return round(sum(g.score for g in self.gates) / len(self.gates)) if self.gates else 100

    @property
    def failures(self) -> list[GateResult]:
        return [g for g in self.gates if not g.passed]


class BuildResult(_Strict):
    """What one full tailor -> render -> grade pass produces."""

    resume: Resume
    # The resume as it went IN, so the UI can show a real per-bullet diff and
    # let a human accept or reject each rewrite instead of taking the whole
    # draft on faith. Without this the "proposed edits" view is decorative.
    source_resume: Resume | None = None
    typst_source: str = ""
    pdf_b64: str = ""
    text: str = ""
    pages: int = 0
    scan: ScanReport
    rubric: RubricReport
    passes: int = 1
    notes: list[str] = Field(default_factory=list)

    @property
    def ready(self) -> bool:
        """The single boolean the UI keys off of.

        `scan.total > 0` is load-bearing, not defensive: an empty keyword set
        scores a vacuous 100% (nothing to miss), so without this a JD the
        ontology does not recognise would report a perfect, meaningless pass.
        """
        return (
            self.scan.total > 0
            and self.pages == 1
            and self.scan.required_score == 100
            and self.scan.score >= 95
            and self.rubric.passed
        )
