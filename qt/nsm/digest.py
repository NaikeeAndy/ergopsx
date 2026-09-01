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


# Движок отдаёт эти слова по-русски: они зашиты таблицами в `psxfft`,
# и менять их там нельзя - по ним сверяются два движка. Переводим здесь,
# на входе в панель. Ключи каталога английские, как и везде.
FROM_ENGINE = {
    "мужской": "male", "женский": "female", "монстр": "monster",
    "гость": "guest", "временно покидает отряд": "temporarily leaves the party",
    "Январь": "January", "Февраль": "February", "Март": "March",
    "Апрель": "April", "Май": "May", "Июнь": "June", "Июль": "July",
    "Август": "August", "Сентябрь": "September", "Октябрь": "October",
    "Ноябрь": "November", "Декабрь": "December",
    "Овен": "Aries", "Телец": "Taurus", "Близнецы": "Gemini", "Рак": "Cancer",
    "Лев": "Leo", "Дева": "Virgo", "Весы": "Libra", "Скорпион": "Scorpio",
    "Стрелец": "Sagittarius", "Козерог": "Capricorn", "Водолей": "Aquarius",
    "Рыбы": "Pisces",
}


def spoken(word):
    """Слово от движка - на языке интерфейса. Числа проходят как есть:
    в дате рядом с месяцем стоит день."""
    key = FROM_ENGINE.get(word)
    return lang.t(key) if key else str(word)


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
    members = []
    for unit in got.get("units", []):
        extra = [unit.get("who", ""), spoken(unit.get("gender", "")),
                 spoken(unit.get("zodiac", ""))]
        if unit.get("guest"):
            extra.append(lang.t("guest"))
        if unit.get("status"):
            extra.append(spoken(unit["status"]))
        # У монстров класс один и сменить его нельзя, поэтому экранных
        # статов для них не существует - только сырые.
        stats = unit.get("stats") or {}
        numbers = [Field(labels.get(key, key), str(stats[key]))
                   for key in ("hp", "mp", "sp", "pa", "ma") if key in stats]
        members.append(Member(
            name=unit.get("name") or unit.get("who", ""),
            role=unit.get("job", ""), level=str(unit.get("level", "")),
            stats=numbers + [Field(lang.t("brave"), str(unit.get("brave", ""))),
                             Field(lang.t("faith"), str(unit.get("faith", "")))],
            gear=gear_names(unit.get("gear")),
            extra=" · ".join(x for x in extra if x)))
    return Digest(
        game="Final Fantasy Tactics", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Hero"), got.get("name", "")),
                Field(lang.t("Class"), got.get("job", "")),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Funds"), lang.t("{0} gil", number(got.get("funds", 0)))),
                Field(lang.t("Place"), got.get("location", "")),
                Field(lang.t("In-game date"),
                      " ".join(spoken(x) for x in (got.get("date") or []))),
                Field(lang.t("Birthday"),
                      " ".join(spoken(x) for x in (got.get("birthday") or [])))],
        members=members, members_title=lang.t("Party@@squad"),
        sections=[Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get("inventory") or [])))])

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
        magic = unit.get("magic") or []
        learned = [m for m in magic if m.get("learned")]
        extra = [", ".join(unit.get("abilities") or [])]
        if magic:
            extra.append(lang.t("magic {0} of {1}", len(learned), len(magic)))
        members.append(Member(
            name=unit.get("name", ""), role=unit.get("who", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field(lang.t("exp"), number(unit.get("exp", 0)))],
            gear=gear_names(unit.get("gear"))
                 + [f"{m.get('name')} {m.get('percent')} %"
                    for m in magic if not m.get("learned")],
            extra=" · ".join(x for x in extra if x)))
    return Digest(
        game="Final Fantasy VI", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("gil", 0))),
                Field(lang.t("Steps"), number(got.get("steps", 0))),
                Field(lang.t("Saves"), str(got.get("saves", ""))),
                Field(lang.t("Place"), got.get("location", "")),
                Field(lang.t("Not recruited"), str(got.get("not_recruited", "")))],
        members=members, members_title=lang.t("Party"),
        sections=[Section(lang.t("Espers"),
                          [Field(x) for x in (got.get("espers") or [])],
                          str(len(got.get("espers") or []))),
                  Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get("inventory") or [])))])

