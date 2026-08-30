import Foundation

/// Разбор двадцатибайтового имени сейва.
///
/// Штатный вид - регион (BA/BE/BI), серийник диска, идентификатор:
/// `BASLUS-00067DRAX02`. Но встречаются и самодельные имена не по схеме
/// (`GT_COMPRESS01`) - их резать на части нельзя.
public struct SaveName: Sendable {
    public let region: Region?
    /// Серийник в том виде, в каком он лежит в базе названий: через дефис.
    public let serial: String
    public let identifier: String
    /// Имя целиком, как записано в сейве.
    public let text: String

    public init(_ raw: [UInt8]) {
        let cut = raw.prefix { $0 != 0 }
        let name = String(decoding: cut, as: UTF8.self)
            .trimmingCharacters(in: .whitespaces)
        text = name

        guard SaveName.isSonyName(name) else {
            region = nil
            serial = ""
            identifier = name
            return
        }
        let chars = Array(name)
        region = Region(rawValue: String(chars[0..<2]))
        // Серийник в базе всегда через дефис, даже когда в имени стоит 'P'.
        serial = String(chars[2..<6]) + "-" + String(chars[7..<12])
        identifier = String(chars[12...])
    }

    /// `B[AEI]` + четыре буквы + `-` или `P` + пять цифр.
    ///
    /// `P` вместо дефиса ставят игры с поддержкой PocketStation: `SLUSP00892`
    /// это `SLUS-00892`, Final Fantasy VIII. По этому же байту MemcardRex
    /// отличает приложения PocketStation от обычных сейвов.
    static func isSonyName(_ name: String) -> Bool {
        let c = Array(name)
        guard c.count >= 12 else { return false }
        guard c[0] == "B", c[1] == "A" || c[1] == "E" || c[1] == "I" else { return false }
        guard c[2...5].allSatisfy({ $0.isUppercase && $0.isLetter }) else { return false }
        guard c[6] == "-" || c[6] == "P" else { return false }
        return c[7...11].allSatisfy(\.isNumber)
    }

    /// Серийник вида `SLUSP00892` к виду `SLUS-00892`.
    ///
    /// Без этого 51 сейв пяти игр висел без названия: такой серийник не
    /// находится ни в базе названий, ни в шаблонах.
    public static func normalize(_ serial: String) -> String {
        let c = Array(serial)
        guard c.count == 10, c[4] == "P",
              c[0...3].allSatisfy({ $0.isUppercase && $0.isLetter }),
              c[5...9].allSatisfy(\.isNumber) else { return serial }
        return String(c[0...3]) + "-" + String(c[5...9])
    }
}
