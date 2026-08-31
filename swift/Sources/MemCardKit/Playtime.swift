import Foundation

/// Наигранное время по играм, найденное автопоиском (`tools/psxdiscover.py`).
///
/// Поле искалось перебором смещений против подписи, которую пишет сама
/// игра, и должно было сойтись на всех её сейвах сразу. Это факт из
/// данных, а не чужой разбор: готовых спецификаций по этим играм нет.
///
/// **Таблица нужна отдельно от разборщиков игр.** Полный разбор есть у
/// одиннадцати игр, а время таблица даёт ещё у шестнадцати - Dino Crisis,
/// Metal Gear Solid, Grandia, The Legend of Dragoon и другие. Без неё
/// приложение показывает время у вдвое меньшего числа сейвов.
public enum Playtime {
    /// Во что превращать сырое значение, чтобы получить секунды.
    /// Названия единиц берутся из таблицы как есть.
    private static let divisors: [String: Double] = [
        "секунды": 1, "минуты": 1.0 / 60, "кадры 60 Гц": 60, "кадры 50 Гц": 50,
    ]

    private struct Spec {
        var offset: Int
        var width: String
        var unit: String
        /// Под одним серийником бывает несколько игр - выбор по подписи.
        /// У Final Fantasy Origins это FF1 и FF2: серийник общий,
        /// раскладка разная.
        var match: String?

        init?(_ raw: [String: Any]) {
            guard let offset = raw["offset"] as? Int,
                  let width = raw["width"] as? String,
                  let unit = raw["unit"] as? String else { return nil }
            self.offset = offset
            self.width = width
            self.unit = unit
            self.match = raw["match"] as? String
        }
    }

    nonisolated(unsafe) private static var table: [String: [Spec]]?
    private static let lock = NSLock()

    private static func load() -> [String: [Spec]] {
        lock.lock()
        defer { lock.unlock() }
        if let table { return table }
        var made: [String: [Spec]] = [:]
        if let url = Bundle.module.url(forResource: "Resources/playtime",
                                       withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let raw = try? JSONSerialization.jsonObject(with: data)
               as? [String: Any] {
            for (serial, value) in raw {
                if let one = value as? [String: Any], let spec = Spec(one) {
                    made[serial] = [spec]
                } else if let many = value as? [[String: Any]] {
                    made[serial] = many.compactMap(Spec.init)
                }
            }
        }
        table = made
        return made
    }

    /// Секунды или `nil`, если игры нет в таблице.
    ///
    /// - Parameter signature: подпись сейва - по её первому слову
    ///   различаются игры под общим серийником.
    public static func seconds(_ block: [UInt8], serial: String,
                               signature: String) -> Int? {
        let variants = load()[serial] ?? []
        guard !variants.isEmpty else { return nil }
        let token = signature.split(separator: " ").first.map(String.init) ?? ""
        let spec: Spec?
        if variants.count == 1, variants[0].match == nil {
            spec = variants[0]
        } else {
            spec = variants.first { $0.match == token }
        }
        guard let spec else { return nil }

        let size = spec.width == "u16" ? 2 : 4
        guard spec.offset >= 0, spec.offset + size <= block.count else { return nil }
        var raw = 0
        for step in 0..<size {
            raw |= Int(block[spec.offset + step]) << (8 * step)
        }
        guard let divisor = divisors[spec.unit] else { return nil }
        let seconds = Int(Double(raw) / divisor)
        // Смещения найдены автопоиском и на части изданий промахиваются:
        // у Metal Gear Solid выходило 19 884 часа. Прохождение длиннее
        // тысячи часов - почти наверняка не время.
        return seconds < 1000 * 3600 ? seconds : nil
    }
}
