#!/bin/bash
# Собирает NaikeeSaveManager.app - обычное приложение macOS, запускаемое
# двойным щелчком. SPM сам .app не делает, поэтому раскладываем руками.
#
#     ./swift/build-app.sh          сборка в release
#     ./swift/build-app.sh debug    быстрая сборка для проверки
set -euo pipefail

MODE="${1:-release}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/.build/$MODE"
APP="$ROOT/NaikeeSaveManager.app"

echo "сборка ($MODE)…"
swift build --package-path "$ROOT" -c "$MODE" --product MemCardSaver

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Файл без пробелов и апострофа, а видимое имя - в Info.plist.
cp "$BUILD/MemCardSaver" "$APP/Contents/MacOS/NaikeeSaveManager"

# Ресурсный пакет с таблицами названий: без него Bundle.module пуст,
# и приложение молча покажет сейвы без имён игр.
cp -R "$BUILD/MemCardSaver_MemCardKit.bundle" "$APP/Contents/Resources/"

# Иконка рисуется кодом (icon/draw.swift), в репозиторий не кладётся -
# если её ещё нет, собираем на месте.
if [ ! -f "$ROOT/icon/MemCardSaver.icns" ]; then
  echo "рисую иконку…"
  "$ROOT/icon/build-icon.sh" >/dev/null
fi
cp "$ROOT/icon/MemCardSaver.icns" "$APP/Contents/Resources/NaikeeSaveManager.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Naikee&apos;s Save Manager</string>
  <key>CFBundleDisplayName</key><string>Naikee&apos;s Save Manager</string>
  <key>CFBundleIdentifier</key><string>ru.memcardsaver.app</string>
  <key>CFBundleDevelopmentRegion</key><string>ru</string>
  <key>CFBundleLocalizations</key>
  <array><string>ru</string><string>en</string></array>
  <key>CFBundleExecutable</key><string>NaikeeSaveManager</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>CFBundleIconFile</key><string>NaikeeSaveManager</string>
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
for lang in ru en; do
  mkdir -p "$APP/Contents/Resources/$lang.lproj"
  cat > "$APP/Contents/Resources/$lang.lproj/InfoPlist.strings" <<'STRINGS'
"CFBundleName" = "Naikee's Save Manager";
"CFBundleDisplayName" = "Naikee's Save Manager";
STRINGS
done

# Подпись для себя: без неё macOS не пускает приложение к папкам
# пользователя и оно молча ничего не находит.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 \
  && echo "подписано локально" \
  || echo "подписать не вышло - приложение запустится, но может не увидеть папки"

echo "готово: $APP"
du -sh "$APP" | cut -f1 | sed 's/^/размер: /'
