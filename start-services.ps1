$repoPath = "C:\Users\jbm06\closet-monitor"
$python   = "$repoPath\subscriber\venv\Scripts\python.exe"
$logDir   = "$repoPath\data\logs"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

Start-Process -FilePath $python `
    -ArgumentList "$repoPath\subscriber\subscriber.py" `
    -WorkingDirectory "$repoPath\subscriber" `
    -RedirectStandardOutput "$logDir\subscriber.log" `
    -RedirectStandardError  "$logDir\subscriber-error.log" `
    -WindowStyle Hidden

Start-Process -FilePath $python `
    -ArgumentList "$repoPath\subscriber\alert_listener.py" `
    -WorkingDirectory "$repoPath\subscriber" `
    -RedirectStandardOutput "$logDir\alert-listener.log" `
    -RedirectStandardError  "$logDir\alert-listener-error.log" `
    -WindowStyle Hidden

Start-Process -FilePath $python `
    -ArgumentList "-m", "streamlit", "run", "$repoPath\dashboard\dashboard.py", "--server.port=8501", "--server.headless=true" `
    -WorkingDirectory "$repoPath\dashboard" `
    -RedirectStandardOutput "$logDir\dashboard.log" `
    -RedirectStandardError  "$logDir\dashboard-error.log" `
    -WindowStyle Hidden

Write-Output "Closet Monitor services started."
