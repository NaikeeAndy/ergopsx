#!/bin/bash
# Собирает ErgoPSXSaveManager.app - обычное приложение macOS, запускаемое
# двойным щелчком. SPM сам .app не делает, поэтому раскладываем руками.
#
#     ./swift/build-app.sh          сборка в release
#     ./swift/build-app.sh debug    быстрая сборка для проверки
set -euo pipefail

MODE="${1:-release}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/.build/$MODE"
APP="$ROOT/ErgoPSXSaveManager.app"

echo "сборка ($MODE)…"
swift build --package-path "$ROOT" -c "$MODE" --product MemCardSaver

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Файл без пробелов и апострофа, а видимое имя - в Info.plist.
cp "$BUILD/MemCardSaver" "$APP/Contents/MacOS/ErgoPSXSaveManager"

# Ресурсный пакет с таблицами названий: без него Bundle.module пуст,
# и приложение молча покажет сейвы без имён игр.
cp -R "$BUILD/MemCardSaver_MemCardKit.bundle" "$APP/Contents/Resources/"

# Иконка рисуется кодом (icon/draw.swift), в репозиторий не кладётся -
# если её ещё нет, собираем на месте.
if [ ! -f "$ROOT/icon/MemCardSaver.icns" ]; then
  echo "рисую иконку…"
  "$ROOT/icon/build-icon.sh" >/dev/null
fi
cp "$ROOT/icon/MemCardSaver.icns" "$APP/Contents/Resources/ErgoPSXSaveManager.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>ErgoPSX Save Manager</string>
  <key>CFBundleDisplayName</key><string>ErgoPSX Save Manager</string>
  <key>CFBundleIdentifier</key><string>com.ergopsx.savemanager</string>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>CFBundleLocalizations</key>
  <array><string>en</string><string>ru</string><string>fr</string>
         <string>de</string><string>ja</string><string>zh-Hans</string>
         <string>pl</string></array>
  <key>CFBundleExecutable</key><string>ErgoPSXSaveManager</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>CFBundleIconFile</key><string>ErgoPSXSaveManager</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSDisabledDictationMenuItem</key><true/>
  <key>NSDisabledCharacterPaletteMenuItem</key><true/>
  <key>NSHumanReadableCopyright</key><string></string>
</dict>
</plist>
PLIST

printf 'APPL????' > "$APP/Contents/PkgInfo"

# Без папки локализации macOS считает приложение английским и рисует
# системные пункты меню - «Файл», «Окно», «Закрыть» - по-английски
# вперемешку с нашими русскими.
for lang in en ru fr de ja zh-Hans pl; do
  mkdir -p "$APP/Contents/Resources/$lang.lproj"
  cat > "$APP/Contents/Resources/$lang.lproj/InfoPlist.strings" <<'STRINGS'
"CFBundleName" = "ErgoPSX Save Manager";
"CFBundleDisplayName" = "ErgoPSX Save Manager";
STRINGS
done

# Подпись для себя: без неё macOS не пускает приложение к папкам
# пользователя и оно молча ничего не находит.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 \
  && echo "подписано локально" \
  || echo "подписать не вышло - приложение запустится, но может не увидеть папки"

echo "готово: $APP"
du -sh "$APP" | cut -f1 | sed 's/^/размер: /'
