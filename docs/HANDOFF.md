# Achilles — Reusable Tailoring & ATS Handoff

A repeatable process for pointing a one-page Typst resume at any job
description (JD), keeping it truthful, and scoring it to a high ATS coverage
before you submit. This is the operator's guide — for the HTTP contract see
`docs/API.md`, for the data contract see `achilles/models.py`, for an AI
agent's map of the repo see `CLAUDE.md`, and for the engineering handoff (what
shipped, what's still open) see `docs/STATUS.md`.

> **One thing this guide predates.** Where it says "Claude", read "the
> configured provider". `achilles/tailor.py` no longer calls Anthropic
> directly — it goes through `achilles/providers/`, which supports eight
> backends and picks one from your key's shape. The tailoring *process* and
> the grounding rules below are unchanged and still authoritative.

The engine now does most of this loop automatically (`achilles tailor` or
`POST /api/tailor`). This guide covers both the automated path and the manual
one, because the manual loop is still how you debug a single stubborn gate,
and understanding it is what lets you trust the automated version.

**Files that matter**
- `templates/typist.typ` — the one Typst template (edit this, never a compiled PDF)
- `achilles/keywords.py` — the JD keyword ontology (extend this to re-point coverage)
- `achilles/rubric.py` — the 7 hard gates and their thresholds
- `profiles/*.json` — your structured resume data (gitignored except `example.json`)
- `docs/HANDOFF.md` — this guide

---

## 0. One-time setup

There is no external binary to install. `typst` (PyPI) compiles `.typ` ->
PDF as a Rust-backed wheel, and `pypdf` extracts text from the result — both
are pure `pip install`, which is also why this runs unchanged on a Vercel
Python function.

> **Obsolete — do not do this anymore.** The original version of this guide
> said to `curl` a `typst` release tarball and `apt-get install poppler-utils`
> for `pdftotext`. Neither is needed or used. If you still have a system
> `typst` binary or `poppler-utils` installed from following the old
> instructions, it's inert — nothing in this repo calls out to either.

```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.13
pip install -e .
```

```powershell
uv venv --python 3.13
.venv\Scripts\Activate.ps1
pip install -e .
```

Compile + verify one page in one line (no LLM call — this is `render.py`
plus `pypdf`, not `achilles tailor`):

```bash
achilles render --profile profiles/example.json --out out/example.pdf
```

---

## 1. The core loop (repeat per role)

### Automated

```bash
achilles tailor --profile profiles/me.json --jd jd.txt \
  --role "Product Manager Intern" --availability "May 2027 - Aug 2027" \
  --out out/ --slug tiktok
```

This runs the full **tailor -> render -> grade** cycle up to
`ACHILLES_MAX_PASSES` times (default 3, override with `--passes`), stopping
the moment `pages == 1 && required_score == 100 && score >= 95 &&
rubric.passed` — the `ready` boolean from `achilles/models.py`. Pass 2+
receives the exact keyword gaps and rubric failures from the prior pass as
repair instructions, so it's fixing named defects, not rewriting blind
(`achilles/pipeline.py`, `achilles/tailor.py`).

It prints the same coverage/rubric report as the manual loop below, plus how
many passes it took and any notes (density tightening, grounding flags).
`--out` writes `<slug>.pdf`, `<slug>.typ` (a standalone, re-compilable
source), and `<slug>.json` (the structured resume — keep this if you like the
result, so the next JD tailors from it rather than from your original text).

### Manual (when you want control over one gate)

1. **Paste the new JD** into a scratch file (`jd.txt` — gitignored).
2. **Check what keywords it extracted:**
   `achilles scan --jd jd.txt --profile profiles/me.json` — no LLM call, prints
   coverage instantly. See what's already covered before you touch anything.
3. **Re-map bullets by hand** in `profiles/me.json` so the JD's language
   shows up in *your real* stories. Reword — never invent. If it isn't true,
   it doesn't go in.
4. **Render**, confirm one page: `achilles render --profile profiles/me.json --out out/me.pdf`.
5. **Re-scan** (step 2 again), read the gaps.
6. **Close gaps only where true.** Repeat 3-5 until coverage is >=95% and
   every line is still defensible in an interview.

Each pass of either loop is the same shape: tailor -> render -> scan -> patch.
Keep a copy of the profile JSON per company (`profiles/tiktok.json`,
`profiles/stripe.json`) — or just use `--slug` on `achilles tailor` and keep
the `<slug>.json` it writes — so you never overwrite a good variant.

---

## 2. How the template is built (so you can edit safely)

`templates/typist.typ` is single-column on purpose — multi-column resumes
scramble in most ATS parsers. It takes **no personal data of its own**; the
resume is handed in as JSON through `sys.inputs.resume` and read by
`#let data = json(bytes(sys.inputs.at("resume", default: "{}")))` at the top
of the file. Structure:

