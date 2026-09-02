import Foundation

/// Состояние Chocobo World - мини-игры Final Fantasy VIII, живущей на
/// PocketStation.
///
/// Одна и та же 64-байтовая запись лежит в двух местах:
///   * в сейве Chocobo World на стороне PocketStation - в двух банках,
///     свежий выбирается по счётчику сохранений;
///   * внутри сейва FF8 - блок `CHOCOBO` по смещению 5344 блока данных.
/// Раскладка полей одинаковая, поэтому обе читаются одним разбором.
///
/// Источники: `ChocoEdit/SAV/Choco.cs` (сторона PocketStation) и
/// `hyne/src/SaveData.h` (сторона FF8). Перенос с `tools/psxpocket.py`,
/// сверяется с ним на всей коллекции.
public struct Boko: Sendable, Equatable {
    public enum Source: Sendable, Equatable {
        /// Блок `CHOCOBO` внутри сейва Final Fantasy VIII.
        case ff8
        /// Сейв Chocobo World на стороне PocketStation.
        case pocketStation(liveBanks: Int)
    }

    public var flags: UInt8
    public var level: Int
    public var hp: Int
    public var hpMax: Int
    public var weapon: Int
    public var rank: Int
    public var move: Int
    public var saveCount: UInt32
    public var id: Int
    public var items: [Int]
    /// Привязка к конкретному сейву FF8: `FF8ID` у ChocoEdit,
    /// `associatedSaveID` у hyne. Игра сверяет это число с обеих сторон,
    /// и при несовпадении объявляет мир чужим.
    public var ff8ID: UInt32
    public var summon: Int
    public var homeWalking: UInt8
    public var source: Source

    /// Уровень призыва Боко в самой игре.
    public static let summonNames = ["none", "ChocoFire", "ChocoFlare",
                                     "ChocoMeteor", "ChocoBocle"]

    public var summonName: String {
        summon < Boko.summonNames.count ? Boko.summonNames[summon] : "?"
    }

    /// Имена битов по ChocoEdit, кроме нулевого: у него тот зовётся
    /// `Eventflag0` с пометкой «назначение неясно», а у hyne это `Enabled` -
    /// главный выключатель Chocobo World, и пишет его hyne именно так
    /// (`CWEditor.cpp:204`).
    public static let flagBits: [(UInt8, String)] = [
        (0x01, "Chocobo World on"),
        (0x02, "Boko is away"),
        (0x04, "MiniMog found"),
        (0x08, "MiniMog obtained"),
        (0x10, "MiniMog on standby"),
        (0x20, "Demon King defeated"),
        (0x40, "current event seen"),
        (0x80, "event wait off"),
    ]

    public var flagNames: [String] {
        Boko.flagBits.filter { flags & $0.0 != 0 }.map { L.t($0.1) }
    }

    public var enabled: Bool { flags & 0x01 != 0 }
    public var away: Bool { flags & 0x02 != 0 }
}

extension Boko {
    public static let recordSize = 64

    // --- Сторона FF8, по hyne ---
    static let ff8MagicAt = 386
    static let ff8Magics: Set<UInt16> = [0x08FF, 0x0FF8]
    static let ff8ChocoboAt = 5344

    // --- Сторона PocketStation, по ChocoEdit ---
    // У ChocoEdit смещения от начала `.mcs` (0x280/0x380), здесь - от
    // начала блока данных.
    static let bankOffsets = [0x200, 0x300]

    // --- Признаки приложения PocketStation, по MemcardRex ---
    static let appNameIndex = 6
    static let appMagicAt = 0x52
    /// **`CRD0` - тоже приложение.** MemcardRex его исключает намеренно:
    /// в комментарии там сказано, что `CRD0` не заставляет браузер PS2
    /// показывать запись как «software». Но это ответ на другой вопрос -
    /// как запись выглядит на PS2, - а нам надо знать, приложение это или
    /// сейв. С `CRD0` идут семь настоящих приложений коллекции: Brightis,
    /// PokeHito, R4, Rockman 3, Doraemon 3, Chivas и Parumui.
    static let appMagics: Set<[UInt8]> = [Array("MCX0".utf8), Array("MCX1".utf8),
                                          Array("CRD0".utf8)]
    /// Показывается ли запись приложением в браузере PS2 - отдельный вопрос.
    static let ps2BrowserMagics: Set<[UInt8]> = [Array("MCX0".utf8),
                                                 Array("MCX1".utf8)]

