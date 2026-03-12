# SOLID Principles

## 1. Overview

SOLID is a set of five object-oriented design principles coined by Robert Martin. They guide how to write code that is maintainable, extensible, and testable — code that can be changed without cascading breakage. In iOS, SOLID principles directly shape how to structure ViewModels, services, protocols, and dependency graphs. Violating them produces the familiar problems: Massive View Controllers (SRP violation), fragile networking layers (OCP violation), untestable code (DIP violation).

## 2. Simple Explanation

Think of a well-designed workshop. Each tool has one purpose (SRP — the hammer doesn't also make coffee). You can add new tools without modifying existing ones (OCP — adding a new drill doesn't change the hammer). Any tool of the same category works interchangeably (LSP — one brand of wrench fits the same bolts as another). Each tool has only the interfaces it needs (ISP — the hammer has a grip, not a USB port). You depend on the category "wrench", not a specific brand (DIP — you ask for a wrench, not a Snap-on model 12A).

## 3. Deep iOS Knowledge

### S — Single Responsibility Principle

**"A class should have only one reason to change."**

Each type should own one well-defined responsibility. Common SRP violations in iOS:

- A ViewController that does networking, parsing, navigation, and display.
- A service class that handles both authentication and data formatting.
- A utility struct that validates input AND formats output AND logs events.

**Swift application**:
```swift
// Violation: one class handles auth + formatting + persistence
class UserManager {
    func login() { }
    func formatDisplayName(_ user: User) -> String { "" }
    func saveToKeychain(_ user: User) { }
}

// Better: split into focused types
class AuthService { func login() { } }
struct UserFormatter { func displayName(for user: User) -> String { "" } }
class KeychainStore { func save(_ user: User) { } }
```

### O — Open/Closed Principle

**"Software entities should be open for extension, but closed for modification."**

You should be able to add new behaviour without editing existing code. In Swift: use **protocols** and **composition** to define extension points. New implementations satisfy the protocol without touching existing code.

```swift
// Closed design — adding a new payment method requires editing existing code
class PaymentProcessor {
    func process(method: String) {
        if method == "card" { }
        else if method == "paypal" { }
        // adding crypto requires editing this function
    }
}

// Open/Closed — new payment methods extend without modifying
protocol PaymentMethod { func process() }
class CardPayment: PaymentMethod { func process() { } }
class PayPalPayment: PaymentMethod { func process() { } }
class CryptoPayment: PaymentMethod { func process() { } }  // new — no edits needed

class PaymentProcessor {
    func process(_ method: PaymentMethod) { method.process() }
}
```

### L — Liskov Substitution Principle

**"Subtypes must be substitutable for their base types."**

Any code that uses a base type must work correctly with any of its subtypes. Violations occur when a subclass overrides a method in a way that breaks the superclass's contract — throwing unexpected exceptions, returning invalid values, or requiring preconditions not in the base type.

```swift
// Violation: Square is not a valid substitute for Rectangle
class Rectangle {
    var width: Double
    var height: Double
    init(width: Double, height: Double) { self.width = width; self.height = height }
    func area() -> Double { width * height }
}

class Square: Rectangle {
    override var width: Double {
        didSet { height = width }   // breaks the contract: setting width changes height
    }
}
// Code expecting a Rectangle and setting width/height independently breaks with Square

// Better: use a protocol; Rectangle and Square are separate implementations
protocol Shape { func area() -> Double }
struct Rectangle: Shape {
    let width, height: Double
    func area() -> Double { width * height }
}
struct Square: Shape {
    let side: Double
    func area() -> Double { side * side }
}
```

**iOS application**: Prefer protocols over class inheritance. `UITableViewDataSource` is a good example — any conforming type can be substituted.

### I — Interface Segregation Principle

**"Clients should not be forced to depend on methods they do not use."**

Large protocols that bundle many methods force implementing types to provide stubs for irrelevant methods. Prefer **small, focused protocols** ("role interfaces").

```swift
// Violation: one fat protocol
protocol DataManager {
    func fetchFromNetwork()
    func saveToDatabase()
    func exportToCSV()
    func sendEmail()
}

// Better: four focused protocols
protocol NetworkFetcher { func fetchFromNetwork() }
protocol DatabasePersister { func saveToDatabase() }
protocol CSVExporter { func exportToCSV() }
protocol EmailSender { func sendEmail() }

// Types implement only what they need
class ReportService: NetworkFetcher, CSVExporter {
    func fetchFromNetwork() { }
    func exportToCSV() { }
}
```

**iOS application**: `UITableViewDataSource` and `UITableViewDelegate` are separate protocols — a good example of ISP in UIKit's design. `Codable` is split into `Encodable` and `Decodable`.

