#!/usr/bin/env python3
"""Просмотрщик сейвов PS1 — локальное приложение в браузере.

    psxapp.py [корневая-папка] [--port 8777]

Слева дерево файлов, справа содержимое выбранного сейва. Никаких зависимостей,
только стандартная библиотека. Слушает исключительно localhost и не выпускает
за пределы указанной корневой папки.
"""

import argparse
import base64
import re
import collections
import json
import os
import posixpath
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psxbuild
import psxchoco
import psxconvert
import psxff5
import psxff6
import psxff7
import psxff8
import psxff8read
import psxfft
import psxff9
import psxfftstats
import psxftp
import psxid
import psxplaytime
import psxre1
import psxsotn
import psxstate
import psxtemplate

PAGE = __file__.replace(".py", ".html")

READERS = (
    ("Final Fantasy Tactics", psxfft.is_fft, psxfft.overview, "fft"),
    ("Castlevania: Symphony of the Night", psxsotn.is_sotn, psxsotn.overview, "sotn"),
    ("Final Fantasy IX", psxff9.is_ff9, psxff9.overview, "ff9"),
    ("Resident Evil", psxre1.is_re1, psxre1.overview, "re1"),
    ("Final Fantasy VII", psxff7.is_ff7, psxff7.overview, "ff7"),
    ("Final Fantasy VI", psxff6.is_ff6, psxff6.overview, "ff6"),
    ("Final Fantasy V", psxff5.is_ff5, psxff5.overview, "ff5"),
)


def icon_uri(block):
    frames = psxid.decode_icon(block)
    sprite, count = psxid.icon_sprite(frames)
    if not sprite:
        return None, 0
    return "data:image/png;base64," + base64.b64encode(sprite).decode(), count


def _seconds(item, playtimes):
    """Наигранное в секундах: сперва таблица автопоиска, потом свой разборщик."""
    found = psxplaytime.playtime(item["block"], item["frame"], playtimes)
    if found:
        return found[0] * 3600 + found[1] * 60 + found[2]
    for _, matches, reader, _ in READERS:
        if matches(item["frame"]):
            try:
                info = reader(item["block"])
            except Exception:
                return None
            # Разборщики отдают время по-разному: кто тройкой, кто словарём.
            value = info and info.get("playtime")
            if isinstance(value, (list, tuple)) and len(value) == 3:
                return value[0] * 3600 + value[1] * 60 + value[2]
            if isinstance(value, dict) and "hours" in value:
                return (value["hours"] * 3600 + value.get("minutes", 0) * 60
                        + value.get("seconds", 0))
            if isinstance(value, dict) and "as_seconds" in value:
                return value["as_seconds"]
            return None
    if psxff8.is_ff8(item["block"]):
        info = psxff8read.overview(item["block"])
        # У FF8 время - разбор нескольких трактовок счётчика; какая из них
        # верна, лежит в "matches", а часы-минуты-секунды внутри неё.
        clock = (info or {}).get("playtime") or {}
        shown = clock.get(clock.get("matches", ""), {})
        if isinstance(shown, dict) and "hours" in shown:
            return (shown["hours"] * 3600 + shown["minutes"] * 60
                    + shown["seconds"])
    return None


def describe_save(item, titles):
    """Краткая карточка сейва для левой панели."""
    entry = psxid.describe(item["frame"], item["block"], titles)
    uri, frames = icon_uri(item["block"])
    return {
        "title": entry["title"] or entry["internal"] or "Неизвестная игра",
        "internal": entry["internal"],
        "serial": entry["serial"],
        "region": entry["region"],
        "blocks": entry["blocks"],
        "identifier": entry["identifier"],
        "application": entry.get("application", False),
        "icon": uri,
        "frames": frames,
    }


