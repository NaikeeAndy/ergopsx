"""Иконки сейвов: те же 16×16, что рисовал BIOS.

Декодирование берётся из движка, здесь только превращение в картинку Qt
и кэш - список прокручивают, а декодировать одно и то же по десять раз
незачем.
"""

import os
import sys

from PySide6.QtGui import QImage, QPixmap

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(HERE, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import psxid  # noqa: E402

SIZE = 16
_cache: dict[str, list[QPixmap]] = {}


def frames(block, key, side=46):
    """Кадры иконки. Пиксель остаётся пикселем: без сглаживания.

    Размер входит в ключ намеренно: панель справа просит 64 пикселя,
    список - 46, и с общим ключом все получали размер того, кто
    попросил первым. В списке иконка вылезала за карточку и наезжала
    на текст.
    """
    full = f"{key}@{side}"
    got = _cache.get(full)
    if got is not None:
        return got

    made = []
    try:
        decoded = psxid.decode_icon(block)
    except Exception:
        decoded = []
    for rows in decoded:
        # Каждая строка - плоский поток RGBA по четыре байта на пиксель.
        flat = b"".join(bytes(row) for row in rows)
        image = QImage(flat, SIZE, SIZE, SIZE * 4, QImage.Format_RGBA8888)
        # Копию делаем сразу: QImage не владеет чужим буфером.
        made.append(QPixmap.fromImage(image.copy().scaled(side, side)))
    _cache[full] = made
    return made
