"""Названия предметов Vagrant Story из образа диска.

В сейве у предметов только номера, а названия лежат в `MENU/ITEMNAME.BIN`
на диске: 512 записей по 24 байта в кодировке игры.

Брать их из декомпиляции нельзя: там имена записаны опознавателями в
стиле camelCase, и апострофы с пробелами в них потеряны - выходит
«Footman'sMace» вместо «Footman's Mace», а «handAxe» при попытке
разделить слова превращается в «H and Axe».

    python3 tools/psxvsitems.py <образ.bin> [выход.json]
"""

import json
import pathlib
import re
import struct
import sys

RAW, USER, HEAD = 2352, 2048, 24      # сырой сектор диска PS1
RECORD = 24                            # длина записи названия
COUNT = 512

TABLE_SOURCE = ("reference/formats/psxsaves-formats/_KEY-FILES/"
                "rood-reverse/tools/etc/vsString.py")

# Управляющие байты кодировки игры.
TERMINATOR = 0xE7
ALIGN = 0xEB
SPACING = 0xFA          # кернинг между словами - показываем пробелом
JAPANESE = range(0xED, 0xF8)
TWO_BYTE = {0xEC, 0xF8, 0xF9, 0xFB, 0xFD, 0xFE, 0xFF}


def load_table(root=pathlib.Path(".")):
    src = (root / TABLE_SOURCE).read_text()
    body = re.search(r"^table = \[(.*?)^\]", src, re.S | re.M).group(1)
    return eval("[" + body + "]")


def decode(raw, table):
    out, i = "", 0
    while i < len(raw):
        code = raw[i]
        if code == TERMINATOR:
            break
        if code == ALIGN:
            i += 1
            continue
        if code == SPACING:
            # Игра ставит его между словами вместо пробела.
            out += " "
            i += 2
            continue
        if code in JAPANESE or code in TWO_BYTE:
            i += 2
            continue
        out += table[code] or ""
        i += 1
    return " ".join(out.split())


def sector(handle, lba):
    handle.seek(lba * RAW)
    return handle.read(RAW)[HEAD:HEAD + USER]


def entries(handle, lba, length):
    data = b"".join(sector(handle, lba + i)
                    for i in range((length + USER - 1) // USER))
    out, at = [], 0
    while at < len(data):
        size = data[at]
        if size == 0:
            at = (at // USER + 1) * USER
            if at >= len(data):
                break
            continue
        rec = data[at:at + size]
        out.append((rec[33:33 + rec[32]].split(b";")[0].decode("ascii", "replace"),
                    struct.unpack_from("<I", rec, 2)[0],
                    struct.unpack_from("<I", rec, 10)[0]))
        at += size
    return out


def find(handle, path):
    """Файл в образе по пути вида MENU/ITEMNAME.BIN."""
    pvd = sector(handle, 16)
    if pvd[1:6] != b"CD001":
        raise SystemExit("это не образ диска: нет метки CD001")
    lba = struct.unpack_from("<I", pvd, 158)[0]
    length = struct.unpack_from("<I", pvd, 166)[0]
    for part in path.split("/"):
        for name, start, size in entries(handle, lba, length):
            if name.upper().startswith(part.upper()):
                lba, length = start, size
                break
        else:
            raise SystemExit(f"в образе нет {part}")
    return lba, length


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    image = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2
                       else "tools/data/vagrant-map.json")

    table = load_table()
    with image.open("rb") as handle:
        lba, size = find(handle, "MENU/ITEMNAME.BIN")
        data = b"".join(sector(handle, lba + i)
                        for i in range((size + USER - 1) // USER))[:size]

    names = [decode(data[i * RECORD:(i + 1) * RECORD], table)
             for i in range(COUNT)]
    named = sum(1 for n in names if n)

    saved = json.loads(out.read_text()) if out.exists() else {}
    saved["items"] = names
    out.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
    print(f"названий: {named} из {COUNT}")
    print(f"примеры: {', '.join(n for n in names[1:6])}")
    print(f"записано: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