The layout reproduces the standard "Jake's resume" structure used by the
reference PDFs in `resume/` — verified at 92.9% line-for-line similarity
against `resume/PM_Abdullahi_Abdi.pdf`.

- **Header** — name centred, then a pipe-separated contact line with
  underlined links. The optional target-role / availability line renders
  *only* when `target_role` or `availability` is set; the reference format has
  no such line. Many internship JDs require stated availability, so
  `tailor()` is told to fill it whenever an availability is passed in.
- `#section("...")` — bold heading with a full-width rule. Titles come from
  the JSON (`education_title`, `skills_title`, `experience_title`,
  `projects_title`, `leadership_title`) and default to Education /
  Technical Skills / Work Experience / Projects / Leadership & Awards.
  `rubric.py`'s `ats_parseable` gate checks that standard headings are
  present, so keep any override recognisable.
- **Entry geometry differs per section — this is the part people get wrong:**

  | Section | Line 1 (bold) | right | Line 2 (italic) | right |
  |---|---|---|---|---|
  | Education | `org` (school) | `location` | `role` (degree) | `date` |
  | Work Experience / Leadership | `org` (employer) | `date` | `role` (title) | `location` |
  | Projects | `role` (name) ` \| ` *`stack`* | `date` | — | — |

  Note Education and Work Experience swap which of date/location goes on
  which line. Set `lead_with: "role"` on the `Resume` to put the job title
  in bold on line 1 instead of the employer (Jake's ordering).
- `#bullets(items)` — a tight bullet list, spacing driven by `density`.
  Entry blocks keep a non-zero `below` on purpose: at `0pt` the first bullet
  is *extracted* onto the same text line as the entry header
  (`Expected Dec 2027• Coursework...`), and extracted text is exactly what an
  ATS reads.

**Editing rules of thumb**

- **Escaping is now a template-authoring concern only, not a content
  concern.** Resume text — including a bullet containing `#`, `$`, `*`, `_`,
  `@`, `[ ]`, or a backslash — reaches Typst as a JSON string value via
  `sys_inputs` and is never spliced into Typst source, so it renders
  literally with no escaping needed at all.
  > **Obsolete advice, still true only inside the template file itself:**
  > the original guide's "escape a literal `#` in *markup* as `\#`" was about
  > hand-writing Typst markup directly in `resume.typ`. If you are editing
  > *content* (a bullet, a skill line) that flows through `Resume` JSON, do
  > **not** double-escape it — you will corrupt the string. That rule still
  > applies if you are editing `typist.typ`'s own markup (e.g. adding a new
  > label like `Tech\#`), because that text *is* Typst source.
- Wrap emphasis with `_underscores_` for italic, `*stars*` for bold — but
  only inside markup you write directly in the template; resume content
  itself isn't parsed as Typst markup, so `*` inside a bullet renders as a
  literal asterisk, not bold.
- If it runs to 2 pages, `render_one_page()` in `achilles/render.py` already
  tries five density steps (`0.0, 0.3, 0.55, 0.75, 1.0`) — each step tightens
  body size, leading, bullet/entry/section spacing, and margins together
  (see `DENSITY_LADDER` and the `lerp()` calls at the top of `typist.typ`)
  before anyone touches content. **What's automatic:** whitespace and type
  size compression. **What's still a human call:** if it's still 2 pages at
  density 1.0, the pipeline returns the tightest attempt with a note saying
  so — you (or the next tailor pass, via `<rubric_failures>`) have to shorten
  a 3-line bullet to 2 or drop the weakest bullet. The levers already in the
  file (`entry-gap`, `bullet-gap`, `section-gap`, `#set par(leading:)`) are
  what the density ladder is tuning — you can hand-tune them the same way for
  a one-off fix.

---

## 3. The scan and the ontology

