import Foundation

/// Разбор сейва Resident Evil (первая часть).
///
/// Смещения - от начала блока сейва, источник: game-tools-collection,
/// шаблон resident-evil.
public enum RE1 {
    /// Все издания из валидатора шаблона, включая Director's Cut - у него
    /// свои серийники, отличные от обычного издания.
    public static let serials: Set<String> = [
        "SLUS-00170", "SLUS-00551", "SLES-00200", "SLES-00227",
        "SLES-00228", "SLES-00969", "SLES-00970", "SLES-00971",
        "SLPS-00222", "SLPS-00998",
    ]

    /// База жёсткая, и это не упущение: часть сейвов Director's Cut объявляет
    /// в байте `0x02` один кадр иконки, а данные всё равно кладёт с `0x200`.
    /// По числу кадров такие читаются мимо - выходит «Крис» вместо «Джилл»
    /// и локация `0xEEEE`. Число кадров это подсказка BIOS для анимации,
    /// а не обязательство игры.
    static let dataAt = 0x200
    static let locationAt = 0x000
    static let health = 0x01E
    static let playtimeAt = 0x024      // u32
    static let inkRibbons = 0x028
    static let character = 0x02B       // бит 0: 0 - Крис, 1 - Джилл

    static let inventoryBase = 0x124, inventorySlots = 8
    static let containerBase = 0x0C4, containerSlots = 48

    public struct Overview: Codable, Sendable {
        enum CodingKeys: String, CodingKey {
            case character, health, location, inventory, container
            case playtimeRaw = "playtime_raw"
            case inkRibbons = "ink_ribbons"
        }
        public var character: String
        public var health: UInt16
        public var playtimeRaw: UInt32
        public var inkRibbons: Int
        public var location: String
        public var inventory: [[String]]
        public var container: [[String]]
    }

    public static func matches(_ save: Save) -> Bool {
        serials.contains(SaveName.normalize(SaveName(save.rawName).serial))
    }

    /// Код локации лежит big-endian - в отличие от всего остального в сейве.
    /// Признак ошибки: код не находится в справочнике, а `0x0600`
    /// подозрительно похож на переставленный `0x0006`.
    static func read16BE(_ block: [UInt8], at offset: Int) -> Int {
        guard offset + 1 < block.count else { return 0 }
        return Int(block[offset]) << 8 | Int(block[offset + 1])
    }

    public static func overview(_ block: [UInt8], data: GameData) -> Overview? {
        guard block.count >= dataAt + 0x200 else { return nil }
        let base = dataAt
        let place = read16BE(block, at: base + locationAt)
        return Overview(
            character: data.name("CHARACTERS", Int(block[base + character] & 1)) ?? "?",
            health: read16(block[...], at: base + health),
            playtimeRaw: read32(block[...], at: base + playtimeAt),
            inkRibbons: Int(block[base + inkRibbons]),
            location: data.name("LOCATIONS", place)
                ?? String(format: "#0x%04x", place),
            inventory: slots(block, base: base + inventoryBase,
                             count: inventorySlots, data: data),
            container: slots(block, base: base + containerBase,
                             count: containerSlots, data: data))
    }

    static func slots(_ block: [UInt8], base: Int, count: Int,
                      data: GameData) -> [[String]] {
        var out: [[String]] = []
        for index in 0..<count {
            let at = base + index * 2
            guard at + 1 < block.count else { break }
            let item = Int(block[at]), qty = Int(block[at + 1])
            if item == 0 { continue }
            out.append([data.name("ITEMS", item) ?? String(format: "#0x%02x", item),
                        String(qty)])
        }
        return out
    }
}
