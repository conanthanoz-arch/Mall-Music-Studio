@echo off
cd /d "%~dp0"
echo Mall Music Studio — publish to GitHub
echo.

set GH=%~dp0.gh-cli\bin\gh.exe
if not exist "%GH%" (
    echo Downloading GitHub CLI...
    mkdir .gh-cli 2>nul
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/cli/cli/releases/download/v2.93.0/gh_2.93.0_windows_amd64.zip' -OutFile '.gh-cli\gh.zip'; Expand-Archive -Path '.gh-cli\gh.zip' -DestinationPath '.gh-cli' -Force"
    set GH=%~dp0.gh-cli\bin\gh.exe
)

"%GH%" auth status >nul 2>&1
if errorlevel 1 (
    echo Log in to GitHub first:
    "%GH%" auth login
)

echo Creating public repo Mall-Music-Studio and pushing...
"%GH%" repo create Mall-Music-Studio --public --description "Procedural lo-fi music studio with Qt Arrangement timeline and YouTube synth import" --source=. --remote=origin --push
if errorlevel 1 (
    echo.
    echo If the repo already exists, run:
    echo   git remote add origin https://github.com/YOUR_USERNAME/Mall-Music-Studio.git
    echo   git push -u origin master
    exit /b 1
)

echo.
echo Done. Repo: https://github.com/conanthanoz-arch/Mall-Music-Studio
pause
