#!/usr/bin/env python3
"""Экранные статы Final Fantasy Tactics из сырых значений сейва.

В сейве лежат raw-статы - 24-битные числа, не зависящие от класса. То, что
игра рисует на экране, получается умножением на множитель текущего класса:

    экранное = clamp(1, потолок, raw * M // 1638400)

Два разных числа на класс, и путать их нельзя: C влияет на рост raw (навсегда),
M - только на отображение (меняется при смене класса). Здесь нужен M.

Константы - в data/fft-growth.json, источник - AeroStar Battle Mechanics Guide
v6.5, §7.1-7.4. Ни одно число не зашито в код.
"""

import json
import os

STATS = ("hp", "mp", "sp", "pa", "ma")
STAT_LABELS = {"hp": "HP", "mp": "MP", "sp": "скорость",
               "pa": "физ. атака", "ma": "маг. атака"}

# ID дженерик-классов идут подряд в том же порядке, что и в таблице guide'а.
GENERIC_FIRST_ID = 0x4A

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data", "fft-growth.json")


def load(path=DATA_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def job_table(data=None):
    """ID класса из сейва -> {'name', 'mult', 'growth'}."""
    data = data or load()
    table = {}
    # Дженерики: 0x4A..0x5D в порядке перечисления, версии только для WotL пропускаем.
    ps1_generics = [j for j in data["generic_jobs"] if not j.get("wotl_only")]
    for offset, job in enumerate(ps1_generics):
        table[GENERIC_FIRST_ID + offset] = job
    # Особые классы перечислены своими ID, иногда через дробь: "1E/34", "01-03".
    for job in data["special_jobs"]:
        for part in job["id"].split("/"):
            if "-" in part:
                lo, hi = (int(x, 16) for x in part.split("-"))
                ids = range(lo, hi + 1)
            else:
                ids = [int(part, 16)]
            for value in ids:
                table[value] = job
    return table


def displayed(raw, job, data=None):
    """raw-статы (dict по STATS) -> экранные значения для данного класса."""
    data = data or load()
    divisor = data["constants"]["display_divisor"]
    caps = data["display_caps"]
    out = {}
    for stat in STATS:
        if stat not in raw or job is None:
            continue
        # Целочисленно и в одно выражение: дробями здесь пользоваться нельзя.
        value = raw[stat] * job["mult"][stat] // divisor
        out[stat] = max(data["constants"]["min_displayed"], min(caps[stat], value))
    return out


def level_up(raw_value, growth, level):
    """level - всегда НИЖНИЙ уровень перехода."""
    return min(0xFFFFFF, raw_value + raw_value // (growth + level))


def level_down(raw_value, growth, level):
    """level - уровень, НА который падаем (он же нижний)."""
    return max(0, raw_value - raw_value // (level + growth))


def run_up(raw_value, growth, start, end):
    for level in range(start, end):
        raw_value = level_up(raw_value, growth, level)
    return raw_value


def run_down(raw_value, growth, start, end):
    for level in range(start - 1, end - 1, -1):
        raw_value = level_down(raw_value, growth, level)
    return raw_value


def capped(raw, data=None):
    """Какие статы уже упёрлись в функциональный потолок raw."""
    data = data or load()
    limits = data["functional_raw_caps"]
    return {stat: raw.get(stat, 0) >= limits[stat] for stat in STATS}
