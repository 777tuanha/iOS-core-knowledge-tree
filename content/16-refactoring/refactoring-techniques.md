# Refactoring Techniques

## 1. Overview

Refactoring techniques are named, repeatable transformations that address specific code smells. Martin Fowler's catalogue documents over 60 techniques — the most practically important for iOS and Swift development are: **Extract Method** (split a long function into smaller named functions), **Extract Class** (split a class with too many responsibilities into two focused classes), **Move Method** (relocate a method to the class whose data it primarily uses), **Replace Conditional with Polymorphism** (replace `switch`/`if-else` chains with protocol conformance), and **Introduce Parameter Object** (replace multiple related parameters with a single struct). Each technique has a mechanical, step-by-step procedure that minimises risk — do the smallest thing, run the tests, commit. The key discipline: refactor in isolation (separate commits from feature work), and only refactor code with test coverage.

## 2. Simple Explanation

Refactoring techniques are like decluttering recipes. **Extract Method** is "take these items off the overcrowded shelf and put them in a labelled box." The shelf (the function) is smaller; the box (the extracted function) has a clear name. **Extract Class** is "these items belong in a different room — move them there and label the room." **Move Method** is "this recipe card is in the drinks cabinet but it's for food — move it to the kitchen drawer where it belongs." **Replace Conditional with Polymorphism** is "instead of a manual decision tree at the door ('if guest, do this; if VIP, do that; if staff, do this'), give each person a badge that knows what to do — the door reads the badge and the badge handles itself." **Introduce Parameter Object** is "instead of passing six individual ingredients every time you cook, put them in a recipe box that you pass as one item."

## 3. Deep iOS Knowledge

### Extract Method

**Smell addressed**: Long Method.
**When to apply**: you can describe a group of lines with a comment, or a logical sub-task within a larger method can be named.
**Procedure**: (1) Identify a cohesive group of lines. (2) Create a new private method with a descriptive name. (3) Identify local variables used as inputs → parameters; used as outputs → return value (or `inout` for multiple). (4) Replace the original lines with a call to the new method. (5) Run tests.

**Swift specifics**: use `@discardableResult` if the return value is optional, `throws` if the extracted code can fail. Prefer smaller, focused functions over large ones — Swift closures can serve as extracted "methods" for very localised logic.

### Extract Class

**Smell addressed**: Large Class, Divergent Change.
**When to apply**: a class has two or more distinct responsibilities — a clear boundary exists between a group of methods/properties.
**Procedure**: (1) Identify the responsibility to extract. (2) Create a new class for that responsibility. (3) Move the relevant fields and methods using Move Field/Move Method. (4) Update the original class to use the new class (either as a composed property or injected dependency). (5) Run tests.

**iOS example**: extracting `NetworkManager` from `FeedViewController` → creates a testable, reusable networking layer.

### Move Method

**Smell addressed**: Feature Envy — a method that uses more data from another class than its own.
**When to apply**: a method in class A accesses fields of class B more than fields of A, or logic logically belongs to B's domain.
**Procedure**: (1) Copy the method to class B, adjusting the signature to remove the B parameter (it's now `self`). (2) Update references: call `b.method()` instead of `a.method(b)`. (3) Optionally delete from A (or keep a delegation that calls B's version). (4) Run tests.

### Replace Conditional with Polymorphism

**Smell addressed**: Switch statements or `if-else` chains that repeat the same type discrimination in multiple places.
**When to apply**: the same `switch type` or `if type == X` pattern appears in multiple methods, and adding a new case requires changes in multiple places.
**Procedure**: (1) Extract each case into a separate type conforming to a protocol. (2) Replace the switch with a polymorphic call to the protocol method. (3) Move case-specific data into the concrete type. (4) The caller holds a `[Protocol]` and calls the method uniformly. (5) Run tests.

### Introduce Parameter Object

**Smell addressed**: Long Parameter List — methods with 4+ parameters, especially when multiple callers pass the same group of parameters.
**Procedure**: (1) Create a new `struct` that groups the related parameters. (2) Update the method signature to accept the struct. (3) Update all call sites to construct and pass the struct. (4) Run tests.

**Swift specifics**: use a `struct` with a memberwise initializer. Often pairs with a Builder if the struct has many optional fields.

### Rename

