#!/bin/bash
# Собирает NaikeeSaveManager.dmg - образ для раздачи: окно с иконкой
# приложения и ярлыком «Программы», перетащил и готово.
#
#     ./swift/build-dmg.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/NaikeeSaveManager.app"
NAME="Naikee's Save Manager"
DMG="$ROOT/NaikeeSaveManager.dmg"
STAGE="$(mktemp -d)"

[ -d "$APP" ] || "$ROOT/build-app.sh"

echo "готовлю содержимое…"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Программы"

rm -f "$DMG"
hdiutil create -quiet -volname "$NAME" -srcfolder "$STAGE" \
    -format UDZO -imagekey zlib-level=9 "$DMG"
rm -rf "$STAGE"

echo "готово: $DMG"
du -sh "$DMG" | cut -f1 | sed 's/^/размер: /'
