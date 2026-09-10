import Foundation

/// Разбор сейва Castlevania: Symphony of the Night.
///
/// Смещения - от начала данных игры, источник: game-tools-collection,
/// шаблон castlevania-symphony-of-the-night.
public enum SotN {
    public static let serials: Set<String> = [
        "SLUS-00067", "SLES-00524", "SLPM-86023", "SCPS-45196",
    ]

    // Где начинаются данные, зависит от числа кадров иконки, и у SotN
    // в коллекции есть сейвы обоих видов: с тремя кадрами (данные с 0x200)
    // и с одним (с 0x100). Жёсткая поправка читала однокадровые мимо -
    // процент карты выходил нулевым при подписи «3%».

    static let progression = 0x124, location = 0x128
    /// uint16, делится на 9.42 - так игра показывает проценты.
    static let mapRate = 0x12A
    static let character = 0x130

    static let hpCur = 0x374, hpMax = 0x378
    static let heartsCur = 0x37C, heartsMax = 0x380
    static let mpCur = 0x384, mpMax = 0x388

    static let level = 0x3BC, experience = 0x3C0, gold = 0x3C4, kills = 0x3C8
    static let playH = 0x404, playM = 0x408, playS = 0x40C

    /// Экипировка: семь слотов подряд по четыре байта.
    static let gearSlots: [(Int, String)] = [
        (0x3D4, L.t("right hand")), (0x3D8, L.t("left hand")), (0x3DC, L.t("head")),
        (0x3E0, L.t("body")), (0x3E4, L.t("cloak")), (0x3E8, L.t("accessory 1")),
        (0x3EC, L.t("accessory 2")),
    ]
    /// В руках свой список предметов, не общий.
    static let handSlots: Set<Int> = [0x3D4, 0x3D8]

