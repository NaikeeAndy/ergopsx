#!/usr/bin/env python3
"""Определение игры по PS1-сейву: PSV, MCS и образы карт."""

import argparse
import os
import re
import struct
import sys
import unicodedata

import psxff8
import psxsign
import psxpocket

FRAME = 128
BLOCK = 8192
# Подпись игры: Shift-JIS с 0x04 до начала палитры иконки. Это 92 байта,
# а не 64: у Crash Bash и CTR подпись ровно на пределе, и обрезание
# отъедало у них хвост.
SIGNATURE_END = 0x60
SLOTS = 15

REGIONS = {"BA": "America", "BE": "Europe", "BI": "Japan"}

SLOT_STATES = {
    0xA0: ("free", False),
    0x51: ("save", True),
    0x52: ("link", False),
    0x53: ("link", False),
    0xA1: ("deleted", True),
    0xA2: ("deleted-link", False),
    0xA3: ("deleted-link", False),
}

# Магия в начале файла -> смещение, с которого начинаются данные карты.
CONTAINERS = [
    (b"MC", 0, "raw"),
    (b"123-456-STD", 3904, "DexDrive .gme"),
    (b"VgsM", 64, "VGS"),
    (b"\x00PMV", 128, "PSP .vmp"),
    # Не путать с PS3 .psv: там магия "\0VSP", здесь "PSV\0" и модель карты
    # в заголовке (SCPH-1020), а данные начинаются с 256.
    (b"PSV\x00", 256, "Memory Juggler .psx"),
]

MCX_SIZE = 0x200A0

# Штатное имя сейва: регион (BA/BE/BI) + серийник диска. Встречаются и самодельные
# имена не по этой схеме (GT_COMPRESS01) - их резать на части нельзя.
# У приложений PocketStation на месте дефиса стоит 'P' - по этому байту
# MemcardRex и отличает их от обычных сейвов (loadSlotDataTypes).
SONY_NAME = re.compile(r"^B[AEI][A-Z]{4}[-P]\d{5}")

# Тот же шаблон, но найденный где угодно в имени файла: raw-сейвы заголовка не имеют,
# и единственный носитель имени - сам файл ("gran-turismo.26537-BASCUS-94194GT.srm").
EMBEDDED_NAME = re.compile(r"B[AEI][A-Z]{4}[-P]\d{5}[A-Za-z0-9_.\-]{0,8}")


# База названий переезжала вместе с репозиториями, поэтому ищем в нескольких местах.
TITLES_CANDIDATES = (
    "reference/psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt",
    "psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt",
    "all saves/psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt",
    # Выгрузка `psxexport.py`. Идёт последней: рядом с проектом лежит сама
    # база, а внутри собранного приложения - только эта.
    "tools/data/titles.json",
    "data/titles.json",
)


def icon_frames(block):
    """Сколько кадров у иконки: младшая цифра байта 0x02 (0x11..0x13)."""
    count = block[0x02] & 0x0F
    return count if 1 <= count <= 3 else 1


def data_offset(block):
    """С какого байта блока начинаются данные игры.

    Заголовок 0x80, дальше кадры иконки по 0x80. У сейва с одним кадром данные
    идут с 0x100, с тремя - с 0x200. Игры пишут разное число кадров даже внутри
    одной игры: у Castlevania в коллекции есть и однокадровые, и трёхкадровые.
    """
    return 0x80 + 0x80 * icon_frames(block)


def template_base(block):
    """Поправка к смещениям чужих шаблонов.

    Шаблоны писались по сейвам с однокадровой иконкой, где данные начинаются
    с 0x100. Для сейва с тремя кадрами всё съезжает на 0x100 вперёд.
    """
    return data_offset(block) - 0x100


