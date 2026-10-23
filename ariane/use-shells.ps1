# Switches the Ariane game copy between SA-MP's original shells and this repo's reworked ones, then restarts the editor.
#   pwsh ariane/use-shells.ps1 baked      # rebuilds SHELLS\SHELLS.IMG from models/baked and loads it after SAMP.IMG
#   pwsh ariane/use-shells.ps1 original   # comments the IMG line out again
param([Parameter(Mandatory)][ValidateSet('baked', 'original')][string]$Which, [string]$GameDir = 'D:\Games\GTA San Andreas\ariane-sa')

$repo = Split-Path $PSScriptRoot
$dat = Join-Path $GameDir 'data\gta.dat'
$line = 'IMG SHELLS\SHELLS.IMG'
if ($Which -eq 'baked') {
    New-Item -ItemType Directory -Force (Join-Path $GameDir 'SHELLS') | Out-Null
    $models = Get-ChildItem (Join-Path $repo 'models\baked') -Filter *.dff | ForEach-Object FullName
    python -I (Join-Path $repo 'tools\img.py') build (Join-Path $GameDir 'SHELLS\SHELLS.IMG') @models
}
# later IMG lines override earlier entries of the same name, so the line sits right after the SA-MP archives
$text = (Get-Content -Raw $dat) -replace "(?m)^#?$([regex]::Escape($line))\r?\n", ''
$entry = if ($Which -eq 'baked') { $line } else { "#$line" }
$text = $text -replace '(?m)^(IMG SAMP\\CUSTOM\.IMG\r?\n)', "`$1$entry`r`n"
Set-Content -LiteralPath $dat -Value $text -NoNewline

Stop-Process -Name ariane -ErrorAction SilentlyContinue
Start-Sleep 2
pwsh (Join-Path $PSScriptRoot 'start.ps1') -GameDir $GameDir
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 2
    pwsh (Join-Path $PSScriptRoot 'ctl.ps1') ping 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
}
pwsh (Join-Path $PSScriptRoot 'apply-removals.ps1') -GameDir $GameDir
"Ariane is showing the $Which shells"
