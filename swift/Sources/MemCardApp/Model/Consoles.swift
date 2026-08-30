import Foundation
import MemCardKit

/// Профили консолей. Файл общий с Python (`tools/data/consoles.json`):
/// там же лежит пароль, поэтому права у файла `0600`, и наружу пароль
/// не показывается - только признак, что он задан.
struct ConsoleProfile: Identifiable, Sendable {
    var id: String { label }
    var label: String
    var kind: String
    var host: String
    var port: UInt16
    var user: String
    var password: String
    var path: String

    var hasPassword: Bool { !password.isEmpty }
    var address: String { "\(host):\(port)" }
    /// Без адреса подключаться некуда - строка «не задан» в интерфейсе.
    var hasAddress: Bool { !host.isEmpty }

    var ftp: FTPClient.Profile {
        FTPClient.Profile(host: host, port: port, user: user,
                          password: password, path: path)
    }
}

enum ConsoleStore {
    static func load(near collection: URL? = nil) -> [ConsoleProfile] {
        guard let url = file(near: collection), let data = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: data)
                  as? [String: Any] else { return [] }
        var out: [ConsoleProfile] = []
        for (label, value) in root {
            guard let entry = value as? [String: Any] else { continue }
            let kind = entry["kind"] as? String ?? "ps3"
            out.append(ConsoleProfile(
                label: label,
                kind: kind,
                host: entry["host"] as? String ?? "",
                port: UInt16(entry["port"] as? Int ?? (kind == "switch" ? 5000 : 21)),
                user: entry["user"] as? String ?? "anonymous",
                password: entry["password"] as? String ?? "",
                path: entry["path"] as? String ?? "/"))
        }
        return out.sorted { $0.label < $1.label }
    }

    /// Заготовки на случай, когда профилей ещё нет: адрес пустой,
    /// остальное - то, чем эти консоли отвечают по умолчанию.
    static let blanks: [ConsoleProfile] = [
        ConsoleProfile(label: "PS3", kind: "ps3", host: "", port: 21,
                       user: "anonymous", password: "",
                       path: "/dev_hdd0/savedata/vmc"),
        ConsoleProfile(label: "Switch", kind: "switch", host: "", port: 5000,
                       user: "psx", password: "",
                       path: "/switch/duckstation/memcards"),
    ]

    /// Список для настроек: что нашлось в файле плюс недостающие заготовки.
    static func all(near collection: URL? = nil) -> [ConsoleProfile] {
        var found = load(near: collection)
        for blank in blanks where !found.contains(where: { $0.kind == blank.kind }) {
            found.append(blank)
        }
        return found.sorted { $0.label < $1.label }
    }

    /// Пишет профили обратно в тот же файл, что читает Python. Одно место
    /// на оба движка: иначе исправленный в приложении адрес не увидела бы
    /// командная строка. Права `0600` - в файле пароль.
    static func save(_ profiles: [ConsoleProfile], near collection: URL?) throws {
        let url = try target(near: collection)
        var root: [String: Any] = [:]
        // Чужие поля в файле сохраняем: там может лежать то,
        // о чём приложение не знает.
        if let data = try? Data(contentsOf: url),
           let existing = try? JSONSerialization.jsonObject(with: data)
               as? [String: Any] {
            root = existing
        }
        for profile in profiles {
            // Пустой адрес в файл не пишем: профиля-заготовки там быть
            // не должно, иначе Python найдёт консоль без адреса.
            guard profile.hasAddress else { continue }
            var entry = root[profile.label] as? [String: Any] ?? [:]
            entry["kind"] = profile.kind
            entry["host"] = profile.host
            entry["port"] = Int(profile.port)
            entry["user"] = profile.user
            entry["password"] = profile.password
            entry["path"] = profile.path
            root[profile.label] = entry
        }
        let data = try JSONSerialization.data(
            withJSONObject: root,
            options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: url)
        try? FileManager.default.setAttributes([.posixPermissions: 0o600],
                                               ofItemAtPath: url.path)
    }

    /// Куда писать: сначала уже существующий файл, потом папка проекта
    /// рядом с коллекцией, и только если ничего нет - к настройкам.
    static func target(near collection: URL?) throws -> URL {
        if let found = file(near: collection) { return found }
        var here = collection
        for _ in 0..<5 {
            guard let step = here else { break }
            if FileManager.default.fileExists(atPath: step.appending(path: "tools").path) {
                return step.appending(path: "tools/data/consoles.json")
            }
            here = step.deletingLastPathComponent()
        }
        return Folders.configURL.deletingLastPathComponent()
            .appending(path: "consoles.json")
    }

    /// Отвечает ли консоль. Проверка лёгкая: вход и один листинг.
    static func check(_ profile: ConsoleProfile) async -> String {
        guard profile.hasAddress else { return L.t("адрес не задан", "no address set") }
        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            _ = try await client.list(profile.path)
            await client.disconnect()
            return L.t("на связи", "connected")
        } catch {
            await client.disconnect()
            return "\(error)"
        }
    }

    /// Профили лежат в репозитории рядом с сейвами. У приложения,
    /// запущенного двойным щелчком, рабочая папка - корень диска, поэтому
    /// отсчитываем от выбранной папки коллекции.
    static func file(near collection: URL?) -> URL? {
        var here = collection
            ?? URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        for _ in 0..<5 {
            let candidate = here.appending(path: "tools/data/consoles.json")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
            here = here.deletingLastPathComponent()
        }
        return nil
    }
}