# Многие игры пишут процент прохождения прямо в подпись сейва: Crash -
# "クラッシュ (6%)", Castlevania - "CASTLEVANIA-1 ALUCARD 200%".
PROGRESS = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def detail(item, titles, templates=None, by_serial=None, playtimes=None):
    """Подробности для правой панели: общая часть плюс разбор по игре."""
    out = describe_save(item, titles)
    block, frame = item["block"], item["frame"]
    found = PROGRESS.search(out.get("internal") or "")
    if found:
        out["progress"] = found.group(1)

    if playtimes:
        found = psxplaytime.playtime(block, frame, playtimes)
        if found:
            hours, minutes, seconds, unit = found
            out["playtime"] = f"{hours}:{minutes:02d}:{seconds:02d}"
            out["playtime_unit"] = unit

    for label, matches, reader, kind in READERS:
        if matches(frame):
            try:
                info = reader(block)
            except Exception as error:
                out["error"] = f"{label}: разбор не удался ({error})"
                return out
            if info:
                out["kind"] = kind
                out["game"] = label
                out["data"] = _jsonable(info)
                return out
    if psxff8.is_ff8(block):
        info = psxff8read.overview(block)
        if info:
            out["kind"] = "ff8"
            out["game"] = "Final Fantasy VIII"
            info["playtime_text"] = psxff8read.format_playtime(info["playtime"])
            out["data"] = _jsonable(info)
            return out
    # Для игр без своего модуля показываем простые поля прямо из шаблона.
    if templates is not None:
        generic = psxtemplate.overview(block, frame, templates, by_serial)
        if generic and (generic["fields"] or generic.get("sections")):
            out["kind"] = "generic"
            out["game"] = generic["game"]
            out["data"] = _jsonable(generic)
    return out


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


# Сравнение должно показывать то, что игрок видит в игре. Внутренние
# представления и дубли уже показанных полей только мешают: на 33 различиях
# сейвов FFT половина строк была сырыми 24-битными статами и индексами
# кортежей вроде "playtime[1]".
COMPARE_SKIP = {"raw_stats", "at_cap", "slot", "job_known", "who",
                "location_text", "playtime_text", "recruited",
                "money_verified"}

# Списки без имён: у FF7 статы персонажа - шесть чисел подряд. Имена берём
# из самого разборщика, чтобы они не разъехались с ним.
COMPARE_POSITIONS = {"stats": psxff7.STAT_NAMES}

COMPARE_LABELS = {
    "playtime": "наиграно", "funds": "казна", "gil": "гилы", "gils": "гилы",
    "gold": "золото", "level": "уровень", "exp": "опыт", "name": "имя",
    "job": "класс", "location": "локация", "date": "дата",
    "birthday": "день рождения", "units": "отряд", "party": "партия",
    "characters": "персонажи", "guardians": "Гардианы",
    "inventory": "инвентарь", "items": "предметы", "container": "сундук",
    "materia": "материя", "materia_stolen": "материя в запасе",
    "gear": "экипировка", "relics": "реликвии", "spells": "заклинания",
    "familiars": "фамильяры", "bestiary": "бестиарий", "drops": "дроп",
    "map": "карта, %", "kills": "убийства", "battles": "бои",
    "runs": "побеги", "steps": "шаги", "hp": "HP", "mp": "MP",
    "hp_max": "HP макс", "hearts": "сердца", "health": "здоровье",
    "stats": "статы", "brave": "храбрость", "faith": "вера",
    "zodiac": "зодиак", "gender": "пол", "guest": "гость",
    "character": "герой", "leader": "лидер", "trance": "транс",
    "ink_ribbons": "чернильные ленты", "limit_level": "уровень лимита",
    "weapon": "оружие", "armor": "броня", "progression": "прогресс",
    "enemy_total": "всего врагов", "checksum_ok": "сумма сходится",
    "is_monster": "монстр", "status": "состояние", "count": "количество",
    "kind": "тип", "learned": "выучено", "learning": "учится",
    "forgotten": "забыто", "total_slots": "слотов", "exists": "есть",
    "magic": "магия", "description": "подпись игры", "sp": "скорость",
    "pa": "физ. атака", "ma": "маг. атака", "ap": "AP", "stars": "звёзд",
    "total": "всего", "mastered": "освоена", "accessory": "аксессуар",
    "saves": "сохранений", "espers": "эсперы", "abilities": "способности",
    "disc": "диск", "trance": "транс",
    "percent": "процент", "learned": "выучено", "not_recruited": "не завербовано",
    "money": "деньги", "next": "до уровня", "party": "отряд",
    "materia_slots": "слоты материи", "hp_current": "HP", "mp_current": "MP",
}


