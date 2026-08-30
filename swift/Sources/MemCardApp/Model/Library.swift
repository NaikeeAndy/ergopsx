import Foundation
import MemCardKit

/// Один сейв в том виде, в каком его показывает приложение.
struct LibraryItem: Identifiable, Sendable {
    let id = UUID()
    let save: Save
    let info: SaveInfo
    /// Файл, из которого сейв приехал. У сейвов с консоли путь удалённый.
    let origin: URL?
    let remotePath: String?

    /// Отпечаток содержимого - по нему сводятся дубли из разных контейнеров.
    ///
    /// Считается **один раз при загрузке**, а не при каждом обращении:
    /// это хеш по всему телу сейва, а тел в коллекции на 17 МБ. Как
    /// вычисляемое свойство оно пересчитывалось на каждый щелчок по меню,
    /// и по нескольку раз - список отзывался через секунды.
    let fingerprint: String
    let title: String
    let signature: String
    let blocks: Int
    /// Наигранное время в секундах, если игра его отдаёт. Считается при
    /// загрузке: сортировать по нему на лету значило бы разбирать
    /// сотни сейвов на каждый щелчок.
    var playtime: Int?
    /// Имя папки, из которой сейв приехал. Когда папок несколько,
    /// без этого непонятно, откуда что.
    var source: String { origin?.deletingLastPathComponent().lastPathComponent ?? "" }

    /// Наигранное время строкой, если оно есть.
    var clock: String? {
        guard let playtime else { return nil }
        return String(format: "%d:%02d", playtime / 3600, playtime / 60 % 60)
    }

    /// Строка для поиска, приведённая заранее: иначе она пересобиралась
    /// на каждое нажатие клавиши, по всей коллекции.
    let searchKey: String

    init(save: Save, info: SaveInfo, origin: URL?, remotePath: String?,
         playtime: Int? = nil) {
        self.playtime = playtime
        self.save = save
        self.info = info
        self.origin = origin
        self.remotePath = remotePath
        // Имя входит в отпечаток намеренно. Оно живёт в каталожном фрейме,
        // а не в теле, и по нему консоль и игра находят сейв. Два сейва
        // с одинаковым телом, но разными именами - это разные сейвы:
        // так, у Castlevania Chronicles с пиратки серийник отличался
        // четырьмя цифрами, и без имени в отпечатке исправленная копия
        // схлопывалась с исходной.
        fingerprint = (save.rawName + save.body).fingerprint
        let name = info.title.isEmpty ? info.serial : info.title
        title = name
        signature = info.internalName
        blocks = save.blocks.count
        searchKey = (name + "\u{1}" + info.internalName + "\u{1}" + info.serial)
            .lowercased()
    }
}

/// Чем упорядочен список.
enum SortOrder: String, CaseIterable, Identifiable {
    case playtime, title, natural
    var id: String { rawValue }

    var label: String {
        switch self {
        case .playtime: L.t("By playtime")
        case .title: L.t("By title")
        case .natural: L.t("As in files")
        }
    }
}

/// Что показано в главном списке.
enum Selection: Hashable {
    case everything
    case game(String)
    case cards
    case console(String)
}

@MainActor
@Observable
final class Library {
    private(set) var items: [LibraryItem] = []
    /// Готовые списки: собираются один раз при загрузке, дальше только
    /// отдаются. Пересобирать их на каждый обход вьюхи слишком дорого.
    private(set) var unique: [LibraryItem] = []
    private(set) var byGame: [String: [LibraryItem]] = [:]
    private(set) var cardSaves: [LibraryItem] = []
    private(set) var games: [(name: String, count: Int)] = []
    private(set) var cardCount = 0
    private(set) var loading = false
    private(set) var roots: [URL] = []
    var root: URL? { roots.first }
    /// Что не удалось прочитать - молчать об этом нельзя.
    private(set) var skipped: [(path: String, reason: String)] = []

    let titles: Titles
    let engine: Engine

    init() {
        engine = Engine()
        titles = engine.titles
    }

    /// Читает все указанные папки разом. Сейв, лежащий в двух папках,
    /// сведётся по содержимому и посчитается один раз.
    func load(_ folders: [URL]) async {
        roots = folders
        loading = true
        skipped = []
        defer { loading = false }

        let engine = self.engine
        let found = await Task.detached(priority: .userInitiated) {
            var all: [LibraryItem] = []
            var cards = 0
            var missed: [(path: String, reason: String)] = []
            for folder in folders {
                let part = Library.scan(folder, engine: engine)
                all += part.items
                cards += part.cards
                missed += part.skipped
            }
            return (items: all, cards: cards, skipped: missed)
        }.value

        items = found.items
        skipped = found.skipped
        cardCount = found.cards
        regroup()
    }

    private func regroup() {
        // Один и тот же сейв часто лежит в нескольких контейнерах:
        // сводим по содержимому, иначе коллекция кажется втрое больше.
        var seen: Set<String> = []
        var deduped: [LibraryItem] = []
        deduped.reserveCapacity(items.count)
        for item in items where seen.insert(item.fingerprint).inserted {
            deduped.append(item)
        }
        unique = deduped

        var grouped: [String: [LibraryItem]] = [:]
        var cards: [LibraryItem] = []
        for item in deduped {
            grouped[item.title, default: []].append(item)
            if item.save.slot != nil { cards.append(item) }
        }
        byGame = grouped
        cardSaves = cards

        var counts: [String: Int] = [:]
        for (name, list) in grouped { counts[name] = list.count }
        // Разбито на шаги намеренно: одним выражением компилятор не справляется.
        var list: [(name: String, count: Int)] = []
        for (name, count) in counts {
            list.append((name: name, count: count))
        }
        list.sort { left, right in
            if left.count != right.count { return left.count > right.count }
            return left.name < right.name
        }
        games = list
    }

