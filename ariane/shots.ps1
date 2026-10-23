# Flies the running Ariane through every named shot at noon and midnight and captures each into screenshots/<set>/.
# The viewport really moves, so whoever is watching the editor sees each shot being taken.
#   pwsh ariane/shots.ps1 before [name-filter]
#   pwsh ariane/shots.ps1 after [name-filter]
param([Parameter(Mandatory)][ValidateSet('before', 'after')][string]$Set, [string]$Filter = '*')

# name = camera position, look-at target, fov
$shots = [ordered]@{
    'ls-ganton-lshouse1-exterior' = @(2712, -1972, 22, 2695.1, -1983.8, 16, 60)
    'ls-ganton-lshouse1-interior' = @(2698.5, -1981.5, 16.4, 2691, -1986, 15.8, 70)
    'sf-sfhouse2-exterior'        = @(-2770, 140, 22, -2786.7, 124.1, 13, 60)
    'sf-sfhouse2-interior'        = @(-2783.5, 121.5, 12.6, -2790, 127, 12.2, 70)
    'lv-lvhouse1-exterior'        = @(1825, 707, 22, 1842.4, 690.3, 14, 60)
    'lv-lvhouse1-interior'        = @(1846, 686.5, 13.7, 1838, 693, 13.2, 70)
}
$ctl = Join-Path $PSScriptRoot 'ctl.ps1'
$out = Join-Path $PSScriptRoot "..\screenshots\$Set"
New-Item -ItemType Directory -Force $out | Out-Null
foreach ($name in $shots.Keys | Where-Object { $_ -like $Filter }) {
    $c = $shots[$name]
    pwsh $ctl camera @c | Out-Null
    foreach ($time in @(@{ hour = 12; label = 'noon' }, @{ hour = 0; label = 'midnight' })) {
        pwsh $ctl environment --hour $time.hour --minute 0 --weather-a 1 --weather-b 1 --blend 0 | Out-Null
        Start-Sleep -Milliseconds 800
        $file = Join-Path $out "$name-$($time.label).png"
        pwsh $ctl capture (Resolve-Path -LiteralPath $out | Join-Path -ChildPath "$name-$($time.label).png") | Out-Null
        "captured $file"
    }
}
pwsh $ctl environment --hour 12 --minute 0 --weather-a 1 --weather-b 1 --blend 0 | Out-Null