/// Обход папок на консоли. Ничего не пишет: только смотрит и скачивает.
@MainActor
@Observable
final class ConsoleBrowser {
    private(set) var entries: [FTPClient.Entry] = []
    private(set) var path = ""
    private(set) var busy = false
    private(set) var trouble: String?
    private(set) var greeting: String?
    private(set) var downloaded: String?
    /// Что показано «на лету»: карта прочитана в память и разобрана,
    /// на диск при этом ничего не легло.
    private(set) var peeked: Peek?

    struct Peek: Sendable {
        var name: String
        var path: String
        var bytes: [UInt8]
        var items: [LibraryItem]
        /// Это образ карты, а не одиночный сейв - от этого зависит,
        /// в какие форматы его можно сохранить.
        var isCard: Bool
    }

    let profile: ConsoleProfile
    private var client: FTPClient?

    init(_ profile: ConsoleProfile) {
        self.profile = profile
        path = profile.path
    }

    func open(_ target: String? = nil) async {
        busy = true
        trouble = nil
        downloaded = nil
        defer { busy = false }

        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            let want = target ?? path
            let found = try await client.list(want)
            entries = found.sorted {
                $0.isDirectory == $1.isDirectory
                    ? $0.name.localizedStandardCompare($1.name) == .orderedAscending
                    : $0.isDirectory
            }
            path = want
            greeting = L.t("на связи", "connected")
            await client.disconnect()
        } catch {
            trouble = "\(error)"
            greeting = nil
            await client.disconnect()
        }
    }

    /// Читает файл в память и разбирает. Ничего не сохраняет: карта
    /// весит 128 КБ, ради просмотра писать её на диск незачем.
    func peek(_ name: String, engine: Engine) async {
        busy = true
        trouble = nil
        downloaded = nil
        defer { busy = false }

        let remote = path.hasSuffix("/") ? path + name : path + "/" + name
        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            let payload = try await client.download(remote)
            await client.disconnect()
            let bytes = [UInt8](payload)
            let stem = (name as NSString).deletingPathExtension
            guard let saves = Identify.saves(in: bytes, fallbackName: stem) else {
                peeked = nil
                trouble = L.t("«\(name)» - не сейв и не образ карты", "\"\(name)\" is neither a save nor a card image")
                return
            }
            var items: [LibraryItem] = []
            for save in saves {
                var made = LibraryItem(
                    save: save,
                    info: Identify.describe(save, titles: engine.titles),
                    origin: nil, remotePath: remote)
                made.playtime = Digest.of(made, engine: engine)?.playtime
                items.append(made)
            }
            peeked = Peek(name: name, path: remote, bytes: bytes,
                          items: items, isCard: CardImage(bytes) != nil)
        } catch {
            trouble = "\(error)"
            await client.disconnect()
        }
    }

    func closePeek() { peeked = nil }

    /// Сохранить прочитанное туда, куда указал пользователь. Скачивать
    /// заново не нужно - байты уже в памяти.
    func save(_ peek: Peek, to target: URL, format: SaveAs) throws {
        let bytes: [UInt8]
        switch format {
        case .asIs:
            bytes = peek.bytes
        case .card(let kind):
            bytes = try Convert.card(peek.items.map { $0.save }, format: kind).image
        case .single(let kind):
            guard let item = peek.items.first else { return }
            bytes = Convert.single(item.save, format: kind)
        }
        try Data(bytes).write(to: target)
    }

    enum SaveAs: Hashable, Sendable {
        case asIs
        case card(Convert.Card)
        case single(Convert.Single)

        /// Название с пояснением: по одним расширениям не понять,
        /// что куда годится.
        var label: String {
            switch self {
            case .asIs:
                return L.t("как есть — копия файла с консоли, байт в байт", "as is — a copy of the console file, byte for byte")
            case .card(let kind):
                switch kind {
                case .mcr:
                    return L.t("MCR — сырой образ карты, понимают почти все", "MCR — raw card image, understood almost everywhere")
                case .mcd:
                    return L.t("MCD — тот же образ; так карты зовёт DuckStation", "MCD — same image; DuckStation names cards this way")
                case .gme:
                    return L.t("GME — DexDrive, старые программы для ПК", "GME — DexDrive, old PC software")
                case .vmp:
                    return L.t("VMP — карта PSP и классики PSN, с подписью", "VMP — PSP and PSN classics card, signed")
                }
            case .single(let kind):
                switch kind {
                case .mcs:
                    return L.t("MCS — отдельный сейв, самый ходовой формат", "MCS — single save, the most common format")
                case .psv:
                    return L.t("PSV — отдельный сейв для PS3, с подписью", "PSV — single save for PS3, signed")
                case .raw:
                    return L.t("RAW — только тело сейва, без заголовка", "RAW — save body only, no header")
                }
            }
        }

        /// Подсказка под списком - что важно знать про выбранное.
        var note: String {
            switch self {
            case .asIs:
                return L.t("Ничего не пересобирается: то же, что лежит на консоли.", "Nothing is rebuilt: exactly what sits on the console.")
            case .card(.mcr):
                return L.t("То же содержимое, что у .VM1 на PS3 и .mcd на Switch — ", "Same content as .VM1 on PS3 and .mcd on Switch — ")
                    + L.t("различается только расширение.", "only the extension differs.")
            case .card(.mcd):
                return L.t("Чтобы карта подхватилась в DuckStation, имя файла должно ", "For DuckStation to pick the card up, the file name must ")
                    + L.t("совпадать с именем образа игры плюс номер слота.", "match the game image name plus the slot number.")
            case .card(.gme):
                return L.t("Заголовок на 3904 байта. Нужен только старым программам.", "A 3904-byte header. Only old software needs it.")
            case .card(.vmp):
                return L.t("Подпись пересчитывается — иначе консоль файл не примет.", "The signature is recomputed — otherwise the console rejects the file.")
            case .single(.psv):
                return L.t("Подпись пересчитывается. Имя сейва берётся из самого ", "The signature is recomputed. The save name comes from the ")
                    + L.t("сейва, а не из имени файла.", "save itself, not from the file name.")
            case .single(.mcs), .single(.raw):
                return L.t("Один сейв, а не вся карта.", "One save, not the whole card.")
            }
        }

        var ext: String {
            switch self {
            case .asIs: ""
            case .card(let k): k.rawValue
            case .single(let k): k.rawValue
            }
        }
    }

    func up() async {
        guard path != "/" else { return }
        let parent = (path as NSString).deletingLastPathComponent
        await open(parent.isEmpty ? "/" : parent)
    }

    /// Скачивает файл в папку коллекции. Одноимённое не перезаписываем.
    func download(_ name: String, into folder: URL) async {
        busy = true
        defer { busy = false }
        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            let remote = path.hasSuffix("/") ? path + name : path + "/" + name
            let payload = try await client.download(remote)
            await client.disconnect()

            let target = folder.appending(path: "_с консоли")
                .appending(path: profile.label)
            try FileManager.default.createDirectory(at: target,
                                                    withIntermediateDirectories: true)
            var file = target.appending(path: name)
            var attempt = 2
            while FileManager.default.fileExists(atPath: file.path) {
                let stem = (name as NSString).deletingPathExtension
                let ext = (name as NSString).pathExtension
                let suffix = ext.isEmpty ? "" : "." + ext
                file = target.appending(path: "\(stem) (\(attempt))\(suffix)")
                attempt += 1
            }
            try payload.write(to: file)
            // Говорим, куда именно легло: иначе «скачано» без пути
            // заставляет угадывать.
            let where_ = "_с консоли/\(profile.label)/\(file.lastPathComponent)"
            downloaded = L.t("скачано в \(where_)", "saved to \(where_)")
        } catch {
            trouble = "\(error)"
            await client.disconnect()
        }
    }
}
