# Creational Patterns

## 1. Overview

Creational patterns deal with **how objects are instantiated** — abstracting the creation logic away from the calling code so that the system is not tightly coupled to specific concrete classes. The four core creational patterns for iOS are: **Factory Method** (a method or type that decides which concrete type to return based on input), **Abstract Factory** (a factory for a family of related objects, enabling swapping the entire family at once), **Builder** (assembles a complex object step-by-step, avoiding a massive initializer), and **Singleton** (ensures exactly one instance exists globally). Each pattern trades off flexibility vs. simplicity — Singleton is the simplest but the hardest to test; Builder is the most explicit but adds boilerplate.

## 2. Simple Explanation

Creational patterns are about ordering from a menu instead of cooking yourself. **Factory Method**: you say "I want a dessert" and the waiter brings you whatever the kitchen's featured dessert is today — you don't specify the exact dish. **Abstract Factory**: you say "I want the Italian menu set" and everything — starter, main, dessert — comes from Italian cuisine. Swap to "French set" and the entire family changes. **Builder**: you custom-order a burger: first choose the bun, then the patty, then the toppings, then confirm. The builder assembles it step by step. **Singleton**: there's only one head chef in the kitchen — everyone sends orders to the same person.

## 3. Deep iOS Knowledge

### Factory Method

A factory method is a static method (or a protocol with a factory method) that returns an instance of a protocol type, hiding the concrete class. Enables: switching implementations, creating test doubles, and decoupling call sites from concrete types.

iOS examples: `UITableViewCell.dequeueReusableCell(withIdentifier:)`, `UIStoryboard.instantiateViewController(withIdentifier:)`.

```swift
protocol Analytics { func log(event: String) }
final class FirebaseAnalytics: Analytics { func log(event: String) { /* ... */ } }
final class MockAnalytics: Analytics { func log(event: String) { /* ... */ } }

enum AnalyticsFactory {
    static func make() -> Analytics {
        #if DEBUG
        return MockAnalytics()
        #else
        return FirebaseAnalytics()
        #endif
    }
}
```

### Abstract Factory

An abstract factory is a protocol (or class) with multiple factory methods — one per product type — forming a family. Switching the factory implementation changes the entire family.

iOS example: creating different UI component families for different app themes or A/B test variants.

```swift
protocol ButtonFactory {
    func makePrimaryButton(title: String) -> UIButton
    func makeSecondaryButton(title: String) -> UIButton
}

final class MaterialButtonFactory: ButtonFactory {
    func makePrimaryButton(title: String) -> UIButton { /* Material style */ UIButton() }
    func makeSecondaryButton(title: String) -> UIButton { UIButton() }
}

final class CupertinoButtonFactory: ButtonFactory {
    func makePrimaryButton(title: String) -> UIButton { /* iOS native style */ UIButton() }
    func makeSecondaryButton(title: String) -> UIButton { UIButton() }
}
```

### Builder

The Builder pattern constructs a complex object incrementally. Swift provides two variants: a **fluent builder** (each setter returns `Self` for method chaining) and a **closure-based builder** (configure a mutable object inside a closure). The closure-based variant is idiomatic in Swift.

iOS examples: `URLComponents`, `URLRequest`, `NSAttributedString`.

```swift
final class NotificationBuilder {
    private var title: String = ""
    private var body: String = ""
    private var sound: UNNotificationSound = .default
    private var badge: NSNumber? = nil
    private var userInfo: [AnyHashable: Any] = [:]

    @discardableResult
    func title(_ title: String) -> Self { self.title = title; return self }

    @discardableResult
    func body(_ body: String) -> Self { self.body = body; return self }

    @discardableResult
    func sound(_ sound: UNNotificationSound) -> Self { self.sound = sound; return self }

    @discardableResult
    func badge(_ count: Int) -> Self { self.badge = NSNumber(value: count); return self }

    @discardableResult
    func userInfo(_ info: [AnyHashable: Any]) -> Self { self.userInfo = info; return self }

    func build() -> UNMutableNotificationContent {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = sound
        content.badge = badge
        content.userInfo = userInfo
        return content
    }
}
```

### Singleton

Singleton ensures a class has exactly one instance. In Swift, `static let` provides thread-safe lazy initialization:

```swift
final class Logger {
    static let shared = Logger()
    private init() {}

    func log(_ message: String) { print("[LOG] \(message)") }
}
```

**Singleton anti-patterns**: global singletons create hidden dependencies, making code hard to test. Prefer dependency injection where possible — inject the singleton as a protocol into types that need it, rather than having them reach for `Logger.shared` directly.

