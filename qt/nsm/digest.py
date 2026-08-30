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
    labels = {"hp": "HP", "mp": "MP", "sp": lang.t("speed"),
              "pa": lang.t("p.atk"), "ma": lang.t("m.atk")}
    order = ("hp", "mp", "sp", "pa", "ma")
    members = []
    for unit in got.get("units", []):
        extra = [unit.get("who", ""), unit.get("gender", ""), unit.get("zodiac", "")]
        if unit.get("guest"):
            extra.append(lang.t("guest"))
        if unit.get("status"):
            extra.append(unit["status"])
        stats = got and unit.get("stats") or {}
        numbers = [Field(labels[key], str(stats[key]))
                   for key in order if key in stats]
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("job", ""),
            level=str(unit.get("level", "")),
            stats=numbers + [Field(lang.t("brave"), str(unit.get("brave", ""))),
                             Field(lang.t("faith"), str(unit.get("faith", "")))],
            gear=gear_names(unit.get("gear")),
            extra=" · ".join(x for x in extra if x)))
    inventory = got.get("inventory") or []
    return Digest(
        game="Final Fantasy Tactics",
        playtime=total(got.get("playtime")),
        fields=[
            Field(lang.t("Hero"), got.get("name", "")),
            Field(lang.t("Class"), got.get("job", "")),
            Field(lang.t("Level"), str(got.get("level", ""))),
            Field(lang.t("Playtime"), clock(got.get("playtime"))),
            Field(lang.t("Funds"), lang.t("{0} gil", number(got.get("funds", 0)))),
            Field(lang.t("Place"), str(got.get("location", ""))),
            Field(lang.t("In-game date"), " ".join(str(x) for x in (got.get("date") or ()))),
            Field(lang.t("Birthday"),
                  " ".join(str(x) for x in (got.get("birthday") or ()))),
        ],
        members=members, members_title=lang.t("Party@@squad"),
        sections=[Section(lang.t("Inventory"), pairs(inventory),
                          lang.t("{0} entries", len(inventory)))])


def from_ff9(got):
    fields = [Field(lang.t("Playtime"), clock(got.get("playtime"))),
              Field(lang.t("Gil"), number(got.get("gil", 0))),
              Field(lang.t("Location"), str(got.get("location", "")))]
    if got.get("disc") is not None:
        fields.insert(0, Field(lang.t("Disc"), str(got["disc"])))
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field(lang.t("exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=lang.t("trance {0}", unit['trance']) if unit.get("trance") else ""))
    inventory = got.get("inventory") or []
    return Digest(game="Final Fantasy IX", playtime=total(got.get("playtime")),
                  fields=fields, members=members, members_title=lang.t("Party"),
                  sections=[Section(lang.t("Inventory"), pairs(inventory),
                                    lang.t("{0} entries", len(inventory)))])


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
                   Field(lang.t("exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra="" if not learned else lang.t("magic {0}", learned)))
    sections = [Section(lang.t("Inventory"), pairs(got.get("inventory")),
                        lang.t("{0} entries", len(got.get('inventory') or [])))]
    if got.get("espers"):
        sections.append(Section(lang.t("Espers"), pairs(got["espers"])))
    # Число, а не список: движок отдаёт сколько персонажей не найдено.
    if got.get("not_recruited"):
        sections.append(Section(lang.t("Not recruited"),
                                [Field(lang.t("characters"), str(got["not_recruited"]))]))
    return Digest(
        game="Final Fantasy VI", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("gil", 0))),
                Field(lang.t("Steps"), number(got.get("steps", 0))),
                Field(lang.t("Saves"), str(got.get("saves", ""))),
                Field(lang.t("Location"), str(got.get("location", "")))],
        members=members, members_title=lang.t("Party"), sections=sections)


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
                   Field(lang.t("exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=lang.t("job level {0}", unit.get('job_level', 0))))
    return Digest(
        game="Final Fantasy V", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("money", 0))),
                Field(lang.t("Killed"), number(got.get("kills", 0))),
                Field(lang.t("Battles"), number(got.get("battles", 0))),
                Field(lang.t("Saves"), str(got.get("saves", ""))),
                Field(lang.t("World"), str(got.get("world", ""))),
                Field(lang.t("Map"), str(got.get("map", "")))],
        members=members, members_title=lang.t("Party"),
        sections=[Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get('inventory') or [])))])


def from_re1(got):
    return Digest(
        game="Resident Evil", playtime=got.get("playtime_raw"),
        fields=[Field(lang.t("Hero"), str(got.get("character", ""))),
                Field(lang.t("Health"), str(got.get("health", ""))),
                Field(lang.t("Ink ribbons"), str(got.get("ink_ribbons", ""))),
                Field(lang.t("Location"), str(got.get("location", "")))],
        sections=[Section(lang.t("Carried"), pairs(got.get("inventory"))),
                  Section(lang.t("In container"), pairs(got.get("container")))])


def from_pe2(got):
    return Digest(
        game="Parasite Eve II",
        playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Second number"), str(got.get("mark", ""))),
                Field(lang.t("Items carried"), str(got.get("items", ""))),
                Field(lang.t("In storage"), str(got.get("stored", ""))),
                Field(lang.t("Records in block"), str(got.get("banks", "")))])


def from_crash2(got):
    return Digest(
        game="Crash Bandicoot 2",
        fields=[Field(lang.t("Player"), got.get("name") or "—"),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Lives"), str(got.get("lives", ""))),
                Field(lang.t("Fruit"), number(got.get("wumpa", 0))),
                Field(lang.t("Aku Aku"), str(got.get("aku_aku", ""))),
                Field(lang.t("Crystals"), str(got.get("crystals", ""))),
                Field(lang.t("Gems@@count"), str(got.get("gems", ""))),
                Field(lang.t("Levels cleared"), str(got.get("progress", ""))),
                Field(lang.t("Secrets"), str(got.get("secrets", "")))])


