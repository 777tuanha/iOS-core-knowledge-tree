# Code Smells

## 1. Overview

A code smell is a surface symptom in code that indicates a deeper problem with the design — not a bug, but a signal that the code may be hard to understand, extend, or test. The term was popularised by Martin Fowler and Kent Beck. In iOS and Swift development, the most common smells are: **Long Method** (a function doing too much), **Large Class** (a class with too many responsibilities — the "Massive View Controller" in iOS), **Duplicate Code** (the same logic in multiple places), **Tight Coupling** (a type that directly creates or depends on a concrete implementation rather than an abstraction), **Feature Envy** (a method that is more interested in the data of another class than its own), and **Primitive Obsession** (using raw types like `String`, `Int`, or `Bool` instead of domain-specific value types). Recognizing smells is the first step — the second is applying the appropriate refactoring.

## 2. Simple Explanation

Code smells are like symptoms a doctor looks for: a persistent cough is not the disease itself, but it signals something might be wrong. A very long function (the cough) signals the function might be doing too many things (the disease: violation of single responsibility). Just as a doctor diagnoses from symptoms and prescribes treatment, a developer identifies smells and applies refactoring techniques. Most smells are not emergencies — code with smells usually works fine — but they accumulate and make future changes progressively slower and riskier.

## 3. Deep iOS Knowledge

### Long Method

A method longer than 20–30 lines typically does more than one thing. Signs: multiple blank lines separating "sections", comments above groups of lines (which are often better expressed as extracted functions), deeply nested `if`/`guard`/`for` combinations.

**Why it's a problem**: hard to understand (reader must hold the entire method in mind), hard to test (can't test the inner sections in isolation), hard to reuse (logic is buried).

**Detection in iOS**: a `viewDidLoad` that sets up networking, layout, animations, and analytics. A JSON decoder method that also validates, maps, and persists.

### Large Class (Massive View Controller)

A class with too many instance variables, too many methods, or too many responsibilities. In iOS, this manifests as the "Massive View Controller" anti-pattern — a UIViewController conforming to 5 protocols, owning network code, business logic, and complex layout.

**Why it's a problem**: every change to the class risks breaking unrelated functionality; the class is hard to test in isolation.

**Signs**: more than 500 lines, more than 10 instance variables, conformance to 4+ protocols, `// MARK: - Network`, `// MARK: - Business Logic`, `// MARK: - UI` sections all in one file.

### Duplicate Code

The same (or very similar) logic appears in two or more places. A bug fix in one copy won't be applied to the others.

**Types in iOS**:
- Copy-pasted animation blocks across multiple view controllers.
- Identical error handling in every networking call.
- Repeated date formatting code in multiple view models.

### Tight Coupling

A type directly creates or references a concrete dependency — `let service = NetworkService()` inside a class. The class is inseparable from `NetworkService` and cannot be tested with a mock.

**Signs**: `let x = ConcreteType()` inside `init` without injection; `ClassName.shared` singleton access throughout the codebase; `import ThirdPartySDK` in 20 files instead of behind an adapter.

### Feature Envy

A method that accesses the data or methods of another class more than its own. This is a signal that the method belongs in the other class.

```swift
// Smell: PostFormatter accesses Post's properties extensively
// — the formatting logic probably belongs in Post or PostViewModel
final class PostFormatter {
    func formatSubtitle(post: Post) -> String {
        "\(post.author.firstName) \(post.author.lastName) · \(post.publishedAt.formatted())"
    }
}
```

### Primitive Obsession

Using primitive types (`String`, `Int`, `Bool`) where a domain-specific value type would be safer and more expressive. Common in iOS: storing currency as `Double` (floating-point rounding errors), email as `String` (no validation), user ID as `Int` (can be confused with post ID).

```swift
// Smell:
func transfer(from account: Int, to: Int, amount: Double) { ... }

// Better:
struct AccountID: RawRepresentable { let rawValue: String }
struct Money: Equatable { let cents: Int; let currency: Currency }
func transfer(from: AccountID, to: AccountID, amount: Money) { ... }
```

### Divergent Change

A class that must be modified every time a different kind of change is made to the system. If adding a new payment method requires changes in 6 different places in one class, that class has divergent change.

### Shotgun Surgery

The inverse of Divergent Change: a single change requires many small changes across many classes. Every time you change the `User` model, you touch 15 files.

## 4. Practical Usage

