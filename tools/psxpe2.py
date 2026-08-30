"""Разбор сейва Parasite Eve II.

Раскладка - из `GabeRealB/parasite-eve-2-decomp`: там проставлены все
смещения и размеры, но **имён у полей нет** - почти все называются
`field_XX`. Поэтому здесь только то, что удалось привязать к якорю:
игра пишет в подпись время и место, и по ним поля найдены перебором.

Что означают остальные сотни байт - неизвестно, и выдумывать им
названия хуже, чем не показывать вовсе.
"""

import struct

import psxid

SERIALS = {"SLUS-01042", "SLUS-01055", "SLES-02558", "SLES-12558",
           "SLPS-02480", "SLPS-02481"}

# Размер `McSaveData`. Сейв держит **две записи подряд**: по этому
# смещению все поля повторяются второй раз.
RECORD = 0x944
# Наигранное время в МИНУТАХ, а не секундах. Сошлось с подписью
# на 32 сейвах коллекции из 32.
PLAYTIME = 0x00C          # u16, от начала записи
# Число, которое игра пишет в скобках после места. Сошлось на всех
# 32 сейвах, но что оно значит - неизвестно.
MARK = 0x011              # u8
# Слоты предметов. Названий предметов в разборе нет, поэтому
# считаем только занятые.
ITEMS, ITEMS_COUNT, ITEM_SIZE = 0x1C8, 0x7C, 8
STORED, STORED_COUNT = 0x5C8, 0x20


def is_pe2(frame):
    return psxid.serial_of(frame) in SERIALS


def overview(block):
    # Данные игры начинаются за кадрами иконки, а их число у сейвов
    # этой игры разное - считаем по блоку, а не предполагаем.
    base = psxid.data_offset(block)
    if len(block) < base + RECORD:
        return None

    minutes = struct.unpack_from("<H", block, base + PLAYTIME)[0]
    banks = 2 if len(block) >= base + RECORD * 2 else 1

    def occupied(at, count):
        used = 0
        for slot in range(count):
            index = base + at + slot * ITEM_SIZE
            if index >= len(block):
                break
            if block[index]:
                used += 1
        return used

    return {
        "playtime": [minutes // 60, minutes % 60, 0],
        "playtime_minutes": minutes,
        "mark": block[base + MARK],
        "items": occupied(ITEMS, ITEMS_COUNT),
        "stored": occupied(STORED, STORED_COUNT),
        "banks": banks,
    }
