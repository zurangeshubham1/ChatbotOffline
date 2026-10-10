"""Smoke test CodeLocal against llama.cpp OpenAI API (via GUI proxy or direct)."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

GUI = "http://127.0.0.1:7860"
LLAMA = "http://127.0.0.1:8080"
PROMPT = "Write a Python function that returns the factorial of n. Keep it short."


def get_json(url: str, timeout: int = 10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print("== CodeLocal / llama.cpp smoke test ==")
    try:
        models = get_json(f"{LLAMA}/v1/models")
    except urllib.error.URLError as exc:
        print(f"FAIL: llama.cpp not on :8080 ({exc})")
        print("Run: powershell -File scripts\\start_llama.ps1")
        return 1
    print(f"llama.cpp models OK: {len(models.get('data') or models.get('models') or [])}")

    try:
        health = get_json(f"{GUI}/api/health")
        print(f"GUI health: {health}")
    except urllib.error.URLError:
        print("WARN: GUI not on :7860 (optional for this test)")

    payload = json.dumps(
        {
            "model": "qwen2.5-coder-1.5b-instruct-q4_k_m",
            "messages": [
                {"role": "system", "content": "You are a concise coding assistant."},
                {"role": "user", "content": PROMPT},
            ],
            "stream": False,
            "temperature": 0.2,
        }
    ).encode()
    req = urllib.request.Request(
        f"{LLAMA}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    print("-" * 40)
    print(text or "(empty)")
    print("-" * 40)
    print(f"OK in {time.time() - t0:.1f}s")
    return 0 if text else 1


if __name__ == "__main__":
    raise SystemExit(main())
