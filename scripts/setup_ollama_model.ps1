# Create a local Ollama coding assistant from the Modelfile.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "== Pull coding model =="
ollama pull qwen2.5-coder:1.5b

Write-Host "== Create local coding-bot model =="
ollama create coding-bot -f Modelfile

Write-Host "== Done. Try: =="
Write-Host "  ollama run coding-bot"
Write-Host "  py -3 scripts\chat.py"
Write-Host "  py -3 scripts\smoke_test.py"
