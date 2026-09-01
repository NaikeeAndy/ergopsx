#!/bin/sh
# Builds a .deb out of the PyInstaller output, so that on Debian and Ubuntu
# the app installs like any other: it lands in the applications menu, gets
# an icon, and apt pulls in the system libraries Qt needs instead of
# leaving the user to guess why nothing starts.
#
#     qt/packaging/build-deb.sh [version]
#
# Run it after qt/build.py, on Linux: dpkg-deb exists nowhere else.
set -e

VERSION="${1:-0.1}"
VERSION="${VERSION#v}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
DIST="$ROOT/qt/dist/ErgoPSXSaveManager"
STAGE="$ROOT/qt/dist/deb"
OUT="$ROOT/ergopsx_${VERSION}_amd64.deb"

[ -d "$DIST" ] || { echo "no $DIST - run qt/build.py first" >&2; exit 1; }

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/opt/ergopsx" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps"

cp -r "$DIST/." "$STAGE/opt/ergopsx/"
cp "$HERE/ergopsx.png" "$STAGE/usr/share/icons/hicolor/256x256/apps/ergopsx.png"

# Started from a terminal as well as from the menu.
ln -s /opt/ergopsx/ErgoPSXSaveManager "$STAGE/usr/bin/ergopsx"

cp "$HERE/ergopsx.desktop" "$STAGE/usr/share/applications/ergopsx.desktop"

# Qt travels inside the package, but it still needs these from the system.
# Declaring them is the point of shipping a .deb at all: apt installs them
# instead of the user meeting "could not load the Qt platform plugin".
cat > "$STAGE/DEBIAN/control" <<CONTROL
Package: ergopsx
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Depends: libgl1, libegl1, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0,
 libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0,
 libxcb-cursor0, fontconfig
Maintainer: Naikee <dktgsitu@gmail.com>
Homepage: https://github.com/NaikeeAndy/ergopsx
Description: PlayStation 1 save manager
 Reads and inspects PlayStation 1 saves: memory cards, single saves and
 every container format in common use. Builds cards, converts between
 formats and moves saves to a PS3 or a Nintendo Switch over FTP.
 .
 Nothing is ever overwritten: every operation writes a new file.
CONTROL

# The menu entry and the icon cache only refresh when asked.
cat > "$STAGE/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
POSTINST
chmod 755 "$STAGE/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$STAGE" "$OUT" > /dev/null
echo "done: $OUT"
dpkg-deb --info "$OUT" | sed -n '2,4p'
