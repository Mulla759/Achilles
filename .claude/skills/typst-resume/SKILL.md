---
name: typst-resume
description: Use when editing templates/typist.typ in this repo — adding or restyling a resume section, changing the one-page density ladder, fixing Typst compile errors, or asking whether resume content needs escaping. Third person trigger keywords — Typst template, sys_inputs, density ladder, resume.typ, one-page fitting, escape hash sign.
---

# Editing templates/typist.typ safely

`templates/typist.typ` is the single, data-driven Typst template every
`Resume` renders through (`achilles/render.py`). It contains **no personal
data** — resume content arrives as JSON via `sys.inputs.resume` and is read
at the top of the file:

```typst
#let data = json(bytes(sys.inputs.at("resume", default: "{}")))
#let density = float(sys.inputs.at("density", default: "0"))
```

## The data contract

`data` is a `Resume` (see `achilles/models.py`) serialized to JSON, so its
shape is fixed: `contact`, `target_role`, `availability`, `education`,
`skills`, `experience`, `projects`, `leadership`. If you add a field to
`templates/typist.typ` that reads `data.at("something")`, that field must
also exist on the corresponding Pydantic model in `achilles/models.py`, or
it will always be empty — Typst never receives more than what
`Resume.model_dump_json()` produced. **Changing what the template reads
means changing `achilles/models.py` (and `docs/API.md`) in the same
change**, not just the template.

Helpers already in the file:
- `has(dict, key)` — true if `dict[key]` is a non-empty trimmed string.
- `get(dict, key)` — the trimmed string value, or `""`.
- `section(title)` — bold heading + rule. Only call this (directly or via
  `render-section`) with one of the five standard names: Education, Skills,
  Experience, Projects, Leadership. ATS parsers and `rubric.py`'s
  `ats_parseable` gate both key off exactly these headers.
- `entry(e)` — one role/project/leadership header row + its bullets.
- `render-section(title, entries)` — skips the section entirely if
  `entries` is empty, so an unused section (e.g. no `leadership`) doesn't
  print an empty heading.
- `bullets(items)` — a tight `list(...)` with density-driven spacing.

## Escaping — what still applies and what doesn't

**Resume content needs no escaping at all**, because it never becomes Typst
source text — it's a JSON string read at runtime, so a bullet containing
`#`, `$`, `*`, `_`, `@`, `[ ]`, or a backslash renders as those literal
characters. This is a deliberate design choice (see the comment at the top
of `typist.typ`) and it obsoletes the old "escape a literal `#` as `\#`"
advice that used to apply when resume text was typed directly into a `.typ`
file.

**Escaping still applies when you write Typst *markup* directly in the
template file itself** — e.g. if you add a hardcoded label like `Tech\#` in
`section()` or a new heading string. Inside markup (not inside a string
literal), `#` starts code, `_..._` is italic, `*...*` is bold, `[...]` is
content — escape any of those with a leading backslash if you mean the
literal character. Inside a Typst *string literal* (`"like this"`), only `\`
and `"` are special — this is what `render._standalone_source()` relies on
when it inlines the resume JSON payload into the downloadable standalone
`.typ` file.

## The density ladder (one-page fitting)

`achilles/render.py`'s `render_one_page()` compiles at
`DENSITY_LADDER = (0.0, 0.3, 0.55, 0.75, 1.0)` in order and stops at the
first density that fits one page. `density` (0.0 = roomiest, 1.0 = tightest)
drives every typographic knob via linear interpolation at the top of the
template:

```typst
#let lerp(a, b) = a + (b - a) * density
#let body-size   = lerp(9.6, 8.7) * 1pt
#let lead        = lerp(0.52, 0.36) * 1em
#let bullet-gap  = lerp(3.0, 1.6) * 1pt
#let entry-gap   = lerp(2.6, 1.0) * 1pt
#let section-gap = lerp(3.0, 1.0) * 1pt
#let side-margin = lerp(0.6, 0.42) * 1in
#let top-margin  = lerp(0.5, 0.34) * 1in
```

This is what's **automatic**: body text size, line leading, bullet/entry/
section spacing, and margins all tighten together as density rises, so
whitespace is squeezed before anything is cut. If it's still 2 pages at
`density = 1.0`, `render_one_page()` gives up and returns the tightest
attempt with a note — cutting a bullet or shortening a 3-line one to 2 is a
**content decision**, left to a human or the next tailor pass, never done
automatically by the renderer.

To add a new density-driven knob, add another `lerp(roomy, tight)` line and
wire it into the relevant `#set`/`block(above:, below:)` call — follow the
existing pattern rather than hardcoding a fixed value.

## Adding a new section

1. Add the field to `Resume` in `achilles/models.py` (a `list[Entry]`,
   matching `education`/`experience`/`projects`/`leadership`) — this is the
   contract; update `docs/API.md` in the same change.
2. Add a call in `typist.typ`, in the position you want it to render:
   `#render-section("Your Header", data.at("your_field", default: ()))`.
3. Use one of the five ATS-standard header names if at all possible; a
   sixth custom header risks nothing in `rubric.py` today (only Education +
   one of Experience/Projects/Skills are checked) but real ATS parsers are
   more forgiving of the standard set.
4. Compile and check page count: `achilles render --profile <profile.json> --out out/test.pdf`.

## Debugging a compile failure

`render.py` wraps any Typst exception as `RenderError` with the message
`"Typst compile failed: {exc}"` and surfaces `source` (the standalone
`.typ`) for inspection. This is always a **template bug**, not user input —
resume text can't break the template because it's never parsed as markup.
Reproduce directly:

```bash
achilles render --profile profiles/example.json --out out/debug.pdf
```
