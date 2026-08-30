import Foundation

/// Кодировка текста Vagrant Story. Таблица перенесена машинно из
/// `tools/etc/vsString.py` проекта `ser-pounce/rood-reverse` (CC0):
/// переписывать 256 значений руками значило бы завести ошибку,
/// которую не видно.
///
/// Имена оружия игрок задаёт сам, и в сейве они лежат в этой кодировке.
/// Пиратские издания перекладывали в ту же таблицу свой алфавит - тогда
/// имя читается как набор латиницы с цифрами. Разбирать это обратно мы
/// не беремся: то же самое имя с лицензионного диска придёт по-английски.
enum VagrantText {
    /// Одной строкой через разделитель, а не массивом литералов:
    /// на массиве из 256 элементов проверка типов в Swift не сходится
    /// и сборка падает без внятного сообщения.
    private static let packed = "0\u{1}1\u{1}2\u{1}3\u{1}4\u{1}5\u{1}6\u{1}7\u{1}8\u{1}9\u{1}A\u{1}B\u{1}C\u{1}D\u{1}E\u{1}F\u{1}G\u{1}H\u{1}I\u{1}J\u{1}K\u{1}L\u{1}M\u{1}N\u{1}O\u{1}P\u{1}Q\u{1}R\u{1}S\u{1}T\u{1}U\u{1}V\u{1}W\u{1}X\u{1}Y\u{1}Z\u{1}a\u{1}b\u{1}c\u{1}d\u{1}e\u{1}f\u{1}g\u{1}h\u{1}i\u{1}j\u{1}k\u{1}l\u{1}m\u{1}n\u{1}o\u{1}p\u{1}q\u{1}r\u{1}s\u{1}t\u{1}u\u{1}v\u{1}w\u{1}x\u{1}y\u{1}z\u{1}Œ\u{1}À\u{1}Á\u{1}Â\u{1}Ä\u{1}Ç\u{1}È\u{1}É\u{1}Ê\u{1}Ë\u{1}Ì\u{1}Í\u{1}Î\u{1}Ï\u{1}Ò\u{1}Ó\u{1}Ô\u{1}Ö\u{1}Ù\u{1}Ú\u{1}Û\u{1}Ü\u{1}ß\u{1}œ\u{1}à\u{1}á\u{1}â\u{1}ä\u{1}ç\u{1}è\u{1}é\u{1}ê\u{1}ë\u{1}ì\u{1}í\u{1}î\u{1}ï\u{1}ò\u{1}ó\u{1}ô\u{1}ö\u{1}ù\u{1}ú\u{1}û\u{1}ü\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}„\u{1}‼\u{1}≠\u{1}≦\u{1}≧\u{1}÷\u{1}·\u{1}—\u{1}⋯\u{1} \u{1}!\u{1}\"\u{1}#\u{1}$\u{1}%\u{1}&\u{1}'\u{1}(\u{1})\u{1}=\u{1}@\u{1}[\u{1}]\u{1};\u{1}:\u{1},\u{1}.\u{1}/\u{1}\\\u{1}<\u{1}>\u{1}?\u{1}_\u{1}-\u{1}+\u{1}*\u{1}`\u{1}{\u{1}}\u{1}♪\u{1}△\u{1}□\u{1}○\u{1}×\u{1}←\u{1}→\u{1}↑\u{1}↓\u{1}Lv.\u{1}★\u{1}◼\u{1}~\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{1}\u{c}\u{1}▼\u{1}\0\u{1}\n\u{1}\u{1}\u{1}\u{1}|m\u{1}|a\u{1}|b\u{1}|c\u{1}|d\u{1}|e\u{1}|g\u{1}|h\u{1}|i\u{1}|j\u{1}|k\u{1}|l\u{1}|!\u{1}|♪\u{1}|>\u{1}|f\u{1}\u{1}|x\u{1}|#\u{1}|$"

    static let table: [String] = packed.components(separatedBy: "\u{1}")

    /// Терминатор строки.
    static let terminator: UInt8 = 0xE7
    /// Байты, за которыми идёт аргумент - кернинг, подстановки, смена
    /// таблицы шрифта. Сам аргумент в текст не попадает.
    static let twoByte: Set<UInt8> = [0xEC, 0xF8, 0xF9, 0xFA, 0xFB, 0xFD, 0xFE, 0xFF]
    /// Японские таблицы: в западных изданиях не встречаются, но байты
    /// пропустить надо, иначе разбор поедет.
    static let japanese: ClosedRange<UInt8> = 0xED...0xF7

    static func read(_ bytes: ArraySlice<UInt8>) -> String {
        let letters = table
        guard letters.count == 256 else { return "" }
        var out = ""
        var index = bytes.startIndex
        while index < bytes.endIndex {
            let byte = bytes[index]
            if byte == terminator { break }
            if byte == 0xEB { index += 1; continue }   // выравнивание
            // Кернинг игра ставит между словами вместо пробела.
            if byte == 0xFA {
                out += " "
                index += 2
                continue
            }
            if japanese.contains(byte) || twoByte.contains(byte) {
                index += 2
                continue
            }
            out += letters[Int(byte)]
            index += 1
        }
        return out.trimmingCharacters(in: .whitespaces)
    }
}
