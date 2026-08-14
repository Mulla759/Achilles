---
name: resume-tailoring
description: Use when the user wants to tailor, customize, or rewrite a resume against a specific job description using this repo's Achilles CLI or API — tailoring a resume, matching a JD, improving ATS keyword coverage, closing rubric gaps, or running achilles tailor / achilles scan / POST /api/tailor. Third person trigger keywords — tailor resume, match job description, ATS score, keyword coverage, resume rubric, reword don't invent.
---

# Resume tailoring with Achilles

Produce a tailored, one-page resume for a specific job description using
this repo's engine (`achilles/pipeline.py`), without ever inventing an
experience the candidate doesn't have.

## The one inviolable rule

**Reword, never invent.** Every claim in the output must trace to something
already in the source resume. You may re-express, re-emphasize, re-order,
merge, split, and re-title. You may NOT add a job, a technology, a
credential, or a number that isn't already there. If the JD wants something
the candidate doesn't have, leave the gap open — a gap is survivable, a
fabrication discovered in an interview is not. See `HANDOFF.md` §4 for the
full grounding rules (one number and stick to it, MAC bullet shape,
restating vs. manufacturing precision).

## Procedure

1. **Gather inputs**: the JD text (>= 40 chars), the candidate's existing
   resume (as plain text or an existing `profiles/*.json`), and the exact
   target role title from the posting. Availability dates if the JD asks for
   them (many internship postings require this).

2. **Run the build.**

   CLI:
   ```bash
   achilles tailor --profile profiles/me.json --jd jd.txt \
     --role "Product Manager Intern" --availability "May 2027 - Aug 2027" \
     --out out/ --slug <company>
   ```
   or `--resume old_resume.txt` instead of `--profile` if there's no
   structured profile yet (this adds one Claude parse call first).

   API: `POST /api/tailor` with `jd_text`, `target_role`, and `resume_text`
   or `resume` — see `docs/API.md`. Note the serverless endpoint defaults to
   **one pass** (60s function cap); the CLI defaults to **three**. To get a
   multi-pass result over the API, re-POST the returned `resume` field back
   in as the `resume` input on the next call.

3. **This loops automatically**: tailor -> render -> scan -> grade, up to
   `max_passes` times, repairing named defects (keyword gaps, failed rubric
   gates) each pass rather than rewriting blind. It stops the moment
   `ready` is true.

4. **Read the report.** The CLI prints:
   - Keyword coverage: `matched/total = score%`, and `required quals` %
     separately (target: >=95% overall, 100% required).
   - Hard rubric: 7 gates, each PASS/FAIL with a score and offending bullets
     (see `docs/API.md`'s rubric gate table, or `.claude/skills/ats-rubric/SKILL.md`
     for what each gate actually checks).
   - Pages (must be 1).
   - Notes: density-tightening explanations and grounding-audit flags.

5. **For each kind of gap, do the right thing — don't just chase the number:**

   | Report says | What it means | What to do |
   |---|---|---|
   | A keyword gap in `scan.gaps` | JD wants a term not found in the resume text | Only add it if genuinely true — surface it in an existing real bullet or a skills group. If it isn't true of the candidate, leave it open. |
   | `semantics` gate fails on a bullet | Opens with a weak/filler verb ("Responsible for", "Helped with") | Reword to open with a strong past-tense verb for the same real action — never change what was done. |
   | `metrics` or `mac` gate fails | Bullet has no real number | Add a number **only if it's real**. If unsure, use a qualitative claim instead of a guess — do not invent a percentage. |
   | `storyline` gate fails | Bullet reads as a duty list, not action -> outcome | Restructure to *did X -> which led to Y -> measured/adopted as Z*, using only facts already present. |
   | `one_page` gate fails | Renders to 2+ pages after the density ladder maxed out | The render step already tried tightening whitespace automatically; if still 2 pages, shorten a 3-line bullet to 2, or cut the weakest bullet — a human/model content call, not automatic. |
   | `ats_parseable` fails | Missing standard section header, table-like layout, no selectable text, or no findable email | Usually a template bug, not a content problem — check `templates/typist.typ` wasn't hand-edited into something non-standard. |
   | A grounding note ("New figure ... — verify") | A number appears in the output that wasn't in the source | Verify it by hand. It's often a legitimate restatement (e.g. "~2 min to under 5 sec" -> "~95% faster") but occasionally a fabrication — this check is advisory, not a guarantee. |

6. **Before calling it done**, confirm: availability dates are current, every
   employment/education end date (especially an open-ended "Present") is
   accurate, and every note in the output has been read — see HANDOFF.md
   §5's "Before you send" checklist.

## Related

- `HANDOFF.md` — full operator's guide, including the manual (non-automated)
  version of this loop for debugging a single stubborn gate.
- `.claude/skills/ats-rubric/SKILL.md` — how the 7 gates and the keyword
  ontology actually work, for tuning thresholds or adding new keywords.
- `.claude/skills/typst-resume/SKILL.md` — editing the template itself.
