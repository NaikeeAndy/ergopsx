import SwiftUI
import MemCardKit

/// Настройки - отдельное окно с разделами слева.
///
/// Своя вёрстка, а не системная форма: у приложения две темы и общий
/// вид панелей, и настройки не должны выглядеть чужими.
struct SettingsView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case folders, look, consoles, about
        var id: String { rawValue }

        var label: String {
            switch self {
            case .folders: L.t("Folders")
            case .look: L.t("View")
            case .consoles: L.t("Consoles")
            case .about: L.t("Collection")
            }
        }

        var icon: String {
            switch self {
            case .folders: "folder"
            case .look: "square.grid.2x2"
            case .consoles: "network"
            case .about: "chart.bar"
            }
        }
    }

    @Environment(AppState.self) private var state
    @Environment(\.colorScheme) private var scheme
    @Environment(\.openWindow) private var openWindow
    @State private var tab: Tab = .folders

    private var palette: Palette { scheme == .dark ? .dark : .light }

    var body: some View {
        HStack(spacing: 0) {
            rail
            Divider().overlay(palette.panelLine)
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    switch tab {
                    case .folders: FoldersPane()
                    case .look: LookPane()
                    case .consoles: ConsolesPane(onOpen: { profile in
                        state.openConsole = profile
                        openWindow(id: "console")
                    })
                    case .about: AboutPane()
                    }
                }
                .padding(22)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(minWidth: 660, minHeight: 480)
        .background(palette.background)
        .environment(\.palette, palette)
    }

    private var rail: some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(Tab.allCases) { item in
                Button { tab = item } label: {
                    HStack(spacing: 9) {
                        Image(systemName: item.icon)
                            .font(.system(size: 12))
                            .frame(width: 16)
                        Text(item.label)
                            .font(.system(size: 12.5,
                                          weight: tab == item ? .semibold : .regular))
                        Spacer(minLength: 0)
                    }
                    .foregroundStyle(tab == item ? palette.accentInk : palette.ink)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background {
                        if tab == item {
                            RoundedRectangle(cornerRadius: 6).fill(palette.accent)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(10)
        .frame(width: 168)
        .background(palette.panel)
    }
}

// MARK: - Папки

private struct FoldersPane: View {
    @Environment(AppState.self) private var state
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Header(L.t("Save folders"),
                   note: L.t("Read at startup. As many as you like — the collection, console dumps, other people’s cards. A save sitting in two folders is counted once."))

            if state.folders.urls.isEmpty && state.folders.missing.isEmpty {
                Text(L.t("None yet"))
                    .font(.system(size: 12.5))
                    .foregroundStyle(palette.inkFaint)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 30)
                    .background(palette.panel, in: RoundedRectangle(cornerRadius: 8))
            } else {
                VStack(spacing: 5) {
                    ForEach(state.folders.urls, id: \.path) { url in
                        row(url, gone: false)
                    }
                    ForEach(state.folders.missing, id: \.self) { path in
                        row(URL(fileURLWithPath: path), gone: true)
                    }
                }
            }

            HStack(spacing: 9) {
                Button(L.t("Add folder…"), action: pick)
                    .buttonStyle(.borderedProminent)
                Button(L.t("Re-read")) { Task { await state.rescan() } }
                    .disabled(state.library.loading)
                Spacer()
                if state.library.loading {
                    ProgressView().controlSize(.small)
                }
            }
            .padding(.top, 2)

            if !state.library.skipped.isEmpty {
                Divider().overlay(palette.panelLine).padding(.vertical, 4)
                Text(L.t("Unreadable: {0}", state.library.skipped.count))
                    .font(.system(size: 11.5, weight: .medium))
                    .foregroundStyle(palette.inkSoft)
                ForEach(state.library.skipped.prefix(6), id: \.path) { item in
                    Text("\(item.path) — \(item.reason)")
                        .font(.system(size: 11))
                        .foregroundStyle(palette.inkFaint)
                }
            }
        }
    }

    /// Сколько сейвов пришло из этой папки — иначе непонятно,
    /// зачем она в списке.
    private func count(_ url: URL) -> Int {
        let prefix = url.path.hasSuffix("/") ? url.path : url.path + "/"
        return state.library.items.filter {
            ($0.origin?.path ?? "").hasPrefix(prefix)
        }.count
    }

    private func row(_ url: URL, gone: Bool) -> some View {
        HStack(spacing: 11) {
            Image(systemName: gone ? "questionmark.folder" : "folder.fill")
                .font(.system(size: 14))
                .foregroundStyle(gone ? Palette.rgb(0xE8433F) : palette.accent)
                .frame(width: 18)

            VStack(alignment: .leading, spacing: 2) {
                Text(url.lastPathComponent)
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(palette.ink)
                Text(url.deletingLastPathComponent().path
                    .replacingOccurrences(of: NSHomeDirectory(), with: "~"))
                    .font(.system(size: 10.5))
                    .foregroundStyle(palette.inkFaint)
                    .lineLimit(1)
                    .truncationMode(.head)
            }

            Spacer(minLength: 8)

            if gone {
                Text(L.t("not found"))
                    .font(.system(size: 10.5, weight: .medium))
                    .foregroundStyle(Palette.rgb(0xE8433F))
            } else if !state.library.loading {
                Text(L.t("{0} saves", count(url)))
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkSoft)
            }

            if !gone {
                Button {
                    NSWorkspace.shared.activateFileViewerSelecting([url])
                } label: {
                    Image(systemName: "arrow.up.forward.square")
                        .font(.system(size: 12))
                        .foregroundStyle(palette.inkSoft)
                }
                .buttonStyle(.plain)
                .help(L.t("Show in Finder"))
            }

            Button {
                Task { await state.removeFolder(url) }
            } label: {
                Image(systemName: "minus.circle")
                    .font(.system(size: 13))
                    .foregroundStyle(palette.inkSoft)
            }
            .buttonStyle(.plain)
            .help(L.t("Remove from the list — the folder stays on disk"))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(gone ? Palette.rgb(0xE8433F).opacity(0.5)
                                   : palette.tileEdge, lineWidth: 1)
        }
    }

    private func pick() {
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
}

