@echo off
REM Concatenate music_library WAVs into lofi_music.mp3 via FFmpeg
cd /d "%~dp0"
set LIST=music_library\_concat_list.txt
if not exist music_library (
    echo music_library folder missing
    exit /b 1
)
del "%LIST%" 2>nul
for %%f in (music_library\*.wav) do echo file '%%f'>> "%LIST%"
find /c /v "" "%LIST%" | find "0" >nul && (
    echo No WAV files in music_library. Save tracks from Music Studio first.
    exit /b 1
)
ffmpeg -y -f concat -safe 0 -i "%LIST%" -ar 44100 -b:a 192k lofi_music.mp3
echo Wrote lofi_music.mp3
echo Run: python generate_playlist_metrics.py
pause
