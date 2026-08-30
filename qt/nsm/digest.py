"""Разбор к тому виду, в каком его показывает панель справа.

Повторяет `swift/Sources/MemCardApp/Model/Digest.swift`: те же поля, те
же подписи, тот же порядок. Каждая игра устроена по-своему, но показать
её нужно одинаково - сводка сверху, состав отряда с числами и
экипировкой, и списки: инвентарь, магия, реликвии, кто что собрал.
"""

from dataclasses import dataclass, field


@dataclass
class Field:
    label: str
    value: str = ""


@dataclass
class Member:
    """Боец, персонаж, фамильяр - всё, что показывается строкой с числами."""
    name: str
    role: str = ""
    level: str = ""
    stats: list = field(default_factory=list)
    gear: list = field(default_factory=list)
    extra: str = ""


@dataclass
class Section:
    title: str
    items: list = field(default_factory=list)
    note: str = ""


@dataclass
class Digest:
    game: str
    playtime: int | None = None
    fields: list = field(default_factory=list)
    members: list = field(default_factory=list)
    members_title: str = ""
    sections: list = field(default_factory=list)


def clock(parts):
    if not parts or len(parts) < 3:
        return "—"
    return f"{parts[0]}:{parts[1]:02d}:{parts[2]:02d}"


def total(parts):
    if not parts or len(parts) < 3:
        return None
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def number(value):
    """Разряды узким пробелом - так длинные числа читаются."""
    text = str(value)
    out = []
    for index, char in enumerate(reversed(text)):
        if index and index % 3 == 0:
            out.append(" ")
        out.append(char)
    return "".join(reversed(out))


def pairs(rows):
    """Пары «название, количество» из списка списков."""
    out = []
    for row in rows or []:
        if isinstance(row, (list, tuple)) and row:
            out.append(Field(str(row[0]), str(row[1]) if len(row) > 1 else ""))
        elif isinstance(row, dict):
            out.append(Field(str(row.get("name", "?")),
                             str(row.get("count", ""))))
        else:
            out.append(Field(str(row)))
    return out


def gear_names(gear):
    """Экипировка приходит парами «слот, предмет» - берём предмет."""
    out = []
    for row in gear or []:
        if isinstance(row, (list, tuple)) and len(row) > 1:
            out.append(str(row[1]))
        elif isinstance(row, str):
            out.append(row)
    return out


# --- по играм ------------------------------------------------------------

def from_fft(got):
    labels = {"hp": "HP", "mp": "MP", "sp": "скорость",
              "pa": "физ. атака", "ma": "маг. атака"}
    order = ("hp", "mp", "sp", "pa", "ma")
    members = []
    for unit in got.get("units", []):
        extra = [unit.get("who", ""), unit.get("gender", ""), unit.get("zodiac", "")]
        if unit.get("guest"):
            extra.append("гость")
        if unit.get("status"):
            extra.append(unit["status"])
        stats = got and unit.get("stats") or {}
        numbers = [Field(labels[key], str(stats[key]))
                   for key in order if key in stats]
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("job", ""),
            level=str(unit.get("level", "")),
            stats=numbers + [Field("храбрость", str(unit.get("brave", ""))),
                             Field("вера", str(unit.get("faith", "")))],
            gear=gear_names(unit.get("gear")),
            extra=" · ".join(x for x in extra if x)))
    inventory = got.get("inventory") or []
    return Digest(
        game="Final Fantasy Tactics",
        playtime=total(got.get("playtime")),
        fields=[
            Field("Герой", got.get("name", "")),
            Field("Класс", got.get("job", "")),
            Field("Уровень", str(got.get("level", ""))),
            Field("Наиграно", clock(got.get("playtime"))),
            Field("Казна", number(got.get("funds", 0)) + " гил"),
            Field("Место", str(got.get("location", ""))),
            Field("Дата в игре", " ".join(str(x) for x in (got.get("date") or ()))),
            Field("День рождения",
                  " ".join(str(x) for x in (got.get("birthday") or ()))),
        ],
        members=members, members_title="Отряд",
        sections=[Section("Инвентарь", pairs(inventory),
                          f"{len(inventory)} позиций")])


