"""Сверка слоя приложения с движком на Swift.

`tools/psxverify.py` сравнивает два движка между собой, а слой приложения -
третий потребитель, и он не был покрыт ничем. Именно здесь жила ошибка,
из-за которой **вся коллекция считалась одноблочной**: приложение собирает
каталожный фрейм на месте, размер сейва движок читает из поля `+4` этого
фрейма, а оно оставалось нулевым. Сверка движков её не поймала - она берёт
число блоков из длины цепочки, а не из ответа движка.

    python3 qt/check.py [папка]

Без собранного `memcard` молча пропускается: на Windows и Linux Swift нет.
"""

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import psxid                     # noqa: E402
from nsm.library import Library  # noqa: E402

BINARY = os.path.join(ROOT, "swift", ".build", "debug", "memcard")
# Наигранное время движок не отдаёт: его собирает слой приложения -
# сперва разборщик игры, потом таблица автопоиска. У версии для macOS
# такой же слой, и сличить их можно только через её выгрузку.
APP = os.path.join(ROOT, "swift", ".build", "debug", "MemCardSaver")
# Сравниваем то, что приложение показывает само: подпись игры приходит
# из движка байт в байт, а вот эти поля оно строит по-своему.
FIELDS = ("title", "serial", "region", "blocks", "internalName")


def app_side(root):
    """Записи так, как их видит приложение."""
    library = Library()
    library.load([root])
    rows = {}
    for item in library.items:
        key = (os.path.relpath(item.path, root),
               hashlib.sha256(item.block).hexdigest())
        rows[key] = {"title": item.title, "serial": item.serial,
                     "region": item.region, "blocks": item.blocks,
                     "internalName": item.signature}
    return rows, library


def playtimes_app(root):
    """Наигранное время приложением для macOS: хеш тела -> секунды."""
    if not os.path.exists(APP):
        return None
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        target = fh.name
    try:
        subprocess.run([APP, "--playtimes", target],
                       capture_output=True, check=True)
        with open(target, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        os.unlink(target)


def digests_app(root):
    """Разбор игр приложением для macOS: то, что видно в панели справа."""
    if not os.path.exists(APP):
        return None
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        target = fh.name
    try:
        subprocess.run([APP, "--digests", target], capture_output=True, check=True)
        with open(target, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        os.unlink(target)


def shown(item, library):
    """То же самое у версии на Qt."""
    from nsm import digest
    made = digest.build(library.detail(item))
    if made is None:
        return None
    return {"game": made.game,
            "fields": [[f.label, f.value] for f in made.fields],
            "membersTitle": made.members_title,
            "members": [[m.name, m.role, m.level,
                         ",".join(f"{s.label}={s.value}" for s in m.stats),
                         ",".join(m.gear or []), m.extra or ""]
                        for m in made.members],
            "sections": [[s.title, str(len(s.items)), s.note]
                         for s in made.sections]}


def engine_side(root):
    """Записи так, как их видит движок на Swift."""
    titles = psxid.default_titles_path()
    out = subprocess.run([BINARY, "--lang", "ru", "dump", titles, root],
                         capture_output=True, check=True).stdout
    return {(row["path"], row["digest"]): row["info"]
            for row in json.loads(out)}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "saves"
    # Пропускаем молча там, где сверять нечем: в публичном репозитории
    # нет ни коллекции, ни базы названий, а на Windows и Linux нет Swift.
    if not os.path.exists(BINARY):
        print(f"нет {BINARY} - сверка пропущена")
        return 0
    if not os.path.isdir(root):
        print(f"нет папки {root} - сверка пропущена")
        return 0
    if not os.path.exists(psxid.default_titles_path()):
        print("нет базы названий - сверка пропущена")
        return 0

    app, library = app_side(root)
    engine = engine_side(root)
    print(f"записей          приложение {len(app)}, движок {len(engine)}")

    only_app = sorted(set(app) - set(engine))
    only_engine = sorted(set(engine) - set(app))
    if only_app:
        print(f"есть только у приложения: {len(only_app)}")
        for key in only_app[:5]:
            print("   ", key[0])
    if only_engine:
        print(f"есть только у движка:     {len(only_engine)}")
        for key in only_engine[:5]:
            print("   ", key[0])

    holes = 0
    for key in sorted(set(app) & set(engine)):
        for field in FIELDS:
            mine, theirs = app[key].get(field), engine[key].get(field)
            # Название игры приложение подменяет своей заглушкой, когда
            # базы названий нет: это не расхождение разбора.
            if field == "title" and not theirs:
                continue
            if mine != theirs:
                holes += 1
                if holes <= 10:
                    print(f"  {key[0]}\n    {field}: приложение {mine!r}, "
                          f"движок {theirs!r}")

    print(f"сверено          {len(set(app) & set(engine))}")
    print(f"расхождений      {holes or 'нет'}")
    # Заодно то, что считает само приложение и никто больше не проверяет.
    multi = [i for i in library.unique if i.blocks > 1]
    print(f"многоблочных     {len(multi)} из {len(library.unique)}"
          f", самый крупный {max((i.blocks for i in multi), default=0)}")
    bad = [i for i in library.items
           if i.blocks != max(1, len(i.block) // psxid.BLOCK)]
    print(f"блоки не по телу {len(bad)}")

    # Наигранное время - отдельным проходом: в `dump` его нет.
    clocks = 0
    theirs = playtimes_app(root)
    if theirs is None:
        print("наигранное    приложение для macOS не собрано, пропущено")
    else:
        seen = set()
        for item in library.items:
            key = hashlib.sha256(item.block).hexdigest()
            if key in seen or key not in theirs:
                continue
            seen.add(key)
            mine = item.playtime if item.playtime is not None else -1
            if mine != theirs[key]:
                clocks += 1
                if clocks <= 5:
                    print(f"  {os.path.basename(item.path)}\n"
                          f"    наигранное: Qt {mine}, macOS {theirs[key]}")
        print(f"наигранное       сверено {len(seen)}, "
              f"расхождений {clocks or 'нет'}")
    # Разбор игр - то, что видно в панели. Движки сверены между собой,
    # а панель каждый строит сам, и она расходилась по всем играм сразу.
    shows = 0
    theirs = digests_app(root)
    if theirs is None:
        print("разбор игр   приложение для macOS не собрано, пропущено")
    else:
        from nsm import lang
        lang.set_language("en")
        seen = set()
        for item in library.items:
            key = hashlib.sha256(bytes(item.frame[10:30]) + item.block).hexdigest()
            if key in seen or key not in theirs:
                continue
            seen.add(key)
            mine, their = shown(item, library), theirs[key]
            if mine == their:
                continue
            shows += 1
            if shows <= 5:
                part = next((p for p in their if mine is None or mine[p] != their[p]),
                            "разбора нет")
                print(f"  {their['game']}: {part}")
                print(f"    macOS {str(their.get(part))[:120]}")
                print(f"    Qt    {str(mine and mine.get(part))[:120]}")
        print(f"разбор игр       сверено {len(seen)}, "
              f"расхождений {shows or 'нет'}")
    return 1 if (holes or bad or clocks or shows or only_app or only_engine) else 0


if __name__ == "__main__":
    sys.exit(main())
