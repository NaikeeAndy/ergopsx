import Foundation

/// Универсальный разбор по декларативным шаблонам game-tools-collection.
///
/// Даёт простые поля (число, флаг, значение из справочника) по любой игре,
/// для которой есть шаблон. Составные разделы - отряды, инвентари - сюда
/// не попадают: они у каждой игры устроены по-своему.
public struct Templates: Sendable {
    /// Игры с отдельным подробным модулем - универсальный разбор для них лишний.
    static let handwritten: Set<String> = [
        "final-fantasy-tactics", "castlevania-symphony-of-the-night",
        "final-fantasy-ix", "resident-evil", "final-fantasy-viii",
    ]

    /// Ниже `0x100` у шаблона идут поля заголовка блока - подпись, иконка.
    /// Они лежат на месте всегда, сдвигать их нельзя: сдвиг относится только
    /// к данным игры.
    static let headerLimit = 0x100

    public struct Field: Codable, Sendable {
        public var name: String
        public var value: String
        public var raw: Int
    }

    public struct Section: Codable, Sendable {
        public var name: String
        public var total: Int
        public var set: [String]
    }

    public struct Overview: Codable, Sendable {
        public var game: String
        public var fields: [Field]
        public var sections: [Section]
    }

    struct FieldSpec: Sendable {
        let name: String
        let type: String
        let offset: Int
        let bit: Int
        let bitStart: Int?
        let bitLength: Int?
        let resource: String?
    }

    struct FlagSpec: Sendable {
        let offset: Int
        let bit: Int
        let label: String
    }

    struct SectionSpec: Sendable {
        let name: String
        let flags: [FlagSpec]
    }

    struct Spec: Sendable {
        let game: String
        let fields: [FieldSpec]
        let sections: [SectionSpec]
        let resources: [String: [String: String]]
    }

    private let bySerial: [String: Spec]

    public init() {
        bySerial = Templates.parse()
    }

    private static func parse() -> [String: Spec] {
        var index: [String: Spec] = [:]
        guard let url = Bundle.module.url(forResource: "Resources/templates",
                                          withExtension: "json"),
              let raw = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: raw) as? [String: Any]
        else { return index }

        for (game, value) in root {
            guard let spec = value as? [String: Any],
                  let serials = spec["serials"] as? [String] else { continue }

            var resources: [String: [String: String]] = [:]
            for (name, table) in spec["resources"] as? [String: Any] ?? [:] {
                if let dict = table as? [String: Any] {
                    resources[name] = dict.mapValues { "\($0)" }
                }
            }

            let fields = (spec["fields"] as? [[String: Any]] ?? []).compactMap {
                entry -> FieldSpec? in
                guard let name = entry["n"] as? String,
                      let type = entry["t"] as? String,
                      let offset = entry["o"] as? Int else { return nil }
                return FieldSpec(name: name, type: type, offset: offset,
                                 bit: entry["b"] as? Int ?? 0,
                                 bitStart: entry["bs"] as? Int,
                                 bitLength: entry["bl"] as? Int,
                                 resource: entry["r"] as? String)
            }

            let sections = (spec["flags"] as? [[String: Any]] ?? []).compactMap {
                entry -> SectionSpec? in
                guard let name = entry["n"] as? String,
                      let rows = entry["f"] as? [[Any]] else { return nil }
                let flags = rows.compactMap { row -> FlagSpec? in
                    guard row.count >= 3, let offset = row[0] as? Int,
                          let bit = row[1] as? Int,
                          let label = row[2] as? String else { return nil }
                    return FlagSpec(offset: offset, bit: bit, label: label)
                }
                return SectionSpec(name: name, flags: flags)
            }

            let parsed = Spec(game: game, fields: fields, sections: sections,
                              resources: resources)
            for serial in serials { index[serial] = parsed }
        }
        return index
    }

    public var count: Int { bySerial.count }

    static let sizes: [String: Int] = [
        "uint8": 1, "int8": 1, "uint16": 2, "int16": 2,
        "uint32": 4, "int32": 4, "lower4": 1, "upper4": 1,
    ]

    static func read(_ block: [UInt8], type: String, at offset: Int) -> Int? {
        guard let size = sizes[type], offset >= 0, offset + size <= block.count
        else { return nil }
        let slice = block[...]
        switch type {
        case "uint8": return Int(block[offset])
        case "int8": return Int(Int8(bitPattern: block[offset]))
        case "uint16": return Int(read16(slice, at: offset))
        case "int16": return Int(Int16(bitPattern: read16(slice, at: offset)))
        case "uint32": return Int(read32(slice, at: offset))
        case "int32": return Int(Int32(bitPattern: read32(slice, at: offset)))
        case "lower4": return Int(block[offset] & 0x0F)
        case "upper4": return Int(block[offset] >> 4)
        default: return nil
        }
    }

    static func field(_ block: [UInt8], _ spec: FieldSpec, base: Int) -> Int? {
        let offset = spec.offset + (spec.offset >= headerLimit ? base : 0)
        if spec.type == "bit" {
            guard offset >= 0, offset < block.count else { return nil }
            return (Int(block[offset]) >> spec.bit) & 1
        }
        guard var value = read(block, type: spec.type, at: offset) else { return nil }
        // Часть полей упакована битами внутри числа: у Crash Bandicoot в одном
        // u16 лежат и номер уровня, и число самоцветов. Без распаковки оба
        // читались как всё число целиком и совпадали друг с другом.
        if let start = spec.bitStart, let length = spec.bitLength {
            value = (value >> start) & ((1 << length) - 1)
        }
        return value
    }

    public func overview(_ block: [UInt8], serial: String) -> Overview? {
        guard let spec = bySerial[serial], !Templates.handwritten.contains(spec.game)
        else { return nil }
        let base = Identify.templateBase(block[...])

        // Одно и то же имя встречается по нескольку раз (у SotN «Experience»
        // есть и у героя, и у каждого фамильяра). Одноимённые различаем
        // смещением, иначе в выводе останется случайное последнее.
        var counts: [String: Int] = [:]
        for entry in spec.fields { counts[entry.name, default: 0] += 1 }

        var sections: [Section] = []
        for section in spec.sections {
            // Часть шаблонов адресует всю карту памяти, и такие флаги за
            // пределами блока. Раздел, дотянуться до которого удалось меньше
            // чем наполовину, не показываем: «0 из 16» там означало бы не
            // «ничего не собрано», а «прочитать нечем».
            let reachable = section.flags.filter { base + $0.offset < block.count }
            if reachable.count * 2 < section.flags.count { continue }
            let on = reachable.compactMap { flag -> String? in
                (block[base + flag.offset] >> flag.bit) & 1 == 1 ? flag.label : nil
            }
            if !on.isEmpty {
                sections.append(Section(name: section.name,
                                        total: reachable.count, set: on))
            }
        }

        var fields: [Field] = []
        for entry in spec.fields {
            guard let value = Templates.field(block, entry, base: base) else { continue }
            var shown = String(value)
            if let resource = entry.resource, let table = spec.resources[resource],
               let found = table[String(value)] {
                shown = found
            }
            let label = counts[entry.name] == 1
                ? entry.name
                : "\(entry.name) @\(String(format: "0x%x", entry.offset))"
            fields.append(Field(name: label, value: shown, raw: value))
        }
        return Overview(game: spec.game, fields: fields, sections: sections)
    }
}
