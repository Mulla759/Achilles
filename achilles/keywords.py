"""JD -> Keyword extraction. Pure Python, no LLM, no network.

The whole point of this module is to turn a wall of pasted job-description
text into the same `Keyword` objects `scan.py` grades a resume against later.
Everything here is deliberately curated rather than learned: a hardcoded
ontology is auditable and stable across runs, which matters more for a
grading engine than recall on exotic job titles.
"""

from __future__ import annotations

import re

from .models import Keyword
from .scan import contains

# --------------------------------------------------------------------------
# Ontology: canonical label -> (group, surface forms).
#
# Forms are matched case-insensitively, word-bounded, against whitespace-
# collapsed JD text via `scan.contains`, so "A/B testing" and "a/b test" both
# work without needing every inflection spelled out. Keep forms lowercase —
# matching is always done against lowercased text.
# --------------------------------------------------------------------------

ONTOLOGY: list[tuple[str, str, tuple[str, ...]]] = [
    # ---- AI / LLM --------------------------------------------------------
    ("LLM", "ai", ("llm", "large language model", "large language models")),
    ("RAG", "ai", ("rag", "retrieval augmented generation", "retrieval-augmented generation")),
    ("Prompt engineering", "ai", ("prompt engineering", "prompt design", "prompting")),
    ("Tool calling", "ai", ("tool calling", "tool use", "function calling")),
    ("Agents", "ai", ("ai agent", "ai-agent", "agentic", "multi-agent", "agent framework")),
    ("Evaluation design", "ai", ("evaluation design", "ai-based evaluation", "eval set", "evals")),
    ("Fine-tuning", "ai", ("fine-tuning", "fine tuning", "finetuning")),
    ("Embeddings / vector search", "ai", ("embedding", "embeddings", "vector search", "vector database")),
    ("Hallucination / grounding", "ai", ("hallucination", "groundedness", "grounded response")),
    ("Conversational AI", "ai", ("chatbot", "conversational ai", "conversation design", "multi-turn")),
    ("Machine learning", "ai", ("machine learning", "ml model", "ml models")),
    ("NLP", "ai", ("nlp", "natural language processing")),
    ("Generative AI", "ai", ("generative ai", "genai", "gen ai")),
    ("LangChain", "ai", ("langchain",)),
    ("LLM provider APIs", "ai", ("openai api", "anthropic api", "claude api", "gpt api")),

    # ---- Product -----------------------------------------------------------
    ("Roadmap", "product", ("roadmap", "product roadmap")),
    ("User research", "product", ("user research", "user-tested", "user testing", "discovery interview", "usability testing")),
    ("Pain points", "product", ("pain point", "pain points", "user needs", "user need")),
    ("A/B testing", "product", ("a/b test", "a/b testing", "ab test", "ab testing", "split test")),
    ("Experimentation", "product", ("experimentation", "experiment design", "iterate", "iteration")),
    ("Metrics definition", "product", ("metrics definition", "north star metric", "kpi", "key performance indicator")),
    ("Retention", "product", ("retention", "churn")),
    ("Activation", "product", ("activation",)),
    ("Engagement", "product", ("engagement", "user engagement")),
    ("Product requirements (PRD)", "product", ("prd", "product requirements document", "product spec")),
    ("Go-to-market", "product", ("go-to-market", "gtm", "launch plan")),
    ("Stakeholder management", "product", ("stakeholder management", "stakeholder")),
    ("Prioritization", "product", ("prioritization", "backlog", "triage")),
    ("Customer discovery", "product", ("customer discovery", "voice of customer")),
    ("Competitive / market analysis", "product", ("competitive analysis", "market analysis", "case analysis", "industry analysis")),
    ("User personas", "product", ("persona", "personas", "user persona")),
    ("Wireframing", "product", ("wireframe", "wireframing", "mockup", "mockups", "figma")),
    ("Product-market fit", "product", ("product-market fit", "product market fit", "pmf")),
    ("Resolution rate", "product", ("resolution rate",)),
    ("Service quality / CSAT", "product", ("service quality", "service-quality", "user satisfaction", "customer satisfaction", "csat")),

    # ---- Data ----------------------------------------------------------
    ("SQL", "data", ("sql", "mysql", "postgresql", "postgres")),
    ("Python", "data", ("python",)),
    ("Tableau", "data", ("tableau",)),
    ("ETL", "data", ("etl", "data pipeline", "data pipelines")),
    ("Analytics", "data", ("analytics", "data analysis", "data analyst")),
    ("Statistics", "data", ("statistics", "statistical analysis")),
    ("Excel", "data", ("excel", "spreadsheets")),
    ("Power BI", "data", ("power bi", "powerbi")),
    ("Data visualization", "data", ("data visualization", "dashboards", "dashboarding")),
    ("Regression / modeling", "data", ("regression", "predictive model", "predictive modeling")),
    ("Clustering", "data", ("k-means", "clustering", "cluster analysis")),
    ("Big data", "data", ("big data", "spark", "hadoop")),
    ("Data warehousing", "data", ("data warehouse", "data warehousing", "snowflake", "bigquery", "redshift")),
    ("Looker", "data", ("looker",)),
    ("Jupyter / notebooks", "data", ("jupyter", "notebook", "notebooks")),
    ("Pandas / NumPy", "data", ("pandas", "numpy")),

    # ---- Engineering -----------------------------------------------------
    ("React", "engineering", ("react", "react.js", "reactjs")),
    ("TypeScript", "engineering", ("typescript",)),
    ("JavaScript", "engineering", ("javascript",)),
    ("Java", "engineering", ("java",)),
    ("C#", "engineering", ("c#", "c-sharp", "csharp")),
    (".NET", "engineering", (".net", "dotnet")),
    ("Docker", "engineering", ("docker", "containerization")),
    ("AWS", "engineering", ("aws", "amazon web services")),
    ("REST APIs", "engineering", ("rest api", "restful", "rest apis")),
    ("Git", "engineering", ("git", "github", "version control")),
    ("CI/CD", "engineering", ("ci/cd", "continuous integration", "continuous deployment")),
    ("Kubernetes", "engineering", ("kubernetes", "k8s")),
    ("Node.js", "engineering", ("node.js", "node js", "nodejs")),
    ("C++", "engineering", ("c++",)),
    ("Microservices", "engineering", ("microservices", "microservice architecture")),
    ("Unit testing", "engineering", ("unit test", "unit testing", "test coverage")),
    ("Agile / Scrum", "engineering", ("agile", "scrum", "sprint planning")),
    ("Cloud computing", "engineering", ("cloud computing", "azure", "gcp", "google cloud")),
    ("API design", "engineering", ("api design", "api development")),
    ("Object-oriented programming", "engineering", ("object-oriented", "oop")),
    ("Linux", "engineering", ("linux", "unix")),

    # ---- Soft skills -------------------------------------------------------
    ("Communication", "soft", ("communication", "communicating")),
    ("Collaboration", "soft", ("collaboration", "collaborative")),
    ("Cross-functional", "soft", ("cross-functional", "cross functional", "cross-team")),
    ("Fast-paced", "soft", ("fast-paced", "fast paced")),
    ("Ownership", "soft", ("ownership", "self-starter", "self starter")),
    ("Adaptability", "soft", ("adaptability", "changing priorities")),
    ("Leadership", "soft", ("leadership",)),
    ("Problem solving", "soft", ("problem solving", "problem-solving", "analytical thinking")),
    ("Time management", "soft", ("time management",)),
    ("Attention to detail", "soft", ("attention to detail", "detail-oriented", "detail oriented")),
    ("Teamwork", "soft", ("teamwork", "team player")),
    ("Presentation skills", "soft", ("presentation skills", "public speaking")),
    ("Mentorship", "soft", ("mentorship", "mentoring")),
]