// MARK: - Вид

private struct LookPane: View {
    @Environment(AppState.self) private var state
    @Environment(\.palette) private var palette

    var body: some View {
        @Bindable var state = state
        VStack(alignment: .leading, spacing: 16) {
            Header(L.t("List view"),
                   note: L.t("The same switches live in the toolbar and the View menu."))

            VStack(alignment: .leading, spacing: 12) {
                Picker(L.t("Order"), selection: $state.order) {
                    ForEach(SortOrder.allCases) { Text($0.label).tag($0) }
                }
                .frame(width: 300)

                Toggle(L.t("Show the game list on the left"), isOn: $state.sidebar)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(palette.panel, in: RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 8) {
                Text(L.t("Language"))
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.ink)
                Picker("", selection: Binding(
                    get: { state.folders.language },
                    set: { state.setLanguage($0) })) {
                    ForEach(Lang.allCases) { Text($0.label).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(width: 260)
                Text(L.t("Save contents and game titles stay as they are — they come from the games themselves."))
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkFaint)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(palette.panel, in: RoundedRectangle(cornerRadius: 8))

            Header(L.t("Theme"),
                   note: L.t("Light is the console shell, dark is the memory card screen of the BIOS. Follows the system appearance."))
        }
    }
}

// MARK: - Консоли

private struct ConsolesPane: View {
    let onOpen: (ConsoleProfile) -> Void
    @Environment(AppState.self) private var state
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Header(L.t("Consoles"),
                   note: L.t("The console shows its own address — on PS3 it is printed by webMAN, on Switch the server puts it on screen. The password is kept next to the collection and is never shown."))

            VStack(spacing: 6) {
                ForEach(state.consolesToSetUp) { profile in
                    ConsoleRow(profile: profile, onOpen: onOpen)
                }
            }

            if let trouble = state.consoleTrouble {
                Text(trouble)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Palette.rgb(0xE8433F))
            }
        }
    }
}

