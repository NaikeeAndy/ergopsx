import Foundation

/// Разбор сейва Final Fantasy VII.
///
/// Раскладка - по `ff7tk` (`FF7Save_Types.h`), там каждое поле подписано
/// hex-смещением прямо в комментарии. Названия предметов и локаций - из
/// шаблона game-tools-collection: в выжимке ff7tk их нет, они подгружаются
/// из ресурсов Qt.
///
/// Слот занимает `0x10F4` байта и начинается с `0x200` блока - проверено
/// якорем: подпись сейва говорит `FF7/SAVE01/00:15`, и по этой базе время
/// выходит 0:15:17.
public enum FF7 {
    public static let serials: Set<String> = [
        "SCUS-94163", "SCUS-94164", "SCUS-94165",
        "SCES-00867", "SCES-00868", "SCES-00869",
        "SLPS-00700", "SLPS-00701", "SLPS-00702",
        "SLES-00867", "SLES-00868", "SLES-00869",
    ]

    static let slot = 0x200, slotSize = 0x10F4

    // Смещения от начала слота.
    static let desc = 0x0004           // FF7DESC, 68 байт
    static let dLevel = 0x00, dName = 0x04, dLocation = 0x24

    static let chars = 0x0054, charSize = 0x84
    static let materiaAt = 0x077C, materiaSlots = 200
    static let materiaStolen = 0x0A9C, materiaStolenSlots = 48
    static let materiaSize = 4
    static let materiaEmpty: UInt8 = 0xFF
    /// У персонажа 16 гнёзд: восемь в оружии, восемь в броне.
    static let cMateria = 0x0040, cMateriaSlots = 16
    static let masteredAP = 0xFFFFFF
    static let itemsAt = 0x04FC, itemSlots = 320
    static let gil = 0x0B7C, timeAt = 0x0B80
    static let locationID = 0x0B96
    static let battles = 0x0BBC, runs = 0x0BBE

    // Смещения внутри записи персонажа.
    static let cID = 0x00, cLevel = 0x01, cStats = 0x02
    static let cLimitLevel = 0x0E, cName = 0x10
    static let cWeapon = 0x1C, cArmor = 0x1D, cAccessory = 0x1E
    static let cKills = 0x24, cHP = 0x2C, cHPBase = 0x2E

    static let nameEnd: UInt8 = 0xFF
    /// Количество предмета лежит в старших семи битах, номер - в младших девяти.
    static let itemMask = 0x1FF, itemShift = 9

    public struct Materia: Codable, Sendable {
        public var name: String
        public var kind: String
        public var ap: Int
        public var stars: Int
        public var total: Int
        public var mastered: Bool
    }

