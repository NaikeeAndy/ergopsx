import SwiftUI
import MemCardKit

/// Какая панель принимает стрелки.
enum Pane: Hashable { case sidebar, saves }

struct RootView: View {
    @Environment(AppState.self) private var state
    @Environment(\.openWindow) private var openWindow
    @Environment(\.colorScheme) private var scheme

    @State private var selection: Selection = .everything
    @State private var search = ""
    @FocusState private var focus: Pane?

    private var palette: Palette { scheme == .dark ? .dark : .light }

    private var shown: [LibraryItem] {
        let all = state.library.visible(selection, order: state.order)
        guard !search.isEmpty else { return all }
        let needle = search.lowercased()
        return all.filter { $0.searchKey.contains(needle) }
    }

    private func current(in list: [LibraryItem]) -> LibraryItem? {
        if let last = state.picked.last, let found = list.first(where: { $0.id == last }) {
            return found
        }
        return list.first
    }

    private func pair(in list: [LibraryItem]) -> (LibraryItem, LibraryItem)? {
        guard state.picked.count == 2,
              let left = list.first(where: { $0.id == state.picked[0] }),
              let right = list.first(where: { $0.id == state.picked[1] }) else { return nil }
        return (left, right)
    }

    /// Листание стрелками. Без выделения начинаем с первого,
    /// на краях останавливаемся, а не заворачиваем по кругу.
    private func move(_ step: Int, in list: [LibraryItem]) {
        guard !list.isEmpty else { return }
        guard let last = state.picked.last,
              let index = list.firstIndex(where: { $0.id == last }) else {
            state.picked = [list[0].id]
            return
        }
        let next = index + step
        guard list.indices.contains(next) else { return }
        state.picked = [list[next].id]
    }

    private func choose(_ item: LibraryItem, extending: Bool) {
        if extending {
            if let index = state.picked.firstIndex(of: item.id) {
                state.picked.remove(at: index)
            } else {
                // Больше двух сравнивать нечем - вытесняем самый старый.
                state.picked.append(item.id)
                if state.picked.count > 2 { state.picked.removeFirst() }
            }
        } else {
            state.picked = [item.id]
        }
    }

