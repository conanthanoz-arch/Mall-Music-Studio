@echo off
cd /d "%~dp0"
echo Mall Music Studio — install
echo.

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    py -m venv .venv
    if errorlevel 1 (
        echo Failed. Install Python 3.9+ from python.org
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Install complete.
echo   Run:  run_music_studio.bat
echo   Build EXE:  build_and_run.bat
echo   YouTube import (optional):  install_import_tools.bat
echo   CC0 sample packs (optional):  install_samples.bat
pause
