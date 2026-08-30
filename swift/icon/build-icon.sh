#!/bin/bash
# Перерисовывает иконку приложения из swift/icon/draw.swift.
# Каждый размер рисуется заново, а не уменьшается с большого:
# тонкие линии значков при уменьшении расплываются.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SET="$ROOT/MemCardSaver.iconset"

rm -rf "$SET"; mkdir -p "$SET"
for pair in 16:icon_16x16 32:icon_16x16@2x 32:icon_32x32 64:icon_32x32@2x \
            128:icon_128x128 256:icon_128x128@2x 256:icon_256x256 \
            512:icon_256x256@2x 512:icon_512x512 1024:icon_512x512@2x; do
  size="${pair%%:*}"
  name="${pair#*:}"
  swift "$ROOT/draw.swift" "$SET/$name.png" "$size"
done

iconutil -c icns "$SET" -o "$ROOT/MemCardSaver.icns"
rm -rf "$SET"
echo "готово: $ROOT/MemCardSaver.icns"
