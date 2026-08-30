import Foundation

/// Разбор сейва Final Fantasy IX.
///
/// Смещения - от начала блока сейва, источник: game-tools-collection,
/// шаблон final-fantasy-ix.
public enum FF9 {
    public static let serials: Set<String> = [
        "SLUS-01251", "SLUS-01295", "SLUS-01296", "SLUS-01297",
        "SLES-02965", "SLES-12965", "SLES-22965", "SLES-32965",
        "SLPS-02000", "SLPS-02001", "SLPS-02002", "SLPS-02003",
    ]

    /// Шаблон называет это секундами, но подпись, которую пишет сама игра,
    /// сходится только при делении на 60: счётчик в кадрах.
    static let playtime = 0x12C
    static let framesPerSecond: UInt32 = 60
    static let location = 0x1A0
    static let gil = 0xEE8

    static let partyBase = 0x9D0
    static let partySize = 0x90
    static let partyCount = 9
    static let nameLength = 0x0B
    static let uLevel = 0x00B      // смещения ниже - от начала записи бойца
    static let uExperience = 0x00C
    static let uHPCur = 0x010, uHPMax = 0x018
    static let uMPCur = 0x012, uMPMax = 0x01A
    static let uTrance = 0x020

    /// Диск лежит битовой маской, а не числом: 1, 2, 4, 8 - это диски 1..4.
    /// Из-за этого его не найти перебором значений 1..4.
    static let disc = 0x104
    static let discs: [UInt8: Int] = [1: 1, 2: 2, 4: 3, 8: 4]

    /// Экипировка, смещения от начала записи бойца. Наручи и тело шаблон
    /// не подписывает, но они лежат между головой и аксессуаром.
    static let gearSlots: [(offset: Int, label: String, table: String)] = [
        (0x39, L.t("оружие", "weapon"), "WEAPONS"), (0x3A, L.t("голова", "head"), "HEAD_GEARS"),
        (0x3B, L.t("наручи", "armlet"), "ARM_GEARS"), (0x3C, L.t("тело", "body"), "BODIES"),
        (0x3D, L.t("аксессуар", "accessory"), "ACCESSORIES"),
    ]
    static let emptyGear: Set<UInt8> = [0x00, 0xFF]

    static let inventoryBase = 0xF20
    static let inventorySlots = 255
    static let nameEnd: UInt8 = 0xFF

    public struct Unit: Codable, Sendable {
        public var slot: Int
        public var who: String
        public var name: String
        public var level: Int
        public var exp: UInt32
        public var hp: [UInt16]
        public var mp: [UInt16]
        public var trance: Int
        public var gear: [[String]]
    }

    public struct Overview: Codable, Sendable {
        // Имена полей повторяют старый движок - по ним идёт сверка.
        enum CodingKeys: String, CodingKey {
            case playtime, gil, location, disc, party, inventory
            case playtimeRaw = "playtime_raw"
        }
        public var playtime: [Int]
        public var playtimeRaw: UInt32
        public var gil: UInt32
        public var location: UInt16
        public var disc: Int?
        public var party: [Unit]
        public var inventory: [[String]]
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    public static func decodeName(_ raw: ArraySlice<UInt8>, _ data: GameData) -> String {
        var out = ""
        for byte in raw {
            if byte == nameEnd { break }
            out += data.name("LETTERS", Int(byte)) ?? ""
        }
        return out.trimmingCharacters(in: .whitespaces)
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        guard block.count >= PSX.block else { return nil }
        let slice = block[...]
        let seconds = read32(slice, at: playtime) / framesPerSecond
        return Overview(
            playtime: [Int(seconds) / 3600, Int(seconds) / 60 % 60, Int(seconds) % 60],
            playtimeRaw: seconds,
            gil: read32(slice, at: gil),
            location: read16(slice, at: location),
            disc: discs[block[disc]],
            party: party(block, data: data),
            inventory: inventory(block, data: data))
    }

    static func party(_ block: [UInt8], data: GameData) -> [Unit] {
        var out: [Unit] = []
        let slice = block[...]
        for index in 0..<partyCount {
            let base = partyBase + index * partySize
            guard base + partySize <= block.count else { continue }
            let level = Int(block[base + uLevel])
            let hpMax = read16(slice, at: base + uHPMax)
            guard level != 0, hpMax != 0 else { continue }
            out.append(Unit(
                slot: index,
                who: data.name("CHARACTERS", index) ?? "#\(index)",
                name: decodeName(block[base..<(base + nameLength)], data),
                level: level,
                exp: read32(slice, at: base + uExperience),
                hp: [read16(slice, at: base + uHPCur), hpMax],
                mp: [read16(slice, at: base + uMPCur), read16(slice, at: base + uMPMax)],
                trance: Int(block[base + uTrance]),
                gear: gear(block, base: base, data: data)))
        }
        return out
    }

    static func gear(_ block: [UInt8], base: Int, data: GameData) -> [[String]] {
        var out: [[String]] = []
        for slot in gearSlots {
            let value = block[base + slot.offset]
            if emptyGear.contains(value) { continue }
            // Самоцветы (Diamond, Ruby, Peridot) тоже надеваются как аксессуары,
            // но лежат в общем справочнике предметов, а не в ACCESSORIES.
            let name = data.name([slot.table, "ALL_GEAR", "ITEMS"], Int(value))
            out.append([slot.label, name ?? "#\(value)"])
        }
        return out
    }

    static func inventory(_ block: [UInt8], data: GameData) -> [[String]] {
        var out: [[String]] = []
        for slot in 0..<inventorySlots {
            let base = inventoryBase + slot * 2
            guard base + 1 < block.count else { break }
            let item = block[base], count = block[base + 1]
            if item == 0xFF || count == 0 { continue }
            let hex = String(format: "#0x%02x", Int(item))
            out.append([data.name("ITEMS", Int(item)) ?? hex, String(count)])
        }
        return out
    }
}
