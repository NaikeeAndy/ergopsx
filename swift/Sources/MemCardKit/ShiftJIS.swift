import Foundation

public enum ShiftJIS {
    /// Заголовок сейва: Shift-JIS, полноширинный, до первого нуля.
    ///
    /// Полуширинные формы приводим к обычным через NFKC - иначе подпись
    /// Castlevania читается как `ＡＬＵＣＡＲＤ`, а не `ALUCARD`.
    public static func decode(_ raw: ArraySlice<UInt8>) -> String {
        let cut = Array(raw.prefix { $0 != 0 })
        guard !cut.isEmpty else { return "" }
        let text = String(data: Data(cut), encoding: .shiftJIS)
            ?? String(decoding: cut, as: UTF8.self)
        return text.precomposedStringWithCompatibilityMapping
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