    var body: some View {
        @Bindable var state = state
        // Список считается один раз за обход: раньше он вычислялся семью
        // разными местами, и каждое пересобирало его заново.
        let list = shown
        let current = current(in: list)
        let pair = pair(in: list)

        return VStack(spacing: 0) {
            ToolbarBar(search: $search, order: $state.order,
                       sidebar: $state.sidebar,
                       canBasket: current != nil,
                       inBasket: current.map(state.basket.contains) ?? false,
                       onSave: { saveOne(current) },
                       onBasket: { if let current { state.basket.toggle(current) } })

            Divider().overlay(palette.barLine)

            HStack(spacing: 0) {
                if state.sidebar {
                    SidebarView(library: state.library, consoles: state.consoles,
                                selection: $selection,
                                focus: $focus,
                                onRight: {
                                    focus = .saves
                                    // Сразу встаём на первый сейв: иначе
                                    // переход выглядит так, будто ничего
                                    // не случилось, пока не нажмёшь стрелку.
                                    let already = state.picked.last
                                    if !list.isEmpty,
                                       !list.contains(where: { $0.id == already }) {
                                        state.picked = [list[0].id]
                                    }
                                },
                                onConsole: { profile in
                                    state.openConsole = profile
                                    openWindow(id: "console")
                                })
                        .frame(width: 214)
                        .transition(.move(edge: .leading))
                    Divider().overlay(palette.panelLine)
                }

                Group {
                    if state.library.loading {
                        Waiting(text: L.t("Читаю сейвы", "Reading saves"))
                    } else if state.folders.urls.isEmpty {
                        Empty(onPick: pick)
                    } else if list.isEmpty {
                        Waiting(text: search.isEmpty ? L.t("Здесь пусто", "Nothing here")
                                                     : L.t("Ничего не нашлось", "Nothing found"))
                    } else {
                        SaveListView(items: list, picked: state.picked,
                                     basket: state.basket,
                                     onChoose: choose, live: focus == .saves,
                                     copies: { state.library.copies(of: $0) },
                                     onSave: { saveOne($0) },
                                     onCompare: { item in
                                         // Второй уже выделен - берём его
                                         // и открываем сравнение.
                                         if let other = state.picked.first,
                                            other != item.id {
                                             state.picked = [other, item.id]
                                         }
                                         state.comparing = true
                                     },
                                     canCompare: { item in
                                         state.picked.contains { $0 != item.id }
                                     },
                                     onCopies: { item in
                                         state.copiesOf = (
                                             title: item.title,
                                             name: item.save.name,
                                             paths: [item.origin].compactMap { $0 }
                                                 + state.library.copies(of: item))
                                         openWindow(id: "copies")
                                     })
                            .focusable()
                            .focusEffectDisabled()
                            .focused($focus, equals: .saves)
                            .onKeyPress(.upArrow) { move(-1, in: list); return .handled }
                            .onKeyPress(.downArrow) { move(1, in: list); return .handled }
                            // Влево - обратно к выбору игры. Так вся
                            // навигация делается с клавиатуры.
                            .onKeyPress(.leftArrow) { focus = .sidebar; return .handled }
                            .onKeyPress(.space) {
                                if let current { state.basket.toggle(current) }
                                return .handled
                            }
                    }
                }
                // Список - одна колонка постоянной ширины. Всё остальное
                // место отдано разбору.
                .frame(maxWidth: RootView.listWidth, maxHeight: .infinity)

                Divider().overlay(palette.panelLine)
                InspectorView(item: current, engine: state.library.engine)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            BasketBar(basket: state.basket)
        }
        .background(palette.background)
        .environment(\.palette, palette)
        .animation(.easeInOut(duration: 0.18), value: state.sidebar)
        .sheet(isPresented: $state.comparing) {
            if let pair {
                CompareView(left: pair.0, right: pair.1,
                            engine: state.library.engine,
                            onClose: { state.comparing = false })
                    .environment(\.palette, palette)
            }
        }
        .frame(minWidth: 900, minHeight: 640)
        .onAppear { if focus == nil { focus = .sidebar } }
        .onChange(of: selection) { _, _ in
            state.picked = []
        }
    }

    /// Сохранить выделенный сейв отдельным файлом. Исходный не трогаем:
    /// пишем только туда, куда указал пользователь.
    private func saveOne(_ item: LibraryItem?) {
        guard let item else { return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = item.save.name + ".mcs"
        panel.message = L.t("Отдельный сейв — исходный файл не меняется", "A single save — the original file is not changed")
        guard panel.runModal() == .OK, let target = panel.url else { return }
        let format: Convert.Single =
            target.pathExtension.lowercased() == "psv" ? .psv
            : target.pathExtension.lowercased() == "raw" ? .raw : .mcs
        try? Data(Convert.single(item.save, format: format)).write(to: target)
    }

    private func pick() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = true
        panel.prompt = L.t("Добавить", "Add")
        panel.message = L.t("Где лежат сейвы", "Where the saves are")
        guard panel.runModal() == .OK else { return }
        let chosen = panel.urls
        Task { for url in chosen { await state.addFolder(url) } }
    }

    /// Ширина колонки со списком. Карточка сейва в неё влезает целиком,
    /// а остальное достаётся разбору.
    static let listWidth: CGFloat = 356
}

struct Waiting: View {
    let text: String
    @Environment(\.palette) private var palette

    var body: some View {
        Text(text)
            .font(.system(size: 14))
            .foregroundStyle(palette.inkSoft)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct Empty: View {
    let onPick: () -> Void
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(spacing: 14) {
            Text(L.t("Папок с сейвами не добавлено", "No save folders added"))
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(palette.ink)
            Text(L.t("Их может быть сколько угодно — приложение ничего в них не меняет", "As many as you like — the app never changes anything in them"))
                .font(.system(size: 12.5))
                .foregroundStyle(palette.inkSoft)
            Button(L.t("Добавить папку", "Add folder"), action: onPick)
                .buttonStyle(.borderedProminent)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
