# Achilles

Paste a job description and your old resume. Get back a tailored, one-page PDF
and a score telling you whether it's actually ready to send.

Built for students. Four steps, no formatting, no guessing.

```
paste the job description  ->  paste your resume  ->  name the role  ->  get a PDF + a score
```

---

## Why it exists

Most resumes are rejected before a person reads them. Two reasons, both fixable:

1. **Keyword matching.** Applicant tracking systems search your resume for the
   posting's exact words. Say "user research" when the posting says "discovery
   interviews" and you don't match — even though you did the work.
2. **Nobody tells you what "good" looks like.** You find out you had a weak
   bullet after you've been rejected, not before.

Achilles closes both. It rewrites your resume in the posting's vocabulary, then
grades the result against a fixed rubric and shows you exactly what's still
weak.

**The one rule it never breaks: it rewords, it never invents.** Everything in
the output traces back to something in your original resume. If the job wants
something you don't have, it leaves the gap open. A gap is survivable; a
fabrication you can't defend in an interview is not.

---

## Quickstart

You need Python 3.11+ and Node 20+. Get an API key from
[console.anthropic.com](https://console.anthropic.com/settings/keys).

```bash
git clone <this repo> && cd Achilles
uv venv .venv --python 3.13
uv pip install --python .venv -r requirements.txt
npm install

echo ANTHROPIC_API_KEY=sk-ant-your-key > .env.local   # git-ignored
npm run dev                                            # http://localhost:3000
```

<details>
<summary>PowerShell</summary>

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv -r requirements.txt
npm install
"ANTHROPIC_API_KEY=sk-ant-your-key" | Out-File .env.local -Encoding utf8
npm run dev
```
</details>

### In the browser

Paste the posting, paste your resume, type the role, press **Ctrl+Enter**.
Takes 30–90 seconds. You get a PDF, a coverage score, and a list of what to fix.

Want a score without spending anything? Press **Ctrl+S** — that runs the
grading only, no AI call, no key needed.

| Key | Does |
|---|---|
| `Ctrl+Enter` | Tailor the resume |
| `Ctrl+S` | Score only (free, instant) |
| `Ctrl+K` | Jump to the API key field |
| `?` | Show all shortcuts |

### From the terminal

```bash
# the whole thing in one command
achilles tailor --resume old-resume.txt --jd job.txt --role "Product Manager Intern" --out out/

# score your current resume against a posting — no AI call, no key
achilles scan --resume old-resume.txt --jd job.txt
```

Four commands total:

| Command | What it does | Costs money? |
|---|---|---|
| `achilles tailor` | Rewrite, render, grade, repeat until it passes | Yes |
| `achilles scan` | Grade against a posting | No |
| `achilles render` | Turn a saved profile into a PDF | No |
| `achilles import` | Turn a pasted resume into a reusable JSON profile | Yes |

Run any of them with `--help` for the full flags.

**Tip:** `tailor --out` also writes a `.json` profile. Keep it and pass it as
`--profile` next time — the following posting then tailors from your improved
resume instead of your original.

---

## The score

Two numbers and seven checks.

**Coverage** — how many of the posting's terms your resume actually contains.
Required qualifications are tracked separately, and that's the one that matters:
95% overall with a missed *required* term is still a rejection.

**The rubric** — seven pass/fail gates:

| Gate | Passes when |
|---|---|
| Graduation | Degree, school, and a readable graduation date are all present |
| Word choice | Bullets open with a strong verb — no "Responsible for", no "Helped with" |
| Metrics | Enough bullets carry a real number |
| Storyline | Bullets read as *did X → which caused Y*, not a list of duties |
| One page | Renders to exactly one page |
| MAC | Every bullet has a **M**etric, an **A**ction verb, and **C**ontext |
| ATS parseable | Single column, standard headings, selectable text, no tables |

Anything that fails tells you which bullet and which piece is missing —
`MISSING metric — Built a multi-turn agentic system for post-session coaching`.

It won't fake a pass. A posting it doesn't recognise reports thin coverage
rather than a meaningless 100%.

---

## How it works

```
job description ──> extract keywords ──┐
                                       ├──> rewrite (Claude) ──> render PDF ──> grade
your resume ───────> parse to JSON ────┘            ^                            │
                                                    └──── repair the failures ────┘
```

Each pass costs one API call, so it stops as soon as the result is good enough
rather than always using its full budget. A repair pass gets the exact gate
failures and missing keywords from the previous attempt, so it fixes named
problems instead of rewriting blind.

| File | Job |
|---|---|
| `achilles/keywords.py` | Pulls requirements out of the posting (no AI, just a curated ontology) |
| `achilles/scan.py` | Word-boundary keyword matching |
| `achilles/rubric.py` | The seven gates and their thresholds |
| `achilles/sanitize.py` | Cleans untrusted input before anything reads it |
| `achilles/tailor.py` | The Claude calls and the reword-never-invent prompt |
| `achilles/render.py` | Resume → PDF, and the one-page fitting |
| `achilles/pipeline.py` | The rewrite → render → grade loop |
| `templates/typist.typ` | The resume layout |
| `api/`, `app/` | HTTP endpoints and the web UI |

**One page happens automatically.** If your content spills over, the renderer
tightens spacing in steps until it fits. It only tells you to cut something when
compression has run out — squeezing whitespace is free, deleting an
accomplishment isn't.

---

## Configuration

Everything optional except the key.

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Your key. Used when a visitor doesn't bring their own. |
| `ACHILLES_MODEL` | `claude-opus-5` | The rubric thresholds are tuned against this model. |
| `ACHILLES_EFFORT` | `high` | `low` \| `medium` \| `high` \| `xhigh` \| `max` |
| `ACHILLES_MAX_PASSES` | `3` | Rewrite→grade cycles for the CLI. |
| `ACHILLES_BYO_KEY_ONLY` | `0` | Set to `1` on a public deploy so visitors must use their own key. |
| `ACHILLES_RENDERER` | `typst` | `typst` or `pdfspark`. |
| `ACHILLES_ALLOWED_ORIGINS` | — | Comma-separated origins allowed to call the API cross-site. |

---

## PDF backends

Two renderers, same output quality. Both produce identical scores.

| | `typst` (default) | `pdfspark` |
|---|---|---|
| Runs | Locally, offline | Calls pdfspark.dev |
| Edit the look by | Editing `templates/typist.typ` | Editing CSS in `achilles/html_render.py` |
| Speed | ~0.8s | ~3.2s |

```bash
achilles render --profile profiles/me.json --out out/me.pdf --renderer pdfspark
```

**Privacy note:** `pdfspark` sends your resume to a third-party service. The
default is local, so this only happens if you turn it on.

---

## Your data

- **Nothing is saved in your browser.** Your resume and the posting live in
  memory and disappear on reload. Earlier versions used `localStorage`; that was
  removed, and anything previously stored is deleted on your next visit.
- **Your API key is never written to disk.**
- **Your real resume is git-ignored.** `profiles/*.json` and `resume/` never get
  committed. `profiles/example.json` is a fictional student.
- **Untrusted input is cleaned** before anything reads it: invisible characters,
  text-direction overrides, and control characters are stripped, and the app
  tells you when it removed something rather than quietly changing your
  document.

---

## Deploying

```bash
npx vercel login
npx vercel --prod
```

Set `ANTHROPIC_API_KEY` in the Vercel dashboard.

Two things to know before a public deploy:

- **Set `ACHILLES_BYO_KEY_ONLY=1`** unless you intend to pay for strangers'
  resumes. There's per-IP rate limiting either way, but that's a speed bump,
  not a spend cap.
- **The function is capped at 60 seconds** (`vercel.json`), so `/api/tailor`
  runs one pass per request. The UI sends the result back for another pass when
  you ask it to. Raise `maxDuration` if your plan allows longer.

---

## Development

```bash
npm run dev        # web UI + Python API together
npm run test       # 123 tests
npm run typecheck
npm run build
```

The Python API runs through `scripts/devapi.py` in development, using the same
handler code Vercel runs in production.

---

## What it can't do

- **It can't give you experience you don't have.** If a posting needs Kubernetes
  and you've never touched it, that gap stays open. By design.
- **Keyword extraction is a curated list.** An unusual posting may match fewer
  terms than it should. `achilles/keywords.py` is a plain list — add to it.
- **`tailor` costs real money** — one Claude call per pass.
- **The grounding check is a warning, not a guarantee.** It flags numbers in the
  output that weren't in your input, but you should still read what it wrote
  before you send it.

---

## More

- `docs/HANDOFF.md` — the operator's guide: tuning the rubric, extending the keyword
  ontology, and the grounding rules
- `docs/API.md` — the HTTP contract
- `CLAUDE.md` — orientation for an AI agent working in this repo

MIT licensed.
