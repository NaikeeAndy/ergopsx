import Foundation
import MemCardKit
import CryptoKit

/// Выгрузка разбора в JSON - на этом строится сверка со старым движком.
///
///     memcard dump <база названий> <папка>

let args = CommandLine.arguments
// Проверка FTP на живой консоли: memcard ftp <host> <port> <user> <pass> <path>
// Скачивание: memcard ftp-get <host> <port> <user> <pass> <файл>
if CommandLine.arguments.count >= 7, CommandLine.arguments[1] == "ftp-get" {
    let a = CommandLine.arguments
    let client = FTPClient(FTPClient.Profile(host: a[2], port: UInt16(a[3]) ?? 21,
                                             user: a[4], password: a[5]))
    do {
        try await client.connect()
        let size = try await client.size(a[6])
        let payload = try await client.download(a[6])
        await client.disconnect()
        let digest = SHA256.hash(data: payload)
            .map { String(format: "%02x", $0) }.joined()
        print("\(payload.count) \(size ?? -1) \(digest)")
        exit(0)
    } catch {
        FileHandle.standardError.write(Data("не вышло: \(error)\n".utf8))
        exit(1)
    }
}

if CommandLine.arguments.count >= 7, CommandLine.arguments[1] == "ftp" {
    let a = CommandLine.arguments
    let profile = FTPClient.Profile(host: a[2], port: UInt16(a[3]) ?? 21,
                                    user: a[4], password: a[5], path: a[6])
    let client = FTPClient(profile)
    do {
        try await client.connect()
        let entries = try await client.list(profile.path)
        struct Row: Encodable { var name: String; var size: Int; var dir: Bool }
        let rows = entries.map { Row(name: $0.name, size: $0.size, dir: $0.isDirectory) }
            .sorted { $0.name < $1.name }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        FileHandle.standardOutput.write(try encoder.encode(rows))
        await client.disconnect()
        exit(0)
    } catch {
        FileHandle.standardError.write(Data("не вышло: \(error)\n".utf8))
        exit(1)
    }
}

// Castlevania Chronicles: сверка с экраном выбора игрока.
if CommandLine.arguments.count >= 4, CommandLine.arguments[1] == "chronicles" {
    let root = URL(fileURLWithPath: CommandLine.arguments[3])
    var seen = Set<String>()
    let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item), data.count >= PSX.block,
              let saves = Identify.saves(in: [UInt8](data),
                                         fallbackName: item.deletingPathExtension()
                                             .lastPathComponent) else { continue }
        for save in saves where Chronicles.matches(save) {
            let body = save.body
            guard seen.insert(body.fingerprintKey).inserted else { continue }
            guard let found = Chronicles.overview(body) else { continue }
            print("  \(found.name.padding(toLength: 10, withPad: " ", startingAt: 0))"
                + " stage \(String(format: "%02d", found.stage))"
                + "  \(String(format: "%02d", found.counter))"
                + "  уровень \(found.level)   сохранён \(found.saved)")
        }
    }
    exit(0)
}

// Parasite Eve II: сверка найденных полей с подписью игры.
if CommandLine.arguments.count >= 4, CommandLine.arguments[1] == "pe2" {
    let root = URL(fileURLWithPath: CommandLine.arguments[3])
    let titles = try Titles(contentsOf: URL(fileURLWithPath: CommandLine.arguments[2]))
    var seen = Set<String>(), ok = 0, total = 0
    var lines: [String] = []
    let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item), data.count >= PSX.block,
              let saves = Identify.saves(in: [UInt8](data),
                                         fallbackName: item.deletingPathExtension()
                                             .lastPathComponent) else { continue }
        for save in saves where ParasiteEve2.matches(save) {
            let body = save.body
            guard seen.insert(body.fingerprintKey).inserted else { continue }
            guard let found = ParasiteEve2.overview(body) else { continue }
            let info = Identify.describe(save, titles: titles)
            let shown = "\(found.playtime[0]):\(String(format: "%02d", found.playtime[1]))"
            total += 1
            let matched = info.internalName.contains(shown)
            if matched { ok += 1 }
            lines.append("  \(matched ? "OK " : "НЕТ") \(shown)  предметов \(found.items)"
                + "  в хранилище \(found.stored)  записей \(found.banks)"
                + "  подпись: \(info.internalName)")
        }
    }
    print("сейвов: \(total), время сошлось: \(ok)")
    for line in lines.sorted() { print(line) }
    exit(0)
}