def from_ff5(got):
    members = []
    for unit in got.get("party", []):
        hp, mp = unit.get("hp", [0, 0]), unit.get("mp", [0, 0])
        members.append(Member(
            name=unit.get("name", ""), role=unit.get("job", ""),
            level=str(unit.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}"),
                   Field("MP", f"{mp[0]}/{mp[1]}"),
                   Field("ABP", str(unit.get("abp", 0)))],
            gear=gear_names(unit.get("gear")),
            extra=lang.t("job level {0}", unit.get("job_level", 0))))
    return Digest(
        game="Final Fantasy V", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("money", 0))),
                Field(lang.t("Battles"), number(got.get("battles", 0))),
                Field(lang.t("Killed"), number(got.get("kills", 0))),
                Field(lang.t("Saves"), str(got.get("saves", ""))),
                Field(lang.t("Chests opened"), str(got.get("chests", ""))),
                Field(lang.t("World"), str(got.get("world", ""))),
                Field(lang.t("Map"), str(got.get("map", ""))),
                Field(lang.t("Roster"), ", ".join(got.get("roster") or []))],
        members=members, members_title=lang.t("Party"),
        sections=[Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get("inventory") or [])))])

def from_re1(got):
    raw = got.get("playtime_raw", 0) or 0
    return Digest(
        game="Resident Evil", playtime=None,
        fields=[Field(lang.t("Hero"), got.get("character", "")),
                Field(lang.t("Health"), str(got.get("health", ""))),
                Field(lang.t("Place"), got.get("location", "")),
                Field(lang.t("Ink ribbons"), str(got.get("ink_ribbons", ""))),
                Field(lang.t("Time counter"), number(raw)),
                Field(lang.t("If these are seconds"),
                      "%d:%02d:%02d" % (raw // 3600, raw // 60 % 60, raw % 60))],
        sections=[Section(lang.t("Carried"), pairs(got.get("inventory")),
                          lang.t("{0} of 8", len(got.get("inventory") or []))),
                  Section(lang.t("In container"), pairs(got.get("container")),
                          lang.t("{0} entries", len(got.get("container") or [])))])

def from_pe2(got, signature=""):
    # Место берём из подписи: справочника локаций в разборе нет, а игра
    # пишет название сама - «PE2 0:52 Square(5)».
    place = signature.split(" ", 2)[2].strip() if signature.count(" ") >= 2 else ""
    parts = got.get("playtime") or [0, 0]
    return Digest(
        game="Parasite Eve II",
        playtime=(got.get("playtime_minutes") or 0) * 60,
        fields=[Field(lang.t("Playtime"), "%d:%02d" % (parts[0], parts[1])),
                Field(lang.t("Place"), place or "—"),
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


# Ёмкости разделов - те же, что у движка: `Vagrant.carried` и `.stored`.
CARRIED_SLOTS = (("weapons", "Weapons", 8), ("shields", "Shields", 8),
                 ("blades", "Blades", 16), ("grips", "Grips", 16),
                 ("armor", "Armor", 16), ("gems", "Gems", 48),
                 ("misc", "Other", 64))
STORED_SLOTS = (("weapons", "Weapons", 32), ("shields", "Shields", 32),
                ("blades", "Blades", 64), ("grips", "Grips", 64),
                ("armor", "Armor", 64), ("gems", "Gems", 192),
                ("misc", "Other", 256))


def from_vagrant(got):
    sections = []
    if got.get("weapons"):
        sections.append(Section(lang.t("Weapons carried"),
                                [Field(x) for x in got["weapons"]]))
    if got.get("stored_weapons"):
        sections.append(Section(lang.t("Weapons in container"),
                                [Field(x) for x in got["stored_weapons"]]))
    for where, title in (("carried_items", lang.t("Carried")),
                         ("stored_items", lang.t("Container"))):
        for kind, name in KINDS:
            rows = (got.get(where) or {}).get(kind)
            if rows:
                sections.append(Section(
                    f"{title} — {name}",
                    [Field(item, str(count) if count > 1 else "")
                     for item, count in rows]))
    # Сводка по местам: сколько занято из скольких. Разбор отдаёт сами
    # предметы, а ёмкости разделов известны - считаем здесь.
    for where, slots, title in (("carried_items", CARRIED_SLOTS, lang.t("Carried")),
                                ("stored_items", STORED_SLOTS, lang.t("In container"))):
        rows = got.get(where) or {}
        sections.append(Section(
            title,
            [Field(name, lang.t("{0} of {1}", len(rows.get(kind) or []), total))
             for kind, name, total in slots]))
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
            Field(lang.t("Chests opened"), str(got.get("chests", ""))),
            Field(lang.t("Arts learned"), lang.t("{0} of 48", got.get('arts_learned', 0))),
            Field(lang.t("Abilities unlocked"), str(got.get("abilities", ""))),
            Field(lang.t("Longest chain"), str(got.get("max_chain", ""))),
            Field(lang.t("Heals"), str(got.get("heals", ""))),
            Field(lang.t("Actions learned"), str(got.get("actions", ""))),
            Field(lang.t("Maps explored"), str(got.get("maps", ""))),
            Field(lang.t("Times cleared"), str(got.get("clear_count", ""))),
            Field(lang.t("Saves total"), str(got.get("saves_total", ""))),
            Field(lang.t("Saves this run"), str(got.get("saves_game", ""))),
            Field(lang.t("Location"), str(got.get("location", ""))),
        ],
        sections=sections)


def from_ff7(got):
    stat_names = [lang.t("str"), lang.t("vit"), lang.t("magic"),
                  lang.t("spr"), lang.t("agi"), lang.t("luck")]
    members = []
    for who in got.get("characters", []):
        hp = who.get("hp", [0, 0])
        # Разбор отдаёт материю парами «куда вставлена, что за камень».
        materia = [m[1].get("name", "") for m in (who.get("materia") or [])
                   if len(m) > 1 and isinstance(m[1], dict)]
        members.append(Member(
            name=who.get("name") or who.get("who", ""),
            role=who.get("who", ""), level=str(who.get("level", "")),
            stats=[Field("HP", f"{hp[0]}/{hp[1]}")]
                  + [Field(name, str(value))
                     for name, value in zip(stat_names, who.get("stats") or [])],
            # Экипировка адресуется своими списками, а не общим инвентарём -
            # иначе Клауд оказывается вооружён зельем.
            gear=[x for x in (who.get("weapon", ""), who.get("armor", ""),
                              who.get("accessory", "")) if x],
            extra=lang.t("materia: ") + ", ".join(materia) if materia else ""))

    def stone(row):
        return Field(row.get("name", ""),
                     lang.t("mastered") if row.get("mastered")
                     else f"{row.get('stars', 0)}/{row.get('total', 0)}")

    return Digest(
        game="Final Fantasy VII", playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Hero"), got.get("leader", "")),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Gil"), number(got.get("gil", 0))),
                Field(lang.t("Place"), str(got.get("location", ""))),
                Field(lang.t("Slot"), got.get("location_text", "")),
                Field(lang.t("Battles"), number(got.get("battles", 0))),
                Field(lang.t("Escapes"), number(got.get("runs", 0)))],
        members=members, members_title=lang.t("Characters"),
        sections=[Section(lang.t("Materia"),
                          [stone(x) for x in (got.get("materia") or [])],
                          str(len(got.get("materia") or []))),
                  Section(lang.t("Stolen by Yuffie"),
                          [stone(x) for x in (got.get("materia_stolen") or [])],
                          str(len(got.get("materia_stolen") or []))),
                  Section(lang.t("Inventory"),
                          [Field(x.get("name", ""), str(x.get("count", "")))
                           for x in (got.get("inventory") or [])],
                          lang.t("{0} entries", len(got.get("inventory") or [])))])

