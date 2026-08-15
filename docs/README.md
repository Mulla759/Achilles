# docs

All prose documentation lives here. Config files stay at the repo root because
their tooling requires it — see the "Repo layout" section of `../CLAUDE.md`.

| Document | Read it when |
|---|---|
| [STATUS.md](STATUS.md) | **Start here.** Picking the repo up cold, or deciding what to work on next. What shipped in each commit, how the layers fit together, and every open thread. |
| [HANDOFF.md](HANDOFF.md) | Actually tailoring a resume — the operator's loop, editing `templates/typist.typ`, tuning rubric gates, extending the keyword ontology, and the grounding rules. |
| [API.md](API.md) | Calling the HTTP API. Authoritative for request and response shapes. |

Two more docs live outside this folder, both because a tool reads them by name:

- `../CLAUDE.md` — orientation for an AI agent working in this repo. Must be at
  the root; that is where Claude Code looks for it.
- `../components/README.md` — the frontend component conventions, colocated
  with the components it describes.

## Keeping these honest

- `API.md` documents the shapes in `achilles/models.py` **by hand**. Change a
  model field and you must update `API.md` and `lib/types.ts` in the same
  commit; nothing enforces the agreement.
- `HANDOFF.md` predates the provider split and says "Claude" where it now
  means "the configured provider". Its process and grounding rules are still
  authoritative; its provider references are historical.
- `STATUS.md` names a commit and a date at the top. If you make a structural
  change, move that marker.
