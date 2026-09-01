import SwiftUI
import MemCardKit

/// Консоль как место, а не как кнопка «подключиться»: зашли, посмотрели,
/// забрали к себе.
struct ConsolesView: View {
    let profile: ConsoleProfile
    let collection: URL?
    /// Нужен, чтобы разбирать прочитанное на лету.
    let engine: Engine
    let basket: Basket
    /// Что делать после скачивания: перечитать папки и сказать,
    /// прибавилось ли что-нибудь.
    var onDownloaded: (() -> Void)?
    /// Открыть окно образов игр этой же консоли.
    var onGames: (() -> Void)?
    /// С какой папки начать - переход из окна образов игр.
    var startPath: String?
    @State private var browser: ConsoleBrowser
    @Environment(\.palette) private var palette

    init(profile: ConsoleProfile, collection: URL?, engine: Engine,
         basket: Basket, startPath: String? = nil,
         onDownloaded: (() -> Void)? = nil,
         onGames: (() -> Void)? = nil) {
        self.startPath = startPath
        self.onGames = onGames
        self.profile = profile
        self.collection = collection
        self.engine = engine
        self.basket = basket
        self.onDownloaded = onDownloaded
        _browser = State(initialValue: ConsoleBrowser(profile))
    }

    var body: some View {
        VStack(spacing: 0) {
            card
            Divider().overlay(palette.panelLine)
            crumbs
            Divider().overlay(palette.panelLine)
            HStack(spacing: 0) {
                listing
                if browser.peeked != nil {
                    Divider().overlay(palette.panelLine)
                    peek.frame(width: 330)
                }
            }
            if let note = browser.downloaded ?? browser.trouble {
                warning(note, bad: browser.trouble != nil)
            }
            warning(L.t("What you write is picked up only when the game starts: the emulator reads the card once. While the game is open, we do not overwrite the card."), bad: false)
        }
        .task(id: profile.id) { await browser.open(startPath) }
    }

