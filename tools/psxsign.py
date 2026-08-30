#!/usr/bin/env python3
"""Подпись сейвов Sony: PSV для PS3 и VMP для PSP.

Без подписи PS3 отказывается принимать файл. Алгоритм - HMAC-SHA1, где ключ
выводится из salt seed через AES-128-ECB на известном ключе Sony.

SHA-1 берётся из стандартной библиотеки, AES реализован здесь же: ради одного
16-байтового блока тянуть внешний пакет незачем, а утилита остаётся запускаемой
на голом Python где угодно.

Раскладка - по save-file-converter (Components/SonyUtil.js, Psp.js, Ps3.js)
и MemcardRex (ps1card.cs, GetHmac).
"""

import hashlib
import struct

# --- AES-128 -----------------------------------------------------------------
# Таблицы строятся из определения поля, а не переписываются руками.

def _build_tables():
    sbox = [0] * 256
    p = q = 1
    while True:
        # p умножается на 3, q делится на 3 - обход мультипликативной группы.
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        value = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) \
            ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (value ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    return sbox, inv


SBOX, INV_SBOX = _build_tables()
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _xtime(value):
    return ((value << 1) ^ 0x1B) & 0xFF if value & 0x80 else value << 1


def _mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def _expand_key(key):
    words = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        temp = list(words[i - 1])
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= RCON[i // 4 - 1]
        words.append([words[i - 4][j] ^ temp[j] for j in range(4)])
    return [sum(words[r * 4:r * 4 + 4], []) for r in range(11)]


def _add_round_key(state, round_key):
    return [state[i] ^ round_key[i] for i in range(16)]


def _shift_rows(state, inverse=False):
    out = [0] * 16
    for row in range(4):
        for col in range(4):
            src = (col - row) % 4 if inverse else (col + row) % 4
            out[row + 4 * col] = state[row + 4 * src]
    return out


def _mix_columns(state, inverse=False):
    coeffs = (0x0E, 0x0B, 0x0D, 0x09) if inverse else (0x02, 0x03, 0x01, 0x01)
    out = [0] * 16
    for col in range(4):
        column = state[4 * col:4 * col + 4]
        for row in range(4):
            out[4 * col + row] = (
                _mul(column[0], coeffs[(0 - row) % 4])
                ^ _mul(column[1], coeffs[(1 - row) % 4])
                ^ _mul(column[2], coeffs[(2 - row) % 4])
                ^ _mul(column[3], coeffs[(3 - row) % 4]))
    return out


def encrypt_block(block, key):
    keys = _expand_key(key)
    state = _add_round_key(list(block), keys[0])
    for rnd in range(1, 11):
        state = [SBOX[b] for b in state]
        state = _shift_rows(state)
        if rnd != 10:
            state = _mix_columns(state)
        state = _add_round_key(state, keys[rnd])
    return bytes(state)


def decrypt_block(block, key):
    keys = _expand_key(key)
    state = _add_round_key(list(block), keys[10])
    for rnd in range(9, -1, -1):
        state = _shift_rows(state, inverse=True)
        state = [INV_SBOX[b] for b in state]
        state = _add_round_key(state, keys[rnd])
        if rnd != 0:
            state = _mix_columns(state, inverse=True)
    return bytes(state)


# --- Подпись Sony ------------------------------------------------------------

SAVE_KEY = bytes.fromhex("AB5ABC9FC1F49DE6A051DBAEFA518859")
# Sony называет это IV, но режим тут ECB - байты используются просто как
# фиксированная гамма при выводе ключа.
SAVE_IV = bytes.fromhex("B30FFEEDB7DC5EB7133DA60D1B6B2CDC")

SALT_LENGTH = 0x40
SEED_LENGTH = 0x14
SIGNATURE_LENGTH = 0x14

# Salt seed произволен; PSP при каждой записи ставит свой. Берём ту же
# возрастающую последовательность, что и save-file-converter.
SEED_INIT = bytes(range(SEED_LENGTH))

PSV = {"header": 0x84, "seed": 0x08, "signature": 0x1C, "magic": b"\x00VSP"}
VMP = {"header": 0x80, "seed": 0x0C, "signature": 0x20, "magic": b"\x00PMV"}


def _xor_range(buf, start, other):
    for i in range(len(other)):
        buf[start + i] ^= other[i]


def calculate_signature(data, salt_seed, signature_offset):
    """HMAC-SHA1 с ключом, выведенным из salt seed через AES."""
    salt = bytearray(SALT_LENGTH)
    salt[0x00:0x10] = decrypt_block(salt_seed[:0x10], SAVE_KEY)
    salt[0x10:0x20] = encrypt_block(salt_seed[:0x10], SAVE_KEY)
    _xor_range(salt, 0x00, SAVE_IV)

    tail = bytearray(b"\xFF" * 0x10)
    tail[0:SEED_LENGTH - 0x10] = salt_seed[0x10:SEED_LENGTH]
    _xor_range(salt, 0x10, tail)

    # Всё за пределами выведенных 20 байт обнуляется - дальше это обычный
    # HMAC: 0x36 даёт ipad, повторный xor на 0x6A превращает его в 0x5C (opad).
    salt[SEED_LENGTH:SALT_LENGTH] = bytes(SALT_LENGTH - SEED_LENGTH)
    salt = bytearray(b ^ 0x36 for b in salt)

    payload = bytearray(data)
    payload[signature_offset:signature_offset + SIGNATURE_LENGTH] = bytes(SIGNATURE_LENGTH)

    inner = hashlib.sha1(bytes(salt) + bytes(payload)).digest()
    salt = bytearray(b ^ 0x6A for b in salt)
    return hashlib.sha1(bytes(salt) + inner).digest()


def _layout(data):
    for layout in (PSV, VMP):
        if data[:4] == layout["magic"]:
            return layout
    return None


def verify(data):
    """Возвращает (записанная подпись, посчитанная, сходится ли)."""
    layout = _layout(data)
    if layout is None:
        raise ValueError("не PSV и не VMP")
    seed = data[layout["seed"]:layout["seed"] + SEED_LENGTH]
    found = bytes(data[layout["signature"]:layout["signature"] + SIGNATURE_LENGTH])
    actual = calculate_signature(data, seed, layout["signature"])
    return found, actual, found == actual


def resign(data, salt_seed=None):
    """Пересчитывает подпись файла на месте. Salt seed сохраняется, если не задан."""
    layout = _layout(data)
    if layout is None:
        raise ValueError("не PSV и не VMP")
    out = bytearray(data)
    if salt_seed is not None:
        out[layout["seed"]:layout["seed"] + SEED_LENGTH] = salt_seed
    seed = bytes(out[layout["seed"]:layout["seed"] + SEED_LENGTH])
    signature = calculate_signature(out, seed, layout["signature"])
    out[layout["signature"]:layout["signature"] + SIGNATURE_LENGTH] = signature
    return bytes(out)


def save_block(data):
    """Данные сейва внутри PSV: то, что лежит после заголовка."""
    if data[:4] != PSV["magic"]:
        raise ValueError("не PSV")
    start = struct.unpack_from("<I", data, 0x44)[0]
    size = struct.unpack_from("<I", data, 0x40)[0]
    return bytes(data[start:start + size])


def replace_block(data, block):
    """Возвращает PSV с новым содержимым сейва и пересчитанной подписью."""
    if data[:4] != PSV["magic"]:
        raise ValueError("не PSV")
    start = struct.unpack_from("<I", data, 0x44)[0]
    size = struct.unpack_from("<I", data, 0x40)[0]
    if len(block) != size:
        raise ValueError(f"размер сейва изменился: было {size}, стало {len(block)}")
    out = bytearray(data)
    out[start:start + size] = block
    return resign(bytes(out))
