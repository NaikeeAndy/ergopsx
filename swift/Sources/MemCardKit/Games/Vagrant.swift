import Foundation

/// Разбор сейва Vagrant Story.
///
/// **Сейв зашифрован**, и без этого раскладка из декомпиляции не сходится
/// ни с чем: байты выглядят случайными, энтропия 7,8 из 8, одинаковых
/// позиций у пяти сейвов одной игры - четыре процента. Именно поэтому
/// Vagrant Story нигде и не разбирали.
///
/// Шифр - поточный, на линейном конгруэнтном генераторе (`_decode`
/// из `ser-pounce/rood-reverse`, MENU7.PRG): ключ лежит открытым текстом
/// по `0x180`, дальше на каждый байт ключ умножается на `0x19660D`,
/// и старший байт результата вычитается из байта данных.
///
/// Проверено якорем: игра пишет наигранное время в подпись сейва, и после
/// расшифровки оно сошлось на всех пяти сейвах коллекции.
public enum Vagrant {
    public static let serials: Set<String> = [
        "SLUS-01040", "SLES-02754", "SLES-02755", "SLES-02756",
        "SLPS-02377", "SLPS-91457", "SLPM-87393", "SCPS-45486",
    ]

    static let keyAt = 0x180          // ключ шифра, четыре байта открытым текстом
    static let cipherFrom = 0x184     // отсюда и до конца - шифрованное
    static let multiplier: UInt32 = 0x19660D

    /// Магия, которой начинается расшифрованный заголовок. По ней и
    /// проверяем, что расшифровали верно, а не получили новый мусор.
    static let magic: UInt32 = 0x20000107
    static let magicAt = 0x18C

    // Смещения в расшифрованном блоке.
    static let slotState = 0x184
    static let generation = 0x188
    static let statsAt = 0x190
    /// `vs_Gametime_t` - четыре байта в порядке «кадры, секунды, минуты, часы».
    static let sFrames = 0x00, sSeconds = 0x01, sMinutes = 0x02, sHours = 0x03
    static let sSavesTotal = 0x04, sSavesGame = 0x06
    static let sHP = 0x08, sHPMax = 0x0A
    static let sLocation = 0x0C, sClearCount = 0x0D, sMapCompletion = 0x0E
    static let sMP = 0x10, sMPMax = 0x12
    static let checksums = 0x1A4

    static let stateFlags = 0x200, stateFlagsSize = 0x440
    static let actionsLearned = 0x640, actionsSize = 32
    /// `vs_main_mapStatus_t`: 16 слов по комнатам (512 бит) и два по
    /// областям (32 из 64 заняты).
    static let mapStatus = 0x660, mapStatusSize = 0x48
    static let roomFlags = 0x660, roomWords = 16
    static let areaFlags = 0x6A0, areaCount = 32

    // Дальше - раскладка `savedata_t` из `src/MENU/MENU7.PRG/260.c`.
    // Смещения не выдуманы: у полей декомпиляции они стоят прямо
    // в именах (`unk6C8`, `unk16C8`, `unk1778`, `unk1898`, `unk59E0`),
    // а размеры записей считаются по комментариям к `vs_main_inventory_t`.
    static let settings = 0x6A8            // vs_main_settings_t, 0x20
    static let party = 0x6C8               // D_80060068_t, 0x100

    /// Разделы инвентаря: смещение, размер записи, сколько мест.
    /// Раздел инвентаря. `kind` не переводится и служит ключом:
    /// по названию привязываться нельзя, оно зависит от языка.
    public struct Section: Sendable {
        public let kind: String
        public let name: String
        let at: Int
        let size: Int
        let slots: Int
        /// Где внутри записи лежит номер предмета. У оружия его нет:
        /// оно собрано из клинка и рукояти, имя даёт игрок.
        var idAt: Int? = nil
        var idWide = false
    }

