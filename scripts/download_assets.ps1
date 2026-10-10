# Download llama.cpp Windows CPU build + Qwen2.5-Coder Q4_K_M GGUF
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $Root "runtime"
$Models = Join-Path $Root "models"
$Tmp = Join-Path $Root "tmp"
New-Item -ItemType Directory -Force -Path $Runtime, $Models, $Tmp | Out-Null

Write-Host "== llama.cpp Windows CPU =="
$rels = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20"
$asset = $null
$tag = $null
foreach ($r in $rels) {
    $a = $r.assets | Where-Object { $_.name -like "*win-cpu-x64.zip" } | Select-Object -First 1
    if ($a) { $asset = $a; $tag = $r.tag_name; break }
}
if (-not $asset) { throw "No win-cpu-x64.zip found on llama.cpp releases" }
Write-Host "Using $tag / $($asset.name)"
$zip = Join-Path $Tmp "llama-cpu.zip"
curl.exe -L --retry 3 -o $zip $asset.browser_download_url
$extract = Join-Path $Tmp "llama-extract"
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $extract -Force
Copy-Item (Join-Path $extract "*") $Runtime -Recurse -Force
Write-Host "Runtime ready: $Runtime"

Write-Host "== Qwen2.5-Coder-1.5B-Instruct Q4_K_M GGUF =="
py -3 -c @"
from huggingface_hub import hf_hub_download
p = hf_hub_download(
    repo_id='Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF',
    filename='qwen2.5-coder-1.5b-instruct-q4_k_m.gguf',
    local_dir=r'$($Models -replace '\\','\\')',
)
print(p)
"@

Write-Host "Done."
Write-Host "Next: powershell -File scripts\start_codelocal.ps1"