// Vagrant Story: сверка расшифровки с подписью, которую пишет игра.
if CommandLine.arguments.count >= 4, CommandLine.arguments[1] == "vagrant" {
    struct Row: Encodable {
        var path: String
        var signature: String
        var playtime: String
        var matches: Bool
        var hp: String
        var mp: String
        var map: Int
        var actions: Int
        var weapons: [String]
        var storedWeapons: [String]
        var carried: [String]
        var stored: [String]
        var arts: Int
        var abilities: Int
        var kills: [Int]
        var rooms: Int
        var chests: Int
        var maxChain: Int
        var heals: Int
        var unopened: [String]
        var carriedItems: [String]
        var storedItems: [String]
    }
    var out: [Row] = []
    let root = URL(fileURLWithPath: CommandLine.arguments[3])
    let titles = try Titles(contentsOf: URL(fileURLWithPath: CommandLine.arguments[2]))
    let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)
    var seen = Set<String>()
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item), data.count >= PSX.block,
              let saves = Identify.saves(in: [UInt8](data),
                                         fallbackName: item.deletingPathExtension()
                                             .lastPathComponent) else { continue }
        for save in saves where Vagrant.matches(save) {
            let body = save.body
            guard seen.insert(body.map { String($0) }.joined().hashValue.description)
                .inserted else { continue }
            guard let found = Vagrant.overview(body) else { continue }
            let info = Identify.describe(save, titles: titles)
            let shown = String(format: "%d:%02d:%02d", found.playtime[0],
                               found.playtime[1], found.playtime[2])
            out.append(Row(path: item.lastPathComponent,
                           signature: info.internalName,
                           playtime: shown,
                           matches: info.internalName.contains(shown),
                           hp: "\(found.hp[0])/\(found.hp[1])",
                           mp: "\(found.mp[0])/\(found.mp[1])",
                           map: found.mapCompletion,
                           actions: found.actions,
                           weapons: found.weapons,
                           storedWeapons: found.storedWeapons,
                           carried: found.carried.map {
                               "\($0.name) \($0.used)/\($0.total)" },
                           stored: found.stored.map {
                               "\($0.name) \($0.used)/\($0.total)" },
                           arts: found.artsLearned,
                           abilities: found.abilities,
                           kills: found.kills,
                           rooms: found.rooms,
                           chests: found.chests,
                           maxChain: found.maxChain,
                           heals: found.heals,
                           unopened: found.unopened.map {
                               "\($0.name): \($0.used)" },
                           carriedItems: Vagrant.carried.compactMap { s in
                               guard let l = found.carriedItems[s.kind] else { return nil }
                               return "\(s.name): " + l.map {
                                   $0.used > 1 ? "\($0.name) x\($0.used)" : $0.name
                               }.joined(separator: ", ")
                           },
                           storedItems: Vagrant.stored.compactMap { s in
                               guard let l = found.storedItems[s.kind] else { return nil }
                               return "\(s.name): \(l.count) видов"
                           }))
        }
    }
    out.sort { $0.playtime < $1.playtime }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys, .prettyPrinted]
    FileHandle.standardOutput.write(try encoder.encode(out))
    exit(0)
}

// Иконки: хеш ленты RGBA по каждому сейву - по нему сверяется декодер.
if CommandLine.arguments.count >= 4, CommandLine.arguments[1] == "icons" {
    struct Row: Encodable {
        var path: String
        var name: String
        var frames: Int
        var digest: String
    }
    var out: [Row] = []
    let root = URL(fileURLWithPath: CommandLine.arguments[3])
    let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item), data.count >= PSX.block,
              let saves = Identify.saves(in: [UInt8](data),
                                         fallbackName: item.deletingPathExtension()
                                             .lastPathComponent) else { continue }
        let relative = item.path.replacingOccurrences(of: root.path + "/", with: "")
        for save in saves {
            guard let block = save.blocks.first,
                  let sheet = Icon.rgba(block) else { continue }
            let digest = SHA256.hash(data: Data(sheet.bytes))
                .map { String(format: "%02x", $0) }.joined()
            out.append(Row(path: relative, name: save.name,
                           frames: sheet.count, digest: digest))
        }
    }
    out.sort { ($0.path, $0.name) < ($1.path, $1.name) }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(out))
    exit(0)
}