# label -> (group, forms), for `coverage_forms` and dedup lookups.
_BY_LABEL: dict[str, tuple[str, tuple[str, ...]]] = {
    label: (group, forms) for label, group, forms in ONTOLOGY
}

# Every known surface form, lowercased, so the "other" fallback doesn't emit
# something the curated ontology already covers under a different label.
_KNOWN_FORMS: set[str] = {f.lower() for _, _, forms in ONTOLOGY for f in forms}

_WS_RE = re.compile(r"\s+")


def _flatten(text: str) -> str:
    """Lowercase + collapse all whitespace, matching the ATS-parser normalization in scan.py."""
    return _WS_RE.sub(" ", text.lower()).strip()


# --------------------------------------------------------------------------
# Required vs. preferred region detection.
#
# JDs are read top to bottom; the region a term appears under carries more
# signal than the term itself. We track a running "current region" as we walk
# lines, flipping it on short heading-like lines, and bucket every line's text
# into a required-buffer or preferred-buffer accordingly. A term found in the
# required buffer wins even if it also happens to appear in the preferred
# buffer (e.g. restated under "nice to have too") — required is the safer
# over-classification since it just means we grade it a bit more strictly.
# --------------------------------------------------------------------------

_REQUIRED_PHRASES = (
    "required qualifications",
    "basic qualifications",
    "minimum qualifications",
    "must have",
    "must-have",
    "required skills",
    "requirements:",
    "you must have",
    "what you'll need",
    "what you need",
)
_PREFERRED_PHRASES = (
    "preferred qualifications",
    "nice to have",
    "nice-to-have",
    "bonus points",
    "preferred skills",
    "a plus",
    "pluses",
    "preferred:",
)
_HEADING_MAX_LEN = 60  # headings are short lines; this keeps us from matching the phrase inside a long sentence


