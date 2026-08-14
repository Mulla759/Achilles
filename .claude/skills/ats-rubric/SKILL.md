---
name: ats-rubric
description: Use when tuning a rubric gate threshold in achilles/rubric.py, adding a new keyword or surface form to the ontology in achilles/keywords.py, or explaining why a specific rubric gate or keyword failed. Third person trigger keywords — rubric gate, ATS score, keyword ontology, coverage threshold, semantics gate, MAC gate, add a keyword.
---

# How the 7 gates and the keyword scan work

Achilles grades a resume two separate, both-deterministic ways: the **hard
rubric** (`achilles/rubric.py`, 7 gates, no LLM) and **keyword coverage**
(`achilles/keywords.py` + `achilles/scan.py`, no LLM). Both run in
`achilles/pipeline.py`'s `score_only()` and inside every pass of `build()`.
Neither calls Claude, so both are cheap enough to run on every keystroke of a
manual edit.

## The 7 rubric gates

All thresholds are named constants at the top of `achilles/rubric.py` —
change them there, not inline in a gate function.

| Gate | Function | Threshold constant | Default | What it measures |
|---|---|---|---|---|
| `graduation` | `_gate_graduation` | binary | pass/fail | An education entry whose `role` matches a degree regex (`DEGREE_RE`) AND whose `date` contains a 4-digit year (`YEAR_RE`). |
| `semantics` | `_gate_semantics` | `SEMANTICS_PASS` | 90 | % of bullets whose first word is in `STRONG_VERBS` and doesn't also match a `WEAK_OPENERS` phrase. |
| `metrics` | `_gate_metrics` | `METRICS_PASS` | 60 | % of bullets matching `METRIC_RE` (`\d` or `->`). Deliberately not 100 — not every bullet can honestly carry a number. |
| `storyline` | `_gate_storyline` | `STORYLINE_PASS` | 70 | % of bullets that open strong AND have either a metric or an `OUTCOME_CONNECTIVES` phrase ("resulting in", "which", "->", ...). |
| `one_page` | `_gate_one_page` | binary | pass/fail | `pages == 1`, passed in from the renderer. |
| `mac` | `_gate_mac` | `MAC_PASS` | 80 | Average of (metric present + strong verb in first 3 words + `_has_context`) / 3 across all bullets. |
| `ats_parseable` | `_gate_ats_parseable` | `ATS_PASS` | 100 | 4 binary checks averaged: selectable text > `MIN_SELECTABLE_TEXT_CHARS` (200 chars), an `EDUCATION` header plus one of `EXPERIENCE`/`PROJECTS`/`SKILLS`, low table-like-line ratio (`TABLE_LINE_RATIO_MAX` = 0.15, detected via 3+-space runs), and a findable email. |

`RubricReport.passed` is the AND of all seven `GateResult.passed` values;
`RubricReport.score` is the plain average of all seven `GateResult.score`
values (0-100 each). `BuildResult.ready` additionally requires `pages == 1`
and both keyword thresholds — see `achilles/models.py`.

### Tuning a threshold

1. Open `achilles/rubric.py`, change the constant (e.g. `METRICS_PASS = 60`
   -> `70`).
2. Update the corresponding row in `docs/API.md`'s rubric gate table and in
   `README.md`'s hard-rubric table — both hand-document these thresholds and
   will drift silently otherwise.
3. Run `pytest tests/test_rubric.py` — it asserts specific pass/fail
   behavior at the current thresholds (e.g. a 250-char resume with one
   degree+year education entry passes `graduation`); a threshold change may
   require updating fixtures, not just the constant.
4. Consider `STRONG_VERBS`, `WEAK_OPENERS`, and `OUTCOME_CONNECTIVES` (also
   in `achilles/rubric.py`) if the gap is a missing verb/phrase rather than a
   threshold — these are plain Python sets/lists, safe to extend directly.

## The keyword ontology

`achilles/keywords.py`'s `ONTOLOGY` is a flat list of
`(label, group, forms)` tuples across five groups: `ai`, `product`, `data`,
`engineering`, `soft`. `extract(jd_text)` walks the JD once, flattens
whitespace, and emits one `Keyword` per ontology entry whose `forms` contains
a substring match — plus a conservative fallback (`_extract_other`) for
comma-separated capitalized-token lines that catches tools outside the
curated list (group `"other"`).

Required vs. preferred is decided by scanning the JD for heading-like lines
(`_REQUIRED_PHRASES` / `_PREFERRED_PHRASES`, e.g. "required qualifications" /
"nice to have") and bucketing subsequent lines accordingly; unlabeled text
defaults to required (the safer over-classification — see `_is_required`).

### Adding a new keyword

Add a tuple to `ONTOLOGY`:

```python
("Segment", "engineering", ("segment", "segment.io", "segment analytics")),
```

- `label` — the human-facing name shown in `scan.gaps` and rubric reports.
- `group` — one of the five existing groups, or a new one if it doesn't fit
  (groups are informational only; nothing enforces a fixed set).
- `forms` — every lowercase substring that should count as a match, in
  either direction (matching the JD to build the `Keyword`, and matching the
  candidate's resume text in `scan.py` to check `hit`). Both directions use
  the identical whitespace-collapsed, lowercased substring match — a form
  that's too broad (e.g. `"ml"` alone) will false-positive inside unrelated
  words, so prefer full words or hyphenated phrases.

Then add or extend a case in `tests/test_scan.py` asserting `extract()`
picks it up and `scan()` matches it, and re-run `achilles scan --jd <jd> ...`
against a real JD in the target domain to sanity-check before relying on it.

### Why a JD's coverage % might look wrong

- **A real gap** — the JD wants something not in the resume and it's true;
  don't force it, see `HANDOFF.md` §4.
- **A synonym the ontology doesn't have** — add the missing `forms` entry
  (above) rather than editing the resume to use unnatural phrasing.
- **A domain the ontology doesn't cover at all** — an exotic JD may under-
  match broadly; this is a known limitation (see `README.md`'s Limitations
  section), not a bug to route around by hand-inventing a keyword match in
  the resume text.
- **`"other"` group noise** — `_extract_other` only fires on skills-list-
  shaped lines and caps at `OTHER_MAX = 15` items; a real term it's missing
  because it wasn't formatted as a comma list is better added to `ONTOLOGY`
  directly than worked around.
