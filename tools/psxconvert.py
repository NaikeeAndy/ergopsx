#!/usr/bin/env python3
"""Перевод сейвов между контейнерами и смена региона.

Одиночные форматы: MCS (каталожный фрейм плюс блоки), PSV (для PS3, с
подписью), сырой блок. Карты целиком собирает psxbuild.

Регион записан двумя первыми байтами имени сейва: BA - Америка, BE - Европа,
BI - Япония. Меняем только их: серийник игры (SLUS/SLES/SLPS) при этом
остаётся прежним, потому что перевести его нельзя - у изданий разных регионов
это разные номера, и соответствие ниоткуда не следует.
"""

import os
import struct

import psxbuild
import psxid
import psxsign

SINGLE = ("mcs", "psv", "raw")
# .mcd - тот же сырой образ, что .mcr. Так называет карты DuckStation
# и его ядро SwanStation, а на Switch это единственный ходовой формат.
CARDS = ("mcr", "mcd", "gme", "vmp")

REGION_CODES = {"america": b"BA", "europe": b"BE", "japan": b"BI"}

# Заголовок PSV: 0x84 байта. Постоянная часть снята с настоящих файлов PS3,
# меняются только размер, имя, salt seed и подпись.
PSV_SIZE = 0x40
PSV_DATA = 0x44
PSV_NAME = 0x64
PSV_HEADER = 0x84


def with_region(name, region):
    """Имя сейва с другим кодом региона."""
    code = REGION_CODES.get((region or "").lower())
    if code is None:
        return bytes(name)
    return code + bytes(name)[2:]


def to_mcs(name, blocks):
    """MCS: каталожный фрейм и следом блоки сейва."""
    frame = bytearray(psxid.FRAME)
    frame[0] = psxbuild.FIRST
    struct.pack_into("<I", frame, 4, len(blocks) * psxid.BLOCK)
    struct.pack_into("<H", frame, 8, psxbuild.END)
    frame[10:30] = bytes(name)[:20].ljust(20, b"\x00")
    frame[0x7F] = 0
    value = 0
    for byte in frame[:psxid.FRAME - 1]:
        value ^= byte
    frame[psxid.FRAME - 1] = value
    return bytes(frame) + b"".join(blocks)


def to_raw(name, blocks):
    return b"".join(blocks)


def to_psv(name, blocks):
    """PSV с пересчитанной подписью."""
    payload = b"".join(blocks)
    header = bytearray(PSV_HEADER)
    header[0:4] = psxsign.PSV["magic"]
    header[0x38] = 0x14
    header[0x3C] = 0x01
    struct.pack_into("<I", header, PSV_SIZE, len(payload))
    struct.pack_into("<I", header, PSV_DATA, PSV_HEADER)
    struct.pack_into("<I", header, 0x48, 0x200)
    struct.pack_into("<I", header, 0x5C, len(payload))
    struct.pack_into("<I", header, 0x60, 0x9003)
    header[PSV_NAME:PSV_NAME + 20] = bytes(name)[:20].ljust(20, b"\x00")
    # Salt seed выводится из имени: он должен быть каким-то, а от чего именно
    # зависит - неважно, подпись считается от него же.
    seed = (bytes(name)[:20].ljust(20, b"\x00"))[:psxsign.SEED_LENGTH]
    return psxsign.resign(bytes(header) + payload, seed)


WRITERS = {"mcs": to_mcs, "psv": to_psv, "raw": to_raw}


def single(entry, fmt, region=None):
    """Один сейв в выбранном формате."""
    if fmt not in WRITERS:
        raise ValueError(f"неизвестный формат '{fmt}'")
    name = with_region(entry["name"], region)
    return WRITERS[fmt](name, entry["blocks"])


def card(entries, fmt, region=None):
    """Несколько сейвов в образ карты."""
    if fmt not in CARDS:
        raise ValueError(f"неизвестный формат карты '{fmt}'")
    if region:
        entries = [dict(e, name=with_region(e["name"], region)) for e in entries]
    image, layout, dropped = psxbuild.build(entries)
    wrapper = psxbuild.WRAPPERS.get("." + fmt)
    return (wrapper(image) if wrapper else image), layout, dropped


def suggest_name(entries, fmt, region=None):
    """Имя файла по содержимому: имя сейва или сколько их в карте.

    Регион учитываем, иначе файл с изменённым регионом назван по-старому."""
    if len(entries) == 1:
        name = with_region(entries[0]["name"], region)
        stem = psxbuild._name_of(name) or "save"
    else:
        stem = f"card-{len(entries)}-saves"
        if region:
            stem += f"-{region}"
    return f"{stem}.{fmt}"