The most underrated refactoring. Renaming a function, variable, or type to better reflect its purpose improves readability immediately with zero risk (Xcode's Rename refactoring updates all references).

**Patterns to watch for**: functions named `handle()`, `process()`, `doStuff()` → rename to describe what they do (`validateAndSubmitOrder()`). Boolean variables named `flag` or `check` → `isLoading`, `hasError`.

## 4. Practical Usage

```swift
// ══════════════════════════════════════════════════════════════
// ── Extract Method ─────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — a 40-line function doing four things
func processCheckout(items: [CartItem], address: Address) {
    // Validate
    guard !items.isEmpty else { showError("Cart is empty"); return }
    guard address.postcode.count == 5 else { showError("Invalid postcode"); return }

    // Calculate total
    let subtotal = items.reduce(Decimal(0)) { $0 + $1.price * Decimal($1.quantity) }
    let tax = subtotal * 0.1
    let deliveryCost: Decimal = subtotal > 50 ? 0 : 4.99
    let total = subtotal + tax + deliveryCost

    // Format receipt
    let receipt = "Order total: \(total)\nDelivery: \(deliveryCost)\nTax: \(tax)"

    // Submit
    orderService.submit(items: items, address: address, total: total) { [weak self] result in
        self?.handleOrderResult(result, receipt: receipt)
    }
}

// AFTER — each step is a named, testable function
func processCheckoutRefactored(items: [CartItem], address: Address) {
    guard validate(items: items, address: address) else { return }
    let pricing = calculatePricing(for: items)
    let receipt = formatReceipt(pricing: pricing)
    submit(items: items, address: address, total: pricing.total, receipt: receipt)
}

private func validate(items: [CartItem], address: Address) -> Bool {
    guard !items.isEmpty else { showError("Cart is empty"); return false }
    guard address.postcode.count == 5 else { showError("Invalid postcode"); return false }
    return true
}

private struct Pricing { let subtotal: Decimal; let tax: Decimal; let delivery: Decimal
    var total: Decimal { subtotal + tax + delivery }
}

private func calculatePricing(for items: [CartItem]) -> Pricing {
    let subtotal = items.reduce(Decimal(0)) { $0 + $1.price * Decimal($1.quantity) }
    return Pricing(subtotal: subtotal, tax: subtotal * 0.1,
                   delivery: subtotal > 50 ? 0 : 4.99)
}

private func formatReceipt(pricing: Pricing) -> String {
    "Order total: \(pricing.total)\nDelivery: \(pricing.delivery)\nTax: \(pricing.tax)"
}

private func submit(items: [CartItem], address: Address, total: Decimal, receipt: String) {
    orderService.submit(items: items, address: address, total: total) { [weak self] result in
        self?.handleOrderResult(result, receipt: receipt)
    }
}

// ══════════════════════════════════════════════════════════════
// ── Extract Class ──────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — UserViewModel responsible for auth AND profile
final class UserViewModel {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoggedIn = false
    @Published var displayName = ""
    @Published var avatarURL: URL? = nil
    @Published var bio = ""

    func login() { /* auth network call */ }
    func logout() { /* clear session */ }
    func updateProfile(name: String, bio: String) { /* profile network call */ }
    func uploadAvatar(_ image: UIImage) { /* upload call */ }
}

// AFTER — two focused classes
final class AuthViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoggedIn = false

    func login() { /* auth network call */ }
    func logout() { /* clear session */ }
}

final class ProfileViewModel: ObservableObject {
    @Published var displayName = ""
    @Published var avatarURL: URL? = nil
    @Published var bio = ""

    func updateProfile(name: String, bio: String) { /* profile network call */ }
    func uploadAvatar(_ image: UIImage) { /* upload call */ }
}

// ══════════════════════════════════════════════════════════════
// ── Replace Conditional with Polymorphism ─────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — switch on notification type repeated in multiple functions
enum NotificationCategory { case message, like, follow, mention }

func icon(for notification: NotificationCategory) -> UIImage {
    switch notification {
    case .message: return UIImage(systemName: "message")!
    case .like: return UIImage(systemName: "heart")!
    case .follow: return UIImage(systemName: "person.badge.plus")!
    case .mention: return UIImage(systemName: "at")!
    }
}

func accessibilityLabel(for notification: NotificationCategory) -> String {
    switch notification {
    case .message: return "New message"
    case .like: return "Someone liked your post"
    case .follow: return "New follower"
    case .mention: return "You were mentioned"
    }
}
// Adding a new category requires changes in BOTH switch statements

// AFTER — each category encapsulates its own behaviour
protocol NotificationPresentation {
    var icon: UIImage { get }
    var accessibilityLabel: String { get }
    var color: UIColor { get }
}

struct MessageNotification: NotificationPresentation {
    var icon: UIImage { UIImage(systemName: "message")! }
    var accessibilityLabel: String { "New message" }
    var color: UIColor { .systemBlue }
}

struct LikeNotification: NotificationPresentation {
    var icon: UIImage { UIImage(systemName: "heart")! }
    var accessibilityLabel: String { "Someone liked your post" }
    var color: UIColor { .systemPink }
}

struct FollowNotification: NotificationPresentation {
    var icon: UIImage { UIImage(systemName: "person.badge.plus")! }
    var accessibilityLabel: String { "New follower" }
    var color: UIColor { .systemGreen }
}

// Adding a new type: add one new struct, zero changes elsewhere
struct MentionNotification: NotificationPresentation {
    var icon: UIImage { UIImage(systemName: "at")! }
    var accessibilityLabel: String { "You were mentioned" }
    var color: UIColor { .systemOrange }
}

// ══════════════════════════════════════════════════════════════
// ── Introduce Parameter Object ────────────────────────────────
// ══════════════════════════════════════════════════════════════

// BEFORE — 6 parameters, repeated at 12 call sites
func fetchPosts(page: Int, pageSize: Int, sortBy: String, filterCategory: String?,
                includeArchived: Bool, userID: String?) async throws -> [Post] { [] }

// AFTER — grouped into a query object
struct PostQuery {
    let page: Int
    let pageSize: Int
    let sortBy: SortOrder
    let filterCategory: Category?
    let includeArchived: Bool
    let userID: UserID?

    enum SortOrder { case newest, oldest, mostLiked }
    init(page: Int = 1, pageSize: Int = 20, sortBy: SortOrder = .newest,
         filterCategory: Category? = nil, includeArchived: Bool = false, userID: UserID? = nil) {
        self.page = page; self.pageSize = pageSize; self.sortBy = sortBy
        self.filterCategory = filterCategory; self.includeArchived = includeArchived
        self.userID = userID
    }
}

func fetchPosts(query: PostQuery) async throws -> [Post] { [] }

// Call site is now self-documenting:
// let posts = try await fetchPosts(query: PostQuery(filterCategory: .tech, sortBy: .newest))

// Placeholder types:
struct CartItem { let price: Decimal; let quantity: Int }
struct Address { let postcode: String }
protocol OrderServiceProtocol { func submit(items: [CartItem], address: Address, total: Decimal, completion: @escaping (Result<Void, Error>) -> Void) }
final class CheckoutVC: UIViewController {
    var orderService: OrderServiceProtocol!
    func processCheckout(items: [CartItem], address: Address) {}
    func processCheckoutRefactored(items: [CartItem], address: Address) {}
    private func validate(items: [CartItem], address: Address) -> Bool { true }
    private struct Pricing { let subtotal: Decimal; let tax: Decimal; let delivery: Decimal; var total: Decimal { subtotal + tax + delivery } }
    private func calculatePricing(for items: [CartItem]) -> Pricing { Pricing(subtotal: 0, tax: 0, delivery: 0) }
    private func formatReceipt(pricing: Pricing) -> String { "" }
    private func submit(items: [CartItem], address: Address, total: Decimal, receipt: String) {}
    private func handleOrderResult(_ result: Result<Void, Error>, receipt: String) {}
    func showError(_ message: String) {}
}
struct Post {}
struct Category {}
struct UserID: RawRepresentable { let rawValue: String }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the Extract Method refactoring and when should you apply it?**

A: Extract Method takes a group of lines from a function and moves them into a new, named function. Apply it when: (1) You can describe the purpose of a group of lines in a few words — that description is the extracted function's name. (2) A function has a comment above a section ("// Validate input") — replace the comment with an extracted function named for that purpose. (3) A function is longer than 20–30 lines and has clearly separable concerns. The benefit is twofold: the original function becomes easier to read (it now reads as a sequence of named steps), and the extracted function becomes independently testable. In Swift, extracted methods are naturally `private` — they're implementation details. The extracted function should do one thing and have a name that describes that thing without needing to read its implementation.

**Q: What is "Replace Conditional with Polymorphism" and what problem does it solve?**

A: This refactoring replaces a repeated `switch` or `if-else` chain on a type discriminator with a protocol method implemented by each concrete type. It solves the "Open/Closed" problem: when a new case is added, a raw `switch` requires changing every place the switch appears; with polymorphism, you add one new conforming type and the existing code automatically handles it via protocol dispatch. It transforms fragile, spread-out conditionals into a single, extensible protocol. Use it when the same `switch type` pattern appears in more than one function, or when the number of cases is growing. Don't apply it for simple, non-recurring switches — the added class hierarchy is overhead for a two-case switch that appears only once.

### Hard

**Q: How do you safely Extract Class from a Massive View Controller that has no tests?**

A: Without tests, you risk introducing bugs during extraction. Safe process: (1) **Add characterisation tests first**: write integration or snapshot tests that document the current visible behaviour (what the screen shows for each state). These are your safety net — if extraction breaks something visible, these tests catch it. (2) **Start with pure extraction (no behaviour change)**: create the new class (`FeedViewModel`), copy (don't cut) the relevant properties and methods from the VC into it. Make the VC use the new class by instantiating it as a property: `var viewModel = FeedViewModel()`. Route existing VC code to call `viewModel.method()` instead of calling the methods directly. (3) **Delete the original code from the VC** only after the new path is working (verified by tests). (4) **Commit frequently**: each small step (create new class, move one property, move one method, update one call site) is a commit. If something breaks, you revert one small commit, not hours of work. (5) **Add unit tests for the extracted class** now that it exists outside the VC — this is where testability pays off.

**Q: When should you use Extract Method vs Extract Class?**

A: Extract Method operates within a single class — it's appropriate when a function is too long but all its concepts belong to the same class's responsibility. The extracted method remains `private` and is an implementation detail. Extract Class operates across a class boundary — use it when you identify a coherent group of methods and data that form a separate responsibility (cohesive but separable). The signals: a group of methods that don't use `self` outside the group (they could move wholesale), or two groups of fields that are never used together. Extract Method is the more frequent, lighter-weight operation. Extract Class is a heavier structural change that produces two independently testable, independently deployable units. In practice: start with Extract Method; if the extracted methods consistently reference the same group of fields that the rest of the class doesn't use, that's the signal for Extract Class.

### Expert

**Q: Describe how you would apply "Replace Conditional with Polymorphism" to a legacy codebase where the type discrimination is embedded in dozens of functions across multiple files.**

A: Five-step strangler-fig approach: (1) **Audit all switch sites**: use Xcode's Find → Find in Project for the discriminating enum or class-check pattern. Catalogue all locations — this determines the scope. (2) **Define the protocol**: create `NotificationPresentation` (or whatever the concept is) with all the methods currently implemented in the switch cases. Don't implement yet. (3) **Create concrete types**: one type per case, each conforming to the protocol with its specific implementation. The concrete types encapsulate the case-specific data (e.g., `LikeNotification` holds the liker's name). (4) **Replace one switch at a time**: start with the most-tested function. Replace its switch with a protocol call. Run tests. Commit. Continue until all switches are replaced. (5) **Enforce at the boundary**: the `switch` that maps the raw enum to the protocol-conforming type (the factory method) is now the only switch in the codebase. Add a compile-time check — use `@unknown default` on the switch to get a warning when a new case is added but the factory is not updated. This makes "adding a new type" a compile-error-detected change rather than a silent bug.

## 6. Common Issues & Solutions

**Issue: After Extract Class, both classes end up calling each other (circular dependency).**

Solution: Circular dependencies indicate the extraction boundary was wrong — the two classes are not truly independent. Options: (1) Introduce a third coordination class that owns both; (2) Define a protocol that one class implements and the other depends on (dependency inversion — breaks the concrete dependency); (3) Re-evaluate the boundary — maybe the extracted class should contain one of the methods that creates the circularity.

**Issue: After Replace Conditional with Polymorphism, you need to serialise/deserialise the protocol type (e.g., store to JSON).**

Solution: The polymorphic type is not directly serialisable because the decoder doesn't know which concrete type to instantiate. Solutions: (1) Use a tagged union: encode with a `type` field (`"type": "like"`) and a custom decoder that switches on the type field to instantiate the right concrete type. (2) Use an `enum` with associated values conforming to `Codable` — Swift's Codable synthesis handles the discriminated union. (3) Keep the raw enum for persistence and convert to protocol types at the presentation layer — the enum is the persistence model, the protocol types are the UI model.

## 7. Related Topics

- [Code Smells](code-smells.md) — the smells that motivate these techniques
- [Design Patterns](../15-design-patterns/index.md) — the patterns these techniques move toward
- [Testable Architecture](../11-testing/testable-architecture.md) — tests required before refactoring
- [Dependency Injection](../06-architecture/dependency-injection.md) — DI introduced by Extract Class
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — architecture after MVC refactoring