def from_chronicles(got):
    return Digest(
        game="Castlevania Chronicles",
        fields=[Field(lang.t("Player"), got.get("name", "")),
                Field(lang.t("Stage"), f"{got.get('stage', 0):02d}"),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Second number"), f"{got.get('counter', 0):02d}"),
                Field(lang.t("Saved"), got.get("saved", ""))])


AREAS = (lang.t("Humans"), lang.t("Beasts"), lang.t("Undead"), lang.t("Phantoms"), lang.t("Dragons"), lang.t("Evils"))
KINDS = (("weapons", lang.t("Weapons")), ("shields", lang.t("Shields")), ("blades", lang.t("Blades")),
         ("grips", lang.t("Grips")), ("armor", lang.t("Armor")), ("gems", lang.t("Gems")),
         ("misc", lang.t("Other")))
LEARNED = (("breakArt", lang.t("Break Arts")), ("spell", lang.t("Spells")),
           ("ability", lang.t("Abilities")))


def from_vagrant(got):
    sections = []
    if got.get("weapons"):
        sections.append(Section(lang.t("Weapons carried"),
                                [Field(x) for x in got["weapons"]]))
    if got.get("stored_weapons"):
        sections.append(Section(lang.t("Weapons in container"),
                                [Field(x) for x in got["stored_weapons"]]))
    for where, title in (("carried_items", lang.t("Carried")),
                         ("stored_items", lang.t("In container"))):
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
        sections.append(Section(lang.t("Rooms not found"),
                                [Field(name, str(count)) for name, count in rows],
                                lang.t("{0} total", sum(got['unopened'].values()))))
    kills = got.get("kills") or []
    sections.append(Section(lang.t("Killed"),
                            [Field(AREAS[i], number(kills[i]))
                             for i in range(min(len(AREAS), len(kills)))],
                            lang.t("{0} total", number(sum(kills)))))
    hp, mp = got.get("hp", [0, 0]), got.get("mp", [0, 0])
    return Digest(
        game="Vagrant Story", playtime=total(got.get("playtime")),
        fields=[
            Field(lang.t("Playtime"), clock(got.get("playtime"))),
            Field("HP", f"{hp[0]}/{hp[1]}"),
            Field("MP", f"{mp[0]}/{mp[1]}"),
            Field(lang.t("Map explored"), f"{got.get('map_completion', 0)} %"),
            Field(lang.t("Rooms found"),
                  lang.t("{0} of {1}", got.get('rooms', 0), got.get('rooms_total', 361))),
            Field(lang.t("Rooms left"),
                  str(max(0, got.get("rooms_total", 361) - got.get("rooms", 0)))),
            Field(lang.t("Arts learned"), lang.t("{0} of 48", got.get('arts_learned', 0))),
            Field(lang.t("Longest chain"), str(got.get("max_chain", ""))),
            Field(lang.t("Heals"), str(got.get("heals", ""))),
            Field(lang.t("Chests opened"), str(got.get("chests", ""))),
            Field(lang.t("Actions learned"), str(got.get("actions", ""))),
            Field(lang.t("Times cleared"), str(got.get("clear_count", ""))),
            Field(lang.t("Saves total"), str(got.get("saves_total", ""))),
            Field(lang.t("Saves this run"), str(got.get("saves_game", ""))),
            Field(lang.t("Location"), str(got.get("location", ""))),
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
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("gil", 0))),
                Field(lang.t("Location"), str(got.get("location", ""))),
                Field(lang.t("Battles"), str(got.get("battles", ""))),
                Field(lang.t("Escapes"), str(got.get("escapes", "")))],
        members=members, members_title=lang.t("Party"),
        sections=[Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get('inventory') or [])))])


def from_sotn(got):
    sections = []
    for key, title in (("relics", lang.t("Relics")), ("inventory", lang.t("Inventory")),
                       ("spells", lang.t("Spells")), ("familiars", lang.t("Familiars"))):
        if got.get(key):
            sections.append(Section(title, pairs(got[key])))
    return Digest(
        game="Castlevania: Symphony of the Night",
        playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Experience"), number(got.get("experience", 0))),
                Field(lang.t("Gold"), number(got.get("gold", 0))),
                Field(lang.t("Map explored"), f"{got.get('map', 0)} %"),
                Field(lang.t("Kills"), number(got.get("kills", 0)))],
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
                   Field(lang.t("exp"), number(unit.get("exp", 0))),
                   Field(lang.t("kills"), str(unit.get("kills", "")))],
            gear=[],
            extra=lang.t("magic {0}", learned) if learned else ""))
    sections = []
    if got.get("guardians"):
        sections.append(Section(
            lang.t("Guardians"),
            [Field(gf.get("name", "?"),
                   lang.t("{0} abilities", len(gf.get('learned') or [])))
             for gf in got["guardians"]],
            lang.t("{0} of 16", len(got['guardians']))))
    if got.get("inventory"):
        sections.append(Section(lang.t("Inventory"), pairs(got["inventory"]),
                                lang.t("{0} entries", len(got['inventory']))))
    return Digest(
        game="Final Fantasy VIII", playtime=total(parts),
        fields=[Field(lang.t("Playtime"), clock(parts)),
                Field(lang.t("Gil"), number(got.get("gil", 0))),
                Field(lang.t("Steps"), number(got.get("steps", 0))),
                Field(lang.t("Battles"), number(got.get("battles", 0)))],
        members=members, members_title=lang.t("Characters"), sections=sections)


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
                              lang.t("{0} of {1}", len(part.get('set', [])), part.get('total', 0)))
                      for part in data.get("sections", [])])
    return None
