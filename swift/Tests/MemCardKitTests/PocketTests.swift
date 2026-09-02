import XCTest
@testable import MemCardKit

/// PocketStation и Chocobo World.
///
/// Разбор записи Боко сверяется с `tools/psxpocket.py` на всей коллекции
/// через `psxverify`; здесь - то, что коллекцией не проверяется: правка
/// записи и перезапечатывание сейва FF8.
final class PocketTests: XCTestCase {

    /// Метка привязки читается и пишется симметрично. Это те четыре байта,
    /// по которым игра отличает своего Боко от чужого; ошибка здесь даёт
    /// «wrong world» и выглядит как проблема железа.
    func testLinkRoundTrip() {
        var record = [UInt8](repeating: 0, count: Boko.recordSize)
        record[0] = 0x01
        for value: UInt32 in [0, 1, 0x42960F20, 0xFFFFFFFF] {
            let written = Boko.withLink(record, value)
            XCTAssertEqual(Boko.link(in: written), value)
            // Меняются ровно четыре байта и ничего больше.
            for index in 0 ..< Boko.recordSize
            where !(Boko.linkAt ..< Boko.linkAt + 4).contains(index) {
                XCTAssertEqual(written[index], record[index],
                               "изменился байт \(index)")
            }
        }
    }

    /// Бит 0 включает Chocobo World, бит 1 отправляет Боко в отлучку.
    /// Без первого игра считает мини-игру не активированной и связку
    /// игнорирует, сколько ни ставь второй.
    func testFlags() {
        let blank = [UInt8](repeating: 0, count: Boko.recordSize)
        XCTAssertEqual(Boko.withFlags(blank, enabled: true)[0], 0x01)
        XCTAssertEqual(Boko.withFlags(blank, away: true)[0], 0x02)
        XCTAssertEqual(Boko.withFlags(blank, enabled: true, away: true)[0], 0x03)
        let both = Boko.withFlags(blank, enabled: true, away: true)
        XCTAssertEqual(Boko.withFlags(both, away: false)[0], 0x01)
        XCTAssertEqual(Boko.withFlags(blank, walking: true)[0x2F], 1)
    }

    /// BCD: 42 лежит в байте как `0x42`. Не заметить это легко, и тогда
    /// выходит мусор, похожий на правду.
    func testBCD() {
        XCTAssertEqual(Boko.bcd(0x42), 42)
        XCTAssertEqual(Boko.bcd(0x99), 99)
        XCTAssertEqual(Boko.bcd(0x09), 9)
        XCTAssertTrue(Boko.isBCD(0x99))
        XCTAssertFalse(Boko.isBCD(0xAB))
    }

    /// `CRD0` - тоже приложение. MemcardRex его исключает намеренно, но
    /// отвечает этим на другой вопрос: как запись выглядит в браузере PS2.
    /// С `CRD0` идут семь настоящих приложений коллекции.
    func testCRD0IsAnApplication() {
        var name = [UInt8](repeating: 0x41, count: 20)
        name[6] = 0x50                                   // 'P'
        var block = [UInt8](repeating: 0, count: PSX.block)
        for (magic, isApp, onPS2) in [("MCX0", true, true), ("MCX1", true, true),
                                      ("CRD0", true, false), ("SAVE", false, false)] {
            block.replaceSubrange(0x52 ..< 0x56, with: Array(magic.utf8))
            XCTAssertEqual(Boko.isApplication(name: name, block: block), isApp,
                           "магия \(magic)")
            XCTAssertEqual(Boko.showsOnPS2(block: block), onPS2, "магия \(magic)")
        }
    }

    /// Без `P` на седьмой позиции имени это обычный сейв, сколько бы
    /// правдоподобной магии ни лежало в блоке.
    func testApplicationNeedsThePInTheName() {
        var block = [UInt8](repeating: 0, count: PSX.block)
        block.replaceSubrange(0x52 ..< 0x56, with: Array("MCX0".utf8))
        let name = [UInt8](repeating: 0x41, count: 20)
        XCTAssertFalse(Boko.isApplication(name: name, block: block))
    }
}
