"""ErgoPSX Save Manager - версия для Windows и Linux.

    python3 qt/app.py               обычный запуск
    python3 qt/app.py --shot view.png  grab the window and quit

Вывод здесь только латиницей: консоль Windows кодирует его в cp1252,
и кириллица роняет процесс целиком.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer                # noqa: E402
from PySide6.QtWidgets import QApplication       # noqa: E402

from nsm.window import Window                     # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ErgoPSX Save Manager")
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
