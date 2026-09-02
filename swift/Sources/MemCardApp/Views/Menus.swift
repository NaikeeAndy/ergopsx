import SwiftUI
import MemCardKit

/// Пункты верхнего меню.
///
/// Системные «Правка» и «Окно» оставлены: первое нужно полю поиска,
/// второе - переключению между окном коллекции и окном консоли.
/// Всё остальное задано здесь.
/// Пункты верхнего меню.
///
/// Меню - для **действий над тем, что открыто**. Настройка папок и
/// консолей живёт в окне настроек и в меню не повторяется: два места
/// для одного и того же расходятся, стоит поправить одно.
///
/// «Правка» убрана целиком: отменять нечего - приложение ничего не
/// перезаписывает, а поиск и правописание ему не нужны. Вместе с ней
/// уходят и горячие клавиши буфера обмена, они держались на её пунктах;
/// в полях ввода остаётся правая кнопка мыши. «Окно» дополнено
/// консолями: они открываются отдельными окнами.
struct Menus: Commands {
    let state: AppState
    let openWindow: (String) -> Void

    var body: some Commands {
        // Справка пустая - убираем.
        CommandGroup(replacing: .help) {}
        // «Правка» целиком: отменять нечего, искать по тексту негде,
        // правописание проверять не в чем.
        CommandGroup(replacing: .undoRedo) {}
        CommandGroup(replacing: .pasteboard) {}
        CommandGroup(replacing: .textEditing) {}

        // «Новое окно» не трогаем: без него WindowGroup при пустом
        // сохранённом состоянии не создаёт ни одного окна, и приложение
        // запускается невидимым. Проверено на себе.
        CommandGroup(replacing: .newItem) {
            Button(L.t("New window")) { openWindow("main") }
                .keyboardShortcut("n")
            Button(L.t("Refresh list")) { Task { await state.rescan() } }
                .keyboardShortcut("r")
                .disabled(state.library.loading)
            Divider()
            Button(L.t("Build card from basket…")) { buildCard() }
                .keyboardShortcut("s", modifiers: [.command, .shift])
                .disabled(state.basket.isEmpty)
        }

        // Своё окно вместо системной панели настроек.
        CommandGroup(replacing: .appSettings) {
            Button(L.t("Settings…")) { openWindow("settings") }
                .keyboardShortcut(",")
        }

        // Всё про выделенный сейв - в своём меню, а не в «Правке»:
        // та про текст в полях ввода.
        CommandMenu(L.t("Save")) {
            Button(L.t("Save as…")) { saveOne() }
                .keyboardShortcut("s")
                .disabled(chosen == nil)
            Button(L.t("Show in Finder")) { reveal() }
                .keyboardShortcut("r", modifiers: [.command, .shift])
                .disabled(chosen?.origin == nil)
            Divider()
            Button(inBasket ? L.t("Remove from basket") : L.t("Add to basket")) {
                toggleBasket()
            }
                .keyboardShortcut("d")
                .disabled(chosen == nil)
            Button(L.t("Clear basket")) { state.basket.clear() }
                .disabled(state.basket.isEmpty)
            Divider()
            Button(L.t("Compare the two selected")) { state.comparing = true }
                .keyboardShortcut("=")
                .disabled(state.picked.count != 2)
        }

        CommandGroup(after: .toolbar) {
            Button(state.sidebar ? L.t("Hide game list")
                                 : L.t("Show game list")) {
                state.sidebar.toggle()
            }
            .keyboardShortcut("\\")

            Picker(L.t("Order"), selection: Binding(
                get: { state.order }, set: { state.order = $0 })) {
                ForEach(SortOrder.allCases) { Text($0.label).tag($0) }
            }
        }

        // PocketStation - своим пунктом, а не внутри «Консолей»:
        // приставочка не консоль, и работа с ней другая - железо через
        // адаптер и перенос Боко между сейвом FF8 и устройством.
        CommandGroup(after: .toolbar) {
            Divider()
            Button(L.t("PocketStation…")) { openWindow("pocket") }
        }

        // Своё меню: консолей две, и у каждой два окна - сохранения
        // и образы игр. В «Окне» это тонуло среди системных пунктов.
        CommandMenu(L.t("Consoles")) {
            if state.consoles.isEmpty {
                Text(L.t("Not configured"))
            } else {
                ForEach(state.consoles) { profile in
                    Button(profile.label) {
                        state.openConsole = profile
                        openWindow("console")
                    }
                }
                Divider()
                ForEach(state.consoles) { profile in
                    Button(L.t("Game images: {0}", profile.label)) {
                        state.openGames = profile
                        openWindow("games")
                    }
                }
            }
        }
    }

    // MARK: - действия

    private var chosen: LibraryItem? {
        guard let last = state.picked.last else { return nil }
        return state.library.unique.first { $0.id == last }
    }

    private var inBasket: Bool {
        guard let item = chosen else { return false }
        return state.basket.contains(item)
    }

    private func toggleBasket() {
        guard let item = chosen else { return }
        state.basket.toggle(item)
    }

    private func reveal() {
        guard let url = chosen?.origin else { return }
        NSWorkspace.shared.activateFileViewerSelecting([url])
    }

    private func addFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = true
        panel.prompt = L.t("Add")
        panel.message = L.t("Save folders")
        guard panel.runModal() == .OK else { return }
        let picked = panel.urls
        Task { for url in picked { await state.addFolder(url) } }
    }

    private func saveOne() {
        guard let item = chosen else { return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = item.save.name + ".mcs"
        panel.message = L.t("A single save — the original file is not changed")
        guard panel.runModal() == .OK, let target = panel.url else { return }
        let format: Convert.Single =
            target.pathExtension.lowercased() == "psv" ? .psv
            : target.pathExtension.lowercased() == "raw" ? .raw : .mcs
        try? Data(Convert.single(item.save, format: format)).write(to: target)
    }

    private func buildCard() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "card.mcr"
        panel.message = L.t("The built card — original files are not changed")
        guard panel.runModal() == .OK, let target = panel.url else { return }
        guard let built = try? state.basket.build() else { return }
        try? Data(built.image).write(to: target)
    }
}
