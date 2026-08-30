import Foundation

/// Сейв Final Fantasy VIII: контрольная сумма и разбор содержимого.
///
/// Раскладка блока по `hyne/src/SaveData.cpp`:
/// `0x180` сумма, `0x182` магия, `0x184` HEADER, `0x1D0` MAIN (4944 байта),
/// `0x1520` та же сумма второй раз.
public enum FF8 {
    static let checksumA = 0x180
    static let magicOffset = 0x182
    static let magicValues: Set<UInt16> = [0x08FF, 0x0FF8]
    static let mainOffset = 0x1D0
    static let mainSize = 4944
    static let checksumB = mainOffset + mainSize     // 0x1520

    static let gfCount = 16, gfSize = 68, gfBase = 464
    static let partyCount = 8, persoSize = 152, persoBase = 1552
    static let itemsBase = 3236, itemsOrderSize = 32, itemSlots = 198
    static let misc1 = 3188
    static let gilsOffset = misc1 + 24, partyOffset = misc1
    static let gameTimeOffset = 3664
    static let misc3 = 3808
    static let stepsOffset = misc3 + 4, battlesOffset = misc3 + 20
    static let magicSlots = 32
    static let descriptionOffset = 4, descriptionSize = 92

    /// Игра пишет в заголовок не больше 99:59 и дальше не растит.
    static let capHours = 99, capMinutes = 59

    /// Таблица CRC из hyne, взятая из общего с Python ресурса.
    ///
    /// Это CRC-16/CCITT с одним отличием: элемент 255 равен нулю вместо
    /// `0x1EF0`. Сгенерировать её по полиному нельзя - суммы разойдутся,
    /// как только индекс попадёт в 255, а на 4944 байтах это неизбежно.
    public struct Tables: Sendable {
        public let crc: [UInt16]
        public init() {
            let data = GameData("psxff8")
            crc = (0..<256).map { UInt16(data.number("CRC_TABLE", $0) ?? 0) }
        }
    }

    /// CRC-16 считается только по MAIN, а пишется в два места.
    public static func checksum(_ block: [UInt8], tables: Tables) -> UInt16 {
        var crc: UInt16 = 0xFFFF
        guard block.count >= mainOffset + mainSize else { return 0 }
        for byte in block[mainOffset..<(mainOffset + mainSize)] {
            let index = Int((crc >> 8) ^ UInt16(byte))
            crc = tables.crc[index] ^ (crc << 8)
        }
        return ~crc
    }

    public static func isFF8(_ block: [UInt8]) -> Bool {
        guard block.count >= checksumB + 2 else { return false }
        guard block[0] == 0x53 || block[0] == 0x73, block[1] == 0x43 else { return false }
        return magicValues.contains(read16(block[...], at: magicOffset))
    }

    public static func verify(_ block: [UInt8], tables: Tables) -> Bool {
        let first = read16(block[...], at: checksumA)
        let second = read16(block[...], at: checksumB)
        let actual = checksum(block, tables: tables)
        return first == second && second == actual
    }