def from_sotn(got):
    hp, mp = got.get("hp", [0, 0]), got.get("mp", [0, 0])
    hearts = got.get("hearts", [0, 0])
    members = [Member(name=row[0] if row else "", role=lang.t("familiar"),
                      level=str(row[1]) if len(row) > 1 else "",
                      stats=[Field(lang.t("exp"), row[2])] if len(row) > 2 else [])
               for row in (got.get("familiars") or [])]
    return Digest(
        game="Castlevania: Symphony of the Night",
        playtime=total(got.get("playtime")),
        fields=[Field(lang.t("Hero"), got.get("character", "")),
                Field(lang.t("Level"), str(got.get("level", ""))),
                Field(lang.t("Playtime"), clock(got.get("playtime"))),
                Field(lang.t("Map"), "%.2f %%" % (got.get("map", 0) or 0)),
                Field("HP", f"{hp[0]}/{hp[1]}"),
                Field("MP", f"{mp[0]}/{mp[1]}"),
                Field(lang.t("Hearts"), f"{hearts[0]}/{hearts[1]}"),
                Field(lang.t("Experience"), number(got.get("exp", 0))),
                Field(lang.t("Gold"), number(got.get("gold", 0))),
                Field(lang.t("Kills"), number(got.get("kills", 0))),
                Field(lang.t("Location"), str(got.get("location", ""))),
                Field(lang.t("Progress"), str(got.get("progression", "")))],
        members=members, members_title=lang.t("Familiars"),
        sections=[Section(lang.t("Equipment"),
                          [Field(row[1], row[0]) for row in (got.get("gear") or [])
                           if len(row) > 1]),
                  Section(lang.t("Relics"),
                          [Field(x) for x in (got.get("relics") or [])],
                          str(len(got.get("relics") or []))),
                  Section(lang.t("Spells"),
                          [Field(x) for x in (got.get("spells") or [])],
                          str(len(got.get("spells") or []))),
                  Section(lang.t("Inventory"), pairs(got.get("inventory")),
                          lang.t("{0} entries", len(got.get("inventory") or []))),
                  Section(lang.t("Bestiary"),
                          [Field(x) for x in (got.get("bestiary") or [])],
                          lang.t("{0} of {1}", len(got.get("bestiary") or []),
                                 got.get("enemy_total", 0))),
                  Section(lang.t("With drop"),
                          [Field(x) for x in (got.get("drops") or [])],
                          str(len(got.get("drops") or [])))])

