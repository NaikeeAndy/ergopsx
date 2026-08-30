#!/usr/bin/env python3
"""Состояния эмулятора ePSXe: какая игра и скриншот.

Файл состояния - это gzip, внутри заголовок "ePSXe", версия и серийник диска,
дальше слепок ОЗУ. Рядом лежит файл .pic - миниатюра 128x96 в сыром RGB,
её эмулятор показывает в меню загрузки.
"""

import gzip
import os
import struct

MAGIC = b"ePSXe"
SERIAL_OFFSET = 7
SERIAL_LENGTH = 11

PIC_WIDTH = 128
PIC_HEIGHT = 96
PIC_SIZE = PIC_WIDTH * PIC_HEIGHT * 3


def read_header(path):
    """Возвращает (серийник в формате базы, версия) или None."""
    try:
        with gzip.open(path, "rb") as fh:
            head = fh.read(64)
    except (OSError, EOFError):
        return None
    if head[:len(MAGIC)] != MAGIC:
        return None
    serial = head[SERIAL_OFFSET:SERIAL_OFFSET + SERIAL_LENGTH]
    serial = serial.split(b"\x00")[0].decode("ascii", errors="replace")
    version = struct.unpack_from("<H", head, len(MAGIC))[0]
    return serial, version


def screenshot_path(state_path):
    """ePSXe кладёт миниатюру рядом, добавляя .pic к имени состояния."""
    candidate = state_path + ".pic"
    return candidate if os.path.exists(candidate) else None


def read_screenshot(path):
    """Сырой RGB 128x96 -> строки RGBA для нашего PNG-писателя."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) < PIC_SIZE:
        return None
    rows = []
    for y in range(PIC_HEIGHT):
        row = bytearray()
        base = y * PIC_WIDTH * 3
        for x in range(PIC_WIDTH):
            offset = base + x * 3
            row += raw[offset:offset + 3]
            row.append(0xFF)
        rows.append(bytes(row))
    return rows


def describe(path, titles=None):
    header = read_header(path)
    if header is None:
        return None
    serial, version = header
    # В базе названий серийники записаны ровно в таком же виде: SLUS_015.41.
    lookup = serial.replace("_", "-").replace(".", "")
    return {
        "serial": serial,
        "version": version,
        "title": (titles or {}).get(lookup, ""),
        "screenshot": screenshot_path(path),
        "slot": os.path.splitext(path)[1].lstrip("."),
    }
