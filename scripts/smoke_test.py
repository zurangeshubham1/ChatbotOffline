"""Quick offline check: Ollama + coding model answer a programming question."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:11434"
PROMPT = (
    "Write a Python function that returns the factorial of n. "
    "Keep it short and include a docstring."
)


def main() -> int:
    print("== Coding bot smoke test ==")
    try:
        with urllib.request.urlopen(f"{URL}/api/tags", timeout=5) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"FAIL: Ollama not running ({exc})")
        print("Start Ollama Desktop, then re-run this script.")
        return 1

    names = [m.get("name", "") for m in tags.get("models", [])]
    print(f"Installed models: {names or '(none)'}")

    preferred = [
        "coding-bot:latest",
        "coding-bot",
        "qwen2.5-coder:1.5b",
        "qwen2.5:1.5b-instruct",
    ]
    model = next((p for p in preferred if p in names), None)
    if model is None:
        # allow tags like qwen2.5-coder:1.5b-base
        for p in preferred:
            hit = next((n for n in names if n.startswith(p.split(":")[0])), None)
            if hit:
                model = hit
                break
    if model is None and names:
        model = names[0]
    if model is None:
        print("FAIL: no models. Run: ollama pull qwen2.5-coder:1.5b")
        return 1

    print(f"Using model: {model}")
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise coding assistant.",
                },
                {"role": "user", "content": PROMPT},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: chat error: {exc}")
        return 1
    elapsed = time.time() - t0
    text = data.get("message", {}).get("content", "").strip()
    print("-" * 40)
    print(text or "(empty reply)")
    print("-" * 40)
    print(f"OK — reply in {elapsed:.1f}s ({len(text)} chars)")
    return 0 if text else 1


if __name__ == "__main__":
    raise SystemExit(main())
