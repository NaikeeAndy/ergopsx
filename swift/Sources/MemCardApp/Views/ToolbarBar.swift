import SwiftUI
import MemCardKit

/// Верхняя полоса: слева вид, справа действия над выделенным.
/// Разделов тут нет — они живут в боковом списке.
struct ToolbarBar: View {
    @Binding var search: String
    @Binding var order: SortOrder
    @Binding var sidebar: Bool
    let canBasket: Bool
    let inBasket: Bool
    let onSave: () -> Void
    let onBasket: () -> Void

    @Environment(\.palette) private var palette

    var body: some View {
        HStack(spacing: 12) {
            Button { sidebar.toggle() } label: {
                Image(systemName: "sidebar.leading")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(sidebar ? palette.ink : palette.inkFaint)
                    .frame(width: 28, height: 28)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help(sidebar ? L.t("Hide the list on the left") : L.t("Show the list on the left"))

            Menu {
                ForEach(SortOrder.allCases) { candidate in
                    Button {
                        order = candidate
                    } label: {
                        if order == candidate {
                            Label(candidate.label, systemImage: "checkmark")
                        } else {
                            Text(candidate.label)
                        }
                    }
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 11, weight: .semibold))
                    Text(order.label).font(.system(size: 12.5))
                }
                .foregroundStyle(palette.ink)
            }
            .menuStyle(.borderlessButton)
            .fixedSize()

            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 12))
                    .foregroundStyle(palette.inkFaint)
                TextField(L.t("Search by game or signature"), text: $search)
                    .textFieldStyle(.plain)
                    .font(.system(size: 13))
                    .foregroundStyle(palette.ink)
            }
            .padding(.horizontal, 10)
            .frame(width: 320, height: 30)
            .background(palette.well, in: RoundedRectangle(cornerRadius: 7))
            .overlay {
                RoundedRectangle(cornerRadius: 7)
                    .strokeBorder(palette.controlEdge, lineWidth: 1)
            }

            Spacer(minLength: 8)

            action(L.t("Save as"), symbol: "square.and.arrow.down",
                   filled: false, action: onSave)
                .disabled(!canBasket)
            action(inBasket ? L.t("Remove") : L.t("To basket"),
                   symbol: inBasket ? "minus" : "plus",
                   filled: !inBasket, action: onBasket)
                .disabled(!canBasket)
        }
        .padding(.horizontal, 16)
        .frame(height: 52)
        .background(palette.bar)
    }

    private func action(_ title: String, symbol: String, filled: Bool,
                        action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 7) {
                Image(systemName: symbol).font(.system(size: 11, weight: .semibold))
                Text(title).font(.system(size: 12.5, weight: filled ? .medium : .regular))
            }
            .foregroundStyle(filled ? palette.accentInk : palette.ink)
            .padding(.horizontal, 13)
            .frame(height: 30)
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
}
