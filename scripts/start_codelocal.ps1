# Start llama.cpp (if needed) + CodeLocal GUI
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Test-PortOpen([int]$Port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $Port)
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-PortOpen 8080)) {
    Write-Host "Starting llama.cpp on :8080 ..."
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $Root "scripts\start_llama.ps1")
    )
    $deadline = (Get-Date).AddMinutes(3)
    while (-not (Test-PortOpen 8080)) {
        if ((Get-Date) -gt $deadline) {
            throw "llama.cpp did not open port 8080. Check the other window."
        }
        Start-Sleep -Seconds 2
        Write-Host "  waiting for llama.cpp ..."
    }
} else {
    Write-Host "llama.cpp already running on :8080"
}

Write-Host "Starting CodeLocal GUI on :7860 ..."
py -3 (Join-Path $Root "scripts\gui_server.py")