    /// Смещение поля привязки внутри записи.
    public static let linkAt = 0x28

    /// Числовые поля записи хранятся в BCD: 42 лежит в байте как `0x42`.
    /// Не заметить это легко, и тогда выходит мусор, похожий на правду.
    static func bcd(_ value: UInt8) -> Int {
        Int(value >> 4) * 10 + Int(value & 0xF)
    }

    static func isBCD(_ value: UInt8) -> Bool {
        (value >> 4) <= 9 && (value & 0xF) <= 9
    }

    /// Разбирает 64-байтовую запись, не проверяя правдоподобие.
    static func record(_ buf: [UInt8], at base: Int, source: Source) -> Boko? {
        guard buf.count >= base + recordSize else { return nil }
        let r = Array(buf[base ..< base + recordSize])

        func u32(_ at: Int) -> UInt32 {
            UInt32(r[at]) | UInt32(r[at + 1]) << 8
                | UInt32(r[at + 2]) << 16 | UInt32(r[at + 3]) << 24
        }

        return Boko(
            flags: r[0],
            // Ноль в поле уровня означает сотню.
            level: bcd(r[1]) == 0 ? 100 : bcd(r[1]),
            hp: bcd(r[2]),
            hpMax: bcd(r[3]),
            // Четыре десятичные цифры в двух байтах, младшая пара - первая.
            weapon: bcd(r[5]) * 100 + bcd(r[4]),
            rank: bcd(r[6]),
            move: Int(r[7]),
            saveCount: u32(8),
            id: Int(r[13] & 0xF) * 100 + bcd(r[12]),
            items: (0 ..< 4).map { bcd(r[0x14 + $0]) },
            ff8ID: u32(linkAt),
            summon: Int(r[0x2D]),
            homeWalking: r[0x2F],
            source: source)
    }

    /// Отсеивает мусор. Записи ищутся в блоках любых игр, поэтому
    /// критерии жёсткие: всё поле - валидный BCD и в игровых пределах,
    /// HP не больше максимума, счётчик сохранений ненулевой.
    static func plausible(_ boko: Boko?, raw: [UInt8], at base: Int) -> Bool {
        guard let boko else { return false }
        for index in [1, 2, 3, 6, 0x14, 0x15, 0x16, 0x17]
        where !isBCD(raw[base + index]) { return false }
        guard 1 ... 100 ~= boko.level,
              1 ... 99 ~= boko.hp,
              6 ... 99 ~= boko.hpMax,
              boko.hp <= boko.hpMax,
              boko.rank <= 6, boko.move <= 5, boko.summon <= 4,
              !boko.items.contains(where: { $0 > 99 }),
              0 < boko.saveCount, boko.saveCount < 1_000_000
        else { return false }
        return true
    }

    /// Блок `CHOCOBO` внутри сейва Final Fantasy VIII.
    public static func fromFF8(_ block: [UInt8]) -> Boko? {
        guard block.count >= ff8MagicAt + 2 else { return nil }
        let magic = UInt16(block[ff8MagicAt]) | UInt16(block[ff8MagicAt + 1]) << 8
        guard ff8Magics.contains(magic) else { return nil }
        let got = record(block, at: ff8ChocoboAt, source: .ff8)
        return plausible(got, raw: block, at: ff8ChocoboAt) ? got : nil
    }

    /// Сейв Chocobo World: два банка, свежий определяется счётчиком.
    ///
    /// Ищется только в приложениях PocketStation - иначе два произвольных
    /// смещения в чужом блоке слишком легко дают правдоподобный мусор.
    public static func fromPocketStation(_ block: [UInt8],
                                         name: [UInt8]?) -> Boko? {
        guard let name, isApplication(name: name, block: block) else {
            return nil
        }
        var banks: [Boko] = []
        for base in bankOffsets {
            let got = record(block, at: base, source: .ff8)
            if plausible(got, raw: block, at: base), let got { banks.append(got) }
        }
        guard var best = banks.max(by: { $0.saveCount < $1.saveCount }) else {
            return nil
        }
        best.source = .pocketStation(liveBanks: banks.count)
        return best
    }

