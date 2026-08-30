#!/usr/bin/env python3
"""Разбор сейва Final Fantasy VII.

Раскладка - по ff7tk (`FF7Save_Types.h`, `Type_FF7CHAR.h`), там каждое поле
подписано hex-смещением прямо в комментарии. Названия предметов и локаций -
из шаблона game-tools-collection: в выжимке ff7tk их нет, они подгружаются
из ресурсов Qt.

Слот занимает 0x10F4 байта и начинается с 0x200 блока - проверено якорем:
подпись сейва говорит "FF7/SAVE01/00:15", и по этой базе время выходит 0:15:17.
"""

import struct

import psxid

import psxff7data as data

SERIALS = ("SCUS-94163", "SCUS-94164", "SCUS-94165",
           "SCES-00867", "SCES-00868", "SCES-00869",
           "SLPS-00700", "SLPS-00701", "SLPS-00702",
           "SLES-00867", "SLES-00868", "SLES-00869")

SLOT = 0x200                # начало слота внутри блока сейва
SLOT_SIZE = 0x10F4

# Смещения от начала слота.
CHECKSUM = 0x0000
DESC = 0x0004               # FF7DESC, 68 байт
DESC_LEVEL = 0x00
DESC_PARTY = 0x01
DESC_NAME = 0x04
DESC_HP, DESC_HP_MAX = 0x14, 0x16
DESC_MP, DESC_MP_MAX = 0x18, 0x1A
DESC_GIL, DESC_TIME = 0x1C, 0x20
DESC_LOCATION = 0x24

CHARS = 0x0054              # 9 записей
CHAR_SIZE = 0x84
PARTY = 0x04F8
MATERIA = 0x077C            # 200 слотов по 4 байта
MATERIA_SLOTS = 200
MATERIA_STOLEN = 0x0A9C     # 48 слотов, украденное Юффи
MATERIA_STOLEN_SLOTS = 48
MATERIA_SIZE = 4
MATERIA_EMPTY = 0xFF
# У персонажа 16 гнёзд: восемь в оружии, восемь в броне.
C_MATERIA = 0x0040
C_MATERIA_SLOTS = 16
MASTERED_AP = 0xFFFFFF
ITEMS = 0x04FC              # 320 слотов по u16: младшие 9 бит - предмет
ITEM_SLOTS = 320
GIL = 0x0B7C
TIME = 0x0B80               # секунды
MAP_ID = 0x0B94
LOCATION_ID = 0x0B96
BATTLES = 0x0BBC
RUNS = 0x0BBE

# Смещения внутри записи персонажа.
C_ID, C_LEVEL = 0x00, 0x01
C_STATS = 0x02              # сила, стойкость, магия, дух, ловкость, удача
C_LIMIT_LEVEL, C_LIMIT_BAR = 0x0E, 0x0F
C_NAME = 0x10
C_WEAPON, C_ARMOR, C_ACCESSORY = 0x1C, 0x1D, 0x1E
C_KILLS = 0x24
C_HP, C_HP_BASE = 0x2C, 0x2E

NAME_END = 0xFF
STAT_NAMES = ("сила", "стойкость", "магия", "дух", "ловкость", "удача")
# Количество предмета лежит в старших семи битах, номер - в младших девяти.
ITEM_MASK, ITEM_SHIFT = 0x1FF, 9


def is_ff7(frame):
    return psxid.serial_of(frame) in SERIALS


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _u32(block, offset):
    return struct.unpack_from("<I", block, offset)[0]


def decode_name(raw):
    out = []
    for byte in raw:
        if byte == NAME_END:
            break
        out.append(data.LETTERS.get(byte, ""))
    return "".join(out).strip()


def read_materia(block, offset):
    """Одно гнездо: номер, AP (24 бита) и уровень звёзд по порогам."""
    ident = block[offset]
    if ident == MATERIA_EMPTY:
        return None
    ap = int.from_bytes(block[offset + 1:offset + 4], "little")
    thresholds = data.MATERIA_AP.get(ident, ())
    stars = sum(1 for t in thresholds if ap >= t)
    return {"name": data.MATERIA.get(ident, f"#{ident:#04x}"),
            "kind": data.MATERIA_TYPE.get(ident, ""),
            "ap": ap, "stars": stars, "total": len(thresholds),
            "mastered": ap >= MASTERED_AP or (
                len(thresholds) > 1 and ap >= thresholds[-1])}


def materia_list(block, base, count):
    out = []
    for index in range(count):
        found = read_materia(block, SLOT + base + index * MATERIA_SIZE)
        if found:
            out.append(found)
    return out


