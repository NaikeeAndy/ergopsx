// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MemCardSaver",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "MemCardKit", targets: ["MemCardKit"]),
        .executable(name: "memcard", targets: ["memcard"]),
        .executable(name: "MemCardSaver", targets: ["MemCardApp"]),
    ],
    targets: [
        .target(name: "MemCardKit", resources: [.copy("Resources")]),
        .executableTarget(name: "memcard", dependencies: ["MemCardKit"]),
        .executableTarget(name: "MemCardApp", dependencies: ["MemCardKit"]),
        .testTarget(name: "MemCardKitTests", dependencies: ["MemCardKit"]),
    ]
)
