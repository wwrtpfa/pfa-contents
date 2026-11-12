#!/usr/bin/env bash
# Media QA for a finished short video.
# Usage:
#   scripts/qa_video.sh out/video.mp4 [frame ...]
# Environment:
#   QA_DIR=/path/to/qa   (default: <video dir>/qa)
set -euo pipefail

MP4="${1:?usage: qa_video.sh <video.mp4> [frame ...]}"
shift || true
[ -f "$MP4" ] || { echo "no such file: $MP4" >&2; exit 1; }

QA_DIR="${QA_DIR:-$(cd "$(dirname "$MP4")" && pwd)/qa}"
mkdir -p "$QA_DIR"

echo "== specs =="
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -show_entries stream=index,codec_name,width,height,r_frame_rate,sample_rate,channels \
  -of default=nw=1 "$MP4"

echo "== decode =="
ffmpeg -v error -i "$MP4" -f null - && echo "decode ok"

echo "== loudness =="
ffmpeg -hide_banner -nostats -i "$MP4" -map 0:a -af volumedetect -f null - 2>&1 \
  | grep -E "mean_volume|max_volume" || echo "no audio stream"

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MP4")

echo "== key frames =="
for n in "$@"; do
  ffmpeg -v error -y -i "$MP4" -vf "select=eq(n\,$n)" -frames:v 1 "$QA_DIR/frame-$n.png"
  echo "  frame $n"
done

echo "== contact sheet =="
ffmpeg -v error -y -i "$MP4" \
  -vf "fps=1/8.5,scale=324:-1,tile=5x2:padding=6:margin=6:color=#0A1213" \
  -frames:v 1 "$QA_DIR/contact-sheet.jpg"

echo "== playback frames =="
ffmpeg -v error -y -ss 00:00:02 -i "$MP4" -frames:v 1 "$QA_DIR/start.jpg"
ffmpeg -v error -y -ss "$(awk -v d="$DUR" 'BEGIN{printf "%.2f", d/2}')" -i "$MP4" -frames:v 1 "$QA_DIR/mid.jpg"
ffmpeg -v error -y -ss "$(awk -v d="$DUR" 'BEGIN{printf "%.2f", d-2}')" -i "$MP4" -frames:v 1 "$QA_DIR/end.jpg"

shasum -a 256 "$MP4"
echo "qa written to $QA_DIR"
