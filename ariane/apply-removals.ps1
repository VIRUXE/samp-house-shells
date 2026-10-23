# Opens a scratch session in the running Ariane and replays upstream's RemoveBuildingForPlayer list on it.
param([string]$GameDir = 'D:\Games\GTA San Andreas\ariane-sa', [string]$Session = 'scavenge-removals')

$ctl = Join-Path $PSScriptRoot 'ctl.ps1'
pwsh $ctl scene ariane/agent_scratch.ipl (Join-Path $GameDir 'scavenge\agent-scratch.ipl') | Out-Null
pwsh $ctl session begin $Session | Out-Null
$removals = Get-Content -Raw (Join-Path $GameDir 'scavenge\removals.json') | ConvertFrom-Json
$failed = 0
foreach ($r in $removals) {
    # SA-MP's -1 means every model in the radius; Ariane wants explicit ids
    if ($r.model -lt 0) { Write-Warning "skipped model -1 at $($r.x),$($r.y)"; continue }
    pwsh $ctl suppress-world-models $r.x $r.y $r.radius $r.model | Out-Null
    if ($LASTEXITCODE -ne 0) { $failed++ }
}
"$($removals.Count) removals, $failed failed"