guard args.count >= 4, ["dump", "rebuild", "sign", "convert"].contains(args[1]) else {
    FileHandle.standardError.write(
        Data("нужно: memcard dump|rebuild|sign|convert <titles.txt> <папка>\n".utf8))
    exit(2)
}

/// Конвертация: каждый сейв во все одиночные форматы и в каждый регион,
/// отдаём хеш результата. По нему сверяется конвертер.
if args[1] == "convert" {
    struct Converted: Encodable {
        var path: String
        var name: String
        var format: String
        var region: String
        var digest: String
    }
    var out: [Converted] = []
    let root = URL(fileURLWithPath: args[3])
    let walker = FileManager.default.enumerator(at: root,
                                                includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item), data.count >= PSX.block,
              let saves = Identify.saves(in: [UInt8](data),
                                         fallbackName: item.deletingPathExtension()
                                             .lastPathComponent) else { continue }
        let relative = item.path.replacingOccurrences(of: root.path + "/", with: "")
        for save in saves {
            for format in Convert.Single.allCases {
                for region in [nil, "america", "europe", "japan"] as [String?] {
                    let bytes = Convert.single(save, format: format, region: region)
                    let digest = SHA256.hash(data: Data(bytes))
                        .map { String(format: "%02x", $0) }.joined()
                    out.append(Converted(path: relative, name: save.name,
                                         format: format.rawValue,
                                         region: region ?? "-", digest: digest))
                }
            }
        }
    }
    out.sort { ($0.path, $0.name, $0.format, $0.region)
             < ($1.path, $1.name, $1.format, $1.region) }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(out))
    exit(0)
}

/// Подпись: по каждому PSV и VMP отдаём вердикт, посчитанную подпись
/// и хеш пересобранного файла. Плюс эталонный вектор FIPS-197.
if args[1] == "sign" {
    struct Signed: Encodable {
        var path: String
        var kind: String
        var ok: Bool
        var actual: String
        var resigned: String
    }
    func hex(_ bytes: [UInt8]) -> String {
        bytes.map { String(format: "%02x", $0) }.joined()
    }

    // FIPS-197, приложение B: единственный эталон, не зависящий от нашего кода.
    let key: [UInt8] = (0...15).map { UInt8($0) }
    let plain: [UInt8] = [0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
                          0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
    let cipher = AES128.encrypt(plain, key: key)
    let back = AES128.decrypt(cipher, key: key)
    var out: [Signed] = [
        Signed(path: "<FIPS-197>", kind: "aes",
               ok: hex(cipher) == "69c4e0d86a7b0430d8cdb78070b4c55a" && back == plain,
               actual: hex(cipher), resigned: hex(back)),
    ]

    let root = URL(fileURLWithPath: args[3])
    let walker = FileManager.default.enumerator(at: root,
                                                includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item) else { continue }
        let bytes = [UInt8](data)
        guard let checked = SonySign.verify(bytes) else { continue }
        let kind = bytes[1] == 0x56 ? "psv" : "vmp"
        let again = SonySign.resign(bytes) ?? []
        out.append(Signed(path: item.path.replacingOccurrences(of: root.path + "/",
                                                               with: ""),
                          kind: kind, ok: checked.ok, actual: hex(checked.actual),
                          resigned: hex(Array(SHA256.hash(data: Data(again)))))) 
    }
    out.sort { $0.path < $1.path }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(out))
    exit(0)
}