# У сейвов, связанных с PocketStation, на месте дефиса в серийнике стоит P:
# "SLUSP00892" вместо "SLUS-00892". Такой серийник не находится ни в базе
# названий, ни в шаблонах - 35 сейвов Final Fantasy VIII висели без игры.
POCKET_SERIAL = re.compile(r"^([A-Z]{4})P(\d{5})$")


def normalize_serial(serial):
    found = POCKET_SERIAL.match(serial)
    return f"{found.group(1)}-{found.group(2)}" if found else serial


def serial_of(frame):
    """Серийник игры из каталожного фрейма, приведённый к виду базы."""
    name = bytes(frame[10:30]).split(b"\x00")[0].decode("ascii", errors="replace")
    return normalize_serial(name[2:12])


def default_titles_path():
    """Где лежит база названий.

    Смотрим и от корня проекта, и от самого движка: упаковщик складывает
    модули плоско, и `tools/` там оказывается на уровень ниже, чем рядом
    с проектом. Без этого собранное приложение показывает сейвы без
    названий игр, а список слева заполняется подписями.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for root in (os.path.dirname(here), here):
        for candidate in TITLES_CANDIDATES:
            path = os.path.join(root, candidate)
            if os.path.exists(path):
                return path
    return os.path.join(os.path.dirname(here), TITLES_CANDIDATES[0])


# Номер диска в названии относится к диску, под которым выпущен серийник,
# а не к сейву. Многодисковые игры пишут сейв с серийником первого диска,
# чтобы он читался с любого: у всех десяти таких игр коллекции встречается
# только "(Disc 1)". Поэтому суффикс убираем - иначе сейв с третьего диска
# подписан первым.
DISC_SUFFIX = re.compile(r"\s*\(Disc \d+\)\s*$")


def load_titles(path):
    """Читает TitlesDB: 'SLUS_009.58 Suikoden II' -> {'SLUS-00958': 'Suikoden II'}."""
    titles = {}
    if not path or not os.path.exists(path):
        return titles
    if path.endswith(".json"):
        import json
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            serial, _, name = line.partition(" ")
            name = name.strip()
            if not name or "_" not in serial:
                continue
            titles[serial.replace("_", "-").replace(".", "")] = \
                DISC_SUFFIX.sub("", name)
    return titles


def decode_shift_jis(raw):
    """Заголовок сейва: Shift-JIS, полноширинный, до первого нуля."""
    raw = raw.split(b"\x00", 1)[0]
    try:
        text = raw.decode("shift_jis")
    except UnicodeDecodeError:
        text = raw.decode("shift_jis", errors="replace")
    # Байт 0x817C кодек shift_jis отдаёт как U+2212 MINUS SIGN, а CP932 и
    # декодер macOS - как обычный дефис. В подписях это разделитель
    # ("PE-04/02:46:16"), и математический минус там только мешает поиску.
    text = text.replace("\u2212", "-")
    return unicodedata.normalize("NFKC", text).strip()


def split_filename(raw):
    """20-байтовое поле имени -> регион, серийник, идентификатор сейва."""
    name = raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    if not SONY_NAME.match(name):
        return "", "", name
    # Серийник в базе названий всегда через дефис, даже когда в имени 'P'.
    serial = name[2:6] + "-" + name[7:12]
    return name[:2], serial, name[12:]


def describe(frame, data, titles):
    region, serial, ident = split_filename(frame[10:30])
    serial = normalize_serial(serial) if serial else serial
    size = struct.unpack_from("<I", frame, 4)[0]
    return {
        "serial": serial or "?",
        "region": REGIONS.get(region, region or "?"),
        "identifier": ident,
        "blocks": max(1, size // BLOCK),
        "title": titles.get(serial, ""),
        "internal": decode_shift_jis(data[4:SIGNATURE_END]) if data else "",
        "icon": decode_icon(data) if data else [],
        "chocobo": psxpocket.find_chocobo(data, frame) if data else None,
        "ff8_checksum": (psxff8.verify(data)[3]
                         if data and psxff8.is_ff8(data) else None),
        "application": bool(data) and psxpocket.is_application(frame, data),
    }


def read_psv(blob, titles):
    if blob[:4] != b"\x00VSP":
        return None
    if blob[0x3C] != 1:
        return [{"error": "PSV содержит сейв PS2, а не PS1"}]
    offset = struct.unpack_from("<I", blob, 0x44)[0]
    frame = bytearray(FRAME)
    frame[10:30] = blob[0x64:0x78]
    struct.pack_into("<I", frame, 4, struct.unpack_from("<I", blob, 0x40)[0])
    entry = describe(frame, blob[offset:], titles)
    entry["signed"] = psxsign.verify(blob)[2]
    return [entry]


def read_raw_save(blob, titles, path):
    """Сейв без заголовка: имя игры несёт только имя файла."""
    if blob[:2] not in (b"SC", b"sc"):
        return None
    stem = os.path.basename(path)
    for ext in (".srm", ".mcb", ".mcx", ".pda", ".psx", ".ps1", ".sav", ".bin"):
        if stem.lower().endswith(ext):
            stem = stem[:-len(ext)]
            break
    found = EMBEDDED_NAME.search(stem)
    frame = bytearray(FRAME)
    frame[10:30] = (found.group(0) if found else stem).encode(
        "ascii", errors="replace")[:20].ljust(20, b"\x00")
    struct.pack_into("<I", frame, 4, len(blob))
    entry = describe(frame, blob, titles)
    entry["from_filename"] = True
    return [entry]


def read_mcs(blob, titles):
    if blob[:1] != b"Q":
        return None
    return [describe(blob[:FRAME], blob[FRAME:], titles)]


def card_offset(blob):
    """Смещение, с которого в контейнере начинаются данные карты."""
    for magic, offset, _ in CONTAINERS:
        if blob[:len(magic)] == magic and blob[offset:offset + 2] == b"MC":
            return offset
    if len(blob) == 134976 and blob[3904:3906] == b"MC":
        return 3904
    return None


def find_card_data(blob):
    """Опознаёт контейнер и возвращает (данные карты, имя формата)."""
    for magic, offset, label in CONTAINERS:
        if blob[:len(magic)] == magic and blob[offset:offset + 2] == b"MC":
            return blob[offset:], label

    # DexDrive с побитым заголовком: магии в начале нет, но карта на месте.
    # Тот же обходной путь, что в MemcardRex (ps1card.cs, OpenMemoryCard).
    if len(blob) == 134976 and blob[3904:3906] == b"MC":
        return blob[3904:], "DexDrive .gme (заголовок побит)"

    if len(blob) == MCX_SIZE:
        return None, "MCX"

    return None, None


def read_card(blob, titles):
    data, label = find_card_data(blob)
    if data is None:
        if label == "MCX":
            return [{"error": "MCX-образ зашифрован, нужен AES-ключ SD2PSX"}]
        return None
    blob = data

    entries = []
    for slot in range(SLOTS):
        frame = blob[FRAME * (slot + 1):FRAME * (slot + 2)]
        state, is_head = SLOT_STATES.get(frame[0], ("corrupt", False))
        if not is_head:
            continue
        entry = describe(frame, blob[BLOCK * (slot + 1):], titles)
        entry["slot"] = slot + 1
        entry["state"] = state
        entries.append(entry)
    if not entries:
        return [{"error": f"карта пуста ({label})"}]
    return entries


def identify(path, titles):
    with open(path, "rb") as fh:
        blob = fh.read()
    for reader in (read_psv, read_mcs, read_card):
        entries = reader(blob, titles)
        if entries is not None:
            return entries
    entries = read_raw_save(blob, titles, path)
    if entries is not None:
        return entries
    return [{"error": "формат не распознан"}]


def main():
    parser = argparse.ArgumentParser(description="Определить игру по PS1-сейву")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--titles", default=default_titles_path())
    args = parser.parse_args()

    titles = load_titles(args.titles)
    if not titles:
        print(f"внимание: база названий не найдена ({args.titles})", file=sys.stderr)

    for path in args.files:
        print(os.path.basename(path))
        for entry in identify(path, titles):
            if "error" in entry:
                print(f"    ! {entry['error']}")
                continue
            slot = f"слот {entry['slot']:>2}  " if "slot" in entry else ""
            name = entry["title"] or entry["internal"] or "— не в базе —"
            print(f"    {slot}{entry['serial']:<11} {name}")
            detail = f"{entry['region']}, {entry['blocks']} бл."
            if entry["identifier"]:
                detail += f", id {entry['identifier']}"
            if entry["title"] and entry["internal"]:
                detail += f", в сейве: {entry['internal']}"
            if entry.get("signed") is False:
                detail += ", ПОДПИСЬ НЕ СХОДИТСЯ"
            if entry.get("state") == "deleted":
                detail += ", удалён"
            if entry.get("from_filename"):
                detail += ", опознан по имени файла"
            if entry.get("application"):
                detail += ", приложение PocketStation"
            if entry.get("ff8_checksum") is False:
                detail += ", КОНТРОЛЬНАЯ СУММА НЕ СХОДИТСЯ"
            print(f"    {' ' * len(slot)}{'':11} {detail}")
            if entry.get("chocobo"):
                print(f"    {' ' * len(slot)}{'':11} "
                      f"{psxpocket.summary(entry['chocobo'])}")
        print()




# --- Иконки -----------------------------------------------------------------
# Палитра: 16 цветов BGR555 по смещению 0x60 блока сейва.
# Кадры: 16x16, 4 бита на пиксель, по 128 байт, начиная с 0x80.
# Число кадров закодировано в байте 0x02 (0x11/0x12/0x13).

ICON_FRAME_COUNTS = {0x11: 1, 0x12: 2, 0x13: 3}
ICON_SIZE = 16


def decode_palette(block):
    palette = []
    for i in range(16):
        lo, hi = block[0x60 + i * 2], block[0x61 + i * 2]
        red = (lo & 0x1F) << 3
        green = ((hi & 0x3) << 6) | ((lo & 0xE0) >> 2)
        blue = (hi & 0x7C) << 1
        # Чёрный с нулевым STP-битом означает прозрачный, а не чёрный пиксель.
        opaque = (red | green | blue | (hi & 0x80)) != 0
        palette.append((red, green, blue, 255 if opaque else 0))
    return palette


def decode_icon(block):
    """Возвращает список кадров, каждый - строки RGBA по 16 пикселей."""
    if len(block) < 0x80 or block[:2] not in (b"SC", b"sc"):
        return []
    count = ICON_FRAME_COUNTS.get(block[2], 0)
    if not count or len(block) < 0x80 + 128 * count:
        return []

    palette = decode_palette(block)
    frames = []
    for index in range(count):
        base = 0x80 + 128 * index
        rows = []
        for y in range(ICON_SIZE):
            row = bytearray()
            for x in range(ICON_SIZE // 2):
                packed = block[base + y * 8 + x]
                row += bytes(palette[packed & 0xF])
                row += bytes(palette[packed >> 4])
            rows.append(bytes(row))
        frames.append(rows)
    return frames


def write_png(width, height, rows):
    """Минимальный PNG RGBA без зависимостей."""
    import zlib

    def chunk(tag, payload):
        body = tag + payload
        return (struct.pack(">I", len(payload)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + row for row in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def icon_sprite(frames):
    """Склеивает кадры в горизонтальную ленту - её анимирует CSS."""
    if not frames:
        return None, 0
    rows = [b"".join(frame[y] for frame in frames) for y in range(ICON_SIZE)]
    return write_png(ICON_SIZE * len(frames), ICON_SIZE, rows), len(frames)


if __name__ == "__main__":
    main()
