# Status & Handoff

Where the code actually stands, what the last few pieces of work changed, and
what is still open. This is the engineering handoff — for the *operator's*
guide to the tailoring loop see `docs/HANDOFF.md`, for the HTTP contract see
`docs/API.md`, and for an agent's map of the repo see `CLAUDE.md`.

Last updated: 2026-08-15, at commit `04a748c`.

---

## 1. What shipped, in order

Five commits carry the whole system. Reading them in order is the fastest way
to understand why the code is shaped the way it is.

### `09e5317` — the engine

The original vertical slice: `models.py` (the data contract), `keywords.py`
(JD → `Keyword[]`, no LLM), `scan.py` (coverage matching, no LLM), `rubric.py`
(the 7 gates, no LLM), `render.py` (Typst → PDF → extracted text),
`tailor.py` (the two Claude calls), `pipeline.py` (the multi-pass loop), and
the `api/` handlers. Everything since has been built on top of this without
changing its shape: the pipeline is still tailor → render → grade, looping
until `BuildResult.ready` or the pass limit.

### `603acd4` — the editorial web interface

A Next.js frontend (`app/`, `components/`, `lib/`) over the same handlers.
Roughly 20 components, each with a colocated CSS module, plus `lib/api.ts`
(the fetch layer), `lib/types.ts` (hand-maintained mirror of the Python
response shapes), `lib/format.ts`, and `lib/storage.ts`. Keyboard-first:
`Ctrl+Enter` tailors, `Ctrl+S` runs the free score-only path, `?` lists the
rest.

**The thing to know:** `lib/types.ts` is written by hand to match
`achilles/models.py` and the JSON the handlers emit. Nothing enforces that
they agree. Changing a model field means changing `lib/types.ts` and
`docs/API.md` in the same commit or the frontend drifts silently.

### `d1fac51` — the provider split

The largest structural change so far, and the one most likely to surprise
someone reading older docs. `tailor.py` used to call Anthropic directly.
It no longer knows what Anthropic is.

Everything provider-specific now lives in `achilles/providers/`:

| File | Owns |
|---|---|
| `__init__.py` | `REGISTRY`, `resolve()`, `structured_call()` — the whole public surface |
| `base.py` | The `Provider` dataclass every backend fills in |
| `keys.py` | Key-shape → provider inference (`sk-ant-` → Anthropic, etc.) and `redact()` |
| `schema.py` | Pydantic model → the two schema dialects (`openai_schema`, `google_schema`) |
| `anthropic_api.py`, `openai_api.py`, `google_api.py` | The three transports |

Eight providers are registered: Anthropic, OpenAI, Google, DeepSeek, Groq,
xAI, OpenRouter, and GitHub Models. The last six all speak the OpenAI wire
format, so they share `openai_api.complete` and differ only by endpoint row.

Credential resolution, first match wins:

1. a key passed in explicitly (UI, CLI, or request body)
2. `ACHILLES_API_KEY` — provider-neutral
3. each provider's conventional variable, Anthropic first

The provider is then inferred from the key's *shape*, unless
`ACHILLES_PROVIDER` names one — which is the escape hatch for gateways and
self-hosted endpoints whose keys look like nothing in particular. If an
explicit provider and a confidently-identified key disagree, `resolve()`
raises rather than letting the upstream 401 explain it badly.

Two deliberate decisions worth not undoing:

- **`GITHUB_TOKEN` is not consulted.** CI sets it automatically for unrelated
  reasons, and silently routing a build's Actions token to an inference
  endpoint is a surprise nobody wants. GitHub Models is opt-in by name via
  `GITHUB_MODELS_TOKEN`.
- **No default model is pinned in `config.py`.** Each provider supplies its
  own; pinning `claude-opus-5` globally would be wrong the moment someone
  switches to Gemini.

**The calibration caveat.** The rubric thresholds were tuned against Opus 5.
Other providers tailor fine but fail the `semantics` gate (word choice) more
often, which costs an extra repair pass. That's a known cost, not a bug — but
it means a score comparison across providers isn't apples to apples.

Same commit also moved `HANDOFF.md` → `docs/HANDOFF.md`, `ats_scan.py` →
`scripts/ats_scan.py`, and `.mcp.json` → `.mcp.json.example` (which MCP
servers you run is a local choice; committing it makes every cloner's agent
install servers they never asked for).

### `17a57c8` — terminal UI primitives (WIP)

`achilles/tui/term.py` (raw key input, ANSI output, Windows
`ENABLE_VIRTUAL_TERMINAL_PROCESSING`) and `achilles/tui/widgets.py` (boxes,
meters, visible-width arithmetic that discounts escape sequences).

**This is unfinished and unreferenced.** The primitives are written and
self-consistent; nothing imports them, there is no TUI entry point, and there
is no `achilles/tui/__init__.py`. It is committed as WIP on purpose. See
§3 for the decision it's waiting on.

### `04a748c` — `/api/health` after the split

`/api/health` still assumed a single Anthropic key. It now probes
`resolve()` and reports `provider`, `model`, the full `providers` list, the
active `renderer`, `byo_key_only`, and `server_key`.

The subtle part, and the reason the code has a comment about it: the probe
passes `byo_key_only=False` *deliberately*. `server_key` answers "is a server
key configured", not "will this deployment spend it" — the UI reads
`byo_key_only` for the second question. A BYO-key host legitimately has no
key, and the UI still needs the rest of the payload to render its key field,
so the failure path returns a valid response rather than a 5xx.

---

## 2. Current shape

```
JD text ──> keywords.py ──┐
                          ├──> tailor.py ──> render.py ──> scan.py + rubric.py
resume ────> tailor.py ───┘   (providers/)    (typst)              │
                 ^                                                 │
                 └────────── repair with named failures ───────────┘
```

