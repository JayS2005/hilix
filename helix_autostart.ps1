$ErrorActionPreference = 'Continue'
$logDir = 'C:\jarvis-client\logs'
$stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'

# 1. Start the backend inside WSL, detached, logging to its own file.
Start-Process -WindowStyle Hidden -FilePath 'wsl.exe' 
    -ArgumentList '-d', 'kali-linux', '--', 'bash', '-lc', 
    "cd ~/jarvis-api && source .venv/bin/activate && ./scripts/run_api.sh >> ~/jarvis-api/autostart.log 2>&1" 
    -RedirectStandardOutput (Join-Path $logDir "wsl_$stamp.log") 
    -RedirectStandardError  (Join-Path $logDir "wsl_$stamp.err.log")

# 2. Give the API a few seconds to come up before the client tries to use it.
Start-Sleep -Seconds 8

# 3. Launch the voice client (this itself starts the dashboard + stats server).
Set-Location 'C:\jarvis-client'
& 'C:\jarvis-client\.venv\Scripts\python.exe' 'C:\jarvis-client\voice_assistant.py' *>> (Join-Path $logDir "client_$stamp.log")
