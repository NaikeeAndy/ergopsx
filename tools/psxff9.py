#!/usr/bin/env python3
"""Разбор сейва Final Fantasy IX.

Смещения - от начала блока сейва, источник: game-tools-collection,
шаблон final-fantasy-ix.
"""

import struct

import psxid

import psxff9data as data

SERIALS = ("SLUS-01251", "SLUS-01295", "SLUS-01296", "SLUS-01297",
           "SLES-02965", "SLES-12965", "SLES-22965", "SLES-32965",
           "SLPS-02000", "SLPS-02001", "SLPS-02002", "SLPS-02003")

# Шаблон называет это секундами, но подпись, которую пишет сама игра,
# сходится только при делении на 60: счётчик в кадрах. Проверено на 13 сейвах.
PLAYTIME = 0x12C
FRAMES_PER_SECOND = 60
LOCATION = 0x1A0
GIL = 0xEE8

PARTY_BASE = 0x9D0
PARTY_SIZE = 0x90
PARTY_COUNT = 9
NAME_LENGTH = 0x0B
LEVEL = 0x00B               # смещения ниже - от начала записи бойца
EXPERIENCE = 0x00C
HP_CUR, HP_MAX = 0x010, 0x018
MP_CUR, MP_MAX = 0x012, 0x01A
TRANCE = 0x020

# Диск лежит битовой маской, а не числом: 1, 2, 4, 8 - это диски 1..4.
# Из-за этого его не найти перебором значений 1..4.
DISC = 0x104
DISCS = {1: 1, 2: 2, 4: 3, 8: 4}

# Экипировка, смещения от начала записи бойца. Источник - шаблон
# game-tools-collection; наручи и тело он не подписывает, но они лежат
# между головой и аксессуаром.
GEAR = ((0x39, "оружие", "WEAPONS"), (0x3A, "голова", "HEAD_GEARS"),
        (0x3B, "наручи", "ARM_GEARS"), (0x3C, "тело", "BODIES"),
        (0x3D, "аксессуар", "ACCESSORIES"))
EMPTY_GEAR = (0x00, 0xFF)

INVENTORY_BASE = 0xF20
INVENTORY_SLOTS = 255
NAME_END = 0xFF


def is_ff9(frame):
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


def party(block):
    out = []
    for index in range(PARTY_COUNT):
        base = PARTY_BASE + index * PARTY_SIZE
        level = block[base + LEVEL]
        hp_max = _u16(block, base + HP_MAX)
        if not level or not hp_max:
            continue
        out.append({
            "slot": index,
            "who": data.CHARACTERS.get(index, f"#{index}"),
            "name": decode_name(block[base:base + NAME_LENGTH]),
            "level": level,
            "exp": _u32(block, base + EXPERIENCE),
            "hp": (_u16(block, base + HP_CUR), hp_max),
            "mp": (_u16(block, base + MP_CUR), _u16(block, base + MP_MAX)),
            "trance": block[base + TRANCE],
            "gear": gear(block, base),
        })
    return out


def gear(block, base):
    """[(слот, предмет)] - пустые слоты пропускаем."""
    out = []
    for offset, label, table in GEAR:
        value = block[base + offset]
        if value in EMPTY_GEAR:
            continue
        # Самоцветы (Diamond, Ruby, Peridot) тоже надеваются как аксессуары,
        # но лежат в общем справочнике предметов, а не в ACCESSORIES.
        name = (getattr(data, table).get(value) or data.ALL_GEAR.get(value)
                or data.ITEMS.get(value))
        out.append((label, name or f"#{value}"))
    return out


def inventory(block):
    out = []
    for slot in range(INVENTORY_SLOTS):
        base = INVENTORY_BASE + slot * 2
        item, count = block[base], block[base + 1]
        if item == 0xFF or not count:
            continue
        out.append((data.ITEMS.get(item, f"#{item:#04x}"), count))
    return out


def overview(block, frame=None):
    if frame is not None and not is_ff9(frame):
        return None
    if len(block) < 0x2000:
        return None
    seconds = _u32(block, PLAYTIME) // FRAMES_PER_SECOND
    return {
        "playtime": (seconds // 3600, seconds // 60 % 60, seconds % 60),
        "playtime_raw": seconds,
        "gil": _u32(block, GIL),
        "location": _u16(block, LOCATION),
        "disc": DISCS.get(block[DISC]),
        "party": party(block),
        "inventory": inventory(block),
    }


def report(info, indent=""):
    hours, minutes, seconds = info["playtime"]
    lines = [f"{indent}наиграно {hours}:{minutes:02d}:{seconds:02d}"
             f" · гилы {info['gil']:,}".replace(",", " ")]
    lines.append(f"{indent}Партия ({len(info['party'])})")
    for unit in info["party"]:
        lines.append(f"{indent}  {unit['name'][:10]:<10} ур.{unit['level']:>3}"
                     f"  HP {unit['hp'][0]}/{unit['hp'][1]:<5}"
                     f"  MP {unit['mp'][0]}/{unit['mp'][1]:<4}"
                     f"  ({unit['who']})")
    lines.append(f"{indent}Инвентарь ({len(info['inventory'])} позиций)")
    for name, count in info["inventory"][:16]:
        lines.append(f"{indent}  {name:<22} ×{count}")
    return "\n".join(lines)
