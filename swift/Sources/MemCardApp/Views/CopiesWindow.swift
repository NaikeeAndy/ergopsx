import SwiftUI
import MemCardKit

/// Где лежит один и тот же сейв.
///
/// Отдельным окошком, а не строкой в главном окне: смотрят такое редко,
/// а места список занимает много. Сводятся копии по содержимому и имени,
/// так что это буквально те же байты в разных контейнерах.
struct CopiesWindow: View {
    @Environment(AppState.self) private var state
    @Environment(\.colorScheme) private var scheme

    private var palette: Palette { scheme == .dark ? .dark : .light }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let found = state.copiesOf {
                VStack(alignment: .leading, spacing: 3) {
                    Text(found.title)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(palette.ink)
                    Text(found.name)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                }
                .padding(.horizontal, 18)
                .padding(.top, 16)
                .padding(.bottom, 12)

                Divider().overlay(palette.panelLine)

                ScrollView {
                    VStack(spacing: 5) {
                        ForEach(Array(found.paths.enumerated()), id: \.offset) {
                            index, url in
                            row(url, first: index == 0)
                        }
                    }
                    .padding(14)
                }

                Divider().overlay(palette.panelLine)
                Text(L.t("Identical bytes and identical name — the list merges them into one save."))
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkFaint)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 11)
            } else {
                Text(L.t("Nothing to show"))
                    .font(.system(size: 13))
                    .foregroundStyle(palette.inkSoft)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .frame(minWidth: 520, minHeight: 260)
        .background(palette.background)
        .environment(\.palette, palette)
    }

    private func row(_ url: URL, first: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "doc")
                .font(.system(size: 12))
                .foregroundStyle(first ? palette.accent : palette.inkSoft)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(url.lastPathComponent)
                    .font(.system(size: 12.5, weight: .medium))
                    .foregroundStyle(palette.ink)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text(url.deletingLastPathComponent().path
                    .replacingOccurrences(of: NSHomeDirectory(), with: "~"))
                    .font(.system(size: 10.5, design: .monospaced))
                    .foregroundStyle(palette.inkFaint)
                    .lineLimit(1)
                    .truncationMode(.head)
            }
            Spacer(minLength: 8)
            if first {
                // Именно этот файл приложение и читает - остальные
                // считаются его копиями.
                Text(L.t("shown in the list"))
                    .font(.system(size: 10.5))
                    .foregroundStyle(palette.accent)
            }
            Button(L.t("In Finder")) {
                NSWorkspace.shared.activateFileViewerSelecting([url])
            }
            .controlSize(.small)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(palette.tileEdge, lineWidth: 1)
        }
    }
}
