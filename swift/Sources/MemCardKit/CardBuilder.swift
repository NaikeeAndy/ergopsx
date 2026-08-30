import Foundation

/// Сборка образа карты памяти PS1 из отдельных сейвов.
///
/// Раскладка выяснена по настоящим картам, а не по описанию:
/// - продолжение многоблочного сейва - состояние `0x53`, нулевой размер,
///   пустое имя;
/// - поле «следующий блок» считает от нуля, то есть номер блока минус один
///   (у Suikoden блок 1 указывает на `0x0001`, а это блок 2);
/// - резервная область фреймов 16..62 одинакова у всех карт коллекции.
public enum CardBuilder {
    public static let cardSize = PSX.block * 16     // 131072
    static let end: UInt16 = 0xFFFF

    public struct Placement: Sendable {
        public var name: String
        public var origin: String
        public var block: Int
        public var blocks: Int
        public var restored: Bool
    }

    public struct Result: Sendable {
        public var image: [UInt8]
        public var layout: [Placement]
        /// Побайтовые дубли, отброшенные молча.
        public var dropped: [(name: String, origin: String)]
    }

    public enum Failure: Error, CustomStringConvertible {
        case duplicateName(String, String, String)
        case tooManyBlocks(Int)
        case badSize(Int)
        case noMagic
        case badChecksum([Int])

        public var description: String {
            switch self {
            case let .duplicateName(name, first, second):
                L.t("два разных сейва с одним именем '\(name)': \(first) и \(second). ", "two different saves share the name '\(name)': \(first) and \(second). ")
                + L.t("Игра находит сейв по имени и различить их не сможет - оставьте один", "the game finds saves by name and cannot tell them apart — keep one")
            case let .tooManyBlocks(need):
                L.t("нужно \(need) блоков, а на карте только \(PSX.slots)", "\(need) blocks needed, the card holds only \(PSX.slots)")
            case let .badSize(size):
                L.t("размер \(size), а должен быть \(cardSize)", "size is \(size), expected \(cardSize)")
            case .noMagic:
                L.t("нет магии 'MC' в начале", "no 'MC' magic at the start")
            case let .badChecksum(frames):
                L.t("неверная контрольная сумма у фреймов \(frames)", "bad checksum in frames \(frames)")
            }
        }
    }

    static func xor(_ frame: ArraySlice<UInt8>) -> UInt8 {
        frame.prefix(PSX.frame - 1).reduce(0, ^)
    }

    /// Дописывает контрольный байт XOR в конец фрейма.
    static func seal(_ frame: [UInt8]) -> [UInt8] {
        var out = frame
        out[PSX.frame - 1] = xor(out[...])
        return out
    }

    static func headerFrame() -> [UInt8] {
        var frame = [UInt8](repeating: 0, count: PSX.frame)
        frame[0] = 0x4D; frame[1] = 0x43           // "MC"
        return seal(frame)
    }

    static func freeFrame() -> [UInt8] {
        var frame = [UInt8](repeating: 0, count: PSX.frame)
        frame[0] = SlotState.free.rawValue
        write16(&frame, at: 8, end)
        return seal(frame)
    }

    /// Фреймы 16..63: список сбойных секторов и проверочный фрейм.
    static func reserve() -> [UInt8] {
        var out: [UInt8] = []
        for _ in 0..<20 {                          // 16..35 - список сбойных
            var frame = [UInt8](repeating: 0, count: PSX.frame)
            write32(&frame, at: 0, 0xFFFFFFFF)
            write16(&frame, at: 8, end)
            out += seal(frame)
        }
        out += [UInt8](repeating: 0, count: PSX.frame * 27)   // 36..62 - пусто
        out += headerFrame()                                  // 63 - проверочный
        return out
    }

