# CodeLocal — offline coding chatbot (llama.cpp)

No Ollama. No cloud API. Local GGUF model via **llama.cpp** + CodeLocal GUI.

## Layout

```
coding-bot/
├── runtime/          # llama-server.exe + DLLs (Windows CPU build)
├── models/
│   └── qwen2.5-coder-1.5b-instruct-q4_k_m.gguf   (~1.12 GB)
├── scripts/
│   ├── download_assets.ps1
│   ├── start_llama.ps1
│   ├── start_codelocal.ps1
│   └── gui_server.py
└── gui/
    ├── index.html
    ├── app.js
    └── app.css
```

## Personal laptop (test first)

### One-time download (if missing)

```powershell
cd d:\LLM\coding-bot
powershell -ExecutionPolicy Bypass -File scripts\download_assets.ps1
```

- Runner: [llama.cpp Windows CPU](https://github.com/ggml-org/llama.cpp/releases) (`*-bin-win-cpu-x64.zip`)
- Model: [Qwen2.5-Coder-1.5B-Instruct Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF)

### Run

```powershell
cd d:\LLM\coding-bot
powershell -ExecutionPolicy Bypass -File scripts\start_codelocal.ps1
```

- llama.cpp API: `http://127.0.0.1:8080/v1/chat/completions`
- CodeLocal GUI: `http://127.0.0.1:7860/`

Or manually:

```powershell
# Terminal 1
powershell -ExecutionPolicy Bypass -File scripts\start_llama.ps1

# Terminal 2
py -3 scripts\gui_server.py
```

## API used by CodeLocal

| From GUI | Proxied to |
|----------|------------|
| `GET /api/tags` | Fixed local model name (no Ollama) |
| `GET /api/health` | `http://127.0.0.1:8080/v1/models` |
| `POST /api/chat` | `http://127.0.0.1:8080/v1/chat/completions` (OpenAI-compatible SSE) |

## Office laptop (after permission)

Copy the whole `coding-bot` folder (including `runtime/` + `models/`). No Ollama install. Run `scripts\start_codelocal.ps1`. Needs Python 3 for the tiny GUI proxy only.

## Security

- Binds to `127.0.0.1` only
- No external LLM API keys
- Chat stays on the machine