def from_ff8(got):
    """Как у версии для macOS: статы, магия в качестве экипировки,
    Гардианы отдельным разделом и опись."""
    chosen = (got.get("playtime") or {}).get("matches") or "as_seconds"
    parts = (got.get("playtime") or {}).get(chosen) or {}
    hours = parts.get("hours", 0)
    seconds = hours * 3600 + parts.get("minutes", 0) * 60 + parts.get("seconds", 0)
    stat_names = [lang.t("Strength"), lang.t("Vitality"), lang.t("Magic"),
                  lang.t("Spirit"), lang.t("Agility"), lang.t("Luck")]

    members = []
    for who in got.get("characters", []):
        if not who.get("exists"):
            continue
        stats = [Field("HP", f"{who.get('hp', 0)}/{who.get('hp_max', 0)}")]
        stats += [Field(name.lower(), str(value))
                  for name, value in zip(stat_names, who.get("stats") or [])]
        members.append(Member(
            name=who.get("name") or "—", role=who.get("weapon", ""),
            level=str(who.get("level", "")), stats=stats,
            gear=[f"{row[0]} ×{row[1]}" if len(row) > 1 else row[0]
                  for row in (who.get("magic") or []) if row],
            extra=lang.t("kills {0} · GF {1}", who.get("kills", 0),
                         who.get("gfs", 0))))

    # Гардианы - половина смысла сейва FF8, без них панель бессмысленна.
    guardians = []
    for gf in got.get("guardians", []):
        if not gf.get("exists"):
            continue
        guardians.append(Field(
            gf.get("name", ""),
            lang.t("lv. {0} · {1}", gf.get("level", 0),
                   lang.t("{0} of {1} abilities", len(gf.get("learned") or []),
                          gf.get("total_slots", 0)))))

    return Digest(
        game="Final Fantasy VIII", playtime=seconds,
        fields=[Field(lang.t("Playtime"),
                      "%d:%02d:%02d" % (hours, parts.get("minutes", 0),
                                        parts.get("seconds", 0))),
                Field(lang.t("Gil"), number(got.get("gils", 0))),
                Field(lang.t("Steps"), number(got.get("steps", 0))),
                Field(lang.t("Battles"), number(got.get("battles", 0))),
                Field(lang.t("In party"), ", ".join(got.get("party") or []))],
        members=members, members_title=lang.t("Characters"),
        sections=[Section(lang.t("Guardians"), guardians,
                          lang.t("{0} of 16", len(guardians))),
                  Section(lang.t("Inventory"), pairs(got.get("items")),
                          lang.t("{0} entries", len(got.get("items") or [])))])

BUILDERS = {
    "fft": from_fft, "ff9": from_ff9, "ff8": from_ff8, "ff7": from_ff7,
    "ff6": from_ff6, "ff5": from_ff5, "re1": from_re1, "sotn": from_sotn,
    "vagrant": from_vagrant, "pe2": from_pe2, "crash2": from_crash2,
    "chronicles": from_chronicles,
}


def build(detail):
    """Из разбора движка - в то, что показывает панель."""
    kind, data = detail.get("kind"), detail.get("data") or {}
    if kind == "pe2":
        # Единственный разборщик, которому нужна подпись сейва: название
        # места игра пишет туда, а справочника локаций у неё нет.
        return from_pe2(data, detail.get("internal", ""))
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
