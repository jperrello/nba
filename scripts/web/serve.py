#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "web" / "dist"
INDEX = DIST / "index.html"
ASSETS = DIST / "assets"

ALLOWED_FIRST = {"schema", "sql", "lineup", "players", "sim", "ingest", "stints", "--help"}

CTYPE = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff": "font-woff",
    ".woff2": "font-woff2",
    ".txt": "text/plain; charset=utf-8",
}


def safe(argv: list[str]) -> bool:
    if not argv:
        return False
    first = argv[0]
    if first not in ALLOWED_FIRST:
        return False
    if first == "ingest" and "--dry-run" not in argv and "--help" not in argv:
        return False
    if first == "sql":
        if len(argv) < 2:
            return False
        q = argv[1].lower()
        for bad in (";", "insert ", "update ", "delete ", "drop ", "alter ", "create ", "truncate "):
            if bad in q:
                return False
        if not q.lstrip().startswith(("select", "with ", "explain")):
            return False
    return True


def under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class H(BaseHTTPRequestHandler):
    def log_message(self, *a, **k):
        sys.stderr.write("[serve] " + (a[0] % a[1:]) + "\n")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, p: Path) -> None:
        ctype = CTYPE.get(p.suffix.lower(), "application/octet-stream")
        self._send(200, p.read_bytes(), ctype)

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path == "/api/health":
            return self._send(200, json.dumps({"live": True}).encode(), "application/json")
        if path in ("/", "/index.html"):
            if not INDEX.exists():
                return self._send(503, b"run `make web` first", "text/plain")
            return self._serve_file(INDEX)
        if path.startswith("/assets/"):
            target = (DIST / path.lstrip("/")).resolve()
            if not under(target, ASSETS) or not target.exists() or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            return self._serve_file(target)
        return self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path != "/api/run":
            return self._send(404, b"not found", "text/plain")
        n = int(self.headers.get("content-length", "0"))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, b'{"error":"bad json"}', "application/json")
        argv = body.get("argv") or []
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return self._send(400, b'{"error":"argv must be list[str]"}', "application/json")
        if not safe(argv):
            return self._send(
                403,
                json.dumps({"error": "command not in allowlist", "argv": argv}).encode(),
                "application/json",
            )
        nba = shutil.which("nba") or str(ROOT / ".venv" / "bin" / "nba")
        try:
            p = subprocess.run(
                [nba, *argv],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )
            payload = {"stdout": p.stdout, "stderr": p.stderr, "rc": p.returncode}
        except subprocess.TimeoutExpired:
            payload = {"stdout": "", "stderr": "timeout", "rc": 124}
        return self._send(200, json.dumps(payload).encode(), "application/json")


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"nba web gateway on http://127.0.0.1:{port}", file=sys.stderr)
    print("ctrl-c to stop", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