def _pretty(key, value):
    """Кортеж - одной читаемой строкой, а не набором индексов."""
    if key == "playtime":
        if isinstance(value, dict):
            return value.get("shown") or value.get("as_seconds")
        if isinstance(value, (list, tuple)) and len(value) == 3:
            return "%d:%02d:%02d" % tuple(value)
    if key in ("date", "birthday") and isinstance(value, (list, tuple)) \
            and len(value) == 2:
        return f"{value[1]} {value[0]}"
    if (isinstance(value, (list, tuple)) and 2 <= len(value) <= 3
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in value)):
        return " / ".join(str(v) for v in value)
    return None


def _identity(item):
    """Чем назвать элемент списка: именем, а не порядковым номером."""
    if isinstance(item, dict):
        return item.get("name") or item.get("who")
    if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
        return item[0]
    if isinstance(item, str):
        return item
    return None


def _identities(items):
    """Имена элементов списка: берём то поле, которое лучше их различает.

    "who" и "name" у разборщиков значат разное. У FF7 и FF9 "who" -
    канонический персонаж (Cloud), а "name" игрок может переименовать.
    У FFT наоборот: "who" - тип бойца ("Male Unit"), общий сразу для
    нескольких, а настоящее имя лежит в "name".

    Поэтому поле не выбирается раз и навсегда: берём то, у которого внутри
    этого списка больше различных значений, при равенстве - "who" (он
    устойчив к переименованию). Иначе отряд FFT вырождается в "Male Unit
    #1..#4", а персонажи FF7 с именами FAIL/PASS слипаются в одного."""
    if items and all(isinstance(item, dict) for item in items):
        best, best_score = None, -1
        for field in ("who", "name"):
            values = [item.get(field) for item in items]
            if any(not value for value in values):
                continue
            if len(set(values)) > best_score:
                best, best_score = values, len(set(values))
        if best is not None:
            return best
    return [_identity(item) for item in items]


def flatten(value, prefix=""):
    """Разбор игры -> плоский словарь "что это: значение" для сравнения."""
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in COMPARE_SKIP or key.endswith("_raw"):
                continue
            label = COMPARE_LABELS.get(key, key)
            path = f"{prefix} · {label}" if prefix else label
            named = COMPARE_POSITIONS.get(key)
            if (named and isinstance(item, (list, tuple))
                    and len(item) == len(named)):
                for position, entry in zip(named, item):
                    out[f"{path} · {position}"] = entry
                continue
            shown = _pretty(key, item)
            if shown is not None:
                out[path] = shown
            else:
                out.update(flatten(item, path))
        return out

    if isinstance(value, (list, tuple)):
        # Списки сличаем по названию, а не по позиции: иначе один добавленный
        # предмет сдвигает весь список и даёт сотни ложных различий.
        #
        # Но имена бывают неуникальны: в отряде FFT у гриндившего игрока по
        # нескольку Mustadio и Agrias сразу. Одно только имя склеило бы их
        # в одну строку, и различия последнего затёрли бы предыдущих, поэтому
        # одноимённых нумеруем.
        names = _identities(list(value))
        repeated = collections.Counter(n for n in names if n is not None)
        occurrence = collections.Counter()
        for index, item in enumerate(value):
            ident = names[index]
            if ident is not None and repeated[ident] > 1:
                occurrence[ident] += 1
                ident = f"{ident} #{occurrence[ident]}"
            path = f"{prefix}: {ident}" if ident else f"{prefix}[{index}]"
            if isinstance(item, str):
                out[path] = "есть"
            elif isinstance(item, (list, tuple)) and ident:
                rest = item[1:]
                # У материи FF7 за названием слота стоит не число, а целый
                # разбор - его надо разворачивать, а не печатать словарём.
                if len(rest) == 1 and isinstance(rest[0], (dict, list, tuple)):
                    out.update(flatten(rest[0], path))
                elif len(rest) == 1:
                    out[path] = rest[0]
                else:
                    out[path] = " / ".join(str(v) for v in rest)
            elif isinstance(item, dict) and ident:
                inner = {k: v for k, v in item.items() if k not in ("name", "who")}
                # Предмет с одним лишь счётчиком не заслуживает вложенности.
                if "count" in inner and set(inner) <= {"count", "kind"}:
                    out[path] = inner["count"]
                else:
                    out.update(flatten(inner, path))
            else:
                out.update(flatten(item, path))
        return out

    out[prefix] = value
    return out