def from_ff9(got):
    fields = [Field("Наиграно", clock(got.get("playtime"))),
              Field("Гилы", number(got.get("gil", 0))),
              Field("Локация", str(got.get("location", "")))]
    if got.get("disc") is not None:
        fields.insert(0, Field("Диск", str(got["disc"])))
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field("опыт", number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=f"транс {unit['trance']}" if unit.get("trance") else ""))
    inventory = got.get("inventory") or []
    return Digest(game="Final Fantasy IX", playtime=total(got.get("playtime")),
                  fields=fields, members=members, members_title="Партия",
                  sections=[Section("Инвентарь", pairs(inventory),
                                    f"{len(inventory)} позиций")])


def from_ff6(got):
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        learned = sum(1 for value in (unit.get("magic") or {}).values()
                      if value >= 100) if isinstance(unit.get("magic"), dict) else 0
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field("опыт", number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra="" if not learned else f"магия {learned}"))
    sections = [Section("Инвентарь", pairs(got.get("inventory")),
                        f"{len(got.get('inventory') or [])} позиций")]
    if got.get("espers"):
        sections.append(Section("Эсперы", pairs(got["espers"])))
    # Число, а не список: движок отдаёт сколько персонажей не найдено.
    if got.get("not_recruited"):
        sections.append(Section("Не завербовано",
                                [Field("персонажей", str(got["not_recruited"]))]))
    return Digest(
        game="Final Fantasy VI", playtime=total(got.get("playtime")),
        fields=[Field("Наиграно", clock(got.get("playtime"))),
                Field("Гилы", number(got.get("gil", 0))),
                Field("Шагов", number(got.get("steps", 0))),
                Field("Сохранений", str(got.get("saves", ""))),
                Field("Локация", str(got.get("location", "")))],
        members=members, members_title="Отряд", sections=sections)


def from_ff5(got):
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("job", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field("опыт", number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=f"уровень работы {unit.get('job_level', 0)}"))
    return Digest(
        game="Final Fantasy V", playtime=total(got.get("playtime")),
        fields=[Field("Наиграно", clock(got.get("playtime"))),
                Field("Гил", number(got.get("money", 0))),
                Field("Убито", number(got.get("kills", 0))),
                Field("Боёв", number(got.get("battles", 0))),
                Field("Сохранений", str(got.get("saves", ""))),
                Field("Мир", str(got.get("world", ""))),
                Field("Карта", str(got.get("map", "")))],
        members=members, members_title="Отряд",
        sections=[Section("Инвентарь", pairs(got.get("inventory")),
                          f"{len(got.get('inventory') or [])} позиций")])


def from_re1(got):
    return Digest(
        game="Resident Evil", playtime=got.get("playtime_raw"),
        fields=[Field("Герой", str(got.get("character", ""))),
                Field("Здоровье", str(got.get("health", ""))),
                Field("Чернильные ленты", str(got.get("ink_ribbons", ""))),
                Field("Локация", str(got.get("location", "")))],
        sections=[Section("При себе", pairs(got.get("inventory"))),
                  Section("В сундуке", pairs(got.get("container")))])


def from_pe2(got):
    return Digest(
        game="Parasite Eve II",
        playtime=total(got.get("playtime")),
        fields=[Field("Наиграно", clock(got.get("playtime"))),
                Field("Второе число", str(got.get("mark", ""))),
                Field("Предметов при себе", str(got.get("items", ""))),
                Field("В хранилище", str(got.get("stored", ""))),
                Field("Записей в блоке", str(got.get("banks", "")))])


def from_crash2(got):
    return Digest(
        game="Crash Bandicoot 2",
        fields=[Field("Игрок", got.get("name") or "—"),
                Field("Уровень", str(got.get("level", ""))),
                Field("Жизней", str(got.get("lives", ""))),
                Field("Фруктов", number(got.get("wumpa", 0))),
                Field("Аку-Аку", str(got.get("aku_aku", ""))),
                Field("Кристаллов", str(got.get("crystals", ""))),
                Field("Самоцветов", str(got.get("gems", ""))),
                Field("Пройдено уровней", str(got.get("progress", ""))),
                Field("Секретов", str(got.get("secrets", "")))])


