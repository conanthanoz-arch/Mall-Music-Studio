#!/bin/bash
set -euo pipefail

STREAM_KEY="YOUR_YOUTUBE_STREAM_KEY"
AUDIO_FILE="lofi_music.mp3"
DISCORD_URL=""
LOG_FILE="stream_monitor.log"

send_alert() {
    if [[ -n "$DISCORD_URL" ]]; then
        curl -H "Content-Type: application/json" -X POST \
            -d "{\"content\": \"$1\"}" "$DISCORD_URL" 2>/dev/null || true
    fi
}

echo "=== YoutubeLoopStream Monitor Started ===" | tee -a "$LOG_FILE"
send_alert "Server Status Online: Initializing RAM pipeline stream."

while true; do
    echo "[$(date)] Launching FFmpeg pipeline..." | tee -a "$LOG_FILE"

    python3 stream_engine.py 2>> "$LOG_FILE" | ffmpeg \
        -f image2pipe -framerate 30 -vcodec mjpeg -i pipe:0 \
        -stream_loop -1 -i "$AUDIO_FILE" \
        -c:v libx264 -pix_fmt yuv420p -preset veryfast -b:v 3000k -g 60 \
        -c:a aac -b:a 168k -ar 44100 \
        -f flv "rtmp://a.rtmp.youtube.com/live2/$STREAM_KEY" 2>> "$LOG_FILE" || true

    echo "[$(date)] WARNING: FFmpeg crashed. Reconnecting in 5 seconds..." | tee -a "$LOG_FILE"
    send_alert "Stream redirect warning: Memory pipe broken. Rebooting..."
    sleep 5
done
