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
    /// **Номера стейджей не сбрасываются на втором круге.** Стейдж 28 -
    /// это второй уровень второго прохождения, а не десятый уровень:
    /// в круге восемь уровней и двадцать четыре стейджа.
    static let levelsPerLoop = 8
    static let stagesPerLoop = stagesPerLevel * levelsPerLoop
    /// **Записей две, через 0x30.** Читалась только первая, и три разных
    /// сейва показывали одинаковые «стейдж 28, уровень 10».
    ///
    /// **Первая запись - Original, вторая - Arrange.** Проверено на
    /// живой консоли: сейв с записями «стейдж 28» и «стейдж 16» игра
    /// показала в Original как 28, в Arrange как 16. Признака режима
    /// внутри записи нет - его задаёт номер записи.
    static let slotStride = 0x30
    public static let modeNames = ["Original", "Arrange"]
    public static let slotCount = 2

    public struct Overview: Codable, Sendable {
        public var name: String
        public var stage: Int
        /// Второе число с экрана выбора. Что оно значит - неизвестно,
        /// поэтому показываем как есть, а не выдумываем название.
        public var counter: Int
        public var level: Int
        /// Круг прохождения, с первого.
        public var loop: Int = 1
        /// Дата и время сохранения, как их записала игра.
        public var saved: String
        /// Режим игры: Original или Arrange.
        public var mode: String = ""
        /// Номер записи в сейве, с единицы.
        public var slot: Int = 0
        /// Заполненные записи. У первой то же содержимое, что у самой
        /// `Overview` - так старые вызовы не ломаются.
        public var slots: [Overview] = []
        /// Рекорды Time Attack, поставленные игроком.
        public var timeAttack: [Record] = []
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    /// Одна из двух записей игры.
    static func slot(_ block: [UInt8], _ base: Int, _ index: Int) -> Overview? {
        let at = base + index * slotStride
        guard block.count >= at + 0x140 else { return nil }

        let raw = Array(block[(at + name)..<(at + name + nameSize)])
        let text = String(decoding: raw.prefix { $0 != filler && $0 != 0 },
                          as: UTF8.self).trimmingCharacters(in: .whitespaces)

        let number = Int(block[at + stage])
        guard (1...99).contains(number) else { return nil }

        let when = String(format: "%04d-%02d-%02d %02d:%02d:%02d",
                          Int(read16(block[...], at: at + year)),
                          Int(block[at + month]), Int(block[at + day]),
                          Int(block[at + hour]), Int(block[at + minute]),
                          Int(block[at + second]))

        return Overview(name: text,
                        stage: number,
                        counter: Int(block[at + counter]),
                        level: ((number - 1) % stagesPerLoop) / stagesPerLevel + 1,
                        loop: (number - 1) / stagesPerLoop + 1,
                        saved: when,
                        mode: index < modeNames.count ? modeNames[index] : "",
                        slot: index + 1)
    }

    /// Заполненные записи. Пустая узнаётся по имени: игра оставляет там
    /// одни заполнители, пока в этом режиме не сохранялись.
    public static func slots(_ block: [UInt8]) -> [Overview] {
        let base = Identify.dataOffset(block[...])
        return (0..<slotCount).compactMap { index in
            guard let got = slot(block, base, index), !got.name.isEmpty else {
                return nil
            }
            return got
        }
    }

    // --- Time Attack ---
    // Восемь таблиц рекордов, по числу уровней в круге, в каждой десять
    // мест. Найдено якорем: заезд по первому уровню с временем 3:26.2 и
    // счётом 23500 встал первой строкой, сдвинув остальные вниз.
    static let taFirst = 0x17C
    static let taEntry = 0x10
    static let taRows = 10
    static let taName = 0x00, taNameSize = 8
    /// Десятые доли секунды.
    static let taTime = 0x0A
    static let taScore = 0x0C
    /// Имя заводских мест: их десять на каждый уровень, и показывать
    /// восемьдесят строк заготовки незачем.
    static let taFactory: [UInt8] = [0x44, 0x52, 0x41, 0, 0, 0, 0, 0]

    public struct Record: Codable, Sendable {
        public var level: Int
        public var place: Int
        public var name: String
        public var tenths: Int
        public var time: String
        public var score: Int
    }

    /// Рекорды Time Attack, поставленные игроком.
    public static func timeAttack(_ block: [UInt8]) -> [Record] {
        let base = Identify.dataOffset(block[...])
        var found: [Record] = []
        for table in 0..<levelsPerLoop {
            for place in 0..<taRows {
                let at = base + taFirst + (table * taRows + place) * taEntry
                guard at + taEntry <= block.count else { return found }
                let raw = Array(block[(at + taName)..<(at + taName + taNameSize)])
                if raw == taFactory { continue }
                let text = String(decoding: raw.prefix { $0 != filler && $0 != 0 },
                                  as: UTF8.self).trimmingCharacters(in: .whitespaces)
                let tenths = Int(read16(block[...], at: at + taTime))
                guard !text.isEmpty, tenths != 0 else { continue }
                found.append(Record(
                    level: table + 1, place: place + 1, name: text,
                    tenths: tenths,
                    time: String(format: "%d:%04.1f", tenths / 600,
                                 Double(tenths % 600) / 10),
                    score: Int(read16(block[...], at: at + taScore))))
            }
        }
        return found
    }

    public static func overview(_ block: [UInt8]) -> Overview? {
        // Данные игры начинаются за кадрами иконки - считаем по блоку.
        let base = Identify.dataOffset(block[...])
        guard var first = slot(block, base, 0) else { return nil }
        first.slots = slots(block)
        first.timeAttack = timeAttack(block)
        return first
    }
}
