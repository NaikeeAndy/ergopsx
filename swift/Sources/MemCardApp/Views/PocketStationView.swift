import SwiftUI
import AppKit
import MemCardKit

/// PocketStation: устройство и Chocobo World.
///
/// Отдельным окном, а не разделом главного: здесь своя работа - железо и
/// перенос Боко между сейвом FF8 и приставочкой, - и она не про коллекцию.
///
/// Главное, ради чего окно существует: игра сверяет **метку привязки**,
/// четыре байта по `+0x28`, с обеих сторон. Не совпали - «wrong world»,
/// и выглядит это как поломка железа, хотя дело в числе.
struct PocketStationView: View {
    /// Снимок мимо экрана. `ImageRenderer` не рисует содержимое
    /// `ScrollView` - панель выходит пустой, и проверить её нечем.
    /// Флаг заменяет прокрутку на обычный столбец: только для `--render-pocket`.
    var snapshot = false

    @Environment(AppState.self) private var state
    @Environment(\.colorScheme) private var scheme

    @State private var adapters: [PS3Adapter.Device] = []
    @State private var otherDevices: [PS3Adapter.Device] = []
    @State private var probed = false
    @State private var chosenBoko: LibraryItem.ID?
    @State private var chosenFF8: LibraryItem.ID?
    @State private var report: String?

    private var palette: Palette { scheme == .dark ? .dark : .light }

    /// Сейвы Chocobo World на стороне PocketStation.
    private var bokoSide: [(item: LibraryItem, boko: Boko?)] {
        state.library.unique.compactMap { item in
            guard let block = item.save.blocks.first,
                  let boko = Boko.fromPocketStation(block, name: item.save.rawName)
            else { return nil }
            return (item, boko)
        }
    }

    /// **Все** сейвы Final Fantasy VIII, а не только те, где Боко уже есть.
    ///
    /// Сперва здесь стояло «носители записи Боко» - и колонка выходила
    /// пустой на всей коллекции: у сейва, который ещё ни разу не видел
    /// PocketStation, запись нулевая и разбор её законно отбрасывает.
    /// А связывать нужно как раз такие: свежую игру с приставочкой.
    private var ff8Side: [(item: LibraryItem, boko: Boko?)] {
        state.library.unique.compactMap { item in
            guard let block = item.save.blocks.first, FF8.isFF8(block) else {
                return nil
            }
            return (item, Boko.fromFF8(block))
        }
    }

