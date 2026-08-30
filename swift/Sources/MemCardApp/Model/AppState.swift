import Foundation
import MemCardKit

/// Общее состояние приложения: одно на все окна.
///
/// Корзина должна быть одна и та же в окне коллекции и в окне консоли -
/// иначе собирать карту из обоих мест не выйдет, а ради этого всё
/// и затевалось.
@MainActor
@Observable
final class AppState {
    let library = Library()
    let basket = Basket()
    let folders = Folders()
    private(set) var consoles: [ConsoleProfile] = []
    /// Какую консоль показывает отдельное окно.
    var openConsole: ConsoleProfile?
    /// Какая консоль показана в окне образов игр.
    var openGames: ConsoleProfile?
    /// С какой папки открыть окно консоли - переход из окна образов.
    var consoleStartPath: String?
    /// Что показывает окошко копий сейва.
    var copiesOf: (title: String, name: String, paths: [URL])?

    // Настройки вида живут здесь, а не во вьюхе: до них дотягивается меню.
    var order: SortOrder = .playtime
    var sidebar = true
    /// Что выделено в главном окне - нужно пунктам меню «Сейв».
    var picked: [LibraryItem.ID] = []
    var comparing = false

    /// Что показывать в настройках: настроенные консоли плюс заготовки
    /// для тех, у которых адреса ещё нет.
    ///
    /// Именно **хранимое** свойство, а не вычисляемое. Вычисляемое читало
    /// файл заново на каждый обход вьюхи и ни на что не подписывало:
    /// после сохранения адреса раздел не перерисовывался, и кнопка
    /// «Сохранить» продолжала висеть, хотя запись уже прошла.
    private(set) var consolesToSetUp: [ConsoleProfile] = []
    /// Почему не сохранилось - молчать об этом нельзя.
    var consoleTrouble: String?

    /// Профили читаются сразу: меню «Окно» строится раньше, чем окно
    /// успевает вызвать start(), и список консолей в нём оставался пустым.
    init() {
        L.current = folders.language
        language = folders.language
        reloadConsoles()
    }

    func start() async {
        if folders.urls.isEmpty, let nearby = Folders.nearby() {
            folders.add(nearby)
        }
        reloadConsoles()
        await rescan()
    }

    /// Язык живёт и в настройках на диске, и в таблице строк.
    func setLanguage(_ lang: Lang) {
        folders.setLanguage(lang)
        L.current = lang
        language = lang
        // Разбор помнит подписи полей - иначе панель справа осталась бы
        // на прежнем языке, пока не перезапустишь.
        Digest.forget()
        // Системные пункты меню («Файл», «Закрыть», «Службы») рисует
        // AppKit по языку приложения, а он выбирается до запуска.
        // Записываем на следующий раз - в этот раз они не изменятся.
        UserDefaults.standard.set([lang.rawValue], forKey: "AppleLanguages")
        Task { await rescan() }
    }

    /// Меняется при переключении языка - вьюхи по нему перерисовываются.
    private(set) var language: Lang = .ru

    func reloadConsoles() {
        let near = folders.urls.first
        consoles = ConsoleStore.load(near: near)
        consolesToSetUp = ConsoleStore.all(near: near)
    }

    /// Правит адрес консоли и пишет его в общий с Python файл профилей.
    func updateConsole(_ profile: ConsoleProfile) {
        consoleTrouble = nil
        var list = ConsoleStore.all(near: folders.urls.first)
        if let index = list.firstIndex(where: { $0.label == profile.label }) {
            list[index] = profile
        } else {
            list.append(profile)
        }
        do {
            try ConsoleStore.save(list, near: folders.urls.first)
        } catch {
            consoleTrouble = L.t("could not save: {0}", error.localizedDescription)
        }
        reloadConsoles()
    }

    func rescan() async {
        await library.load(folders.urls)
    }

    func addFolder(_ url: URL) async {
        folders.add(url)
        reloadConsoles()
        await rescan()
    }

    func removeFolder(_ url: URL) async {
        folders.remove(url)
        await rescan()
    }
}
