import Foundation

/// Контейнер, в который завёрнут образ карты или одиночный сейв.
public enum Container: String, Sendable {
    case raw = "raw"
    case dexDrive = "DexDrive .gme"
    case dexDriveBroken = "DexDrive .gme (broken header)"
    case vgs = "VGS"
    case vmp = "PSP .vmp"
    case juggler = "Memory Juggler .psx"
    case mcx = "MCX"

    /// Название для показа. У сырого значения роль ключа, поэтому
    /// перевод отдельно.
    public var label: String {
        switch self {
        case .dexDriveBroken:
            L.t("DexDrive .gme (заголовок побит)", "DexDrive .gme (broken header)")
        default: rawValue
        }
    }
}

public enum CardContainer {
    /// Магия в начале файла и смещение, с которого идут данные карты.
    ///
    /// `PSV\0` у Memory Juggler не путать с `\0VSP` у PS3: у первого в
    /// заголовке модель карты (SCPH-1020), данные с 256.
    static let known: [(magic: [UInt8], offset: Int, kind: Container)] = [
        (Array("MC".utf8), 0, .raw),
        (Array("123-456-STD".utf8), 3904, .dexDrive),
        (Array("VgsM".utf8), 64, .vgs),
        ([0x00] + Array("PMV".utf8), 128, .vmp),
        (Array("PSV".utf8) + [0x00], 256, .juggler),
    ]

    static let mcxSize = 0x200A0
    static let dexDriveSize = 134976

    /// Данные карты и опознанный контейнер. `nil`, если это не карта.
    public static func find(_ blob: [UInt8]) -> (data: ArraySlice<UInt8>, kind: Container)? {
        for entry in known where blob.count > entry.offset + 1 {
            guard blob.starts(with: entry.magic) else { continue }
            guard blob[entry.offset] == 0x4D, blob[entry.offset + 1] == 0x43 else { continue }
            return (blob[entry.offset...], entry.kind)
        }
        // DexDrive с побитым заголовком: магии в начале нет, но карта на месте.
        // Тот же обходной путь, что в MemcardRex (ps1card.cs, OpenMemoryCard).
        if blob.count == dexDriveSize, blob.count > 3906,
           blob[3904] == 0x4D, blob[3905] == 0x43 {
            return (blob[3904...], .dexDriveBroken)
        }
        return nil
    }

    /// Отдельно: зашифрованный образ SD2PSX, читать его нечем.
    public static func isMCX(_ blob: [UInt8]) -> Bool { blob.count == mcxSize }
}
