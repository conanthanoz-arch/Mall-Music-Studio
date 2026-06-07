@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Create venv first: py -m venv .venv
    exit /b 1
)

echo Closing Mall Music Studio if running...
taskkill /IM MallMusicStudio.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

call .venv\Scripts\activate.bat
pip install -q pyinstaller numpy pygame PySide6

echo Building dist\MallMusicStudio.exe ...
pyinstaller --noconfirm --clean build_music_studio.spec
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

if exist instrument_presets (
    echo Syncing instrument_presets to dist\ ...
    xcopy /E /I /Y /Q instrument_presets dist\instrument_presets >nul
)
if exist licensed_library (
    echo Syncing licensed_library manifest to dist\ ...
    if not exist dist\licensed_library mkdir dist\licensed_library
    if exist licensed_library\manifest.json copy /Y licensed_library\manifest.json dist\licensed_library\ >nul
    if exist licensed_library\LICENSES xcopy /E /I /Y /Q licensed_library\LICENSES dist\licensed_library\LICENSES >nul
)

echo Build OK: dist\MallMusicStudio.exe
endlocal
