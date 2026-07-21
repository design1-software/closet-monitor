# Registers the ClosetMonitorWatchdog scheduled task: runs watchdog.ps1 every
# 5 minutes as SYSTEM (survives logoff, no stored password). Run once, from an
# elevated (Administrator) PowerShell, in the repo root.
$wd = Join-Path $PSScriptRoot "watchdog.ps1"
schtasks /Create /TN ClosetMonitorWatchdog `
    /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$wd`"" `
    /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F

Write-Output "Registered ClosetMonitorWatchdog (every 5 min). Verify:  schtasks /Query /TN ClosetMonitorWatchdog"
