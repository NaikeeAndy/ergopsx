"""Корзина: то, из чего соберётся карта. Копится по дороге, из любого места."""

from . import lang
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(HERE, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import psxbuild  # noqa: E402

SLOTS = 15


class Basket:
    def __init__(self):
        self.items = []
        self.note = None

    @property
    def used(self):
        return sum(item.blocks for item in self.items)

    @property
    def free(self):
        return SLOTS - self.used

    def contains(self, item):
        return any(x.fingerprint == item.fingerprint for x in self.items)

    def toggle(self, item):
        if self.contains(item):
            self.items = [x for x in self.items
                          if x.fingerprint != item.fingerprint]
            self.note = None
            return
        self.add(item)

    def add(self, item):
        if self.contains(item):
            return
        if item.blocks > self.free:
            self.note = (lang.t(f"{item.title} занимает {item.blocks} ", f"{item.title} takes {item.blocks} ")
                         + lang.t(f"{blocks_word(item.blocks)}, а свободно {self.free}", f"{blocks_word(item.blocks)}, only {self.free} free"))
            return
        # Игра находит сейв по имени, поэтому двух одинаковых имён на
        # карте быть не должно. Выбирать за пользователя нельзя - говорим.
        name = bytes(item.frame[10:30])
        clash = next((x for x in self.items
                      if bytes(x.frame[10:30]) == name), None)
        if clash:
            shown = name.split(b"\x00")[0].decode("ascii", "replace")
            self.note = (f"«{shown}» "
                         + lang.t(f"уже в корзине — из {clash.title}. Игра различает ",
                                  f"is already in the basket — from {clash.title}. The game tells ")
                         + lang.t(f"сейвы по имени, двух одинаковых быть не может", f"saves apart by name; two identical names cannot share a card"))
            return
        self.items.append(item)
        self.note = None

    def clear(self):
        self.items = []
        self.note = None

    def layout(self):
        """Раскладка по пятнадцати слотам: у многоблочного видна цепочка."""
        cells = []
        for item in self.items:
            for position in range(item.blocks):
                cells.append((item, position > 0))
        while len(cells) < SLOTS:
            cells.append((None, False))
        return cells

    def build(self):
        """Собирает образ карты из выбранного."""
        entries = []
        for item in self.items:
            blocks = [item.block[at:at + psxbuild.psxid.BLOCK]
                      for at in range(0, len(item.block), psxbuild.psxid.BLOCK)]
            entries.append({"name": bytes(item.frame[10:30]),
                            "blocks": blocks, "where": item.where})
        return psxbuild.build(entries)


def saves_word(count):
    tail = count % 100
    if 11 <= tail <= 14:
        return lang.t("сейвов", "saves")
    return {1: lang.t("сейв", "save"), 2: lang.t("сейва", "saves"), 3: lang.t("сейва", "saves"), 4: lang.t("сейва", "saves")}.get(count % 10, lang.t("сейвов", "saves"))


def blocks_word(count):
    tail = count % 100
    if 11 <= tail <= 14:
        return lang.t("блоков", "blocks")
    return {1: lang.t("блок", "block"), 2: lang.t("блока", "blocks"), 3: lang.t("блока", "blocks"), 4: lang.t("блока", "blocks")}.get(count % 10, lang.t("блоков", "blocks"))
