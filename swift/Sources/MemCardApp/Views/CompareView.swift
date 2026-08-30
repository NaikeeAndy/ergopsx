import SwiftUI
import MemCardKit

/// Сравнение двух сейвов: раскрывается только то, что менялось.
struct CompareView: View {
    let left: LibraryItem
    let right: LibraryItem
    let engine: Engine
    let onClose: () -> Void

    @Environment(\.palette) private var palette
    @State private var open: Set<UUID> = []

    private var diff: Diff { Diff.between(left, right, engine: engine) }

    var body: some View {
        let found = diff
        VStack(spacing: 0) {
            header(found)

            if found.groups.isEmpty {
                VStack(spacing: 8) {
                    Text(L.t("No differences"))
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(palette.ink)
                    Text(L.t("The saves match on every field we read"))
                        .font(.system(size: 12))
                        .foregroundStyle(palette.inkSoft)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(spacing: 7) {
                        ForEach(found.groups) { group(($0)) }
                    }
                    .padding(16)
                }
            }

            footer(found)
        }
        .frame(width: 900, height: 640)
        .background(palette.background)
    }

    private func header(_ found: Diff) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text(L.t("COMPARISON"))
                    .font(.system(size: 11, weight: .bold))
                    .tracking(1.6)
                    .foregroundStyle(palette.ink)
                Spacer()
                Text(L.t("{0} {1} · {2} match", found.count, L.plural("difference", found.count), found.same))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
            }
            .padding(.horizontal, 16)
            .frame(height: 44)
            .background(palette.bar)

            HStack(spacing: 0) {
                side(left, role: L.t("LEFT"), tint: Palette.rgb(0xC4728A))
                Divider().overlay(palette.panelLine)
                side(right, role: L.t("RIGHT"), tint: Palette.rgb(0x6FBF8B))
            }
            .frame(height: 82)
            Divider().overlay(palette.panelLine)
        }
    }

    private func side(_ item: LibraryItem, role: String, tint: Color) -> some View {
        HStack(spacing: 13) {
            IconView(block: item.save.blocks[0], key: item.fingerprint, side: 46)
            VStack(alignment: .leading, spacing: 3) {
                Text(role)
                    .font(.system(size: 9, weight: .bold))
                    .tracking(1.4)
                    .foregroundStyle(tint)
                Text(item.title)
                    .font(.system(size: 13.5, weight: .semibold))
                    .foregroundStyle(palette.ink)
                    .lineLimit(1)
                Text(item.signature.isEmpty ? item.save.name : item.signature)
                    .font(.system(size: 10.5, design: .monospaced))
                    .foregroundStyle(palette.inkSoft)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 18)
        .frame(maxWidth: .infinity)
        .background(tint.opacity(0.07))
    }

    private func group(_ group: Diff.Group) -> some View {
        let expanded = open.contains(group.id) || open.isEmpty
        return VStack(spacing: 0) {
            Button {
                if open.contains(group.id) { open.remove(group.id) }
                else { open.insert(group.id) }
            } label: {
                HStack(spacing: 11) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(palette.accent)
                        .frame(width: 3, height: 17)
                    Text(group.name)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(palette.ink)
                    Text(group.kind)
                        .font(.system(size: 10.5, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                    Spacer()
                    Text("\(group.rows.count)")
                        .font(.system(size: 10.5, design: .monospaced))
                        .foregroundStyle(palette.inkSoft)
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(palette.inkFaint)
                }
                .padding(.horizontal, 13)
                .padding(.vertical, 10)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if expanded {
                VStack(spacing: 0) {
                    ForEach(group.rows) { row in
                        HStack(alignment: .firstTextBaseline, spacing: 12) {
                            Text(row.label)
                                .font(.system(size: 12))
                                .foregroundStyle(palette.inkSoft)
                                .frame(width: 128, alignment: .leading)
                            Text(row.left)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(Palette.rgb(0xC4728A))
                                .frame(maxWidth: .infinity, alignment: .trailing)
                            Image(systemName: "arrow.right")
                                .font(.system(size: 9))
                                .foregroundStyle(palette.inkFaint)
                            Text(row.right)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(Palette.rgb(0x6FBF8B))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .padding(.horizontal, 13)
                        .padding(.vertical, 6)
                        Divider().overlay(palette.panelLine.opacity(0.6))
                    }
                }
                .padding(.bottom, 4)
            }
        }
        .background(palette.tile, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(palette.tileEdge, lineWidth: 1)
        }
    }

    private func footer(_ found: Diff) -> some View {
        HStack(spacing: 11) {
            legend(Palette.rgb(0xC4728A), L.t("left"))
            legend(Palette.rgb(0x6FBF8B), L.t("right"))
            Spacer()
            Button(L.t("Close"), action: onClose)
                .buttonStyle(.borderedProminent)
        }
        .padding(.horizontal, 16)
        .frame(height: 54)
        .background(palette.panel)
        .overlay(alignment: .top) { Divider().overlay(palette.panelLine) }
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 7) {
            RoundedRectangle(cornerRadius: 2).fill(color).frame(width: 9, height: 9)
            Text(text).font(.system(size: 12)).foregroundStyle(palette.inkSoft)
        }
    }
}
