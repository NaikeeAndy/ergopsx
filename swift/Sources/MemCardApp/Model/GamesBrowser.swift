import Foundation
import MemCardKit

/// Образы игр на консоли: посмотреть, положить новый, убрать лишний.
///
/// Отдельно от `ConsoleBrowser` намеренно: тот только смотрит и
/// скачивает, а здесь **пишем на консоль**, и цена ошибки другая.
@MainActor
@Observable
final class GamesBrowser {
    struct Game: Identifiable, Sendable {
        var id: String { path }
        var name: String
        var path: String
        var isDirectory: Bool
        /// Сколько занимает целиком: у папки - сумма файлов внутри.
        var size: Int
        /// Из чего состоит - показываем, что именно удалится.
        var files: [String]
    }

    private(set) var games: [Game] = []
    private(set) var busy = false
    private(set) var trouble: String?
    private(set) var note: String?
    /// Ход длинной операции: «3 из 7 файлов, 240 МБ».
    private(set) var progress: String?
    /// Отправлено байт из скольких - для полосы.
    private(set) var sent = 0
    private(set) var total = 0
    /// Какой файл идёт сейчас и сколько их всего.
    private(set) var fileName = ""
    private(set) var fileIndex = 0
    private(set) var fileCount = 0

    /// Доля отправленного, 0…1. Считается по всем файлам разом, а не
    /// по текущему: у игры PS1 один файл почти весь размер.
    var fraction: Double {
        guard total > 0 else { return 0 }
        return min(1, Double(sent) / Double(total))
    }

    var percent: Int { Int((fraction * 100).rounded()) }
    var uploading: Bool { total > 0 }
    private(set) var folder: String = ""
    private(set) var freeSpace: Int?
    /// Идёт ли досчёт размеров - показываем, чтобы список не выглядел
    /// неполным.
    private(set) var counting: String?

    let profile: ConsoleProfile

    init(_ profile: ConsoleProfile) { self.profile = profile }

