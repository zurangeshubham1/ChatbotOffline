# Start llama.cpp OpenAI-compatible server on 127.0.0.1:8080
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime"
$Model = Join-Path $Root "models\qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
$Server = Join-Path $Runtime "llama-server.exe"
$Llama = Join-Path $Runtime "llama.exe"

if (-not (Test-Path $Model)) {
    throw "Model missing: $Model`nRun: powershell -File scripts\download_assets.ps1"
}

Set-Location $Runtime
Write-Host "Starting llama.cpp with:"
Write-Host "  model: $Model"
Write-Host "  api:   http://127.0.0.1:8080/v1/chat/completions"
Write-Host "Stop with Ctrl+C"
Write-Host ""

if (Test-Path $Server) {
    & $Server -m $Model --host 127.0.0.1 --port 8080 -c 4096
} elseif (Test-Path $Llama) {
    & $Llama serve -m $Model --host 127.0.0.1 --port 8080 -c 4096
} else {
    throw "Neither llama-server.exe nor llama.exe found in $Runtime"
}
