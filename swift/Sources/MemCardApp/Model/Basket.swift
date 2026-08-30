import Foundation
import MemCardKit

/// Корзина: то, из чего соберётся карта. Копится по дороге, из любого места.
@MainActor
@Observable
final class Basket {
    private(set) var items: [LibraryItem] = []
    /// Что не влезло или было отброшено - показываем, а не молчим.
    private(set) var note: String?

    var used: Int { items.reduce(0) { $0 + $1.blocks } }
    var free: Int { PSX.slots - used }
    var isEmpty: Bool { items.isEmpty }

    func contains(_ item: LibraryItem) -> Bool {
        items.contains { $0.fingerprint == item.fingerprint }
    }

    func toggle(_ item: LibraryItem) {
        if let index = items.firstIndex(where: { $0.fingerprint == item.fingerprint }) {
            items.remove(at: index)
            note = nil
            return
        }
        add(item)
    }

    func add(_ item: LibraryItem) {
        guard !contains(item) else { return }
        guard item.blocks <= free else {
            note = L.t("\(item.title) занимает \(item.blocks) ", "\(item.title) takes \(item.blocks) ")
                + Basket.blockWord(item.blocks) + L.t(", а свободно \(free)", ", only \(free) free")
            return
        }
        // Игра находит сейв по имени, поэтому двух одинаковых имён на карте
        // быть не должно. Разные сейвы под одним именем выбирать за
        // пользователя нельзя - говорим и не берём.
        if let clash = items.first(where: { $0.save.name == item.save.name }) {
            note = L.t("«\(item.save.name)» уже в корзине — из \(clash.title). ", "\"\(item.save.name)\" is already in the basket — from \(clash.title). ")
                + L.t("Игра различает сейвы по имени, двух одинаковых на карте быть не может", "The game tells saves apart by name; two identical names cannot share a card")
            return
        }
        items.append(item)
        note = nil
    }

    func remove(_ item: LibraryItem) {
        items.removeAll { $0.fingerprint == item.fingerprint }
        note = nil
    }

    func clear() {
        items = []
        note = nil
    }

    /// Раскладка по пятнадцати слотам: у многоблочного сейва видна вся цепочка.
    struct Cell: Identifiable {
        let id: Int
        let item: LibraryItem?
        let isContinuation: Bool
    }

    var layout: [Cell] {
        var cells: [Cell] = []
        for item in items {
            for position in 0..<item.blocks {
                cells.append(Cell(id: cells.count, item: item,
                                  isContinuation: position > 0))
            }
        }
        while cells.count < PSX.slots {
            cells.append(Cell(id: cells.count, item: nil, isContinuation: false))
        }
        return cells
    }

    func build() throws -> CardBuilder.Result {
        try CardBuilder.build(items.map(\.save))
    }

    static func blockWord(_ count: Int) -> String {
        let tail = count % 100
        if (11...14).contains(tail) { return L.t("блоков", "blocks") }
        switch count % 10 {
        case 1: return L.t("блок", "block")
        case 2, 3, 4: return L.t("блока", "blocks")
        default: return L.t("блоков", "blocks")
        }
    }
}
