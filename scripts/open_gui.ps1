$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
Write-Host "Starting CodeLocal GUI..."
py -3 scripts\gui_server.py
