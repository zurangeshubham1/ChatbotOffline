"""Serve CodeLocal GUI and proxy llama.cpp OpenAI-compatible API."""

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
LLAMA = "http://127.0.0.1:8080"
MODEL_ID = "qwen2.5-coder-1.5b-instruct-q4_k_m"
MODEL_FILE = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"


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
        if path == "/api/health":
            self._health()
            return
        if path == "/api/tags":
            # Fixed local model list — no Ollama dependency.
            body = json.dumps(
                {
                    "models": [{"name": MODEL_ID, "file": MODEL_FILE}],
                    "backend": "llama.cpp",
                    "endpoint": f"{LLAMA}/v1/chat/completions",
                }
            ).encode()
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            self._file(GUI / "index.html", "text/html; charset=utf-8")
            return
        if path in ("/app.css", "/style.css"):
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

    def _health(self) -> None:
        ok = False
        detail = "llama.cpp not reachable on 127.0.0.1:8080"
        try:
            with urllib.request.urlopen(f"{LLAMA}/v1/models", timeout=3) as resp:
                ok = resp.status == 200
                detail = "ok" if ok else f"status {resp.status}"
        except urllib.error.URLError as exc:
            detail = str(exc.reason if hasattr(exc, "reason") else exc)
        body = json.dumps({"ok": ok, "backend": "llama.cpp", "detail": detail}).encode()
        self._send(200 if ok else 503, body, "application/json; charset=utf-8")

    def _proxy_chat(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            incoming = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return

        payload = {
            "model": incoming.get("model") or MODEL_ID,
            "messages": incoming.get("messages") or [],
            "stream": bool(incoming.get("stream", True)),
            "temperature": float(
                (incoming.get("options") or {}).get("temperature", incoming.get("temperature", 0.2))
            ),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{LLAMA}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                self.send_response(200)
                ctype = resp.headers.get("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                while True:
                    chunk = resp.read(256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.URLError as exc:
            msg = json.dumps(
                {
                    "error": str(exc),
                    "hint": "Start llama.cpp first: scripts\\start_llama.ps1",
                }
            ).encode()
            if not getattr(self, "wfile", None) or self.wfile.closed:
                return
            try:
                self._send(502, msg, "application/json")
            except Exception:
                pass
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="CodeLocal GUI server (llama.cpp)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not GUI.is_dir():
        raise SystemExit(f"GUI folder missing: {GUI}")

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"CodeLocal GUI -> {url}")
    print(f"Backend API  -> {LLAMA}/v1/chat/completions")
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