`achilles/scan.py` reads the PDF's extracted text (`pypdf`), normalizes
whitespace the way real parsers do (collapses all whitespace, including line
breaks, to a single space — so "cross-\nfunctional" still matches "cross
functional"), and checks each `Keyword`'s accepted surface forms against it.
It's a straight port of the original prototype's core insight (still present
as `scripts/ats_scan.py`, kept for reference — `achilles/scan.py` is
what the pipeline actually calls now).

**Where the keywords come from — it's automatic now.** The original process
was to hand-edit a `groups` dict per JD. Now `achilles/keywords.py` extracts
`Keyword` objects straight from the JD text:

- `ONTOLOGY` is a hardcoded list of `(label, group, forms)` tuples across five
  groups (`ai`, `product`, `data`, `engineering`, `soft`). A JD term matches
  if any of its `forms` appears as a lowercased substring of the
  whitespace-collapsed JD.
- Required vs. preferred is detected by walking the JD line by line, flipping
  a "current region" flag on short heading-like lines that contain phrases
  like `required qualifications` / `must have` (-> required) or
  `preferred qualifications` / `nice to have` (-> preferred). Unlabeled body
  text defaults to required — the safer over-classification.
- A conservative fallback (`_extract_other`) catches tools not in the curated
  ontology: it only fires on comma-separated, 3+-item, capitalized-token
  lines (a skills-list shape), so it won't harvest random capitalized words
  out of prose.

**Re-pointing it at a new domain:** open `achilles/keywords.py` and add a
tuple to `ONTOLOGY` — `("Label", "group", ("surface form one", "surface form
two"))`. Forms must be lowercase; matching always lowercases the JD and the
resume text first. See `.claude/skills/ats-rubric/SKILL.md` for the exact
procedure and a worked example.

**Reading the output**

- A gap in `scan.gaps` = the JD wants it and it's not in the resume text.
- Only close a gap if it's *true*. Prefer surfacing it in an existing real
  bullet or a skills group over adding a new claim.
- A gap that's a genuine whitespace/line-break artifact (a real term split
  across two lines) is already handled — the scanner collapses whitespace,
  matching parser behavior, including the `\x0c` form-feed Typst/pypdf insert
  at page boundaries (`scan_pdf_text`).

Target: **>=95% overall, and 100% on required quals** — this is exactly the
`ready` condition `BuildResult.ready` checks in `achilles/models.py`.

---

## 4. Grounding rules (don't skip — this is what makes it survive interviews)

These are unchanged from the original process and are the most important
section in this file. They are also encoded directly into the `tailor()`
system prompt in `achilles/tailor.py` — this isn't just guidance for a human
editing JSON by hand, it's what the model itself is instructed to follow.

- **One number, and stick to it.** If you're unsure a metric is real (e.g. a
  retention %), don't print a number — use a qualitative claim ("maximize
  repeat engagement") instead of a guess.
- **Reword, don't fabricate.** Matching a keyword means telling a true story
  in the JD's vocabulary, not inventing a story. This is the one inviolable
  rule of the whole system — see the `SYSTEM` prompt's first paragraph in
  `achilles/tailor.py`.
- **Every bullet = action + what you built/integrated + result/adoption**
  (MAC: Metric, Action, Context — this is also `rubric.py`'s `mac` gate, so
  it's graded, not just advised). The strongest pattern: *prototyped X -> user-tested it
  -> it revealed Y -> it got adopted.*
- **Keep the skills split** (Languages / Tools & Technologies / a domain group
  such as Product, Data, or ML — matching the reference resumes).
  It reads as domain-fluent while still proving you can build.
- **A restated number is not a new number, but a manufactured one is.** You
  may restate a metric in the JD's units when the source supports it (e.g.
  "~2 min to under 5 sec" may also be phrased "~95% faster"), but never
  sharpen a vague claim into a precise one that wasn't there.

After every tailor pass, `audit_grounding()` diffs numerals in the output
against numerals in the source (bullets, roles, orgs, dates, stack lines) and
flags anything new as a note — not a hard failure, because a legitimate
restatement genuinely introduces a new numeral. Read every note in the
output before you send the resume; the audit is advisory, not a guarantee.

---

## 5. Recording a baseline result

Every time you land a resume you're happy with for a real company, record it
here (or in your own log) as a reference point for the next JD in the same
family: role, company, the coverage numbers `achilles tailor` printed, and
anything you had to leave uncovered on purpose. This is what lets you sanity-
check whether a new JD-generated coverage number is normal or a sign that the
ontology needs a new entry.

**Reference result — TikTok, Customer Service Product PM Intern:** 100%
keyword coverage (26/26), 1 page, single column, no images, standard
headers. Fully covered: AI agents / agentic, LLM, prompt engineering, RAG,
tool calling, agent frameworks, evaluation design, resolution rate, service
quality, A/B testing, SQL, user research, pain points, experimentation. This
predates the ontology-driven `achilles/keywords.py` (it came from the
original hand-edited `scripts/ats_scan.py` `groups` dict) but the coverage bar it set
— 100% required, ~95%+ overall — is exactly what `BuildResult.ready` still
enforces today.

To record a new baseline: run `achilles tailor`, note `scan.matched/total`,
`scan.required_score`, `rubric.score`, and `passes` from the printed report,
and add a short paragraph here the same shape as the TikTok one above.

**Before you send, always:**
- Confirm the **availability dates** in the header are your real, current ones.
- Confirm every **employment/education end date** (especially an open-ended
  "Present") is still accurate.
- Read every note in the `notes` list, especially any grounding flag or
  density-tightening note.