### D — Dependency Inversion Principle

**"High-level modules should not depend on low-level modules. Both should depend on abstractions."**

ViewModels (high-level) should not import or instantiate concrete service classes (low-level). Both should depend on protocols. This enables testing with mocks and swapping implementations.

```swift
// Violation: ViewModel depends on concrete URLSession networking class
class FeedViewModel {
    private let service = NetworkService()   // concrete — can't test without network
}

// Better: depend on abstraction
protocol FeedServiceProtocol {
    func fetchPosts() async throws -> [Post]
}

class FeedViewModel {
    private let service: FeedServiceProtocol   // depends on abstraction

    init(service: FeedServiceProtocol) { self.service = service }
}

// Test: inject mock
class MockFeedService: FeedServiceProtocol {
    var stubbedPosts: [Post] = []
    func fetchPosts() async throws -> [Post] { stubbedPosts }
}
```

### Composition Over Inheritance

Prefer composing behaviour via protocols and value types over building deep class hierarchies. Swift's value types and protocol extensions make this natural:

```swift
// Deep inheritance — fragile
class Animal { func breathe() { } }
class Mammal: Animal { func nurse() { } }
class Dog: Mammal { func bark() { } }
class GuideDog: Dog { func guide() { } }

// Composition — each behaviour is a protocol/struct
protocol Breathable { func breathe() }
protocol Barkable { func bark() }
protocol Guidable { func guide() }

struct GuideDog: Breathable, Barkable, Guidable {
    func breathe() { }
    func bark() { }
    func guide() { }
}
```

Protocol extensions provide shared default implementations without inheritance.

## 4. Practical Usage

