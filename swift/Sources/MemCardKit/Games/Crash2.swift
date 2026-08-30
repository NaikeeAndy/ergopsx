import Foundation

/// Разбор сейва Crash Bandicoot 2: Cortex Strikes Back.
///
/// Смещения - из `giuse94/PSDX`, где описано **европейское** издание
/// (SCES-00967) в формате `.mcs`, то есть от начала файла: кадр каталога
/// плюс блок. Данные игры там начинаются с `0x180`.
///
/// У американского издания `tonyhax` называет `0x280` вместо `0x180`, и
/// это ровно разница в один кадр иконки: европейский сейв объявляет один
/// кадр, американский - три. Поэтому база считается по самому блоку,
/// а не задаётся числом: тогда оба издания читаются одним кодом,
/// и европейские сейвы заработают сразу, как появятся.
///
/// **Проверить нечем.** Crash 2, в отличие от первой части, не пишет
/// процент прохождения в подпись - там просто «Crash Bandicoot 2».
/// За разбор говорит только осмысленность значений: имя игрока читается
/// текстом, жизни и фрукты в разумных пределах, число собранного растёт
/// вместе с номером уровня.
public enum Crash2 {
    public static let serials: Set<String> = [
        "SCUS-94154", "SCES-00967", "SCPS-10047", "SCPS-91109",
        "SCES-01005", "SCES-01006", "SCES-01007",
    ]

    /// Смещения PSDX отсчитаны от начала `.mcs`, где данные с `0x180`.
    /// Здесь они переведены в отсчёт от начала данных игры.
    static let base = 0x180
    static let freeSlot = 0x184 - base
    static let lastLevel = 0x188 - base
    static let username = 0x18C - base
    static let usernameSize = 16
    static let checksum = 0x1A4 - base
    static let lives = 0x1AC - base
    static let wumpa = 0x1B0 - base
    static let akuAku = 0x1B4 - base
    static let secrets = 0x1B8 - base
    static let progress = 0x1BC - base
    static let crystals = 0x1C4 - base
    static let gems = 0x1CC - base

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case name, level, lives, wumpa, crystals, gems, progress, secrets
            case akuAku = "aku_aku"
        }
        public var name: String
        public var level: Int
        public var lives: Int
        public var wumpa: Int
        public var akuAku: Int
        /// Собранное лежит битовыми масками, а не числами: без подсчёта
        /// битов выходят миллиарды вместо десятков.
        public var crystals: Int
        public var gems: Int
        public var progress: Int
        public var secrets: Int
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    public static func overview(_ block: [UInt8]) -> Overview? {
        let at = Identify.dataOffset(block[...])
        guard block.count >= at + 0x60 else { return nil }
        let slice = block[...]

        func value(_ offset: Int) -> UInt32 { read32(slice, at: at + offset) }
        func bits(_ offset: Int) -> Int { value(offset).nonzeroBitCount }

        let raw = Array(block[(at + username)..<(at + username + usernameSize)])
        let name = String(decoding: raw.prefix { $0 != 0 }, as: UTF8.self)
            .trimmingCharacters(in: .whitespaces)

        return Overview(
            name: name,
            level: Int(value(lastLevel)),
            lives: Int(value(lives)),
            wumpa: Int(value(wumpa)),
            akuAku: Int(value(akuAku)),
            crystals: bits(crystals),
            gems: bits(gems),
            progress: bits(progress),
            secrets: bits(secrets))
    }
}
