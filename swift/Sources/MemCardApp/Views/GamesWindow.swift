import SwiftUI
import MemCardKit

/// Окно образов игр на консоли. Отдельное от окна сохранений: там
/// только читают, здесь пишут на консоль и удаляют с неё.
struct GamesWindow: View {
    @Environment(AppState.self) private var state
    @Environment(\.colorScheme) private var scheme
    @Environment(\.openWindow) private var openWindow
    @State private var browser: GamesBrowser?
    @State private var picked: String = ""
    @State private var asking: GamesBrowser.Game?

    private var palette: Palette { scheme == .dark ? .dark : .light }

    private var profile: ConsoleProfile? {
        state.openGames ?? state.consoles.first
    }

    var body: some View {
        VStack(spacing: 0) {
            if let profile {
                head(profile)
                Divider().overlay(palette.barLine)
                folders(profile)
                Divider().overlay(palette.panelLine)
                listing
                bottom(profile)
            } else {
                Text(L.t("Консоли не настроены", "No consoles configured"))
                    .font(.system(size: 13))
                    .foregroundStyle(palette.inkSoft)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(palette.background)
        .environment(\.palette, palette)
        .frame(minWidth: 760, minHeight: 560)
        .task(id: profile?.id) { await start() }
        .alert(item: $asking) { game in
            Alert(
                title: Text(L.t("Удалить с консоли?", "Delete from console?")),
                message: Text(L.t(
                    "«\(game.name)» — \(GamesBrowser.size(game.size)), "
                        + L.t("файлов: \(game.files.count). Это нельзя отменить.", "\(game.files.count) files. This cannot be undone."),
                    "\"\(game.name)\" — \(GamesBrowser.size(game.size)), "
                        + "\(game.files.count) files. This cannot be undone.")),
                primaryButton: .destructive(Text(L.t("Удалить", "Delete"))) {
                    Task { await browser?.delete(game) }
                },
                secondaryButton: .cancel(Text(L.t("Отмена", "Cancel"))))
        }
    }

    private func start() async {
        guard let profile else { return }
        let made = GamesBrowser(profile)
        browser = made
        let list = state.folders.gameFolders(for: profile.label)
        picked = list.first ?? ""
        if !picked.isEmpty {
            await made.open(picked)
            await made.checkSpace()
        }
    }

    private func head(_ profile: ConsoleProfile) -> some View {
        HStack(spacing: 13) {
            Image(systemName: "opticaldisc")
                .font(.system(size: 15))
                .foregroundStyle(palette.accent)
            VStack(alignment: .leading, spacing: 3) {
                Text(L.t("Образы игр — \(profile.label)",
                         "Game images — \(profile.label)"))
                    .font(.system(size: 14.5, weight: .semibold))
                    .foregroundStyle(palette.ink)
                Text(profile.address)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
            }
            Spacer()
            if let free = browser?.freeSpace {
                Text(L.t("свободно \(GamesBrowser.size(free))",
                         "\(GamesBrowser.size(free)) free"))
                    .font(.system(size: 11.5, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
            }
            if browser?.busy == true { ProgressView().controlSize(.small) }
            Button(L.t("Обновить", "Refresh")) {
                Task {
                    await browser?.open(picked)
                    await browser?.checkSpace()
                }
            }
            .disabled(browser?.busy ?? true)
        }
        .padding(.horizontal, 18)
        .frame(height: 68)
    }

    private func folders(_ profile: ConsoleProfile) -> some View {
        HStack(spacing: 8) {
            Text(L.t("Папка:", "Folder:"))
                .font(.system(size: 11.5))
                .foregroundStyle(palette.inkSoft)
            Picker("", selection: $picked) {
                ForEach(state.folders.gameFolders(for: profile.label), id: \.self) {
                    Text($0).tag($0)
                }
            }
            .labelsHidden()
            .frame(maxWidth: 420)
            .onChange(of: picked) { _, next in
                Task {
                    await browser?.open(next)
                    await browser?.checkSpace()
                }
            }
            Button(L.t("Добавить путь…", "Add path…")) { addFolder(profile) }
                .controlSize(.small)
                .help(L.t("Ещё одна папка на консоли, где лежат образы",
                          "Another folder on the console holding images"))
            if state.folders.gameFolders(for: profile.label).count > 1 {
                Button(L.t("Убрать из списка", "Remove from list")) {
                    state.folders.removeGameFolder(picked, for: profile.label)
                    picked = state.folders.gameFolders(for: profile.label).first ?? ""
                }
                .controlSize(.small)
                // Название важно: рядом список игр, и короткое «Убрать»
                // читается как удаление с консоли.
                .help(L.t("Убирает путь из списка приложения. На консоли "
                          + "ничего не удаляется",
                          "Removes the path from the app's list. Nothing is "
                          + "deleted on the console"))
            }
            Spacer()
            if let counting = browser?.counting {
                Text(counting)
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkFaint)
            }
            Text("\(browser?.games.count ?? 0)")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(palette.inkFaint)
        }
        .padding(.horizontal, 18)
        .frame(height: 44)
    }

    private var listing: some View {
        ScrollView {
            LazyVStack(spacing: 4) {
                ForEach(browser?.games ?? []) { game in
                    row(game)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
        .frame(maxHeight: .infinity)
    }

    private func row(_ game: GamesBrowser.Game) -> some View {
        HStack(spacing: 11) {
            Image(systemName: game.isDirectory ? "folder.fill" : "opticaldisc.fill")
                .font(.system(size: 13))
                .foregroundStyle(palette.accent)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                Text(game.name)
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(palette.ink)
                    .lineLimit(1)
                if game.files.count > 1 {
                    Text(game.files.prefix(3).joined(separator: " · ")
                         + (game.files.count > 3
                            ? " · +\(game.files.count - 3)" : ""))
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(palette.inkFaint)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 8)
            Text(game.size < 0 ? "…" : GamesBrowser.size(game.size))
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(game.size < 0 ? palette.inkFaint : palette.inkSoft)
            Button(L.t("Удалить", "Delete")) { asking = game }
                .controlSize(.small)
                .disabled(browser?.busy ?? true)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(palette.tileEdge, lineWidth: 1)
        }
        .contextMenu {
            Button(L.t("Удалить с диска", "Delete from disk"), role: .destructive) {
                asking = game
            }
            Divider()
            Button(L.t("Копировать путь", "Copy path")) {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(game.path, forType: .string)
            }
            Button(L.t("Открыть папку в окне консоли",
                       "Open the folder in the console window")) {
                openInConsole(game)
            }
        }
    }

    /// Переход от образов к файлам: то же место, но в окне сохранений,
    /// где видно всё содержимое, а не только образы.
    private func openInConsole(_ game: GamesBrowser.Game) {
        guard let profile else { return }
        state.openConsole = profile
        state.consoleStartPath = game.isDirectory
            ? game.path
            : (game.path as NSString).deletingLastPathComponent
        openWindow(id: "console")
    }

    private func bottom(_ profile: ConsoleProfile) -> some View {
        VStack(spacing: 0) {
            if let browser, browser.uploading {
                uploading(browser)
            } else if let text = browser?.progress {
                note(text, bad: false, icon: "arrow.up.circle")
            } else if let text = browser?.trouble {
                note(text, bad: true, icon: "exclamationmark.triangle")
            } else if let text = browser?.note {
                note(text, bad: false, icon: "checkmark.circle")
            }

            HStack(spacing: 9) {
                Button(L.t("Загрузить игру…", "Add game…")) { pick() }
                    .buttonStyle(.borderedProminent)
                    .disabled((browser?.busy ?? true) || picked.isEmpty)
                Text(L.t("Игра PS1 — это .cue и .bin вместе; выбирайте папку целиком",
                         "A PS1 game is .cue plus .bin — pick the whole folder"))
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkFaint)
                Spacer()
                if profile.kind == "ps3" {
                    Text(L.t("после переноса нужен /refresh.ps3",
                             "run /refresh.ps3 afterwards"))
                        .font(.system(size: 11))
                        .foregroundStyle(palette.inkSoft)
                }
            }
            .padding(.horizontal, 18)
            .frame(height: 60)
            .background(palette.bar)
            .overlay(alignment: .top) { Divider().overlay(palette.barLine) }
        }
    }

    /// Строка хода загрузки: название файла, процент и полоса - всё
    /// в один ряд, чтобы не прыгала высота окна.
    private func uploading(_ browser: GamesBrowser) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "arrow.up.circle")
                .font(.system(size: 12))
                .foregroundStyle(palette.accent)

            Text(browser.fileCount > 1
                 ? L.t("\(browser.fileIndex) из \(browser.fileCount): \(browser.fileName)",
                       "\(browser.fileIndex) of \(browser.fileCount): \(browser.fileName)")
                 : browser.fileName)
                .font(.system(size: 12))
                .foregroundStyle(palette.ink)
                .lineLimit(1)
                .truncationMode(.middle)

            Text(L.t("Загружено \(browser.percent)%",
                     "Uploaded \(browser.percent)%"))
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundStyle(palette.accent)
                .fixedSize()

            ProgressView(value: browser.fraction)
                .progressViewStyle(.linear)
                .tint(palette.accent)
                .frame(minWidth: 120)

            Text("\(GamesBrowser.size(browser.sent)) / "
                 + GamesBrowser.size(browser.total))
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(palette.inkSoft)
                .fixedSize()
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 11)
        .background(palette.accent.opacity(0.09))
    }

    private func note(_ text: String, bad: Bool, icon: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(bad ? Palette.rgb(0xE8433F) : palette.accent)
            Text(text)
                .font(.system(size: 12))
                .foregroundStyle(palette.ink)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
        .background((bad ? Palette.rgb(0xE8433F) : palette.accent).opacity(0.09))
    }

    private func pick() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        panel.prompt = L.t("Загрузить", "Upload")
        panel.message = L.t("Папка с игрой или отдельный образ",
                            "Game folder or a single image")
        guard panel.runModal() == .OK, let source = panel.url else { return }
        Task { await browser?.upload(source, into: picked) }
    }

    private func addFolder(_ profile: ConsoleProfile) {
        let alert = NSAlert()
        alert.messageText = L.t("Папка на консоли", "Folder on the console")
        alert.informativeText = L.t(
            L.t("Полный путь, например /dev_usb000/PSXISO", "Full path, for example /dev_usb000/PSXISO"),
            "Full path, for example /dev_usb000/PSXISO")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
        field.stringValue = picked
        alert.accessoryView = field
        alert.addButton(withTitle: L.t("Добавить", "Add"))
        alert.addButton(withTitle: L.t("Отмена", "Cancel"))
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        let path = field.stringValue.trimmingCharacters(in: .whitespaces)
        guard path.hasPrefix("/") else { return }
        state.folders.addGameFolder(path, for: profile.label)
        picked = path
    }
}