def from_chronicles(got):
    return Digest(
        game="Castlevania Chronicles",
        fields=[Field("Игрок", got.get("name", "")),
                Field("Стейдж", f"{got.get('stage', 0):02d}"),
                Field("Уровень", str(got.get("level", ""))),
                Field("Второе число", f"{got.get('counter', 0):02d}"),
                Field("Сохранён", got.get("saved", ""))])


AREAS = ("Люди", "Звери", "Нежить", "Призраки", "Драконы", "Демоны")
KINDS = (("weapons", "Оружие"), ("shields", "Щиты"), ("blades", "Клинки"),
         ("grips", "Рукояти"), ("armor", "Броня"), ("gems", "Самоцветы"),
         ("misc", "Прочее"))
LEARNED = (("breakArt", "Приёмы оружия"), ("spell", "Заклинания"),
           ("ability", "Способности"))


def from_vagrant(got):
    sections = []
    if got.get("weapons"):
        sections.append(Section("Оружие при себе",
                                [Field(x) for x in got["weapons"]]))
    if got.get("stored_weapons"):
        sections.append(Section("Оружие в сундуке",
                                [Field(x) for x in got["stored_weapons"]]))
    for where, title in (("carried_items", "При себе"),
                         ("stored_items", "В сундуке")):
        for kind, name in KINDS:
            rows = (got.get(where) or {}).get(kind)
            if rows:
                sections.append(Section(
                    f"{title} — {name}",
                    [Field(item, str(count) if count > 1 else "")
                     for item, count in rows]))
    for key, title in LEARNED:
        rows = (got.get("learned") or {}).get(key)
        if rows:
            sections.append(Section(title, [Field(x) for x in rows],
                                    str(len(rows))))
    if got.get("unopened"):
        rows = sorted(got["unopened"].items())
        sections.append(Section("Комнаты не открыты",
                                [Field(name, str(count)) for name, count in rows],
                                f"всего {sum(got['unopened'].values())}"))
    kills = got.get("kills") or []
    sections.append(Section("Убито",
                            [Field(AREAS[i], number(kills[i]))
                             for i in range(min(len(AREAS), len(kills)))],
                            f"всего {number(sum(kills))}"))
    hp, mp = got.get("hp", [0, 0]), got.get("mp", [0, 0])
    return Digest(
        game="Vagrant Story", playtime=total(got.get("playtime")),
        fields=[
            Field("Наиграно", clock(got.get("playtime"))),
            Field("HP", f"{hp[0]}/{hp[1]}"),
            Field("MP", f"{mp[0]}/{mp[1]}"),
            Field("Карта пройдена", f"{got.get('map_completion', 0)} %"),
            Field("Комнат открыто",
                  f"{got.get('rooms', 0)} из {got.get('rooms_total', 361)}"),
            Field("Комнат осталось",
                  str(max(0, got.get("rooms_total", 361) - got.get("rooms", 0)))),
            Field("Приёмов изучено", f"{got.get('arts_learned', 0)} из 48"),
            Field("Длиннейшая цепь", str(got.get("max_chain", ""))),
            Field("Лечений", str(got.get("heals", ""))),
            Field("Сундуков открыто", str(got.get("chests", ""))),
            Field("Действий изучено", str(got.get("actions", ""))),
            Field("Пройдено раз", str(got.get("clear_count", ""))),
            Field("Сохранений всего", str(got.get("saves_total", ""))),
            Field("Сохранений в игре", str(got.get("saves_game", ""))),
            Field("Локация", str(got.get("location", ""))),
        ],
        sections=sections)


