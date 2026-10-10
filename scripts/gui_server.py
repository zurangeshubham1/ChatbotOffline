"""Serve SuperBot GUI, SQLite history API, and llama.cpp OpenAI-compatible proxy."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chat_db import get_store  # noqa: E402

GUI = ROOT / "gui"
LLAMA = "http://127.0.0.1:8080"
MODEL_ID = "qwen2.5-coder-1.5b-instruct-q4_k_m"
MODEL_FILE = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"


class Handler(BaseHTTPRequestHandler):
    server_version = "SuperBotGUI/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[gui] {self.address_string()} - {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            self._health()
            return
        if path == "/api/tags":
            self._json(
                200,
                {
                    "models": [{"name": MODEL_ID, "file": MODEL_FILE}],
                    "backend": "llama.cpp",
                    "endpoint": f"{LLAMA}/v1/chat/completions",
                    "app": "SuperBot",
                },
            )
            return
        if path == "/api/conversations":
            q = (qs.get("q") or [""])[0]
            try:
                self._json(200, {"conversations": get_store().list_conversations(q)})
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
            return
        if path.startswith("/api/conversations/"):
            parts = path.strip("/").split("/")
            # /api/conversations/{id}
            if len(parts) == 3 and parts[2].isdigit():
                try:
                    self._json(200, get_store().get_conversation(int(parts[2])))
                except KeyError as exc:
                    self._json(404, {"error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    self._json(500, {"error": str(exc)})
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
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/chat":
            self._proxy_chat()
            return
        if path == "/api/conversations":
            try:
                body = self._read_json()
                title = body.get("title") or "New chat"
                self._json(201, get_store().create_conversation(title))
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"error": str(exc)})
            return
        if path.startswith("/api/conversations/") and path.endswith("/messages"):
            parts = path.strip("/").split("/")
            # api conversations {id} messages
            if len(parts) == 4 and parts[2].isdigit():
                try:
                    body = self._read_json()
                    msg = get_store().add_message(
                        int(parts[2]),
                        body.get("role", ""),
                        body.get("content", ""),
                    )
                    self._json(201, msg)
                except KeyError as exc:
                    self._json(404, {"error": str(exc)})
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    self._json(500, {"error": str(exc)})
                return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_PATCH(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "conversations" and parts[2].isdigit():
            try:
                body = self._read_json()
                self._json(200, get_store().rename_conversation(int(parts[2]), body.get("title", "")))
            except KeyError as exc:
                self._json(404, {"error": str(exc)})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "conversations" and parts[2].isdigit():
            try:
                get_store().delete_conversation(int(parts[2]))
                self._json(200, {"ok": True})
            except KeyError as exc:
                self._json(404, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": str(exc)})
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
        try:
            get_store().list_conversations()
            db_ok = True
        except Exception as exc:  # noqa: BLE001
            db_ok = False
            detail = f"{detail}; db: {exc}"
        self._json(
            200 if ok else 503,
            {"ok": ok, "backend": "llama.cpp", "db_ok": db_ok, "detail": detail, "app": "SuperBot"},
        )

    def _proxy_chat(self) -> None:
        try:
            incoming = self._read_json()
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
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
            msg = {
                "error": str(exc),
                "hint": "Start llama.cpp first: scripts\\start_llama.ps1",
            }
            if not getattr(self, "wfile", None) or self.wfile.closed:
                return
            try:
                self._json(502, msg)
            except Exception:
                pass
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="SuperBot GUI server (llama.cpp + SQLite)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not GUI.is_dir():
        raise SystemExit(f"GUI folder missing: {GUI}")

    # Ensure DB is ready at startup
    get_store()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"SuperBot GUI -> {url}")
    print(f"Backend API  -> {LLAMA}/v1/chat/completions")
    print(f"Chat DB      -> {ROOT / 'data' / 'chat_history.db'}")
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
