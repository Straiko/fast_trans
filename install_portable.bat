@echo off
chcp 65001 >nul
title Olympus PORTABLE - NO ADMIN!
color 0A

echo ========================================
echo   OLYMPUS PORTABLE - NO ADMIN!
echo ========================================
echo.

set "OL=C:\Olympus"
md "%OL%" 2>nul

REM === 1. Portable Python (DLLs built-in, no admin) ===
if not exist "%OL%\python\python.exe" (
    echo [1/5] Downloading portable Python 3.12...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip' -OutFile '%OL%\py.zip'"
    powershell -Command "Expand-Archive -Path '%OL%\py.zip' -DestinationPath '%OL%\python' -Force"
    del "%OL%\py.zip"

    REM Enable import site in _pth (needed for pip)
    powershell -Command "$p = (Get-ChildItem '%OL%\python\*._pth')[0].FullName; $c = Get-Content $p; $c = $c -replace '#import site', 'import site'; Set-Content $p $c"
) else (
    echo [1/5] Python already installed!
)

REM === 2. pip ===
if not exist "%OL%\python\Scripts\pip.exe" (
    echo [2/5] Installing pip...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%OL%\get-pip.py'"
    "%OL%\python\python.exe" "%OL%\get-pip.py" --quiet
    del "%OL%\get-pip.py"
) else (
    echo [2/5] pip already installed!
)

REM === 3. Project ===
echo [3/5] Downloading project...
if not exist "%OL%\fast_trans\main.py" (
    git --version >nul 2>&1
    if %errorlevel%==0 (
        git clone https://github.com/Straiko/fast_trans.git "%OL%\fast_trans"
    ) else (
        echo    git not found, downloading zip...
        powershell -Command "Invoke-WebRequest -Uri 'https://github.com/Straiko/fast_trans/archive/refs/heads/master.zip' -OutFile '%OL%\ft.zip'"
        powershell -Command "Expand-Archive -Path '%OL%\ft.zip' -DestinationPath '%OL%' -Force"
        ren "%OL%\fast_trans-master" "fast_trans"
        del "%OL%\ft.zip"
    )
) else (
    echo    Project already downloaded!
)

REM === 4. Add project dir to _pth (embedded Python needs this) ===
powershell -Command "$p = (Get-ChildItem '%OL%\python\*._pth')[0].FullName; $lines = Get-Content $p; if ($lines -notcontains '%OL%\fast_trans') { Add-Content $p '%OL%\fast_trans' }"

REM === 5. Dependencies ===
echo [4/5] Installing libraries...
"%OL%\python\python.exe" -m pip install --upgrade pip --quiet --no-warn-script-location
"%OL%\python\python.exe" -m pip install -r "%OL%\fast_trans\requirements.txt" --quiet --no-warn-script-location

REM === 6. Launch ===
echo [5/5] LAUNCHING!
cd /d "%OL%\fast_trans"
set PYTHONPATH=%OL%\fast_trans
"%OL%\python\python.exe" main.py

echo.
echo Done! Look in system tray (near the clock).
echo.
echo Re-launch:
echo   C:\Olympus\python\python.exe C:\Olympus\fast_trans\main.py
pause
