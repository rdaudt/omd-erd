[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontend = Join-Path $projectRoot 'frontend'
$vite = Join-Path $frontend 'node_modules\vite\bin\vite.js'
$envFile = Join-Path $projectRoot '.env'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Missing .venv\Scripts\python.exe. Create the Python 3.12.10 environment and install backend dependencies; see README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules') -PathType Container) -or -not (Test-Path -LiteralPath $vite -PathType Leaf)) {
    throw 'Missing frontend dependencies. Run npm.cmd ci --prefix frontend.'
}
$node = (Get-Command node.exe -ErrorAction Stop).Source

# Import only adapter settings, without evaluating dotenv values or printing secrets.
# Explicit process environment takes precedence over the local .env file.
if (Test-Path -LiteralPath $envFile -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*(OMD_HOST|OMD_TOKEN|OMD_REQUEST_TIMEOUT_SECONDS|OMD_CACHE_TTL_SECONDS)\s*=\s*(.*?)\s*$') {
            $settingName = $Matches[1]
            $settingValue = $Matches[2]
            if ($settingValue.Length -ge 2 -and (($settingValue.StartsWith('"') -and $settingValue.EndsWith('"')) -or ($settingValue.StartsWith("'") -and $settingValue.EndsWith("'")))) {
                $settingValue = $settingValue.Substring(1, $settingValue.Length - 2)
            }
            if (-not [Environment]::GetEnvironmentVariable($settingName, 'Process')) {
                [Environment]::SetEnvironmentVariable($settingName, $settingValue, 'Process')
            }
        }
    }
}
if ([string]::IsNullOrWhiteSpace($env:OMD_HOST)) { throw 'OMD_HOST is required. Set it in .env or the process environment.' }
if ([string]::IsNullOrWhiteSpace($env:OMD_TOKEN) -or $env:OMD_TOKEN -eq 'replace-with-a-bot-jwt') {
    throw 'OMD_TOKEN must contain a valid bot JWT. Set it in .env or the process environment.'
}
$hostUri = $null
if (-not [Uri]::TryCreate($env:OMD_HOST, [UriKind]::Absolute, [ref]$hostUri) -or $hostUri.Scheme -notin @('http', 'https')) {
    throw 'OMD_HOST must be an absolute HTTP(S) API URL.'
}
foreach ($port in @(8000, 5173)) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try { $listener.Start() }
    catch { throw "Port $port is already in use. Stop the existing listener before starting the demo." }
    finally { $listener.Stop() }
}

$logs = Join-Path $projectRoot '.dev-logs'
$null = New-Item -ItemType Directory -Path $logs -Force
$children = @()

function Wait-LocalServer([int]$port, [System.Diagnostics.Process]$process) {
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($process.HasExited) { throw 'A development server exited. See .dev-logs for details.' }
        $socket = [System.Net.Sockets.TcpClient]::new()
        try {
            $connection = $socket.ConnectAsync('127.0.0.1', $port)
            if ($connection.Wait(200) -and $socket.Connected) { return }
        }
        catch { } # A connection refusal is expected until the server binds.
        finally { $socket.Dispose() }
        Start-Sleep -Milliseconds 200
    }
    throw "Development server on port $port did not start within 120 seconds. See .dev-logs."
}

try {
    # Avoid npm/cmd wrappers. Python's Windows venv launcher can still have a
    # child interpreter, so the finally block stops each owned process tree.
    Write-Host 'Starting adapter (cold OpenMetadata SDK imports can take a minute)...'
    $children += Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--app-dir', ('"{0}"' -f (Join-Path $projectRoot 'backend')), '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'backend.out.log') -RedirectStandardError (Join-Path $logs 'backend.err.log')
    Wait-LocalServer 8000 $children[0]
    $children += Start-Process -FilePath $node -ArgumentList @(('"{0}"' -f $vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs 'frontend.out.log') -RedirectStandardError (Join-Path $logs 'frontend.err.log')
    Wait-LocalServer 5173 $children[1]
    Write-Host 'ERD viewer: http://127.0.0.1:5173'
    Write-Host 'Adapter: http://127.0.0.1:8000 | Logs: .dev-logs | Press Ctrl+C to stop both servers.'
    while ($true) {
        foreach ($child in $children) {
            if ($child.HasExited) { throw 'A development server exited. See .dev-logs for details.' }
        }
        Start-Sleep -Milliseconds 300
    }
}
finally {
    foreach ($child in $children) {
        if (-not $child.HasExited) {
            & (Join-Path $env:SystemRoot 'System32\taskkill.exe') /PID $child.Id /T /F 2>$null | Out-Null
        }
    }
    Write-Host 'Development servers stopped.'
}
