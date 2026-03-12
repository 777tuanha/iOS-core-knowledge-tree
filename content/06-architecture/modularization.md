# Modularization

## 1. Overview

Modularization is the practice of splitting a monolithic iOS app into separate, independently buildable units — **modules** — each owning a well-defined slice of functionality or shared infrastructure. As iOS apps grow, a single-module monolith produces long build times, tight coupling, large teams blocked on each other, and impossible-to-test boundaries. Modularization with Swift Package Manager (SPM) creates hard dependency boundaries, dramatically improves incremental build times, enables parallel development, and makes each module independently testable and releasable.

## 2. Simple Explanation

Imagine a large city where every building is physically connected to every other building — if one building renovates, the whole city is blocked. Modularization is like zoning the city into independent districts (modules): a residential district, a commercial district, a transit hub. Each district has clear boundaries and defined roads in and out (public interfaces). Renovating one district doesn't block the others. The transit hub (shared core) is shared by all districts but owned by nobody.

## 3. Deep iOS Knowledge

### Why Modularize?

| Problem (Monolith) | Solution (Modules) |
|-------------------|--------------------|
| 10-minute full build | Each module builds independently; clean builds hit cache |
| One change breaks unrelated features | Explicit import boundaries; compile errors catch leakage |
| Can't test a feature without the whole app | Feature module has its own test target |
| Large team — merge conflicts everywhere | Teams own separate packages; no shared file churn |
| Feature can't be reused in another app | Module is a standalone package |
| Long Xcode project file | Each module has its own `Package.swift` |

### Module Types

| Type | Description | Examples |
|------|-------------|---------|
| **Feature module** | One user-facing feature, vertical slice (UI + logic) | `FeedFeature`, `AuthFeature`, `ProfileFeature` |
| **Domain module** | Pure business logic, entities, use cases — no UI | `FeedDomain`, `AuthDomain` |
| **Data module** | Networking, persistence, external services | `NetworkKit`, `DatabaseKit` |
| **Core module** | Shared utilities used by all features | `DesignSystem`, `Analytics`, `Logger` |
| **App module** | Top-level app target — wires everything together | The Xcode project `.app` target |

### Layered Architecture

```
┌─────────────────────────────────┐
│           App Target            │  (composition root — wires modules)
├─────────────────────────────────┤
│  Feature Modules                │  FeedFeature  AuthFeature  ProfileFeature
│  (depend on Domain + Core)      │
├─────────────────────────────────┤
│  Domain Modules                 │  FeedDomain  AuthDomain
│  (depend on Data + Core)        │
├─────────────────────────────────┤
│  Data Modules                   │  NetworkKit  DatabaseKit  KeychainKit
│  (depend on Core only)          │
├─────────────────────────────────┤
│  Core Modules                   │  DesignSystem  Analytics  Logger  Extensions
│  (no internal dependencies)     │
└─────────────────────────────────┘
```

Dependencies flow **downward only** — upper layers depend on lower layers; lower layers never import upper layers. Violating this (a Domain importing a Feature) creates circular dependencies that SPM will reject at compile time.

### Swift Package Manager Modularization

Each module is a Swift Package (or a local package referenced from the Xcode project):

```
MyApp/
├── MyApp.xcodeproj
├── Packages/
│   ├── FeedFeature/
│   │   ├── Package.swift
│   │   └── Sources/FeedFeature/
│   ├── NetworkKit/
│   │   ├── Package.swift
│   │   └── Sources/NetworkKit/
│   └── DesignSystem/
│       ├── Package.swift
│       └── Sources/DesignSystem/
└── App/  (main Xcode target)
```

`Package.swift` for a feature module:
```swift
// swift-tools-version:5.9
.package(name: "FeedFeature", products: [
    .library(name: "FeedFeature", targets: ["FeedFeature"])
], dependencies: [
    .package(path: "../NetworkKit"),
    .package(path: "../DesignSystem"),
    .package(path: "../FeedDomain"),
], targets: [
    .target(
        name: "FeedFeature",
        dependencies: ["NetworkKit", "DesignSystem", "FeedDomain"]
    ),
    .testTarget(
        name: "FeedFeatureTests",
        dependencies: ["FeedFeature"]
    )
])
```

### Access Control as Module API

Swift's access control defines a module's public API:
- `public` / `open`: part of the module's API — intentionally visible
- `internal`: implementation detail — invisible to importers
- `private` / `fileprivate`: within the file/type

A tight public API surface reduces coupling and communicates intent. Design modules with minimal public surfaces — expose protocols, not concrete types.

### Module Boundaries and Protocols

At module boundaries, depend on protocols not concrete types:

```swift
// NetworkKit module
public protocol NetworkClientProtocol {
    func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T
}

// FeedDomain module — imports NetworkKit, depends on protocol
import NetworkKit
public class FeedRepository {
    private let client: NetworkClientProtocol
    public init(client: NetworkClientProtocol) { self.client = client }
}
```

The concrete `URLSessionNetworkClient` is an internal implementation detail of `NetworkKit`.

