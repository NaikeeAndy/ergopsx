import SwiftUI
import AppKit
import MemCardKit

/// Главный список. Сейв выглядит одинаково независимо от того,
/// откуда приехал.
struct SaveListView: View {
    let items: [LibraryItem]
    let picked: [LibraryItem.ID]
    let basket: Basket
    let onChoose: (LibraryItem, Bool) -> Void
    /// На этом ли списке сейчас клавиатура.
    let live: Bool
    /// Все копии сейва - те же байты в других контейнерах. В списке
    /// они сведены в одну строку, и без этого не видно, где ещё лежит.
    var copies: (LibraryItem) -> [URL] = { _ in [] }
    var onSave: (LibraryItem) -> Void = { _ in }
    var onCompare: (LibraryItem) -> Void = { _ in }
    var canCompare: (LibraryItem) -> Bool = { _ in false }
    /// Показать копии отдельным окошком - в общий интерфейс это
    /// вписывать незачем, смотрят их редко.
    var onCopies: (LibraryItem) -> Void = { _ in }

    @Environment(\.palette) private var palette

    var body: some View {
        ScrollViewReader { scroller in
            list.onChange(of: picked.last) { _, target in
                // Выделение, уехавшее за край, надо догнать - иначе
                // листание стрелками выглядит так, будто ничего не делает.
                guard let target else { return }
                withAnimation(.easeOut(duration: 0.12)) {
                    scroller.scrollTo(target, anchor: .center)
                }
            }
        }
    }

    private var list: some View {
        ScrollView {
            // Одна колонка: карточка с иконкой, подписью и временем.
            // Второй столбец съедал место у разбора.
            LazyVStack(spacing: 8) {
                ForEach(items) { item in
                    tile(item)
                }
            }
            .padding(.vertical, 12)
            .padding(.horizontal, 14)
        }
    }

    private func tile(_ item: LibraryItem) -> some View {
        let on = picked.contains(item.id)
        let inBasket = basket.contains(item)
        return Button {
            onChoose(item, NSEvent.modifierFlags.contains(.command))
        } label: {
            HStack(alignment: .top, spacing: 11) {
                IconView(block: item.save.blocks[0], key: item.fingerprint, side: 46)
                VStack(alignment: .leading, spacing: 3) {
                    Text(item.title)
                        .font(.system(size: 12.5, weight: .medium))
                        .foregroundStyle(palette.ink)
                        .lineLimit(1)
                    Text(item.signature.isEmpty ? item.save.name : item.signature)
                        .font(.system(size: 10.5, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    HStack(spacing: 6) {
                        Tag(text: item.info.region, filled: on)
                        if let clock = item.clock {
                            Text(clock)
                                .font(.system(size: 10.5, weight: .medium,
                                              design: .monospaced))
                                .foregroundStyle(palette.accent)
                        }
                        Text("\(item.blocks) \(Basket.blockWord(item.blocks))")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(palette.inkFaint)
                        if inBasket {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 11))
                                .foregroundStyle(palette.accent)
                        }
                    }
                    .padding(.top, 2)
                }
                Spacer(minLength: 0)
            }
            .padding(11)
            .background(palette.tile, in: RoundedRectangle(cornerRadius: 9))
            .overlay {
                RoundedRectangle(cornerRadius: 9)
                    .strokeBorder(on ? palette.accent.opacity(live ? 1 : 0.35)
                                     : palette.tileEdge,
                                  lineWidth: on ? 1.5 : 1)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .contextMenu { menu(item) }
    }

    /// Правая кнопка. Названия те же, что в верхнем меню: разные слова
    /// для одного действия сбивают сильнее, чем отсутствие пункта.
    @ViewBuilder
    private func menu(_ item: LibraryItem) -> some View {
        Button(basket.contains(item)
               ? L.t("Убрать из корзины", "Remove from basket")
               : L.t("Добавить в корзину", "Add to basket")) {
            basket.toggle(item)
        }
        Button(L.t("Сравнить с выделенным", "Compare with selected")) {
            onCompare(item)
        }
        .disabled(!canCompare(item))

        Divider()

        Button(L.t("Сохранить как…", "Save as…")) { onSave(item) }
        Button(L.t("Показать в Finder", "Show in Finder")) {
            guard let url = item.origin else { return }
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
        .disabled(item.origin == nil)

        let others = copies(item)
        Button(others.isEmpty
               ? L.t("Других копий нет", "No other copies")
               : L.t("Показать другие копии (\(others.count))",
                     "Show other copies (\(others.count))")) {
            onCopies(item)
        }
        .disabled(others.isEmpty)
    }
}

private struct Tag: View {
    let text: String
    let filled: Bool
    @Environment(\.palette) private var palette

    var body: some View {
        Text(text)
            .font(.system(size: 8.5, weight: .bold))
            .tracking(0.8)
            .foregroundStyle(filled ? palette.accentInk : palette.inkSoft)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background {
                RoundedRectangle(cornerRadius: 3)
                    .fill(filled ? AnyShapeStyle(palette.accent)
                                 : AnyShapeStyle(palette.control))
            }
    }
}