    private var card: some View {
        HStack(spacing: 13) {
            Circle()
                .fill(browser.greeting != nil ? Palette.rgb(0x2FA84F) : palette.inkFaint)
                .frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 3) {
                Text(profile.label)
                    .font(.system(size: 14.5, weight: .semibold))
                    .foregroundStyle(palette.ink)
                Text(profile.address + " · "
                     + (profile.hasPassword ? L.t("password login") : L.t("anonymous")))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
            }
            Spacer()
            if browser.busy { ProgressView().controlSize(.small) }
            Button(L.t("Game list")) { onGames?() }
            Button(L.t("Refresh")) { Task { await browser.open() } }
                .disabled(browser.busy)
        }
        .padding(.horizontal, 18)
        .frame(height: 68)
    }

    private var crumbs: some View {
        HStack(spacing: 10) {
            Button {
                Task { await browser.up() }
            } label: {
                Image(systemName: "arrow.up").font(.system(size: 11, weight: .bold))
            }
            .disabled(browser.path == "/" || browser.busy)

            Text(browser.path)
                .font(.system(size: 11.5, design: .monospaced))
                .foregroundStyle(palette.inkSoft)
                .lineLimit(1)
                .truncationMode(.head)
            Spacer()
            Text("\(browser.entries.count)")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(palette.inkFaint)
        }
        .padding(.horizontal, 18)
        .frame(height: 34)
    }

    private var listing: some View {
        ScrollView {
            LazyVStack(spacing: 3) {
                ForEach(Array(browser.entries.enumerated()), id: \.offset) { _, entry in
                    row(entry)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
        .frame(maxHeight: .infinity)
    }

    private func row(_ entry: FTPClient.Entry) -> some View {
        HStack(spacing: 11) {
            Image(systemName: entry.isDirectory ? "folder" : "doc")
                .font(.system(size: 12))
                .foregroundStyle(entry.isDirectory ? palette.accent : palette.inkSoft)
                .frame(width: 16)
            Text(entry.name)
                .font(.system(size: 12.5, design: entry.isDirectory ? .default
                                                                    : .monospaced))
                .foregroundStyle(palette.ink)
                .lineLimit(1)
            Spacer(minLength: 8)
            if !entry.isDirectory {
                Text(Self.size(entry.size))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(palette.inkFaint)
                Button(L.t("Fetch")) { save(entry.name) }
                    .disabled(browser.busy)
                    .controlSize(.small)
            }
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 7)
        .background {
            if entry.isDirectory {
                RoundedRectangle(cornerRadius: 7).fill(palette.tile)
            }
        }
        .background {
            if browser.peeked?.name == entry.name {
                RoundedRectangle(cornerRadius: 7).fill(palette.accent.opacity(0.18))
            }
        }
        .contentShape(Rectangle())
        .contextMenu {
            Button(L.t("Copy path")) {
                let full = browser.path.hasSuffix("/")
                    ? browser.path + entry.name
                    : browser.path + "/" + entry.name
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(full, forType: .string)
            }
        }
        .onTapGesture {
            if entry.isDirectory {
                enter(entry.name)
            } else {
                // Смотрим не скачивая: карта читается в память.
                Task { await browser.peek(entry.name, engine: engine) }
            }
        }
    }

    private func enter(_ name: String) {
        let next = browser.path.hasSuffix("/") ? browser.path + name
                                               : browser.path + "/" + name
        Task { await browser.open(next) }
    }

    /// Панель просмотра: что лежит внутри файла на консоли.
    private var peek: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let found = browser.peeked {
                HStack(spacing: 8) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(found.name)
                            .font(.system(size: 12.5, weight: .semibold))
                            .foregroundStyle(palette.ink)
                            .lineLimit(1)
                        Text(found.isCard
                             ? L.t("card image · {0} saves", found.items.count)
                             : L.t("{0} saves", found.items.count))
                            .font(.system(size: 11))
                            .foregroundStyle(palette.inkSoft)
                    }
                    Spacer(minLength: 6)
                    Button {
                        browser.closePeek()
                    } label: {
                        Image(systemName: "xmark").font(.system(size: 10, weight: .bold))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(palette.inkSoft)
                }
                .padding(.horizontal, 14)
                .frame(height: 52)

                Divider().overlay(palette.panelLine)

                ScrollView {
                    LazyVStack(spacing: 4) {
                        ForEach(found.items) { item in
                            peekRow(item)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                }

                Divider().overlay(palette.panelLine)
                HStack(spacing: 8) {
                    Button(L.t("Save…")) { save(found.name) }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                    Spacer()
                    Text(L.t("nothing written to disk"))
                        .font(.system(size: 10.5))
                        .foregroundStyle(palette.inkFaint)
                }
                .padding(.horizontal, 14)
                .frame(height: 46)
            }
        }
        .background(palette.panel)
    }

    private func peekRow(_ item: LibraryItem) -> some View {
        HStack(spacing: 10) {
            IconView(block: item.save.blocks[0], key: item.fingerprint, side: 34)
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(palette.ink)
                    .lineLimit(1)
                Text(item.signature.isEmpty ? item.save.name : item.signature)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
                    .lineLimit(1)
            }
            Spacer(minLength: 6)
            if let clock = item.clock {
                Text(clock)
                    .font(.system(size: 10.5, design: .monospaced))
                    .foregroundStyle(palette.accent)
            }
            Button {
                basket.toggle(item)
            } label: {
                Image(systemName: basket.contains(item)
                      ? "checkmark.circle.fill" : "plus.circle")
                    .font(.system(size: 13))
                    .foregroundStyle(basket.contains(item) ? palette.accent
                                                           : palette.inkSoft)
            }
            .buttonStyle(.plain)
            .help(basket.contains(item) ? L.t("Remove from basket")
                                        : L.t("To basket — no need to download the whole card"))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 7))
    }

    /// Забрать файл: сначала читаем его в память, потом спрашиваем,
    /// куда и в каком виде положить.
    private func save(_ name: String) {
        Task {
            if browser.peeked?.name != name {
                await browser.peek(name, engine: engine)
            }
            guard let found = browser.peeked else { return }
            await MainActor.run { ask(found) }
        }
    }

    private func ask(_ found: ConsoleBrowser.Peek) {
        let choices: [ConsoleBrowser.SaveAs] = found.isCard
            ? [.asIs] + Convert.Card.allCases.map { .card($0) }
            : [.asIs] + Convert.Single.allCases.map { .single($0) }

        // Приписка под списком меняется вместе с выбором - иначе
        // разница между MCR, MCD и VMP видна только знающему.
        let hint = NSTextField(wrappingLabelWithString: choices[0].note)
        hint.font = .systemFont(ofSize: 11)
        hint.textColor = .secondaryLabelColor
        hint.frame = NSRect(x: 74, y: 4, width: 386, height: 32)

        let helper = FormatHelper(choices: choices, hint: hint)
        let picker = NSPopUpButton(frame: NSRect(x: 74, y: 40, width: 386, height: 25))
        picker.addItems(withTitles: choices.map(\.label))
        picker.target = helper
        picker.action = #selector(FormatHelper.changed(_:))

        let label = NSTextField(labelWithString: L.t("Format:"))
        label.frame = NSRect(x: 12, y: 44, width: 60, height: 20)

        let box = NSView(frame: NSRect(x: 0, y: 0, width: 476, height: 76))
        box.addSubview(label)
        box.addSubview(picker)
        box.addSubview(hint)

        let panel = NSSavePanel()
        panel.nameFieldStringValue = found.name
        panel.message = L.t("The file on the console is not changed — a copy is saved")
        panel.accessoryView = box
        panel.canCreateDirectories = true
        if let collection { panel.directoryURL = collection }

        let answer = panel.runModal()
        // Список держит помощника слабой ссылкой: без этого он может
        // исчезнуть раньше окна, и подсказка перестанет обновляться.
        withExtendedLifetime(helper) {}
        guard answer == .OK, var target = panel.url else { return }
        let choice = choices[picker.indexOfSelectedItem]
        // Расширение подставляем сами, если пользователь его не написал.
        if !choice.ext.isEmpty,
           target.pathExtension.lowercased() != choice.ext {
            target = target.deletingPathExtension().appendingPathExtension(choice.ext)
        }
        do {
            try browser.save(found, to: target, format: choice)
            onDownloaded?()
        } catch {
            NSSound.beep()
        }
    }

    private func warning(_ text: String, bad: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: bad ? "exclamationmark.triangle" : "info.circle")
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
        .overlay(alignment: .top) { Divider().overlay(palette.panelLine) }
    }

    /// Держатель обратного вызова для списка форматов: SwiftUI сюда
    /// не дотягивается, панель сохранения - обычный AppKit.
    private final class FormatHelper: NSObject {
        let choices: [ConsoleBrowser.SaveAs]
        let hint: NSTextField

        init(choices: [ConsoleBrowser.SaveAs], hint: NSTextField) {
            self.choices = choices
            self.hint = hint
        }

        // Обработчик зовёт AppKit, а тот живёт на главном потоке.
        // Без пометки Swift 6 отказывается собирать.
        @MainActor @objc func changed(_ sender: NSPopUpButton) {
            let index = sender.indexOfSelectedItem
            guard choices.indices.contains(index) else { return }
            hint.stringValue = choices[index].note
        }
    }

    static func size(_ bytes: Int) -> String {
        if bytes >= 1_048_576 {
            return String(format: L.t("%.1f MB"), Double(bytes) / 1_048_576)
        }
        if bytes >= 1024 { return L.t("{0} KB", bytes / 1024) }
        return L.t("{0} B", bytes)
    }
}
