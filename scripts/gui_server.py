"""Serve CodeLocal GUI and proxy Ollama (avoids browser CORS)."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui"
OLLAMA = "http://127.0.0.1:11434"


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeLocalGUI/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[gui] {self.address_string()} - {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/tags":
            self._proxy_get("/api/tags")
            return
        if path in ("/", "/index.html"):
            self._file(GUI / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.css":
            self._file(GUI / "app.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._file(GUI / "app.js", "application/javascript; charset=utf-8")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/chat":
            self._proxy_chat()
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def _file(self, file_path: Path, content_type: str | None = None) -> None:
        if not file_path.is_file():
            self._send(404, b"Missing file", "text/plain; charset=utf-8")
            return
        data = file_path.read_bytes()
        ctype = content_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self._send(200, data, ctype)

    def _proxy_get(self, ollama_path: str) -> None:
        try:
            with urllib.request.urlopen(f"{OLLAMA}{ollama_path}", timeout=10) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/json")
            self._send(200, body, ctype)
        except urllib.error.URLError as exc:
            msg = json.dumps({"error": str(exc)}).encode()
            self._send(502, msg, "application/json")

    def _proxy_chat(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        req = urllib.request.Request(
            f"{OLLAMA}/api/chat",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                while True:
                    chunk = resp.read(256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.URLError as exc:
            msg = json.dumps({"error": str(exc)}).encode()
            if not self.wfile.closed:
                try:
                    self._send(502, msg, "application/json")
                except Exception:
                    pass
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeLocal GUI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not GUI.is_dir():
        raise SystemExit(f"GUI folder missing: {GUI}")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"CodeLocal GUI -> {url}")
    print("Keep this window open. Stop with Ctrl+C.")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
