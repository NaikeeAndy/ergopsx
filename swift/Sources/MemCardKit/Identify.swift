import Foundation

/// Что мы знаем о сейве, не заглядывая в данные конкретной игры.
public struct SaveInfo: Sendable, Codable {
    public var serial: String
    public var region: String
    public var identifier: String
    public var blocks: Int
    public var title: String
    public var internalName: String
    public var slot: Int?
    public var state: String?
}

public enum Identify {
    /// Подпись игры: Shift-JIS с `0x04` до начала палитры иконки.
    /// Это 92 байта, а не 64: у Crash Bash и CTR подпись ровно
    /// на пределе, и обрезание отъедало у них хвост.
    static let signatureEnd = 0x60

    /// Сколько кадров у иконки: младшая цифра байта 0x02 (0x11..0x13).
    public static func iconFrames(_ block: ArraySlice<UInt8>) -> Int {
        guard block.count > 2 else { return 1 }
        let count = Int(block[block.startIndex + 2] & 0x0F)
        return (1...3).contains(count) ? count : 1
    }

    /// С какого байта блока начинаются данные игры.
    ///
    /// Заголовок 0x80, дальше кадры иконки по 0x80. Число кадров - свойство
    /// сейва, а не игры: у Castlevania в коллекции есть и однокадровые,
    /// и трёхкадровые.
    public static func dataOffset(_ block: ArraySlice<UInt8>) -> Int {
        0x80 + 0x80 * iconFrames(block)
    }

    /// Поправка к смещениям чужих шаблонов: они писались по сейвам
    /// с однокадровой иконкой, где данные идут с 0x100.
    public static func templateBase(_ block: ArraySlice<UInt8>) -> Int {
        dataOffset(block) - 0x100
    }

    public static func describe(_ save: Save, titles: Titles) -> SaveInfo {
        let name = SaveName(save.rawName)
        let serial = name.serial.isEmpty ? "" : SaveName.normalize(name.serial)
        let body = save.blocks.first ?? []
        return SaveInfo(
            serial: serial.isEmpty ? "?" : serial,
            region: name.region?.label ?? "?",
            identifier: name.identifier,
            blocks: save.blocks.count,
            title: serial.isEmpty ? "" : (titles[serial] ?? ""),
            internalName: body.isEmpty ? "" : ShiftJIS.decode(body[4..<min(signatureEnd, body.count)]),
            slot: save.slot,
            state: save.state?.label)
    }

    /// Сейвы из любого файла: PSV, MCS, блок без заголовка или образ карты.
    ///
    /// `fallbackName` нужен сырому блоку: заголовка у него нет, и единственный
    /// носитель имени - имя файла.
    public static func saves(in blob: [UInt8], fallbackName: String = "") -> [Save]? {
        if let one = readPSV(blob) { return [one] }
        if let one = readMCS(blob) { return [one] }
        if let one = readRaw(blob, name: fallbackName) { return [one] }
        if let card = CardImage(blob) { return card.saves() }
        return nil
    }

    /// Блок без заголовка: начинается прямо с магии `SC`.
    static func readRaw(_ blob: [UInt8], name: String) -> Save? {
        guard blob.count >= PSX.block,
              blob[0] == 0x53 || blob[0] == 0x73, blob[1] == 0x43 else { return nil }
        var raw = Array(embeddedName(in: name).utf8.prefix(20))
        raw.append(contentsOf: [UInt8](repeating: 0, count: 20 - raw.count))
        return Save(rawName: raw, blocks: split(blob), origin: L.t("block without a header"))
    }

    /// Штатное имя сейва, найденное где угодно внутри имени файла:
    /// `gran-turismo.26537-BASCUS-94194GT.srm`.
    static func embeddedName(in stem: String) -> String {
        let chars = Array(stem)
        for start in chars.indices where chars.count - start >= 12 {
            let window = String(chars[start...])
            if SaveName.isSonyName(window) {
                let tail = window.prefix(20).prefix {
                    $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" || $0 == "."
                }
                return String(tail)
            }
        }
        return String(stem.prefix(20))
    }

    /// PS3 `.psv`: магия `\0VSP`, размер по 0x40, смещение данных по 0x44,
    /// имя по 0x64 - брать надо оттуда, а не из имени файла.
    static func readPSV(_ blob: [UInt8]) -> Save? {
        guard blob.count > 0x84,
              blob[0] == 0x00, blob[1] == 0x56, blob[2] == 0x53, blob[3] == 0x50,
              blob[0x3C] == 1 else { return nil }
        let size = Int(read32(blob[...], at: 0x40))
        let offset = Int(read32(blob[...], at: 0x44))
        guard offset < blob.count else { return nil }
        let end = size > 0 ? min(blob.count, offset + size) : blob.count
        return Save(rawName: Array(blob[0x64..<0x78]),
                    blocks: split(Array(blob[offset..<end])), origin: "PSV")
    }

    /// `.mcs`: каталожный фрейм и следом блоки сейва.
    ///
    /// Длину берём из поля во фрейме, а не из длины файла: встречаются файлы
    /// с хвостом мусора после сейва, и по длине файла они не делятся на блоки.
    static func readMCS(_ blob: [UInt8]) -> Save? {
        guard blob.count > PSX.frame, blob[0] == 0x51 else { return nil }
        let declared = Int(read32(blob[...], at: 4))
        let size = declared > 0 ? declared : blob.count - PSX.frame
        let end = min(blob.count, PSX.frame + size)
        return Save(rawName: Array(blob[10..<30]),
                    blocks: split(Array(blob[PSX.frame..<end])), origin: "MCS")
    }

    /// Полезные данные в блоки по 8192, добивая нулями.
    static func split(_ payload: [UInt8]) -> [[UInt8]] {
        let count = max(1, (payload.count + PSX.block - 1) / PSX.block)
        var padded = payload
        padded.append(contentsOf: [UInt8](repeating: 0, count: count * PSX.block - payload.count))
        return (0..<count).map { Array(padded[($0 * PSX.block)..<(($0 + 1) * PSX.block)]) }
    }
}
