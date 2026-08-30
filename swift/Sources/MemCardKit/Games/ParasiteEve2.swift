import Foundation

/// Разбор сейва Parasite Eve II.
///
/// Раскладка - из `GabeRealB/parasite-eve-2-decomp`: там проставлены все
/// смещения и размеры, но **имён у полей нет** - почти все называются
/// `field_XX`. Поэтому здесь только то, что удалось привязать к якорю:
/// игра пишет в подпись время и место, и по ним поля найдены перебором.
///
/// Что означают остальные сотни байт - неизвестно, и выдумывать им
/// названия хуже, чем не показывать вовсе.
public enum ParasiteEve2 {
    public static let serials: Set<String> = ["SLUS-01042", "SLUS-01055",
                                              "SLES-02558", "SLES-12558",
                                              "SLPS-02480", "SLPS-02481"]

    /// Размер `McSaveData`. Сейв держит **две записи подряд**: по этому
    /// смещению все поля повторяются второй раз.
    static let recordSize = 0x944

    /// Наигранное время в МИНУТАХ, а не секундах. Сошлось с подписью
    /// на 32 сейвах коллекции из 32.
    static let playtimeAt = 0x00C          // u16, от начала записи
    /// Число, которое игра пишет в скобках после места. Сошлось на всех
    /// 32 сейвах, но что оно значит - неизвестно.
    static let markAt = 0x011              // u8

    /// Слоты предметов. Названий предметов в разборе нет, поэтому
    /// считаем только занятые.
    static let itemsAt = 0x1C8, itemsCount = 0x7C, itemSize = 8
    static let extraItemsAt = 0x5C8, extraItemsCount = 0x20

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case playtime, mark, items, stored, banks
            case playtimeMinutes = "playtime_minutes"
        }
        public var playtime: [Int]
        public var playtimeMinutes: Int
        public var mark: Int
        /// Занятых слотов при себе.
        public var items: Int
        /// Занятых слотов в хранилище.
        public var stored: Int
        /// Сколько записей нашлось в блоке - обычно две.
        public var banks: Int
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    public static func overview(_ block: [UInt8]) -> Overview? {
        // Данные игры начинаются за кадрами иконки, а их число у сейвов
        // этой игры разное - считаем по блоку, а не предполагаем.
        let base = Identify.dataOffset(block[...])
        guard block.count >= base + recordSize else { return nil }

        let minutes = Int(read16(block[...], at: base + playtimeAt))
        let banks = block.count >= base + recordSize * 2 ? 2 : 1

        func occupied(_ at: Int, _ count: Int) -> Int {
            var used = 0
            for slot in 0..<count {
                let index = base + at + slot * itemSize
                guard index < block.count else { break }
                if block[index] != 0 { used += 1 }
            }
            return used
        }

        return Overview(
            playtime: [minutes / 60, minutes % 60, 0],
            playtimeMinutes: minutes,
            mark: Int(block[base + markAt]),
            items: occupied(itemsAt, itemsCount),
            stored: occupied(extraItemsAt, extraItemsCount),
            banks: banks)
    }
}
