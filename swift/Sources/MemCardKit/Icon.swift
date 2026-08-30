import Foundation

/// Иконка сейва: палитра BGR555 по `0x60`, кадры 16×16 по четыре бита
/// на пиксель с `0x80`, по 128 байт на кадр.
public enum Icon {
    public static let size = 16
    static let frameCounts: [UInt8: Int] = [0x11: 1, 0x12: 2, 0x13: 3]

    public struct Color: Sendable, Equatable {
        public let red: UInt8
        public let green: UInt8
        public let blue: UInt8
        public let alpha: UInt8
    }

    /// Шестнадцать цветов BGR555.
    ///
    /// **Цвет с нулевым STP-битом прозрачный, а не чёрный** - без этого
    /// фон иконки заливается чёрным вместо того, чтобы просвечивать.
    public static func palette(_ block: [UInt8]) -> [Color] {
        guard block.count >= 0x80 else { return [] }
        return (0..<16).map { index in
            let lo = block[0x60 + index * 2], hi = block[0x61 + index * 2]
            let red = (lo & 0x1F) << 3
            let green = ((hi & 0x3) << 6) | ((lo & 0xE0) >> 2)
            let blue = (hi & 0x7C) << 1
            let opaque = (red | green | blue | (hi & 0x80)) != 0
            return Color(red: red, green: green, blue: blue,
                         alpha: opaque ? 255 : 0)
        }
    }

    /// Кадры иконки: каждый - 16×16 пикселей построчно.
    public static func frames(_ block: [UInt8]) -> [[[Color]]] {
        guard block.count >= 0x80,
              block[0] == 0x53 || block[0] == 0x73, block[1] == 0x43,
              let count = frameCounts[block[2]],
              block.count >= 0x80 + 128 * count else { return [] }

        let colors = palette(block)
        return (0..<count).map { index in
            let base = 0x80 + 128 * index
            return (0..<size).map { y in
                var row: [Color] = []
                row.reserveCapacity(size)
                for x in 0..<(size / 2) {
                    let packed = block[base + y * 8 + x]
                    row.append(colors[Int(packed & 0xF)])
                    row.append(colors[Int(packed >> 4)])
                }
                return row
            }
        }
    }

    /// Кадры одной лентой RGBA - в таком виде их проще отдать в изображение.
    public static func rgba(_ block: [UInt8]) -> (bytes: [UInt8], width: Int,
                                                  height: Int, count: Int)? {
        let all = frames(block)
        guard !all.isEmpty else { return nil }
        var bytes: [UInt8] = []
        bytes.reserveCapacity(size * size * 4 * all.count)
        for y in 0..<size {
            for frame in all {
                for pixel in frame[y] {
                    bytes.append(pixel.red)
                    bytes.append(pixel.green)
                    bytes.append(pixel.blue)
                    bytes.append(pixel.alpha)
                }
            }
        }
        return (bytes, size * all.count, size, all.count)
    }
}