/// Одна консоль: адрес правится на месте, рядом проверка связи
/// и подсказка, что на этой консоли должно быть запущено.
private struct ConsoleRow: View {
    let profile: ConsoleProfile
    let onOpen: (ConsoleProfile) -> Void

    @Environment(AppState.self) private var state
    @Environment(\.palette) private var palette

    @State private var host = ""
    @State private var port = ""
    @State private var checking = false
    @State private var verdict: String?
    @State private var saved = false
    @State private var helping = false
    @FocusState private var editing: Bool

    private var changed: Bool {
        host != profile.host || port != String(profile.port)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 9) {
                Image(systemName: "gamecontroller.fill")
                    .font(.system(size: 13))
                    .foregroundStyle(profile.hasAddress ? palette.accent
                                                        : palette.inkFaint)
                    .frame(width: 18)

                Text(profile.label)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.ink)

                Button { helping.toggle() } label: {
                    Image(systemName: "questionmark.circle")
                        .font(.system(size: 12))
                        .foregroundStyle(palette.inkSoft)
                }
                .buttonStyle(.plain)
                .help(L.t("What the console needs"))
                .popover(isPresented: $helping, arrowEdge: .bottom) {
                    ConsoleHelp(kind: profile.kind)
                }

                Spacer(minLength: 8)

                if !profile.hasAddress {
                    Text(L.t("not configured"))
                        .font(.system(size: 11))
                        .foregroundStyle(palette.inkFaint)
                }
            }

            HStack(spacing: 7) {
                Text(L.t("Address"))
                    .font(.system(size: 11.5))
                    .foregroundStyle(palette.inkSoft)
                TextField("192.168.0.1", text: $host)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12, design: .monospaced))
                    .frame(width: 138)
                    .focused($editing)
                    .onSubmit(commit)
                    .onChange(of: host) { _, _ in saved = false }
                Text(L.t("port"))
                    .font(.system(size: 11.5))
                    .foregroundStyle(palette.inkSoft)
                TextField("21", text: $port)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12, design: .monospaced))
                    .frame(width: 58)
                    .onSubmit(commit)

                if changed {
                    Button(L.t("Save@@verb"), action: commit)
                        .controlSize(.small)
                        .buttonStyle(.borderedProminent)
                } else if saved {
                    // Иначе сохранение проходит совершенно молча,
                    // и непонятно, случилось оно или нет.
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                        Text(L.t("saved"))
                    }
                    .font(.system(size: 11))
                    .foregroundStyle(Palette.rgb(0x2FA84F))
                }

                Spacer(minLength: 6)

                Button(L.t("Check")) { Task { await check() } }
                    .controlSize(.small)
                    .disabled(host.isEmpty || checking)
                Button(L.t("Open")) { onOpen(profile) }
                    .controlSize(.small)
                    .disabled(!profile.hasAddress)
            }

            if checking {
                HStack(spacing: 6) {
                    ProgressView().controlSize(.small)
                    Text(L.t("checking…"))
                        .font(.system(size: 11))
                        .foregroundStyle(palette.inkSoft)
                }
            } else if let verdict {
                Text(verdict == L.t("connected") ? L.t("Responds") : L.t("No response: {0}", verdict))
                    .font(.system(size: 11))
                    .foregroundStyle(verdict == L.t("connected")
                                     ? Palette.rgb(0x2FA84F)
                                     : Palette.rgb(0xE8433F))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(13)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(palette.tileEdge, lineWidth: 1)
        }
        .onAppear { pull() }
        // Профиль мог измениться снаружи - подхватываем.
        .onChange(of: profile.address) { _, _ in pull() }
    }

    private func pull() {
        host = profile.host
        port = String(profile.port)
    }

    private func commit() {
        let cleaned = host.trimmingCharacters(in: .whitespaces)
        guard let number = UInt16(port.trimmingCharacters(in: .whitespaces)),
              number > 0 else { return }
        var next = profile
        next.host = cleaned
        next.port = number
        verdict = nil
        state.updateConsole(next)
        host = cleaned
        port = String(number)
        saved = state.consoleTrouble == nil
    }

    private func check() async {
        if changed { commit() }
        checking = true
        defer { checking = false }
        var probe = profile
        probe.host = host.trimmingCharacters(in: .whitespaces)
        if let number = UInt16(port.trimmingCharacters(in: .whitespaces)) {
            probe.port = number
        }
        verdict = await ConsoleStore.check(probe)
    }
}

