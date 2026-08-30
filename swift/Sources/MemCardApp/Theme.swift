import SwiftUI

/// Две темы: тёмная — экран карт памяти BIOS, светлая — корпус приставки.
/// Раскладка у них одна, различаются только цвета и материал.
struct Palette {
    let background: LinearGradient
    let bar: LinearGradient
    let barLine: Color
    let panel: Color
    let panelLine: Color
    let tile: LinearGradient
    let tileEdge: Color
    let control: Color
    let controlEdge: Color
    let well: Color
    let ink: Color
    let inkSoft: Color
    let inkFaint: Color
    let accent: Color
    let accentInk: Color
    let iconWell: Color
    let iconWellEdge: Color
    /// Метки игр — четыре цвета логотипа в тёмной теме и четыре значка
    /// с геймпада в светлой.
    let marks: [Color]
    let letterpress: Bool

    static func rgb(_ hex: UInt32) -> Color {
        Color(.sRGB,
              red: Double((hex >> 16) & 0xFF) / 255,
              green: Double((hex >> 8) & 0xFF) / 255,
              blue: Double(hex & 0xFF) / 255)
    }

    static let dark = Palette(
        background: LinearGradient(
            stops: [.init(color: rgb(0x16233F), location: 0),
                    .init(color: rgb(0x0D1526), location: 0.46),
                    .init(color: rgb(0x080C16), location: 1)],
            startPoint: .top, endPoint: .bottom),
        bar: LinearGradient(colors: [rgb(0x1D2E4E), rgb(0x142138)],
                            startPoint: .top, endPoint: .bottom),
        barLine: rgb(0x0A1120),
        panel: rgb(0x090F1B).opacity(0.55),
        panelLine: rgb(0x16233A),
        tile: LinearGradient(colors: [rgb(0x22355A), rgb(0x172742)],
                             startPoint: .top, endPoint: .bottom),
        tileEdge: rgb(0x2C4470),
        control: rgb(0x16243C),
        controlEdge: rgb(0x2A3E5E),
        well: rgb(0x0C1424),
        ink: rgb(0xE8EEF8),
        inkSoft: rgb(0x9FB3D2),
        inkFaint: rgb(0x5C7099),
        accent: rgb(0xF2B705),
        accentInk: rgb(0x08101F),
        iconWell: rgb(0x070C16),
        iconWellEdge: rgb(0x2C4470),
        marks: [rgb(0xF2B705), rgb(0x2E7CD6), rgb(0x2FA84F), rgb(0xE8433F)],
        letterpress: false)

    static let light = Palette(
        background: LinearGradient(colors: [rgb(0xC9C5BB), rgb(0xC9C5BB)],
                                   startPoint: .top, endPoint: .bottom),
        bar: LinearGradient(colors: [rgb(0xD6D2C8), rgb(0xC4C0B6)],
                            startPoint: .top, endPoint: .bottom),
        barLine: rgb(0xA9A69D),
        panel: rgb(0xC3BFB5),
        panelLine: rgb(0xABA79E),
        tile: LinearGradient(colors: [rgb(0xDBD7CD), rgb(0xCAC6BC)],
                             startPoint: .top, endPoint: .bottom),
        tileEdge: rgb(0xABA79E),
        control: rgb(0xDEDAD0),
        controlEdge: rgb(0xABA79E),
        well: rgb(0xBFBBB1),
        ink: rgb(0x2E2C28),
        inkSoft: rgb(0x6B675F),
        inkFaint: rgb(0x7C7870),
        accent: rgb(0xC9A24C),
        accentInk: rgb(0x33301F),
        iconWell: rgb(0x4A4740),
        iconWellEdge: rgb(0x9A968D),
        marks: [rgb(0xC9A24C), rgb(0x5B7BB0), rgb(0x5E9E77), rgb(0xC4636F)],
        letterpress: true)
}

extension EnvironmentValues {
    @Entry var palette: Palette = .dark
}

extension View {
    /// Гравировка по пластику — только в светлой теме, где есть что гравировать.
    @ViewBuilder
    func etched(_ palette: Palette) -> some View {
        if palette.letterpress {
            shadow(color: .white.opacity(0.7), radius: 0, x: 0, y: 1)
        } else {
            self
        }
    }
}
