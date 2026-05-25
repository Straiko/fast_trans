$ErrorActionPreference = "Stop"

Write-Host "Olympus (Windows build) - PyInstaller" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python not found. Install Python 3.10+ and retry."
}

python --version

# Create venv if missing
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip wheel setuptools
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install pyinstaller

# Clean old output
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

& .\.venv\Scripts\pyinstaller.exe `
  --onefile `
  --noconsole `
  --name "Olympus" `
  --icon ".\icon.ico" `
  --add-data ".\icon.png;." `
  --hidden-import="pynput.keyboard._win32" `
  --hidden-import="pynput.mouse._win32" `
  --hidden-import="pyperclip" `
  ".\main.py"

Write-Host ""
Write-Host "Done. Output is in .\dist\Olympus.exe (single-file build)" -ForegroundColor Green