    /// Файлы, в которых лежит тот же сейв. В списке дубли сведены
    /// в одну строку, и без этого не видно, где ещё он есть.
    func copies(of item: LibraryItem) -> [URL] {
        items.filter { $0.fingerprint == item.fingerprint }
            .compactMap(\.origin)
            .filter { $0.path != item.origin?.path }
    }

    /// Готовый список для выбранного раздела - без вычислений.
    func visible(_ selection: Selection) -> [LibraryItem] {
        switch selection {
        case .everything: unique
        case let .game(name): byGame[name] ?? []
        case .cards: cardSaves
        case .console: []
        }
    }

    /// Упорядоченный список. Сейвы без времени уходят вниз, а не
    /// притворяются нулевыми.
    func visible(_ selection: Selection, order: SortOrder) -> [LibraryItem] {
        let list = visible(selection)
        switch order {
        case .natural:
            return list
        case .title:
            return list.sorted {
                $0.title == $1.title
                    ? $0.signature < $1.signature
                    : $0.title.localizedStandardCompare($1.title) == .orderedAscending
            }
        case .playtime:
            return list.sorted { left, right in
                switch (left.playtime, right.playtime) {
                case let (a?, b?): return a == b ? left.title < right.title : a > b
                case (nil, _?): return false
                case (_?, nil): return true
                case (nil, nil): return left.title < right.title
                }
            }
        }
    }

    nonisolated static func scan(_ folder: URL, engine: Engine)
        -> (items: [LibraryItem], cards: Int, skipped: [(path: String, reason: String)]) {
        var items: [LibraryItem] = []
        var skipped: [(String, String)] = []
        var cards = 0

        let keys: [URLResourceKey] = [.isRegularFileKey, .fileSizeKey]
        guard let walker = FileManager.default.enumerator(
            at: folder, includingPropertiesForKeys: keys) else {
            return ([], 0, [])
        }
        while let item = walker.nextObject() as? URL {
            guard let values = try? item.resourceValues(forKeys: Set(keys)),
                  values.isRegularFile == true,
                  (values.fileSize ?? 0) >= PSX.block else { continue }
            guard let data = try? Data(contentsOf: item) else {
                skipped.append((item.lastPathComponent, L.t("could not be read")))
                continue
            }
            let bytes = [UInt8](data)
            let stem = item.deletingPathExtension().lastPathComponent
            guard let saves = Identify.saves(in: bytes, fallbackName: stem) else {
                // Архивы PocketStation и прочее, что сейвом не является.
                continue
            }
            if CardImage(bytes) != nil { cards += 1 }
            for save in saves {
                var made = LibraryItem(
                    save: save,
                    info: Identify.describe(save, titles: engine.titles),
                    origin: item, remotePath: nil)
                // Разбор всё равно понадобится - и панели справа, и
                // сортировке. Делаем его здесь, разом, в фоновой задаче.
                made.playtime = Digest.of(made, engine: engine)?.playtime
                items.append(made)
            }
        }
        return (items, cards, skipped.map { (path: $0.0, reason: $0.1) })
    }
}

/// Общие таблицы и справочники: грузятся один раз на запуск.
final class Engine: Sendable {
    let titles: Titles
    let templates: Templates
    let ff9: GameData
    let fft: GameData
    let fftGrowth: FFTStats
    let ff8: GameData
    let ff8Tables: FF8.Tables
    let ff7: GameData
    let ff6: GameData
    let ff5: GameData
    let sotn: GameData
    let re1: GameData

    init() {
        titles = Engine.loadTitles()
        templates = Templates()
        ff9 = GameData("psxff9data")
        fft = GameData("psxfftdata")
        fftGrowth = FFTStats()
        ff8 = GameData("psxff8data")
        ff8Tables = FF8.Tables()
        ff7 = GameData("psxff7data")
        ff6 = GameData("psxff6data")
        ff5 = GameData("psxff5data")
        sotn = GameData("psxsotndata")
        re1 = GameData("psxre1data")
    }

    /// Сначала ресурс внутри приложения, потом папка рядом с проектом -
    /// так работает и в собранном .app, и при запуске из исходников.
    static func loadTitles() -> Titles {
        if let bundled = Titles.bundled() { return bundled }
        return searchNearby()
    }

    static func searchNearby() -> Titles {
        let candidates = [
            "reference/psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt",
            "psxsaves/sd2psx-save-converter/BAT/TitlesDB_PS1_English.txt",
        ]
        var here = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        for _ in 0..<4 {
            for candidate in candidates {
                let path = here.appending(path: candidate)
                if let found = try? Titles(contentsOf: path), found.count > 0 {
                    return found
                }
            }
            here = here.deletingLastPathComponent()
        }
        return Titles(bySerial: [:])
    }
}

extension [UInt8] {
    /// Дешёвый отпечаток содержимого: длина плюс FNV-1a. Нужен только для
    /// сведения дублей внутри одного запуска, не для проверки целостности.
    var fingerprint: String {
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in self {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return "\(count):\(String(hash, radix: 16))"
    }
}
