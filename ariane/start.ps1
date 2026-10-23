# Starts the agent-enabled Ariane on the dedicated game copy with the fixed port/token the MCP server uses.
# The token lives outside the repo in %LOCALAPPDATA%\ariane-agent\token (created on first run).
param([string]$GameDir = 'D:\Games\GTA San Andreas\ariane-sa')

$tokenFile = Join-Path $env:LOCALAPPDATA 'ariane-agent\token'
if (-not (Test-Path $tokenFile)) {
    New-Item -ItemType Directory -Force (Split-Path $tokenFile) | Out-Null
    [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N') | Set-Content -NoNewline $tokenFile
}
$env:ARIANE_ENGINE_TCP_PORT = '48731'
$env:ARIANE_ENGINE_TOKEN = Get-Content -Raw $tokenFile
Start-Process (Join-Path $GameDir 'ariane.exe') -WorkingDirectory $GameDir