## 4. Practical Usage

```swift
import Foundation
import UserNotifications

// ── Factory Method: View Controller Factory ───────────────────
protocol Screen {}
final class FeedViewController: UIViewController, Screen {}
final class AuthViewController: UIViewController, Screen {}

enum ScreenFactory {
    enum Route { case feed, auth, profile(userID: String) }

    static func make(for route: Route) -> UIViewController {
        switch route {
        case .feed:   return FeedViewController()
        case .auth:   return AuthViewController()
        case .profile(let id): return ProfileViewController(userID: id)
        }
    }
}

// Usage — call site never mentions the concrete class
let vc = ScreenFactory.make(for: .feed)

// ── Abstract Factory: Theme System ────────────────────────────
protocol Theme {
    var primaryColor: UIColor { get }
    var font: UIFont { get }
    func makeButton(title: String) -> UIButton
}

final class DarkTheme: Theme {
    var primaryColor: UIColor { .systemIndigo }
    var font: UIFont { .systemFont(ofSize: 16, weight: .semibold) }

    func makeButton(title: String) -> UIButton {
        let b = UIButton(type: .system)
        b.setTitle(title, for: .normal)
        b.backgroundColor = primaryColor
        return b
    }
}

final class LightTheme: Theme {
    var primaryColor: UIColor { .systemBlue }
    var font: UIFont { .systemFont(ofSize: 16) }

    func makeButton(title: String) -> UIButton {
        let b = UIButton(type: .system)
        b.setTitle(title, for: .normal)
        b.tintColor = primaryColor
        return b
    }
}

// Inject the factory — swap entire theme without touching UI code
final class SettingsViewController: UIViewController {
    private let theme: Theme

    init(theme: Theme) {
        self.theme = theme
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        let saveButton = theme.makeButton(title: "Save")
        view.addSubview(saveButton)
    }
}

// ── Builder: URLRequest builder ───────────────────────────────
final class RequestBuilder {
    private var url: URL
    private var method: String = "GET"
    private var headers: [String: String] = [:]
    private var body: Data? = nil

    init(url: URL) { self.url = url }

    @discardableResult
    func method(_ method: String) -> Self { self.method = method; return self }

    @discardableResult
    func header(_ key: String, _ value: String) -> Self { headers[key] = value; return self }

    @discardableResult
    func jsonBody<T: Encodable>(_ value: T) -> Self {
        body = try? JSONEncoder().encode(value)
        headers["Content-Type"] = "application/json"
        return self
    }

    func build() -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        headers.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }
        return request
    }
}

// Usage
let request = RequestBuilder(url: URL(string: "https://api.example.com/posts")!)
    .method("POST")
    .header("Authorization", "Bearer \(token)")
    .jsonBody(newPost)
    .build()

// ── Singleton: App-wide configuration ────────────────────────
final class AppConfiguration {
    static let shared = AppConfiguration()
    private init() {}

    private(set) var apiBaseURL: URL = URL(string: "https://api.example.com")!
    private(set) var featureFlags: [String: Bool] = [:]

    func configure(baseURL: URL, flags: [String: Bool]) {
        apiBaseURL = baseURL
        featureFlags = flags
    }
}

// Testable version: inject as protocol
protocol Configuration {
    var apiBaseURL: URL { get }
    var featureFlags: [String: Bool] { get }
}

extension AppConfiguration: Configuration {}

// In tests:
struct MockConfiguration: Configuration {
    let apiBaseURL = URL(string: "https://mock.api")!
    let featureFlags: [String: Bool] = ["newFeed": true]
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a Factory Method and an Abstract Factory?**

A: A **Factory Method** is a single method that creates one type of product — it encapsulates the `if/else` or `switch` logic that decides which concrete subtype to return. Callers ask for "an Analytics" and receive whichever implementation is appropriate (production vs. test). An **Abstract Factory** is a protocol or class with multiple factory methods, one per product in a family. It ensures that the products it creates are consistent with each other — a `MaterialTheme` factory produces both buttons and text fields in Material style; a `CupertinoTheme` factory produces both in iOS style. Swapping the factory swaps the entire family at once. Use Factory Method when you need to abstract the creation of one type of object; use Abstract Factory when you need to ensure a whole group of related objects are created together consistently.

**Q: What are the disadvantages of the Singleton pattern?**

A: Three main disadvantages: (1) **Hidden dependencies** — code that calls `Logger.shared` has an implicit coupling to the singleton. This is invisible from the function signature and cannot be mocked in unit tests without altering the global. (2) **Global mutable state** — if the singleton holds mutable state, concurrent access requires synchronisation (actor or lock), and state changes from one test or module can affect unrelated code. (3) **Tight coupling to concrete type** — the singleton is always the concrete class; you cannot inject a `MockLogger` for testing unless you redesign the call sites. Mitigation: define the singleton as a protocol (`LoggerProtocol`), inject it into types that need it rather than having them reach for `.shared` directly. The singleton can be the default implementation but the dependency can be swapped in tests.

### Hard

**Q: When should you use a Builder pattern instead of a multi-parameter initializer?**

A: Use Builder when: (1) The object has many optional parameters (more than 3–4) — a 10-parameter initializer is hard to read and call correctly. Builder allows you to set only the parameters you care about and leave others at defaults. (2) Construction requires multiple steps that must occur in a specific order. (3) The same construction process needs to produce different representations (e.g., a JSON query builder that can produce either SQL or GraphQL). For Swift specifically, Builder is less necessary when the type is a `struct` with default values — `URLComponents` uses it because it's an Objective-C type with a mutable API; a Swift `struct` with default parameter values achieves the same result more concisely. Use Builder in Swift primarily when (a) the type is a class with mutability, (b) the fluent interface significantly improves readability at call sites, or (c) you need to validate the combination of parameters at build time (returning `nil` or throwing from `build()`).

**Q: How do you make a Singleton testable?**

A: Two approaches: (1) **Protocol injection**: define a protocol (`AnalyticsProtocol`) that the singleton conforms to. Types that use the singleton take `AnalyticsProtocol` as a dependency in their initializer. In production, pass `Analytics.shared`; in tests, pass a `MockAnalytics`. The singleton still exists globally but the dependency is explicit and swappable. (2) **Static property injection**: expose the shared instance as a settable `static var` (with access control): `static var shared: Analytics = RealAnalytics()`. In test `setUp`, replace it: `Analytics.shared = MockAnalytics()`. Reset in `tearDown`. This is less clean (global mutation) but requires less refactoring of existing call sites. Prefer approach (1) for new code — it makes dependencies explicit and doesn't require global mutation in tests.

### Expert

**Q: Design a ViewController factory for a large app with 50+ screens that supports dependency injection, deep linking, and testability.**

A: Three-component design: (1) **Route enum**: define all app destinations as associated-value cases (`enum Route { case feed; case profile(userID: String); case post(id: String, source: String) }`). This is the single-source-of-truth for navigation destinations — deep link parsing translates URL paths into `Route` cases. (2) **ViewController factory protocol**: `protocol ViewControllerFactory { func makeViewController(for route: Route) -> UIViewController }`. The concrete factory holds references to all app-level dependencies (`struct AppDependencies { let networkService: NetworkServiceProtocol; let database: DatabaseProtocol; ... }`). Each `case` in the factory implementation injects only the dependencies the created VC needs. (3) **Test factory**: `final class MockViewControllerFactory: ViewControllerFactory { var createdRoutes: [Route] = []; func makeViewController(for route: Route) -> UIViewController { createdRoutes.append(route); return UIViewController() } }`. Tests inject the mock factory into the `Coordinator`, assert that navigating to a screen creates the right route. This architecture means: adding a new screen adds one `Route` case and one factory method — no scattered `if` chains at call sites.

## 6. Common Issues & Solutions

**Issue: Builder pattern has many `@discardableResult` annotations and callers forget to call `build()`.**

Solution: Make the intermediate builder type distinct from the final product using a two-type approach: `RequestBuilder` has no `URLRequest` conversion; calling `.build()` returns a `URLRequest`. If callers need a compile-time guarantee, make `RequestBuilder` accept a closure: `RequestBuilder(url:) { builder in builder.method("POST") }` — the closure returns `Void`, and the `URLRequest` is produced internally. Swift's result builder (`@resultBuilder`) can also express this.

**Issue: Factory Method returns `UIViewController` (a concrete class) instead of a protocol, causing import cycles.**

Solution: Define a `Screen` protocol in a shared module that both the factory and the view controllers conform to. The factory returns `Screen`, breaking the import cycle. Alternatively, use `any UIViewController` conforming to a protocol in the same module.

## 7. Related Topics

- [Structural Patterns](structural-patterns.md) — Adapter and Facade for wrapping factories
- [Behavioral Patterns](behavioral-patterns.md) — Command for queuing factory-created objects
- [iOS-Specific Patterns](ios-patterns.md) — Dependency Injection as the complement to Factory
- [Dependency Injection](../06-architecture/dependency-injection.md) — injecting factory-created objects
- [Testable Architecture](../11-testing/testable-architecture.md) — test doubles for factories
