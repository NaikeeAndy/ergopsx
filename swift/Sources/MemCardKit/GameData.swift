import Foundation

/// Таблицы названий, выгруженные из Python в JSON.
///
/// Файл общий для обоих движков: сверять там нечего, а переписывать
/// пять тысяч строк названий на Swift незачем. Формы разные - словари,
/// массивы, массивы массивов и отдельные числа, - потому что такими они
/// сложились в старом движке, и менять их значило бы менять смысл.
public struct GameData: Sendable {
    private let maps: [String: [String: String]]
    private let numberMaps: [String: [String: Int]]
    private let texts: [String: [String]]
    private let numbers: [String: [Int]]
    private let nested: [String: [[Int]]]
    /// Таблицы списком пар: у SotN так лежат реликвии, где важно смещение.
    private let pairs: [String: [(name: String, value: Int)]]
    private let scalars: [String: Int]
    private let tupleMaps: [String: [String: String]]
    private let numberRows: [String: [String: [Int]]]

    private struct Parsed {
        var maps: [String: [String: String]] = [:]
        var numberMaps: [String: [String: Int]] = [:]
        var texts: [String: [String]] = [:]
        var numbers: [String: [Int]] = [:]
        var nested: [String: [[Int]]] = [:]
        var pairs: [String: [(name: String, value: Int)]] = [:]
        var scalars: [String: Int] = [:]
        /// Словарь, где значение - пара: у FF6 так лежат предметы,
        /// название плюс служебное число.
        var tupleMaps: [String: [String: String]] = [:]
        /// Словарь, где значение - список чисел: у FF7 так лежат пороги AP
        /// для каждой материи.
        var numberRows: [String: [String: [Int]]] = [:]
    }

    public init(_ resource: String) {
        let parsed = GameData.parse(resource)
        maps = parsed.maps
        numberMaps = parsed.numberMaps
        texts = parsed.texts
        numbers = parsed.numbers
        nested = parsed.nested
        pairs = parsed.pairs
        scalars = parsed.scalars
        tupleMaps = parsed.tupleMaps
        numberRows = parsed.numberRows
    }

    private static func parse(_ resource: String) -> Parsed {
        var out = Parsed()
        guard let url = Bundle.module.url(forResource: "Resources/\(resource)",
                                          withExtension: "json"),
              let raw = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: raw) as? [String: Any]
        else { return out }

        for (name, value) in root {
            switch value {
            case let dict as [String: Any]:
                let strings = dict.compactMapValues { $0 as? String }
                if strings.count == dict.count {
                    out.maps[name] = strings
                    break
                }
                let firsts = dict.compactMapValues { ($0 as? [Any])?.first as? String }
                if firsts.count == dict.count {
                    out.tupleMaps[name] = firsts
                    break
                }
                let rows = dict.compactMapValues { $0 as? [Int] }
                if rows.count == dict.count {
                    out.numberRows[name] = rows
                    break
                }
                out.numberMaps[name] = dict.compactMapValues { $0 as? Int }
            case let list as [String]:
                out.texts[name] = list
            case let list as [Int]:
                out.numbers[name] = list
            case let list as [[Int]]:
                out.nested[name] = list
            case let list as [[Any]]:
                out.pairs[name] = list.compactMap {
                    guard $0.count >= 2, let key = $0[0] as? String,
                          let number = $0[1] as? Int else { return nil }
                    return (key, number)
                }
            case let number as Int:
                out.scalars[name] = number
            default:
                continue
            }
        }
        return out
    }

    /// Название по числовому ключу - хоть из словаря, хоть из массива.
    public func name(_ table: String, _ key: Int) -> String? {
        if let found = maps[table]?[String(key)] { return found }
        if let found = tupleMaps[table]?[String(key)] { return found }
        if let list = texts[table], key >= 0, key < list.count { return list[key] }
        return nil
    }

    /// Первое непустое из нескольких таблиц - так адресуются самоцветы FF9:
    /// они надеваются как аксессуары, но лежат в общем справочнике предметов.
    public func name(_ candidates: [String], _ key: Int) -> String? {
        for table in candidates {
            if let found = name(table, key) { return found }
        }
        return nil
    }

    /// Ключи словаря по возрастанию - когда важен порядок вывода.
    public func keys(_ table: String) -> [Int] {
        let source = maps[table]?.keys ?? tupleMaps[table]?.keys
        return (source?.compactMap { Int($0) } ?? []).sorted()
    }

    public func list(_ table: String) -> [(name: String, value: Int)] {
        pairs[table] ?? []
    }

    public func number(_ table: String, _ key: Int) -> Int? {
        if let found = numberMaps[table]?[String(key)] { return found }
        if let list = numbers[table], key >= 0, key < list.count { return list[key] }
        return nil
    }

    public func row(_ table: String, _ index: Int) -> [Int] {
        if let found = numberRows[table]?[String(index)] { return found }
        guard let list = nested[table], index >= 0, index < list.count else { return [] }
        return list[index]
    }

    public func scalar(_ name: String) -> Int? { scalars[name] }

    public func count(_ table: String) -> Int {
        maps[table]?.count ?? tupleMaps[table]?.count ?? texts[table]?.count
            ?? numbers[table]?.count ?? nested[table]?.count ?? pairs[table]?.count ?? 0
    }

    public var isEmpty: Bool {
        maps.isEmpty && texts.isEmpty && numbers.isEmpty && nested.isEmpty
            && pairs.isEmpty && scalars.isEmpty
    }
}
