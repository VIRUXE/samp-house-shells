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
$editor = Start-Process (Join-Path $GameDir 'ariane.exe') -WorkingDirectory $GameDir -PassThru
# bring the new window to the front so whoever is watching sees it, not the one that just closed
Add-Type -Namespace Win32 -Name Window -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h); [DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int c);'
for ($i = 0; $i -lt 40 -and $editor.MainWindowHandle -eq 0; $i++) { Start-Sleep -Milliseconds 250; $editor.Refresh() }
[Win32.Window]::ShowWindow($editor.MainWindowHandle, 5) | Out-Null
[Win32.Window]::SetForegroundWindow($editor.MainWindowHandle) | Out-Null
