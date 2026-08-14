"""Local stand-in for the Vercel Python runtime.

`next dev` serves the React app but knows nothing about `api/*.py`, and
`vercel dev` needs a Vercel login. This module routes /api/<name> to the
`handler` class in api/<name>.py using the same BaseHTTPRequestHandler contract
Vercel uses, so what runs locally is the same code that runs deployed.

    python scripts/devapi.py --port 8787

`npm run dev` starts this alongside Next, and next.config.mjs rewrites
/api/* to it.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _reexec_in_venv() -> None:
    """`npm run dev` invokes bare `python`, which on most machines is the system
    interpreter without our dependencies. Hand off to .venv rather than making
    the contributor remember to activate it first."""
    if os.environ.get("ACHILLES_DEV_REEXEC"):
        return  # already handed off once; don't loop
    try:
        import typst  # noqa: F401

        return  # current interpreter is already good
    except ModuleNotFoundError:
        pass

    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
        ROOT / ".venv" / "bin" / "python",  # macOS / Linux
    ]
    venv_python = next((p for p in candidates if p.exists()), None)
    if venv_python is None:
        sys.exit(
            "Dependencies are missing and no .venv was found.\n"
            "  uv venv .venv --python 3.13\n"
            "  uv pip install --python .venv -r requirements.txt"
        )
    env = {**os.environ, "ACHILLES_DEV_REEXEC": "1"}
    raise SystemExit(subprocess.call([str(venv_python), *sys.argv], env=env))


_reexec_in_venv()
API_DIR = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API_DIR))  # so `from _lib import ...` resolves as it does on Vercel

_lock = threading.Lock()
_cache: dict[str, type[BaseHTTPRequestHandler]] = {}


def _load(name: str) -> type[BaseHTTPRequestHandler] | None:
    """Import api/<name>.py fresh so edits show up without a restart."""
    path = API_DIR / f"{name}.py"
    if not path.exists() or name.startswith("_"):
        return None
    with _lock:
        spec = importlib.util.spec_from_file_location(f"_api_{name}", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        handler = getattr(module, "handler", None)
        _cache[name] = handler
        return handler


class Router(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _dispatch(self, verb: str) -> None:
        route = self.path.split("?", 1)[0].strip("/")
        route = route[4:] if route.startswith("api/") else route

        try:
            handler_cls = _load(route)
        except Exception as exc:  # a syntax error in a handler shouldn't kill the server
            self._fail(500, f"Failed to import api/{route}.py: {type(exc).__name__}: {exc}")
            return

        if handler_cls is None:
            self._fail(404, f"No handler at api/{route}.py")
            return

        # Re-dispatch into the Vercel-style handler using this live connection.
        shim = handler_cls.__new__(handler_cls)
        shim.rfile, shim.wfile = self.rfile, self.wfile
        shim.headers, shim.path, shim.command = self.headers, self.path, verb
        shim.request_version, shim.client_address, shim.server = (
            self.request_version,
            self.client_address,
            self.server,
        )
        shim.send_response = self.send_response  # type: ignore[method-assign]
        shim.send_header = self.send_header  # type: ignore[method-assign]
        shim.end_headers = self.end_headers  # type: ignore[method-assign]
        getattr(shim, f"do_{verb}")()

    def _fail(self, status: int, message: str) -> None:
        body = f'{{"error":"dev_router","message":{message!r},"hint":""}}'.encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._dispatch("OPTIONS")

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("  api  %s\n" % (fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    # Load .env.local the way Next does, so the API key works in local dev.
    env_file = ROOT / ".env.local"
    if env_file.exists():
        import os

        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Router)
    print(f"achilles dev api  ->  http://127.0.0.1:{args.port}/api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
