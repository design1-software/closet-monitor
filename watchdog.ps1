# Closet Monitor watchdog — self-heals the stack.
#
# Re-launches all services if the dashboard (:8501) is down OR the subscriber
# has not written a reading in the last 10 minutes. The boot-time task
# (ClosetMonitorServices) only handles reboots; this catches process crashes
# between reboots. Runs every 5 min via the ClosetMonitorWatchdog scheduled
# task — see register-watchdog.ps1. Logs only when it takes action.
$repo   = $PSScriptRoot
$logDir = Join-Path $repo "data\logs"
$wlog   = Join-Path $logDir "watchdog.log"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
function Log($m) { Add-Content -Path $wlog -Value ("{0} - {1}" -f (Get-Date -Format o), $m) }

# health 1: dashboard listening on :8501
$dashUp = @(Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue).Count -gt 0

# health 2: subscriber wrote a reading within the last 10 minutes
$subLog   = Join-Path $logDir "subscriber-error.log"
$subFresh = $false
if (Test-Path $subLog) {
    $ageMin   = ((Get-Date) - (Get-Item $subLog).LastWriteTime).TotalMinutes
    $subFresh = $ageMin -lt 10
}

if (-not $dashUp -or -not $subFresh) {
    Log ("unhealthy (dashUp={0} subFresh={1}) - restarting" -f $dashUp, $subFresh)
    # clean up stale closet-monitor python processes to avoid duplicates / port conflicts
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*closet-monitor*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
    & (Join-Path $repo "start-services.ps1")
    Log "restart issued"
}
