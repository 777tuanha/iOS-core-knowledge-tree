# Modular Architecture

## 1. Overview

Modular architecture organises a large iOS codebase into a graph of discrete, independently compilable units (Swift packages or Xcode frameworks) rather than a single monolithic target. Each module owns a specific vertical slice of functionality (a feature) or a horizontal slice (shared infrastructure), exposes a narrow public API, and hides its implementation details. The benefits compound with team size: **build performance** (incremental compilation — only changed modules recompile, not the whole app), **parallel development** (teams work independently on separate modules without merge conflicts in shared files), **testability** (modules can be unit-tested without the full app), **reusability** (a NetworkKit module is used by both the main app and a share extension), and **feature isolation** (a feature module that fails to compile doesn't prevent other features from building). The tradeoffs: higher initial setup cost, cross-module navigation complexity, and risk of premature modularisation creating more friction than value.

## 2. Simple Explanation

Modular architecture is like a city of specialist shops instead of one enormous department store. A bakery (FeatureAuth), a pharmacy (FeatureOnboarding), and a hardware store (CoreNetworking) each have their own staff, inventory, and front door. When the bakery wants bread bags, it buys from a supplier (CoreShared) — it doesn't go through the pharmacy. The city directory (the app target) knows all the shops but doesn't manage their internal operations. If the bakery catches fire, the pharmacy stays open. That's isolation. If you add a new branch of the bakery (iPad target), it reuses the same bread-making equipment (Swift Package) — that's reusability.

## 3. Deep iOS Knowledge

### Module Graph Topology

A well-designed module graph is a directed acyclic graph (DAG). Common layers:

```
┌─────────────────────────────────────────────┐
│                   App Target                 │
│  (thin shell: entry point, DI container)     │
└────────┬───────────────────────┬────────────┘
         │                       │
         ▼                       ▼
┌────────────────┐   ┌────────────────────────┐
│  FeatureAuth   │   │     FeatureFeed         │
│  (login UI,    │   │  (timeline UI,          │
│   sign-up)     │   │   posts, interactions)  │
└───────┬────────┘   └─────────┬──────────────┘
        │                      │
        ▼                      ▼
┌──────────────────────────────────────────────┐
│              CoreNetworking                  │
│  (URLSession, auth token injection,          │
│   retry, error types)                        │
└─────────────────────────────────────────────┘
        │                      │
        ▼                      ▼
┌─────────────────┐  ┌────────────────────────┐
│   CoreData      │  │     CoreUI             │
│  (persistence,  │  │  (design system:       │
│   models)       │  │   colors, fonts,       │
│                 │  │   shared components)   │
└─────────────────┘  └────────────────────────┘
        │
        ▼
┌─────────────────┐
│   CoreFoundation│
│  (extensions,   │
│   utilities,    │
│   no UIKit dep) │
└─────────────────┘
```

**Rules:**
- Feature modules depend on Core modules, never on other Feature modules.
- Core modules never depend on Feature modules.
- No circular dependencies.
- The App target is the only place that knows about all Feature modules (DI wiring).

### Swift Package Manager for Modules

SPM is the preferred tool for modularisation (Xcode 12+). A multi-package monorepo:

```
Packages/
├── CoreNetworking/
│   ├── Package.swift
│   └── Sources/CoreNetworking/
│       ├── NetworkClient.swift
│       └── AuthInterceptor.swift
├── CoreUI/
│   ├── Package.swift
│   └── Sources/CoreUI/
│       └── DesignSystem.swift
├── FeatureAuth/
│   ├── Package.swift
│   └── Sources/FeatureAuth/
│       ├── LoginView.swift
│       └── AuthCoordinator.swift
└── FeatureFeed/
    ├── Package.swift
    └── Sources/FeatureFeed/
        ├── FeedView.swift
        └── FeedViewModel.swift
```

```swift
// Packages/FeatureAuth/Package.swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FeatureAuth",
    platforms: [.iOS(.v16)],
    products: [
        .library(name: "FeatureAuth", targets: ["FeatureAuth"])
    ],
    dependencies: [
        .package(path: "../CoreNetworking"),   // sibling package
        .package(path: "../CoreUI")
    ],
    targets: [
        .target(
            name: "FeatureAuth",
            dependencies: [
                "CoreNetworking",
                "CoreUI"
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "FeatureAuthTests",
            dependencies: ["FeatureAuth"]
        )
    ]
)
```

### Public API Design

Each module exposes only what downstream consumers need. Everything else is `internal` (default in Swift):

```swift
// CoreNetworking — public surface
public protocol NetworkClient: Sendable {
    func send<T: Decodable>(_ request: URLRequest) async throws -> T
}

public struct HTTPError: Error {
    public let statusCode: Int
    public let body: Data?
}

// Internal implementation — not visible outside the module
final class DefaultNetworkClient: NetworkClient, @unchecked Sendable {
    private let session: URLSession
    private let tokenProvider: TokenProvider

    // ...hidden implementation
    func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        // retry, token refresh, error mapping
    }
}

// Factory — the only way to create a NetworkClient from outside the module
public enum NetworkClientFactory {
    public static func make(tokenProvider: TokenProvider) -> any NetworkClient {
        DefaultNetworkClient(session: .shared, tokenProvider: tokenProvider)
    }
}
```

### Cross-Module Navigation

Feature modules cannot import each other (no cycles), so they cannot push to each other's view controllers directly. Solutions:

**Coordinator-based navigation** (preferred):

```swift
// The App target owns all coordinators and wires them together
// Feature modules expose a `Coordinator` type but don't know about sibling features

// FeatureAuth exposes:
public protocol AuthCoordinatorDelegate: AnyObject {
    func authCoordinatorDidAuthenticate(_ coordinator: AuthCoordinator)
}

public final class AuthCoordinator {
    public weak var delegate: AuthCoordinatorDelegate?
    private let navigationController: UINavigationController

    public init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    public func start() {
        let vc = LoginViewController(viewModel: LoginViewModel())
        navigationController.setViewControllers([vc], animated: false)
    }
}

// App target wires:
final class AppCoordinator: AuthCoordinatorDelegate {
    func authCoordinatorDidAuthenticate(_ coordinator: AuthCoordinator) {
        // Start the FeedCoordinator — App target knows both modules
        startFeedCoordinator()
    }
}
```

**URL-based deep linking** (for decoupled navigation):

```swift
// Each module registers its routes in a central router
// The router is in a CoreNavigation module that features depend on

// CoreNavigation module
public protocol RouteHandler: AnyObject {
    func canHandle(url: URL) -> Bool
    func handle(url: URL, from navigationController: UINavigationController)
}

public final class AppRouter {
    private var handlers: [RouteHandler] = []

    public func register(_ handler: RouteHandler) {
        handlers.append(handler)
    }

    public func route(to url: URL, from nav: UINavigationController) -> Bool {
        guard let handler = handlers.first(where: { $0.canHandle(url: url) }) else {
            return false
        }
        handler.handle(url: url, from: nav)
        return true
    }
}

// FeatureFeed registers at startup (via App target):
final class FeedRouteHandler: RouteHandler {
    func canHandle(url: URL) -> Bool {
        url.host == "feed"
    }
    func handle(url: URL, from nav: UINavigationController) {
        nav.pushViewController(FeedViewController(), animated: true)
    }
}
```

### Shared Components (CoreUI / Design System)

```swift
// CoreUI/Sources/CoreUI/DesignSystem.swift
import SwiftUI

// Colours — single source of truth
public extension Color {
    static let brandPrimary = Color("BrandPrimary", bundle: .module)
    static let brandSecondary = Color("BrandSecondary", bundle: .module)
    static let textPrimary = Color(.label)
    static let textSecondary = Color(.secondaryLabel)
}

// Typography
public extension Font {
    static func branded(_ style: Font.TextStyle) -> Font {
        .system(style, design: .default)   // or custom font via UIFontMetrics
    }
}

// Shared button component
public struct PrimaryButton: View {
    let title: String
    let action: () -> Void

    public init(_ title: String, action: @escaping () -> Void) {
        self.title = title
        self.action = action
    }

    public var body: some View {
        Button(action: action) {
            Text(title)
                .font(.branded(.headline))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.brandPrimary)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .accessibilityLabel(title)
    }
}
```

### SDK Design

When packaging a module for external consumption (third-party SDK, internal library consumed by other teams):

**Binary XCFramework** (for proprietary code — source not distributed):
```bash
# Build for simulator and device, then combine
xcodebuild archive -scheme CoreAnalytics -destination "generic/platform=iOS" \
  -archivePath build/CoreAnalytics-iOS.xcarchive SKIP_INSTALL=NO
xcodebuild archive -scheme CoreAnalytics -destination "generic/platform=iOS Simulator" \
  -archivePath build/CoreAnalytics-Simulator.xcarchive SKIP_INSTALL=NO
xcodebuild -create-xcframework \
  -archive build/CoreAnalytics-iOS.xcarchive -framework CoreAnalytics.framework \
  -archive build/CoreAnalytics-Simulator.xcarchive -framework CoreAnalytics.framework \
  -output CoreAnalytics.xcframework
```

**SDK design principles:**
1. **Minimal surface area**: expose only what the consumer needs — hide internals with `internal` or `private`.
2. **Sendable compliance**: all public types crossing module boundaries must be `Sendable` (Swift concurrency requirement).
3. **No transitive dependency leakage**: don't expose third-party types in your public API — wrap them.
4. **Semantic versioning**: major = breaking change, minor = additive, patch = bugfix.
5. **Thread safety guarantees**: document whether callbacks arrive on the main thread or a background thread.

## 4. Practical Usage

```swift
// ── App target: wiring the module graph ──────────────────────
import FeatureAuth
import FeatureFeed
import CoreNetworking
import CoreUI

@main
struct AcmeApp: App {
    // DI container — only the App target knows about all modules
    private let container = DependencyContainer()

    var body: some Scene {
        WindowGroup {
            RootView(container: container)
        }
    }
}

final class DependencyContainer {
    // Shared infrastructure
    lazy var networkClient: any NetworkClient = NetworkClientFactory.make(
        tokenProvider: keychainTokenProvider
    )
    private lazy var keychainTokenProvider = KeychainTokenProvider()

    // Feature coordinators — created on demand
    func makeAuthCoordinator(nav: UINavigationController) -> AuthCoordinator {
        AuthCoordinator(networkClient: networkClient, navigationController: nav)
    }

    func makeFeedCoordinator(nav: UINavigationController) -> FeedCoordinator {
        FeedCoordinator(networkClient: networkClient, navigationController: nav)
    }
}

// ── FeatureAuth/Sources/FeatureAuth/LoginViewModel.swift ──────
// (no import of FeatureFeed — no cross-feature dependency)
import CoreNetworking

@MainActor
public final class LoginViewModel: ObservableObject {
    @Published public var email = ""
    @Published public var password = ""
    @Published public private(set) var isLoading = false

    private let networkClient: any NetworkClient

    public init(networkClient: any NetworkClient) {
        self.networkClient = networkClient
    }

    public func signIn() async {
        isLoading = true
        defer { isLoading = false }
        // Uses CoreNetworking — no knowledge of FeatureFeed
        do {
            let _: AuthResponse = try await networkClient.send(
                URLRequest(url: URL(string: "https://api.acme.com/auth/login")!)
            )
            // Notify delegate (set by App target's AppCoordinator)
        } catch { }
    }
}

struct AuthResponse: Decodable { let token: String }
struct KeychainTokenProvider {}
```

## 5. Interview Questions & Answers

### Basic

**Q: What are the main benefits of modular iOS architecture?**

A: Four primary benefits: (1) **Build performance**: Xcode only recompiles modules that have changed and their dependents. In a monolith, changing a shared utility recompiles the entire app. In a modular setup, changing `CoreNetworking` recompiles `CoreNetworking` and the feature modules that import it — not the design system or unrelated features. With parallel compilation, build times for large apps drop from 10+ minutes to 2–3 minutes. (2) **Team scalability**: separate teams work on separate modules with minimal merge conflicts. A team of 4 working on `FeatureFeed` doesn't need to touch files owned by the `FeatureAuth` team. (3) **Testability**: modules can be unit-tested in isolation. `FeatureAuth` tests can inject mock `NetworkClient` without launching the full app or depending on `FeatureFeed`. (4) **Reuse across targets**: a `CoreNetworking` module is shared between the main app target, the Notification Service Extension, and a Share Extension without duplicating code.

**Q: How do you handle navigation between two feature modules that cannot import each other?**

A: Use either the Coordinator pattern or URL-based routing — both mediated by the App target (which is the only place that can import both feature modules). **Coordinator pattern**: each feature module exposes a `Coordinator` class and a `Delegate` protocol. The feature coordinator calls its delegate when it's done (e.g., `AuthCoordinatorDelegate.authCoordinatorDidAuthenticate`). The App target's `AppCoordinator` implements the delegate and transitions to the next coordinator. The feature module doesn't know what comes next — it only signals that it's finished. **URL routing**: each feature module registers a `RouteHandler` with a `CoreNavigation.AppRouter` (a shared module both features can import). When any module wants to navigate to another feature, it calls `router.route(to: URL(string: "myapp://feed"))` — the router finds the appropriate handler and handles the navigation. This is more decoupled but harder to pass typed data between features.

### Hard

**Q: How do you manage shared dependencies (e.g., a singleton cache, a database) across multiple feature modules without creating global state?**

A: Use a **dependency injection container** owned exclusively by the App target. Feature modules declare their dependencies as protocol types in their `init` methods (constructor injection) — they don't create or own shared instances. The App target creates all shared instances (`URLSession`, Core Data stack, `NSCache`, analytics service) in one `DependencyContainer` and injects the appropriate instances when creating each feature coordinator/view model. Because feature modules depend on protocols (not concrete types), the container can inject real implementations in production and mock implementations in tests. For protocol types that cross module boundaries (e.g., `NetworkClient` defined in `CoreNetworking`, used in `FeatureAuth` and `FeatureFeed`): both feature modules import `CoreNetworking` for the protocol; the App target injects the same `DefaultNetworkClient` instance to both, so they share the same URLSession connection pool and auth token state. No global state — the container is the single owner, passed via init.

**Q: What is the risk of premature modularisation and how do you decide when to modularise?**

A: Premature modularisation creates overhead without benefit: (1) **Cross-module refactoring cost**: renaming a type in a core module requires updating all dependent modules and often a `public` API bump; in a monolith, Xcode's refactor rename handles it in one step. (2) **Boilerplate**: every public type needs explicit `public` access control; internal utilities that don't need sharing still get extracted. (3) **Build system complexity**: `Package.swift` files must be maintained; local package paths break when repo layout changes. (4) **Over-engineering for small teams**: a team of 3 doesn't benefit from parallel compilation or module isolation. Modularise when: (a) build times exceed 5 minutes and slow daily development, (b) the team has ≥ 3 independent workstreams that frequently conflict, (c) code needs to be reused in a second target (extension, watch app, widget) without duplication, or (d) a subsystem needs to be packaged as a binary SDK for external consumption. Start by extracting the most isolated, stable layer first (typically the network or persistence layer) — not feature modules.

### Expert

**Q: Design a modular architecture for a super-app with 20 features developed by 5 independent teams, where features must be composable (a feature can host another feature's UI inline) and independently releasable.**

A: Six-layer design: (1) **Module tiers**: `CoreFoundation` (zero UIKit, pure Swift utilities), `CoreData` (persistence), `CoreNetworking`, `CoreUI` (design system), `CoreNavigation` (routing protocols, no concrete features), then one `Feature<X>` package per feature. (2) **Feature contracts**: each feature module exports a `FeatureXEntry` type conforming to a `FeatureEntry` protocol (defined in `CoreNavigation`): `func makeRootView() -> AnyView` and `func makeCoordinator(nav:) -> Coordinator`. The App target composes features by calling `makeRootView()` — features don't know who hosts them. (3) **Inline embedding**: to embed Feature B inside Feature A's UI (without a direct import), use `CoreNavigation.FeatureRegistry` — a shared registry where features register themselves by ID at startup. Feature A asks the registry for a view by ID: `registry.view(for: "featureB.miniCard")`. The App target registers all feature views at launch. (4) **Independent release via feature flags**: each feature module is a versioned SPM package in a separate Git repo. The main app's `Package.resolved` specifies exact versions. New feature code ships in the binary but behind a feature flag — the flag controls whether the `FeatureXEntry` is registered at startup. (5) **Shared test infrastructure**: a `TestSupport` package (not shipped in production) exports mock implementations of all Core protocols. Each feature's test target depends only on `TestSupport` + the feature under test. (6) **CI per module**: each feature repo has its own GitHub Actions workflow that builds and unit-tests the module independently on every commit. Integration testing (all features combined) runs only in the main app repo on PRs.

## 6. Common Issues & Solutions

**Issue: Adding a new `public` type to a Core module breaks the build in all feature modules.**

Solution: Distinguish between additive and breaking changes. Adding a new `public` type is additive — it cannot break downstream modules (they don't reference it). Breaking changes are: renaming a `public` type or method, changing method signatures, removing a public API. Use semantic versioning: additive changes = minor bump; breaking changes = major bump. For internal API evolution, add a `@available(*, deprecated, renamed: "newName")` annotation before removing the old API — this gives downstream modules time to migrate before the old API is deleted in the next major version.

**Issue: Two feature modules both need the same singleton (e.g., analytics service) but importing the App target from a feature module creates a cycle.**

Solution: The singleton should live in a Core module (e.g., `CoreAnalytics`) that both feature modules can import. The App target creates the concrete implementation and injects it via the DI container. Feature modules depend only on the protocol defined in `CoreAnalytics` — they call `analyticsService.track(...)` without knowing the implementation. If `CoreAnalytics` would create a cycle (it needs something from a Feature module), extract a thinner `CoreAnalyticsProtocol` package that contains only the protocol with no implementation dependencies — both feature modules and `CoreAnalytics` can import it without cycles.

## 7. Related Topics

- [Architecture](../06-architecture/index.md) — MVVM and Clean Architecture within each module
- [Dependency Management](../10-dependency-management/index.md) — SPM package management
- [Testing](../11-testing/index.md) — unit testing modules in isolation with mocks
- [App Distribution — Fastlane & CI/CD](../19-app-distribution/fastlane-cicd.md) — per-module CI pipelines
- [Offline-First Architecture](offline-first-architecture.md) — repository pattern as a module boundary