    /// Смещение номера предмета внутри записи и его ширина.
    ///
    /// У щита запись начинается со своих полей, а `vs_main_inventoryArmor`
    /// с его номером идёт с четвёртого байта. У оружия номера нет вовсе:
    /// оно собрано из клинка и рукояти, и название даёт игрок.
    /// То, что носит с собой Эшли.
    public static let carried: [Section] = [
        Section(kind: "weapons", name: L.t("Оружие", "Weapons"), at: 0x07C8, size: 32, slots: 8),
        Section(kind: "shields", name: L.t("Щиты", "Shields"), at: 0x08C8, size: 48, slots: 8, idAt: 4, idWide: false),
        Section(kind: "blades", name: L.t("Клинки", "Blades"), at: 0x0A48, size: 44, slots: 16, idAt: 0, idWide: false),
        Section(kind: "grips", name: L.t("Рукояти", "Grips"), at: 0x0D08, size: 16, slots: 16, idAt: 0, idWide: true),
        Section(kind: "armor", name: L.t("Броня", "Armor"), at: 0x0E08, size: 40, slots: 16, idAt: 0, idWide: false),
        Section(kind: "gems", name: L.t("Самоцветы", "Gems"), at: 0x1088, size: 28, slots: 48, idAt: 0, idWide: true),
        Section(kind: "misc", name: L.t("Прочее", "Other"), at: 0x15C8, size: 4, slots: 64, idAt: 0, idWide: true),
    ]

    /// Сундук в мастерской. Те же разделы, мест вчетверо больше.
    public static let stored: [Section] = [
        Section(kind: "weapons", name: L.t("Оружие", "Weapons"), at: 0x1DE0, size: 32, slots: 32),
        Section(kind: "shields", name: L.t("Щиты", "Shields"), at: 0x21E0, size: 48, slots: 32, idAt: 4, idWide: false),
        Section(kind: "blades", name: L.t("Клинки", "Blades"), at: 0x27E0, size: 44, slots: 64, idAt: 0, idWide: false),
        Section(kind: "grips", name: L.t("Рукояти", "Grips"), at: 0x32E0, size: 16, slots: 64, idAt: 0, idWide: true),
        Section(kind: "armor", name: L.t("Броня", "Armor"), at: 0x36E0, size: 40, slots: 64, idAt: 0, idWide: false),
        Section(kind: "gems", name: L.t("Самоцветы", "Gems"), at: 0x40E0, size: 28, slots: 192, idAt: 0, idWide: true),
        Section(kind: "misc", name: L.t("Прочее", "Other"), at: 0x55E0, size: 4, slots: 256, idAt: 0, idWide: true),
    ]

    /// `vs_main_inventoryWeapon`: индекс, клинок, рукоять, надето,
    /// четыре самоцвета и имя на 24 байта. Имя даёт игрок.
    static let weaponName = 8, weaponNameSize = 24
    static let weaponEquipped = 3

    /// `vs_main_artsStatus_t` - сразу перед сундуком.
    static let arts = 0x1DBC, artsSize = 12
    static let artsAbilities = 0x1DDC

    /// `vs_main_scoredata_t`. Проверено отношением: процент карты в
    /// `stats` и число комнат здесь дают одно и то же 3,6 на всех
    /// сейвах, а все счётчики растут вместе с прохождением.
    /// Всего комнат, засчитываемых в проценте. Число из самой игры:
    /// `vs_battle_getMapCompletion` считает единицы в
    /// `roomFlags & mapCompletionFlags` и делит на 361.
    public static let roomsTotal = 361

