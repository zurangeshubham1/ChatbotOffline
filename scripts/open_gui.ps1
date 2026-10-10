# Launch full CodeLocal stack (llama.cpp + GUI)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
powershell -ExecutionPolicy Bypass -File .\scripts\start_codelocal.ps1
