import Foundation

/// Экранные статы Final Fantasy Tactics из сырых значений сейва.
///
/// В сейве лежат raw-статы - 24-битные числа, не зависящие от класса. То, что
/// игра рисует на экране, получается умножением на множитель текущего класса:
///
///     экранное = clamp(1, потолок, raw * M / 1638400)
///
/// Два разных числа на класс, и путать их нельзя: C влияет на рост raw
/// (навсегда), M - только на отображение. Здесь нужен M.
///
/// Константы - в `fft-growth.json`, источник AeroStar Battle Mechanics Guide
/// v6.5, §7.1-7.4. Ни одно число не зашито в код.
public struct FFTStats: Sendable {
    public static let stats = ["hp", "mp", "sp", "pa", "ma"]
    /// ID дженерик-классов идут подряд в том же порядке, что и в таблице guide'а.
    static let genericFirstID = 0x4A

    public struct Job: Sendable {
        public let name: String
        public let mult: [String: Int]
    }

    let divisor: Int
    let minDisplayed: Int
    let caps: [String: Int]
    let rawCaps: [String: Int]
    public let jobs: [Int: Job]

    public init() {
        guard let url = Bundle.module.url(forResource: "Resources/fft-growth",
                                          withExtension: "json"),
              let raw = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: raw) as? [String: Any]
        else {
            divisor = 1638400; minDisplayed = 1; caps = [:]; rawCaps = [:]; jobs = [:]
            return
        }
        let constants = root["constants"] as? [String: Any] ?? [:]
        divisor = constants["display_divisor"] as? Int ?? 1638400
        minDisplayed = constants["min_displayed"] as? Int ?? 1
        caps = (root["display_caps"] as? [String: Any] ?? [:]).compactMapValues { $0 as? Int }
        rawCaps = (root["functional_raw_caps"] as? [String: Any] ?? [:])
            .compactMapValues { $0 as? Int }

        var table: [Int: Job] = [:]
        // Дженерики: 0x4A и дальше по порядку, версии только для WotL пропускаем.
        let generics = (root["generic_jobs"] as? [[String: Any]] ?? [])
            .filter { ($0["wotl_only"] as? Bool) != true }
        for (offset, job) in generics.enumerated() {
            table[FFTStats.genericFirstID + offset] = FFTStats.job(job)
        }
        // Особые классы перечислены своими ID, иногда через дробь: "1E/34", "01-03".
        for job in root["special_jobs"] as? [[String: Any]] ?? [] {
            guard let ids = job["id"] as? String else { continue }
            for part in ids.split(separator: "/") {
                for value in FFTStats.expand(String(part)) {
                    table[value] = FFTStats.job(job)
                }
            }
        }
        jobs = table
    }

    static func job(_ raw: [String: Any]) -> Job {
        Job(name: raw["name"] as? String ?? "?",
            mult: (raw["mult"] as? [String: Any] ?? [:]).compactMapValues { $0 as? Int })
    }

    static func expand(_ part: String) -> [Int] {
        if part.contains("-") {
            let bounds = part.split(separator: "-").compactMap { Int($0, radix: 16) }
            guard bounds.count == 2, bounds[0] <= bounds[1] else { return [] }
            return Array(bounds[0]...bounds[1])
        }
        return Int(part, radix: 16).map { [$0] } ?? []
    }

    /// raw-статы -> экранные значения для данного класса.
    public func displayed(_ raw: [String: Int], job: Job?) -> [String: Int] {
        guard let job else { return [:] }
        var out: [String: Int] = [:]
        for stat in FFTStats.stats {
            guard let value = raw[stat], let mult = job.mult[stat],
                  let cap = caps[stat] else { continue }
            // Целочисленно и в одно выражение: дробями здесь пользоваться нельзя.
            out[stat] = max(minDisplayed, min(cap, value * mult / divisor))
        }
        return out
    }

    /// Какие статы уже упёрлись в функциональный потолок raw.
    public func capped(_ raw: [String: Int]) -> [String: Bool] {
        var out: [String: Bool] = [:]
        for stat in FFTStats.stats {
            out[stat] = (raw[stat] ?? 0) >= (rawCaps[stat] ?? Int.max)
        }
        return out
    }
}
