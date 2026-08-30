import Foundation

/// Разбор сейва Final Fantasy Tactics.
///
/// Смещения - от начала блока сейва (слот занимает ровно один блок, 0x2000).
/// Источник раскладки: game-tools-collection, шаблон final-fantasy-tactics.
public enum FFT {
    public static let serials: Set<String> = [
        "SCUS-94221", "SLPS-00770", "SLPM-87392", "SLPS-02768", "SLPS-91435",
    ]

    // Сводка, которую игра показывает в меню загрузки.
    static let nameOffset = 0x101, nameLength = 0x0E
    static let jobPreview = 0x112, levelPreview = 0x113
    static let playtime = 0x120

    // Общее состояние партии.
    static let warFunds = 0x1934
    static let dateMonth = 0x193C, dateDay = 0x1940
    static let location = 0x1948
    static let birthMonth = 0x1A00, birthDay = 0x1A04

    // Отряд: 20 записей по 0xE0 байт подряд.
    static let unitBase = 0x484, unitSize = 0xE0, unitCount = 20
    static let uType = 0x000        // смещения ниже - от начала записи бойца
    static let uJob = 0x002
    static let uGender = 0x004      // биты 5..7 - пол, младшие 4 - признак гостя
    static let uZodiac = 0x006
    static let uExp = 0x015, uLevel = 0x016
    static let uBrave = 0x017, uFaith = 0x018
    static let uStatus = 0x0D0, uName = 0x0BE

    /// Базовые статы: по три байта на каждый. Это множитель роста, а не то,
    /// что показывает игра.
    static let statOffsets: [(Int, String)] = [
        (0x019, "hp"), (0x01C, "mp"), (0x01F, "sp"), (0x022, "pa"), (0x025, "ma"),
    ]

    /// Пустой слот у людей помечен 0xFF; у монстров там 0x00, но носить они
    /// ничего не могут - индекс 0x00 это Dagger, и его легко принять за
    /// настоящий предмет.
    static let gearSlots: [(Int, String)] = [
        (0x011, L.t("правая рука", "right hand")), (0x013, L.t("левая рука", "left hand")), (0x00E, L.t("голова", "head")),
        (0x00F, L.t("тело", "body")), (0x010, L.t("аксессуар", "accessory")),
    ]
    static let gearEmpty: UInt8 = 0xFF

    /// Инвентарь: по байту-счётчику на предмет, индекс предмета - смещение.
    static let inventoryBase = 0x1605
    static let nameEnd: UInt8 = 0xFE

    /// Месяцы в сейве нумеруются с единицы, а не с нуля.
    static let months = ["", L.t("Январь", "January"), L.t("Февраль", "February"), L.t("Март", "March"), L.t("Апрель", "April"), L.t("Май", "May"),
                         L.t("Июнь", "June"), L.t("Июль", "July"), L.t("Август", "August"), L.t("Сентябрь", "September"), L.t("Октябрь", "October"),
                         L.t("Ноябрь", "November"), L.t("Декабрь", "December")]
    static let zodiacSigns = [L.t("Овен", "Aries"), L.t("Телец", "Taurus"), L.t("Близнецы", "Gemini"), L.t("Рак", "Cancer"), L.t("Лев", "Leo"), L.t("Дева", "Virgo"),
                              L.t("Весы", "Libra"), L.t("Скорпион", "Scorpio"), L.t("Стрелец", "Sagittarius"), L.t("Козерог", "Capricorn"),
                              L.t("Водолей", "Aquarius"), L.t("Рыбы", "Pisces")]
    /// Пол занимает три старших бита байта, а не весь байт.
    static let genders: [Int: String] = [4: L.t("мужской", "male"), 2: L.t("женский", "female"), 1: L.t("монстр", "monster")]
    static let statuses: [UInt8: String] = [0x0: "", 0x1: L.t("временно покидает отряд", "temporarily leaves the party")]

    public struct Unit: Codable, Sendable {
        public var slot: Int
        public var gear: [[String]]
        public var rawStats: [String: Int]
        public var isMonster: Bool
        public var jobKnown: Bool
        public var stats: [String: Int]
        public var atCap: [String: Bool]
        public var name: String
        public var who: String
        public var job: String
        public var level: Int
        public var exp: Int
        public var brave: Int
        public var faith: Int
        public var gender: String
        public var guest: Bool
        public var status: String
        public var zodiac: String

