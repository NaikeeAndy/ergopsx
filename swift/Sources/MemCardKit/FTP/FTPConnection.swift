import Foundation
import Network

/// Сокет с построчным чтением - основа и управляющего канала, и канала данных.
///
/// В Swift нет FTP-клиента ни в стандартной библиотеке, ни в Foundation:
/// из `URLSession` его убрали. Поэтому всё ниже написано поверх
/// Network.framework.
actor FTPSocket {
    private let connection: NWConnection
    private var buffer = Data()
    private var closed = false

    init(host: String, port: UInt16) {
        connection = NWConnection(
            host: NWEndpoint.Host(host),
            port: NWEndpoint.Port(rawValue: port) ?? 21,
            using: .tcp)
    }

    func open(timeout: TimeInterval) async throws {
        let once = Once()
        let connection = self.connection
        try await withCheckedThrowingContinuation {
            (done: CheckedContinuation<Void, Error>) in
            connection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    if once.claim() { done.resume() }
                case let .failed(error):
                    if once.claim() {
                        done.resume(throwing: FTPError.transport(error.localizedDescription))
                    }
                case .cancelled:
                    if once.claim() {
                        done.resume(throwing: FTPError.transport(L.t("соединение закрыто", "connection closed")))
                    }
                default:
                    break
                }
            }
            connection.start(queue: .global(qos: .userInitiated))
            Task {
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                if once.claim() {
                    connection.cancel()
                    done.resume(throwing: FTPError.timeout)
                }
            }
        }
    }

    /// `endIsFine` - для канала данных: закрытие сервером это конец передачи,
    /// а не сбой. На управляющем канале та же ошибка означала бы обрыв,
    /// и её надо поднимать наверх.
    /// Сколько ждать ответа, прежде чем считать соединение зависшим.
    ///
    /// Раньше времени ожидания не было вовсе: оно стояло только на
    /// установке соединения, а чтение ответа могло ждать бесконечно.
    /// Стоило прошивке подвиснуть после большой записи - и окно
    /// «зависало» насовсем, без единого способа выйти.
    static let replyTimeout: TimeInterval = 25

    private func receive(endIsFine: Bool) async throws -> Data {
        try await withCheckedThrowingContinuation { done in
            let answered = Once()
            Task {
                try? await Task.sleep(nanoseconds:
                    UInt64(FTPSocket.replyTimeout * 1_000_000_000))
                if answered.claim() { done.resume(throwing: FTPError.timeout) }
            }
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65536) {
                data, _, isComplete, error in
                guard answered.claim() else { return }
                if let data, !data.isEmpty {
                    done.resume(returning: data)
                } else if let error {
                    if endIsFine {
                        done.resume(returning: Data())
                    } else {
                        done.resume(throwing: FTPError.transport(error.localizedDescription))
                    }
                } else {
                    _ = isComplete
                    done.resume(returning: Data())
                }
            }
        }
    }

    /// Одна строка ответа без перевода строки. `nil` - канал закончился.
    func readLine() async throws -> String? {
        while true {
            if let index = buffer.firstIndex(of: 0x0A) {
                let line = buffer[buffer.startIndex..<index]
                buffer.removeSubrange(buffer.startIndex...index)
                // Управляющий канал читаем как latin-1: этот набор переносит
                // любые байты без потерь. webMAN дописывает в ответ температуру
                // консоли со знаком градуса (0xB0), и разбор как UTF-8 на нём
                // падает - при том, что данные приходят целыми.
                var bytes = Array(line)
                if bytes.last == 0x0D { bytes.removeLast() }
                return String(bytes.map { Character(UnicodeScalar($0)) })
            }
            let chunk = try await receive(endIsFine: false)
            if chunk.isEmpty {
                if buffer.isEmpty { return nil }
                let rest = String(buffer.map { Character(UnicodeScalar($0)) })
                buffer.removeAll()
                return rest
            }
            buffer.append(chunk)
        }
    }

    /// Читает канал до конца - так забираются данные RETR и листингов.
    func readAll() async throws -> Data {
        var out = buffer
        buffer.removeAll()
        while true {
            let chunk = try await receive(endIsFine: true)
            if chunk.isEmpty { break }
            out.append(chunk)
        }
        return out
    }

    func send(_ data: Data) async throws {
        try await withCheckedThrowingContinuation { (done: CheckedContinuation<Void, Error>) in
            connection.send(content: data, completion: .contentProcessed { error in
                if let error {
                    done.resume(throwing: FTPError.transport(error.localizedDescription))
                } else {
                    done.resume()
                }
            })
        }
    }

    /// Закрывает свою сторону, чтобы сервер увидел конец передачи.
    func finish() async throws {
        try await withCheckedThrowingContinuation { (done: CheckedContinuation<Void, Error>) in
            connection.send(content: nil, contentContext: .finalMessage,
                            isComplete: true, completion: .contentProcessed { _ in
                done.resume()
            })
        }
    }

    func close() {
        guard !closed else { return }
        closed = true
        connection.cancel()
    }
}

/// Одноразовый флажок: continuation можно возобновить ровно один раз,
/// а состояние соединения и таймаут приходят из разных потоков.
final class Once: @unchecked Sendable {
    private let lock = NSLock()
    private var done = false

    func claim() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        if done { return false }
        done = true
        return true
    }
}

public enum FTPError: Error, CustomStringConvertible {
    case transport(String)
    case timeout
    case refused(String)
    case noListing
    case badResponse(String)

    public var description: String {
        switch self {
        case let .transport(text): text
        case .timeout: L.t("истекло время ожидания", "timed out")
        case let .refused(text): text
        case .noListing: L.t("прошивка не поддержала ни MLSD, ни LIST, ни NLST", "the firmware supports neither MLSD, LIST nor NLST")
        case let .badResponse(text): L.t("непонятный ответ: \(text)", "unexpected reply: \(text)")
        }
    }
}
