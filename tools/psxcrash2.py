"""Разбор сейва Crash Bandicoot 2: Cortex Strikes Back.

Смещения - из `giuse94/PSDX`, где описано **европейское** издание
(SCES-00967) в формате `.mcs`, то есть от начала файла: кадр каталога
плюс блок. Данные игры там начинаются с `0x180`.

У американского издания `tonyhax` называет `0x280` вместо `0x180`, и это
ровно разница в один кадр иконки: европейский сейв объявляет один кадр,
американский - три. Поэтому база считается по самому блоку, а не задаётся
числом: тогда оба издания читаются одним кодом.

**Проверить нечем.** Crash 2, в отличие от первой части, не пишет процент
прохождения в подпись. За разбор говорит только осмысленность значений.
"""

import struct

import psxid

SERIALS = {"SCUS-94154", "SCES-00967", "SCPS-10047", "SCPS-91109",
           "SCES-01005", "SCES-01006", "SCES-01007"}

# Смещения PSDX отсчитаны от начала `.mcs`, где данные с 0x180.
# Здесь они переведены в отсчёт от начала данных игры.
_BASE = 0x180
LAST_LEVEL = 0x188 - _BASE
USERNAME, USERNAME_SIZE = 0x18C - _BASE, 16
LIVES = 0x1AC - _BASE
WUMPA = 0x1B0 - _BASE
AKU_AKU = 0x1B4 - _BASE
SECRETS = 0x1B8 - _BASE
PROGRESS = 0x1BC - _BASE
CRYSTALS = 0x1C4 - _BASE
GEMS = 0x1CC - _BASE


def is_crash2(frame):
    return psxid.serial_of(frame) in SERIALS


def _u32(block, at):
    return struct.unpack_from("<I", block, at)[0]


def _bits(block, at):
    """Собранное лежит битовой маской в одном u32, а не числом: без
    подсчёта битов выходят миллиарды вместо десятков."""
    return bin(_u32(block, at)).count("1")


def overview(block):
    base = psxid.data_offset(block)
    if len(block) < base + 0x200:
        return None

    raw = bytes(block[base + USERNAME:base + USERNAME + USERNAME_SIZE])
    name = raw.split(b"\x00")[0].decode("ascii", "replace").strip()
    return {
        "name": name,
        "level": _u32(block, base + LAST_LEVEL),
        "lives": _u32(block, base + LIVES),
        "wumpa": _u32(block, base + WUMPA),
        "aku_aku": _u32(block, base + AKU_AKU),
        "crystals": _bits(block, base + CRYSTALS),
        "gems": _bits(block, base + GEMS),
        "progress": _bits(block, base + PROGRESS),
        "secrets": _bits(block, base + SECRETS),
    }
