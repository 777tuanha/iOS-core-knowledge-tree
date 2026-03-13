# Swift Package Manager

## 1. Overview

Swift Package Manager (SPM) is Apple's first-party dependency and build tool, integrated directly into Xcode since Xcode 11. It manages external library dependencies, defines reusable modules through a `Package.swift` manifest, and builds both application targets and standalone packages. SPM uses Git for package distribution — no central registry — and resolves versions according to semantic versioning rules, recording resolutions in `Package.resolved`. For modular app architectures, SPM is the preferred tool: local packages let you split an app into feature modules with enforced boundaries while keeping everything in one Xcode workspace. Binary targets allow distribution of closed-source SDKs without CocoaPods.

## 2. Simple Explanation

Swift Package Manager is like a shopping list system for your project. The `Package.swift` manifest is the list: it says which ingredients (libraries) your project needs and which version range is acceptable. SPM goes to the source (GitHub or a local folder) and downloads exactly the right version. The `Package.resolved` file is the receipt — it records exactly which version was actually purchased, so everyone on the team and CI builds use identical versions. Local packages are like growing your own herbs — they're always fresh and you can edit them directly.

## 3. Deep iOS Knowledge

### Package.swift Manifest Structure

A `Package.swift` file declares the package: its name, supported platforms, products (what it exports), targets (what it builds), and dependencies.

```
Package.swift
├── platforms   — minimum OS/Swift versions
├── products    — what this package exposes (.library, .executable, .plugin)
├── dependencies — external packages (remote or local)
└── targets     — buildable units: .target, .testTarget, .binaryTarget, .plugin
    ├── name
    ├── dependencies (other targets or products)
    ├── path (default: Sources/<name>/)
    ├── sources
    ├── resources
    └── swiftSettings
```

### Targets vs Products

| Concept | Description |
|---------|-------------|
| **Target** | A buildable unit — a set of Swift/ObjC/C source files compiled together |
| **Product** | What the package exposes to consumers — a `.library` (static or dynamic) or `.executable` |
| **Dependency** | A remote package URL + version requirement, or a local path |

A package can have multiple targets (e.g., `NetworkKit` + `NetworkKitTests`). A product wraps one or more targets into what consumers import.

### Version Requirements

| Specifier | Syntax | Meaning |
|-----------|--------|---------|
| Exact | `.exact("2.3.1")` | Only 2.3.1 |
| Up to next minor | `.upToNextMinor(from: "2.3.0")` | 2.3.x (patch updates only) |
| Up to next major | `.upToNextMajor(from: "2.0.0")` | 2.x.x (minor + patch) ← default |
| Range | `.range("1.0.0"..<"2.0.0")` | Any 1.x |
| Branch | `.branch("main")` | Tip of branch — not reproducible |
| Commit | `.revision("abc1234")` | Exact commit — reproducible |

**Recommendation**: use `.upToNextMajor` for stable libraries. Use `.upToNextMinor` for libraries with frequent breaking changes at minor versions. Pin with `.exact` only for security-sensitive packages.

### Package.resolved

`Package.resolved` is automatically generated and updated by Xcode. It pins every dependency (including transitive dependencies) to exact versions. **Commit it to source control** for apps — this guarantees reproducible builds. For libraries/SDKs, do NOT commit it (consumers choose their own resolution).

### Local Packages

A local package lives in the repository itself (or at a file path). No versioning — always reflects the current state. Ideal for modularising an app:

```swift
// In app's Package.swift or added via Xcode → File → Add Packages:
.package(path: "../FeatureModules/FeedFeature")
```

In Xcode: drag a folder containing `Package.swift` into the project navigator → the package's targets appear as buildable products.

### Resource Bundles

SPM supports copying resources (images, fonts, JSON, strings files, Core Data models) into a bundle:

```swift
.target(
    name: "DesignSystem",
    resources: [
        .process("Resources/Assets.xcassets"),   // processed by asset catalog compiler
        .copy("Resources/Fonts"),                 // copied verbatim
        .process("Localisation.strings")
    ]
)
```

At runtime, access via `Bundle.module` (generated accessor):
```swift
let image = UIImage(named: "logo", in: .module, compatibleWith: nil)
let url = Bundle.module.url(forResource: "config", withExtension: "json")
```

### Binary Targets

A binary target wraps a pre-built `.xcframework` or checksum-verified remote archive:

```swift
.binaryTarget(
    name: "Analytics",
    url: "https://cdn.example.com/Analytics-2.1.0.zip",
    checksum: "abc123def456..."    // SHA-256 of the zip; verified at download
)
// or local:
.binaryTarget(name: "Analytics", path: "Frameworks/Analytics.xcframework")
```

### Swift Settings and Conditional Compilation

```swift
.target(
    name: "Core",
    swiftSettings: [
        .define("DEBUG_LOGGING", .when(configuration: .debug)),
        .unsafeFlags(["-Xfrontend", "-enable-experimental-feature"])
    ]
)
```

### Plugins

