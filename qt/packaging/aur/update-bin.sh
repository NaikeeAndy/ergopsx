#!/bin/sh
# Rewrites ergopsx-bin/PKGBUILD for a new release: the version and the three
# checksums. Hand-editing those on every release is exactly the kind of
# chore that gets done wrong once and then ships a package nobody can build.
#
#     qt/packaging/aur/update-bin.sh v0.2 path/to/ErgoPSX...-linux-x86_64.tar.gz
#
# The archive is the one that was just built, so the checksum describes the
# very file the release will carry.
set -e

TAG="${1:?usage: update-bin.sh <tag> <linux tarball>}"
TARBALL="${2:?usage: update-bin.sh <tag> <linux tarball>}"
VERSION="${TAG#v}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PKGBUILD="$HERE/ergopsx-bin/PKGBUILD"
SHARED="$(cd "$HERE/../.." && pwd)/packaging"

sum() { sha256sum "$1" | cut -d' ' -f1; }

ARCHIVE="$(sum "$TARBALL")"
DESKTOP="$(sum "$SHARED/ergopsx.desktop")"
ICON="$(sum "$SHARED/ergopsx.png")"

python3 - "$PKGBUILD" "$VERSION" "$ARCHIVE" "$DESKTOP" "$ICON" <<'PY'
import re, sys
path, version, archive, desktop, icon = sys.argv[1:6]
with open(path, encoding="utf-8") as fh:
    text = fh.read()

text = re.sub(r"^pkgver=.*$", f"pkgver={version}", text, count=1, flags=re.M)
text = re.sub(r"^pkgrel=.*$", "pkgrel=1", text, count=1, flags=re.M)
text = re.sub(
    r"sha256sums=\('[^']*'\n\s*'[^']*'\n\s*'[^']*'\)",
    f"sha256sums=('{archive}'\n            '{desktop}'\n            '{icon}')",
    text, count=1)
with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)
print(f"ergopsx-bin: version {version}")
PY

grep -E "^pkgver=|^ *'" "$PKGBUILD"
