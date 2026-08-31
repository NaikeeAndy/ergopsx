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
    return 1 if (holes or bad or only_app or only_engine) else 0


if __name__ == "__main__":
    sys.exit(main())
