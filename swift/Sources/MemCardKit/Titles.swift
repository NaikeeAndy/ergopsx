import Foundation

/// База названий игр по серийникам: 10 937 записей.
public struct Titles: Sendable {
    private let bySerial: [String: String]

    public init(bySerial: [String: String]) { self.bySerial = bySerial }

    /// Читает TitlesDB: `SLUS_009.58 Suikoden II` -> `SLUS-00958` / `Suikoden II`.
    public init(contentsOf url: URL) throws {
        let text = try String(contentsOf: url, encoding: .utf8)
        var map: [String: String] = [:]
        for line in text.split(separator: "\n", omittingEmptySubsequences: true) {
            guard let space = line.firstIndex(of: " ") else { continue }
            let serial = line[line.startIndex..<space]
            guard serial.contains("_") else { continue }
            let name = line[line.index(after: space)...]
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty else { continue }
            let key = serial.replacingOccurrences(of: "_", with: "-")
                            .replacingOccurrences(of: ".", with: "")
            map[key] = Titles.stripDisc(name)
        }
        bySerial = map
    }

    /// База, положенная ресурсом внутрь приложения.
    ///
    /// Приложение, запущенное двойным щелчком, работает из корня диска и
    /// репозиторий рядом с собой не найдёт - поэтому база едет с ним.
    public static func bundled() -> Titles? {
        guard let url = Bundle.module.url(forResource: "Resources/titles",
                                          withExtension: "json"),
              let raw = try? Data(contentsOf: url),
              let map = try? JSONSerialization.jsonObject(with: raw)
                  as? [String: String], !map.isEmpty else { return nil }
        return Titles(bySerial: map)
    }

    public var count: Int { bySerial.count }

    public subscript(serial: String) -> String? { bySerial[serial] }

    /// Номер диска в названии относится к диску, под которым выпущен серийник,
    /// а не к сейву. Многодисковые игры пишут сейв с серийником первого диска,
    /// чтобы он читался с любого, поэтому суффикс убираем: иначе сейв
    /// с третьего диска подписан первым.
    static func stripDisc(_ name: String) -> String {
        guard name.hasSuffix(")"), let open = name.lastIndex(of: "(") else { return name }
        let inside = name[name.index(after: open)..<name.index(before: name.endIndex)]
        guard inside.hasPrefix("Disc "),
              inside.dropFirst(5).allSatisfy(\.isNumber),
              !inside.dropFirst(5).isEmpty else { return name }
        return name[name.startIndex..<open].trimmingCharacters(in: .whitespaces)
    }
}