        enum CodingKeys: String, CodingKey {
            case slot, gear, stats, name, who, job, level, exp, brave, faith
            case gender, guest, status, zodiac
            case rawStats = "raw_stats"
            case isMonster = "is_monster"
            case jobKnown = "job_known"
            case atCap = "at_cap"
        }
    }

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case name, playtime, level, job, funds, date, birthday, location
            case units, inventory
            case playtimeRaw = "playtime_raw"
        }
        public var name: String
        public var playtime: [Int]
        public var playtimeRaw: UInt32
        public var level: Int
        public var job: String
        public var funds: UInt32
        public var date: [String]
        public var birthday: [String]
        public var location: String
        public var units: [Unit]
        public var inventory: [[String]]
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    /// Своя кодировка на 271 символ, конец строки - 0xFE.
    public static func decodeName(_ raw: ArraySlice<UInt8>, _ data: GameData) -> String {
        var out = ""
        for byte in raw {
            if byte == nameEnd { break }
            out += data.name("LETTERS", Int(byte)) ?? "?"
        }
        return out.trimmingCharacters(in: .whitespaces)
    }

    static func jobName(_ value: Int, gender: Int, _ data: GameData) -> String {
        let order = gender == 1 ? ["MONSTERS", "JOBS"] : ["JOBS", "MONSTERS"]
        return data.name(order, value) ?? "#\(value)"
    }

    public static func overview(_ block: [UInt8], data: GameData,
                                growth: FFTStats) -> Overview? {
        guard block.count >= 0x2000 else { return nil }
        let slice = block[...]
        let seconds = read32(slice, at: playtime)
        let month = Int(read32(slice, at: dateMonth))
        let birth = Int(read32(slice, at: birthMonth))
        let job = Int(block[jobPreview])
        let place = Int(block[location])
        return Overview(
            name: decodeName(block[nameOffset..<(nameOffset + nameLength)], data),
            playtime: [Int(seconds) / 3600, Int(seconds) / 60 % 60, Int(seconds) % 60],
            playtimeRaw: seconds,
            level: Int(block[levelPreview]),
            job: data.name("JOBS", job) ?? "#\(job)",
            funds: read32(slice, at: warFunds),
            date: [monthName(month), String(read32(slice, at: dateDay))],
            birthday: [monthName(birth), String(read32(slice, at: birthDay))],
            location: data.name("LOCATIONS", place) ?? "#\(place)",
            units: units(block, data: data, growth: growth),
            inventory: inventory(block, data: data))
    }

    static func monthName(_ value: Int) -> String {
        (1..<months.count).contains(value) ? months[value] : "#\(value)"
    }

    static func units(_ block: [UInt8], data: GameData, growth: FFTStats) -> [Unit] {
        var out: [Unit] = []
        for index in 0..<unitCount {
            let base = unitBase + index * unitSize
            guard base + unitSize <= block.count else { break }
            let kind = Int(block[base + uType])
            if kind == 0 { continue }

            let genderByte = block[base + uGender]
            let gender = Int(genderByte >> 5) & 0x7
            // Знак зодиака лежит в старших четырёх битах байта.
            let sign = Int(block[base + uZodiac] >> 4)

            var gear: [[String]] = []
            if gender != 1 {
                for (offset, label) in gearSlots {
                    let value = block[base + offset]
                    if value == gearEmpty { continue }
                    if let name = data.name("ITEMS", Int(value)) {
                        gear.append([label, name])
                    }
                }
            }

            var raw: [String: Int] = [:]
            for (offset, key) in statOffsets {
                let i = base + offset
                raw[key] = Int(block[i]) | Int(block[i + 1]) << 8 | Int(block[i + 2]) << 16
            }
            let jobID = Int(block[base + uJob])
            let jobData = growth.jobs[jobID]

            out.append(Unit(
                slot: index + 1,
                gear: gear,
                rawStats: raw,
                isMonster: gender == 1,
                jobKnown: jobData != nil,
                stats: growth.displayed(raw, job: jobData),
                atCap: growth.capped(raw),
                name: decodeName(block[(base + uName)..<(base + uName + nameLength)], data),
                who: data.name("UNIT_TYPES", kind) ?? "",
                job: jobName(jobID, gender: gender, data),
                level: Int(block[base + uLevel]),
                exp: Int(block[base + uExp]),
                brave: Int(block[base + uBrave]),
                faith: Int(block[base + uFaith]),
                gender: genders[gender] ?? "?\(gender)",
                guest: (genderByte & 0x0F) != 0,
                status: statuses[block[base + uStatus]] ?? "",
                zodiac: sign < zodiacSigns.count ? zodiacSigns[sign] : "?"))
        }
        return out
    }

    static func inventory(_ block: [UInt8], data: GameData) -> [[String]] {
        var out: [[String]] = []
        for index in 0..<256 {
            guard let name = data.name("ITEMS", index) else { continue }
            let at = inventoryBase + index
            guard at < block.count else { break }
            let count = Int(block[at])
            if count > 0 { out.append([name, String(count)]) }
        }
        return out
    }
}
