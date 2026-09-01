"""ErgoPSX Save Manager - версия для Windows и Linux.

    python3 qt/app.py               обычный запуск
    python3 qt/app.py --shot view.png  grab the window and quit
    python3 qt/app.py --digests out.json --folder saves
                                       dump every breakdown and quit

Вывод здесь только латиницей: консоль Windows кодирует его в cp1252,
и кириллица роняет процесс целиком.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer                # noqa: E402
from PySide6.QtGui import QIcon                   # noqa: E402
from PySide6.QtWidgets import QApplication       # noqa: E402

from nsm.window import Window                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def icon():
    """Значок окна. Без него в панели задач висит заглушка системы.

    На macOS его даёт сам пакет приложения, а на Windows и Linux задать
    его должен кто-то - иначе окно остаётся безымянным.
    """
    for where in (os.path.join(HERE, "packaging", "ergopsx.png"),
                  os.path.join(HERE, "..", "packaging", "ergopsx.png"),
                  os.path.join(os.path.dirname(HERE), "packaging",
                               "ergopsx.png")):
        if os.path.exists(where):
            return QIcon(where)
    return QIcon()


def digests(target, folder):
    import hashlib
    import json
    from nsm import digest, lang
    from nsm.library import Library
    lang.set_language("en")
    library = Library()
    library.load([folder])
    out, seen = {}, set()
    for item in library.items:
        key = hashlib.sha256(bytes(item.frame[10:30]) + item.block).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out[key] = digest.dump(item, library)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"digests: {len(out)} saves, {sum(v is not None for v in out.values())} with a breakdown -> {target}")
    return 0


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ErgoPSX Save Manager")
    app.setWindowIcon(icon())
    # Связывает окно с пунктом меню приложений: без этого оболочка
    # рисует рядом с ним заглушку, а не наш значок.
    app.setDesktopFileName("ergopsx")
    # Выгрузка разборов для сличения с версией для macOS, без окна:
    # запускается упакованный бинарник там, где он живёт, и сличается
    # то, что реально ушло пользователю, а не исходники в моём окружении.
    if "--digests" in sys.argv:
        return digests(sys.argv[sys.argv.index("--digests") + 1],
                       sys.argv[sys.argv.index("--folder") + 1])
    window = Window()
    # `app.quit()` не зовёт `closeEvent`, а поток обхода надо остановить
    # в любом случае - иначе Qt уничтожает его на ходу и приложение
    # падает уже на выходе.
    app.aboutToQuit.connect(window.stop_loading)
    window.show()

    # Снимок окна для проверки вида: собрать, дождаться чтения, снять.
    if "--shot" in sys.argv:
        target = sys.argv[sys.argv.index("--shot") + 1]
        wait = sys.argv.index("--wait") + 1 if "--wait" in sys.argv else None
        delay = int(sys.argv[wait]) if wait else 6

        def shoot():
            # Для снимка выбираем игру с подробным разбором - иначе
            # видно только общую часть.
            # Поле поиска очищаем: в снимок попадало случайное содержимое.
            window.search.clear()
            want = None
            for index in range(window.sidebar.count()):
                if "Vagrant" in window.sidebar.item(index).text():
                    want = index
                    break
            if want is not None:
                window.sidebar.setCurrentRow(want)
                window.list.setCurrentRow(0)
                # Сигнал не приходит, если строка и так первая - зовём сами.
                current = window.list.currentItem()
                if current is not None:
                    item = current.data(Qt.UserRole)
                    print("list selection:", item.title)
                    window.inspector.show_item(item)
                    print("handed to the panel:", item.title)
                for row in range(min(3, window.list.count())):
                    window.basket.add(window.list.item(row).data(Qt.UserRole))
                window.basket_bar.refresh()
            if "--compare" in sys.argv and window.list.count() >= 2:
                window.list.item(0).setSelected(True)
                window.list.item(1).setSelected(True)
                from nsm.compare import CompareView
                view = CompareView(window.list.item(0).data(Qt.UserRole),
                                   window.list.item(1).data(Qt.UserRole),
                                   window.library, window.palette_now, window)
                view.show()
                view.grab().save(target)
                print("shot saved:", target)
                app.quit()
                return
            # Снимать сразу нельзя: добавленные виджеты ещё не разложены,
            # и панель справа выходит пустой. Даём циклу событий пройти.
            def grab():
                window.grab().save(target)
                print(f"shot saved: {target}")
                app.quit()

            QTimer.singleShot(400, grab)

        QTimer.singleShot(delay * 1000, shoot)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
