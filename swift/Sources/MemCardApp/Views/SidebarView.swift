import SwiftUI
import MemCardKit

/// Боковой список — только места, где лежат сейвы.
/// Действия сюда не попадают: они над выделенным, наверху.
struct SidebarView: View {
    let library: Library
    let consoles: [ConsoleProfile]
    @Binding var selection: Selection
    var focus: FocusState<Pane?>.Binding
    let onRight: () -> Void
    let onConsole: (ConsoleProfile) -> Void
    @Environment(\.palette) private var palette

    /// Всё, по чему можно ходить стрелками. Консоли пропущены:
    /// они открывают окно, а не меняют содержимое списка.
    private var targets: [Selection] {
        [.everything, .cards] + library.games.map { .game($0.name) }
    }

    private func move(_ step: Int) {
        guard let index = targets.firstIndex(of: selection) else {
            selection = targets.first ?? .everything
            return
        }
        let next = index + step
        guard targets.indices.contains(next) else { return }
        selection = targets[next]
    }

    var body: some View {
        ScrollViewReader { scroller in
            list
                .onChange(of: selection) { _, target in
                    withAnimation(.easeOut(duration: 0.12)) {
                        scroller.scrollTo(target, anchor: .center)
                    }
                }
                // При возврате из сейвов подводим выбранную игру к глазам:
                // выделение и так стоит, но может быть за краем.
                .onChange(of: focus.wrappedValue) { _, where_ in
                    guard where_ == .sidebar else { return }
                    withAnimation(.easeOut(duration: 0.12)) {
                        scroller.scrollTo(selection, anchor: .center)
                    }
                }
        }
        .focusable()
        .focusEffectDisabled()
        .focused(focus, equals: .sidebar)
        .onKeyPress(.upArrow) { move(-1); return .handled }
        .onKeyPress(.downArrow) { move(1); return .handled }
        // Вправо - к сейвам выбранной игры.
        .onKeyPress(.rightArrow) { onRight(); return .handled }
    }

    private var list: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                group(L.t("COLLECTION")) {
                    row(L.t("All saves"), count: library.games.reduce(0) { $0 + $1.count },
                        mark: palette.marks[0], target: .everything)
                    row(L.t("Card images"), count: library.cardCount,
                        mark: palette.marks[2], target: .cards)
                }

                if !library.games.isEmpty {
                    // Показываем все игры, а не первые сколько-то: коллекция
                    // растёт, и обрезание списка прятало часть безо всякого
                    // признака, что она есть.
                    group(L.t("GAMES · {0}", library.games.count)) {
                        ForEach(Array(library.games.enumerated()),
                                id: \.offset) { index, game in
                            row(game.name, count: game.count,
                                mark: palette.marks[(index + 1) % palette.marks.count],
                                target: .game(game.name))
                        }
                    }
                }

                if !consoles.isEmpty {
                    group(L.t("CONSOLES")) {
                        ForEach(consoles) { profile in
                            Button { onConsole(profile) } label: {
                                HStack(spacing: 9) {
                                    Circle().fill(palette.marks[1])
                                        .frame(width: 7, height: 7)
                                    Text(profile.label)
                                        .font(.system(size: 13))
                                        .foregroundStyle(palette.ink)
                                    Spacer(minLength: 6)
                                    Image(systemName: "arrow.up.forward.square")
                                        .font(.system(size: 10))
                                        .foregroundStyle(palette.inkFaint)
                                }
                                .padding(.horizontal, 8)
                                .frame(height: 29)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .help(L.t("Open in a separate window"))
                        }
                    }
                }

                if !library.skipped.isEmpty {
                    Text(L.t("unreadable: {0}", library.skipped.count))
                        .font(.system(size: 11))
                        .foregroundStyle(palette.inkFaint)
                        .padding(.horizontal, 8)
                }
            }
            .padding(.vertical, 14)
            .padding(.horizontal, 10)
        }
        .background(palette.panel)
    }

    @ViewBuilder
    private func group(_ title: String,
                       @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 9.5, weight: .bold))
                .tracking(1.6)
                .foregroundStyle(palette.inkFaint)
                .padding(.horizontal, 8)
                .padding(.bottom, 5)
            content()
        }
    }

    private func row(_ name: String, count: Int?, mark: Color,
                     target: Selection, round: Bool = false) -> some View {
        let on = selection == target
        return Button { selection = target } label: {
            HStack(spacing: 9) {
                RoundedRectangle(cornerRadius: round ? 3.5 : 2)
                    .fill(mark)
                    .frame(width: 7, height: 7)
                Text(name)
                    .font(.system(size: 13, weight: on ? .semibold : .regular))
                    .foregroundStyle(palette.ink)
                    .lineLimit(1)
                Spacer(minLength: 6)
                if let count {
                    Text("\(count)")
                        .font(.system(size: 10.5, design: .monospaced))
                        .foregroundStyle(palette.inkFaint)
                }
            }
            .padding(.horizontal, 8)
            .frame(height: 29)
            .background {
                if on {
                    // Список, принимающий стрелки, подсвечен ярко, другой -
                    // приглушённо. Иначе не видно, где сейчас клавиатура.
                    let live = focus.wrappedValue == .sidebar
                    RoundedRectangle(cornerRadius: 6)
                        .fill(palette.accent.opacity(live ? 0.30 : 0.10))
                        .overlay {
                            RoundedRectangle(cornerRadius: 6)
                                .strokeBorder(palette.accent,
                                              lineWidth: live ? 1.5 : 0)
                        }
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .id(target)
    }

}
