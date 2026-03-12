# Dependency Injection

## 1. Overview

Dependency Injection (DI) is the practice of supplying an object's dependencies from outside rather than having the object create them internally. It is the primary mechanism for making code testable, composable, and flexible. Instead of `let service = NetworkService()` inside a ViewModel, the ViewModel receives `service: NetworkServiceProtocol` through its initialiser. The caller decides which concrete implementation to provide — a real service in production, a mock in tests. DI underpins all advanced iOS architecture patterns (MVVM, VIPER, TCA) and is the practical implementation of the Dependency Inversion Principle.

## 2. Simple Explanation

Imagine a coffee machine (your ViewModel). A poorly designed machine has a specific brand of beans locked inside — you can't change them. A well-designed machine has a bean compartment (a protocol) — you can put in any brand of beans (any service implementation) from outside. For your morning routine (production), you use real beans. For a demonstration (unit test), you use decaf. The machine's brewing logic is the same; only the beans differ. Dependency Injection is designing the bean compartment.

## 3. Deep iOS Knowledge

### Constructor (Initialiser) Injection

The most recommended form. Dependencies are passed through the initialiser:

```swift
class FeedViewModel {
    private let service: FeedServiceProtocol

    init(service: FeedServiceProtocol) {
        self.service = service   // injected at creation time
    }
}
```

**Advantages**:
- Dependencies are explicit and visible at the call site
- Object is ready to use immediately after `init` — no partially-initialised state
- Compiler enforces that the dependency is provided
- Easiest to test — create the object with a mock

**When to use**: The default choice for all non-trivial dependencies.

### Property Injection

Dependencies are set via a mutable property after initialisation:

```swift
class ArticlePresenter {
    weak var view: ArticleViewProtocol?      // set by VIPER assembler
    var interactor: ArticleInteractorProtocol?  // set by assembler
}
```