    static let spellsBase = 0x156, spellSlots = 8
    /// **Списков два, подряд.** По `0x15E` - ручные предметы (оружие,
    /// щиты, метательное, еда), таблица `HANDS`. Сразу за ними, по
    /// `0x207`, снаряжение (доспехи, шлемы, плащи, украшения), таблица
    /// `ITEMS`. Раньше читался только первый список и чужой таблицей.
    static let inventoryBase = 0x15E
    static let handCount = 169
    static let gearBase = inventoryBase + handCount
    static let familiarBase = 0x418, familiarSize = 0x0C, familiarCount = 7
    static let bestiarySeen = 0x758, bestiaryDrops = 0x778
    static let relicOn: UInt8 = 3
    static let mapDivisor = 9.42
    static let characters = [0: "Alucard", 1: "Richter", 2: "Maria"]

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case character, level, exp, gold, kills, hp, mp, hearts, map
            case location, progression, playtime, gear, relics, spells
            case inventory, kept, familiars, bestiary, drops
            case enemyTotal = "enemy_total"
        }
        public var character: String
        public var level: UInt32
        public var exp: UInt32
        public var gold: UInt32
        public var kills: UInt32
        public var hp: [UInt32]
        public var mp: [UInt32]
        public var hearts: [UInt32]
        public var map: Double
        public var location: Int
        public var progression: Int
        public var playtime: [UInt32]
        public var gear: [[String]]
        public var relics: [String]
        public var spells: [String]
        public var inventory: [[String]]
        public var kept: [[String]] = []
        public var familiars: [[String]]
        public var bestiary: [String]
        public var drops: [String]
        public var enemyTotal: Int
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    static func bit(_ block: [UInt8], base: Int, at index: Int) -> Bool {
        let i = base + index / 8
        guard i < block.count else { return false }
        return (block[i] >> (index % 8)) & 1 == 1
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        let base = Identify.templateBase(block[...])
        guard block.count >= base + 0x420 else { return nil }
        let slice = block[...]
        let who = Int(read32(slice, at: base + character))
        let rate = Double(read16(slice, at: base + mapRate)) / mapDivisor
        return Overview(
            character: characters[who] ?? "#\(who)",
            level: read32(slice, at: base + level),
            exp: read32(slice, at: base + experience),
            gold: read32(slice, at: base + gold),
            kills: read32(slice, at: base + kills),
            hp: [read32(slice, at: base + hpCur), read32(slice, at: base + hpMax)],
            mp: [read32(slice, at: base + mpCur), read32(slice, at: base + mpMax)],
            hearts: [read32(slice, at: base + heartsCur),
                     read32(slice, at: base + heartsMax)],
            map: (rate * 100).rounded() / 100,
            location: Int(block[base + location]),
            progression: Int(block[base + progression]),
            playtime: [read32(slice, at: base + playH),
                       read32(slice, at: base + playM),
                       read32(slice, at: base + playS)],
            gear: gear(block, base: base, data: data),
            relics: relics(block, base: base, data: data),
            spells: spells(block, base: base, data: data),
            inventory: inventory(block, base: base, data: data),
            kept: kept(block, base: base, data: data),
            familiars: familiars(block, base: base, data: data),
            bestiary: bestiary(block, base: base, at: bestiarySeen, data: data),
            drops: bestiary(block, base: base, at: bestiaryDrops, data: data),
            enemyTotal: data.count("ENEMIES"))
    }

    static func gear(_ block: [UInt8], base: Int, data: GameData) -> [[String]] {
        var out: [[String]] = []
        for (offset, label) in gearSlots {
            let value = Int(read32(block[...], at: base + offset))
            let table = handSlots.contains(offset) ? "HANDS" : "ITEMS"
            if let name = data.name(table, value) { out.append([label, name]) }
        }
        return out
    }

    static func relics(_ block: [UInt8], base: Int, data: GameData) -> [String] {
        data.list("RELICS").compactMap { relic in
            let at = base + relic.value
            guard at < block.count, block[at] == relicOn else { return nil }
            return relic.name
        }
    }

    static func spells(_ block: [UInt8], base: Int, data: GameData) -> [String] {
        (0..<spellSlots).compactMap { slot in
            let value = Int(block[base + spellsBase + slot])
            guard value != 0, let name = data.name("SPELLS", value) else { return nil }
            return name
        }
    }

    static func counted(_ block: [UInt8], at start: Int, table: String,
                        data: GameData) -> [[String]] {
        data.keys(table).compactMap { index in
            let at = start + index
            guard at < block.count, block[at] != 0,
                  let name = data.name(table, index) else { return nil }
            return [name, String(block[at])]
        }
    }

    /// Оба списка подряд - так их показывает и меню игры.
    static func inventory(_ block: [UInt8], base: Int, data: GameData) -> [[String]] {
        counted(block, at: base + inventoryBase, table: "HANDS", data: data)
            + counted(block, at: base + gearBase, table: "ITEMS", data: data)
    }

    /// Инвентарь без расходуемого, разложенный по видам: тройки
    /// «раздел, предмет, сколько».
    ///
    /// Еды в игре 42 наименования, лекарств 21 - списком они забивают
    /// панель, а к собранному отношения не имеют. Виды взяты из того же
    /// game-tools-collection, что и названия. Плоскими тройками, а не
    /// вложенно: так вид одинаков у обоих движков.
    static func kept(_ block: [UInt8], base: Int, data: GameData) -> [[String]] {
        // Ключи таблицы и есть номера отсеиваемых видов, а значения -
        // их названия, чтобы было видно, что именно отброшено.
        let drop = Set(data.keys("CONSUMABLE_TYPES"))
        var out: [[String]] = []
        for (start, table, types, kinds) in [
            (base + inventoryBase, "HANDS", "HAND_TYPE_OF", "HAND_TYPES"),
            (base + gearBase, "ITEMS", "GEAR_TYPE_OF", "GEAR_TYPES"),
        ] {
            var groups: [Int: [[String]]] = [:]
            for index in data.keys(table).sorted() {
                let at = start + index
                guard at < block.count, block[at] != 0,
                      let name = data.name(table, index) else { continue }
                let kind = data.number(types, index) ?? -1
                if table == "HANDS", drop.contains(kind) { continue }
                groups[kind, default: []].append([name, String(block[at])])
            }
            for kind in data.keys(kinds).sorted() {
                guard let rows = groups[kind],
                      let title = data.name(kinds, kind) else { continue }
                for row in rows { out.append([title, row[0], row[1]]) }
            }
        }
        return out
    }

    static func familiars(_ block: [UInt8], base: Int, data: GameData) -> [[String]] {
        var out: [[String]] = []
        for index in 0..<familiarCount {
            let at = base + familiarBase + index * familiarSize
            let level = read32(block[...], at: at)
            guard level != 0 else { continue }
            out.append([data.name("FAMILIARS", index) ?? "#\(index)",
                        String(level), String(read32(block[...], at: at + 4))])
        }
        return out
    }

    static func bestiary(_ block: [UInt8], base: Int, at table: Int,
                         data: GameData) -> [String] {
        data.keys("ENEMIES").compactMap { index in
            guard bit(block, base: base + table, at: index) else { return nil }
            return data.name("ENEMIES", index)
        }
    }
}