    public struct Playtime: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case raw, freq, shown, matches, capped
            case asSeconds = "as_seconds"
            case asTicks = "as_ticks"
        }
        public var raw: UInt32
        public var freq: Int
        public var asSeconds: [String: Int]
        public var asTicks: [String: Int]
        public var shown: [Int]?
        public var matches: String?
        public var capped: Bool
    }

    public struct Character: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case name, exists, level, exp, hp, weapon, stats, magic, kills, gfs
            case hpMax = "hp_max"
        }
        public var name: String
        public var exists: Bool
        public var level: Int
        public var exp: UInt32
        public var hp: UInt16
        public var hpMax: UInt16
        public var weapon: String
        public var stats: [Int]
        public var magic: [[String]]
        public var kills: UInt16
        public var gfs: UInt16
    }

    public struct Guardian: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case name, exists, level, exp, hp, learned, learning, forgotten, kills
            case totalSlots = "total_slots"
        }
        public var name: String
        public var exists: Bool
        public var level: Int
        public var exp: UInt32
        public var hp: UInt16
        public var learned: [String]
        public var learning: [[String]]
        public var forgotten: [String]
        public var totalSlots: Int
        public var kills: UInt16
    }

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case description, playtime, gils, steps, battles, party
            case characters, guardians, items
            case checksumOK = "checksum_ok"
        }
        public var description: String
        public var playtime: Playtime
        public var gils: UInt32
        public var steps: UInt32
        public var battles: UInt32
        public var party: [String]
        public var characters: [Character]
        public var guardians: [Guardian]
        public var items: [[String]]
        public var checksumOK: Bool
    }

    /// Заголовок, который написала сама игра: `FF8[01]/32:54`.
    public static func description(_ block: [UInt8]) -> String {
        let end = min(block.count, descriptionOffset + descriptionSize)
        guard descriptionOffset < end else { return "" }
        return ShiftJIS.decode(block[descriptionOffset..<end])
    }

    /// Наигранное время.
    ///
    /// В сейве один 32-битный счётчик, и из кода hyne не следует, тики это
    /// или секунды. Считаем оба варианта и сверяем с заголовком, который
    /// написала сама игра.
    public static func playtime(_ block: [UInt8], region: String?) -> Playtime {
        let raw = read32(block[...], at: gameTimeOffset)
        let freq: UInt32 = region == "Europe" ? 50 : 60

        func split(_ value: UInt32) -> [String: Int] {
            ["hours": Int(value / 3600), "minutes": Int(value / 60 % 60),
             "seconds": Int(value % 60)]
        }
        let asSeconds = split(raw)
        let asTicks = split(raw / freq)

        var result = Playtime(raw: raw, freq: Int(freq), asSeconds: asSeconds,
                              asTicks: asTicks, shown: nil, matches: nil, capped: false)
        guard let shown = firstTime(in: description(block)) else { return result }
        result.shown = shown
        // Поле в заголовке двузначное и упирается в 99:59 - это ограничение,
        // а не переполнение: счётчик за ним продолжает расти.
        result.capped = shown == [capHours, capMinutes]
        for (name, value) in [("as_seconds", asSeconds), ("as_ticks", asTicks)] {
            if result.capped {
                if value["hours"]! >= capHours { result.matches = name; break }
            } else if [value["hours"]!, value["minutes"]!] == shown {
                result.matches = name
                break
            }
        }
        return result
    }

    /// Первое `часы:минуты` в строке, с любыми пробелами вокруг двоеточия.
    static func firstTime(in text: String) -> [Int]? {
        let chars = Array(text)
        var index = 0
        while index < chars.count {
            guard chars[index].isNumber else { index += 1; continue }
            var left = ""
            while index < chars.count, chars[index].isNumber {
                left.append(chars[index]); index += 1
            }
            var probe = index
            while probe < chars.count, chars[probe] == " " { probe += 1 }
            guard probe < chars.count, chars[probe] == ":" else { continue }
            probe += 1
            while probe < chars.count, chars[probe] == " " { probe += 1 }
            var right = ""
            while probe < chars.count, chars[probe].isNumber {
                right.append(chars[probe]); probe += 1
            }
            guard !right.isEmpty, let a = Int(left), let b = Int(right) else { continue }
            return [a, b]
        }
        return nil
    }

    public static func overview(_ block: [UInt8], region: String?,
                                data: GameData, tables: Tables) -> Overview? {
        guard isFF8(block) else { return nil }
        var party: [String] = []
        for offset in 0..<3 {
            let index = Int(block[partyOffset + offset])
            if let name = data.name("PARTY_ORDER", index) { party.append(name) }
        }
        return Overview(
            description: description(block),
            playtime: playtime(block, region: region),
            gils: read32(block[...], at: gilsOffset),
            steps: read32(block[...], at: stepsOffset),
            battles: read32(block[...], at: battlesOffset),
            party: party,
            characters: characters(block, data: data),
            guardians: guardians(block, data: data),
            items: items(block, data: data),
            checksumOK: verify(block, tables: tables))
    }

    static func characters(_ block: [UInt8], data: GameData) -> [Character] {
        var out: [Character] = []
        for index in 0..<partyCount {
            let base = persoBase + index * persoSize
            let exp = read32(block[...], at: base + 4)
            var magic: [[String]] = []
            for slot in 0..<magicSlots {
                let packed = read16(block[...], at: base + 16 + slot * 2)
                let spell = Int(packed & 0xFF), count = Int(packed >> 8)
                if spell != 0, count != 0 {
                    magic.append([data.name("MAGICS", spell) ?? "#\(spell)", String(count)])
                }
            }
            let weapon = Int(block[base + 9])
            out.append(Character(
                name: data.name("PARTY_ORDER", index) ?? "#\(index)",
                exists: block[base + 148] != 0,
                level: min(100, Int(exp) / 1000 + 1),
                exp: exp,
                hp: read16(block[...], at: base),
                hpMax: read16(block[...], at: base + 2),
                weapon: data.name("WEAPONS", weapon) ?? "#\(weapon)",
                stats: (0..<6).map { Int(block[base + 10 + $0]) },
                magic: magic,
                kills: read16(block[...], at: base + 144),
                gfs: read16(block[...], at: base + 88)))
        }
        return out
    }

    static func guardians(_ block: [UInt8], data: GameData) -> [Guardian] {
        let defaultDivisor = data.scalar("GF_LEVEL_DIVISOR_DEFAULT") ?? 500
        var out: [Guardian] = []
        for index in 0..<gfCount {
            let base = gfBase + index * gfSize
            let exp = read32(block[...], at: base + 12)
            let divisor = data.number("GF_LEVEL_DIVISOR", index) ?? defaultDivisor

            // Две разные индексации, и это легко перепутать: маска выученного
            // адресуется глобальным номером способности, а массив AP и маска
            // забытого - номером слота в списке этого Гардиана.
            let forgotten = Int(block[base + 65]) | Int(block[base + 66]) << 8
                | Int(block[base + 67]) << 16
            var learned: [String] = [], learning: [[String]] = [], lost: [String] = []
            let slots = data.row("GF_ABILITY_SLOTS", index)
            for (slot, ability) in slots.enumerated() {
                if ability == 0 { continue }
                let name = data.name("ABILITIES", ability) ?? "#\(ability)"
                if (block[base + 20 + ability / 8] >> (ability % 8)) & 1 == 1 {
                    learned.append(name)
                } else if (forgotten >> slot) & 1 == 1 {
                    lost.append(name)
                } else {
                    let points = Int(block[base + 36 + slot])
                    if points != 0 {
                        learning.append([name, String(points),
                                         String(data.number("ABILITY_AP_COST", ability) ?? 0)])
                    }
                }
            }
            out.append(Guardian(
                name: data.name("GF_NAMES", index) ?? "#\(index)",
                exists: block[base + 17] & 1 == 1,
                level: min(100, Int(exp) / divisor + 1),
                exp: exp,
                hp: read16(block[...], at: base + 18),
                learned: learned,
                learning: learning,
                forgotten: lost,
                totalSlots: slots.filter { $0 != 0 }.count,
                kills: read16(block[...], at: base + 60)))
        }
        return out
    }

    static func items(_ block: [UInt8], data: GameData) -> [[String]] {
        let base = itemsBase + itemsOrderSize
        var out: [[String]] = []
        for slot in 0..<itemSlots {
            let packed = read16(block[...], at: base + slot * 2)
            let item = Int(packed & 0xFF), count = Int(packed >> 8)
            if item != 0, count != 0 {
                out.append([data.name("ITEMS", item) ?? "#\(item)", String(count)])
            }
        }
        return out
    }
}
