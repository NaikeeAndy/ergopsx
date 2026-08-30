"""Разбор к тому виду, в каком его показывает панель справа.

Повторяет `swift/Sources/MemCardApp/Model/Digest.swift`: те же поля, те
же подписи, тот же порядок. Каждая игра устроена по-своему, но показать
её нужно одинаково - сводка сверху, состав отряда с числами и
экипировкой, и списки: инвентарь, магия, реликвии, кто что собрал.
"""

from . import lang
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
    labels = {"hp": "HP", "mp": "MP", "sp": lang.t("скорость", "speed"),
              "pa": lang.t("физ. атака", "p.atk"), "ma": lang.t("маг. атака", "m.atk")}
    order = ("hp", "mp", "sp", "pa", "ma")
    members = []
    for unit in got.get("units", []):
        extra = [unit.get("who", ""), unit.get("gender", ""), unit.get("zodiac", "")]
        if unit.get("guest"):
            extra.append(lang.t("гость", "guest"))
        if unit.get("status"):
            extra.append(unit["status"])
        stats = got and unit.get("stats") or {}
        numbers = [Field(labels[key], str(stats[key]))
                   for key in order if key in stats]
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("job", ""),
            level=str(unit.get("level", "")),
            stats=numbers + [Field(lang.t("храбрость", "brave"), str(unit.get("brave", ""))),
                             Field(lang.t("вера", "faith"), str(unit.get("faith", "")))],
            gear=gear_names(unit.get("gear")),
            extra=" · ".join(x for x in extra if x)))
    inventory = got.get("inventory") or []
    return Digest(
        game="Final Fantasy Tactics",
        playtime=total(got.get("playtime")),
        fields=[
            Field(lang.t("Герой", "Hero"), got.get("name", "")),
            Field(lang.t("Класс", "Class"), got.get("job", "")),
            Field(lang.t("Уровень", "Level"), str(got.get("level", ""))),
            Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
            Field(lang.t("Казна", "Funds"), number(got.get("funds", 0)) + lang.t(" гил", " gil")),
            Field(lang.t("Место", "Place"), str(got.get("location", ""))),
            Field(lang.t("Дата в игре", "In-game date"), " ".join(str(x) for x in (got.get("date") or ()))),
            Field(lang.t("День рождения", "Birthday"),
                  " ".join(str(x) for x in (got.get("birthday") or ()))),
        ],
        members=members, members_title=lang.t("Отряд", "Party"),
        sections=[Section(lang.t("Инвентарь", "Inventory"), pairs(inventory),
                          lang.t(f"{len(inventory)} позиций", f"{len(inventory)} entries"))])


