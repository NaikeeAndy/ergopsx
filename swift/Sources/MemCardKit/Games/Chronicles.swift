import Foundation

/// Разбор сейва Castlevania Chronicles.
///
/// Публичного разбора этой игры нет - раскладка найдена якорем по экрану
/// выбора игрока: он показывает имя и два числа, и они нашлись в байтах
/// один в один на трёх сейвах коллекции.
///
/// Уровень игра не хранит, а выводит из номера стейджа: их по три на
/// уровень, как в оригинальной Castlevania, ремейком которой Chronicles
/// и является. Проверено на стейджах 4, 13 и 16 - второй, пятый и шестой
/// уровни соответственно.
public enum Chronicles {
    public static let serials: Set<String> = [
        "SLUS-01384", "SLES-03449", "SLPM-86808", "SLPM-86809",
    ]

    // Смещения от начала данных игры.
    static let year = 0x102        // u16
    static let month = 0x104, day = 0x105
    static let hour = 0x106, minute = 0x107, second = 0x108
    static let name = 0x11A, nameSize = 8
    /// Символ-заполнитель в имени: игра рисует его точкой.
    static let filler: UInt8 = 0x5B
    /// Два числа, которые игра показывает под заголовком «stage».
    static let stage = 0x124
    static let counter = 0x125
    static let stagesPerLevel = 3

    public struct Overview: Codable, Sendable {
        public var name: String
        public var stage: Int
        /// Второе число с экрана выбора. Что оно значит - неизвестно,
        /// поэтому показываем как есть, а не выдумываем название.
        public var counter: Int
        public var level: Int
        /// Дата и время сохранения, как их записала игра.
        public var saved: String
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    public static func overview(_ block: [UInt8]) -> Overview? {
        // Данные игры начинаются за кадрами иконки - считаем по блоку.
        let base = Identify.dataOffset(block[...])
        guard block.count >= base + 0x140 else { return nil }

        let raw = Array(block[(base + name)..<(base + name + nameSize)])
        let text = String(decoding: raw.prefix { $0 != filler && $0 != 0 },
                          as: UTF8.self).trimmingCharacters(in: .whitespaces)

        let number = Int(block[base + stage])
        guard (1...99).contains(number) else { return nil }

        let when = String(format: "%04d-%02d-%02d %02d:%02d:%02d",
                          Int(read16(block[...], at: base + year)),
                          Int(block[base + month]), Int(block[base + day]),
                          Int(block[base + hour]), Int(block[base + minute]),
                          Int(block[base + second]))

        return Overview(name: text,
                        stage: number,
                        counter: Int(block[base + counter]),
                        level: (number - 1) / stagesPerLevel + 1,
                        saved: when)
    }
}
