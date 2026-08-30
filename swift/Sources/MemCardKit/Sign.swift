import Foundation
import CryptoKit

/// Подпись сейвов Sony: PSV для PS3 и VMP для PSP.
///
/// Без подписи PS3 отказывается принимать файл. Алгоритм - HMAC-SHA1, где
/// ключ выводится из salt seed через AES-128-ECB на известном ключе Sony.
///
/// AES реализован здесь же, а не взят из системной библиотеки: режим ECB
/// без набивки на одном блоке слишком легко получить чужими умолчаниями,
/// а тут нужна побайтовая повторяемость со старым движком.
///
/// Раскладка - по save-file-converter (`SonyUtil.js`) и MemcardRex.
public enum AES128 {
    /// Таблицы строятся из определения поля, а не переписываются руками.
    static let tables: (sbox: [UInt8], inverse: [UInt8]) = {
        var sbox = [UInt8](repeating: 0, count: 256)
        var p: UInt8 = 1, q: UInt8 = 1
        repeat {
            // p умножается на 3, q делится на 3 - обход мультипликативной группы.
            p = p ^ (p << 1) ^ ((p & 0x80) != 0 ? 0x1B : 0)
            q ^= q << 1
            q ^= q << 2
            q ^= q << 4
            if q & 0x80 != 0 { q ^= 0x09 }
            let value = q ^ rotate(q, 1) ^ rotate(q, 2) ^ rotate(q, 3) ^ rotate(q, 4)
            sbox[Int(p)] = value ^ 0x63
        } while p != 1
        sbox[0] = 0x63
        var inverse = [UInt8](repeating: 0, count: 256)
        for (index, value) in sbox.enumerated() { inverse[Int(value)] = UInt8(index) }
        return (sbox, inverse)
    }()

    static func rotate(_ value: UInt8, _ by: UInt8) -> UInt8 {
        (value << by) | (value >> (8 - by))
    }

    static let rcon: [UInt8] = [0x01, 0x02, 0x04, 0x08, 0x10,
                                0x20, 0x40, 0x80, 0x1B, 0x36]

    static func xtime(_ value: UInt8) -> UInt8 {
        (value & 0x80) != 0 ? (value << 1) ^ 0x1B : value << 1
    }

    static func multiply(_ a: UInt8, _ b: UInt8) -> UInt8 {
        var left = a, right = b, result: UInt8 = 0
        while right != 0 {
            if right & 1 != 0 { result ^= left }
            left = xtime(left)
            right >>= 1
        }
        return result
    }

    static func expand(_ key: [UInt8]) -> [[UInt8]] {
        var words = (0..<4).map { Array(key[($0 * 4)..<($0 * 4 + 4)]) }
        for index in 4..<44 {
            var temp = words[index - 1]
            if index % 4 == 0 {
                temp = Array(temp[1...]) + [temp[0]]
                temp = temp.map { tables.sbox[Int($0)] }
                temp[0] ^= rcon[index / 4 - 1]
            }
            words.append((0..<4).map { words[index - 4][$0] ^ temp[$0] })
        }
        return (0..<11).map { Array(words[($0 * 4)..<($0 * 4 + 4)].joined()) }
    }

    static func addRoundKey(_ state: [UInt8], _ key: [UInt8]) -> [UInt8] {
        (0..<16).map { state[$0] ^ key[$0] }
    }

    static func shiftRows(_ state: [UInt8], inverse: Bool = false) -> [UInt8] {
        var out = [UInt8](repeating: 0, count: 16)
        for row in 0..<4 {
            for col in 0..<4 {
                let src = inverse ? ((col - row) %% 4) : ((col + row) % 4)
                out[row + 4 * col] = state[row + 4 * src]
            }
        }
        return out
    }

    static func mixColumns(_ state: [UInt8], inverse: Bool = false) -> [UInt8] {
        let coeffs: [UInt8] = inverse ? [0x0E, 0x0B, 0x0D, 0x09] : [0x02, 0x03, 0x01, 0x01]
        var out = [UInt8](repeating: 0, count: 16)
        for col in 0..<4 {
            let column = Array(state[(4 * col)..<(4 * col + 4)])
            for row in 0..<4 {
                out[4 * col + row] =
                    multiply(column[0], coeffs[(0 - row) %% 4])
                    ^ multiply(column[1], coeffs[(1 - row) %% 4])
                    ^ multiply(column[2], coeffs[(2 - row) %% 4])
                    ^ multiply(column[3], coeffs[(3 - row) %% 4])
            }
        }
        return out
    }

    public static func encrypt(_ block: [UInt8], key: [UInt8]) -> [UInt8] {
        let keys = expand(key)
        var state = addRoundKey(block, keys[0])
        for round in 1...10 {
            state = state.map { tables.sbox[Int($0)] }
            state = shiftRows(state)
            if round != 10 { state = mixColumns(state) }
            state = addRoundKey(state, keys[round])
        }
        return state
    }