    private func carrier(_ id: LibraryItem.ID?)
    -> (item: LibraryItem, boko: Boko?)? {
        (bokoSide + ff8Side).first { $0.item.id == id }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            device
            Divider().overlay(palette.panelLine)
            chocobo
        }
        .frame(minWidth: 640, minHeight: 520)
        .background(palette.background)
        .environment(\.palette, palette)
        .task { probe() }
    }

    // MARK: - устройство

    private var device: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(L.t("Adapter")).font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.ink)
                Spacer()
                Button(L.t("Look again")) { probe() }.controlSize(.small)
            }
            if let found = adapters.first {
                label("checkmark.circle.fill", palette.accent, found.name,
                      String(format: "%04X:%04X", found.vendorID, found.productID))
            } else if probed {
                label("questionmark.circle", palette.inkSoft,
                      L.t("PS3 Memory Card Adaptor not found"),
                      L.t("Plug in the CECHZM1 (SCPH-98042). This Mac has USB-C only, so it needs an adapter."))
                // «Не найден» и «опрос не работает» выглядят одинаково.
                // Список того, что система видит, эту разницу показывает.
                Text(L.plural("device", otherDevices.count) + ": "
                     + otherDevices.prefix(4).map(\.name).joined(separator: ", ")
                     + (otherDevices.count > 4 ? "…" : ""))
                    .font(.system(size: 10.5)).foregroundStyle(palette.inkFaint)
                    .lineLimit(2)
            }
        }
        .padding(18)
    }

    private func label(_ icon: String, _ tint: Color,
                       _ title: String, _ note: String) -> some View {
        HStack(alignment: .top, spacing: 9) {
            Image(systemName: icon).font(.system(size: 13)).foregroundStyle(tint)
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(palette.ink)
                Text(note).font(.system(size: 11)).foregroundStyle(palette.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: - Chocobo World

    private var chocobo: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(L.t("Chocobo World"))
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(palette.ink)
                .padding(.horizontal, 18).padding(.top, 16).padding(.bottom, 4)
            Text(L.t("The game compares a four-byte tag on both sides. Different tags and it calls the world someone else's."))
                .font(.system(size: 11)).foregroundStyle(palette.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 18).padding(.bottom, 12)

            HStack(alignment: .top, spacing: 0) {
                column(L.t("Boko"), bokoSide, $chosenBoko)
                Divider().overlay(palette.panelLine)
                column(L.t("Final Fantasy VIII save"), ff8Side, $chosenFF8)
            }

            Divider().overlay(palette.panelLine)
            footer
        }
    }

    private func column(_ title: String, _ rows: [(item: LibraryItem, boko: Boko?)],
                        _ pick: Binding<LibraryItem.ID?>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.system(size: 11, weight: .medium))
                .foregroundStyle(palette.inkSoft)
                .padding(.horizontal, 14).padding(.top, 10)
            if rows.isEmpty {
                Text(L.t("Nothing to show")).font(.system(size: 11.5))
                    .foregroundStyle(palette.inkFaint).padding(14)
            }
            let stack = VStack(spacing: 4) {
                ForEach(snapshot ? Array(rows.prefix(5)) : rows,
                        id: \.item.id) { row in
                    card(row, picked: pick.wrappedValue == row.item.id)
                        .onTapGesture { pick.wrappedValue = row.item.id }
                }
            }
            .padding(.horizontal, 10).padding(.bottom, 10)
            if snapshot {
                stack
                Spacer(minLength: 0)
            } else {
                ScrollView { stack }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func card(_ row: (item: LibraryItem, boko: Boko?),
                      picked: Bool) -> some View {
        // Метка читается прямо из байтов: она лежит там и тогда, когда
        // разбора нет - у сейва, ещё не видевшего PocketStation.
        let tag = tagOf(row.item)
        // Подпись из самого сейва, а не название игры: сейвов FF8 у
        // коллекции восемьдесят один, и по названию они все одинаковы.
        let caption = row.item.signature.isEmpty ? row.item.save.name
                                                 : row.item.signature
        return VStack(alignment: .leading, spacing: 3) {
            Text(caption)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(palette.ink).lineLimit(1)
                .truncationMode(.middle)
            Text(row.boko.map { L.t("level {0}, rank {1}", "\($0.level)",
                                    "\($0.rank)") }
                 ?? L.t("no Boko yet"))
                .font(.system(size: 10.5)).foregroundStyle(palette.inkSoft)
                .lineLimit(1)
            Text(String(format: "%08X", tag))
                .font(.system(size: 10.5, design: .monospaced))
                .foregroundStyle(tag == 0 ? palette.inkFaint : palette.accent)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 10).padding(.vertical, 8)
        .background {
            RoundedRectangle(cornerRadius: 7).fill(palette.tile)
            if picked {
                RoundedRectangle(cornerRadius: 7)
                    .fill(palette.accent.opacity(0.16))
            }
        }
        .overlay {
            RoundedRectangle(cornerRadius: 7)
                .strokeBorder(picked ? palette.accent : palette.tileEdge,
                              lineWidth: 1)
        }
        .contentShape(Rectangle())
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let report {
                Text(report).font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button(L.t("Link…")) { link() }
                    .disabled(chosenBoko == nil || chosenFF8 == nil)
            }
        }
        .padding(.horizontal, 18).padding(.vertical, 12)
    }

    // MARK: - действия

    /// Четыре байта привязки как они лежат в файле.
    private func tagOf(_ item: LibraryItem) -> UInt32 {
        guard let block = item.save.blocks.first else { return 0 }
        if FF8.isFF8(block), let bytes = FF8.chocoboBytes(block) {
            return Boko.link(in: bytes)
        }
        return Boko.fromPocketStation(block, name: item.save.rawName)?.ff8ID ?? 0
    }

    private func probe() {
        adapters = PS3Adapter.find()
        otherDevices = PS3Adapter.allDevices()
        probed = true
    }

    /// Переносит метку из сейва FF8 в запись Боко и включает мини-игру
    /// с обеих сторон. Пишет **в новые файлы** - как и всё остальное
    /// в этом приложении.
    private func link() {
        guard let bokoRow = carrier(chosenBoko),
              let ff8Row = carrier(chosenFF8),
              let ff8Block = ff8Row.item.save.blocks.first,
              let tagBytes = FF8.chocoboBytes(ff8Block) else { return }
        let tag = Boko.link(in: tagBytes)

        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.prompt = L.t("Save here")
        panel.message = L.t("Two new files — the originals are not changed")
        guard panel.runModal() == .OK, let folder = panel.url else { return }

        // Сторона Боко: метка из сейва FF8, Chocobo World включён, Боко
        // в отлучке - без первого флага игра считает мини-игру
        // не активированной и связку игнорирует.
        guard let bokoBlock = bokoRow.item.save.blocks.first,
              let newBokoBlock = Boko.relinked(bokoBlock, tag: tag)
        else { report = L.t("No Chocobo World record here"); return }

        // Сторона FF8: те же флаги, метка своя - её и оставляем.
        let fixedFF8 = Boko.withFlags(tagBytes, enabled: true, away: true,
                                      walking: false)
        guard let newFF8Block = FF8.withChocobo(ff8Block, record: fixedFF8,
                                                tables: state.library.engine.ff8Tables)
        else { report = L.t("Could not reseal the Final Fantasy VIII save"); return }

        let bokoOut = folder.appendingPathComponent(bokoRow.item.save.name
                                                    + "-linked.mcs")
        let ff8Out = folder.appendingPathComponent(ff8Row.item.save.name
                                                   + "-linked.mcs")
        do {
            try Data(Convert.single(remade(bokoRow.item.save, newBokoBlock),
                                    format: .mcs)).write(to: bokoOut)
            try Data(Convert.single(remade(ff8Row.item.save, newFF8Block),
                                    format: .mcs)).write(to: ff8Out)
        } catch {
            report = error.localizedDescription
            return
        }
        report = L.t("Tag {0} written to both. Files: {1}",
                     String(format: "%08X", tag),
                     bokoOut.lastPathComponent + ", " + ff8Out.lastPathComponent)
            + (tag == 0 ? "\n" + L.t("The tag is zero: this save has never been paired.") : "")
    }

    /// Тот же сейв с заменённым первым блоком.
    private func remade(_ save: Save, _ block: [UInt8]) -> Save {
        var blocks = save.blocks
        blocks[0] = block
        return Save(rawName: save.rawName, blocks: blocks, slot: save.slot,
                    state: save.state, origin: save.origin)
    }
}
