# Achilles HTTP API

Authoritative contract between `achilles/` (Python engine), `api/` (Vercel
serverless handlers), and `app/` (Next.js frontend). If you change a shape
here, change it in `achilles/models.py` in the same commit.

All endpoints are `POST` with `Content-Type: application/json` unless noted.

---

## `GET /api/health`

Liveness plus capability probe. The UI calls this on mount to decide whether to
show the "bring your own key" field as required or optional.

```jsonc
200 {
  "ok": true,
  "version": "0.1.0",
  "model": "claude-opus-5",
  "byo_key_only": false,   // if true, the UI must collect a key
  "server_key": true       // a server-side key is configured
}
```

---

## `POST /api/scan`

Deterministic grading only — **no LLM call, no API key required, sub-second.**
Use it for the "how does my current resume score?" path and for live re-grading
after a manual edit.

```jsonc
// request
{
  "resume": { /* Resume */ },      // one of resume | resume_text is required
  "resume_text": "plain text...",  // if given, graded as-is (no PDF render)
  "jd_text": "paste the JD here"   // required
}
```

```jsonc
// 200
{
  "scan":   { /* ScanReport */ },
  "rubric": { /* RubricReport */ },
  "pages":  1
}
```

---

## `POST /api/tailor`

The main event: rewrite → render → grade, looping until it passes or
`max_passes` is hit.

```jsonc
// request
{
  "resume_text": "paste your old resume",  // one of resume_text | resume required
  "resume": { /* Resume */ },              // skips the parse step if you have it
  "jd_text": "paste the job description",  // required, >= 40 chars
  "target_role": "Product Manager Intern", // required
  "availability": "May 2027 - Aug 2027",   // optional, some JDs require it
  // Reserved. Accepted and ignored today — nothing reads it yet.
  "company_url": "https://...",
  "api_key": "sk-ant-...",                 // optional; falls back to server key
  "max_passes": 3                          // optional, 1-5
}
```

```jsonc
// 200 — BuildResult
{
  "ready": true,            // pages==1 && required==100 && score>=95 && rubric passes
  "pages": 1,
  "passes": 2,              // how many tailor->grade cycles it took
  "resume": { /* Resume */ },            // the tailored result
  "source_resume": { /* Resume */ },     // what went in, for a per-bullet diff
  "typst_source": "...",    // editable source, for the "download .typ" button
  "pdf_b64": "JVBERi0...",  // the artifact
  "text": "extracted text ATS would read",
  "scan": {
    "score": 96,
    "required_score": 100,
    "matched": 25, "total": 26,
    "word_count": 612,
    "gaps": ["market / case analysis"],
    "hits": [ { "label": "SQL", "group": "metrics", "required": true,
                "hit": true, "matched_form": "sql" } ]
  },
  "rubric": {
    "passed": true,
    "score": 94,
    "gates": [ { "name": "one_page", "passed": true, "score": 100,
                 "detail": "1 page", "offenders": [] } ]
  },
  "notes": ["Tightened density to 0.4 to hold one page."]
}
```

### Rubric gate names

Stable identifiers — the UI maps these to labels and icons.

| `name`           | Checks |
|------------------|--------|
| `graduation`     | Degree, school, and a parseable graduation date are present. |
| `semantics`      | Bullets lead with strong action verbs; no weak/filler openers ("Responsible for", "Helped with"). |
| `metrics`        | A high enough share of bullets carry a real number. |
| `storyline`      | Bullets read as action → what was built → result, not a duty list. |
| `one_page`       | Renders to exactly one page. |
| `mac`            | Per bullet: **M**etric + **A**ction + **C**ontext all present. |
| `ats_parseable`  | Single column, standard section headers, selectable text, no images/tables. |

---

## Errors

Every non-2xx has the same shape. `hint` is written for the end user; show it.

```jsonc
{ "error": "missing_api_key",
  "message": "No Anthropic API key configured.",
  "hint": "Paste your own key, or set ANTHROPIC_API_KEY in .env.local." }
```

| HTTP | `error`            | Meaning |
|------|--------------------|---------|
| 400  | `bad_input`        | Missing/short JD, no resume, bad JSON, a field of the wrong type (`jd_text: []`), a malformed `resume` object, or `max_passes` outside 1-5. |
| 401  | `missing_api_key`  | No key from the request or the environment. |
| 422  | `ungrounded_claim` | The model invented something not in the source resume. |
| 500  | `render_failed`    | Typst could not compile — a template bug, not user error. |
| 502  | `upstream_error`   | Claude API refused, rate-limited, or errored. |
