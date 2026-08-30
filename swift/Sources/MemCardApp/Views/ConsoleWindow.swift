import SwiftUI
import MemCardKit

/// Окно консоли. Отдельное намеренно: с корзиной внизу можно держать
/// коллекцию и консоль открытыми рядом и собирать карту из обоих мест,
/// не переключая режимы.
struct ConsoleWindow: View {
    @Environment(AppState.self) private var state
    @Environment(\.openWindow) private var openWindow
    @Environment(\.colorScheme) private var scheme

    private var palette: Palette { scheme == .dark ? .dark : .light }

    var body: some View {
        VStack(spacing: 0) {
            if let profile = state.openConsole ?? state.consoles.first {
                ConsolesView(profile: profile,
                             collection: state.folders.urls.first,
                             engine: state.library.engine,
                             basket: state.basket,
                             startPath: state.consoleStartPath,
                             onDownloaded: {
                                 // Перечитываем сами: иначе скачанное
                                 // не появится, пока не нажмёшь ⌘R.
                                 Task { await state.rescan() }
                             },
                             onGames: {
                                 state.openGames = profile
                                 openWindow(id: "games")
                             })
            } else {
                Text(L.t("Консоли не настроены", "No consoles configured"))
                    .font(.system(size: 13))
                    .foregroundStyle(palette.inkSoft)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            BasketBar(basket: state.basket)
        }
        .background(palette.background)
        .environment(\.palette, palette)
        .frame(minWidth: 720, minHeight: 560)
    }
}
