@echo off
cd /d "%~dp0"
echo YouTube Sound Emulator — stem separation worker
echo Requires: pip install yt-dlp demucs soundfile
echo.
if not exist .venv\Scripts\python.exe (
    echo Create venv first: py -m venv .venv
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run_import_worker.bat "https://youtube.com/watch?v=..."
    exit /b 1
)
call .venv\Scripts\activate.bat
set LIB=%~dp0music_library
.venv\Scripts\python.exe tools\import_worker.py "%~1" --library-dir "%LIB%" %2 %3 %4 %5
pause
