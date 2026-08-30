import XCTest
@testable import MemCardKit

/// Языковой слой. Проверяется то, что ломается молча: подстановки,
/// формы числа и то, что таблицы вообще доезжают в собранный пакет.
final class LangTests: XCTestCase {

    override func tearDown() {
        L.current = .en
        super.tearDown()
    }

    /// Таблица лежит ресурсом, и её легко потерять при сборке `.app`.
    /// Тогда язык переключается, а строки остаются английскими - на глаз
    /// это выглядит как «перевода нет», а не как «ресурс не доехал».
    func testEveryLanguageHasATable() {
        for language in Lang.allCases where language != .en {
            L.current = language
            XCTAssertNotEqual(L.t("Playtime"), "Playtime",
                              "таблица \(language.rawValue) не загрузилась")
        }
    }

    func testEnglishIsTheKeyItself() {
        L.current = .en
        XCTAssertEqual(L.t("Playtime"), "Playtime")
        XCTAssertEqual(L.t("Nothing found"), "Nothing found")
    }

    /// Пометка после `@@` разводит одинаковые английские слова с разным
    /// смыслом. Наружу она попасть не должна ни в одном языке.
    func testContextMarkNeverReachesTheScreen() {
        for language in Lang.allCases {
            L.current = language
            for key in ["Save@@verb", "Party@@squad", "Gems@@count",
                        "Folders@@count", "Card images@@count"] {
                XCTAssertFalse(L.t(key).contains("@@"),
                               "\(key) в языке \(language.rawValue)")
            }
        }
        L.current = .en
        XCTAssertEqual(L.t("Save@@verb"), "Save")
        L.current = .ru
        XCTAssertEqual(L.t("Save@@verb"), "Сохранить")
        XCTAssertEqual(L.t("Save"), "Сейв")
    }

    func testArgumentsGoIntoPlaceholders() {
        L.current = .en
        XCTAssertEqual(L.t("{0} of {1}", 3, 16), "3 of 16")
        L.current = .ja
        // В японском порядок обратный - подстановка это и позволяет.
        XCTAssertEqual(L.t("{0} of {1}", 3, 16), "16中3")
    }

    /// У русского и польского три формы, у английского две, у японского
    /// одна. Ошибка здесь тихая: «5 сейва» читается почти правильно.
    func testPluralForms() {
        L.current = .ru
        XCTAssertEqual(L.plural("save", 1), "сейв")
        XCTAssertEqual(L.plural("save", 2), "сейва")
        XCTAssertEqual(L.plural("save", 5), "сейвов")
        XCTAssertEqual(L.plural("save", 11), "сейвов")
        XCTAssertEqual(L.plural("save", 21), "сейв")
        XCTAssertEqual(L.plural("save", 104), "сейва")
        L.current = .pl
        XCTAssertEqual(L.plural("block", 1), "blok")
        XCTAssertEqual(L.plural("block", 3), "bloki")
        XCTAssertEqual(L.plural("block", 12), "bloków")
        L.current = .en
        XCTAssertEqual(L.plural("block", 1), "block")
        XCTAssertEqual(L.plural("block", 2), "blocks")
        L.current = .ja
        XCTAssertEqual(L.plural("block", 1), L.plural("block", 7))
    }

    func testUnknownKeyFallsBackToEnglish() {
        L.current = .ja
        XCTAssertEqual(L.t("no such key in any table"), "no such key in any table")
    }
}