/// Пересборка: каждый образ карты разбираем и собираем заново, отдаём хеш.
/// По нему сверяется сборщик - байт в байт со старым движком.
if args[1] == "rebuild" {
    struct Rebuilt: Encodable {
        var path: String
        var digest: String
        var saves: Int
        var blocks: Int
        var error: String?
    }
    var out: [Rebuilt] = []
    let root = URL(fileURLWithPath: args[3])
    let walker = FileManager.default.enumerator(at: root,
                                                includingPropertiesForKeys: nil)
    while let item = walker?.nextObject() as? URL {
        guard let data = try? Data(contentsOf: item),
              let card = CardImage([UInt8](data)) else { continue }
        let relative = item.path.replacingOccurrences(of: root.path + "/", with: "")
        let saves = card.saves(origin: "образ")
        if saves.isEmpty { continue }
        do {
            let result = try CardBuilder.build(saves)
            let digest = SHA256.hash(data: Data(result.image))
                .map { String(format: "%02x", $0) }.joined()
            out.append(Rebuilt(path: relative, digest: digest,
                               saves: result.layout.count,
                               blocks: result.layout.reduce(0) { $0 + $1.blocks },
                               error: nil))
        } catch {
            out.append(Rebuilt(path: relative, digest: "", saves: 0, blocks: 0,
                               error: "\(error)"))
        }
    }
    out.sort { $0.path < $1.path }
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    FileHandle.standardOutput.write(try encoder.encode(out))
    exit(0)
}

let titles = try Titles(contentsOf: URL(fileURLWithPath: args[2]))
let root = URL(fileURLWithPath: args[3])
let ff9Data = GameData("psxff9data")
let fftData = GameData("psxfftdata")
let fftGrowth = FFTStats()
let sotnData = GameData("psxsotndata")
let ff8Data = GameData("psxff8data")
let ff8Tables = FF8.Tables()
let ff6Data = GameData("psxff6data")
let ff5Data = GameData("psxff5data")
let re1Data = GameData("psxre1data")
let ff7Data = GameData("psxff7data")
let templates = Templates()

struct Row: Encodable {
    var path: String
    var digest: String
    var info: SaveInfo
    var ff9: FF9.Overview?
    var fft: FFT.Overview?
    var sotn: SotN.Overview?
    var ff8: FF8.Overview?
    var ff6: FF6.Overview?
    var ff5: FF5.Overview?
    var re1: RE1.Overview?
    var ff7: FF7.Overview?
    var template: Templates.Overview?
}

var rows: [Row] = []
let walker = FileManager.default.enumerator(at: root,
                                            includingPropertiesForKeys: [.isRegularFileKey])
while let item = walker?.nextObject() as? URL {
    guard (try? item.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true,
          let data = try? Data(contentsOf: item), data.count >= PSX.block else { continue }
    let stem = item.deletingPathExtension().lastPathComponent
    guard let saves = Identify.saves(in: [UInt8](data), fallbackName: stem) else { continue }
    let relative = item.path.replacingOccurrences(of: root.path + "/", with: "")
    for save in saves {
        let body = save.body
        let info = Identify.describe(save, titles: titles)
        let digest = SHA256.hash(data: Data(body))
            .map { String(format: "%02x", $0) }.joined()
        rows.append(Row(path: relative, digest: digest,
                        info: info,
                        ff9: FF9.matches(save) ? FF9.overview(body, data: ff9Data) : nil,
                        fft: FFT.matches(save)
                            ? FFT.overview(body, data: fftData, growth: fftGrowth) : nil,
                        sotn: SotN.matches(save) ? SotN.overview(body, data: sotnData) : nil,
                        ff8: FF8.overview(body, region: info.region,
                                          data: ff8Data, tables: ff8Tables),
                        ff6: FF6.matches(save) ? FF6.overview(body, data: ff6Data) : nil,
                        ff5: FF5.matches(save) ? FF5.overview(body, data: ff5Data) : nil,
                        re1: RE1.matches(save) ? RE1.overview(body, data: re1Data) : nil,
                        ff7: FF7.matches(save) ? FF7.overview(body, data: ff7Data) : nil,
                        template: templates.overview(
                            body, serial: SaveName.normalize(SaveName(save.rawName).serial))))
    }
}

rows.sort { ($0.digest, $0.path) < ($1.digest, $1.path) }
let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys]
FileHandle.standardOutput.write(try encoder.encode(rows))
