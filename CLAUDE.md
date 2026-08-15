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
| `achilles/tailor.py` | The two model calls (`parse_resume`, `tailor`) and their system prompts; `audit_grounding()` (advisory, non-LLM). Provider-agnostic — it calls `providers.structured_call()`. |
| `achilles/providers/` | The only place that knows one vendor from another. `__init__.py` holds `REGISTRY`, `resolve()` (key → provider inference), and `structured_call()`; `base.py` the `Provider` dataclass; `keys.py` key-shape identification and `redact()`; `schema.py` the two JSON-schema dialects; `anthropic_api.py` / `openai_api.py` / `google_api.py` the transports. |
| `achilles/keywords.py` | JD text -> `Keyword[]`. Pure Python, hardcoded ontology (`ONTOLOGY`), no LLM. |
| `achilles/scan.py` | `Keyword[]` + extracted text -> `ScanReport`. Whitespace-collapse substring matching, no LLM. |
| `achilles/rubric.py` | `Resume` + extracted text + page count -> `RubricReport` (7 gates). Regex/heuristic, no LLM. |
| `achilles/render.py` | `Resume` -> Typst source -> PDF -> extracted text, via the `typst` and `pypdf` PyPI packages. Owns the one-page density ladder and the backend switch (`active_backend()`). |
| `achilles/html_render.py`, `achilles/pdfspark.py` | The alternate PDF backend (`ACHILLES_RENDERER=pdfspark`) — HTML/CSS instead of Typst, rendered by a third-party service. Off by default; the default path is local and offline. |
| `achilles/sanitize.py` | Cleans untrusted input (invisible characters, bidi overrides, control characters) before any stage reads it, and reports what it removed. |
| `achilles/tui/` | **Unfinished, unreferenced.** Dependency-free terminal primitives (`term.py`: raw keys + ANSI; `widgets.py`: boxes, meters, visible-width arithmetic). No entry point and no `__init__.py`. See `docs/STATUS.md` §3 before building on it or deleting it. |
| `achilles/pipeline.py` | Orchestrates the multi-pass loop (`build()`) and the no-LLM grading path (`score_only()`). |
| `achilles/cli.py` | `achilles import\|render\|scan\|tailor`. |
| `achilles/config.py` | `Settings` — env var resolution, API key fallback order. |
| `achilles/errors.py` | Typed exceptions, each with an `http_status` and a user-facing `hint`. |
| `templates/typist.typ` | The one Typst template. Single column. Data-driven via `sys.inputs.resume` (JSON) — never string-interpolated. |
| `api/*.py` | Thin Vercel `BaseHTTPRequestHandler` wrappers around `achilles/` (`api/_lib.py` is the shared JSON/error plumbing and `api/_guard.py` the origin allowlist + per-IP rate limit — neither is itself routed). |
| `app/`, `components/`, `lib/` | Next.js frontend — owned by the frontend work, not this document's authority. `lib/types.ts` mirrors `achilles/models.py` by hand; nothing enforces that they agree. |
| `scripts/` | Developer tooling, not part of the package. `devapi.py` is the local Python API server `npm run dev` shells out to; `ats_scan.py` is the original prototype scanner, kept for reference; `snapshot_ui.py` screenshots the web UI; `review-prompt.md` is a saved code-review prompt. |
| `docs/API.md` | The HTTP contract. Authoritative for request/response shapes. |
| `docs/HANDOFF.md` | Operator's guide to the tailoring loop, template editing, and the grounding rules. |
| `docs/STATUS.md` | **Read this first.** What shipped in each commit, the current three-layer shape, and the open threads. Start here when picking the repo up cold. |

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