```swift
import Foundation

// ─────────────────────────────────────────────────────────────
// SOLID applied to a typical iOS service layer
// ─────────────────────────────────────────────────────────────

struct Post: Codable { let id: Int; let title: String }
struct Comment: Codable { let id: Int; let body: String }

// ISP: separate protocols for each data concern
protocol PostFetching { func fetchPosts() async throws -> [Post] }
protocol CommentFetching { func fetchComments(postID: Int) async throws -> [Comment] }
protocol PostCreating { func createPost(title: String) async throws -> Post }

// SRP: one service per concern
class PostService: PostFetching, PostCreating {
    func fetchPosts() async throws -> [Post] {
        // URLSession networking
        []
    }
    func createPost(title: String) async throws -> Post {
        Post(id: 0, title: title)
    }
}

class CommentService: CommentFetching {
    func fetchComments(postID: Int) async throws -> [Comment] { [] }
}

// DIP: ViewModel depends on protocols, not concretions
@MainActor
final class FeedViewModel: ObservableObject {
    @Published private(set) var posts: [Post] = []
    @Published private(set) var isLoading = false

    // Dependencies are abstractions — injectable and mockable
    private let postFetcher: PostFetching
    private let postCreator: PostCreating

    init(postFetcher: PostFetching, postCreator: PostCreating) {
        self.postFetcher = postFetcher
        self.postCreator = postCreator
    }

    func loadPosts() async {
        isLoading = true
        defer { isLoading = false }
        posts = (try? await postFetcher.fetchPosts()) ?? []
    }

    func createPost(title: String) async {
        guard !title.isEmpty else { return }  // SRP: validation in ViewModel
        if let post = try? await postCreator.createPost(title: title) {
            posts.append(post)
        }
    }
}

// OCP: add caching without changing PostService
class CachingPostService: PostFetching {
    private let wrapped: PostFetching
    private var cache: [Post]?

    init(wrapping service: PostFetching) { self.wrapped = service }

    func fetchPosts() async throws -> [Post] {
        if let cached = cache { return cached }   // extend behaviour, no edit to PostService
        let posts = try await wrapped.fetchPosts()
        cache = posts
        return posts
    }
}

// LSP: any PostFetching can substitute for another
let liveService: PostFetching = PostService()
let cachedService: PostFetching = CachingPostService(wrapping: PostService())
// Both work identically as a PostFetching; the ViewModel doesn't care which

// Mock for tests
class MockPostFetcher: PostFetching {
    var stubbedPosts: [Post] = [Post(id: 1, title: "Test")]
    func fetchPosts() async throws -> [Post] { stubbedPosts }
}

class MockPostCreator: PostCreating {
    var createdPost: Post = Post(id: 99, title: "Created")
    func createPost(title: String) async throws -> Post { createdPost }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What does the Single Responsibility Principle mean in practice for an iOS ViewController?**

A: SRP means a ViewController should have one reason to change — one primary responsibility. In practice, its responsibility is **UI lifecycle management**: display data, forward user events, manage its view hierarchy. Everything else is a violation: networking belongs in a service layer, JSON parsing in a model layer, navigation in a Coordinator, and presentation logic in a ViewModel or Presenter. When you find yourself adding a `URLSession` call or a switch statement on a data enum inside a VC, that is an SRP violation. The fix is to extract that logic into a dedicated, focused object.

**Q: What is the Dependency Inversion Principle and why does it matter for testing?**

A: DIP says high-level modules (ViewModels, Presenters) should not depend on concrete low-level modules (URLSession, UserDefaults, a specific third-party library). Both should depend on **abstractions** (protocols). This matters for testing because: if a ViewModel creates `let service = NetworkService()` directly, any test that instantiates the ViewModel makes real network calls — slow, flaky, and environment-dependent. By having `init(service: NetworkServiceProtocol)`, you inject a `MockNetworkService` in tests with controlled, deterministic responses. DIP is what makes protocol-oriented mock injection possible.

### Hard

**Q: Explain the Open/Closed Principle with an iOS example and describe a scenario where its absence caused a bug.**

A: OCP says a type should be open for extension (new functionality added) but closed for modification (existing behaviour unchanged). A common iOS scenario: an analytics service with a `func track(event: String)` that dispatches to a specific analytics provider. When the team adds a second provider, the developer edits `track(event:)` to add an `if/else`. When a third provider arrives, another `if/else`. Each edit risks breaking the existing provider paths, and the method grows without bound. The OCP solution: define `protocol AnalyticsProvider { func track(event: String) }`. The analytics service holds a `[AnalyticsProvider]` array. New providers are added by creating a new type — no changes to existing code. The bug class eliminated: touching existing code for new providers would sometimes break existing provider logic due to variable shadowing or early-return regressions.

**Q: How does composition over inheritance apply to Swift's protocol-oriented design?**

A: Swift is designed around protocols rather than class hierarchies. Instead of `class Button: View: UIResponder: NSObject`, you express behaviour via protocol conformances: `struct RoundedButton: Tappable, Displayable, Accessible`. Protocol extensions provide default implementations, enabling shared behaviour without inheritance. This matters because: (1) multiple protocols can be combined without the diamond-inheritance problem; (2) structs (value types) can participate — not just classes; (3) each protocol can be tested independently; (4) removing a protocol conformance is localised — no superclass methods to worry about. In practice, a SwiftUI `View` conformance, `Identifiable`, `Hashable`, and `Codable` on the same struct is idiomatic Swift composition.

### Expert

**Q: Where does SOLID break down or create over-engineering in a typical iOS app?**

A: (1) **ISP over-applied**: Creating a protocol for every single method (one method per protocol) produces "protocol soup" — dozens of protocols with identical names like `UserFetching`, `UserSaving`, `UserDeleting`. The indirection cost (reading through 10 protocols to understand a service) outweighs the benefit. Group related operations into sensible interfaces. (2) **OCP rigidity**: Applying OCP strictly means never editing a class. But some changes are genuine fixes to wrong behaviour, not extensions. Treating every bug fix as "must not edit" is wrong. OCP applies to *extension points* — places deliberately designed for variation. (3) **DIP over-applied**: Protocol-per-class for every type, including trivial ones, creates a maintenance burden with no testing benefit (e.g., creating a `JSONDecoderProtocol`). Apply DIP at boundaries that matter: at the seam between your code and external systems (networking, persistence, device APIs).

## 6. Common Issues & Solutions

**Issue: Adding a new feature requires editing 5 existing files.**

Solution: Likely an OCP/SRP violation. Identify the extension point, define a protocol for it, and let new features add new implementations rather than editing existing types.

**Issue: Every class in the app imports every other class — tight coupling.**

Solution: DIP violation. Introduce protocols at the boundaries between layers. Use dependency injection (constructor injection) to decouple concrete types. Draw the dependency graph: arrows should point inward (presentation → domain → data), never outward.

**Issue: A class implementing a protocol has 10 stub methods it doesn't use.**

Solution: ISP violation. Split the protocol into smaller, focused protocols. Each class implements only the protocols relevant to its purpose.

## 7. Related Topics

- [Dependency Injection](dependency-injection.md) — the mechanism that enables DIP in practice
- [MVC](mvc.md) — SRP violations that lead to Massive VC
- [MVVM](mvvm.md) — SRP and DIP applied to the presentation layer
- [MVP & VIPER](mvp-viper.md) — VIPER is a direct application of SOLID to iOS modules
- [Modularization](modularization.md) — SOLID at the module level
