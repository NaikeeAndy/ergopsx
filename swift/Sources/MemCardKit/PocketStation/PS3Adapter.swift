import Foundation
import IOKit
import IOKit.usb

/// Адаптер карт памяти PlayStation 3 CECHZM1 (SCPH-98042) - тот самый,
/// в который вставляется карта PS1 или сам PocketStation.
///
/// Транспорт написан на IOKit, а не на libusb: libusb пришлось бы класть
/// внутрь `.app` и тащить как зависимость, а IOKit есть в системе всегда.
/// Сверялся с тремя независимыми реализациями: `ps3mca-ps1` (libusb),
/// `PS3MemCardAdaptor.cs` из MemcardRex и драйвером PocketStation из MAME.
public enum PS3Adapter {
    /// Sony Corp., PlayStation 3 Memory Card Adaptor.
    public static let vendorID = 0x054C
    public static let productID = 0x02EA

    public struct Device: Sendable, Equatable {
        public let name: String
        public let vendorID: Int
        public let productID: Int
        /// Занят ли драйвером системы. Забрать устройство у чужого драйвера
        /// нельзя, и это видно заранее, а не в момент передачи.
        public let claimed: Bool
    }

    /// Ищет адаптер среди устройств USB.
    ///
    /// Ничего не открывает и прав не спрашивает: это опрос реестра IOKit,
    /// он работает и без разрешения на доступ к устройству. Нужен, чтобы
    /// окно могло честно сказать «адаптер не воткнут», не пугая систему
    /// запросом доступа раньше времени.
    public static func find() -> [Device] {
        guard let matching = IOServiceMatching(kIOUSBDeviceClassName) else {
            return []
        }
        var iterator: io_iterator_t = 0
        guard IOServiceGetMatchingServices(kIOMainPortDefault, matching,
                                           &iterator) == KERN_SUCCESS else {
            return []
        }
        defer { IOObjectRelease(iterator) }

        var found: [Device] = []
        while case let service = IOIteratorNext(iterator), service != 0 {
            defer { IOObjectRelease(service) }
            guard let vendor = number(service, "idVendor"),
                  let product = number(service, "idProduct"),
                  vendor == vendorID, product == productID else { continue }
            found.append(Device(name: text(service, "USB Product Name")
                                    ?? "PS3 Memory Card Adaptor",
                                vendorID: vendor, productID: product,
                                claimed: number(service, "IOUserClientClass") != nil))
        }
        return found
    }

    public static var isPresent: Bool { !find().isEmpty }

    /// Все устройства USB. Нужно для диагностики: «адаптер не найден» и
    /// «перечисление не работает» выглядят одинаково, а это разные беды.
    /// Пригодится и пользователю - адаптер он воткнёт через переходник,
    /// и надо будет понять, видит ли его система вообще.
    public static func allDevices() -> [Device] {
        guard let matching = IOServiceMatching(kIOUSBDeviceClassName) else {
            return []
        }
        var iterator: io_iterator_t = 0
        guard IOServiceGetMatchingServices(kIOMainPortDefault, matching,
                                           &iterator) == KERN_SUCCESS else {
            return []
        }
        defer { IOObjectRelease(iterator) }
        var found: [Device] = []
        while case let service = IOIteratorNext(iterator), service != 0 {
            defer { IOObjectRelease(service) }
            guard let vendor = number(service, "idVendor"),
                  let product = number(service, "idProduct") else { continue }
            found.append(Device(name: text(service, "USB Product Name") ?? "?",
                                vendorID: vendor, productID: product,
                                claimed: false))
        }
        return found
    }

    private static func number(_ service: io_object_t, _ key: String) -> Int? {
        guard let raw = IORegistryEntryCreateCFProperty(
            service, key as CFString, kCFAllocatorDefault, 0)?
            .takeRetainedValue() else { return nil }
        return (raw as? NSNumber)?.intValue
    }

    private static func text(_ service: io_object_t, _ key: String) -> String? {
        guard let raw = IORegistryEntryCreateCFProperty(
            service, key as CFString, kCFAllocatorDefault, 0)?
            .takeRetainedValue() else { return nil }
        return raw as? String
    }
}