Three layers, and the boundary between them is the thing to preserve:

- **No-LLM core** — `keywords.py`, `scan.py`, `rubric.py`, `render.py`.
  Deterministic, fast, testable without a key. `score_only()` in
  `pipeline.py` is this path on its own, and it's what `Ctrl+S` and
  `achilles scan` run.
- **The one LLM seam** — `tailor.py` + `providers/`. `tailor.py` owns the
  prompts and knows nothing about transports; `providers/` owns transports
  and knows nothing about resumes.
- **Delivery** — `cli.py` (5 commands: `import`, `providers`, `render`,
  `scan`, `tailor`), `api/*.py` (Vercel handlers), `app/` + `components/`
  (the web UI).

Abuse controls live in `api/_guard.py`: origin allowlist, per-IP rate limit
that's stricter when spending the *server's* key, and `ACHILLES_BYO_KEY_ONLY`
as the real answer for a public deploy. The limiter is in-process, so on
serverless it's per-instance and resets on cold start — the module says so
itself. It raises the cost of casual abuse; it is not a substitute for
BYO-key mode or a platform WAF.

Two PDF backends: `typst` (default, local, offline) and `pdfspark`
(`achilles/pdfspark.py` + `achilles/html_render.py`, calls a third-party
service). Selected with `ACHILLES_RENDERER` or `--renderer`.

---

## 3. Open threads — pick these up next

Ordered by how much they'd cost someone who doesn't know about them.

**1. The TUI is a fork in the road, not a to-do.** `achilles/tui/` is two
files of solid primitives with no consumer. Either build the interactive
`achilles tailor` front-end they were written for (add
`achilles/tui/__init__.py`, wire an entry point, give it a `--tui` flag), or
delete the directory. Leaving it is the worst of the three: it reads as a
feature to anyone scanning the module list, and the next person to touch
`cli.py` will wonder what they're missing.

**2. `lib/types.ts` has no enforcement.** It mirrors `achilles/models.py` by
hand. A field rename in Python typechecks clean in TypeScript and fails at
runtime. Worth either generating it from the Pydantic models or adding a test
that asserts the two agree.

**3. Multi-provider is unproven past Anthropic.** Eight providers are
registered; the rubric was calibrated on one. Nobody has recorded what
coverage and gate-pass rates look like on Gemini, GPT, or DeepSeek. A short
matrix — same JD and profile through each provider, scores recorded — would
turn a caveat into a number. `docs/HANDOFF.md` §5 is where baselines go.

**4. `keywords.py`'s ontology is the coverage ceiling.** It's a hardcoded
list. An unusual posting matches fewer terms than it should, and the system
correctly reports thin coverage rather than a fake 100%. Extending it is
routine (`.claude/skills/ats-rubric/SKILL.md` has the procedure); the open
question is whether a curated list is still the right design at, say, triple
the current size.

**5. One pass per HTTP request.** `vercel.json` caps the function at 60s, so
`/api/tailor` runs a single pass and the UI re-submits for another. The CLI
loops internally up to `ACHILLES_MAX_PASSES`. That asymmetry is a deployment
constraint, not a design choice — worth revisiting if the function budget
changes.

**6. Test coverage is lopsided.** `tests/` covers `rubric`, `scan`, `sanitize`,
`html_render`, and the API handlers (`test_api.py`, `test_guard.py`). There is
no test file for `tailor.py`, `pipeline.py`, `render.py`, `cli.py`,
`config.py`, or `providers/`. The provider layer is the notable one: `resolve()`
is pure logic over a dict of env vars — it takes an `env` parameter precisely so
it can be tested without touching the real environment — and nothing tests it.

**7. `audit_grounding()` is advisory by design.** It diffs numerals in the
output against numerals in the source and flags new ones. It cannot be made
blocking as-is, because a legitimate restatement ("~2 min to under 5 sec" →
"~95% faster") genuinely introduces a new numeral. Making it a hard gate
needs a way to tell restatement from invention, which nobody has built.

---

## 4. Things that will bite you

- **Docs that predate the split.** `docs/HANDOFF.md` still speaks in terms of
  Claude specifically in places. It's right about the tailoring *process* and
  the grounding rules; treat its provider references as historical.
- **The `sys_inputs` invariant.** Resume data reaches Typst as JSON through
  `sys.inputs.resume`, never string-interpolated. This is why no resume text
  needs escaping. The single exception is `render._standalone_source`, which
  inlines the already-serialized JSON payload into a Typst string literal and
  therefore only escapes `\` and `"`. If you find yourself f-stringing resume
  content into `.typ` source, stop.
- **Section headers are load-bearing.** Single column, standard headings.
  Both `rubric.py`'s `ats_parseable` gate and real ATS parsers depend on it.
- **Never log request bodies.** `/api/tailor` accepts `api_key` in the JSON
  body (the BYO-key path). Verbatim body logging on the server would write
  visitors' keys to logs. `providers.redact()` exists for when you need to
  show a key at all.
- **`profiles/example.json` is the only committable profile.** It's a
  fictional student. A real profile carries a real phone number and email;
  `.gitignore` covers `profiles/*.json`, `resume*`, `jd*`, and `out/`.

---

## 5. Verifying a fresh clone

```bash
git clone <this repo> && cd Achilles
uv venv --python 3.13
.venv/Scripts/Activate.ps1        # PowerShell; use `source .venv/bin/activate` on POSIX
pip install -e ".[dev]"
pytest

npm install
npm run typecheck
```

No API key is needed for any of the above — the whole no-LLM core, which is
most of the test suite, runs without one. First command that needs a key is
`achilles tailor`.
