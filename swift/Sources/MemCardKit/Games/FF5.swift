import Foundation

/// Разбор сейва Final Fantasy V (издание для PS1 из Final Fantasy Anthology).
///
/// Раскладка - из дизассемблировки `everything8215/ff5`: слот сохранения там
/// побайтовая копия куска WRAM `$7E:0500-$7E:0AFF`.
///
/// **В блоке карты памяти PS1 слот SNES начинается с `0x300`**, а не с `0x200`,
/// как у FF6: перед ним лежат ещё `0x100` байт превью для меню загрузки.
/// Реверс по якорю сначала находит именно превью - поля там настоящие, но
/// раскладка другая, и дальше по ней ничего не сходится.
public enum FF5 {
    public static let serials: Set<String> = [
        "SLUS-00879", "SCES-13840", "SLPS-01340", "SLPM-86140",
    ]

    static let slot = 0x300            // слот SNES внутри блока PS1

    // Смещения внутри слота
    static let unitsAt = 0x000, unitSize = 0x50, unitCount = 4
    static let itemIDs = 0x140, itemCounts = 0x240
    static let money = 0x447           // 3 байта
    static let playtimeAt = 0x44A      // u32, кадры 60 Гц
    static let kills = 0x44E           // u16
    static let namesAt = 0x490         // 6 записей по 6 байт
    static let battles = 0x4C0, saveCount = 0x4C2
    static let chestsAt = 0x4D4        // 32 байта = 256 сундуков
    static let mapIndex = 0x5D4, worldIndex = 0x5D6

    // Внутри записи персонажа
    static let uWho = 0x00             // младшие три бита - номер героя в ростере
    static let uJob = 0x01, uLevel = 0x02, uExp = 0x03
    static let uHP = 0x06, uMP = 0x0A, uGear = 0x0E
    static let uJobLevel = 0x3A, uABP = 0x3B

    static let gearSlots = [L.t("helmet"), L.t("armor"), L.t("accessory"), L.t("right shield"),
                            L.t("left shield"), L.t("right weapon"), L.t("left weapon")]
    static let nameLength = 6
    static let nameEnd: UInt8 = 0xFF
    static let frames: UInt32 = 60

    public struct Unit: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case slot, who, name, job, level, exp, hp, mp, abp, gear
            case jobLevel = "job_level"
        }
        public var slot: Int
        public var who: Int
        public var name: String
        public var job: String
        public var level: Int
        public var exp: Int
        public var hp: [Int]
        public var mp: [Int]
        public var jobLevel: Int
        public var abp: UInt16
        public var gear: [[String]]
    }

    public struct Overview: Codable, Sendable {
        public var playtime: [Int]
        public var money: Int
        public var party: [Unit]
        public var roster: [String]
        public var inventory: [[String]]
        public var kills: UInt16
        public var battles: UInt16
        public var saves: UInt16
        public var chests: Int
        public var map: UInt16
        public var world: UInt16
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

    static func u24(_ block: [UInt8], at offset: Int) -> Int {
        guard offset + 2 < block.count else { return 0 }
        return Int(block[offset]) | Int(block[offset + 1]) << 8
            | Int(block[offset + 2]) << 16
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        guard block.count >= slot + 0x600 else { return nil }
        let slice = block[...]
        let total = read32(slice, at: slot + playtimeAt) / frames
        let roster = names(block, data: data)
        return Overview(
            playtime: [Int(total) / 3600, Int(total) / 60 % 60, Int(total) % 60],
            money: u24(block, at: slot + money),
            party: party(block, roster: roster, data: data),
            roster: roster.filter { !$0.isEmpty },
            inventory: inventory(block, data: data),
            kills: read16(slice, at: slot + kills),
            battles: read16(slice, at: slot + battles),
            saves: read16(slice, at: slot + saveCount),
            chests: chests(block),
            map: read16(slice, at: slot + mapIndex),
            world: read16(slice, at: slot + worldIndex))
    }

    static func names(_ block: [UInt8], data: GameData) -> [String] {
        (0..<6).map { index in
            let at = slot + namesAt + index * nameLength
            return decodeName(block[at..<(at + nameLength)], data)
        }
    }

    static func party(_ block: [UInt8], roster: [String], data: GameData) -> [Unit] {
        var out: [Unit] = []
        let slice = block[...]
        for index in 0..<unitCount {
            let at = slot + unitsAt + index * unitSize
            guard at + unitSize <= block.count else { break }
            var gear: [[String]] = []
            for (n, name) in gearSlots.enumerated() where block[at + uGear + n] != 0 {
                gear.append([name, item(Int(block[at + uGear + n]), data)])
            }
            // Порядок записей отряда не совпадает с ростером: кто именно
            // в слоте, говорят младшие три бита флагов.
            let who = Int(block[at + uWho]) & 0x07
            let jobID = Int(block[at + uJob])
            out.append(Unit(
                slot: index,
                who: who,
                name: who < roster.count && !roster[who].isEmpty ? roster[who] : "#\(who)",
                job: data.name("JOBS", jobID) ?? "#\(jobID)",
                level: Int(block[at + uLevel]),
                exp: u24(block, at: at + uExp),
                hp: [Int(read16(slice, at: at + uHP)),
                     Int(read16(slice, at: at + uHP + 2))],
                mp: [Int(read16(slice, at: at + uMP)),
                     Int(read16(slice, at: at + uMP + 2))],
                jobLevel: Int(block[at + uJobLevel]),
                abp: read16(slice, at: at + uABP),
                gear: gear))
        }
        return out
    }

    static func item(_ index: Int, _ data: GameData) -> String {
        data.name("ITEMS", index) ?? "#\(index)"
    }

    static func inventory(_ block: [UInt8], data: GameData) -> [[String]] {
        var out: [[String]] = []
        for at in 0..<256 {
            let count = block[slot + itemCounts + at]
            if count == 0 { continue }
            out.append([item(Int(block[slot + itemIDs + at]), data), String(count)])
        }
        return out
    }

    /// Сколько сундуков открыто - из них игра считает процент прохождения.
    static func chests(_ block: [UInt8]) -> Int {
        (0..<32).reduce(0) { $0 + block[slot + chestsAt + $1].nonzeroBitCount }
    }
}