    public struct Character: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case who, name, level, stats, hp, kills, weapon, armor, accessory, materia
            case limitLevel = "limit_level"
        }
        public var who: String
        public var name: String
        public var level: Int
        public var stats: [Int]
        public var hp: [Int]
        public var kills: UInt16
        public var limitLevel: Int
        public var weapon: String
        public var armor: String
        public var accessory: String
        public var materia: [MateriaSlot]
    }

    public struct MateriaSlot: Codable, Sendable {
        public var slot: String
        public var materia: Materia
    }

    public struct Item: Codable, Sendable {
        public var name: String
        public var count: Int
        public var kind: String
    }

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case leader, level, playtime, gil, location, battles, runs
            case characters, inventory, materia
            case playtimeRaw = "playtime_raw"
            case locationText = "location_text"
            case materiaStolen = "materia_stolen"
        }
        public var leader: String
        public var level: Int
        public var playtime: [Int]
        public var playtimeRaw: UInt32
        public var gil: UInt32
        public var location: String
        public var locationText: String
        public var battles: UInt16
        public var runs: UInt16
        public var characters: [Character]
        public var inventory: [Item]
        public var materia: [Materia]
        public var materiaStolen: [Materia]
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

    /// Одно гнездо: номер, AP (24 бита) и уровень звёзд по порогам.
    static func materia(_ block: [UInt8], at offset: Int, data: GameData) -> Materia? {
        guard offset + 3 < block.count else { return nil }
        let ident = block[offset]
        if ident == materiaEmpty { return nil }
        let ap = Int(block[offset + 1]) | Int(block[offset + 2]) << 8
            | Int(block[offset + 3]) << 16
        let thresholds = data.row("MATERIA_AP", Int(ident))
        return Materia(
            name: data.name("MATERIA", Int(ident)) ?? String(format: "#0x%02x", Int(ident)),
            kind: data.name("MATERIA_TYPE", Int(ident)) ?? "",
            ap: ap,
            stars: thresholds.filter { ap >= $0 }.count,
            total: thresholds.count,
            mastered: ap >= masteredAP
                || (thresholds.count > 1 && ap >= thresholds[thresholds.count - 1]))
    }

    static func materiaList(_ block: [UInt8], base: Int, count: Int,
                            data: GameData) -> [Materia] {
        (0..<count).compactMap {
            materia(block, at: slot + base + $0 * materiaSize, data: data)
        }
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        guard block.count >= slot + slotSize else { return nil }
        let at = slot + desc
        let seconds = read32(block[...], at: slot + timeAt)
        let place = Int(read16(block[...], at: slot + locationID))
        return Overview(
            leader: decodeName(block[(at + dName)..<(at + dName + 16)], data),
            level: Int(block[at + dLevel]),
            playtime: [Int(seconds) / 3600, Int(seconds) / 60 % 60, Int(seconds) % 60],
            playtimeRaw: seconds,
            gil: read32(block[...], at: slot + gil),
            location: data.name("LOCATIONS", place) ?? String(format: "#0x%04x", place),
            locationText: decodeName(block[(at + dLocation)..<(at + dLocation + 32)], data),
            battles: read16(block[...], at: slot + battles),
            runs: read16(block[...], at: slot + runs),
            characters: characters(block, data: data),
            inventory: inventory(block, data: data),
            materia: materiaList(block, base: materiaAt, count: materiaSlots, data: data),
            materiaStolen: materiaList(block, base: materiaStolen,
                                       count: materiaStolenSlots, data: data))
    }

    static func characters(_ block: [UInt8], data: GameData) -> [Character] {
        var out: [Character] = []
        for index in 0..<9 {
            let base = slot + chars + index * charSize
            guard base + charSize <= block.count else { break }
            let ident = block[base + cID]
            if ident == 0xFF { continue }
            var worn: [MateriaSlot] = []
            for at in 0..<cMateriaSlots {
                guard let found = materia(block, at: base + cMateria + at * materiaSize,
                                          data: data) else { continue }
                worn.append(MateriaSlot(slot: at < 8 ? L.t("weapon") : L.t("armor"), materia: found))
            }
            out.append(Character(
                who: data.name("CHARACTERS", Int(ident)) ?? "#\(ident)",
                name: decodeName(block[(base + cName)..<(base + cName + 12)], data),
                level: Int(block[base + cLevel]),
                stats: (0..<6).map { Int(block[base + cStats + $0]) },
                hp: [Int(read16(block[...], at: base + cHP)),
                     Int(read16(block[...], at: base + cHPBase))],
                kills: read16(block[...], at: base + cKills),
                limitLevel: Int(block[base + cLimitLevel]),
                weapon: data.name("WEAPONS", Int(block[base + cWeapon]))
                    ?? "#\(block[base + cWeapon])",
                armor: data.name("ARMORS", Int(block[base + cArmor]))
                    ?? "#\(block[base + cArmor])",
                accessory: data.name("ACCESSORIES", Int(block[base + cAccessory])) ?? "",
                materia: worn))
        }
        return out
    }

    static func inventory(_ block: [UInt8], data: GameData) -> [Item] {
        var out: [Item] = []
        for at in 0..<itemSlots {
            let packed = Int(read16(block[...], at: slot + itemsAt + at * 2))
            if packed == 0xFFFF { continue }
            let item = packed & itemMask, count = packed >> itemShift
            if count == 0 { continue }
            out.append(Item(name: data.name("ITEMS", item) ?? "#\(item)",
                            count: count,
                            kind: data.name("ITEM_KIND", item) ?? L.t("Items")))
        }
        return out
    }
}