SPM supports two plugin types:
- **Build tool plugin**: generates source code or resources during the build (e.g., SwiftGen, Protobuf).
- **Command plugin**: runs commands on demand (e.g., SwiftFormat, Swift-DocC).

### Dependency Resolution Algorithm

SPM uses a SAT-solver-based algorithm to find a consistent set of versions satisfying all constraints. If two packages require incompatible versions of the same dependency, resolution fails with a "dependency conflict" error. Resolve by: checking if a compatible version range exists, pinning the conflicting package, or using local overrides during debugging.

## 4. Practical Usage

```swift
// ── Package.swift for a multi-module iOS library ──────────────
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AppModules",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        // What consumers can import
        .library(name: "NetworkKit",   targets: ["NetworkKit"]),
        .library(name: "DesignSystem", targets: ["DesignSystem"]),
        .library(name: "FeedFeature",  targets: ["FeedFeature"])
    ],
    dependencies: [
        // Remote packages
        .package(url: "https://github.com/Alamofire/Alamofire.git",
                 .upToNextMajor(from: "5.8.0")),
        .package(url: "https://github.com/groue/GRDB.swift.git",
                 .upToNextMajor(from: "6.0.0")),
        // Local sibling package
        .package(path: "../SharedUtils")
    ],
    targets: [
        // ── NetworkKit ───────────────────────────────────────
        .target(
            name: "NetworkKit",
            dependencies: [
                .product(name: "Alamofire", package: "Alamofire"),
                .product(name: "SharedUtils", package: "SharedUtils")
            ],
            swiftSettings: [
                .define("MOCK_NETWORK", .when(configuration: .debug))
            ]
        ),
        .testTarget(
            name: "NetworkKitTests",
            dependencies: ["NetworkKit"]
        ),

        // ── DesignSystem (with resources) ─────────────────────
        .target(
            name: "DesignSystem",
            resources: [
                .process("Resources/Assets.xcassets"),
                .copy("Resources/Fonts")
            ]
        ),

        // ── FeedFeature (depends on internal modules) ─────────
        .target(
            name: "FeedFeature",
            dependencies: [
                "NetworkKit",
                "DesignSystem",
                .product(name: "GRDB", package: "GRDB.swift")
            ]
        ),
        .testTarget(
            name: "FeedFeatureTests",
            dependencies: ["FeedFeature"]
        ),

        // ── Binary target for closed-source analytics SDK ─────
        .binaryTarget(
            name: "AnalyticsSDK",
            url: "https://cdn.example.com/AnalyticsSDK-3.0.0.zip",
            checksum: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
    ]
)

// ── Accessing resources in a target ──────────────────────────
// In DesignSystem/Sources/DesignSystem/Theme.swift:
import UIKit

public extension UIImage {
    static func dsImage(named name: String) -> UIImage? {
        UIImage(named: name, in: .module, compatibleWith: nil)
    }
}

public extension UIFont {
    static func registerBundleFonts() {
        guard let fontURLs = Bundle.module.urls(forResourcesWithExtension: "ttf", subdirectory: "Fonts")
        else { return }
        fontURLs.forEach { CTFontManagerRegisterFontsForURL($0 as CFURL, .process, nil) }
    }
}

// ── Version pinning for security-sensitive dependency ─────────
// In Package.swift:
// .package(url: "https://github.com/krzyzanowskim/CryptoSwift.git",
//          .exact("1.8.0"))    // pin crypto libraries exactly

// ── Overriding a dependency locally during development ────────
// In Xcode: File → Packages → Edit Package → set to local path
// Or in Package.swift (temporary, don't commit):
// .package(path: "/Users/me/Dev/GRDB.swift")

// ── Checking Bundle.module in tests ──────────────────────────
// In NetworkKitTests target, Bundle.module refers to the test bundle,
// not the NetworkKit bundle. To access NetworkKit resources from tests:
// let bundle = Bundle(for: NetworkKitTests.self)
// let networkKitBundle = Bundle(url: bundle.url(forResource: "NetworkKit_NetworkKit",
//                                                withExtension: "bundle")!)

// ── Conditional compilation from Swift settings ───────────────
#if MOCK_NETWORK
let client: NetworkClient = MockNetworkClient()
#else
let client: NetworkClient = LiveNetworkClient()
#endif
```

## 5. Interview Questions & Answers

### Basic

**Q: What is `Package.resolved` and should it be committed to source control?**

A: `Package.resolved` is a lock file that records the exact version (or commit hash) of every resolved package — including transitive dependencies. It ensures that every developer and every CI build uses identical dependency versions, preventing "works on my machine" bugs caused by version drift. For **app targets**, always commit `Package.resolved` — reproducible builds are critical. For **library/framework targets** intended for distribution, do NOT commit it: consumers will resolve the package against their own dependency graph, and a committed `Package.resolved` in a library can cause conflicts. This is the same convention as `Gemfile.lock` (commit for apps, ignore for gems).

**Q: What is the difference between a SPM target and a product?**

