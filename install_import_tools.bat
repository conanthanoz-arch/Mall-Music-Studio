@echo off
cd /d "%~dp0"
echo Installing YouTube import tools (yt-dlp + demucs + PyTorch)...
echo This may take several minutes and several GB of disk space.
echo.
if not exist .venv\Scripts\python.exe (
    echo Creating venv...
    py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install yt-dlp demucs scipy soundfile
echo.
python -c "import yt_dlp; import demucs; print('Import tools OK')"
echo.
echo Done. Restart Mall Music Studio and click Refresh status in Import from YouTube.
pause
