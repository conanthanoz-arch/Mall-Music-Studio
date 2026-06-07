@echo off
setlocal enabledelayedexpansion

:: --- Configuration ---
set STREAM_KEY=YOUR_YOUTUBE_STREAM_KEY
set AUDIO_FILE=lofi_music.mp3
set DISCORD_URL=
set LOG_FILE=stream_monitor.log

title YoutubeLoopStream - 24/7 Auto-Recovery Monitor

echo === YoutubeLoopStream Monitor Started === >> %LOG_FILE%
echo [%date% %time%] Monitor started >> %LOG_FILE%

if not "%DISCORD_URL%"=="" (
    curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"Server Status Online: Initializing RAM pipeline stream.\"}" "%DISCORD_URL%"
)

:start
echo [%date% %time%] Launching FFmpeg pipeline... >> %LOG_FILE%
echo Launching FFmpeg pipeline...

python stream_engine.py 2>> %LOG_FILE% | ffmpeg -f image2pipe -framerate 30 -vcodec mjpeg -i pipe:0 -stream_loop -1 -i "%AUDIO_FILE%" -c:v libx264 -pix_fmt yuv420p -preset veryfast -b:v 3000k -g 60 -c:a aac -b:a 168k -ar 44100 -f flv "rtmp://a.rtmp.youtube.com/live2/%STREAM_KEY%" 2>> %LOG_FILE%

echo [%date% %time%] WARNING: FFmpeg crashed. Reconnecting in 5 seconds... >> %LOG_FILE%
echo WARNING: Stream dropped. Reconnecting in 5 seconds...

if not "%DISCORD_URL%"=="" (
    curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"Stream redirect warning: Memory pipe broken. Rebooting...\"}" "%DISCORD_URL%"
)

timeout /t 5 /nobreak >nul
goto start
