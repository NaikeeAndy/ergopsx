import Foundation

/// Перевод сейвов между контейнерами и смена региона.
public enum Convert {
    public enum Single: String, CaseIterable, Sendable { case mcs, psv, raw }
    /// `.mcd` - тот же сырой образ, что `.mcr`. Так называет карты DuckStation
    /// и его ядро SwanStation, а на Switch это единственный ходовой формат.
    public enum Card: String, CaseIterable, Sendable { case mcr, mcd, gme, vmp }

    /// Регион - два первых байта имени сейва. Менять можно только их:
    /// серийник игры при этом остаётся, потому что у изданий разных регионов
    /// это разные номера и соответствие ниоткуда не следует.
    static let regionCodes: [String: [UInt8]] = [
        "america": [0x42, 0x41], "europe": [0x42, 0x45], "japan": [0x42, 0x49],
    ]

    static let psvSize = 0x40, psvData = 0x44, psvName = 0x64, psvHeader = 0x84

    public static func withRegion(_ name: [UInt8], _ region: String?) -> [UInt8] {
        guard let region, let code = regionCodes[region.lowercased()],
              name.count >= 2 else { return name }
        return code + Array(name[2...])
    }

    /// MCS: каталожный фрейм и следом блоки сейва.
    public static func toMCS(_ name: [UInt8], _ blocks: [[UInt8]]) -> [UInt8] {
        var frame = [UInt8](repeating: 0, count: PSX.frame)
        frame[0] = SlotState.save.rawValue
        write32(&frame, at: 4, UInt32(blocks.count * PSX.block))
        write16(&frame, at: 8, 0xFFFF)
        var padded = Array(name.prefix(20))
        padded += [UInt8](repeating: 0, count: 20 - padded.count)
        frame.replaceSubrange(10..<30, with: padded)
        frame[PSX.frame - 1] = 0
        var checksum: UInt8 = 0
        for byte in frame.prefix(PSX.frame - 1) { checksum ^= byte }
        frame[PSX.frame - 1] = checksum
        return frame + blocks.flatMap { $0 }
    }

    public static func toRaw(_ name: [UInt8], _ blocks: [[UInt8]]) -> [UInt8] {
        blocks.flatMap { $0 }
    }

    /// PSV с пересчитанной подписью. Постоянная часть заголовка снята
    /// с настоящих файлов PS3, меняются размер, имя, salt seed и подпись.
    public static func toPSV(_ name: [UInt8], _ blocks: [[UInt8]]) -> [UInt8] {
        let payload = blocks.flatMap { $0 }
        var header = [UInt8](repeating: 0, count: psvHeader)
        header.replaceSubrange(0..<4, with: SonySign.psv.magic)
        header[0x38] = 0x14
        header[0x3C] = 0x01
        write32(&header, at: psvSize, UInt32(payload.count))
        write32(&header, at: psvData, UInt32(psvHeader))
        write32(&header, at: 0x48, 0x200)
        write32(&header, at: 0x5C, UInt32(payload.count))
        write32(&header, at: 0x60, 0x9003)
        var padded = Array(name.prefix(20))
        padded += [UInt8](repeating: 0, count: 20 - padded.count)
        header.replaceSubrange(psvName..<(psvName + 20), with: padded)
        // Salt seed выводится из имени: он должен быть каким-то, а от чего
        // именно зависит - неважно, подпись считается от него же.
        var seed = Array(padded.prefix(SonySign.seedLength))
        seed += [UInt8](repeating: 0, count: SonySign.seedLength - seed.count)
        return SonySign.resign(header + payload, seed: seed) ?? (header + payload)
    }

    /// Один сейв в выбранном формате.
    public static func single(_ save: Save, format: Single,
                              region: String? = nil) -> [UInt8] {
        let name = withRegion(save.rawName, region)
        switch format {
        case .mcs: return toMCS(name, save.blocks)
        case .psv: return toPSV(name, save.blocks)
        case .raw: return toRaw(name, save.blocks)
        }
    }

    /// Несколько сейвов в образ карты.
    public static func card(_ saves: [Save], format: Card,
                            region: String? = nil) throws -> CardBuilder.Result {
        let entries = region == nil ? saves : saves.map {
            Save(rawName: withRegion($0.rawName, region), blocks: $0.blocks,
                 slot: $0.slot, state: $0.state, origin: $0.origin)
        }
        var result = try CardBuilder.build(entries)
        switch format {
        case .mcr, .mcd: break
        case .gme: result.image = CardBuilder.asGME(result.image)
        case .vmp: result.image = asVMP(result.image)
        }
        return result
    }

    /// Обёртка PSP с пересчитанной подписью.
    public static func asVMP(_ card: [UInt8]) -> [UInt8] {
        var head = [UInt8](repeating: 0, count: PSX.block / 64)
        head.replaceSubrange(0..<4, with: SonySign.vmp.magic)
        write32(&head, at: 4, 0x80)
        write32(&head, at: 8, UInt32(CardBuilder.cardSize))
        let blob = head + card
        return SonySign.resign(blob) ?? blob
    }
}