    func open(_ path: String) async {
        busy = true
        trouble = nil
        note = nil
        defer { busy = false }
        folder = path

        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            let found = try await client.list(path)
            // Сначала показываем список, и только потом считаем размеры.
            // Раньше размер каждой игры выяснялся заходом внутрь её
            // папки, все 39 обходов подряд до первой отрисовки - окно
            // висело минутами и выглядело зависшим.
            games = found
                .filter { $0.name != "." && $0.name != ".." }
                .filter { $0.isDirectory || GamesBrowser.isImage($0.name) }
                .map {
                    Game(name: $0.name,
                         path: path.hasSuffix("/") ? path + $0.name
                                                   : path + "/" + $0.name,
                         isDirectory: $0.isDirectory,
                         size: $0.isDirectory ? -1 : $0.size,
                         files: $0.isDirectory ? [] : [$0.name])
                }
                .sorted {
                    $0.name.localizedStandardCompare($1.name) == .orderedAscending
                }
            await client.disconnect()
        } catch {
            trouble = "\(error)"
            games = []
            await client.disconnect()
            return
        }
        await measure()
    }

    /// Считает размеры папок по одной, дописывая их в уже показанный
    /// список. Соединение одно на всех - открывать его на каждую папку
    /// заново было бы втрое дольше.
    func measure() async {
        let folders = games.filter { $0.isDirectory && $0.size < 0 }
        guard !folders.isEmpty else { counting = nil; return }

        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            for (index, game) in folders.enumerated() {
                counting = L.t("measuring: {0} of {1}", index + 1, folders.count)
                guard let inside = try? await client.list(game.path) else { continue }
                var files: [String] = []
                var size = 0
                for entry in inside where entry.name != "." && entry.name != ".." {
                    if entry.isDirectory {
                        // Бывает вложенная папка - иначе игра показывалась
                        // как «0 Б».
                        let deeper = (try? await client.list(
                            game.path + "/" + entry.name)) ?? []
                        size += deeper.reduce(0) { $0 + $1.size }
                        files.append(entry.name + "/")
                    } else {
                        size += entry.size
                        files.append(entry.name)
                    }
                }
                if let at = games.firstIndex(where: { $0.path == game.path }) {
                    games[at].size = size
                    games[at].files = files
                }
            }
            await client.disconnect()
        } catch {
            await client.disconnect()
        }
        counting = nil
    }

    /// Кладёт образ на консоль. Папку с игрой переносим целиком:
    /// у PS1 образ - это .cue плюс .bin, по отдельности он не запустится.
    func upload(_ source: URL, into path: String) async {
        busy = true
        trouble = nil
        note = nil
        progress = nil
        defer {
            busy = false
            progress = nil
            sent = 0
            total = 0
            fileCount = 0
        }

        var files: [URL] = []
        var target = path
        var isDirectory: ObjCBool = false
        FileManager.default.fileExists(atPath: source.path,
                                       isDirectory: &isDirectory)
        if isDirectory.boolValue {
            let inside = (try? FileManager.default.contentsOfDirectory(
                at: source, includingPropertiesForKeys: nil)) ?? []
            files = inside.filter { !$0.hasDirectoryPath }
            target = path.hasSuffix("/") ? path + source.lastPathComponent
                                         : path + "/" + source.lastPathComponent
        } else {
            files = [source]
        }
        guard !files.isEmpty else {
            trouble = L.t("nothing to upload in \"{0}\"", source.lastPathComponent)
            return
        }

        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            if target != path { try? await client.makeDirectory(target) }
            // Общий размер считаем заранее: полоса должна идти
            // ровно, а не прыгать от файла к файлу.
            total = files.reduce(0) {
                $0 + ((try? FileManager.default
                    .attributesOfItem(atPath: $1.path)[.size] as? Int) ?? 0 ?? 0)
            }
            sent = 0
            fileCount = files.count
            var base = 0
            var done = 0
            for file in files {
                let remote = target.hasSuffix("/") ? target + file.lastPathComponent
                                                   : target + "/" + file.lastPathComponent
                // Уже лежащее не перезаписываем молча.
                if let there = try? await client.size(remote), there > 0 {
                    trouble = L.t("\"{0}\" already on the console — leaving it alone", file.lastPathComponent)
                    await client.disconnect()
                    return
                }
                fileIndex = done + 1
                fileName = file.lastPathComponent
                progress = L.t("{0} of {1}: {2}", done + 1, files.count, file.lastPathComponent)
                // Отправляем кусками и отчитываемся о ходе: образ игры
                // весит под гигабайт, читать его в память целиком незачем.
                let start = base
                try await client.upload(remote, from: file) { part, _ in
                    Task { @MainActor [weak self] in
                        self?.sent = start + part
                    }
                }
                base += (try? FileManager.default
                    .attributesOfItem(atPath: file.path)[.size] as? Int) ?? 0 ?? 0
                sent = base
                done += 1
            }
            await client.disconnect()
            note = L.t("uploaded: {0}", source.lastPathComponent)
            await open(path)
        } catch {
            trouble = "\(error)"
            await client.disconnect()
        }
    }

    /// Удаляет образ с консоли. Только по прямой команде пользователя.
    func delete(_ game: Game) async {
        busy = true
        trouble = nil
        note = nil
        defer { busy = false }

        let client = FTPClient(profile.ftp)
        do {
            try await client.connect()
            if game.isDirectory {
                for name in game.files {
                    try? await client.remove(game.path + "/" + name)
                }
                try await client.removeDirectory(game.path)
            } else {
                try await client.remove(game.path)
            }
            await client.disconnect()
            note = L.t("deleted: {0}", game.name)
            await open(folder)
        } catch {
            trouble = "\(error)"
            await client.disconnect()
        }
    }

    /// Свободное место тома. У PS3 его показывает LIST в поле размера
    /// папки устройства - другого способа по FTP нет.
    func checkSpace() async {
        guard profile.kind == "ps3" else { freeSpace = nil; return }
        let device = folder.split(separator: "/").first.map(String.init) ?? ""
        guard !device.isEmpty else { return }
        let client = FTPClient(profile.ftp)
        defer { Task { await client.disconnect() } }
        do {
            try await client.connect()
            // Именно LIST: MLSD отдаёт папкам нулевой размер, и место
            // показывалось как «0 Б».
            let root = try await client.listUnix("/")
            freeSpace = root.first { $0.name == device }?.size
        } catch {
            freeSpace = nil
        }
    }

    static let imageExtensions: Set<String> = [
        "bin", "cue", "img", "iso", "chd", "pbp", "ccd", "mdf", "ecm",
    ]

    static func isImage(_ name: String) -> Bool {
        imageExtensions.contains((name as NSString).pathExtension.lowercased())
    }

    static func size(_ bytes: Int) -> String {
        if bytes >= 1_073_741_824 {
            return String(format: L.t("%.2f GB"), Double(bytes) / 1_073_741_824)
        }
        if bytes >= 1_048_576 {
            return String(format: L.t("%.0f MB"), Double(bytes) / 1_048_576)
        }
        if bytes >= 1024 { return L.t("{0} KB", bytes / 1024) }
        return L.t("{0} B", bytes)
    }
}
