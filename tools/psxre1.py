#!/usr/bin/env python3
"""Разбор сейва Resident Evil (первая часть).

Смещения - от начала блока сейва, источник: game-tools-collection,
шаблон resident-evil.
"""

import struct

import psxid
import psxre1data as data

# Все издания, которые перечисляет валидатор шаблона, включая Director's Cut.
SERIALS = ("SLUS-00170", "SLUS-00551", "SLES-00200", "SLES-00227",
           "SLES-00228", "SLES-00969", "SLES-00970", "SLES-00971",
           "SLPS-00222", "SLPS-00998")

# Смещения от начала блока. Здесь база жёсткая, и это не упущение: часть
# сейвов Director's Cut объявляет в байте 0x02 один кадр иконки, а данные всё
# равно кладёт с 0x200 - по числу кадров такие читаются мимо. Проверено
# подписью игры на обоих видах.
DATA = 0x200
LOCATION = 0x000
HEALTH = 0x01E
PLAYTIME = 0x024           # u32
INK_RIBBONS = 0x028
CHARACTER = 0x02B          # бит 0: 0 - Крис, 1 - Джилл

INVENTORY_BASE = 0x124
INVENTORY_SLOTS = 8
CONTAINER_BASE = 0x0C4
CONTAINER_SLOTS = 48


def is_re1(frame):
    return psxid.serial_of(frame) in SERIALS


def _u16(block, offset):
    return struct.unpack_from("<H", block, offset)[0]


def _u16be(block, offset):
    """Код локации лежит big-endian - в отличие от всего остального в сейве.
    Проверено сверкой с подписью, которую пишет сама игра."""
    return struct.unpack_from(">H", block, offset)[0]


def _u32(block, offset):
    return struct.unpack_from("<I", block, offset)[0]


def _slots(block, base, count):
    out = []
    for index in range(count):
        item, qty = block[base + index * 2], block[base + index * 2 + 1]
        if not item:
            continue
        out.append((data.ITEMS.get(item, f"#{item:#04x}"), qty))
    return out


def overview(block, frame=None):
    if frame is not None and not is_re1(frame):
        return None
    base = DATA
    if len(block) < base + 0x200:
        return None
    place = _u16be(block, base + LOCATION)
    return {
        "character": data.CHARACTERS.get(block[base + CHARACTER] & 1, "?"),
        "health": _u16(block, base + HEALTH),
        "playtime_raw": _u32(block, base + PLAYTIME),
        "ink_ribbons": block[base + INK_RIBBONS],
        "location": data.LOCATIONS.get(place, f"#{place:#06x}"),
        "inventory": _slots(block, base + INVENTORY_BASE, INVENTORY_SLOTS),
        "container": _slots(block, base + CONTAINER_BASE, CONTAINER_SLOTS),
    }


def report(info, indent=""):
    lines = [f"{indent}{info['character']} · здоровье {info['health']}"
             f" · чернильных лент {info['ink_ribbons']}",
             f"{indent}место: {info['location']}",
             f"{indent}при себе ({len(info['inventory'])}): "
             + (", ".join(f"{n}×{q}" if q else n for n, q in info["inventory"]) or "—"),
             f"{indent}в сундуке ({len(info['container'])}): "
             + (", ".join(f"{n}×{q}" if q else n for n, q in info["container"]) or "—")]
    return "\n".join(lines)
