import SwiftUI
import MemCardKit

/// Иконка сейва — та самая, что рисовал BIOS: 16×16, до трёх кадров.
///
/// Кадры переключаются сами, но только когда их больше одного: у
/// однокадровой иконки таймер не заводится.
struct IconView: View {
    let block: [UInt8]
    /// Готовый ключ кэша. Считать хеш заголовка на каждый показ незачем:
    /// у сейва уже есть отпечаток, посчитанный при загрузке.
    let key: String
    var side: CGFloat = 46

    @State private var frame = 0
    @Environment(\.palette) private var palette

    private var frames: [CGImage] { IconView.render(block, key: key) }

    var body: some View {
        let all = frames
        RoundedRectangle(cornerRadius: side * 0.11)
            .fill(palette.iconWell)
            .overlay {
                if let image = all.isEmpty ? nil : all[frame % all.count] {
                    // Без сглаживания: пиксель должен остаться пикселем.
                    Image(image, scale: 1, label: Text(L.t("save icon")))
                        .interpolation(.none)
                        .resizable()
                        .frame(width: side * 0.7, height: side * 0.7)
                }
            }
            .overlay {
                RoundedRectangle(cornerRadius: side * 0.11)
                    .strokeBorder(palette.iconWellEdge, lineWidth: 1)
            }
            .frame(width: side, height: side)
            .task(id: all.count) {
                guard all.count > 1 else { return }
                // BIOS крутил иконку примерно вчетверо медленнее кадра.
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(180))
                    frame &+= 1
                }
            }
    }

    /// Кадры в изображения. Результат кэшируется: список прокручивают,
    /// а декодировать одно и то же по десять раз незачем.
    static func render(_ block: [UInt8], key: String) -> [CGImage] {
        guard block.count >= 0x80 else { return [] }
        if let cached = cache.withLock({ $0[key] }) { return cached }

        let made = Icon.frames(block).compactMap { rows -> CGImage? in
            var bytes: [UInt8] = []
            bytes.reserveCapacity(Icon.size * Icon.size * 4)
            for row in rows {
                for pixel in row {
                    bytes.append(pixel.red)
                    bytes.append(pixel.green)
                    bytes.append(pixel.blue)
                    bytes.append(pixel.alpha)
                }
            }
            guard let provider = CGDataProvider(data: Data(bytes) as CFData) else {
                return nil
            }
            return CGImage(width: Icon.size, height: Icon.size,
                           bitsPerComponent: 8, bitsPerPixel: 32,
                           bytesPerRow: Icon.size * 4,
                           space: CGColorSpaceCreateDeviceRGB(),
                           bitmapInfo: CGBitmapInfo(rawValue:
                               CGImageAlphaInfo.premultipliedLast.rawValue),
                           provider: provider, decode: nil,
                           shouldInterpolate: false, intent: .defaultIntent)
        }
        cache.withLock { $0[key] = made }
        return made
    }

    private static let cache = Mutex<[String: [CGImage]]>([:])
}

/// Крошечная замена ещё не везде доступному `Synchronization.Mutex`.
final class Mutex<Value>: @unchecked Sendable {
    private var value: Value
    private let lock = NSLock()

    init(_ value: Value) { self.value = value }

    func withLock<Result>(_ body: (inout Value) -> Result) -> Result {
        lock.lock()
        defer { lock.unlock() }
        return body(&value)
    }
}
