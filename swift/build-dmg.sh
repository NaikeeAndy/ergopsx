#!/bin/bash
# Собирает ErgoPSXSaveManager.dmg - образ для раздачи: окно с иконкой
# приложения и ярлыком на «Программы», перетащил и готово.
#
#     ./swift/build-dmg.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/ErgoPSXSaveManager.app"
NAME="ErgoPSX Save Manager"
DMG="$ROOT/ErgoPSXSaveManager.dmg"
STAGE="$(mktemp -d)"

[ -d "$APP" ] || "$ROOT/build-app.sh"

echo "готовлю содержимое…"
cp -R "$APP" "$STAGE/"
# Ярлык зовём «Applications»: Finder сам показывает это имя на языке
# системы. С русским именем он всегда пишет «Программы», даже у того,
# у кого macOS английская.
ln -s /Applications "$STAGE/Applications"

rm -f "$DMG"
hdiutil create -quiet -volname "$NAME" -srcfolder "$STAGE" \
    -format UDZO -imagekey zlib-level=9 "$DMG"
rm -rf "$STAGE"

echo "готово: $DMG"
du -sh "$DMG" | cut -f1 | sed 's/^/размер: /'
