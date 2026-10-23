# Runs arianectl against the editor started by start.ps1: pwsh ariane/ctl.ps1 ping
$env:ARIANE_ENGINE_TCP_PORT = '48731'
$env:ARIANE_ENGINE_TOKEN = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'ariane-agent\token')
& 'C:\dev\gta\sa\tools\ariane-agent\ariane-agent-windows-x64\.venv-agent\Scripts\arianectl.exe' @args
exit $LASTEXITCODE
