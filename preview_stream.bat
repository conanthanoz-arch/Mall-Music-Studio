@echo off
cd /d "%~dp0"
echo Local preview — 30 seconds of composited mall patrol (no YouTube)
echo Close the ffplay window or press Q to stop.
echo.
if not exist .venv\Scripts\python.exe (
    echo Run: py -m venv .venv ^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)
.venv\Scripts\python.exe stream_engine.py 2>nul | ffplay -f image2pipe -framerate 30 -i pipe:0 -t 30 -window_title "Mall Patrol Preview"