A: A **target** is a build unit — a set of source files compiled together into a module. A **product** is what the package makes available to consumers: a `.library` (wrapping one or more targets) or `.executable`. A package can have many internal targets (e.g., `NetworkKitCore`, `NetworkKitTesting`) and expose only a subset as products (e.g., just `NetworkKit`). Internal targets that are not listed as products are implementation details — consumers cannot import them directly. This is how you enforce encapsulation at the module boundary.

### Hard

**Q: How does SPM resolve version conflicts between transitive dependencies, and what do you do when resolution fails?**

A: SPM uses a SAT-solver-based algorithm: it collects all version constraints from the dependency graph (including transitive dependencies) and finds a set of versions that satisfies all constraints simultaneously. If package A requires `Lib >= 1.0.0` and package B requires `Lib < 1.0.0`, no solution exists and resolution fails with a conflict error. Resolution strategies: (1) Update conflicting packages — often a newer version relaxes its constraint. (2) Check if you can fork and patch one of the dependencies to widen its version range. (3) Use `.package(url:, exact:)` to pin one side of the conflict. (4) For local development, use a local path override via Xcode's "Edit Package" to substitute a modified version. (5) Avoid deep transitive dependency trees by preferring focused packages with few dependencies.

**Q: How do SPM binary targets work and what security guarantee does the checksum provide?**

A: A `.binaryTarget` references either a local `.xcframework` or a remote `.zip` archive containing one. For remote targets, the `checksum` field is a SHA-256 hash of the `.zip` file. When SPM downloads the archive, it hashes the download and compares it to the declared checksum — if they don't match, the build fails. This prevents supply-chain attacks where a malicious actor replaces the file at the URL. The checksum does NOT authenticate the author — it only verifies file integrity. For production use, host the archive on infrastructure you control (your CDN or a pinned S3 URL) rather than relying on the package author's servers. Always verify the checksum from a trusted source (the vendor's release notes or GitHub release) rather than computing it from a download you haven't verified.

### Expert

**Q: How would you structure a large iOS app as a collection of local SPM packages to optimise build times and enforce module boundaries?**

A: The standard approach is a layered package graph: (1) **Core packages** (`FoundationKit`, `NetworkKit`, `DesignSystem`) — no dependencies on feature code; built once and cached. (2) **Domain packages** (`UserDomain`, `FeedDomain`) — depend on Core; contain pure Swift models and use-case protocols. (3) **Feature packages** (`FeedFeature`, `ProfileFeature`) — depend on Domain and Core; contain ViewModels, Views, and coordinators. (4) **App target** — composes feature packages; contains AppDelegate/SceneDelegate and top-level navigation. Each package is a directory with `Package.swift`. All are added to the Xcode workspace via File → Add Local Package. Enforce boundaries via Swift access control: `internal` for package-private types, `public` for API, `package` (Swift 5.9+) for cross-target sharing within a package. Benefits: Xcode caches compiled modules — changing `FeedFeature` doesn't recompile `NetworkKit`. SwiftUI previews in `FeedFeature` have a fast build graph (only its dependencies, not the whole app). The dependency graph is explicit and auditable via `Package.swift`.

## 6. Common Issues & Solutions

**Issue: "no such module" error after adding a local package.**

Solution: The local package's product is not added to the app target's "Frameworks, Libraries, and Embedded Content." In Xcode, select the app target → General → Frameworks → add the product from the local package. Also verify the `Package.swift` lists the target as a product (not just a target).

**Issue: `Bundle.module` crash at runtime — "could not find bundle."**

Solution: `Bundle.module` requires that the package has at least one resource rule (`.process` or `.copy`). If no resources are declared, `Bundle.module` isn't generated. Also verify the resource files are listed in the target's `resources` array — files that aren't listed are excluded from the bundle.

**Issue: SPM resolution fails with "dependency graph is unresolvable."**

Solution: Two dependencies require incompatible versions of the same transitive package. Run `swift package show-dependencies` to visualise the graph. Update both dependencies to versions that agree on the transitive requirement. As a last resort, use a `.package(path:)` local override to modify the conflicting package's version constraint.

**Issue: Build is slow after adding many SPM packages.**

Solution: Ensure packages use `.upToNextMajor` (not `.branch`) — branch dependencies cannot be cached. Pre-build SPM packages using `xcodebuild -resolvePackageDependencies`. Move stable internal code to local packages (Xcode caches compiled modules per-package). Check for packages that re-declare overlapping Swift modules, forcing Xcode to rebuild both.

## 7. Related Topics

- [CocoaPods & Carthage](cocoapods-carthage.md) — alternative managers; migration to SPM
- [XCFrameworks](xcframeworks.md) — binary targets reference `.xcframework`
- [Static Libraries & Dynamic Frameworks](static-dynamic-frameworks.md) — SPM `.library(type: .static/.dynamic)`
- [Modularization](../06-architecture/modularization.md) — local SPM packages as feature/domain module boundaries