**Advantages**: Allows circular references (e.g., VIPER's Presenter ↔ View mutual weak reference).

**Disadvantages**: Object may be used before the dependency is set (partial init). Requires optionals or `!` — introduces potential crashes.

**When to use**: When circular references require it (VIPER assembler pattern) or for `delegate` properties that UIKit manages.

### Method Injection

A dependency is passed as a parameter to the specific method that needs it:

```swift
func formatDate(_ date: Date, using formatter: DateFormatter) -> String {
    formatter.string(from: date)
}
```

**When to use**: When the dependency is needed only for one operation and does not persist. Good for pure utility functions.

### Service Locator

A central registry that resolves dependencies on demand:

```swift
class ServiceLocator {
    static let shared = ServiceLocator()
    private var services: [ObjectIdentifier: Any] = [:]

    func register<T>(_ service: T, for type: T.Type) {
        services[ObjectIdentifier(type)] = service
    }

    func resolve<T>(_ type: T.Type) -> T? {
        services[ObjectIdentifier(type)] as? T
    }
}

// Registration
ServiceLocator.shared.register(NetworkService(), for: FeedServiceProtocol.self)

// Usage
let service = ServiceLocator.shared.resolve(FeedServiceProtocol.self)
```

**Advantages**: Avoids "dependency propagation" — you don't pass dependencies through every layer.

**Disadvantages**:
- Dependencies are hidden (not visible at call site) — a form of global state
- Compile-time safety lost — missing registrations crash at runtime
- Harder to test — tests must set up and tear down the locator

**When to use**: Sparingly, as a fallback for deeply nested dependencies or third-party libraries that can't be refactored.

### DI Containers

A DI container is a more sophisticated service locator with automatic resolution (resolves dependency graphs automatically), lifecycle management (singleton vs transient), and compile-time or registration-time validation.

Popular iOS options:
- **Swinject** — manual registration with graph resolution
- **Needle** — compile-time DI (Uber's internal framework, open-sourced)
- **TCA Dependencies** — TCA's built-in `@Dependency` system
- **Factory** — modern Swift DI framework using property wrappers

### Environment-based DI (SwiftUI)

SwiftUI's `@Environment` and `environmentObject` are a form of DI built into the framework:

```swift
struct ContentView: View {
    @EnvironmentObject var authService: AuthService  // injected by ancestor
}
```

For dependency injection across the app boundary without SwiftUI's environment, create a root `DependencyContainer`:

```swift
struct AppDependencies {
    let networkService: NetworkServiceProtocol
    let authService: AuthServiceProtocol
    let analyticsService: AnalyticsProtocol

    static let live = AppDependencies(
        networkService: URLSessionNetworkService(),
        authService: FirebaseAuthService(),
        analyticsService: FirebaseAnalytics()
    )

    static let mock = AppDependencies(
        networkService: MockNetworkService(),
        authService: MockAuthService(),
        analyticsService: NoOpAnalytics()
    )
}
```

Pass the container to the root coordinator/view and propagate it via constructor injection or `@EnvironmentObject`.

### Testing with DI

The key benefit of DI: unit tests swap real dependencies for fast, deterministic mocks:

```swift
// Production
let vm = FeedViewModel(service: URLSessionFeedService())

// Unit test
let mock = MockFeedService()
mock.stubbedPosts = [Post(id: 1, title: "Test")]
let vm = FeedViewModel(service: mock)
await vm.loadPosts()
XCTAssertEqual(vm.posts.count, 1)
// No network call. Test runs in milliseconds.
```

### Protocol-Driven Design

DI works best with protocols that define the interface. Concrete implementations are swappable:

```swift
protocol AnalyticsProtocol {
    func track(event: String, properties: [String: Any])
}

class FirebaseAnalytics: AnalyticsProtocol {
    func track(event: String, properties: [String: Any]) { /* Firebase */ }
}

class NoOpAnalytics: AnalyticsProtocol {
    func track(event: String, properties: [String: Any]) { /* nothing */ }
}

class ConsoleAnalytics: AnalyticsProtocol {
    func track(event: String, properties: [String: Any]) {
        print("Track: \(event) - \(properties)")
    }
}
```

`NoOpAnalytics` is useful in tests; `ConsoleAnalytics` in debug builds; `FirebaseAnalytics` in production.

## 4. Practical Usage

```swift
import Foundation

// ── Protocols define the contracts ───────────────────────────
protocol NetworkServiceProtocol {
    func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T
}

protocol KeychainServiceProtocol {
    func save(token: String)
    func loadToken() -> String?
}

protocol AnalyticsProtocol {
    func track(_ event: String)
}

// ── Concrete implementations (live) ──────────────────────────
class URLSessionNetworkService: NetworkServiceProtocol {
    func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T {
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(T.self, from: data)
    }
}

class AppKeychainService: KeychainServiceProtocol {
    func save(token: String) { /* Keychain API */ }
    func loadToken() -> String? { /* Keychain API */ return nil }
}

struct FirebaseAnalyticsService: AnalyticsProtocol {
    func track(_ event: String) { print("[Firebase] \(event)") }
}

// ── Dependency Container ──────────────────────────────────────
struct AppDependencies {
    let network: NetworkServiceProtocol
    let keychain: KeychainServiceProtocol
    let analytics: AnalyticsProtocol

    // Production dependencies
    static let live = AppDependencies(
        network: URLSessionNetworkService(),
        keychain: AppKeychainService(),
        analytics: FirebaseAnalyticsService()
    )

    // Test dependencies (all mocks — no network, no Keychain, no analytics calls)
    static let test = AppDependencies(
        network: MockNetworkService(),
        keychain: MockKeychainService(),
        analytics: NoOpAnalytics()
    )
}

// ── ViewModels receive dependencies via constructor injection ──
struct Post: Decodable { let id: Int; let title: String }

@MainActor
final class FeedViewModel: ObservableObject {
    @Published private(set) var posts: [Post] = []
    @Published private(set) var isLoading = false

    // Injected abstractions — not concrete types
    private let network: NetworkServiceProtocol
    private let analytics: AnalyticsProtocol

    init(network: NetworkServiceProtocol, analytics: AnalyticsProtocol) {
        self.network = network
        self.analytics = analytics
    }

    func loadFeed() async {
        isLoading = true
        defer { isLoading = false }
        let url = URL(string: "https://api.example.com/feed")!
        posts = (try? await network.fetch([Post].self, from: url)) ?? []
        analytics.track("feed_loaded")
    }
}

// ── Using the container at the composition root ───────────────
// In AppDelegate / App struct (composition root):
//
// let deps = AppDependencies.live
// let feedVM = FeedViewModel(network: deps.network, analytics: deps.analytics)

// ── Mocks for tests ──────────────────────────────────────────
class MockNetworkService: NetworkServiceProtocol {
    var stubbedResult: Any?
    var stubbedError: Error?

    func fetch<T: Decodable>(_ type: T.Type, from url: URL) async throws -> T {
        if let error = stubbedError { throw error }
        return stubbedResult as! T
    }
}

class MockKeychainService: KeychainServiceProtocol {
    private var token: String?
    func save(token: String) { self.token = token }
    func loadToken() -> String? { token }
}

struct NoOpAnalytics: AnalyticsProtocol {
    func track(_ event: String) { /* intentional no-op in tests */ }
}

// ── Unit test (no network, no Firebase, no Keychain) ─────────
// func testFeedLoadPopulatesPosts() async {
//     let mock = MockNetworkService()
//     mock.stubbedResult = [Post(id: 1, title: "Hello")]
//     let analytics = NoOpAnalytics()
//     let vm = await FeedViewModel(network: mock, analytics: analytics)
//     await vm.loadFeed()
//     let posts = await vm.posts
//     XCTAssertEqual(posts.count, 1)
//     XCTAssertEqual(posts[0].title, "Hello")
// }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is dependency injection and why is it important for testability?**

A: Dependency injection means providing an object's dependencies from outside rather than having it create them internally. Instead of `let service = NetworkService()` in a ViewModel, the ViewModel receives `service: NetworkServiceProtocol` via its `init`. This is important for testability because: unit tests can inject a `MockNetworkService` that returns pre-programmed responses without making real network calls. Tests run in milliseconds, are deterministic, and can simulate error conditions (timeout, 404, 500) that would be hard to reproduce against a real server. Without DI, every test that creates the ViewModel would trigger real networking.

**Q: What is the difference between constructor injection and the service locator pattern?**

A: Constructor injection makes dependencies visible and explicit — you can see what a class needs by reading its `init` signature. The compiler enforces that all dependencies are provided. Service locator hides dependencies — the class calls a global registry at runtime to resolve them. This has several drawbacks: (1) missing registrations crash at runtime, not compile time; (2) a class's dependencies are invisible without reading its implementation; (3) tests must configure the shared locator before each test, introducing shared mutable state. Constructor injection is strongly preferred; service locator is a pragmatic fallback for legacy codebases or deeply nested dependencies.

### Hard

**Q: How do you handle dependency injection in a large app with deeply nested view hierarchies?**

A: Several approaches: (1) **Prop drilling**: pass dependencies through constructors at every level. Simple, explicit, but verbose for deeply nested hierarchies. (2) **Dependency container**: create a root `AppDependencies` struct containing all dependencies; pass it to root coordinators; each coordinator extracts what it needs and passes focused subsets deeper. (3) **SwiftUI environment**: inject shared services via `.environmentObject` at the root and read them with `@EnvironmentObject` anywhere in the tree — avoids prop drilling for genuinely app-wide services. (4) **TCA Dependencies**: `@Dependency` property wrapper accesses a global registry with test overrides, combining convenience and testability. The right choice depends on app architecture — a mix of (2) + (3) works well for most MVVM SwiftUI apps.

**Q: What is the "composition root" and why is it important?**

A: The composition root is the single place in the application where all concrete implementations are assembled and wired together. In iOS, this is typically the `AppDelegate.application(_:didFinishLaunchingWithOptions:)` or the SwiftUI `App.init()`. All `DependencyContainer.live` objects are created here. Everywhere else in the app, code depends only on protocols. The composition root is the only place that knows about concrete types. This is important because: (1) changing a dependency (e.g., switching from Firebase to a different analytics provider) requires only a one-line change in the composition root; (2) in tests, the `TestCase.setUp()` is the test composition root, and it assembles all mocks.

### Expert

**Q: Compare constructor injection, property injection, and method injection — when is each appropriate in iOS?**

A: **Constructor injection**: Use as the default. Dependencies are immutable after `init`, clearly documented in the signature, enforced by the compiler, and easiest to test. Appropriate for all primary dependencies a class needs throughout its lifetime. **Property injection**: Use only when circular references are unavoidable (e.g., VIPER's Presenter needs a weak reference to the View, and the View holds the Presenter) or when UIKit/SwiftUI imposes it (`delegate` is set after `init`). The risk is partial initialisation — the object can be used before the dependency is set. Use `weak var` for delegate-style properties and document when they must be set. **Method injection**: Use for one-off, per-operation dependencies that don't belong to the object's lifetime (a `DateFormatter` parameter to a formatting function, a `Logger` to a utility method). Avoids polluting the class interface with single-use dependencies.

## 6. Common Issues & Solutions

**Issue: ViewModel creates its dependencies internally — untestable.**

Solution: Move dependency creation out of the class. Use constructor injection with a protocol. Create a factory or use the composition root to wire concretions.

**Issue: Service locator crashes in tests because a service wasn't registered.**

Solution: Add a `setUp` method that registers all required services before each test, and a `tearDown` that clears the locator. Or migrate the dependency to constructor injection to eliminate the runtime crash risk.

**Issue: Passing a `DependencyContainer` through 10 layers of initializers — "dependency prop drilling".**

Solution: (1) Use SwiftUI `@EnvironmentObject` for app-wide singletons. (2) Group related dependencies into focused sub-containers passed only to the layer that needs them. (3) Use TCA's `@Dependency` if already using TCA. Avoid passing the full container to every layer — each layer should only receive the dependencies it directly uses.

## 7. Related Topics

- [SOLID Principles](solid-principles.md) — DIP is the principle DI implements
- [MVVM](mvvm.md) — constructor injection for ViewModel services
- [MVP & VIPER](mvp-viper.md) — VIPER assembler as the composition root for a module
- [The Composable Architecture](tca.md) — TCA's @Dependency system
- [Modularization](modularization.md) — DI at module boundaries
