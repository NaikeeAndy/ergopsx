import XCTest
@testable import MemCardKit

/// Проверки того, на чём разбор ломался в жизни, а не того, что и так
/// очевидно. Все они обходятся без чужих сейвов: данные либо собраны
/// здесь же, либо взяты из опубликованных эталонов.
final class MemCardKitTests: XCTestCase {

    /// Шифр AES-128 на эталонном векторе FIPS-197, приложение C.1.
    /// Подпись PSV и VMP держится на нём: ошибись здесь - и консоль
    /// отвергнет любой собранный файл.
    func testAESMatchesFIPS197() {
        let plain: [UInt8] = [0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
                              0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
        let key: [UInt8] = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                            0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F]
        let want: [UInt8] = [0x69, 0xC4, 0xE0, 0xD8, 0x6A, 0x7B, 0x04, 0x30,
                             0xD8, 0xCD, 0xB7, 0x80, 0x70, 0xB4, 0xC5, 0x5A]
        XCTAssertEqual(AES128.encrypt(plain, key: key), want)
    }

    /// У игр с поддержкой PocketStation на седьмом месте серийника стоит
    /// `P` вместо дефиса. Без приведения к общему виду 51 сейв пяти игр
    /// оставался без названия: такой серийник не находится ни в базе
    /// названий, ни в шаблонах.
    func testPocketStationSerialNormalises() {
        XCTAssertEqual(SaveName.normalize("SLUSP00892"), "SLUS-00892")
        XCTAssertEqual(SaveName.normalize("SLUS-00892"), "SLUS-00892")
        XCTAssertEqual(SaveName.normalize("SCPS-45486"), "SCPS-45486")
    }

    /// Пустая карта: размер, магия и целостность каталога. Контрольный
    /// байт фрейма - XOR всех предыдущих 127; на нём ловятся почти все
    /// ошибки сборки.
    func testEmptyCardIsWellFormed() throws {
        let built = try CardBuilder.build([])
        XCTAssertEqual(built.image.count, PSX.block * 16)
        XCTAssertEqual(Array(built.image[0..<2]), Array("MC".utf8))

        for slot in 1...PSX.slots {
            let frame = Array(built.image[(slot * 128)..<((slot + 1) * 128)])
            XCTAssertEqual(frame[0], 0xA0, "слот \(slot) должен быть свободен")
            let xor = frame[0..<127].reduce(UInt8(0)) { $0 ^ $1 }
            XCTAssertEqual(xor, frame[127], "контрольный байт слота \(slot)")
        }
    }

    /// Иконка: число кадров лежит в байте 0x02, данные игры начинаются
    /// сразу за кадрами. Ошибка здесь сдвигает весь разбор игры - у
    /// трёхкадрового сейва на 0x100.
    func testDataStartsAfterIconFrames() {
        var block = [UInt8](repeating: 0, count: PSX.block)
        block[0] = 0x53
        block[1] = 0x43
        block[2] = 0x13                     // три кадра
        XCTAssertEqual(Identify.dataOffset(block[...]), 0x80 + 0x80 * 3)
        block[2] = 0x11                     // один кадр
        XCTAssertEqual(Identify.dataOffset(block[...]), 0x80 + 0x80)
    }
}
