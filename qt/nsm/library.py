"""Коллекция сейвов: обход папок, сведение дублей, группировка по играм.

Разбор берётся из `tools/` без изменений - тот же движок, что у версии
для macOS, и сверенный с ней построчно.
"""

from . import lang
import hashlib
import os
import sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(HERE, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import psxid            # noqa: E402
import psxbuild         # noqa: E402
import psxchoco         # noqa: E402
import psxplaytime      # noqa: E402
import psxtemplate      # noqa: E402
import psxapp           # noqa: E402


@dataclass
class Item:
    """Один сейв в том виде, в каком его показывает приложение."""
    path: str
    where: str
    block: bytes
    frame: bytes
    title: str
    signature: str
    serial: str
    region: str
    blocks: int
    playtime: int | None
    fingerprint: str
    search_key: str = ""
    frames: int = 1

    @property
    def folder(self):
        return os.path.basename(os.path.dirname(self.path))

    @property
    def clock(self):
        if self.playtime is None:
            return None
        return f"{self.playtime // 3600}:{self.playtime // 60 % 60:02d}"


class Library:
    """Все папки разом. Сейв, лежащий в двух папках, считается один раз."""

    def __init__(self):
        self.titles = psxid.load_titles(psxid.default_titles_path())
        self.templates = psxtemplate.load()
        self.by_serial = psxtemplate.by_serial(self.templates)
        self.playtimes = psxplaytime.load()
        self.items: list[Item] = []
        self.unique: list[Item] = []
        self.by_game: dict[str, list[Item]] = {}
        self.games: list[tuple[str, int]] = []
        self.cards = 0
        self.skipped: list[tuple[str, str]] = []

    def load(self, folders, progress=None):
        self.items, self.skipped, self.cards = [], [], 0
        files = []
        for folder in folders:
            for root, _, names in os.walk(folder):
                for name in sorted(names):
                    if name.startswith("."):
                        continue
                    full = os.path.join(root, name)
                    try:
                        if os.path.getsize(full) < psxid.BLOCK:
                            continue
                    except OSError:
                        continue
                    files.append(full)

        for done, full in enumerate(files):
            if progress and done % 25 == 0:
                progress(done, len(files))
            try:
                found = psxbuild.sources(full)
            except Exception:
                self.skipped.append((os.path.basename(full), lang.t("could not be read")))
                continue
            if not found:
                continue
            if self._is_card(full):
                self.cards += 1
            for entry in found:
                item = self._make(full, entry)
                if item:
                    self.items.append(item)
        if progress:
            progress(len(files), len(files))
        self._regroup()

    @staticmethod
    def _is_card(path):
        """Образ карты: 15 слотов по 8192 плюс каталог, магия MC.

        Проверять только магию мало - она есть и у отдельного сейва
        внутри контейнера.
        """
        try:
            with open(path, "rb") as fh:
                blob = fh.read()
        except OSError:
            return False
        # Возвращает пару (данные, название формата).
        data, _ = psxid.find_card_data(blob)
        return data is not None and len(data) >= psxid.BLOCK * 16

    def _make(self, path, entry):
        """Сейв целиком: у многоблочного тело - все блоки подряд.

        Так же его собирает и сверка движков, и версия для macOS. Если
        брать только первый блок, у многоблочных сейвов расходится
        отпечаток, и дубли сводятся неверно.
        """
        chain = entry.get("blocks") or []
        if not chain:
            return None
        block = b"".join(chain)
        frame = bytearray(psxid.FRAME)
        frame[10:30] = bytes(entry["name"])
        frame = bytes(frame)
        card = psxapp.describe_save({"block": block, "frame": frame}, self.titles)
        seconds = self._playtime(block, frame)
        # Имя входит в отпечаток намеренно: оно живёт в каталожном фрейме,
        # и по нему консоль с игрой находят сохранение. Два сейва с одним
        # телом, но разными именами - разные сейвы.
        digest = hashlib.blake2b(bytes(frame[10:30]) + bytes(block),
                                 digest_size=16).hexdigest()
        # Движок ставит русскую заглушку, а интерфейс бывает любым:
        # берём её на себя. Сама игра название всё равно не сообщает -
        # оно приходит из базы серийников.
        title = card["title"]
        # Движок ставит русскую заглушку, а интерфейс бывает любым.
        # Название игры он всё равно не придумывает - оно приходит из
        # базы серийников, и когда её нет, названия нет ни на каком языке.
        if title == "Неизвестная игра":
            title = lang.t("Unknown game")
        return Item(
            path=path, where=entry.get("where", ""),
            block=bytes(block), frame=bytes(frame),
            title=title, signature=card["internal"], serial=card["serial"],
            region=card["region"], blocks=card["blocks"],
            playtime=seconds, fingerprint=digest,
            search_key=f"{title}\x01{card['internal']}\x01{card['serial']}".lower(),
            frames=card.get("frames", 1) or 1)

    def _playtime(self, block, frame):
        """Сперва свой разборщик игры, потом таблица автопоиска.

        Порядок важен: у Parasite Eve II по общему смещению из таблицы
        лежит не время, и выходило триста тысяч часов. Свой разборщик
        читает поле внутри записи и сходится с подписью.
        """
        for _label, matches, reader, _kind in psxapp.READERS:
            if not matches(frame):
                continue
            try:
                info = reader(block)
            except Exception:
                return None
            value = (info or {}).get("playtime")
            if isinstance(value, (list, tuple)) and len(value) == 3:
                return value[0] * 3600 + value[1] * 60 + value[2]
            if isinstance(value, dict):
                if "as_seconds" in value:
                    return value["as_seconds"]
                if "hours" in value:
                    return (value["hours"] * 3600 + value.get("minutes", 0) * 60
                            + value.get("seconds", 0))
            break
        try:
            found = psxplaytime.playtime(block, frame, self.playtimes)
        except Exception:
            return None
        if not found:
            return None
        seconds = found[0] * 3600 + found[1] * 60 + found[2]
        # Смещения таблицы найдены автопоиском и на части изданий
        # промахиваются: у Metal Gear Solid выходило 19 884 часа.
        # Прохождение длиннее тысячи часов - почти наверняка не время.
        return seconds if seconds < 1000 * 3600 else None

    def _regroup(self):
        seen, unique = set(), []
        for item in self.items:
            if item.fingerprint in seen:
                continue
            seen.add(item.fingerprint)
            unique.append(item)
        self.unique = unique

        grouped: dict[str, list[Item]] = {}
        for item in unique:
            grouped.setdefault(item.title, []).append(item)
        self.by_game = grouped
        self.games = sorted(((name, len(rows)) for name, rows in grouped.items()),
                            key=lambda pair: (-pair[1], pair[0]))

    def visible(self, selection, order="playtime", search=""):
        if selection == "*":
            rows = self.unique
        elif selection == "#cards":
            # Сейвы, лежащие внутри образов карт, а не отдельными файлами.
            rows = [r for r in self.unique if self._is_card(r.path)]
        else:
            rows = self.by_game.get(selection, [])
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in r.search_key]
        if order == "title":
            return sorted(rows, key=lambda r: (r.title.lower(), r.signature))
        if order == "natural":
            return list(rows)
        # По времени: сейвы без него уходят вниз, а не притворяются нулевыми.
        return sorted(rows, key=lambda r: (r.playtime is None,
                                           -(r.playtime or 0), r.title.lower()))

    def detail(self, item):
        """Подробный разбор для панели справа."""
        entry = {"block": item.block, "frame": item.frame}
        return psxapp.detail(entry, self.titles, self.templates,
                             self.by_serial, self.playtimes)