    public static func build(_ entries: [Save]) throws -> Result {
        // Консоль и игры находят сейв по имени, поэтому двух одинаковых имён
        // на карте быть не должно. Побайтовый дубль отбрасываем молча - он
        // ничего не теряет; а вот разные сейвы под одним именем выбирать
        // за пользователя нельзя.
        var seen: [String: Save] = [:]
        var unique: [Save] = []
        var dropped: [(name: String, origin: String)] = []
        for entry in entries {
            let key = entry.name
            guard let first = seen[key] else {
                seen[key] = entry
                unique.append(entry)
                continue
            }
            if first.blocks == entry.blocks {
                dropped.append((key, entry.origin))
                continue
            }
            throw Failure.duplicateName(key, first.origin, entry.origin)
        }

        let need = unique.reduce(0) { $0 + $1.blocks.count }
        guard need <= PSX.slots else { throw Failure.tooManyBlocks(need) }

        var frames = (0..<PSX.slots).map { _ in freeFrame() }
        var blocks = (0..<PSX.slots).map { _ in [UInt8](repeating: 0, count: PSX.block) }
        var layout: [Placement] = []
        var cursor = 0

        for entry in unique {
            let chain = Array(cursor..<(cursor + entry.blocks.count))
            let size = UInt32(entry.blocks.count * PSX.block)
            for (position, slot) in chain.enumerated() {
                var frame = [UInt8](repeating: 0, count: PSX.frame)
                blocks[slot] = entry.blocks[position]
                if position == 0 {
                    frame[0] = SlotState.save.rawValue
                    write32(&frame, at: 4, size)
                    // Ссылка считает от нуля: номер блока минус один.
                    write16(&frame, at: 8, chain.count > 1 ? UInt16(chain[1]) : end)
                    var name = Array(entry.rawName.prefix(20))
                    name += [UInt8](repeating: 0, count: 20 - name.count)
                    frame.replaceSubrange(10..<30, with: name)
                } else {
                    let last = position == chain.count - 1
                    frame[0] = (last ? SlotState.linkEnd : SlotState.link).rawValue
                    write16(&frame, at: 8, last ? end : UInt16(chain[position + 1]))
                }
                frames[slot] = seal(frame)
            }
            layout.append(Placement(name: entry.name, origin: entry.origin,
                                    block: chain[0] + 1, blocks: chain.count,
                                    restored: entry.isDeleted))
            cursor += chain.count
        }

        var card = headerFrame()
        for frame in frames { card += frame }
        card += reserve()
        for block in blocks { card += block }
        precondition(card.count == cardSize, L.t("получилось \(card.count) байт", "got \(card.count) bytes"))
        return Result(image: card, layout: layout, dropped: dropped)
    }

    /// Разбирает готовый образ и проверяет контрольные байты всех 64 фреймов.
    public static func check(_ card: [UInt8]) throws -> [Save] {
        guard card.count == cardSize else { throw Failure.badSize(card.count) }
        guard card[0] == 0x4D, card[1] == 0x43 else { throw Failure.noMagic }
        let bad = (0..<64).filter { n in
            let start = PSX.frame * n
            return xor(card[start..<(start + PSX.frame)]) != card[start + PSX.frame - 1]
        }
        guard bad.isEmpty else { throw Failure.badChecksum(bad) }
        return CardImage(card)?.saves(origin: L.t("образ", "image")) ?? []
    }

    /// Обёртка DexDrive: заголовок на 3904 байта.
    public static func asGME(_ card: [UInt8]) -> [UInt8] {
        var head = [UInt8](repeating: 0, count: 3904)
        for (index, byte) in Array("123-456-STD".utf8).enumerated() { head[index] = byte }
        head[18] = 0x1
        head[20] = 0x1
        head[21] = 0x4D
        return head + card
    }
}

@inline(__always)
func write16(_ bytes: inout [UInt8], at offset: Int, _ value: UInt16) {
    bytes[offset] = UInt8(value & 0xFF)
    bytes[offset + 1] = UInt8(value >> 8)
}

@inline(__always)
func write32(_ bytes: inout [UInt8], at offset: Int, _ value: UInt32) {
    bytes[offset] = UInt8(value & 0xFF)
    bytes[offset + 1] = UInt8((value >> 8) & 0xFF)
    bytes[offset + 2] = UInt8((value >> 16) & 0xFF)
    bytes[offset + 3] = UInt8((value >> 24) & 0xFF)
}
