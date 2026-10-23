# Opens a scratch session in the running Ariane and replays upstream's RemoveBuildingForPlayer list on it.
# -WithoutPanes also hides every window001 the maps place, as a server would once the shells carry their own glass.
param([string]$GameDir = 'D:\Games\GTA San Andreas\ariane-sa', [string]$Session = 'scavenge-removals', [switch]$WithoutPanes)

$ctl = Join-Path $PSScriptRoot 'ctl.ps1'
pwsh $ctl scene ariane/agent_scratch.ipl (Join-Path $GameDir 'scavenge\agent-scratch.ipl') | Out-Null
pwsh $ctl session begin $Session | Out-Null
# SA-MP's -1 (every model in the radius) has no Ariane equivalent; removals.py skips it
$env:ARIANE_ENGINE_TCP_PORT = '48731'
$env:ARIANE_ENGINE_TOKEN = Get-Content -Raw (Join-Path $env:LOCALAPPDATA 'ariane-agent\token')
$python = 'C:\dev\gta\sa\tools\ariane-agent\ariane-agent-windows-x64\.venv-agent\Scripts\python.exe'
$extra = if ($WithoutPanes) { @('--without-panes') } else { @() }
& $python (Join-Path $PSScriptRoot 'removals.py') $GameDir @extra
