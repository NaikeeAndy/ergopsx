import Foundation

/// Разбор сейва Final Fantasy VI (издание для PS1 из Final Fantasy Anthology).
///
/// Шаблона для PS1 не существует - есть только для SNES. Но PS1-порт хранит
/// сейв SNES дословно, со смещением `0x200` от начала блока. Отличие одно:
/// таблица букв сдвинута на `-0x60`.
public enum FF6 {
    /// Валидатор шаблона перечисляет только SNES и GBA, поэтому серийники PS1
    /// взяты из базы названий. Японские издания используют кану - её тут нет,
    /// сверять не на чем.
    public static let serials: Set<String> = [
        "SLUS-00900", "SCES-03828", "SCPS-45387", "SLPM-86198", "SLPS-01950",
    ]

    static let base = 0x200            // слот SNES внутри блока PS1
    static let unit = 0x25, units = 16
    static let money = 0x260           // u24
    static let playtimeAt = 0x263      // три отдельных байта: часы, минуты, секунды
    static let steps = 0x266           // u16
    static let itemIDs = 0x269, itemCounts = 0x369, itemSlots = 256
    static let espersAt = 0x469        // битовая карта
    static let magicAt = 0x46E
    /// Гого и Умаро магию не учат, дальше идёт Sword Tech - шаг в 16 записей
    /// залез бы в чужие данные.
    static let magicUnits = 12, magicSpells = 54
    static let saveCount = 0x7C7
    static let locationAt = 0x964      // u16, значащих 9 бит

    // Внутри записи персонажа
    static let uName = 0x02, uLevel = 0x08
    static let uHP = 0x09, uHPMax = 0x0B
    static let uMP = 0x0D, uMPMax = 0x0F
    static let uExp = 0x11             // u24
    static let uAbilities = 0x16, uVigor = 0x1A, uGear = 0x1F

    static let gearSlots = [L.t("right hand"), L.t("left hand"), L.t("head"), L.t("body"),
                            L.t("relic 1"), L.t("relic 2")]
    static let empty: UInt8 = 0xFF

    public struct Spell: Codable, Sendable {
        public var name: String
        public var learned: Bool
        public var percent: Int
    }

    public struct Unit: Codable, Sendable {
        public var slot: Int
        public var who: String
        public var name: String
        public var recruited: Bool
        public var level: Int
        public var exp: Int
        public var hp: [Int]
        public var mp: [Int]
        public var stats: [Int]
        public var abilities: [String]
        public var gear: [[String]]
        public var magic: [Spell]
    }

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case playtime, gil, steps, saves, location, party, inventory, espers
            case notRecruited = "not_recruited"
        }
        public var playtime: [Int]
        public var gil: Int
        public var steps: UInt16
        public var saves: Int
        public var location: String
        public var party: [Unit]
        public var notRecruited: Int
        public var inventory: [[String]]
        public var espers: [String]
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    /// Имя персонажа. Таблица та же, что у SNES, но байты сдвинуты на `-0x60`.
    public static func decodeName(_ raw: ArraySlice<UInt8>, _ data: GameData) -> String {
        var out = ""
        for byte in raw {
            if byte == empty { break }
            out += data.name("LETTERS", Int(byte) + 0x60) ?? ""
        }
        return out.trimmingCharacters(in: .whitespaces)
    }

    static func u24(_ block: [UInt8], at offset: Int) -> Int {
        guard offset + 2 < block.count else { return 0 }
        return Int(block[offset]) | Int(block[offset + 1]) << 8
            | Int(block[offset + 2]) << 16
    }

    static func item(_ index: Int, _ data: GameData) -> String {
        data.name("ITEMS", index) ?? String(format: "#0x%02x", index)
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        guard block.count >= base + 0xA00 else { return nil }
        let slice = block[...]
        let place = Int(read16(slice, at: base + locationAt)) & 0x1FF
        let all = (0..<units).compactMap { self.unit(block, index: $0, data: data) }
        return Overview(
            playtime: [Int(block[base + playtimeAt]), Int(block[base + playtimeAt + 1]),
                       Int(block[base + playtimeAt + 2])],
            gil: u24(block, at: base + money),
            steps: read16(slice, at: base + steps),
            saves: Int(block[base + saveCount]),
            location: data.name("LOCATIONS", place) ?? "#\(place)",
            party: all.filter(\.recruited),
            notRecruited: all.filter { !$0.recruited }.count,
            inventory: inventory(block, data: data),
            espers: espers(block, data: data))
    }

    static func unit(_ block: [UInt8], index: Int, data: GameData) -> Unit? {
        let at = base + index * unit
        guard at + self.unit <= block.count else { return nil }
        let name = decodeName(block[(at + uName)..<(at + uName + 6)], data)
        if name.isEmpty { return nil }

        var gear: [[String]] = []
        for (n, slot) in gearSlots.enumerated() where block[at + uGear + n] != empty {
            gear.append([slot, item(Int(block[at + uGear + n]), data)])
        }
        let abilities = (0..<4).compactMap { n -> String? in
            let name = data.name("ABILITIES", Int(block[at + uAbilities + n])) ?? ""
            return (name.isEmpty || name == "-") ? nil : name
        }
        var spells: [Spell] = []
        if index < magicUnits {
            for spell in 0..<magicSpells {
                let value = Int(block[base + magicAt + index * magicSpells + spell])
                if value == 0 { continue }
                spells.append(Spell(name: data.name("MAGIC", spell) ?? "#\(spell)",
                                    learned: value >= 100,
                                    percent: value >= 100 ? 100 : value))
            }
        }
        let slice = block[...]
        return Unit(
            slot: index,
            who: data.name("CHARACTERS", Int(block[at])) ?? "#\(block[at])",
            name: name,
            // Не завербованных игра держит в отряде с именем из одних знаков
            // вопроса - это её собственная заглушка, а не сбой чтения.
            recruited: Set(name) != Set("?"),
            level: Int(block[at + uLevel]),
            exp: u24(block, at: at + uExp),
            // Максимум HP и MP - четырнадцатибитные: старшие два бита заняты
            // флагами снаряжения, без маски выходит 49836 вместо 684.
            hp: [Int(read16(slice, at: at + uHP)),
                 Int(read16(slice, at: at + uHPMax) & 0x3FFF)],
            mp: [Int(read16(slice, at: at + uMP)),
                 Int(read16(slice, at: at + uMPMax) & 0x3FFF)],
            stats: (0..<4).map { Int(block[at + uVigor + $0]) },
            abilities: abilities,
            gear: gear,
            magic: spells)
    }

    static func inventory(_ block: [UInt8], data: GameData) -> [[String]] {
        var out: [[String]] = []
        for slot in 0..<itemSlots {
            let index = block[base + itemIDs + slot]
            let count = block[base + itemCounts + slot]
            if index == empty || count == 0 { continue }
            out.append([item(Int(index), data), String(count)])
        }
        return out
    }

    static func espers(_ block: [UInt8], data: GameData) -> [String] {
        data.keys("ESPERS").compactMap { index in
            let at = base + espersAt + index / 8
            guard at < block.count, (block[at] >> (index % 8)) & 1 == 1 else { return nil }
            return data.name("ESPERS", index)
        }
    }
}
