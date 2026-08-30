import Foundation

/// Размеры, одинаковые для всех карт PS1.
public enum PSX {
    public static let frame = 128
    public static let block = 8192
    public static let slots = 15
    /// Образ карты целиком: заголовочный блок плюс 15 слотов.
    public static let cardSize = block * 16
}

/// Состояние слота из первого байта каталожного фрейма.
public enum SlotState: UInt8, Sendable {
    case free = 0xA0
    case save = 0x51
    case link = 0x52
    case linkEnd = 0x53
    case deleted = 0xA1
    case deletedLink = 0xA2
    case deletedLinkEnd = 0xA3

    /// Начинает ли этот слот цепочку. Удалённые тоже начинают: при удалении
    /// BIOS меняет только байт состояния, данные и имя остаются на месте.
    public var isHead: Bool { self == .save || self == .deleted }

    public var label: String {
        switch self {
        case .free: "free"
        case .save: "save"
        case .link, .linkEnd: "link"
        case .deleted: "deleted"
        case .deletedLink, .deletedLinkEnd: "deleted-link"
        }
    }
}

public enum Region: String, Sendable {
    case america = "BA", europe = "BE", japan = "BI"

    public var label: String {
        switch self {
        case .america: "America"
        case .europe: "Europe"
        case .japan: "Japan"
        }
    }
}

/// Один сейв, вынутый из карты или из одиночного контейнера.
public struct Save: Sendable {
    /// Двадцать байт имени: регион, серийник, идентификатор.
    public let rawName: [UInt8]
    /// Блоки цепочки целиком, в порядке следования по ссылкам.
    public let blocks: [[UInt8]]
    public let slot: Int?
    public let state: SlotState?
    /// Откуда взят - попадает в расклад собранной карты.
    public let origin: String

    public init(rawName: [UInt8], blocks: [[UInt8]], slot: Int? = nil,
                state: SlotState? = nil, origin: String = "") {
        self.rawName = rawName
        self.blocks = blocks
        self.slot = slot
        self.state = state
        self.origin = origin
    }

    /// Удалённые сейвы тоже берём: при удалении BIOS меняет только байт
    /// состояния, поэтому на новой карте такой сейв оживает.
    public var isDeleted: Bool { state == .deleted }

    /// Имя сейва как текст, до первого нуля.
    public var name: String { SaveName(rawName).text }

    /// Все блоки одним куском - так к сейву обращаются разборщики игр.
    public var body: [UInt8] { blocks.flatMap { $0 } }
}


public extension [UInt8] {
    /// Дешёвый отпечаток содержимого - для сведения дублей.
    var fingerprintKey: String {
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in self {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return "\(count):\(String(hash, radix: 16))"
    }
}