### Monolith vs Modular

| | Monolith | Modular |
|--|---------|---------|
| Build time | Grows linearly | Incremental per-module |
| Team scalability | Difficult (shared files) | Natural (per-module ownership) |
| Feature reuse | Hard (implicit deps) | Easy (explicit imports) |
| Test isolation | Hard | Easy (each module has tests) |
| Initial setup | Low | Higher |
| Complexity | Low | Medium-High |

**Rule**: Start modular as soon as you have 2+ teams or 3+ features with shared code. Don't modularize a solo 1-screen prototype.

### Preview Providers in Modular Apps

Each feature module can provide SwiftUI preview content without depending on the app target:

```swift
// Inside FeedFeature module
#Preview {
    FeedView(viewModel: FeedViewModel(service: MockFeedService()))
}
```

`MockFeedService` lives in the feature module's test utilities, making previews self-contained.

## 4. Practical Usage

```swift
// ─────────────────────────────────────────────────────────────
// NetworkKit — Core data module
// Package.swift targets: NetworkKit, NetworkKitMocks
// ─────────────────────────────────────────────────────────────

// Sources/NetworkKit/NetworkClientProtocol.swift
import Foundation

public protocol NetworkClientProtocol {
    func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T
}

// Sources/NetworkKit/URLSessionNetworkClient.swift
import Foundation

public final class URLSessionNetworkClient: NetworkClientProtocol {
    private let session: URLSession
    private let decoder: JSONDecoder

    public init(session: URLSession = .shared, decoder: JSONDecoder = .init()) {
        self.session = session
        self.decoder = decoder
    }

    public func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T {
        let (data, _) = try await session.data(from: url)
        return try decoder.decode(T.self, from: data)
    }
}

// Sources/NetworkKitMocks/MockNetworkClient.swift   (test helper, separate target)
import NetworkKit

public final class MockNetworkClient: NetworkClientProtocol {
    public var stubbedData: Any?
    public var stubbedError: Error?
    public init() {}

    public func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T {
        if let error = stubbedError { throw error }
        return stubbedData as! T
    }
}

// ─────────────────────────────────────────────────────────────
// FeedDomain — Domain module
// ─────────────────────────────────────────────────────────────

// Sources/FeedDomain/FeedPost.swift
public struct FeedPost: Identifiable, Decodable, Equatable {
    public let id: Int
    public let title: String
    public let body: String
    public init(id: Int, title: String, body: String) {
        self.id = id; self.title = title; self.body = body
    }
}

// Sources/FeedDomain/FeedRepositoryProtocol.swift
public protocol FeedRepositoryProtocol {
    func fetchPosts() async throws -> [FeedPost]
}

// Sources/FeedDomain/FeedRepository.swift
import NetworkKit

public final class FeedRepository: FeedRepositoryProtocol {
    private let client: NetworkClientProtocol

    public init(client: NetworkClientProtocol) { self.client = client }

    public func fetchPosts() async throws -> [FeedPost] {
        let url = URL(string: "https://jsonplaceholder.typicode.com/posts")!
        return try await client.fetch([FeedPost].self, from: url)
    }
}

// ─────────────────────────────────────────────────────────────
// FeedFeature — Feature module (UI layer)
// ─────────────────────────────────────────────────────────────

import SwiftUI
import FeedDomain

@MainActor
public final class FeedViewModel: ObservableObject {
    @Published public private(set) var posts: [FeedPost] = []
    @Published public private(set) var isLoading = false

    private let repository: FeedRepositoryProtocol

    public init(repository: FeedRepositoryProtocol) {
        self.repository = repository
    }

    public func onAppear() async {
        isLoading = true
        defer { isLoading = false }
        posts = (try? await repository.fetchPosts()) ?? []
    }
}

public struct FeedView: View {
    @StateObject private var vm: FeedViewModel

    public init(repository: FeedRepositoryProtocol) {
        _vm = StateObject(wrappedValue: FeedViewModel(repository: repository))
    }

    public var body: some View {
        List(vm.posts) { post in
            VStack(alignment: .leading) {
                Text(post.title).font(.headline)
                Text(post.body).font(.subheadline).lineLimit(2)
            }
        }
        .task { await vm.onAppear() }
        .overlay { if vm.isLoading { ProgressView() } }
    }
}

// ─────────────────────────────────────────────────────────────
// App target — composition root
// ─────────────────────────────────────────────────────────────
import FeedFeature
import FeedDomain
import NetworkKit

// @main
struct MyApp: App {
    // Compose dependencies at the root
    private let networkClient = URLSessionNetworkClient()

    var body: some Scene {
        WindowGroup {
            FeedView(repository: FeedRepository(client: networkClient))
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the main motivation for modularizing an iOS app?**

A: The primary motivations are **build time** and **team scalability**. In a monolith, every change triggers a rebuild of all code. With modules, only the changed module and its dependents rebuild — dramatically reducing incremental build times for large codebases. Team scalability: different teams or engineers own separate modules, preventing merge conflicts and allowing parallel development. Additional benefits: modules create hard dependency boundaries (a module cannot accidentally import another), enable independent testing (each module has its own test target), and allow feature reuse across multiple apps.

**Q: What is the difference between a feature module and a core module?**

A: A **feature module** is a vertical slice of a user-facing feature — it contains the UI, ViewModel, and feature-specific logic for one piece of user-visible functionality (e.g., `AuthFeature`, `FeedFeature`). Feature modules depend on domain and core modules but never on other feature modules. A **core module** is horizontal infrastructure shared by all features — utilities, design systems, analytics wrappers, logging, extensions. Core modules have no dependencies on feature or domain modules (they sit at the bottom of the dependency graph). The distinction ensures shared code is only in one place and feature modules remain independent.

### Hard

**Q: How does Swift's access control enforce module API boundaries?**

A: Swift has five access levels: `open`, `public`, `package` (Swift 5.9+), `internal`, and `private`/`fileprivate`. `public` and `open` are the module's public API — visible to any importer. `internal` is the default — visible within the module only, invisible to importers. This means a module author explicitly chooses what becomes API. A `public protocol` defines a contract; a `class` that implements it can remain `internal`, hiding the implementation from consumers. `package` access (Swift 5.9) allows visibility within the same package (across targets in one `Package.swift`) without exposing to external importers — useful for sharing implementation details between related targets like `FeedDomain` and `FeedDomainTests`.

**Q: What are the risks of a poorly designed modular dependency graph?**

A: (1) **Circular dependencies**: Module A imports B, B imports A — SPM rejects this at build time. This usually signals that shared code should be extracted to a common module C. (2) **God modules**: A `CoreKit` that grows to include everything becomes a second monolith — every change rebuilds all dependents. Prefer many small, focused core modules. (3) **Leaked abstractions**: A module exposes internal types (concrete classes instead of protocols) — consumers become tightly coupled to implementation details. (4) **Over-modularization**: Splitting a 5-file feature into 5 modules creates overhead without benefit. Modules should be sized around team ownership and feature boundaries, not individual files. (5) **Diamond dependencies**: A depends on B and C; both B and C depend on D at different versions — SPM resolves this to one version, but incompatible APIs can cause subtle issues.

### Expert

**Q: Design the module structure for a large e-commerce iOS app with 10 features and a team of 15 engineers.**

A: (1) **Core layer** (owned by platform team): `DesignSystem` (UI components, colors, fonts), `NetworkKit` (URLSession wrapper + protocols), `DatabaseKit` (CoreData/SQLite abstraction), `AnalyticsKit` (event tracking protocol + Firebase impl), `AuthKit` (token storage, auth state). (2) **Domain layer** (owned by feature teams): `CatalogDomain`, `CartDomain`, `OrdersDomain`, `UserProfileDomain` — pure business logic, entities, use cases; depend on `NetworkKit` and `DatabaseKit` protocols only. (3) **Feature layer** (owned by squads, one squad per 2–3 features): `CatalogFeature`, `CartFeature`, `CheckoutFeature`, `OrderHistoryFeature`, `ProfileFeature`, `SearchFeature`, `WishlistFeature`, `AuthFeature`, `NotificationsFeature`, `ReviewsFeature`. (4) **App target**: Composition root — imports all feature modules, creates `AppDependencies.live`, passes to root coordinator. Feature flags determine which features are shown. Build time is 2-5 minutes for full clean build but 15-30 seconds for incremental changes in one feature.

## 6. Common Issues & Solutions

**Issue: Circular dependency between two modules.**

Solution: Extract the shared protocol or type into a third module that both depend on. Example: `FeedFeature` and `ProfileFeature` both need `UserModel` — create a `SharedModels` module.

**Issue: Long full clean build even after modularization.**

Solution: Ensure modules don't have excessive transitive dependencies. Profile with `xcodebuild -showBuildTimingSummary`. Consider splitting large modules, improving parallelism by reducing serial dependency chains, and enabling explicit module builds in Xcode.

**Issue: Xcode previews fail in a feature module.**

Solution: The preview tries to instantiate objects that require app-level setup (e.g., environment objects, a database that's not initialised). Move the preview to use mock data from a `TestMocks` target included in the module. Ensure all preview dependencies are self-contained within the feature module.

**Issue: Team confusion about what belongs in a module.**

Solution: Define and document the **one-sentence purpose** for each module. If a piece of code doesn't fit the purpose, it belongs elsewhere. Create a `MODULES.md` at the repo root listing each module, its purpose, its owners, and its allowed dependencies.

## 7. Related Topics

- [Dependency Injection](dependency-injection.md) — DI at module boundaries; composition root in the app target
- [SOLID Principles](solid-principles.md) — SOLID at the module level (SRP, OCP, DIP)
- [MVP & VIPER](mvp-viper.md) — VIPER modules align well with SPM modules
- [The Composable Architecture](tca.md) — TCA features compose across module boundaries
