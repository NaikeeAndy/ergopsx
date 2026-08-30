#!/usr/bin/env python3
"""Наигранное время по играм, найденное автопоиском (см. psxdiscover.py).

Поле искалось перебором смещений против подписи, которую пишет сама игра,
и должно было сойтись на всех её сейвах сразу. Это факт из данных, а не
чужой разбор - готовых спецификаций по этим играм не существует.
"""

import json
import os
import struct

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "playtime.json")

# Во что превращать сырое значение, чтобы получить секунды.
DIVISORS = {"секунды": 1, "минуты": 1 / 60, "кадры 60 Гц": 60, "кадры 50 Гц": 50}
WIDTHS = {"u32": ("<I", 4), "u16": ("<H", 2)}


def load(path=DATA_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def serial_of(frame):
    import psxid
    return psxid.serial_of(frame)


def _pick(spec, block):
    """Под одним серийником бывает несколько игр - выбираем по подписи.

    У Final Fantasy Origins это FF1 и FF2: серийник общий, раскладка разная."""
    if isinstance(spec, dict):
        return spec
    import psxid
    title = psxid.decode_shift_jis(block[4:68])
    token = title.split()[0] if title.split() else ""
    for variant in spec:
        if variant.get("match") == token:
            return variant
    return None


def playtime(block, frame, table=None):
    """(часы, минуты, секунды, название единицы) или None."""
    table = table if table is not None else load()
    spec = table.get(serial_of(frame))
    if spec is None:
        return None
    spec = _pick(spec, block)
    if spec is None:
        return None
    fmt, size = WIDTHS[spec["width"]]
    if spec["offset"] + size > len(block):
        return None
    raw = struct.unpack_from(fmt, block, spec["offset"])[0]
    seconds = int(raw / DIVISORS[spec["unit"]])
    return (seconds // 3600, seconds // 60 % 60, seconds % 60, spec["unit"])
