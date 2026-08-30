import SwiftUI
import MemCardKit

/// Панель разбора. Занимает всё место справа от списка: сейвы идут одной
/// колонкой, а сюда помещается всё, что движок умеет достать.
struct InspectorView: View {
    let item: LibraryItem?
    let engine: Engine
    @Environment(\.palette) private var palette

    var body: some View {
        ScrollView {
            if let item {
                content(item)
            } else {
                Text(L.t("Nothing selected"))
                    .font(.system(size: 13))
                    .foregroundStyle(palette.inkSoft)
                    .padding(.top, 40)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(palette.panel)
    }

    @ViewBuilder
    private func content(_ item: LibraryItem) -> some View {
        let digest = Digest.of(item, engine: engine)
        VStack(alignment: .leading, spacing: 18) {
            head(item, digest: digest)

            grid([(L.t("Serial"), item.info.serial),
                  (L.t("Region"), item.info.region),
                  (L.t("Blocks"), String(item.blocks)),
                  (L.t("Save name"), item.save.name)])

            if let digest {
                if !digest.fields.isEmpty {
                    divider
                    heading(digest.game)
                    grid(digest.fields.map { ($0.label, $0.value) })
                }

                if !digest.members.isEmpty {
                    divider
                    heading("\(digest.membersTitle) · \(digest.members.count)")
                    VStack(spacing: 8) {
                        ForEach(digest.members) { member($0) }
                    }
                }

                ForEach(digest.sections.filter { !$0.items.isEmpty }) { section in
                    divider
                    heading(section.note.isEmpty
                            ? section.title
                            : "\(section.title) · \(section.note)")
                    columns(section.items)
                }
            } else {
                divider
                Text(L.t("No detailed parser for this game — only the basics are shown: game, region, signature and icon."))
                    .font(.system(size: 12.5))
                    .foregroundStyle(palette.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let origin = item.origin {
                divider
                HStack(spacing: 10) {
                    Text(origin.lastPathComponent)
                        .font(.system(size: 11.5, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Spacer(minLength: 8)
                    Button(L.t("Show in Finder")) {
                        NSWorkspace.shared.activateFileViewerSelecting([origin])
                    }
                    .controlSize(.small)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func head(_ item: LibraryItem, digest: Digest?) -> some View {
        HStack(spacing: 14) {
            IconView(block: item.save.blocks[0], key: item.fingerprint, side: 64)
            VStack(alignment: .leading, spacing: 4) {
                Text(item.title)
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(palette.ink)
                    .lineLimit(2)
                if !item.signature.isEmpty {
                    Text(item.signature)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 0)
        }
    }

    private var divider: some View {
        Rectangle().fill(palette.panelLine).frame(height: 1)
    }

    private func heading(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9.5, weight: .bold))
            .tracking(1.6)
            .foregroundStyle(palette.inkFaint)
    }

    /// Сводка в несколько колонок - на широкой панели столбик из двух
    /// значений выглядел бы нелепо.
    private func grid(_ pairs: [(String, String)]) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 210, maximum: 340),
                                     spacing: 14, alignment: .leading)],
                  alignment: .leading, spacing: 8) {
            ForEach(Array(pairs.enumerated()), id: \.offset) { _, pair in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(pair.0)
                        .font(.system(size: 12))
                        .foregroundStyle(palette.inkSoft)
                    Spacer(minLength: 4)
                    Text(pair.1.isEmpty ? "—" : pair.1)
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(palette.ink)
                        .multilineTextAlignment(.trailing)
                }
            }
        }
    }

    /// Списки - плотными колонками: инвентарь на две сотни позиций
    /// в один столбец не читается.
    private func columns(_ items: [Digest.Field]) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180, maximum: 300),
                                     spacing: 12, alignment: .leading)],
                  alignment: .leading, spacing: 5) {
            ForEach(items) { entry in
                HStack(spacing: 6) {
                    Text(entry.label)
                        .font(.system(size: 11.5))
                        .foregroundStyle(palette.ink)
                        .lineLimit(1)
                    Spacer(minLength: 4)
                    if !entry.value.isEmpty {
                        Text(entry.value)
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(palette.inkSoft)
                    }
                }
            }
        }
    }

    private func member(_ member: Digest.Member) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 9) {
                Text(member.name)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.ink)
                Text(member.role)
                    .font(.system(size: 12))
                    .foregroundStyle(palette.inkSoft)
                    .lineLimit(1)
                Spacer(minLength: 6)
                if !member.level.isEmpty {
                    Text(L.t("lv. ") + member.level)
                        .font(.system(size: 11.5, design: .monospaced))
                        .foregroundStyle(palette.ink)
                }
            }

            if !member.stats.isEmpty {
                HStack(spacing: 12) {
                    ForEach(member.stats) { stat in
                        HStack(spacing: 4) {
                            Text(stat.label)
                                .font(.system(size: 10.5))
                                .foregroundStyle(palette.inkFaint)
                            Text(stat.value)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(palette.inkSoft)
                        }
                    }
                    Spacer(minLength: 0)
                }
            }

            if !member.gear.isEmpty {
                Text(member.gear.joined(separator: " · "))
                    .font(.system(size: 11))
                    .foregroundStyle(palette.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !member.extra.isEmpty {
                Text(member.extra)
                    .font(.system(size: 10.5))
                    .foregroundStyle(palette.inkFaint)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(palette.tileEdge, lineWidth: 1)
        }
    }
}
