import Foundation

/// FTP-клиент под две консоли: PS3 с webMAN MOD и Switch с ftpsrv.
///
/// Написан с нуля: в Swift FTP нет ни в стандартной библиотеке, ни в
/// Foundation. Особенности, ради которых пришлось повозиться, отмечены
/// по месту.
public actor FTPClient {
    public struct Entry: Sendable {
        public let name: String
        public let size: Int
        public let isDirectory: Bool
    }

    public struct Profile: Sendable {
        public var host: String
        public var port: UInt16
        public var user: String
        public var password: String
        public var path: String

        public init(host: String, port: UInt16 = 21, user: String = "anonymous",
                    password: String = "", path: String = "/") {
            self.host = host
            self.port = port
            self.user = user
            self.password = password
            self.path = path
        }
    }

    public struct Response: Sendable {
        public let code: Int
        public let text: String
        public var ok: Bool { (200..<400).contains(code) }
    }

    static let timeout: TimeInterval = 8
    /// Встроенный сервер sphaira отвечает не с первого раза: порт занят
    /// всегда, а обслуживать соединения он готов не сразу.
    static let attempts = 3

    private let profile: Profile
    private var control: FTPSocket?

    public init(_ profile: Profile) { self.profile = profile }

    public func connect() async throws {
        var last: Error = FTPError.timeout
        for attempt in 0..<FTPClient.attempts {
            do {
                let socket = FTPSocket(host: profile.host, port: profile.port)
                try await socket.open(timeout: FTPClient.timeout)
                control = socket
                _ = try await readResponse()
                let user = try await command("USER \(profile.user)")
                if user.code == 331 {
                    let pass = try await command("PASS \(profile.password)")
                    guard pass.ok else { throw FTPError.refused(pass.text) }
                } else if !user.ok {
                    throw FTPError.refused(user.text)
                }
                _ = try? await command("TYPE I")
                return
            } catch {
                last = error
                await control?.close()
                control = nil
                if attempt + 1 < FTPClient.attempts {
                    try? await Task.sleep(nanoseconds: 1_500_000_000)
                }
            }
        }
        throw last
    }

    public func disconnect() async {
        _ = try? await command("QUIT")
        await control?.close()
        control = nil
    }

    /// Ответ сервера, включая многострочные (`код-` в первой строке).
    private func readResponse() async throws -> Response {
        guard let control else { throw FTPError.transport(L.t("нет соединения", "not connected")) }
        var lines: [String] = []
        while true {
            guard let line = try await control.readLine() else { break }
            lines.append(line)
            let chars = Array(line)
            if chars.count >= 4, chars[3] == " ",
               let code = Int(String(chars[0..<3])) {
                return Response(code: code, text: lines.joined(separator: "\n"))
            }
            if chars.count >= 4, chars[3] == "-" { continue }
            if lines.count > 64 { break }
        }
        throw FTPError.badResponse(lines.joined(separator: "\n"))
    }

    @discardableResult
    public func command(_ text: String) async throws -> Response {
        guard let control else { throw FTPError.transport(L.t("нет соединения", "not connected")) }
        // Наружу отдаём байты UTF-8: канал открыт latin-1, иначе имя
        // с кириллицей уедет.
        var bytes = Array(text.utf8)
        bytes.append(contentsOf: [0x0D, 0x0A])
        try await control.send(Data(bytes))
        return try await readResponse()
    }

    /// Открывает канал данных через PASV.
    private func passive() async throws -> FTPSocket {
        let answer = try await command("PASV")
        guard answer.ok else { throw FTPError.refused(answer.text) }
        let numbers = answer.text.split(whereSeparator: { !$0.isNumber })
            .compactMap { Int($0) }
        guard numbers.count >= 6 else { throw FTPError.badResponse(answer.text) }
        let tail = Array(numbers.suffix(6))
        let port = UInt16(tail[4] * 256 + tail[5])
        let socket = FTPSocket(host: profile.host, port: port)
        try await socket.open(timeout: FTPClient.timeout)
        return socket
    }

    /// Данные команды целиком: PASV, команда, чтение канала, финальный ответ.
    private func transfer(_ text: String) async throws -> Data {
        let data = try await passive()
        let started = try await command(text)
        guard started.ok || started.code == 125 || started.code == 150 else {
            await data.close()
            throw FTPError.refused(started.text)
        }
        do {
            let payload = try await data.readAll()
            await data.close()
            // Завершающий ответ читаем всегда: непрочитанный отклик остаётся
            // в канале, и следующая проба падает уже не по своей вине.
            _ = try? await readResponse()
            return payload
        } catch {
            await data.close()
            _ = try? await readResponse()
            throw error
        }
    }

    /// Листинг: MLSD, потом LIST в стиле Unix, потом NLST.
    ///
    /// На одном способе полагаться нельзя: Switch не понимает MLSD, PS3
    /// понимает оба. Между пробами шлём NOOP - упавшая проба оставляет
    /// в канале непрочитанный ответ, и следующая падает уже не по своей вине.
    /// Листинг только через LIST.
    ///
    /// Нужен для свободного места на PS3: его прошивка кладёт в поле
    /// размера папки устройства, а MLSD отдаёт папкам ноль, и цифра
    /// пропадает. Другого способа спросить место по FTP нет.
    public func listUnix(_ path: String) async throws -> [Entry] {
        let raw = try await transfer("LIST \(path.isEmpty ? "/" : path)")
        return FTPListing.parseUnix(FTPListing.lines(raw))
    }

    public func list(_ path: String) async throws -> [Entry] {
        let target = path.isEmpty ? "/" : path
        var trouble: [String] = []

        do {
            let raw = try await transfer("MLSD \(target)")
            let parsed = FTPListing.parseMLSD(FTPListing.lines(raw))
            if !parsed.isEmpty { return parsed }
            trouble.append(L.t("MLSD: пусто", "MLSD: empty"))
        } catch {
            trouble.append("MLSD: \(error)")
        }
        _ = try? await command("NOOP")

        do {
            let raw = try await transfer("LIST \(target)")
            let parsed = FTPListing.parseUnix(FTPListing.lines(raw))
            if !parsed.isEmpty { return parsed }
            trouble.append(L.t("LIST: разобрано 0 из ", "LIST: parsed 0 of ")
                           + L.t("\(FTPListing.lines(raw).count) строк", "\(FTPListing.lines(raw).count) lines"))
        } catch {
            trouble.append("LIST: \(error)")
        }
        _ = try? await command("NOOP")

        // Совсем скупой сервер: только имена, тип определяем попыткой войти.
        do {
            let raw = try await transfer("NLST \(target)")
            var out: [Entry] = []
            for line in FTPListing.lines(raw) {
                let name = (line as NSString).lastPathComponent
                if name.isEmpty || name == "." || name == ".." { continue }
                let full = target.hasSuffix("/") ? target + name : target + "/" + name
                let entered = (try? await command("CWD \(full)"))?.ok ?? false
                out.append(Entry(name: name, size: 0, isDirectory: entered))
            }
            if !out.isEmpty { return out }
            trouble.append(L.t("NLST: пусто", "NLST: empty"))
        } catch {
            trouble.append("NLST: \(error)")
        }
        throw FTPError.badResponse(trouble.joined(separator: " · "))
    }

    public func download(_ path: String) async throws -> Data {
        try await transfer("RETR \(path)")
    }

    public func upload(_ path: String, _ payload: Data) async throws {
        let data = try await passive()
        let started = try await command("STOR \(path)")
        guard started.ok || started.code == 125 || started.code == 150 else {
            await data.close()
            throw FTPError.refused(started.text)
        }
        try await data.send(payload)
        try await data.finish()
        await data.close()
        let done = try await readResponse()
        guard done.ok else { throw FTPError.refused(done.text) }
    }

    /// Отправка файла кусками, с отчётом о ходе.
    ///
    /// Отдельно от отправки готовых байт: образ игры весит под гигабайт,
    /// и читать его в память целиком незачем - `send` ждёт, пока кусок
    /// уйдёт, так что чтение с диска само подстраивается под сеть.
    public func upload(_ path: String, from file: URL, chunk: Int = 1 << 19,
                       progress: (@Sendable (Int, Int) -> Void)? = nil)
        async throws {
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        let total = (try? FileManager.default
            .attributesOfItem(atPath: file.path)[.size] as? Int) ?? 0

        let data = try await passive()
        let started = try await command("STOR \(path)")
        guard started.ok || started.code == 125 || started.code == 150 else {
            await data.close()
            throw FTPError.refused(started.text)
        }

        var sent = 0
        progress?(0, total ?? 0)
        while true {
            let piece = try handle.read(upToCount: chunk) ?? Data()
            if piece.isEmpty { break }
            try await data.send(piece)
            sent += piece.count
            progress?(sent, total ?? 0)
        }
        try await data.finish()
        await data.close()
        let done = try await readResponse()
        guard done.ok else { throw FTPError.refused(done.text) }
    }

    /// Размер файла или `nil`, если такого нет. По этому же признаку
    /// приложение говорит «заменено» или «создано».
    public func size(_ path: String) async throws -> Int? {
        let answer = try await command("SIZE \(path)")
        guard answer.code == 213 else { return nil }
        let digits = answer.text.split(separator: " ").last.map(String.init) ?? ""
        return Int(digits.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    /// Удаление файла. Отдельно от папки: сервер отвечает ошибкой,
    /// если перепутать команду.
    public func remove(_ path: String) async throws {
        let answer = try await command("DELE \(path)")
        guard (200..<300).contains(answer.code) else {
            throw FTPError.refused("\(answer.code) \(answer.text)")
        }
    }

    public func removeDirectory(_ path: String) async throws {
        let answer = try await command("RMD \(path)")
        guard (200..<300).contains(answer.code) else {
            throw FTPError.refused("\(answer.code) \(answer.text)")
        }
    }

    public func makeDirectory(_ path: String) async throws {
        _ = try? await command("MKD \(path)")
    }
}