def from_ff9(got):
    fields = [Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
              Field(lang.t("Гилы", "Gil"), number(got.get("gil", 0))),
              Field(lang.t("Локация", "Location"), str(got.get("location", "")))]
    if got.get("disc") is not None:
        fields.insert(0, Field(lang.t("Диск", "Disc"), str(got["disc"])))
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field(lang.t("опыт", "exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=lang.t(f"транс {unit['trance']}", f"trance {unit['trance']}") if unit.get("trance") else ""))
    inventory = got.get("inventory") or []
    return Digest(game="Final Fantasy IX", playtime=total(got.get("playtime")),
                  fields=fields, members=members, members_title=lang.t("Партия", "Party"),
                  sections=[Section(lang.t("Инвентарь", "Inventory"), pairs(inventory),
                                    lang.t(f"{len(inventory)} позиций", f"{len(inventory)} entries"))])


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
                   Field(lang.t("опыт", "exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra="" if not learned else lang.t(f"магия {learned}", f"magic {learned}")))
    sections = [Section(lang.t("Инвентарь", "Inventory"), pairs(got.get("inventory")),
                        lang.t(f"{len(got.get('inventory') or [])} позиций", f"{len(got.get('inventory') or [])} entries"))]
    if got.get("espers"):
        sections.append(Section(lang.t("Эсперы", "Espers"), pairs(got["espers"])))
    # Число, а не список: движок отдаёт сколько персонажей не найдено.
    if got.get("not_recruited"):
        sections.append(Section(lang.t("Не завербовано", "Not recruited"),
                                [Field(lang.t("персонажей", "characters"), str(got["not_recruited"]))]))
    return Digest(
        game="Final Fantasy VI", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Гилы", "Gil"), number(got.get("gil", 0))),
                Field(lang.t("Шагов", "Steps"), number(got.get("steps", 0))),
                Field(lang.t("Сохранений", "Saves"), str(got.get("saves", ""))),
                Field(lang.t("Локация", "Location"), str(got.get("location", "")))],
        members=members, members_title=lang.t("Отряд", "Party"), sections=sections)


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
                   Field(lang.t("опыт", "exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=lang.t(f"уровень работы {unit.get('job_level', 0)}", f"job level {unit.get('job_level', 0)}")))
    return Digest(
        game="Final Fantasy V", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Гил", "Gil"), number(got.get("money", 0))),
                Field(lang.t("Убито", "Killed"), number(got.get("kills", 0))),
                Field(lang.t("Боёв", "Battles"), number(got.get("battles", 0))),
                Field(lang.t("Сохранений", "Saves"), str(got.get("saves", ""))),
                Field(lang.t("Мир", "World"), str(got.get("world", ""))),
                Field(lang.t("Карта", "Map"), str(got.get("map", "")))],
        members=members, members_title=lang.t("Отряд", "Party"),
        sections=[Section(lang.t("Инвентарь", "Inventory"), pairs(got.get("inventory")),
                          lang.t(f"{len(got.get('inventory') or [])} позиций", f"{len(got.get('inventory') or [])} entries"))])


def from_re1(got):
    return Digest(
        game="Resident Evil", playtime=got.get("playtime_raw"),
        fields=[Field(lang.t("Герой", "Hero"), str(got.get("character", ""))),
                Field(lang.t("Здоровье", "Health"), str(got.get("health", ""))),
                Field(lang.t("Чернильные ленты", "Ink ribbons"), str(got.get("ink_ribbons", ""))),
                Field(lang.t("Локация", "Location"), str(got.get("location", "")))],
        sections=[Section(lang.t("При себе", "Carried"), pairs(got.get("inventory"))),
                  Section(lang.t("В сундуке", "In container"), pairs(got.get("container")))])


def from_pe2(got):
    return Digest(
        game="Parasite Eve II",
        playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Второе число", "Second number"), str(got.get("mark", ""))),
                Field(lang.t("Предметов при себе", "Items carried"), str(got.get("items", ""))),
                Field(lang.t("В хранилище", "In storage"), str(got.get("stored", ""))),
                Field(lang.t("Записей в блоке", "Records in block"), str(got.get("banks", "")))])


def from_crash2(got):
    return Digest(
        game="Crash Bandicoot 2",
        fields=[Field(lang.t("Игрок", "Player"), got.get("name") or "—"),
                Field(lang.t("Уровень", "Level"), str(got.get("level", ""))),
                Field(lang.t("Жизней", "Lives"), str(got.get("lives", ""))),
                Field(lang.t("Фруктов", "Fruit"), number(got.get("wumpa", 0))),
                Field(lang.t("Аку-Аку", "Aku Aku"), str(got.get("aku_aku", ""))),
                Field(lang.t("Кристаллов", "Crystals"), str(got.get("crystals", ""))),
                Field(lang.t("Самоцветов", "Gems"), str(got.get("gems", ""))),
                Field(lang.t("Пройдено уровней", "Levels cleared"), str(got.get("progress", ""))),
                Field(lang.t("Секретов", "Secrets"), str(got.get("secrets", "")))])


def from_chronicles(got):
    return Digest(
        game="Castlevania Chronicles",
        fields=[Field(lang.t("Игрок", "Player"), got.get("name", "")),
                Field(lang.t("Стейдж", "Stage"), f"{got.get('stage', 0):02d}"),
                Field(lang.t("Уровень", "Level"), str(got.get("level", ""))),
                Field(lang.t("Второе число", "Second number"), f"{got.get('counter', 0):02d}"),
                Field(lang.t("Сохранён", "Saved"), got.get("saved", ""))])


AREAS = (lang.t("Люди", "Humans"), lang.t("Звери", "Beasts"), lang.t("Нежить", "Undead"), lang.t("Призраки", "Phantoms"), lang.t("Драконы", "Dragons"), lang.t("Демоны", "Evils"))
KINDS = (("weapons", lang.t("Оружие", "Weapons")), ("shields", lang.t("Щиты", "Shields")), ("blades", lang.t("Клинки", "Blades")),
         ("grips", lang.t("Рукояти", "Grips")), ("armor", lang.t("Броня", "Armor")), ("gems", lang.t("Самоцветы", "Gems")),
         ("misc", lang.t("Прочее", "Other")))
LEARNED = (("breakArt", lang.t("Приёмы оружия", "Break Arts")), ("spell", lang.t("Заклинания", "Spells")),
           ("ability", lang.t("Способности", "Abilities")))


def from_vagrant(got):
    sections = []
    if got.get("weapons"):
        sections.append(Section(lang.t("Оружие при себе", "Weapons carried"),
                                [Field(x) for x in got["weapons"]]))
    if got.get("stored_weapons"):
        sections.append(Section(lang.t("Оружие в сундуке", "Weapons in container"),
                                [Field(x) for x in got["stored_weapons"]]))
    for where, title in (("carried_items", lang.t("При себе", "Carried")),
                         ("stored_items", lang.t("В сундуке", "In container"))):
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
        sections.append(Section(lang.t("Комнаты не открыты", "Rooms not found"),
                                [Field(name, str(count)) for name, count in rows],
                                lang.t(f"всего {sum(got['unopened'].values())}", f"{sum(got['unopened'].values())} total")))
    kills = got.get("kills") or []
    sections.append(Section(lang.t("Убито", "Killed"),
                            [Field(AREAS[i], number(kills[i]))
                             for i in range(min(len(AREAS), len(kills)))],
                            lang.t(f"всего {number(sum(kills))}", f"{number(sum(kills))} total")))
    hp, mp = got.get("hp", [0, 0]), got.get("mp", [0, 0])
    return Digest(
        game="Vagrant Story", playtime=total(got.get("playtime")),
        fields=[
            Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
            Field("HP", f"{hp[0]}/{hp[1]}"),
            Field("MP", f"{mp[0]}/{mp[1]}"),
            Field(lang.t("Карта пройдена", "Map explored"), f"{got.get('map_completion', 0)} %"),
            Field(lang.t("Комнат открыто", "Rooms found"),
                  lang.t(f"{got.get('rooms', 0)} из {got.get('rooms_total', 361)}", f"{got.get('rooms', 0)} of {got.get('rooms_total', 361)}")),
            Field(lang.t("Комнат осталось", "Rooms left"),
                  str(max(0, got.get("rooms_total", 361) - got.get("rooms", 0)))),
            Field(lang.t("Приёмов изучено", "Arts learned"), lang.t(f"{got.get('arts_learned', 0)} из 48", f"{got.get('arts_learned', 0)} of 48")),
            Field(lang.t("Длиннейшая цепь", "Longest chain"), str(got.get("max_chain", ""))),
            Field(lang.t("Лечений", "Heals"), str(got.get("heals", ""))),
            Field(lang.t("Сундуков открыто", "Chests opened"), str(got.get("chests", ""))),
            Field(lang.t("Действий изучено", "Actions learned"), str(got.get("actions", ""))),
            Field(lang.t("Пройдено раз", "Times cleared"), str(got.get("clear_count", ""))),
            Field(lang.t("Сохранений всего", "Saves total"), str(got.get("saves_total", ""))),
            Field(lang.t("Сохранений в игре", "Saves this run"), str(got.get("saves_game", ""))),
            Field(lang.t("Локация", "Location"), str(got.get("location", ""))),
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
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Гилы", "Gil"), number(got.get("gil", 0))),
                Field(lang.t("Локация", "Location"), str(got.get("location", ""))),
                Field(lang.t("Боёв", "Battles"), str(got.get("battles", ""))),
                Field(lang.t("Побегов", "Escapes"), str(got.get("escapes", "")))],
        members=members, members_title=lang.t("Партия", "Party"),
        sections=[Section(lang.t("Инвентарь", "Inventory"), pairs(got.get("inventory")),
                          lang.t(f"{len(got.get('inventory') or [])} позиций", f"{len(got.get('inventory') or [])} entries"))])


def from_sotn(got):
    sections = []
    for key, title in (("relics", lang.t("Реликвии", "Relics")), ("inventory", lang.t("Инвентарь", "Inventory")),
                       ("spells", lang.t("Заклинания", "Spells")), ("familiars", lang.t("Фамильяры", "Familiars"))):
        if got.get(key):
            sections.append(Section(title, pairs(got[key])))
    return Digest(
        game="Castlevania: Symphony of the Night",
        playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Уровень", "Level"), str(got.get("level", ""))),
                Field(lang.t("Опыт", "Experience"), number(got.get("experience", 0))),
                Field(lang.t("Золото", "Gold"), number(got.get("gold", 0))),
                Field(lang.t("Карта пройдена", "Map explored"), f"{got.get('map', 0)} %"),
                Field(lang.t("Убийств", "Kills"), number(got.get("kills", 0)))],
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
                   Field(lang.t("опыт", "exp"), number(unit.get("exp", 0))),
                   Field(lang.t("убийств", "kills"), str(unit.get("kills", "")))],
            gear=[],
            extra=lang.t(f"магия {learned}", f"magic {learned}") if learned else ""))
    sections = []
    if got.get("guardians"):
        sections.append(Section(
            lang.t("Гардианы", "Guardians"),
            [Field(gf.get("name", "?"),
                   lang.t(f"{len(gf.get('learned') or [])} способностей", f"{len(gf.get('learned') or [])} abilities"))
             for gf in got["guardians"]],
            lang.t(f"{len(got['guardians'])} из 16", f"{len(got['guardians'])} of 16")))
    if got.get("inventory"):
        sections.append(Section(lang.t("Инвентарь", "Inventory"), pairs(got["inventory"]),
                                lang.t(f"{len(got['inventory'])} позиций", f"{len(got['inventory'])} entries")))
    return Digest(
        game="Final Fantasy VIII", playtime=total(parts),
        fields=[Field(lang.t("Наиграно", "Playtime"), clock(parts)),
                Field(lang.t("Гилы", "Gil"), number(got.get("gil", 0))),
                Field(lang.t("Шагов", "Steps"), number(got.get("steps", 0))),
                Field(lang.t("Боёв", "Battles"), number(got.get("battles", 0)))],
        members=members, members_title=lang.t("Персонажи", "Characters"), sections=sections)


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
                              lang.t(f"{len(part.get('set', []))} из {part.get('total', 0)}", f"{len(part.get('set', []))} of {part.get('total', 0)}"))
                      for part in data.get("sections", [])])
    return None
