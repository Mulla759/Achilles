# CLAUDE.md

Context resume for an AI agent picking up this repo cold.

## What this is

Achilles turns a job description + a pasted resume into a tailored,
one-page, ATS-scored PDF. The tailoring model may reword existing experience
into the JD's vocabulary; it may never invent experience that isn't in the
source. A deterministic keyword scanner and a 7-gate rubric grade the result;
the pipeline loops tailor -> render -> grade until it passes or a pass limit
is hit.

## Module map

| Module | Owns |
|---|---|
| `achilles/models.py` | The data contract: `Resume`, `Keyword`, `ScanReport`, `RubricReport`, `BuildResult`. Every stage speaks these types. |
| `achilles/tailor.py` | The two Claude calls (`parse_resume`, `tailor`) and their system prompts; `audit_grounding()` (advisory, non-LLM). |
| `achilles/keywords.py` | JD text -> `Keyword[]`. Pure Python, hardcoded ontology (`ONTOLOGY`), no LLM. |
| `achilles/scan.py` | `Keyword[]` + extracted text -> `ScanReport`. Whitespace-collapse substring matching, no LLM. |
| `achilles/rubric.py` | `Resume` + extracted text + page count -> `RubricReport` (7 gates). Regex/heuristic, no LLM. |
| `achilles/render.py` | `Resume` -> Typst source -> PDF -> extracted text, via the `typst` and `pypdf` PyPI packages. Owns the one-page density ladder. |
| `achilles/pipeline.py` | Orchestrates the multi-pass loop (`build()`) and the no-LLM grading path (`score_only()`). |
| `achilles/cli.py` | `achilles import\|render\|scan\|tailor`. |
| `achilles/config.py` | `Settings` — env var resolution, API key fallback order. |
| `achilles/errors.py` | Typed exceptions, each with an `http_status` and a user-facing `hint`. |
| `templates/typist.typ` | The one Typst template. Single column. Data-driven via `sys.inputs.resume` (JSON) — never string-interpolated. |
| `api/*.py` | Thin Vercel `BaseHTTPRequestHandler` wrappers around `achilles/` (`api/_lib.py` is the shared JSON/error plumbing, not itself routed). |
| `app/`, `components/`, `lib/` | Next.js frontend — owned by the frontend work, not this document's authority. |
| `docs/API.md` | The HTTP contract. Authoritative for request/response shapes. |
| `docs/HANDOFF.md` | Operator's guide to the tailoring loop, template editing, and the grounding rules. |

## Invariants — do not break these

1. **Reword, never invent.** The tailor system prompt (`achilles/tailor.py`,
   `SYSTEM`) is the enforcement point. Any change to that prompt must
   preserve this as the first, unconditional rule.
2. **Single column, standard section headers only** (Education, Skills,
   Experience, Projects, Leadership). `rubric.py`'s `ats_parseable` gate and
   real ATS parsers both depend on this.
3. **Data reaches the template via `sys_inputs` as JSON, never via string
   interpolation.** This is why no resume text needs escaping. If you ever
   catch yourself f-string-ing resume content into `.typ` source, stop — that
   reintroduces the exact escaping bug class this design avoids. (The one
   narrow exception is `render._standalone_source`, which inlines the
   *already-serialized JSON payload* into a Typst string literal for the
   downloadable standalone `.typ` — that substitution only needs to escape
   `\` and `"`, because JSON, not arbitrary Typst markup, is what's being
   embedded.)
4. **`achilles/models.py` is the contract.** Every stage of the pipeline, the
   Claude structured-output schema, and the HTTP API all read from these
   classes. If you change a field here, update `docs/API.md` in the same
   commit — it documents the same shapes by hand.
5. **One number, and stick to it.** No stage may sharpen a vague claim into a
   precise metric or manufacture a number not present in the source resume.
   `audit_grounding()` is the (advisory, non-blocking) tripwire for this.

## Running things

```bash
pip install -e ".[dev]"
pytest
```

```bash
achilles scan   --jd jd.txt --profile profiles/example.json      # no LLM, sub-second
achilles tailor --jd jd.txt --profile profiles/example.json --role "Product Manager Intern" --out out/
```

```bash
npm install
npm run dev        # Next.js dev server (frontend); calls into api/*.py
npm run typecheck
```

Local dev venv (this repo's `.venv` was created this way):

```powershell
uv venv --python 3.13
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Secrets

- `ANTHROPIC_API_KEY` (server-side fallback key) lives in `.env.local`, which
  is git-ignored. `.env.example` documents every variable with no real
  values — copy it, never commit its filled-in copy.
- Never commit `resume.typ`, `resume.pdf`, `resume.txt`, or any
  `profiles/*.json` other than `profiles/example.json` (a fictional
  student) — see `.gitignore`. A real profile carries a real phone number
  and email.
- `api_key` can also arrive per-request in the `/api/tailor` JSON body
  (bring-your-own-key path — `/api/scan` never calls Claude, so it takes no
  key) — never log request bodies verbatim on the server for this reason.