    public static func decrypt(_ block: [UInt8], key: [UInt8]) -> [UInt8] {
        let keys = expand(key)
        var state = addRoundKey(block, keys[10])
        for round in stride(from: 9, through: 0, by: -1) {
            state = shiftRows(state, inverse: true)
            state = state.map { tables.inverse[Int($0)] }
            state = addRoundKey(state, keys[round])
            if round != 0 { state = mixColumns(state, inverse: true) }
        }
        return state
    }
}

infix operator %%: MultiplicationPrecedence
/// Остаток по модулю, всегда неотрицательный - как `%` в Python.
func %% (lhs: Int, rhs: Int) -> Int {
    let value = lhs % rhs
    return value < 0 ? value + rhs : value
}

public enum SonySign {
    static let saveKey: [UInt8] = [0xAB, 0x5A, 0xBC, 0x9F, 0xC1, 0xF4, 0x9D, 0xE6,
                                   0xA0, 0x51, 0xDB, 0xAE, 0xFA, 0x51, 0x88, 0x59]
    /// Sony называет это IV, но режим тут ECB - байты используются просто
    /// как фиксированная гамма при выводе ключа.
    static let saveIV: [UInt8] = [0xB3, 0x0F, 0xFE, 0xED, 0xB7, 0xDC, 0x5E, 0xB7,
                                  0x13, 0x3D, 0xA6, 0x0D, 0x1B, 0x6B, 0x2C, 0xDC]

    static let saltLength = 0x40
    static let seedLength = 0x14
    static let signatureLength = 0x14

    public struct Layout: Sendable {
        public let header: Int
        public let seed: Int
        public let signature: Int
        public let magic: [UInt8]
    }

    public static let psv = Layout(header: 0x84, seed: 0x08, signature: 0x1C,
                                   magic: [0x00, 0x56, 0x53, 0x50])   // "\0VSP"
    public static let vmp = Layout(header: 0x80, seed: 0x0C, signature: 0x20,
                                   magic: [0x00, 0x50, 0x4D, 0x56])   // "\0PMV"

    static func layout(of data: [UInt8]) -> Layout? {
        guard data.count >= 4 else { return nil }
        for candidate in [psv, vmp] where Array(data[0..<4]) == candidate.magic {
            return candidate
        }
        return nil
    }

    /// HMAC-SHA1 с ключом, выведенным из salt seed через AES.
    public static func signature(_ data: [UInt8], seed: [UInt8],
                                 at signatureOffset: Int) -> [UInt8] {
        var salt = [UInt8](repeating: 0, count: saltLength)
        let head = Array(seed[0..<0x10])
        salt.replaceSubrange(0x00..<0x10, with: AES128.decrypt(head, key: saveKey))
        salt.replaceSubrange(0x10..<0x20, with: AES128.encrypt(head, key: saveKey))
        for index in 0..<0x10 { salt[index] ^= saveIV[index] }

        var tail = [UInt8](repeating: 0xFF, count: 0x10)
        tail.replaceSubrange(0..<(seedLength - 0x10), with: seed[0x10..<seedLength])
        for index in 0..<0x10 { salt[0x10 + index] ^= tail[index] }

        // Всё за пределами выведенных 20 байт обнуляется - дальше это обычный
        // HMAC: 0x36 даёт ipad, повторный xor на 0x6A превращает его в 0x5C.
        for index in seedLength..<saltLength { salt[index] = 0 }
        salt = salt.map { $0 ^ 0x36 }

        var payload = data
        for index in signatureOffset..<(signatureOffset + signatureLength)
        where index < payload.count {
            payload[index] = 0
        }

        var inner = Insecure.SHA1()
        inner.update(data: Data(salt))
        inner.update(data: Data(payload))
        let innerDigest = Array(inner.finalize())

        salt = salt.map { $0 ^ 0x6A }
        var outer = Insecure.SHA1()
        outer.update(data: Data(salt))
        outer.update(data: Data(innerDigest))
        return Array(outer.finalize())
    }

    /// Записанная подпись, посчитанная и сходятся ли.
    public static func verify(_ data: [UInt8]) -> (found: [UInt8], actual: [UInt8],
                                                   ok: Bool)? {
        guard let layout = layout(of: data),
              data.count >= layout.signature + signatureLength else { return nil }
        let seed = Array(data[layout.seed..<(layout.seed + seedLength)])
        let found = Array(data[layout.signature..<(layout.signature + signatureLength)])
        let actual = signature(data, seed: seed, at: layout.signature)
        return (found, actual, found == actual)
    }

    /// Пересчитывает подпись на месте. Salt seed сохраняется, если не задан.
    public static func resign(_ data: [UInt8], seed newSeed: [UInt8]? = nil) -> [UInt8]? {
        guard let layout = layout(of: data) else { return nil }
        var out = data
        if let newSeed {
            out.replaceSubrange(layout.seed..<(layout.seed + seedLength),
                                with: newSeed.prefix(seedLength))
        }
        let seed = Array(out[layout.seed..<(layout.seed + seedLength)])
        let value = signature(out, seed: seed, at: layout.signature)
        out.replaceSubrange(layout.signature..<(layout.signature + signatureLength),
                            with: value)
        return out
    }
}
