<#
Run ONCE on Windows, in an elevated PowerShell prompt:
    powershell -ExecutionPolicy Bypass -File setup_helix_autostart.ps1

Sets up Helix to start automatically at logon:
  1. Starts the FastAPI backend inside WSL (Kali), the same way you'd start
     it manually with run_api.sh.
  2. Waits a few seconds for it to come up.
  3. Launches voice_assistant.py, which -- per your existing dashboard-
     autostart patch -- already spawns stats_server.py and opens the
     dashboard in your browser on its own.

Everything runs in a minimized/hidden window so you don't get terminal
windows cluttering your desktop on every login. Logs go to
C:\jarvis-client\logs\ so you can check what happened if something didn't
start.

Idempotent: re-running replaces the existing task/wrapper rather than
duplicating them.
#>

$ErrorActionPreference = "Stop"

$ClientDir  = "C:\jarvis-client"
$LogDir     = Join-Path $ClientDir "logs"
$WrapperPs1 = Join-Path $ClientDir "helix_autostart.ps1"
$TaskName   = "HelixAutostart"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- Distro name -------------------------------------------------------
# Adjust this if your WSL distro isn't named "kali-linux" -- check with:
#   wsl -l -v
$WslDistro = "kali-linux"

# --- Wrapper script that the scheduled task actually runs ---------------
$wrapperContent = @"
`$ErrorActionPreference = 'Continue'
`$logDir = '$LogDir'
`$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'

# 1. Start the backend inside WSL, detached, logging to its own file.
Start-Process -WindowStyle Hidden -FilePath 'wsl.exe' `
    -ArgumentList '-d', '$WslDistro', '--', 'bash', '-lc', `
    "cd ~/jarvis-api && source .venv/bin/activate && ./scripts/run_api.sh >> ~/jarvis-api/autostart.log 2>&1" `
    -RedirectStandardOutput (Join-Path `$logDir "wsl_`$stamp.log") `
    -RedirectStandardError  (Join-Path `$logDir "wsl_`$stamp.err.log")

# 2. Give the API a few seconds to come up before the client tries to use it.
Start-Sleep -Seconds 8

# 3. Launch the voice client (this itself starts the dashboard + stats server).
Set-Location '$ClientDir'
& '$ClientDir\.venv\Scripts\python.exe' '$ClientDir\voice_assistant.py' *>> (Join-Path `$logDir "client_`$stamp.log")
"@

Set-Content -Path $WrapperPs1 -Value $wrapperContent -Encoding UTF8

# --- Register the scheduled task -----------------------------------------
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action    = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WrapperPs1`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Done. Helix will now start automatically at logon."
Write-Host "Logs land in: $LogDir"
Write-Host ""
Write-Host "To test right now without logging out:"
Write-Host "    Start-ScheduledTask -TaskName $TaskName"
Write-Host ""
Write-Host "To remove autostart later:"
Write-Host "    Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