def from_ff7(got):
    members = []
    for unit in got.get("party", []) or got.get("characters", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}")],
            gear=gear_names(unit.get("gear"))))
    return Digest(
        game="Final Fantasy VII", playtime=total(got.get("playtime")),
        fields=[Field("Наиграно", clock(got.get("playtime"))),
                Field("Гилы", number(got.get("gil", 0))),
                Field("Локация", str(got.get("location", ""))),
                Field("Боёв", str(got.get("battles", ""))),
                Field("Побегов", str(got.get("escapes", "")))],
        members=members, members_title="Партия",
        sections=[Section("Инвентарь", pairs(got.get("inventory")),
                          f"{len(got.get('inventory') or [])} позиций")])


def from_sotn(got):
    sections = []
    for key, title in (("relics", "Реликвии"), ("inventory", "Инвентарь"),
                       ("spells", "Заклинания"), ("familiars", "Фамильяры")):
        if got.get(key):
            sections.append(Section(title, pairs(got[key])))
    return Digest(
        game="Castlevania: Symphony of the Night",
        playtime=total(got.get("playtime")),
        fields=[Field("Наиграно", clock(got.get("playtime"))),
                Field("Уровень", str(got.get("level", ""))),
                Field("Опыт", number(got.get("experience", 0))),
                Field("Золото", number(got.get("gold", 0))),
                Field("Карта пройдена", f"{got.get('map', 0)} %"),
                Field("Убийств", number(got.get("kills", 0)))],
        sections=sections)


def from_ff8(got):
    playtime = got.get("playtime") or {}
    chosen = playtime.get("matches") or "as_seconds"
    shown = playtime.get(chosen) or {}
    parts = [shown.get("hours", 0), shown.get("minutes", 0), shown.get("seconds", 0)]
    members = []
    for unit in got.get("characters", []):
        if not unit.get("exists", True):
            continue
        # HP у FF8 - одно число, а не пара: максимум игра считает на лету.
        learned = len(unit.get("magic") or [])
        members.append(Member(
            name=unit.get("name", ""),
            role=unit.get("weapon", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", str(unit.get("hp", ""))),
                   Field("опыт", number(unit.get("exp", 0))),
                   Field("убийств", str(unit.get("kills", "")))],
            gear=[],
            extra=f"магия {learned}" if learned else ""))
    sections = []
    if got.get("guardians"):
        sections.append(Section(
            "Гардианы",
            [Field(gf.get("name", "?"),
                   f"{len(gf.get('learned') or [])} способностей")
             for gf in got["guardians"]],
            f"{len(got['guardians'])} из 16"))
    if got.get("inventory"):
        sections.append(Section("Инвентарь", pairs(got["inventory"]),
                                f"{len(got['inventory'])} позиций"))
    return Digest(
        game="Final Fantasy VIII", playtime=total(parts),
        fields=[Field("Наиграно", clock(parts)),
                Field("Гилы", number(got.get("gil", 0))),
                Field("Шагов", number(got.get("steps", 0))),
                Field("Боёв", number(got.get("battles", 0)))],
        members=members, members_title="Персонажи", sections=sections)


BUILDERS = {
    "fft": from_fft, "ff9": from_ff9, "ff8": from_ff8, "ff7": from_ff7,
    "ff6": from_ff6, "ff5": from_ff5, "re1": from_re1, "sotn": from_sotn,
    "vagrant": from_vagrant, "pe2": from_pe2, "crash2": from_crash2,
    "chronicles": from_chronicles,
}


def build(detail):
    """Из разбора движка - в то, что показывает панель."""
    kind, data = detail.get("kind"), detail.get("data") or {}
    if kind in BUILDERS:
        return BUILDERS[kind](data)
    if kind == "generic":
        # Игры без своего разборщика - общий разбор по шаблону.
        return Digest(
            game=data.get("game", detail.get("game", "")),
            fields=[Field(row.get("name", "?"), str(row.get("value", "")))
                    for row in data.get("fields", [])],
            sections=[Section(part.get("name", "?"),
                              [Field(x) for x in part.get("set", [])],
                              f"{len(part.get('set', []))} из {part.get('total', 0)}")
                      for part in data.get("sections", [])])
    return None