    static let score = 0x1784
    static let scoreKills = 0x04          // шесть классов противников
    static let scoreWeaponUse = 0x14      // десять видов оружия
    static let scoreMaxChain = 0x88
    static let scoreRooms = 0x94
    static let scoreChests = 0x98
    static let scoreHeals = 0x112

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case playtime, hp, mp, location, generation, actions, maps
            case weapons, carried, stored, kills, rooms, chests, heals
            case abilities
            case storedWeapons = "stored_weapons"
            case artsLearned = "arts_learned"
            case maxChain = "max_chain"
            case unopened
            case carriedItems = "carried_items"
            case storedItems = "stored_items"
            case savesTotal = "saves_total"
            case savesGame = "saves_game"
            case clearCount = "clear_count"
            case mapCompletion = "map_completion"
            case playtimeRaw = "playtime_raw"
        }
        public var playtime: [Int]
        public var playtimeRaw: Int
        public var hp: [Int]
        public var mp: [Int]
        public var location: Int
        public var clearCount: Int
        public var mapCompletion: Int
        public var savesTotal: Int
        public var savesGame: Int
        public var generation: UInt32
        /// Сколько приёмов изучено - по битам.
        public var actions: Int
        /// Сколько карт хоть сколько-то исследовано.
        public var maps: Int
        /// Имена оружия - те, что игрок дал сам.
        public var weapons: [String]
        public var storedWeapons: [String]
        /// Занято мест по разделам: «Клинки 7 из 16».
        public var carried: [Slot]
        public var stored: [Slot]
        public var artsLearned: Int
        public var abilities: Int
        public var kills: [Int]
        public var rooms: Int
        public var chests: Int
        public var maxChain: Int
        public var heals: Int
        /// Сколько засчитываемых комнат не открыто, по областям.
        public var unopened: [Slot]
        /// Что лежит в разделах, по названиям.
        public var carriedItems: [String: [Slot]]
        public var storedItems: [String: [Slot]]
    }

    /// Карта комнат: маска засчитываемых, область каждой комнаты
    /// и названия областей. Всё - из самой игры: маска лежит в
    /// `BATTLE.PRG` по `0x800E8508`, область комнаты - в `sectionB`
    /// файла `MAP<номер>.MPD`, названия - в `mapNames` из MENU5.
    public struct MapTable: Codable, Sendable {
        public var roomsTotal: Int
        public var mask: [UInt32]
        public var scenes: [Int]
        public var areas: [String]
        /// Названия предметов по номеру. Пустая строка - у предмета
        /// в игре имени нет.
        public var items: [String]

        enum CodingKeys: String, CodingKey {
            case mask, scenes, areas, items
            case roomsTotal = "rooms_total"
        }

        public static func bundled() -> MapTable? {
            guard let url = Bundle.module.url(forResource: "vagrant-map",
                                              withExtension: "json"),
                  let data = try? Data(contentsOf: url) else { return nil }
            return try? JSONDecoder().decode(MapTable.self, from: data)
        }
    }

    /// Сколько комнат не открыто, по областям. Порядок - как в игре.
    public static func unopened(_ block: [UInt8], table: MapTable) -> [Slot] {
        guard block.count >= mapStatus + mapStatusSize else { return [] }
        let plain = decode(block)
        var words = (0..<roomWords).map {
            read32(plain[...], at: roomFlags + $0 * 4)
        }
        // Поправка из самой игры перед подсчётом.
        if words[1] & 0x800000 != 0 { words[1] |= 0x400000 }

        var perArea: [Int: Int] = [:]
        for room in 0..<(roomWords * 32) {
            let word = room / 32, bit = room % 32
            guard word < table.mask.count,
                  table.mask[word] >> UInt32(bit) & 1 == 1 else { continue }
            guard words[word] >> UInt32(bit) & 1 == 0 else { continue }
            let scene = room < table.scenes.count ? table.scenes[room] : -1
            perArea[scene, default: 0] += 1
        }

        return perArea.sorted { $0.key < $1.key }.map { scene, count in
            let name = scene >= 0 && scene < table.areas.count
                && !table.areas[scene].isEmpty
                ? table.areas[scene] : L.t("неизвестно", "unknown")
            return Slot(name: name, used: count, total: count)
        }
    }

    public struct Slot: Codable, Sendable {
        public var name: String
        public var used: Int
        public var total: Int
    }

    /// Место занято, если запись не пустая. У всех разделов первым
    /// полем идёт номер предмета, и у свободного места он нулевой
    /// вместе со всей записью.
    static func count(_ plain: [UInt8], _ section: Section) -> Int {
        var used = 0
        for index in 0..<section.slots {
            let at = section.at + index * section.size
            guard at + section.size <= plain.count else { break }
            if plain[at..<(at + section.size)].contains(where: { $0 != 0 }) {
                used += 1
            }
        }
        return used
    }

    /// Что лежит в разделе, по названиям. Одинаковые собираются вместе:
    /// «Cure Potion x4» читается лучше, чем четыре одинаковые строки.
    public static func contents(_ plain: [UInt8], _ section: Section,
                                table: MapTable) -> [Slot] {
        guard let idAt = section.idAt else { return [] }
        var counts: [String: Int] = [:]
        var order: [String] = []
        for index in 0..<section.slots {
            let at = section.at + index * section.size
            guard at + section.size <= plain.count else { break }
            guard plain[at..<(at + section.size)].contains(where: { $0 != 0 })
            else { continue }
            let id = section.idWide
                ? Int(read16(plain[...], at: at + idAt))
                : Int(plain[at + idAt])
            guard id > 0, id < table.items.count else { continue }
            let name = table.items[id]
            // У части номеров названия в игре нет - показываем номер,
            // а не пустую строку.
            let shown = name.isEmpty ? "#\(id)" : name
            if counts[shown] == nil { order.append(shown) }
            counts[shown, default: 0] += 1
        }
        return order.map { Slot(name: $0, used: counts[$0] ?? 0, total: 0) }
    }

    static func weaponNames(_ plain: [UInt8], _ section: Section) -> [String] {
        var out: [String] = []
        for index in 0..<section.slots {
            let at = section.at + index * section.size
            guard at + section.size <= plain.count else { break }
            guard plain[at..<(at + section.size)].contains(where: { $0 != 0 })
            else { continue }
            let from = at + weaponName
            let name = VagrantText.read(plain[from..<(from + weaponNameSize)])
            // Имя из одних нулей - место занято, но не подписано.
            let clean = name.trimmingCharacters(in: CharacterSet(charactersIn: "0 "))
            out.append(clean.isEmpty ? L.t("без имени", "unnamed") : name)
        }
        return out
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    /// Расшифровка на месте. Ключ остаётся как есть - он не шифрован.
    public static func decode(_ block: [UInt8]) -> [UInt8] {
        guard block.count > cipherFrom else { return block }
        var out = block
        var key = read32(block[...], at: keyAt)
        for index in cipherFrom..<out.count {
            key = key &* multiplier
            out[index] = out[index] &- UInt8((key >> 24) & 0xFF)
        }
        return out
    }

    public static func overview(_ block: [UInt8]) -> Overview? {
        // Сундук кончается на 0x59E0, дальше читать нечего.
        guard block.count >= 0x59E0 else { return nil }
        let plain = decode(block)
        // Если магия не встала на место - расшифровали не то, и читать
        // дальше значило бы выдумывать числа.
        guard read32(plain[...], at: magicAt) == magic else { return nil }

        let at = statsAt
        let hours = Int(plain[at + sHours])
        let minutes = Int(plain[at + sMinutes])
        let seconds = Int(plain[at + sSeconds])

        let learned = (0..<actionsSize).reduce(0) {
            $0 + plain[actionsLearned + $1].nonzeroBitCount
        }
        let explored = (0..<mapStatusSize).reduce(0) {
            $0 + (plain[mapStatus + $1] != 0 ? 1 : 0)
        }

        // Таблица нужна и комнатам, и названиям предметов - читаем один раз.
        let table = MapTable.bundled()

        let kills = (0..<6).map {
            Int(read16(plain[...], at: score + scoreKills + $0 * 2))
        }

        return Overview(
            playtime: [hours, minutes, seconds],
            playtimeRaw: hours * 3600 + minutes * 60 + seconds,
            hp: [Int(read16(plain[...], at: at + sHP)),
                 Int(read16(plain[...], at: at + sHPMax))],
            mp: [Int(read16(plain[...], at: at + sMP)),
                 Int(read16(plain[...], at: at + sMPMax))],
            location: Int(plain[at + sLocation]),
            clearCount: Int(plain[at + sClearCount]),
            mapCompletion: Int(plain[at + sMapCompletion]),
            savesTotal: Int(read16(plain[...], at: at + sSavesTotal)),
            savesGame: Int(read16(plain[...], at: at + sSavesGame)),
            generation: read32(plain[...], at: generation),
            actions: learned,
            maps: explored,
            weapons: weaponNames(plain, carried[0]),
            storedWeapons: weaponNames(plain, stored[0]),
            carried: carried.map {
                Slot(name: $0.name, used: count(plain, $0), total: $0.slots)
            },
            stored: stored.map {
                Slot(name: $0.name, used: count(plain, $0), total: $0.slots)
            },
            artsLearned: (0..<artsSize).reduce(0) {
                $0 + plain[arts + $1].nonzeroBitCount
            },
            abilities: Int(read16(plain[...], at: artsAbilities)),
            kills: kills,
            rooms: Int(read32(plain[...], at: score + scoreRooms)),
            chests: Int(read32(plain[...], at: score + scoreChests)),
            maxChain: Int(read16(plain[...], at: score + scoreMaxChain)),
            heals: Int(read16(plain[...], at: score + scoreHeals)),
            unopened: table.map { unopened(block, table: $0) } ?? [],
            carriedItems: table.map { made in
                Dictionary(uniqueKeysWithValues: carried.compactMap { section in
                    let list = contents(plain, section, table: made)
                    return list.isEmpty ? nil : (section.kind, list)
                })
            } ?? [:],
            storedItems: table.map { made in
                Dictionary(uniqueKeysWithValues: stored.compactMap { section in
                    let list = contents(plain, section, table: made)
                    return list.isEmpty ? nil : (section.kind, list)
                })
            } ?? [:])
    }
}
