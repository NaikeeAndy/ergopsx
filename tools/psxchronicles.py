"""Разбор сейва Castlevania Chronicles.

Публичного разбора этой игры нет - раскладка найдена якорем по экрану
выбора игрока: он показывает имя и два числа, и они нашлись в байтах
один в один на трёх сейвах коллекции.

Уровень игра не хранит, а выводит из номера стейджа: их по три на
уровень, как в оригинальной Castlevania, ремейком которой Chronicles
и является. Проверено на стейджах 4, 13 и 16 - второй, пятый и шестой
уровни соответственно.
"""

import struct

import psxid

SERIALS = {"SLUS-01384", "SLES-03449", "SLPM-86808", "SLPM-86809"}

# Смещения от начала данных игры.
YEAR = 0x102        # u16
MONTH, DAY = 0x104, 0x105
HOUR, MINUTE, SECOND = 0x106, 0x107, 0x108
NAME, NAME_SIZE = 0x11A, 8
# Символ-заполнитель в имени: игра рисует его точкой.
FILLER = 0x5B
# Два числа, которые игра показывает под заголовком «stage».
STAGE, COUNTER = 0x124, 0x125
STAGES_PER_LEVEL = 3


def is_chronicles(frame):
    return psxid.serial_of(frame) in SERIALS


def overview(block):
    base = psxid.data_offset(block)
    if len(block) < base + 0x140:
        return None

    raw = bytes(block[base + NAME:base + NAME + NAME_SIZE])
    letters = []
    for byte in raw:
        if byte in (FILLER, 0):
            break
        letters.append(byte)
    name = bytes(letters).decode("ascii", "replace").strip()

    stage = block[base + STAGE]
    return {
        "name": name,
        "stage": stage,
        # Что значит второе число - неизвестно, показываем как есть.
        "counter": block[base + COUNTER],
        "level": (stage - 1) // STAGES_PER_LEVEL + 1 if stage else 0,
        "saved": "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            struct.unpack_from("<H", block, base + YEAR)[0],
            block[base + MONTH], block[base + DAY],
            block[base + HOUR], block[base + MINUTE], block[base + SECOND]),
    }
