// Рисует иконку приложения: карта памяти PlayStation на подложке.
// Запуск: swift swift/icon/draw.swift <путь.png> <сторона>
import AppKit

let side = CommandLine.arguments.count > 2
    ? Int(CommandLine.arguments[2]) ?? 1024 : 1024
let out = CommandLine.arguments[1]

func rgb(_ hex: UInt32) -> NSColor {
    NSColor(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255, alpha: 1)
}

// Рисуем прямо в битмап нужного размера. NSImage.lockFocus на Retina
// берёт масштаб экрана, и каждый файл выходил вдвое больше заказанного.
guard let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil, pixelsWide: side, pixelsHigh: side,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: side * 4, bitsPerPixel: 32),
    let canvas = NSGraphicsContext(bitmapImageRep: rep) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = canvas
let context = canvas.cgContext
let unit = CGFloat(side) / 1024

// Подложка: скруглённый квадрат по правилам macOS - поля по краям
// и небольшое смещение вниз, иначе иконка кажется больше соседних.
let margin = 100 * unit
let plate = CGRect(x: margin, y: margin,
                   width: CGFloat(side) - margin * 2,
                   height: CGFloat(side) - margin * 2)
let plateShape = CGPath(roundedRect: plate,
                        cornerWidth: 185 * unit, cornerHeight: 185 * unit,
                        transform: nil)
context.saveGState()
context.addPath(plateShape)
context.clip()
let space = CGColorSpaceCreateDeviceRGB()
let sky = CGGradient(colorsSpace: space,
                     colors: [rgb(0x1D2E4E).cgColor, rgb(0x0A1120).cgColor] as CFArray,
                     locations: [0, 1])!
context.drawLinearGradient(sky, start: CGPoint(x: 0, y: plate.maxY),
                           end: CGPoint(x: 0, y: plate.minY), options: [])
context.restoreGState()

// Карта памяти: корпус, скос угла сверху справа - как у настоящей.
let cardWidth = 470 * unit, cardHeight = 560 * unit
let card = CGRect(x: (CGFloat(side) - cardWidth) / 2,
                  y: (CGFloat(side) - cardHeight) / 2 - 8 * unit,
                  width: cardWidth, height: cardHeight)
let bevel = 92 * unit
let body = CGMutablePath()
let radius = 34 * unit
body.move(to: CGPoint(x: card.minX + radius, y: card.minY))
body.addLine(to: CGPoint(x: card.maxX - radius, y: card.minY))
body.addQuadCurve(to: CGPoint(x: card.maxX, y: card.minY + radius),
                  control: CGPoint(x: card.maxX, y: card.minY))
body.addLine(to: CGPoint(x: card.maxX, y: card.maxY - bevel))
body.addLine(to: CGPoint(x: card.maxX - bevel, y: card.maxY))
body.addLine(to: CGPoint(x: card.minX + radius, y: card.maxY))
body.addQuadCurve(to: CGPoint(x: card.minX, y: card.maxY - radius),
                  control: CGPoint(x: card.minX, y: card.maxY))
body.addLine(to: CGPoint(x: card.minX, y: card.minY + radius))
body.addQuadCurve(to: CGPoint(x: card.minX + radius, y: card.minY),
                  control: CGPoint(x: card.minX, y: card.minY))
body.closeSubpath()

context.saveGState()
context.setShadow(offset: CGSize(width: 0, height: -14 * unit),
                  blur: 34 * unit, color: NSColor.black.withAlphaComponent(0.5).cgColor)
context.addPath(body)
context.setFillColor(rgb(0xD8D6CE).cgColor)
context.fillPath()
context.restoreGState()

// Наклейка: тёмное поле, куда на настоящей карте клеили подпись.
context.saveGState()
context.addPath(body)
context.clip()
let label = CGRect(x: card.minX + 46 * unit, y: card.minY + 150 * unit,
                   width: cardWidth - 92 * unit, height: 300 * unit)
context.addPath(CGPath(roundedRect: label, cornerWidth: 16 * unit,
                       cornerHeight: 16 * unit, transform: nil))
context.setFillColor(rgb(0x2A3242).cgColor)
context.fillPath()

// Разъём снизу: восемь контактов.
let pinTop = card.minY + 96 * unit
for index in 0..<8 {
    let step = (cardWidth - 92 * unit) / 8
    let pin = CGRect(x: card.minX + 46 * unit + step * CGFloat(index) + 6 * unit,
                     y: card.minY + 34 * unit,
                     width: step - 12 * unit, height: pinTop - card.minY - 46 * unit)
    context.addPath(CGPath(roundedRect: pin, cornerWidth: 5 * unit,
                           cornerHeight: 5 * unit, transform: nil))
    context.setFillColor(rgb(0xB6B2A6).cgColor)
    context.fillPath()
}
context.restoreGState()

// Четыре значка с геймпада на наклейке - те же цвета, что в теме.
let mark = 74 * unit
// Расстояние от середины до центра значка. Меньше - значки слипаются.
let gap = 108 * unit
let centerX = card.midX, centerY = label.midY
let stroke = 13 * unit

// Треугольник, сверху.
context.setStrokeColor(rgb(0x2FA84F).cgColor)
context.setLineWidth(stroke)
context.setLineJoin(.round)
let tri = CGMutablePath()
let ty = centerY + gap
tri.move(to: CGPoint(x: centerX, y: ty + mark / 2))
tri.addLine(to: CGPoint(x: centerX + mark / 2, y: ty - mark / 2))
tri.addLine(to: CGPoint(x: centerX - mark / 2, y: ty - mark / 2))
tri.closeSubpath()
context.addPath(tri)
context.strokePath()

// Круг, справа.
context.setStrokeColor(rgb(0xE8433F).cgColor)
context.addEllipse(in: CGRect(x: centerX + gap - mark / 2, y: centerY - mark / 2,
                              width: mark, height: mark)
    .insetBy(dx: 3 * unit, dy: 3 * unit))
context.strokePath()

// Крест, снизу.
context.setStrokeColor(rgb(0x2E7CD6).cgColor)
context.setLineCap(.round)
let cy = centerY - gap
context.move(to: CGPoint(x: centerX - mark / 2 + 6 * unit, y: cy - mark / 2 + 6 * unit))
context.addLine(to: CGPoint(x: centerX + mark / 2 - 6 * unit, y: cy + mark / 2 - 6 * unit))
context.move(to: CGPoint(x: centerX + mark / 2 - 6 * unit, y: cy - mark / 2 + 6 * unit))
context.addLine(to: CGPoint(x: centerX - mark / 2 + 6 * unit, y: cy + mark / 2 - 6 * unit))
context.strokePath()

// Квадрат, слева.
context.setStrokeColor(rgb(0xF2B705).cgColor)
context.setLineCap(.butt)
context.addPath(CGPath(roundedRect:
    CGRect(x: centerX - gap - mark / 2 + 3 * unit, y: centerY - mark / 2 + 3 * unit,
           width: mark - 6 * unit, height: mark - 6 * unit),
    cornerWidth: 6 * unit, cornerHeight: 6 * unit, transform: nil))
context.strokePath()

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try! png.write(to: URL(fileURLWithPath: out))