/// Что должно стоять и работать на консоли, чтобы FTP отвечал.
private struct ConsoleHelp: View {
    let kind: String
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            Text(kind == "switch" ? "Switch" : "PlayStation 3")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(palette.ink)

            ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                HStack(alignment: .top, spacing: 7) {
                    Text("•").foregroundStyle(palette.accent)
                    Text(line)
                        .fixedSize(horizontal: false, vertical: true)
                        .foregroundStyle(palette.inkSoft)
                }
                .font(.system(size: 11.5))
            }
        }
        .padding(15)
        .frame(width: 380)
        .background(palette.panel)
    }

    private var lines: [String] {
        if kind == "switch" {
            return [
                L.t("The console is on, awake and on the same network. The screen may be off, but the console must be running."),
                L.t("The ftpsrv FTP server is running, and specifically as a sysmodule (switch_sysmod), not the app: the app runs only while the homebrew menu is open, and closes together with it."),
                L.t("The module lives in /atmosphere/contents/420000000000011B/ — exefs.nsp, toolbox.json and an empty flags/boot2.flag. Enable it in an overlay (ovlSysmodules or uberhand)."),
                L.t("Login and password come from the [Nx-Sys] section of /config/ftpsrv/config.ini. The [Nx-App] section belongs to the app, not the module."),
                L.t("The usual port is 5000. The sphaira app and the module take the same port — they cannot run together."),
                L.t("Emulator memory cards are plain files: /switch/duckstation/memcards/."),
            ]
        }
        return [
            L.t("The console is on and on the same network. In sleep mode FTP does not answer."),
            L.t("Custom firmware with webMAN MOD or multiMAN is installed — they are what run the FTP server."),
            L.t("The usual port is 21, anonymous login, no password."),
            L.t("webMAN shows the console address on its front page, and the console network settings show it too."),
            L.t("Saves live in /dev_hdd0/home/<profile>/savedata/, virtual cards in /dev_hdd0/savedata/vmc."),
            L.t("While a PS1 game is running, leave the card alone: the console keeps it mounted."),
        ]
    }
}

// MARK: - Коллекция

private struct AboutPane: View {
    @Environment(AppState.self) private var state
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Header(L.t("What was read"),
                   note: L.t("Duplicates are merged by content and name: the same save often sits in several containers."))

            let unique = state.library.unique.count
            let parsed = state.library.unique.filter {
                Digest.of($0, engine: state.library.engine) != nil
            }.count
            let timed = state.library.unique.filter { $0.playtime != nil }.count

            VStack(spacing: 1) {
                stat(L.t("Folders@@count"), "\(state.folders.urls.count)")
                stat(L.t("Files found"), "\(state.library.items.count)")
                stat(L.t("Unique saves"), "\(unique)")
                stat(L.t("Games"), "\(state.library.games.count)")
                stat(L.t("Card images@@count"), "\(state.library.cardCount)")
                stat(L.t("Parsed in detail"), "\(parsed)")
                stat(L.t("With playtime"), "\(timed)")
            }
            .background(palette.panel, in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(palette.panelLine, lineWidth: 1)
            }
        }
    }

    private func stat(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 12.5))
                .foregroundStyle(palette.inkSoft)
            Spacer()
            Text(value)
                .font(.system(size: 12.5, weight: .semibold, design: .monospaced))
                .foregroundStyle(palette.ink)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
    }
}

private struct Header: View {
    let title: String
    let note: String
    @Environment(\.palette) private var palette

    init(_ title: String, note: String) {
        self.title = title
        self.note = note
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(palette.ink)
            Text(note)
                .font(.system(size: 11.5))
                .foregroundStyle(palette.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
