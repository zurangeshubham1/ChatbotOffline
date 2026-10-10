# Coding Bot (offline)

Local ChatGPT-style coding assistant.

## Your PC right now

| Item | Status |
|------|--------|
| GPU | Intel UHD only (no NVIDIA CUDA) |
| RAM | 16 GB |
| Ollama | Installed — used for offline chat |
| Unsloth repo | `d:\LLM\unsloth` — for fine-tune when GPU available |

**Offline chat works today** via Ollama.  
**Unsloth LoRA fine-tune needs an NVIDIA GPU** (or free Colab T4). Jarvis (voice + desktop) comes later.

## 1) Run offline chat (GUI — recommended)

```powershell
cd d:\LLM\coding-bot
py -3 scripts\gui_server.py
```

Browser opens at [http://127.0.0.1:7860/](http://127.0.0.1:7860/) — CodeLocal GUI.

Or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\open_gui.ps1
```

Terminal chat (optional): `py -3 scripts\chat.py` · or `ollama run coding-bot`

## 2) Fine-tune with your Q&A (Unsloth)

Dataset: `data\coding_qa.jsonl` (add more rows anytime — one JSON object per line).

Config: `configs\train_coder.yaml`  
Base model: `unsloth/Qwen2.5-Coder-1.5B-Instruct`

```powershell
# Install Unsloth Core from local clone
powershell -ExecutionPolicy Bypass -File scripts\setup_unsloth.ps1

# Dry-run (works without GPU)
py -3 scripts\finetune_unsloth.py --dry-run

# Real train — NVIDIA GPU required
py -3 scripts\finetune_unsloth.py
```

Or from the Unsloth CLI (after Studio/Core install):

```powershell
cd d:\LLM\unsloth
unsloth train -c ..\coding-bot\configs\train_coder.yaml
```

## 3) Later: Jarvis

After chat + coding + offline are solid, add voice recognition and desktop automation as a separate step.
