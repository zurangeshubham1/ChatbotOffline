"""Interactive offline coding chatbot via Ollama."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_MODEL = "coding-bot"
FALLBACK_MODEL = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://127.0.0.1:11434"


SYSTEM = (
    "You are a helpful offline coding assistant. "
    "Prefer clear, correct code with short explanations. "
    "Support Python, Java, JavaScript, SQL, and algorithms."
)


def ollama_tags(base_url: str) -> list[str]:
    req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m.get("name", "") for m in data.get("models", [])]


def pick_model(base_url: str, preferred: str) -> str:
    names = ollama_tags(base_url)
    for candidate in (preferred, FALLBACK_MODEL, "qwen2.5:1.5b-instruct"):
        if any(n == candidate or n.startswith(candidate + ":") for n in names):
            return candidate if candidate in names else next(
                n for n in names if n == candidate or n.startswith(candidate + ":")
            )
        # exact match helpers
        if candidate in names:
            return candidate
    if names:
        return names[0]
    raise RuntimeError(
        "No Ollama models found. Run: ollama pull qwen2.5-coder:1.5b"
    )


def chat_stream(base_url: str, model: str, messages: list[dict]) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "stream": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            obj = json.loads(line)
            piece = obj.get("message", {}).get("content", "")
            if piece:
                chunks.append(piece)
                print(piece, end="", flush=True)
            if obj.get("done"):
                break
    print()
    return "".join(chunks)


def one_shot(base_url: str, model: str, prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    return chat_stream(base_url, model, messages)


def interactive(base_url: str, model: str) -> None:
    messages: list[dict] = [{"role": "system", "content": SYSTEM}]
    print(f"Offline coding chat — model: {model}")
    print("Commands: /exit  /reset  /model")
    print("-" * 40)
    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not user:
            continue
        if user in {"/exit", "/quit", "exit", "quit"}:
            print("Bye.")
            return
        if user == "/reset":
            messages = [{"role": "system", "content": SYSTEM}]
            print("History cleared.")
            continue
        if user == "/model":
            print(f"Using: {model}")
            continue
        messages.append({"role": "user", "content": user})
        print("\nAssistant: ", end="", flush=True)
        try:
            reply = chat_stream(base_url, model, messages)
        except urllib.error.URLError as exc:
            print(f"\nOllama not reachable at {base_url}: {exc}")
            print("Start Ollama Desktop, then try again.")
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": reply})


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline coding chatbot (Ollama)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=OLLAMA_URL)
    parser.add_argument("--prompt", help="Single prompt then exit (smoke test)")
    args = parser.parse_args()

    try:
        model = pick_model(args.url, args.model)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.model != model:
        print(f"Note: '{args.model}' not found, using '{model}'")

    try:
        if args.prompt:
            print(f"Model: {model}\n")
            one_shot(args.url, model, args.prompt)
        else:
            interactive(args.url, model)
    except urllib.error.URLError as exc:
        print(f"Ollama not reachable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
