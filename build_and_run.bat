@echo off
cd /d "%~dp0"
call "%~dp0build_music_studio.bat"
if errorlevel 1 exit /b 1
start "" "%~dp0dist\MallMusicStudio.exe"
exit /b 0
