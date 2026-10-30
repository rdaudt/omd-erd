[CmdletBinding()]
param([int]$Port = 8100)

$ErrorActionPreference = 'Stop'
$marketplace = $PSScriptRoot
$projectRoot = Split-Path -Parent $marketplace
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Missing .venv\Scripts\python.exe. Create the Python 3.12 environment first; see the repo README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env') -PathType Leaf)) {
    throw 'Missing .env with OMD_HOST and OMD_TOKEN. Copy .env.example and fill it in.'
}

Write-Host "Data Marketplace demo: http://localhost:$Port/"
Set-Location $marketplace
& $python -m uvicorn app.main:app --port $Port