```swift
// ══════════════════════════════════════════════════════════════
// ── SMELL: Long Method ────────────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — one massive method with four distinct responsibilities
final class OrderViewController: UIViewController {

    func submitOrder() {
        // 1. Validate (10 lines)
        guard !cartItems.isEmpty else {
            showAlert(title: "Error", message: "Your cart is empty")
            return
        }
        guard let address = selectedAddress else {
            showAlert(title: "Error", message: "No delivery address selected")
            return
        }

        // 2. Calculate total (8 lines)
        let subtotal = cartItems.reduce(Decimal(0)) { $0 + $1.price * Decimal($1.quantity) }
        let tax = subtotal * 0.1
        let shipping = subtotal > 50 ? Decimal(0) : Decimal(5)
        let total = subtotal + tax + shipping

        // 3. Submit network request (15 lines)
        isLoading = true
        let order = Order(items: cartItems, address: address, total: total)
        NetworkService.shared.submitOrder(order) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success(let order): self?.navigateToConfirmation(order: order)
                case .failure(let error): self?.showAlert(title: "Error", message: error.localizedDescription)
                }
            }
        }
    }

    private var cartItems: [CartItem] = []
    private var selectedAddress: Address? = nil
    private var isLoading = false
    private func showAlert(title: String, message: String) {}
    private func navigateToConfirmation(order: Order) {}
}

// AFTER — each responsibility extracted into a focused method
// (shown as extension for clarity; in practice, move to ViewModel)
extension OrderViewController {

    func submitOrderRefactored() {
        guard validateCart() else { return }
        guard let address = selectedAddress else {
            showAlert(title: "Error", message: "No delivery address selected"); return
        }
        let total = calculateTotal()
        placeOrder(address: address, total: total)
    }

    private func validateCart() -> Bool {
        guard !cartItems.isEmpty else {
            showAlert(title: "Error", message: "Your cart is empty")
            return false
        }
        return true
    }

    private func calculateTotal() -> Decimal {
        let subtotal = cartItems.reduce(Decimal(0)) { $0 + $1.price * Decimal($1.quantity) }
        return subtotal + subtotal * 0.1 + (subtotal > 50 ? 0 : 5)
    }

    private func placeOrder(address: Address, total: Decimal) {
        isLoading = true
        let order = Order(items: cartItems, address: address, total: total)
        NetworkService.shared.submitOrder(order) { [weak self] result in
            DispatchQueue.main.async {
                self?.isLoading = false
                switch result {
                case .success(let o): self?.navigateToConfirmation(order: o)
                case .failure(let e): self?.showAlert(title: "Error", message: e.localizedDescription)
                }
            }
        }
    }
}

// ══════════════════════════════════════════════════════════════
// ── SMELL: Primitive Obsession ────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE
func calculateDiscount(userType: String, orderTotal: Double) -> Double {
    // "premium", "standard", "guest" — easy to mistype
    userType == "premium" ? orderTotal * 0.2 : 0
}

// AFTER
enum UserType: String { case premium, standard, guest }
struct Money: Equatable, Comparable {
    let cents: Int
    static func < (lhs: Money, rhs: Money) -> Bool { lhs.cents < rhs.cents }
    func discount(percent: Int) -> Money { Money(cents: cents * percent / 100) }
}

func calculateDiscount(userType: UserType, orderTotal: Money) -> Money {
    userType == .premium ? orderTotal.discount(percent: 20) : Money(cents: 0)
}

// ══════════════════════════════════════════════════════════════
// ── SMELL: Duplicate Code ─────────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — same error handling in multiple ViewModels
// In FeedViewModel:
// do { posts = try await repository.fetchPosts() }
// catch let e as NetworkError { errorMessage = e.userFacingMessage }
// catch { errorMessage = "Something went wrong" }
//
// In ProfileViewModel — IDENTICAL pattern

// AFTER — extracted shared error handler
extension Error {
    var userFacingMessage: String {
        if let networkError = self as? NetworkError {
            return networkError.userFacingMessage
        }
        return "Something went wrong. Please try again."
    }
}

// Placeholder types:
struct CartItem { let price: Decimal; let quantity: Int }
struct Address {}
struct Order { let items: [CartItem]; let address: Address; let total: Decimal }
enum NetworkError: Error { case serverError(Int)
    var userFacingMessage: String { "Server error" }
}
final class NetworkService {
    static let shared = NetworkService()
    func submitOrder(_ order: Order, completion: @escaping (Result<Order, Error>) -> Void) {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the "Massive View Controller" anti-pattern and why is it a problem in iOS?**

A: Massive View Controller (MVC) is an iOS-specific instance of the Large Class code smell where `UIViewController` accumulates network calls, data transformation, business rules, navigation logic, and UI setup in one file. It happens because `UIViewController`'s delegate/data source protocols (UITableViewDataSource, UITableViewDelegate, NSFetchedResultsControllerDelegate) are often implemented directly on the VC, making it convenient but bloated. Problems: (1) **Untestable**: a VC requires the full UIKit lifecycle (`loadView`, `viewDidLoad`) to test, making unit tests slow and fragile. (2) **Hard to read**: a 2000-line VC with mixed concerns requires understanding the whole file to make a change. (3) **Impossible to reuse**: business logic buried in a VC can't be shared with another VC or a widget extension. Solutions: extract business logic into a `ViewModel`, networking into a `Repository`, navigation into a `Coordinator`, and data source logic into a dedicated `DataSource` object.

**Q: What is duplicate code (DRY violation) and why is it dangerous?**

A: Duplicate code is the same (or very similar) logic appearing in two or more places. The "Don't Repeat Yourself" principle states that every piece of knowledge should have a single, authoritative representation. Danger: (1) **Bug propagation**: a fix applied to one copy is not automatically applied to the others. The bug resurfaces in the untouched copy, often in a production incident. (2) **Inconsistency**: over time, duplicate copies diverge as different developers modify them independently, leading to subtly different behaviours for the same conceptual operation. (3) **Refactoring cost**: every future change to the logic must be made N times. The fix: extract the logic into a shared function, extension, protocol default, or base class (depending on the context), then replace all copies with calls to the single authoritative implementation.

### Hard

**Q: How do you identify and resolve tight coupling in an iOS codebase?**

A: Identify tight coupling by looking for: `let x = ConcreteType()` inside an `init`, `ClassName.shared` calls scattered throughout the codebase, `import ThirdPartySDK` in non-adapter files, and types that cannot be unit tested without the real dependency present. Resolve by: (1) **Introduce a protocol (seam)**: define `protocol AnalyticsService` and make both the real `FirebaseAnalytics` and a `MockAnalytics` conform. (2) **Constructor injection**: change `class FeedViewModel { let analytics = FirebaseAnalytics() }` to `class FeedViewModel { init(analytics: AnalyticsService) { ... } }`. (3) **Adapter for third-party code**: create `FirebaseAnalyticsAdapter: AnalyticsService` that wraps `FirebaseAnalytics`. Only the adapter file imports `Firebase`. All other code depends on `AnalyticsService`. (4) **Dependency container**: create an `AppDependencies` struct that wires real implementations at the app entry point, and pass mock implementations in tests.

### Expert

**Q: You've been asked to improve a 3000-line UIViewController with mixed responsibilities. Describe your step-by-step refactoring approach without breaking existing functionality.**

A: Systematic six-step approach: (1) **Write characterisation tests**: before touching anything, write tests that capture the VC's current behaviour (even if imperfect). These are safety nets. Use Snapshot tests for UI states, unit tests for any pure functions you can identify. (2) **Extract the pure logic first**: look for methods that don't use `self` (or use only non-UIKit properties). These can be moved to static functions or a new struct without changing any interface. Run the tests after each extraction. (3) **Extract the ViewModel**: move `@IBOutlet`-unrelated state (`var isLoading`, `var posts`, network calls) into a new `ViewModel` class. Wire it to the VC via `@Published`/`ObservableObject` or a closure-based binding. This is the highest-value extraction — it immediately makes the business logic testable. (4) **Extract the data source**: if the VC conforms to `UITableViewDataSource`/`UICollectionViewDataSource`, extract those methods into a dedicated `DataSource` class that takes the data model as input. (5) **Extract navigation**: pull `present`, `push`, `performSegue` calls into a `Coordinator`. The VC exposes callbacks; the coordinator handles navigation. (6) **Validate and commit incrementally**: commit after each extraction with a message like "refactor: extract PostListDataSource from FeedViewController". All tests must pass at each commit. Never do all six steps in one commit — small commits make bisecting regressions easy.

## 6. Common Issues & Solutions

**Issue: You identified duplicate code in two view controllers but they're not identical — one has extra validation.**

Solution: This is parallel implementation drift — the copies started identical and diverged. Extract the common core into a shared function, and parameterise the different parts: the extra validation becomes an optional parameter or a strategy protocol. Create a unified `validateAndFormat(input: String, validators: [ValidationStrategy]) -> Result<String, ValidationError>` function that both callers use with their respective validator sets.

**Issue: You want to fix tight coupling but the codebase has hundreds of call sites for `AnalyticsService.shared`.**

Solution: Use an IDE refactoring (Xcode's "Rename") to change `AnalyticsService.shared.log(...)` to a wrapper function `logAnalyticsEvent(...)` in one global file. This consolidates all call sites to one function. Then update that function to accept an `AnalyticsService` parameter (defaulting to `AnalyticsService.shared`), making it injectable. Migrate call sites gradually, starting with the most-tested classes.

## 7. Related Topics

- [Refactoring Techniques](refactoring-techniques.md) — the fixes for each smell
- [Design Patterns](../15-design-patterns/index.md) — the patterns refactoring moves toward
- [Testable Architecture](../11-testing/testable-architecture.md) — tests needed before refactoring
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — the target architecture for MVC-smell refactoring