def _split_path(key):
    """'отряд: Mustadio #1 · статы · HP' -> ('отряд', 'Mustadio #1', 'статы · HP')."""
    parts = key.split(" · ")
    head = parts[0]
    if ": " not in head:
        return None, None, key
    collection, _, obj = head.partition(": ")
    return collection, obj, " · ".join(parts[1:])


def _group_diff(rows, all_keys):
    """Различия по объектам: что изменилось, а что сравнилось и совпало.

    Без этого непонятно, почему в отряде из 19 бойцов показаны двое: дифф
    молчит про совпавших, и выглядит это как потеря данных."""
    # Сколько объектов вообще сравнивалось - считаем по всем полям, а не
    # только по различающимся.
    total = collections.defaultdict(set)
    for key in all_keys:
        collection, obj, _ = _split_path(key)
        if collection:
            total[collection].add(obj)

    plain = []
    order = []
    changed = collections.defaultdict(dict)
    for row in rows:
        collection, obj, leaf = _split_path(row["field"])
        if not collection:
            plain.append({"field": leaf, "a": row["a"], "b": row["b"]})
            continue
        if collection not in changed:
            order.append(collection)
        entry = changed[collection].setdefault(obj, [])
        # Предмет инвентаря - само значение, у него нет вложенных полей.
        entry.append({"field": leaf, "a": row["a"], "b": row["b"]})

    groups = []
    for collection in order:
        objects = [{"name": obj, "rows": fields,
                    "simple": len(fields) == 1 and not fields[0]["field"]}
                   for obj, fields in changed[collection].items()]
        untouched = sorted(total[collection] - set(changed[collection]))
        groups.append({"name": collection, "total": len(total[collection]),
                       "changed": len(objects), "objects": objects,
                       "untouched": untouched})
    return groups, plain


