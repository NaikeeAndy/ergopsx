import Foundation

/// Разбор листингов. Разные прошивки отдают их по-разному, поэтому три вида.
public enum FTPListing {
    /// Строки из канала данных. Читаем как latin-1, а имена приводим обратно
    /// к тексту: сперва UTF-8, иначе оставляем как есть.
    public static func lines(_ data: Data) -> [String] {
        data.split(separator: 0x0A).map { chunk in
            var bytes = Array(chunk)
            if bytes.last == 0x0D { bytes.removeLast() }
            return decode(bytes)
        }
    }

    public static func decode(_ bytes: [UInt8]) -> String {
        if let text = String(bytes: bytes, encoding: .utf8) { return text }
        return String(bytes.map { Character(UnicodeScalar($0)) })
    }

    /// MLSD: `type=dir;size=0; имя`
    public static func parseMLSD(_ lines: [String]) -> [Entry] {
        var out: [Entry] = []
        for line in lines {
            guard let space = line.firstIndex(of: " ") else { continue }
            let name = String(line[line.index(after: space)...])
            if name.isEmpty || name == "." || name == ".." { continue }
            var size = 0
            var isDirectory = false
            for fact in line[line.startIndex..<space].split(separator: ";") {
                let parts = fact.split(separator: "=", maxSplits: 1)
                guard parts.count == 2 else { continue }
                switch parts[0].lowercased() {
                case "size": size = Int(parts[1]) ?? 0
                case "type": isDirectory = parts[1] == "dir"
                default: break
                }
            }
            out.append(Entry(name: name, size: size, isDirectory: isDirectory))
        }
        return out
    }

    /// LIST в стиле Unix: `drwxr-xr-x 1 root root 0 Dec 31 23:59 имя`
    public static func parseUnix(_ lines: [String]) -> [Entry] {
        var out: [Entry] = []
        for line in lines {
            let parts = line.split(separator: " ", maxSplits: 8,
                                   omittingEmptySubsequences: true)
            guard parts.count >= 9 else { continue }
            let name = String(parts[8])
            if name == "." || name == ".." { continue }
            out.append(Entry(name: name, size: Int(parts[4]) ?? 0,
                             isDirectory: line.first == "d"))
        }
        return out
    }

    public typealias Entry = FTPClient.Entry
}
