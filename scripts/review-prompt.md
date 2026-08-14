Read-only code review. Do NOT edit, create, or delete any file. Report findings as text only.

Scope: `achilles/keywords.py`, `achilles/scan.py`, `achilles/rubric.py`, `achilles/render.py`, `achilles/tailor.py`, `achilles/pipeline.py`, `api/_lib.py`, `api/tailor.py`, `api/scan.py`.

Context: `achilles/models.py` is the data contract; `docs/API.md` is the HTTP contract. Ignore `templates/`, `app/`, `components/`, `lib/`, `tests/` — they are being edited concurrently.

Find real defects only, ranked most severe first. Hunt specifically for:

1. Crashes or unhandled exceptions on edge-case input: empty resume, empty JD, a resume with zero bullets, a JD with no recognized keywords, a bullet that is only whitespace.
2. Scoring logic errors: off-by-one, division by zero, a percentage that can exceed 100 or go negative, a gate that passes vacuously when there is no data.
3. `pipeline.build()`: does the best-attempt ranking actually pick the better draft? Are `prior_scan` / `prior_rubric` fed back correctly on the repair pass? Can it waste or skip a pass?
4. `api/tailor.py`: the `max_passes` parsing expression — is it correct for every input type it can receive (missing, int, str, float, negative, zero, huge, non-numeric)?
5. `render.py`: correctness of the density ladder and the standalone-source regex substitution.

For each finding give: `file:line`, one sentence describing the defect, and a concrete failing input. Skip style, naming, and formatting nits entirely. If something looks wrong but you cannot prove it, say so and mark it UNVERIFIED.