def characters(block):
    out = []
    for index in range(9):
        base = SLOT + CHARS + index * CHAR_SIZE
        ident = block[base + C_ID]
        if ident == 0xFF:
            continue
        weapon = block[base + C_WEAPON]
        out.append({
            "who": data.CHARACTERS.get(ident, f"#{ident}"),
            "name": decode_name(block[base + C_NAME:base + C_NAME + 12]),
            "level": block[base + C_LEVEL],
            "stats": tuple(block[base + C_STATS + i] for i in range(6)),
            "hp": (_u16(block, base + C_HP), _u16(block, base + C_HP_BASE)),
            "kills": _u16(block, base + C_KILLS),
            "limit_level": block[base + C_LIMIT_LEVEL],
            "weapon": data.WEAPONS.get(weapon, f"#{weapon}"),
            "armor": data.ARMORS.get(block[base + C_ARMOR],
                                     f"#{block[base + C_ARMOR]}"),
            "accessory": data.ACCESSORIES.get(block[base + C_ACCESSORY], ""),
            "materia": [
                (("оружие" if slot < 8 else "броня"), found)
                for slot in range(C_MATERIA_SLOTS)
                for found in [read_materia(block, base + C_MATERIA
                                           + slot * MATERIA_SIZE)]
                if found],
        })
    return out


def inventory(block):
    out = []
    for slot in range(ITEM_SLOTS):
        packed = _u16(block, SLOT + ITEMS + slot * 2)
        if packed == 0xFFFF:
            continue
        item, count = packed & ITEM_MASK, packed >> ITEM_SHIFT
        if not count:
            continue
        out.append({"name": data.ITEMS.get(item, f"#{item}"), "count": count,
                    "kind": data.ITEM_KIND.get(item, "Предметы")})
    return out


def overview(block, frame=None):
    if frame is not None and not is_ff7(frame):
        return None
    if len(block) < SLOT + SLOT_SIZE:
        return None
    desc = SLOT + DESC
    seconds = _u32(block, SLOT + TIME)
    location = _u16(block, SLOT + LOCATION_ID)
    return {
        "leader": decode_name(block[desc + DESC_NAME:desc + DESC_NAME + 16]),
        "level": block[desc + DESC_LEVEL],
        "playtime": (seconds // 3600, seconds // 60 % 60, seconds % 60),
        "playtime_raw": seconds,
        "gil": _u32(block, SLOT + GIL),
        "location": data.LOCATIONS.get(location, f"#{location:#06x}"),
        "location_text": decode_name(
            block[desc + DESC_LOCATION:desc + DESC_LOCATION + 32]),
        "battles": _u16(block, SLOT + BATTLES),
        "runs": _u16(block, SLOT + RUNS),
        "characters": characters(block),
        "inventory": inventory(block),
        "materia": materia_list(block, MATERIA, MATERIA_SLOTS),
        "materia_stolen": materia_list(block, MATERIA_STOLEN,
                                       MATERIA_STOLEN_SLOTS),
    }


def report(info, indent=""):
    hours, minutes, seconds = info["playtime"]
    lines = [f"{indent}{info['leader']}, уровень {info['level']} · "
             f"наиграно {hours}:{minutes:02d}:{seconds:02d}",
             f"{indent}гилы {info['gil']:,}".replace(",", " ")
             + f" · боёв {info['battles']} · побегов {info['runs']}",
             f"{indent}место: {info['location']}"
             + (f" ({info['location_text']})" if info["location_text"] else ""),
             "",
             f"{indent}Персонажи ({len(info['characters'])})"]
    for unit in info["characters"]:
        lines.append(f"{indent}  {unit['name'][:10]:<10} ур.{unit['level']:>3}"
                     f"  HP {unit['hp'][0]}/{unit['hp'][1]:<5}"
                     f"  {unit['weapon'][:18]:<18} {unit['armor'][:16]}")
        lines.append(f"{indent}      " + "  ".join(
            f"{n} {v}" for n, v in zip(STAT_NAMES, unit["stats"])))
        if unit["materia"]:
            lines.append(f"{indent}      материя: " + ", ".join(
                f"{m['name']}{'★' * m['stars']}" for _, m in unit["materia"]))
    lines.append("")
    mastered = sum(1 for m in info["materia"] if m["mastered"])
    lines.append(f"{indent}Материя в запасе ({len(info['materia'])}, "
                 f"освоено {mastered})")
    for item in info["materia"][:12]:
        lines.append(f"{indent}  {item['name'][:20]:<20} {'★' * item['stars']:<6}"
                     f" {item['ap']:>8} AP   {item['kind']}")
    if info["materia_stolen"]:
        lines.append(f"{indent}  украдено Юффи: {len(info['materia_stolen'])}")
    lines.append("")
    lines.append(f"{indent}Инвентарь ({len(info['inventory'])} позиций)")
    for entry in info["inventory"]:
        lines.append(f"{indent}  {entry['name']:<24} ×{entry['count']}")
    return "\n".join(lines)
