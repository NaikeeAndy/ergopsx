import Foundation

/// Язык приложения. Хранится в файле настроек рядом с папками.
public enum Lang: String, CaseIterable, Identifiable, Sendable {
    case ru, en
    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .ru: "Русский"
        case .en: "English"
        }
    }
}

/// Строки интерфейса.
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
    nonisolated(unsafe) private static var value: Lang = .ru

    public static var current: Lang {
        get { lock.lock(); defer { lock.unlock() }; return value }
        set { lock.lock(); value = newValue; lock.unlock() }
    }

    public static func t(_ ru: String, _ en: String) -> String {
        current == .ru ? ru : en
    }
}
