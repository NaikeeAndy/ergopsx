import SwiftUI
import AppKit
import CryptoKit
import ImageIO
import UniformTypeIdentifiers
import MemCardKit

@main
struct MemCardSaverApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var state = AppState()
    @Environment(\.openWindow) private var openWindow

    init() {
        // Самопроверка: прогоняет разбор по всей коллекции и выходит.
        // Ловит выходы за границу массива, до которых руками пришлось бы
        // доклацываться.
        if CommandLine.arguments.contains("--check-all") {
            MemCardSaverApp.checkAll()
            exit(0)
        }
        // Снимок вида в файл, без окна на экране.
        //     MemCardSaver --render корзина.png
        // Окна приложения, запущенного не с рабочего стола, `screencapture`
        // не видит, и вид приходилось проверять на глаз. `ImageRenderer`
        // рисует тот же самый вид мимо экрана.
        let args = CommandLine.arguments
        if let mark = args.firstIndex(of: "--render"), mark + 1 < args.count {
            MemCardSaverApp.render(to: URL(fileURLWithPath: args[mark + 1]))
            exit(0)
        }
        // Наигранное время, как его считает слой приложения.
        //     MemCardSaver --playtimes время.json
        // В `memcard dump` его нет: время собирает не движок, а `Digest` -
        // сперва разборщик игры, потом таблица автопоиска. У версии на Qt
        // свой такой же слой, и сличить их больше нечем.
        if let mark = args.firstIndex(of: "--playtimes"), mark + 1 < args.count {
            MemCardSaverApp.playtimes(to: URL(fileURLWithPath: args[mark + 1]))
            exit(0)
        }
        // Разбор игр в том виде, в каком его показывает панель справа.
        //     MemCardSaver --digests разбор.json
        // Движки сверены между собой, а слой отображения - нет: панель
        // строит его сама, и у двух приложений он может разойтись.
        if let mark = args.firstIndex(of: "--digests"), mark + 1 < args.count {
            MemCardSaverApp.digests(to: URL(fileURLWithPath: args[mark + 1]))
            exit(0)
        }
    }

    var body: some Scene {
        WindowGroup(id: "main") {
            RootView()
                .environment(state)
                .task { await state.start() }
        }
        .defaultSize(width: 1280, height: 820)
        .commands { Menus(state: state, openWindow: { openWindow(id: $0) }) }

        Window(L.t("Console"), id: "console") {
            ConsoleWindow().environment(state)
        }
        .defaultSize(width: 860, height: 700)

        // Настройки - обычное окно, а не системная панель: в нём есть
        // разделы, и его хочется двигать и оставлять открытым.
        Window(L.t("Save copies"), id: "copies") {
            CopiesWindow().environment(state)
        }
        .defaultSize(width: 560, height: 300)

        Window(L.t("Game images"), id: "games") {
            GamesWindow().environment(state)
        }
        .defaultSize(width: 900, height: 640)

        Window(L.t("Settings"), id: "settings") {
            SettingsView().environment(state)
        }
        .defaultSize(width: 760, height: 540)
    }

    static func footprint() -> Int {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size
                                           / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return -1 }
        return Int(info.phys_footprint) / 1024 / 1024
    }

    static func checkAll() {
        var folders = Folders.stored()
        if folders.isEmpty, let nearby = Folders.nearby() { folders = [nearby] }
        guard !folders.isEmpty else { print("папок с сейвами нет"); return }

        let engine = Engine()
        var items: [LibraryItem] = []
        for folder in folders { items += Library.scan(folder, engine: engine).items }
        print("папок: \(folders.count), сейвов: \(items.count)")

        var parsed = 0, blank = 0
        for item in items {
            if Digest.of(item, engine: engine) != nil { parsed += 1 } else { blank += 1 }
        }
        print("разобрано: \(parsed), без разбора: \(blank)")

        var pairs = 0
        for index in stride(from: 0, to: items.count - 1, by: 1) {
            pairs += Diff.between(items[index], items[index + 1],
                                  engine: engine).groups.count
        }
        print("сравнений: \(max(0, items.count - 1)), групп различий: \(pairs)")

        var chosen: [Save] = []
        var blocks = 0
        for item in items where blocks + item.blocks <= PSX.slots {
            if chosen.contains(where: { $0.name == item.save.name }) { continue }
            chosen.append(item.save)
            blocks += item.blocks
        }
        if let built = try? CardBuilder.build(chosen) {
            print("сборка карты: \(built.layout.count) сейвов, \(built.image.count) байт")
        }
        print("память: \(footprint()) МБ")
        print("выходов за границу не случилось")
    }

    /// Наигранное время по всей коллекции: хеш тела сейва -> секунды.
    ///
    /// Ключ - только тело: время зависит от него одного, и один и тот же
    /// сейв из разных контейнеров даёт одно значение.
    static func playtimes(to target: URL) {
        var folders = Folders.stored()
        if folders.isEmpty, let nearby = Folders.nearby() { folders = [nearby] }
        guard !folders.isEmpty else { print("папок с сейвами нет"); return }

        let engine = Engine()
        var rows: [String: Int] = [:]
        for folder in folders {
            for item in Library.scan(folder, engine: engine).items {
                let body = Data(item.save.blocks.flatMap { $0 })
                let key = SHA256.hash(data: body)
                    .map { String(format: "%02x", $0) }.joined()
                rows[key] = item.playtime ?? -1
            }
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        guard let blob = try? encoder.encode(rows),
              (try? blob.write(to: target)) != nil else {
            print("выгрузить не вышло"); return
        }
        let known = rows.values.filter { $0 >= 0 }.count
        print("сейвов: \(rows.count), со временем: \(known)")
        print("снято: \(target.path)")
    }

    /// Разбор игр по всей коллекции: хеш тела сейва -> то, что видно.
    static func digests(to target: URL) {
        L.current = .en
        var folders = Folders.stored()
        if folders.isEmpty, let nearby = Folders.nearby() { folders = [nearby] }
        guard !folders.isEmpty else { print("папок с сейвами нет"); return }

        struct Shown: Encodable {
            var game: String
            var fields: [[String]]
            var membersTitle: String
            var members: [[String]]
            var sections: [[String]]
        }

        let engine = Engine()
        var rows: [String: Shown] = [:]
        for folder in folders {
            for item in Library.scan(folder, engine: engine).items {
                guard let made = Digest.of(item, engine: engine) else { continue }
                // Ключ - имя и тело: у одного и того же тела бывает
                // два имени, и по одному телу записи склеиваются.
                var payload = Data(item.save.rawName)
                payload.append(contentsOf: item.save.blocks.flatMap { $0 })
                let key = SHA256.hash(data: payload)
                    .map { String(format: "%02x", $0) }.joined()
                rows[key] = Shown(
                    game: made.game,
                    fields: made.fields.map { [$0.label, $0.value] },
                    membersTitle: made.membersTitle,
                    members: made.members.map { member in
                        [member.name, member.role, member.level,
                         member.stats.map { "\($0.label)=\($0.value)" }
                             .joined(separator: ","),
                         member.gear.joined(separator: ","),
                         member.extra]
                    },
                    sections: made.sections.map { part in
                        [part.title, String(part.items.count), part.note]
                    })
            }
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        guard let blob = try? encoder.encode(rows),
              (try? blob.write(to: target)) != nil else {
            print("выгрузить не вышло"); return
        }
        print("сейвов с разбором: \(rows.count)")
        print("снято: \(target.path)")
    }

    /// Рисует корзину с несколькими сейвами и кладёт в PNG.
    @MainActor
    static func render(to target: URL) {
        var folders = Folders.stored()
        if folders.isEmpty, let nearby = Folders.nearby() { folders = [nearby] }
        guard !folders.isEmpty else { print("папок с сейвами нет"); return }

        let engine = Engine()
        var items: [LibraryItem] = []
        for folder in folders { items += Library.scan(folder, engine: engine).items }
        // Берём многоблочный сейв и пару однoблочных: так видно и цепочку.
        let basket = Basket()
        for item in items.sorted(by: { $0.blocks > $1.blocks })
        where basket.used + item.blocks <= 6 {
            basket.add(item)
        }
        print("в корзине: " + basket.items.map(\.title).joined(separator: ", "))

        let view = BasketBar(basket: basket)
            .environment(\.palette, .dark)
            .frame(width: 1000)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        guard let image = renderer.cgImage,
              let out = CGImageDestinationCreateWithURL(
                  target as CFURL, "public.png" as CFString, 1, nil) else {
            print("нарисовать не вышло"); return
        }
        CGImageDestinationAddImage(out, image, nil)
        CGImageDestinationFinalize(out)
        print("снято: \(target.path)")
    }
}

/// Приложение, собранное пакетом SPM, не всегда выходит вперёд само.
///
/// И отдельно: **не убирать `CommandGroup(replacing: .newItem)`** - без
/// команды «Новое окно» `WindowGroup` при пустом сохранённом состоянии
/// не создаёт ни одного окна, и приложение запускается невидимым.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        AppDelegate.wireClipboard()
        // Чтобы системные пункты меню совпадали с выбранным языком
        // при следующем запуске.
        let want = L.current.rawValue
        let now = (UserDefaults.standard.stringArray(forKey: "AppleLanguages") ?? [])
            .first?.prefix(2)
        if now.map(String.init) != want {
            UserDefaults.standard.set([want], forKey: "AppleLanguages")
        }
        watchMenuBar()

        // Проверка полосы меню без прав Универсального доступа:
        // спрашиваем у самого приложения, а не через System Events.
        if CommandLine.arguments.contains("--dump-menu") {
            // Через очередь, а не блокировкой цикла событий: под
            // блокировкой SwiftUI не успевает достроить меню, и видно
            // не то, что будет у пользователя.
            DispatchQueue.main.asyncAfter(deadline: .now() + 6) {
                for item in NSApp.mainMenu?.items ?? [] {
                    let inside = (item.submenu?.items ?? [])
                        .map { $0.isSeparatorItem ? "—" : $0.title }
                        .joined(separator: " · ")
                    print("[\(item.title)] \(inside)")
                }
                exit(0)
            }
        }

        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        DispatchQueue.main.async {
            guard let window = NSApp.windows.first(where: \.isVisible) else { return }
            window.center()
            window.makeKeyAndOrderFront(nil)
        }
    }

    /// Буфер обмена без меню «Правка».
    ///
    /// На macOS ⌘C и ⌘V обрабатывает **не поле ввода, а полоса меню**:
    /// нажатие сначала обходит пункты меню, и если у пункта такое
    /// сочетание, он посылает своё действие первому отвечающему. Нет
    /// пункта - нет и сочетания, поле получает обычное нажатие клавиши
    /// и ничего с ним не делает. Поэтому вместе с меню отваливается
    /// вставка, хотя само поле её умеет.
    ///
    /// Здесь то же самое делается напрямую: перехватываем нажатие и сами
    /// посылаем действие по цепочке отвечающих.
    static func wireClipboard() {
        let actions: [String: Selector] = [
            "x": #selector(NSText.cut(_:)),
            "c": #selector(NSText.copy(_:)),
            "v": #selector(NSText.paste(_:)),
            "a": #selector(NSText.selectAll(_:)),
            "z": Selector(("undo:")),
        ]
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            let keys = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
            guard keys == .command,
                  let letter = event.charactersIgnoringModifiers?.lowercased(),
                  let action = actions[letter] else { return event }
            // Съедаем нажатие только если его кто-то принял: иначе
            // ⌘A в списке сейвов перестал бы доходить до списка.
            // AppKit зовёт обработчик на главном потоке, но тип замыкания
            // об этом не говорит - подтверждаем явно, иначе Swift 6
            // отказывается собирать.
            // Наружу отдаём только признак: сам NSEvent через границу
            // изоляции не проходит, он не Sendable.
            let accepted = MainActor.assumeIsolated {
                NSApp.sendAction(action, to: nil, from: nil)
            }
            return accepted ? nil : event
        }
    }

    /// «Правку» SwiftUI убирает сам, как только у неё не остаётся своих
    /// пунктов, а «Справка» остаётся висеть пустой. Снимаем только её и
    /// только здесь: полосу меню SwiftUI достраивает **после** запуска,
    /// и правки, сделанные раньше, он затирает. Трогать что-то ещё
    /// нельзя - перестановка меню на старте оставляла «Вид» пустым.
    /// Полосу меню SwiftUI достраивает и пересобирает уже после запуска,
    /// поэтому одного прохода не хватает: «Справка» пустеет позже него.
    /// Слушаем обновление приложения - оно приходит на каждом обороте
    /// цикла событий, а проверка стоит обход шести пунктов.
    func watchMenuBar() {
        NotificationCenter.default.addObserver(
            forName: NSApplication.willUpdateNotification,
            object: nil, queue: .main) { _ in
            MainActor.assumeIsolated { AppDelegate.dropEmptyMenus() }
        }
    }

    @MainActor static func dropEmptyMenus() {
        guard let bar = NSApp.mainMenu else { return }
        for item in bar.items {
            guard let inside = item.submenu else { continue }
            // «Справка» пустой не выглядит: AppKit кладёт туда поле
            // поиска по справке - пункт без заголовка. Отбор по пустоте
            // его не ловит, поэтому смотрим и на то, есть ли внутри
            // хоть один пункт с названием.
            let named = inside.items.contains {
                !$0.isSeparatorItem && !$0.title.isEmpty
            }
            if !named { bar.removeItem(item) }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(
        _ sender: NSApplication) -> Bool { true }
}
