#!/usr/bin/env bash
# GamingShorts native-source image quality experiment. CPU only.
# No source changes, no project changes, no publishing.
set -euo pipefail

SOURCE="${1:-/mnt/d/GamingShorts/Sources/videoplayback (2).mp4}"
OUT="${2:-/mnt/d/GamingShorts/QualityAB_2026_11}"

for app in ffmpeg ffprobe; do
  if ! command -v "$app" >/dev/null 2>&1; then
    echo "ERROR: Missing $app; install FFmpeg first." >&2
    exit 2
  fi
done
if [ ! -f "$SOURCE" ]; then
  echo "ERROR: Original recording not found: $SOURCE" >&2
  exit 2
fi
mkdir -p "$OUT"

read -r SW SH SOURCE_FPS < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$SOURCE" | tr ',' ' ')
echo "Original recording: ${SW}x${SH}, rate ${SOURCE_FPS}"
if [ "$SW" -lt 2560 ] || [ "$SH" -lt 1440 ]; then
  echo "ERROR: This isn't the expected 2560x1440-or-better source. Aborting so we do not test with a compressed Short." >&2
  exit 2
fi

echo "A/B quality test: identical source frames, 60 FPS, CPU libx264, CRF 16, slow preset."
echo "Save location: $OUT"
echo "Nothing will be uploaded, posted, or modified outside $OUT."

make_clip() {
  local label="$1"; local start="$2"; local width="$3"; local height="$4"
  local file="$OUT/${label}_${width}x${height}_60fps_crf16_slow.mp4"
  echo "Rendering $(basename "$file")"
  ffmpeg -hide_banner -loglevel warning -stats -nostdin -y \
    -ss "$start" -i "$SOURCE" -t 6 \
    -map 0:v:0 -map 0:a:0? \
    -vf "scale=${width}:${height}:force_original_aspect_ratio=increase:flags=lanczos,crop=${width}:${height},setsar=1,fps=60,format=yuv420p" \
    -c:v libx264 -preset slow -crf 16 -threads 4 \
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
    -c:a aac -b:a 192k -ar 48000 \
    -movflags +faststart \
    "$file"
  ffprobe -v error -show_entries stream=width,height,avg_frame_rate:format=duration,size,bit_rate -of default=noprint_wrappers=1 "$file" > "${file%.mp4}.info.txt"
}

# These are non-ending footage samples from the exact source used for our projects.
# Shelter: 35m47s, deliberately outside the known black-frame segments.
# Snowstorm: 66m18s, detailed snowy climbing footage.
for sample in shelter:2147.0 snowstorm:3978.0; do
  label="${sample%%:*}"; start="${sample##*:}"
  make_clip "$label" "$start" 1080 1920
  make_clip "$label" "$start" 1440 2560
done

printf '\nDONE. Compare pairs at the same on-screen size, then upload the files for review:\n'
printf '  %s\n' "$OUT"/*.mp4
printf '\nNote: 1440x2560 is upscaled from the native 9:16 crop; this test checks export/YouTube compression, not recovered source detail.\n'
