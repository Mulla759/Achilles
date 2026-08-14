"""Command line interface.

    achilles import  --resume old.txt --out profiles/me.json
    achilles render  --profile profiles/me.json --out out/me.pdf
    achilles scan    --profile profiles/me.json --jd jd.txt
    achilles tailor  --profile profiles/me.json --jd jd.txt --role "PM Intern" --out out/

`tailor` is the whole product in one command; the others exist so you can debug
one stage without paying for a Claude call.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_settings
from .errors import AchillesError
from .models import Resume
from .render import BACKENDS, active_backend, load_resume, render_one_page

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _mark(ok: bool) -> str:
    return f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"


def _print_reports(scan, rubric, pages: int) -> None:
    print(f"\n{BOLD}Keyword coverage{RESET}  {scan.matched}/{scan.total} = {scan.score}%")
    print(f"  required quals  {scan.required_score}%   {_mark(scan.required_score == 100)}")
    if scan.gaps:
        print(f"{DIM}  gaps (close only if TRUE for you):{RESET}")
        for gap in scan.gaps:
            print(f"    - {gap}")

    print(f"\n{BOLD}Hard rubric{RESET}  {rubric.score}/100")
    for gate in rubric.gates:
        print(f"  [{_mark(gate.passed)}] {gate.name:<15} {gate.score:>3}  {gate.detail}")
        for offender in gate.offenders[:5]:
            print(f"{DIM}         * {offender}{RESET}")

    print(f"\n{BOLD}Pages{RESET} {pages}  {_mark(pages == 1)}")


def _cmd_import(args: argparse.Namespace) -> int:
    from .tailor import parse_resume

    settings = load_settings()
    resume = parse_resume(_read(args.resume), api_key=settings.resolve_key(), settings=settings)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(resume.model_dump_json(indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    used = args.renderer or active_backend()
    resume = load_resume(args.profile)
    rendered, notes = render_one_page(resume, backend=used)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rendered.pdf)
    # The sidecar is whatever source actually produced this PDF.
    sidecar = out.with_suffix(".html" if used == "pdfspark" else ".typ")
    sidecar.write_text(rendered.typst_source, encoding="utf-8")

    print(
        f"Wrote {out} ({rendered.pages} page(s), density {rendered.density:g}, "
        f"renderer {used})"
    )
    for note in notes:
        print(f"{DIM}  note: {note}{RESET}")
    return 0 if rendered.pages == 1 else 1


def _cmd_scan(args: argparse.Namespace) -> int:
    from .pipeline import score_only

    resume = load_resume(args.profile) if args.profile else None
    scan, rubric, pages = score_only(
        jd_text=_read(args.jd),
        resume=resume,
        resume_text=_read(args.resume) if args.resume else None,
    )
    _print_reports(scan, rubric, pages)
    return 0 if (scan.required_score == 100 and rubric.passed and pages == 1) else 1


def _cmd_tailor(args: argparse.Namespace) -> int:
    from .pipeline import build

    resume: Resume | None = load_resume(args.profile) if args.profile else None
    result = build(
        jd_text=_read(args.jd),
        target_role=args.role,
        resume=resume,
        resume_text=_read(args.resume) if args.resume else None,
        availability=args.availability or "",
        max_passes=args.passes,
    )

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    slug = (args.slug or args.role).lower().replace(" ", "-").replace("/", "-")
    import base64

    (outdir / f"{slug}.pdf").write_bytes(base64.b64decode(result.pdf_b64))
    ext = "html" if active_backend() == "pdfspark" else "typ"
    (outdir / f"{slug}.{ext}").write_text(result.typst_source, encoding="utf-8")
    (outdir / f"{slug}.json").write_text(result.resume.model_dump_json(indent=2), encoding="utf-8")

    _print_reports(result.scan, result.rubric, result.pages)
    print(f"\n{BOLD}Passes{RESET} {result.passes}")
    for note in result.notes:
        print(f"{DIM}  note: {note}{RESET}")
    verdict = f"{GREEN}READY{RESET}" if result.ready else f"{RED}NOT READY{RESET}"
    print(f"\n{verdict}  ->  {outdir / (slug + '.pdf')}")
    return 0 if result.ready else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="achilles", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import", help="parse a pasted resume into a JSON profile")
    p.add_argument("--resume", required=True, help="path to plain-text resume")
    p.add_argument("--out", default="profiles/me.json")
    p.set_defaults(fn=_cmd_import)

    p = sub.add_parser("render", help="compile a profile to PDF (no LLM)")
    p.add_argument("--profile", required=True)
    p.add_argument("--out", default="out/resume.pdf")
    p.add_argument(
        "--renderer",
        choices=BACKENDS,
        help="PDF backend; defaults to $ACHILLES_RENDERER, else typst",
    )
    p.set_defaults(fn=_cmd_render)

    p = sub.add_parser("scan", help="grade against a JD (no LLM)")
    p.add_argument("--jd", required=True)
    p.add_argument("--profile")
    p.add_argument("--resume", help="plain-text resume instead of a profile")
    p.set_defaults(fn=_cmd_scan)

    p = sub.add_parser("tailor", help="rewrite, render, and grade against a JD")
    p.add_argument("--jd", required=True)
    p.add_argument("--profile")
    p.add_argument("--resume", help="plain-text resume instead of a profile")
    p.add_argument("--role", required=True)
    p.add_argument("--availability")
    p.add_argument("--passes", type=int, default=None)
    p.add_argument("--out", default="out")
    p.add_argument("--slug", help="output filename stem (defaults to the role)")
    p.set_defaults(fn=_cmd_tailor)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except AchillesError as exc:
        print(f"{RED}error{RESET} {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"{DIM}{exc.hint}{RESET}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"{RED}error{RESET} file not found: {exc.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"{RED}error{RESET} profile is not valid JSON: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
