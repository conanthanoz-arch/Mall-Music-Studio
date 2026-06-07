@echo off
cd /d "%~dp0"
echo Mall Music Studio — install CC0 sample packs
echo.

if not exist .venv\Scripts\python.exe (
    echo Run install.bat first to create the virtual environment.
    exit /b 1
)

call .venv\Scripts\activate.bat
python tools\fetch_sample_packs.py %*
if errorlevel 1 exit /b 1

echo.
echo Sample packs installed under licensed_library\
echo Optional: set FREESOUND_API_KEY in .env for full-quality Freesound downloads.
pause
