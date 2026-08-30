import Foundation

/// Язык приложения. Хранится в файле настроек рядом с папками.
public enum Lang: String, CaseIterable, Identifiable, Sendable {
    case en, ru, fr, de, ja, zh, pl
    public var id: String { rawValue }

    /// Название языка на нём самом - так его узнают, не зная текущего.
    public var label: String {
        switch self {
        case .en: "English"
        case .ru: "Русский"
        case .fr: "Français"
        case .de: "Deutsch"
        case .ja: "日本語"
        case .zh: "中文"
        case .pl: "Polski"
        }
    }
}

/// Строки интерфейса.
///
/// **Ключ - английская строка.** Английский здесь исходный: он написан
/// прямо в коде, остальные языки лежат таблицами в `Resources/i18n`.
/// Нет перевода - показывается ключ, то есть английский, а не пустое
/// место и не имя переменной.
///
/// Своя таблица, а не `.strings` из бандла: у приложения, собранного
/// пакетом SPM, ресурсы лежат в отдельном бандле, и стандартная
/// локализация до них не дотягивается. Заодно язык переключается на
/// лету, без перезапуска.
///
/// **Не привязан к главному потоку намеренно.** Разбор сейвов идёт в
/// фоновой задаче, и подписи полей собираются там же - с `@MainActor`
/// они были бы недоступны.
public enum L {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var value: Lang = .en
    nonisolated(unsafe) private static var table: [String: String] = [:]
    nonisolated(unsafe) private static var plurals: [String: [String: String]] = [:]

    public static var current: Lang {
        get { lock.lock(); defer { lock.unlock() }; return value }
        set {
            let (words, forms) = L.load(newValue)
            lock.lock()
            value = newValue
            table = words
            plurals = forms
            lock.unlock()
        }
    }

    /// Строка по ключу. Аргументы подставляются вместо `{0}`, `{1}` и так
    /// далее - порядок в переводе может быть любым, языки строят фразу
    /// по-разному.
    public static func t(_ key: String, _ args: Any...) -> String {
        lock.lock()
        var out = table[key]
        lock.unlock()
        // Одинаковые английские слова с разным смыслом различаются
        // пометкой после `@@`: «Save@@verb» - кнопка, «Save» - сейв.
        // Наружу пометка не идёт.
        if out == nil { out = key.components(separatedBy: "@@")[0] }
        var text = out!
        for (index, value) in args.enumerated() {
            text = text.replacingOccurrences(of: "{\(index)}", with: String(describing: value))
        }
        if text.contains("{{") || text.contains("}}") {
            text = text.replacingOccurrences(of: "{{", with: "{")
                       .replacingOccurrences(of: "}}", with: "}")
        }
        return text
    }

    /// Слово при числе. У русского и польского три формы, у французского
    /// и немецкого две, у японского и китайского одна - выбирает язык,
    /// а не место вызова.
    public static func plural(_ noun: String, _ count: Int) -> String {
        lock.lock()
        let forms = plurals[noun]
        let code = value
        lock.unlock()
        guard let forms else { return noun }
        return forms[L.form(code, count)] ?? forms["other"] ?? noun
    }

    private static func form(_ code: Lang, _ count: Int) -> String {
        switch code {
        case .ja, .zh:
            return "other"
        case .ru, .pl:
            let ten = count % 10, hundred = count % 100
            if ten == 1 && hundred != 11 { return "one" }
            if (2...4).contains(ten) && !(12...14).contains(hundred) { return "few" }
            return "many"
        case .fr:
            return count < 2 ? "one" : "other"
        case .en, .de:
            return count == 1 ? "one" : "other"
        }
    }

    private static func load(_ code: Lang) -> ([String: String], [String: [String: String]]) {
        guard let url = Bundle.module.url(forResource: "Resources/i18n/\(code.rawValue)",
                                          withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return ([:], [:]) }
        var words: [String: String] = [:]
        var forms: [String: [String: String]] = [:]
        for (key, value) in raw {
            if let text = value as? String {
                words[key] = text
            } else if let group = value as? [String: String], key.hasPrefix("plural:") {
                forms[String(key.dropFirst("plural:".count))] = group
            }
        }
        return (words, forms)
    }
}
