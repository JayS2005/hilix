<#
Run ONCE on Windows, in an elevated PowerShell prompt:
    powershell -ExecutionPolicy Bypass -File fix_python_store_sandbox.ps1

Root cause: voice_assistant.py is running under the Microsoft Store build of
Python (installed under
  C:\Users\<you>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_...)
Store-distributed Python runs inside a Windows AppContainer sandbox. That
sandbox is known to intermittently reset outbound HTTPS connections mid TLS
handshake -- exactly the WinError 10054 you're seeing talking to ElevenLabs.
It's not your API key, not your network, not ElevenLabs -- it's the sandbox.

Fix: install the official python.org build (unsandboxed), rebuild the venv
under it, and reinstall dependencies. This removes the root cause instead of
retrying around it.

This script:
  1. Installs official Python via winget (Python.Python.3.12 -- the
     python.org build, distinct from the Store package).
  2. Deletes the old venv (which is bound to the Store interpreter) and
     recreates it using the new official interpreter.
  3. Reinstalls everything from requirements.txt into the new venv.

Your code, .env, and all other files are untouched -- only the Python
interpreter and venv are replaced.
#>

$ErrorActionPreference = "Stop"
$ClientDir = "C:\jarvis-client"

Write-Host "Step 1/3: Installing official Python (python.org build) via winget..."
winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements

Write-Host ""
Write-Host "Step 2/3: Rebuilding the virtual environment under the new interpreter..."
Set-Location $ClientDir

if (Test-Path ".venv") {
    Write-Host "Removing old venv (was bound to the Store Python sandbox)..."
    Remove-Item -Recurse -Force ".venv"
}

# Refresh PATH in this session so the newly installed python.org build is
# found instead of any cached Store shim.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Locate the official python.org install explicitly (avoids accidentally
# picking the Store alias if both are still on PATH).
$pyOfficial = Get-ChildItem "C:\Program Files\Python312\python.exe","C:\Program Files (x86)\Python312\python.exe","$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $pyOfficial) {
    Write-Host "Could not auto-locate the new python.org install."
    Write-Host "Open a NEW PowerShell window (so PATH refreshes) and run:"
    Write-Host "    where.exe python"
    Write-Host "Confirm it points to Program Files\Python312, NOT AppData\Local\Packages,"
    Write-Host "then re-run this script."
    exit 1
}

Write-Host "Using interpreter: $($pyOfficial.FullName)"
& $pyOfficial.FullName -m venv .venv

Write-Host ""
Write-Host "Step 3/3: Reinstalling dependencies into the new venv..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Done. Verifying the new venv is NOT the Store build:"
& ".\.venv\Scripts\python.exe" -c "import sys; print(sys.executable)"
Write-Host ""
Write-Host "The path above should be under .venv\Scripts, backed by Program Files\Python312"
Write-Host "-- not AppData\Local\Packages\PythonSoftwareFoundation...  If it looks right,"
Write-Host "start the assistant as usual:"
Write-Host "    .\.venv\Scripts\activate"
Write-Host "    python .\voice_assistant.py"
