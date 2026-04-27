@echo off
title Olympus SIMPLE - РАБОТАЕТ НА ВСЕХ ПК!
color 0A

echo ========================================
echo   OLYMPUS SIMPLE v7 - 1 КЛИК!
echo ========================================
echo.

REM Проверяем Python
python --version >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Python найден!
    goto :vccheck
) else (
    echo [!] Python не найден!
    echo.
    echo Скачайте Python:
    echo   https://www.python.org/downloads/
    echo.
    echo ВАЖНО: При установке поставьте галочку
    echo   "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:vccheck
echo [1/5] Проверяем Visual C++ Redistributable...
md "C:\Olympus\vcredist" 2>nul

if not exist "C:\Olympus\vcredist\vc2015_2019_x64.exe" (
    echo   Скачиваем VC++ 2015-2019 x64...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/16/release/vc_redist.x64.exe' -OutFile 'C:\Olympus\vcredist\vc2015_2019_x64.exe'"
)
if not exist "C:\Olympus\vcredist\vc2015_2019_x86.exe" (
    echo   Скачиваем VC++ 2015-2019 x86...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/16/release/vc_redist.x86.exe' -OutFile 'C:\Olympus\vcredist\vc2015_2019_x86.exe'"
)
if not exist "C:\Olympus\vcredist\vc2015_2022_x64.exe" (
    echo   Скачиваем VC++ 2015-2022 x64...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile 'C:\Olympus\vcredist\vc2015_2022_x64.exe'"
)
if not exist "C:\Olympus\vcredist\vc2015_2022_x86.exe" (
    echo   Скачиваем VC++ 2015-2022 x86...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x86.exe' -OutFile 'C:\Olympus\vcredist\vc2015_2022_x86.exe'"
)

echo   Устанавливаем VC++ Redistributable...
echo   [x64] 2015-2019...
start /wait "" "C:\Olympus\vcredist\vc2015_2019_x64.exe" /install /quiet /norestart
echo   [x86] 2015-2019...
start /wait "" "C:\Olympus\vcredist\vc2015_2019_x86.exe" /install /quiet /norestart
echo   [x64] 2015-2022...
start /wait "" "C:\Olympus\vcredist\vc2015_2022_x64.exe" /install /quiet /norestart
echo   [x86] 2015-2022...
start /wait "" "C:\Olympus\vcredist\vc2015_2022_x86.exe" /install /quiet /norestart
echo [OK] VC++ Redistributable установлены!

:install
echo [2/5] Создаём папку...
md "C:\Olympus" 2>nul
cd /d C:\Olympus

echo [3/5] Скачиваем проект...
if not exist fast_trans (
    powershell -Command "git clone https://github.com/Straiko/fast_trans.git"
)
cd fast_trans

echo [4/5] Устанавливаем библиотеки...
python -m venv venv --clear 2>nul
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

echo [5/5] ЗАПУСК!
python main.py

echo.
echo Готово! Ищите в трее (рядом с часами).
echo.
echo Повторный запуск:
echo   C:\Olympus\fast_trans\venv\Scripts\activate ^&^& python main.py
pause