class App:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.titles = psxid.load_titles(psxid.default_titles_path())
        self._index = None
        self.templates = psxtemplate.load()
        self.by_serial = psxtemplate.by_serial(self.templates)
        self.playtimes = psxplaytime.load()

    def resolve(self, relative):
        """Не выпускаем за корень: любой путь наружу считаем ошибкой."""
        target = os.path.abspath(os.path.join(self.root, relative.lstrip("/")))
        if target != self.root and not target.startswith(self.root + os.sep):
            raise ValueError("путь вне корневой папки")
        return target

    def browse(self, relative):
        target = self.resolve(relative)
        folders, files = [], []
        for name in sorted(os.listdir(target)):
            if name.startswith("."):
                continue
            full = os.path.join(target, name)
            rel = os.path.relpath(full, self.root)
            if os.path.isdir(full):
                folders.append({"name": name, "path": rel})
                continue
            info = {"name": name, "path": rel, "size": os.path.getsize(full),
                    "saves": None, "kind": None}
            state = psxstate.describe(full, self.titles)
            if state is not None:
                info["kind"] = "state"
                info["saves"] = 1
                info["label"] = state["title"] or state["serial"]
            else:
                # Разбор всей папки стоит десятки миллисекунд, поэтому превью
                # первого сейва отдаём сразу - иначе список выглядит пустым.
                try:
                    items = psxchoco.scan(full)
                except Exception:
                    items = []
                info["saves"] = len(items)
                if items:
                    first = describe_save(items[0], self.titles)
                    info["label"] = first["title"]
                    info["icon"] = first["icon"]
                    info["frames"] = first["frames"]
                    # Наигранное берём у самого «старшего» сейва в файле:
                    # у образа карты внутри могут лежать разные прохождения.
                    best = None
                    for item in items:
                        seconds = _seconds(item, self.playtimes)
                        if seconds and (best is None or seconds > best):
                            best = seconds
                    if best:
                        info["playtime"] = best
                        info["playtime_text"] = f"{best // 3600}:{best // 60 % 60:02d}"
            files.append(info)
        return {"path": relative.strip("/"), "folders": folders, "files": files,
                "parent": None if not relative.strip("/")
                else os.path.dirname(relative.strip("/"))}

    def index(self, rebuild=False):
        """Один проход по всей папке: каждый сейв с игрой, серийником и иконкой.

        Строится лениво и кешируется - обход коллекции на 500 файлов занимает
        секунды, повторять его на каждый поиск незачем."""
        if self._index is not None and not rebuild:
            return self._index
        rows = []
        for folder, _, names in os.walk(self.root):
            for name in sorted(names):
                if name.startswith("."):
                    continue
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, self.root)
                try:
                    items = psxchoco.scan(full)
                except Exception:
                    continue
                for slot, item in enumerate(items):
                    card = describe_save(item, self.titles)
                    rows.append({"path": rel, "slot": slot, "name": name,
                                 "title": card["title"], "serial": card["serial"],
                                 "internal": card["internal"], "icon": card["icon"],
                                 "frames": card["frames"],
                                 "blocks": card["blocks"], "region": card["region"]})
        self._index = rows
        return rows

    def compare(self, left, right):
        """Сравнивает два сейва по полям разбора; если игра разная - по общему."""
        pair = []
        for spec in (left, right):
            path, _, slot = spec.rpartition("#")
            items = psxchoco.scan(self.resolve(path or spec))
            index = int(slot) if slot.isdigit() else 0
            if index >= len(items):
                raise ValueError(f"в '{path}' нет слота {index}")
            pair.append((os.path.basename(path or spec),
                         detail(items[index], self.titles, self.templates,
                                self.by_serial, self.playtimes)))
        (name_a, a), (name_b, b) = pair
        flat_a = flatten(a.get("data", {}))
        flat_b = flatten(b.get("data", {}))
        # Сортируем по ветке, а не по всей строке: иначе собственные поля
        # бойца ("уровень") оказываются по разные стороны от вложенных
        # ("статы · HP"), и одна и та же ветка печатается дважды.
        def order(key):
            parts = key.split(" · ")
            return parts[:-1], parts[-1]

        keys = sorted(set(flat_a) | set(flat_b), key=order)
        rows = [{"field": k, "a": flat_a.get(k), "b": flat_b.get(k)}
                for k in keys if flat_a.get(k) != flat_b.get(k)]
        groups, plain = _group_diff(rows, keys)
        return {"a": {"name": name_a, "title": a["title"], "kind": a.get("kind")},
                "b": {"name": name_b, "title": b["title"], "kind": b.get("kind")},
                "same_game": a.get("kind") == b.get("kind") and a.get("kind"),
                "common": len(keys) - len(rows), "plain": plain,
                "groups": groups, "diff_total": len(rows)}

    def _card_entries(self, items):
        """'путь#слот, путь#слот' -> сейвы для сборки, в порядке выбора."""
        entries = []
        for spec in items:
            spec = spec.strip()
            if not spec:
                continue
            where, _, slot = spec.rpartition("#")
            found = psxbuild.sources(self.resolve(where or spec))
            if slot.isdigit():
                index = int(slot)
                if index >= len(found):
                    raise ValueError(f"в '{where}' нет сейва №{index}")
                found = [found[index]]
            entries += found
        if not entries:
            raise ValueError("не выбрано ни одного сейва")
        return entries

    def card_plan(self, items):
        """Что получится, без записи файла: расклад по блокам либо причина."""
        titles = self.titles
        try:
            entries = self._card_entries(items)
            _, layout, dropped = psxbuild.build(entries)
        except ValueError as error:
            return {"error": str(error)}
        for row in layout:
            row["title"] = titles.get(
                psxid.normalize_serial(row["name"][2:12]), row["name"])
        return {"rows": layout, "used": sum(r["blocks"] for r in layout),
                "free": psxid.SLOTS - sum(r["blocks"] for r in layout),
                "dropped": [{"name": n, "where": w} for n, w in dropped]}

    EXPORT_DIR = "saves/_экспорт"

    def _export_target(self, filename):
        """Путь в папке экспорта; занятое имя не перезаписываем."""
        folder = os.path.join(self.root, self.EXPORT_DIR)
        os.makedirs(folder, exist_ok=True)
        stem, extension = os.path.splitext(filename)
        candidate, number = filename, 2
        while os.path.exists(os.path.join(folder, candidate)):
            candidate = f"{stem} ({number}){extension}"
            number += 1
        return os.path.join(folder, candidate), candidate

    def convert(self, items, fmt, region=None, write=False, filename=None):
        """Переводит выбранные сейвы в формат fmt.

        Один сейв - одиночный формат либо карта из одного; несколько - только
        карта. Возвращает готовые байты и имя файла, а при write=True ещё и
        кладёт файл в папку экспорта."""
        entries = self._card_entries(items)
        if fmt in psxconvert.SINGLE:
            if len(entries) != 1:
                raise ValueError(f"формат {fmt} - для одного сейва, "
                                 f"а выбрано {len(entries)}")
            blob = psxconvert.single(entries[0], fmt, region)
            dropped = []
        elif fmt in psxconvert.CARDS:
            blob, _, dropped = psxconvert.card(entries, fmt, region)
        else:
            raise ValueError(f"неизвестный формат '{fmt}'")
        # Имя важно: DuckStation ищет карту, названную ровно как образ игры,
        # поэтому его надо уметь задать, а не только получить автоматом.
        if filename:
            filename = os.path.basename(filename.strip())
            if not filename.lower().endswith("." + fmt):
                filename += "." + fmt
        else:
            filename = psxconvert.suggest_name(entries, fmt, region)
        if not write:
            return blob, filename, None, dropped
        path, name = self._export_target(filename)
        with open(path, "wb") as fh:
            fh.write(blob)
        return blob, name, os.path.join(self.EXPORT_DIR, name), dropped

    def split(self, path, fmt="mcs", region=None):
        """Разбирает карту на отдельные файлы.

        Каждый сейв кладётся своим файлом в saves/_экспорт/<имя карты>/,
        названный по имени сейва - так его ждёт и PS3, и любой редактор."""
        if fmt not in psxconvert.SINGLE:
            raise ValueError(f"для отдельных файлов нужен формат "
                             f"{', '.join(psxconvert.SINGLE)}, а не '{fmt}'")
        entries = psxbuild.sources(self.resolve(path))
        if not entries:
            raise ValueError("в этом файле нет сейвов")
        stem = os.path.splitext(os.path.basename(path))[0]
        folder = os.path.join(self.root, self.EXPORT_DIR, stem)
        os.makedirs(folder, exist_ok=True)
        out = []
        for entry in entries:
            blob = psxconvert.single(entry, fmt, region)
            name = psxconvert.suggest_name([entry], fmt, region)
            target = os.path.join(folder, name)
            base, extension = os.path.splitext(target)
            number = 2
            while os.path.exists(target):
                target = f"{base} ({number}){extension}"
                number += 1
            with open(target, "wb") as fh:
                fh.write(blob)
            out.append({"name": os.path.basename(target),
                        "title": self.titles.get(
                            psxid.normalize_serial(
                                psxbuild._name_of(entry["name"])[2:12]), ""),
                        "size": len(blob),
                        "path": os.path.relpath(target, self.root)})
        return {"folder": os.path.join(self.EXPORT_DIR, stem), "files": out}

    def card_bytes(self, items, suffix):
        """Готовый образ карты и имя файла для скачивания."""
        suffix = suffix if suffix in (".mcr", ".gme", ".vmp") else ".mcr"
        card, layout, _ = psxbuild.build(self._card_entries(items))
        blob = psxbuild.WRAPPERS.get(suffix, lambda c: c)(card)
        return blob, f"card-{len(layout)}-saves{suffix}"

    # --- консоли по FTP ---------------------------------------------------
    DOWNLOAD_DIR = "saves/_с консоли"

    def consoles(self):
        """Профили без паролей - наружу их отдавать незачем."""
        return [{"name": name, **{k: v for k, v in spec.items()
                                  if k != "password"},
                 "has_password": bool(spec.get("password"))}
                for name, spec in sorted(psxftp.load().items())]

    def console_save(self, spec):
        name = (spec.get("name") or "").strip()
        if not name:
            raise ValueError("у профиля должно быть название")
        if not (spec.get("host") or "").strip():
            raise ValueError("нужен адрес консоли")
        profiles = psxftp.load()
        kept = profiles.get(name, {})
        profiles[name] = {
            "kind": spec.get("kind") or "ps3",
            "host": spec["host"].strip(),
            "port": int(spec.get("port") or 21),
            "user": spec.get("user") or "anonymous",
            # Пустой пароль в форме means «не менять», иначе его нельзя было бы
            # не перевводить при каждой правке адреса.
            "password": spec.get("password") or kept.get("password", ""),
            "path": spec.get("path") or "/",
        }
        psxftp.save(profiles)
        return self.consoles()

    def console_delete(self, name):
        profiles = psxftp.load()
        profiles.pop(name, None)
        psxftp.save(profiles)
        return self.consoles()

    def _profile(self, name):
        profiles = psxftp.load()
        if name not in profiles:
            raise ValueError(f"консоль '{name}' не настроена")
        return profiles[name]

    def console_list(self, name, path):
        profile = self._profile(name)
        ftp = psxftp.connect(profile)
        try:
            path = path or profile.get("path") or "/"
            entries = psxftp.listdir(ftp, path)
        finally:
            ftp.close()
        rows = [{"name": n, "size": size, "dir": is_dir} for n, size, is_dir in entries]
        rows.sort(key=lambda r: (not r["dir"], r["name"].lower()))
        parent = posixpath.dirname(path.rstrip("/")) or "/"
        return {"path": path, "parent": None if path in ("/", "") else parent,
                "entries": rows}

    def console_scan(self, name, path):
        profile = self._profile(name)
        ftp = psxftp.connect(profile)
        try:
            found = psxftp.walk_saves(ftp, path or profile.get("path") or "/")
        finally:
            ftp.close()
        return {"found": [{"path": p, "size": size} for p, size in found]}

    def console_get(self, name, paths):
        """Качает файлы с консоли в saves/_с консоли/<профиль>."""
        profile = self._profile(name)
        folder = os.path.join(self.root, self.DOWNLOAD_DIR, name)
        os.makedirs(folder, exist_ok=True)
        ftp = psxftp.connect(profile)
        out = []
        try:
            for remote in paths:
                remote = remote.strip()
                if not remote:
                    continue
                data = psxftp.download(ftp, remote)
                target = os.path.join(folder, posixpath.basename(remote))
                stem, extension = os.path.splitext(target)
                number = 2
                while os.path.exists(target):
                    target = f"{stem} ({number}){extension}"
                    number += 1
                with open(target, "wb") as fh:
                    fh.write(data)
                out.append({"remote": remote, "size": len(data),
                            "path": os.path.relpath(target, self.root)})
        finally:
            ftp.close()
        return {"saved": out}

    def console_put(self, name, local, remote):
        """Отправляет один файл из коллекции на консоль."""
        profile = self._profile(name)
        source = self.resolve(local)
        if os.path.isdir(source):
            raise ValueError("на консоль отправляется файл, а не папка")
        if not os.path.exists(source):
            raise ValueError(f"нет файла '{local}'")
        with open(source, "rb") as fh:
            data = fh.read()
        if not remote:
            raise ValueError("не указан путь на консоли")
        if remote.endswith("/"):
            remote += os.path.basename(source)
        ftp = psxftp.connect(profile)
        try:
            # PS3 ведёт свой указатель сохранений: новый файл, положенный
            # по FTP, консоль может просто не увидеть, пока не переиндексирует
            # или пока карту не смонтирует игра. Замена уже известного файла
            # такой беды не создаёт, поэтому предупреждаем именно про новый.
            before = psxftp.exists(ftp, remote)
            sent = psxftp.upload(ftp, remote, data)
        finally:
            ftp.close()
        return {"remote": remote, "size": sent, "replaced": before is not None,
                "was": before}

    def open_file(self, relative):
        target = self.resolve(relative)
        state = psxstate.describe(target, self.titles)
        if state is not None:
            shot = None
            if state["screenshot"]:
                rows = psxstate.read_screenshot(state["screenshot"])
                if rows:
                    png = psxid.write_png(psxstate.PIC_WIDTH, psxstate.PIC_HEIGHT, rows)
                    shot = "data:image/png;base64," + base64.b64encode(png).decode()
            return {"kind": "state", "name": os.path.basename(target),
                    "state": {**state, "screenshot": shot}}
        saves = [detail(item, self.titles, self.templates, self.by_serial,
                        self.playtimes) for item in psxchoco.scan(target)]
        for index, item in enumerate(psxchoco.scan(target)):
            saves[index]["where"] = item["where"]
        return {"kind": "saves", "name": os.path.basename(target), "saves": saves}