def _regions(jd_text: str) -> tuple[str, str]:
    """Split the JD into (required-region text, preferred-region text), both flattened."""
    required_lines: list[str] = []
    preferred_lines: list[str] = []
    current = "required"  # default: unlabeled body text (responsibilities, intro) reads as expected, not optional
    for raw_line in jd_text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if len(line) <= _HEADING_MAX_LEN:
            if any(p in lowered for p in _REQUIRED_PHRASES):
                current = "required"
            elif any(p in lowered for p in _PREFERRED_PHRASES):
                current = "preferred"
        (required_lines if current == "required" else preferred_lines).append(line)
    return _flatten(" ".join(required_lines)), _flatten(" ".join(preferred_lines))


def _is_required(forms: tuple[str, ...], required_text: str, preferred_text: str) -> bool:
    if any(contains(required_text, f) for f in forms):
        return True
    if any(contains(preferred_text, f) for f in forms):
        return False
    return True  # never seen in either labeled region -> not explicitly downgraded, so treat as required


# --------------------------------------------------------------------------
# Fallback: unmatched capitalized multiword tech tokens.
#
# Only fires on lines shaped like a skills/tools list (3+ short, comma-
# separated, capitalized items) — real sentences almost never look like that,
# so this stays conservative rather than harvesting every capitalized word
# in the JD (which would just be company names and sentence-initial words).
# --------------------------------------------------------------------------

_OTHER_TOKEN_RE = re.compile(
    r"^[A-Z][A-Za-z0-9+.#/\-]{1,24}(?:\s[A-Z][A-Za-z0-9+.#/\-]{1,24}){0,2}$"
)
_OTHER_STOPWORDS = {
    "strong", "excellent", "good", "ability", "experience", "skills", "knowledge",
    "years", "proven", "solid", "working", "understanding", "familiarity",
    "demonstrated", "willingness", "etc", "and", "or", "plus", "including",
}

# Postings carry a location line ("Seattle, WA / San Jose, CA") that splits into
# comma-separated capitalized tokens exactly like a skills list, so state codes
# were being harvested as job requirements. A phantom requirement is worse than
# a missed one: it shows the student a gap they can only close by lying.
_US_STATES = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il",
    "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt",
    "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri",
    "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}
OTHER_MIN_LEN = 3  # two-letter tokens are almost always state codes or noise
OTHER_MAX = 15  # cap so a noisy JD can't flood the "other" group with junk


