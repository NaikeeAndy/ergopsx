import Foundation
import MemCardKit

/// Папки с сейвами. Их может быть сколько угодно: коллекция, выгрузки
/// с консолей, чужие карты - всё сканируется при запуске и попадает
/// в один список с группировкой по играм.
///
/// Хранятся в **обычном файле настроек**, а не в системном хранилище:
/// его видно, можно открыть, поправить руками и положить в резервную
/// копию. Путь - `~/Library/Application Support/MemCardSaver/config.json`.
@MainActor
@Observable
final class Folders {
    private(set) var urls: [URL] = []
    /// Что не удалось прочитать из конфига - показываем, а не молчим.
    private(set) var missing: [String] = []

    /// Старый ключ на одну папку - переносим из него при первом запуске.
    private static let legacyOne = "collectionFolder"
    private static let legacyMany = "collectionFolders"

    nonisolated static var configURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask)[0]
        return base.appending(path: "MemCardSaver").appending(path: "config.json")
    }

    struct Config: Codable {
        var folders: [String]
        /// Папки с образами игр на консолях, по названию профиля.
        /// Их может быть несколько: у PS3 обычно флешка и диск.
        var games: [String: [String]]?
        /// Язык приложения.
        var language: String?
    }

    /// Где консоли обычно держат образы игр. Подставляется при первом
    /// запуске, дальше правится в настройках.
    static let knownGameFolders: [String: [String]] = [
        "PS3": ["/dev_usb000/PSXISO", "/dev_hdd0/PSXISO"],
        "Switch": ["/switch/duckstation/iso", "/switch/duckstation/psx"],
    ]

    private(set) var games: [String: [String]] = [:]
    var language: Lang = .en

    /// Папки с играми для консоли. Если ничего не задано - берём
    /// известные места, чтобы не заставлять вводить их руками.
    func gameFolders(for label: String) -> [String] {
        if let mine = games[label], !mine.isEmpty { return mine }
        return Folders.knownGameFolders[label] ?? []
    }

    func setGameFolders(_ list: [String], for label: String) {
        games[label] = list
        write()
    }

    func addGameFolder(_ path: String, for label: String) {
        var list = gameFolders(for: label)
        guard !list.contains(path) else { return }
        list.append(path)
        setGameFolders(list, for: label)
    }

    func removeGameFolder(_ path: String, for label: String) {
        setGameFolders(gameFolders(for: label).filter { $0 != path }, for: label)
    }

    func setLanguage(_ lang: Lang) {
        language = lang
        write()
    }

    init() { load() }

    func load() {
        missing = []
        if let config = Folders.read() {
            games = config.games ?? [:]
            language = Lang(rawValue: config.language ?? "en") ?? .en
            // Известные места на консолях проставляем сами: иначе
            // пользователю пришлось бы вводить их руками, зная наизусть.
            let needsDefaults = config.games == nil || config.language == nil
            var found: [URL] = []
            for path in config.folders {
                let url = URL(fileURLWithPath: path)
                if FileManager.default.fileExists(atPath: url.path) {
                    found.append(url)
                } else {
                    missing.append(path)
                }
            }
            urls = found
            if needsDefaults {
                if games.isEmpty { games = Folders.knownGameFolders }
                write()
            }
            return
        }
        // Первый запуск на новом хранилище: переносим то, что помнила
        // прежняя версия, и сразу записываем в файл.
        urls = Folders.fromDefaults()
        if !urls.isEmpty { write() }
    }

    func add(_ folder: URL) {
        guard !urls.contains(where: { $0.path == folder.path }) else { return }
        urls.append(folder)
        write()
    }

    func remove(_ folder: URL) {
        urls.removeAll { $0.path == folder.path }
        write()
    }

    /// Записывает конфиг. Читаемый: с отступами и без экранирования путей.
    func write() {
        let url = Folders.configURL
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes,
                                    .sortedKeys]
        let config = Config(folders: urls.map(\.path),
                            games: games.isEmpty ? Folders.knownGameFolders : games,
                            language: language.rawValue)
        guard let data = try? encoder.encode(config) else { return }
        try? data.write(to: url)
    }

    /// Список из файла настроек - для самопроверки, которой окно не нужно.
    nonisolated static func stored() -> [URL] {
        (read()?.folders ?? [])
            .map { URL(fileURLWithPath: $0) }
            .filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    nonisolated static func read() -> Config? {
        guard let data = try? Data(contentsOf: configURL),
              let config = try? JSONDecoder().decode(Config.self, from: data)
        else { return nil }
        return config
    }

    /// Что помнила прежняя версия в системном хранилище.
    static func fromDefaults() -> [URL] {
        let store = UserDefaults.standard
        var found: [URL] = []
        if let list = store.array(forKey: legacyMany) as? [Data] {
            found += list.compactMap(resolve)
        }
        if found.isEmpty, let one = store.data(forKey: legacyOne),
           let url = resolve(one) {
            found.append(url)
        }
        if found.isEmpty, let nearby = nearby() { found.append(nearby) }
        return found
    }

    static func resolve(_ bookmark: Data) -> URL? {
        var stale = false
        guard let url = try? URL(resolvingBookmarkData: bookmark,
                                 options: .withSecurityScope,
                                 relativeTo: nil,
                                 bookmarkDataIsStale: &stale),
              FileManager.default.fileExists(atPath: url.path) else { return nil }
        _ = url.startAccessingSecurityScopedResource()
        return url
    }

    /// Папка `saves` рядом с проектом - чтобы при запуске из исходников
    /// не выбирать её каждый раз руками.
    static func nearby() -> URL? {
        var here = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        for _ in 0..<4 {
            let candidate = here.appending(path: "saves")
            var isDirectory: ObjCBool = false
            if FileManager.default.fileExists(atPath: candidate.path,
                                              isDirectory: &isDirectory),
               isDirectory.boolValue {
                return candidate
            }
            here = here.deletingLastPathComponent()
        }
        return nil
    }
}
