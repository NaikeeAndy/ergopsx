import Foundation

/// Образ карты памяти: разбор каталога и выемка сейвов по цепочкам блоков.
public struct CardImage: Sendable {
    public let data: [UInt8]
    public let container: Container

    public init?(_ blob: [UInt8]) {
        guard let found = CardContainer.find(blob) else { return nil }
        data = Array(found.data)
        container = found.kind
    }

    /// Каталожный фрейм слота: 128 байт по адресу `128 * (слот + 1)`.
    public func frame(_ slot: Int) -> ArraySlice<UInt8> {
        let start = PSX.frame * (slot + 1)
        guard start + PSX.frame <= data.count else { return [][...] }
        return data[start..<(start + PSX.frame)]
    }

    public func block(_ slot: Int) -> ArraySlice<UInt8> {
        let start = PSX.block * (slot + 1)
        guard start + PSX.block <= data.count else { return [][...] }
        return data[start..<(start + PSX.block)]
    }

    /// Сейвы с проходом по цепочке блоков.
    ///
    /// Блоки многоблочного сейва лежат не обязательно подряд, поэтому идём
    /// по ссылкам, а не по порядку слотов.
    public func saves(origin: String = "") -> [Save] {
        var out: [Save] = []
        for slot in 0..<PSX.slots {
            let head = frame(slot)
            guard let first = head.first,
                  let state = SlotState(rawValue: first), state.isHead else { continue }

            let size = read32(head, at: 4)
            let want = size > 0 ? max(1, Int(size) / PSX.block) : 1

            var chain = [slot]
            var seen: Set<Int> = [slot]
            var current = slot
            while chain.count < want {
                // Ссылка считает от нуля: номер блока минус один.
                let next = Int(read16(frame(current), at: 8))
                guard next != 0xFFFF, next < PSX.slots, !seen.contains(next) else { break }
                current = next
                seen.insert(next)
                chain.append(next)
            }
            guard chain.count == want else { continue }

            let name = Array(head[(head.startIndex + 10)..<(head.startIndex + 30)])
            out.append(Save(rawName: name,
                            blocks: chain.map { Array(block($0)) },
                            slot: slot + 1,
                            state: state,
                            origin: origin.isEmpty
                                ? L.t("slot {0}", slot + 1) : L.t("{0}, slot {1}", origin, slot + 1)))
        }
        return out
    }
}

@inline(__always)
func read16(_ bytes: ArraySlice<UInt8>, at offset: Int) -> UInt16 {
    let i = bytes.startIndex + offset
    guard i + 1 < bytes.endIndex else { return 0 }
    return UInt16(bytes[i]) | (UInt16(bytes[i + 1]) << 8)
}

@inline(__always)
func read32(_ bytes: ArraySlice<UInt8>, at offset: Int) -> UInt32 {
    let i = bytes.startIndex + offset
    guard i + 3 < bytes.endIndex else { return 0 }
    return UInt32(bytes[i]) | (UInt32(bytes[i + 1]) << 8)
        | (UInt32(bytes[i + 2]) << 16) | (UInt32(bytes[i + 3]) << 24)
}