class Handler(BaseHTTPRequestHandler):
    app = None

    def log_message(self, *args):
        pass

    def _send(self, code, body, mime):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        route = posixpath.normpath(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        arg = query.get("path", [""])[0]
        try:
            if route == "/":
                with open(PAGE, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if route == "/api/browse":
                payload = self.app.browse(arg)
            elif route == "/api/open":
                payload = self.app.open_file(arg)
            elif route == "/api/index":
                payload = {"saves": self.app.index("rebuild" in query)}
            elif route == "/api/cardplan":
                payload = self.app.card_plan(query.get("items", [""])[0].split(","))
            elif route == "/api/consoles":
                payload = {"consoles": self.app.consoles()}
            elif route == "/api/console/save":
                payload = {"consoles": self.app.console_save(
                    {k: v[0] for k, v in query.items()})}
            elif route == "/api/console/delete":
                payload = {"consoles": self.app.console_delete(
                    query.get("name", [""])[0])}
            elif route == "/api/console/list":
                payload = self.app.console_list(query.get("name", [""])[0],
                                                query.get("path", [""])[0])
            elif route == "/api/console/scan":
                payload = self.app.console_scan(query.get("name", [""])[0],
                                                query.get("path", [""])[0])
            elif route == "/api/console/get":
                payload = self.app.console_get(
                    query.get("name", [""])[0],
                    query.get("paths", [""])[0].split("|"))
            elif route == "/api/console/put":
                payload = self.app.console_put(query.get("name", [""])[0],
                                               query.get("local", [""])[0],
                                               query.get("remote", [""])[0])
            elif route == "/api/split":
                payload = self.app.split(query.get("path", [""])[0],
                                         query.get("format", ["mcs"])[0],
                                         query.get("region", [""])[0] or None)
            elif route == "/api/export":
                items = query.get("items", [""])[0].split(",")
                fmt = query.get("format", ["mcr"])[0]
                region = query.get("region", [""])[0] or None
                blob, name, where, dropped = self.app.convert(
                    items, fmt, region, write=True,
                    filename=query.get("name", [""])[0])
                payload = {"file": name, "path": where, "size": len(blob),
                           "dropped": [{"name": n} for n, _ in dropped]}
            elif route == "/api/card":
                items = query.get("items", [""])[0].split(",")
                suffix = query.get("format", [".mcr"])[0]
                blob, filename = self.app.card_bytes(items, suffix)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)
                return
            elif route == "/api/compare":
                payload = self.app.compare(query.get("a", [""])[0],
                                           query.get("b", [""])[0])
            else:
                return self._send(404, b"not found", "text/plain")
        except Exception as error:
            payload = {"error": str(error)}
        body = json.dumps(payload, ensure_ascii=False).encode()
        self._send(200, body, "application/json; charset=utf-8")


def main():
    parser = argparse.ArgumentParser(description="Просмотрщик сейвов PS1")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    Handler.app = App(args.root)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"корень: {Handler.app.root}")
    print(f"открыто: {url}   (Ctrl+C чтобы остановить)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")


if __name__ == "__main__":
    main()
