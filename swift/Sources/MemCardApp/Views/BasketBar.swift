import SwiftUI
import MemCardKit
import UniformTypeIdentifiers

/// Корзина внизу: пятнадцать блоков настоящей карты.
/// У многоблочного сейва видна вся цепочка — иначе непонятно,
/// куда делось место.
struct BasketBar: View {
    let basket: Basket
    @State private var saving = false
    @State private var result: String?
    @Environment(\.palette) private var palette

    var body: some View {
        VStack(spacing: 0) {
            if let note = basket.note ?? result {
                HStack(spacing: 9) {
                    Image(systemName: "exclamationmark.circle")
                        .font(.system(size: 12))
                        .foregroundStyle(palette.accent)
                    Text(note)
                        .font(.system(size: 12))
                        .foregroundStyle(palette.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(palette.accent.opacity(0.1))
            }

            HStack(spacing: 14) {
                HStack(spacing: 9) {
                    Image(systemName: "tray.full")
                        .font(.system(size: 12))
                        .foregroundStyle(palette.accent)
                    Text(L.t("КАРТА", "CARD"))
                        .font(.system(size: 10, weight: .bold))
                        .tracking(1.4)
                        .foregroundStyle(palette.ink)
                }

                HStack(spacing: 4) {
                    ForEach(basket.layout) { cell in
                        Cell(cell: cell)
                            .contextMenu {
                                if let item = cell.item {
                                    Button(L.t("Убрать из корзины",
                                               "Remove from basket")) {
                                        basket.remove(item)
                                        result = nil
                                    }
                                }
                                Button(L.t("Очистить корзину", "Clear basket")) {
                                    basket.clear()
                                    result = nil
                                }
                                .disabled(basket.isEmpty)
                            }
                    }
                }
                .fixedSize()

                VStack(alignment: .leading, spacing: 3) {
                    Text(line)
                        .font(.system(size: 12.5))
                        .foregroundStyle(palette.ink)
                        .lineLimit(1)
                        .truncationMode(.tail)
                    Text(L.t("занято \(basket.used) из \(PSX.slots) блоков", "\(basket.used) of \(PSX.slots) blocks used"))
                        .font(.system(size: 10.5, design: .monospaced))
                        .foregroundStyle(palette.inkFaint)
                        .lineLimit(1)
                        .fixedSize()
                }
                // Ужимается именно надпись, а не кнопки: в узком окне
                // текст обрезался по букве и «Очистить» вставало
                // столбиком по одному символу.
                .frame(minWidth: 0, maxWidth: .infinity, alignment: .leading)
                .layoutPriority(-1)

                HStack(spacing: 8) {
                    button(L.t("Очистить", "Clear"), filled: false) { basket.clear(); result = nil }
                        .disabled(basket.isEmpty)
                    button(L.t("В файл", "To file"), filled: true, action: save)
                        .disabled(basket.isEmpty || saving)
                }
                .fixedSize()
            }
            .padding(.horizontal, 16)
            .frame(height: 78)
            .background(palette.bar)
        }
        .overlay(alignment: .top) { Divider().overlay(palette.controlEdge) }
    }

    private var line: String {
        basket.isEmpty
            ? L.t("Пусто — добавляйте сейвы по дороге, из любого места", "Empty — add saves as you go, from anywhere")
            : basket.items.map(\.title).joined(separator: " · ")
    }

    private func save() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "card.mcr"
        panel.message = L.t("Собранная карта — исходные файлы не меняются", "The built card — original files are not changed")
        guard panel.runModal() == .OK, let target = panel.url else { return }
        saving = true
        defer { saving = false }
        do {
            let built = try basket.build()
            try Data(built.image).write(to: target)
            var text = L.t("Собрано: \(built.layout.count) ", "Built: \(built.layout.count) ")
                + (built.layout.count == 1 ? L.t("сейв", "save") : L.t("сейвов", "saves"))
            if !built.dropped.isEmpty {
                text += L.t(", отброшено дублей: \(built.dropped.count)", ", duplicates dropped: \(built.dropped.count)")
            }
            result = text
        } catch {
            result = L.t("Не собралось: \(error)", "Build failed: \(error)")
        }
    }

    private func button(_ title: String, filled: Bool,
                        action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 12, weight: filled ? .semibold : .regular))
                .foregroundStyle(filled ? palette.accentInk : palette.inkSoft)
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, 15)
                .padding(.vertical, 9)
                .background {
                    RoundedRectangle(cornerRadius: 7)
                        .fill(filled ? AnyShapeStyle(palette.accent)
                                     : AnyShapeStyle(palette.control))
                }
                .overlay {
                    if !filled {
                        RoundedRectangle(cornerRadius: 7)
                            .strokeBorder(palette.controlEdge, lineWidth: 1)
                    }
                }
        }
        .buttonStyle(.plain)
    }

    private struct Cell: View {
        let cell: Basket.Cell
        @Environment(\.palette) private var palette

        var body: some View {
            RoundedRectangle(cornerRadius: 4)
                .fill(cell.item == nil ? AnyShapeStyle(palette.well)
                                       : AnyShapeStyle(palette.tile))
                .overlay {
                    if let item = cell.item {
                        Text(cell.isContinuation ? "·" : short(item.title))
                            .font(.system(size: 8.5, weight: .medium,
                                          design: .monospaced))
                            .foregroundStyle(palette.inkSoft)
                            .lineLimit(1)
                            .padding(.horizontal, 2)
                    }
                }
                .overlay {
                    RoundedRectangle(cornerRadius: 4)
                        .strokeBorder(cell.item == nil ? palette.controlEdge
                                                       : palette.accent.opacity(0.7),
                                      lineWidth: 1)
                }
                .frame(width: 30, height: 40)
        }

        private func short(_ title: String) -> String {
            let words = title.split(separator: " ")
            if words.count >= 2 {
                return words.prefix(3).compactMap(\.first).map(String.init).joined()
            }
            return String(title.prefix(4))
        }
    }
}