    public static func find(block: [UInt8], name: [UInt8]? = nil) -> Boko? {
        fromFF8(block) ?? fromPocketStation(block, name: name)
    }

    /// Приложение PocketStation, а не обычный сейв: `P` на седьмой позиции
    /// имени плюс магия `MCX0`/`MCX1` в блоке.
    ///
    /// Имя - те же двадцать байт, что лежат в каталожном фрейме по `+10`
    /// и хранятся в `Save.rawName`.
    public static func isApplication(name: [UInt8], block: [UInt8]) -> Bool {
        guard block.count >= appMagicAt + 4 else { return false }
        guard name.count > appNameIndex, name[appNameIndex] == 0x50 else {
            return false
        }
        return appMagics.contains(Array(block[appMagicAt ..< appMagicAt + 4]))
    }

    /// Показывает ли браузер PS2 эту запись приложением, а не сейвом.
    public static func showsOnPS2(block: [UInt8]) -> Bool {
        guard block.count >= appMagicAt + 4 else { return false }
        return ps2BrowserMagics.contains(Array(block[appMagicAt ..< appMagicAt + 4]))
    }

    // MARK: - правка

    /// Метка привязки внутри произвольной 64-байтовой записи.
    public static func link(in record: [UInt8]) -> UInt32 {
        guard record.count >= linkAt + 4 else { return 0 }
        return UInt32(record[linkAt]) | UInt32(record[linkAt + 1]) << 8
            | UInt32(record[linkAt + 2]) << 16 | UInt32(record[linkAt + 3]) << 24
    }

    public static func withLink(_ record: [UInt8], _ value: UInt32) -> [UInt8] {
        var out = record
        guard out.count >= linkAt + 4 else { return out }
        for shift in 0 ..< 4 {
            out[linkAt + shift] = UInt8((value >> (8 * shift)) & 0xFF)
        }
        return out
    }

    /// Переписывает метку привязки во всех живых банках сейва Chocobo
    /// World и заодно правит флаги. Возвращает `nil`, если записи там нет.
    ///
    /// Банков два, и трогать надо оба: игра берёт свежий по счётчику
    /// сохранений, а какой окажется свежим после следующего запуска -
    /// заранее не известно.
    public static func relinked(_ block: [UInt8], tag: UInt32,
                                enabled: Bool? = true, away: Bool? = true,
                                walking: Bool? = false) -> [UInt8]? {
        var out = block
        var touched = false
        for base in bankOffsets where base + recordSize <= block.count {
            let raw = Array(block[base ..< base + recordSize])
            guard plausible(record(raw, at: 0, source: .ff8), raw: raw, at: 0)
            else { continue }
            let fixed = withFlags(withLink(raw, tag), enabled: enabled,
                                  away: away, walking: walking)
            out.replaceSubrange(base ..< base + recordSize, with: fixed)
            touched = true
        }
        return touched ? out : nil
    }

    /// Правит флаги записи. Бит 0 включает Chocobo World, бит 1 отправляет
    /// Боко в отлучку. Без первого игра считает мини-игру не активированной
    /// и связку игнорирует, сколько ни ставь второй.
    public static func withFlags(_ record: [UInt8], enabled: Bool? = nil,
                                 away: Bool? = nil,
                                 walking: Bool? = nil) -> [UInt8] {
        var out = record
        guard !out.isEmpty else { return out }
        for (bit, value) in [(UInt8(0x01), enabled), (UInt8(0x02), away)] {
            guard let value else { continue }
            out[0] = value ? (out[0] | bit) : (out[0] & ~bit)
        }
        if let walking, out.count > 0x2F { out[0x2F] = walking ? 1 : 0 }
        return out
    }
}
