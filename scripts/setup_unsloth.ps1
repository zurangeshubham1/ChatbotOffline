# Install Unsloth Core from the local clone (Windows).
# Full QLoRA training still needs an NVIDIA GPU.
$ErrorActionPreference = "Stop"
$Repo = "d:\LLM\unsloth"
$Venv = "d:\LLM\coding-bot\.venv"

if (-not (Test-Path $Repo)) {
    throw "Unsloth repo not found at $Repo"
}

# Ensure uv is available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    winget install --id=astral-sh.uv -e --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "== Creating venv at $Venv =="
uv venv $Venv --python 3.11
& "$Venv\Scripts\Activate.ps1"

Write-Host "== Installing torchao + unsloth from local clone =="
uv pip install torchao
uv pip install -e $Repo --torch-backend=auto

Write-Host "== Dry-run dataset check =="
py -3 "d:\LLM\coding-bot\scripts\finetune_unsloth.py" --dry-run

Write-Host "Unsloth install finished."
Write-Host "Train (NVIDIA GPU required): py -3 scripts\finetune_unsloth.py"