def _extract_other(jd_text: str, required_text: str, preferred_text: str) -> list[Keyword]:
    seen: set[str] = set()
    out: list[Keyword] = []
    for raw_line in jd_text.splitlines():
        items = [p.strip().strip(".") for p in raw_line.split(",")]
        if len(items) < 3:
            continue
        for item in items:
            if not _OTHER_TOKEN_RE.match(item):
                continue
            key = item.lower()
            if (
                len(key) < OTHER_MIN_LEN
                or key in _US_STATES
                or key in _OTHER_STOPWORDS
                or key in _KNOWN_FORMS
                or key in seen
            ):
                continue
            seen.add(key)
            out.append(
                Keyword(
                    label=item,
                    forms=[key],
                    required=_is_required((key,), required_text, preferred_text),
                    group="other",
                )
            )
            if len(out) >= OTHER_MAX:
                return out
    return out


# --------------------------------------------------------------------------
# Degree fields are ALTERNATIVES, not a checklist.
#
# "...a Bachelor's degree in Computer Science, Statistics, Data Science,
# Economics, or a related quantitative field" is one requirement satisfied by
# any one field. Scoring each field as its own keyword makes 100% required
# coverage unreachable for every real candidate, and — far worse — it hands the
# tailoring pass a list of "gaps" whose only fix is claiming a degree the
# candidate does not have. Collapse the whole list into one OR-keyword.
# --------------------------------------------------------------------------

DEGREE_FIELDS: dict[str, tuple[str, ...]] = {
    "computer science": ("computer science",),
    "statistics": ("statistics", "statistical"),
    "data science": ("data science",),
    "economics": ("economics", "econometrics"),
    "mathematics": ("mathematics", "applied math"),
    "engineering": ("engineering",),
    "information systems": ("information systems",),
    "operations research": ("operations research",),
    "physics": ("physics",),
    "business": ("business administration",),
}

# Anchor words for the degree requirement. We search a window around each hit
# rather than a sentence, because the field list routinely wraps across a line
# break ("...degree in Computer Science, Statistics,\n  Data Science, ...") and
# because "B.S." is full of periods that defeat sentence splitting.
_DEGREE_ANCHOR_RE = re.compile(
    r"\b(?:degree|bachelor'?s?|master'?s?|b\.?s\.?|b\.?a\.?|m\.?s\.?|ph\.?d\.?|"
    r"majoring|pursuing|major in)\b",
    re.I,
)
_DEGREE_WINDOW = 220  # characters after the anchor; long enough for a 6-field list


def _degree_alternation(
    jd_text: str, required_text: str, preferred_text: str
) -> tuple[Keyword | None, set[str]]:
    """Return the collapsed degree keyword plus the field names it absorbs."""
    flat = _flatten(jd_text)
    windows = [
        flat[m.start() : m.end() + _DEGREE_WINDOW] for m in _DEGREE_ANCHOR_RE.finditer(flat)
    ]
    if not windows:
        return None, set()

    blob = " ".join(windows)
    matched = {
        field
        for field, forms in DEGREE_FIELDS.items()
        if any(contains(blob, f) for f in forms)
    }
    # A single named field is an ordinary requirement, not an alternation.
    if len(matched) < 2:
        return None, set()

    forms: list[str] = []
    for field in sorted(matched):
        forms.extend(DEGREE_FIELDS[field])

    pretty = " / ".join(f.title() for f in sorted(matched))
    return (
        Keyword(
            label=f"Degree in {pretty}",
            forms=forms,
            required=_is_required(tuple(forms), required_text, preferred_text),
            group="qualification",
        ),
        matched,
    )


def extract(jd_text: str) -> list[Keyword]:
    if not jd_text or not jd_text.strip():
        return []
    flat = _flatten(jd_text)
    required_text, preferred_text = _regions(jd_text)

    degree_kw, absorbed = _degree_alternation(jd_text, required_text, preferred_text)

    out: list[Keyword] = []
    if degree_kw is not None:
        out.append(degree_kw)

    for label, group, forms in ONTOLOGY:
        if label.lower() in absorbed:
            continue
        if any(contains(flat, f) for f in forms):
            out.append(
                Keyword(
                    label=label,
                    forms=list(forms),
                    required=_is_required(forms, required_text, preferred_text),
                    group=group,
                )
            )

    out.extend(
        kw
        for kw in _extract_other(jd_text, required_text, preferred_text)
        if kw.label.lower() not in absorbed
    )
    return out


def coverage_forms(label: str) -> list[str]:
    entry = _BY_LABEL.get(label)
    return list(entry[1]) if entry else []
