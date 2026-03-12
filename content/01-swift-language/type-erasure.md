# Type Erasure

## 1. Overview

Type erasure is a technique for hiding a concrete type behind a protocol or wrapper interface, allowing heterogeneous collections and API surfaces that don't expose implementation details. Swift's type system is powerful but strict: protocols with associated types or `Self` requirements cannot be used directly as types in many contexts. Type erasure solves this by wrapping the concrete type in a generic struct or class that exposes only the protocol surface. Swift 5.7 introduced `any` keyword and improved existential handling, reducing the need for manual erasure in many cases.

## 2. Simple Explanation

Imagine a music streaming service. It doesn't care whether you're playing from Spotify, Apple Music, or a local file — it just needs to know "can you play a track?" It creates a universal `AnyPlayer` wrapper: hand it any music source and it exposes a single `play()` button.

Type erasure works the same way:
- The `AnyPlayer` is the type-erased wrapper
- The concrete sources (Spotify, Apple Music) are hidden inside
- The caller only sees `AnyPlayer` — no generics, no leaking implementation details

## 3. Deep iOS Knowledge

### Why Type Erasure Is Needed

Consider `Publisher` in Combine. Every operator (`map`, `filter`, `flatMap`) produces a distinct concrete type. A view model that exposes its entire transformation chain would expose internals:

```swift
var publisher: Publishers.Map<Publishers.Filter<URLSession.DataTaskPublisher>, String>
```

Type erasure collapses this to `AnyPublisher<String, Error>`, hiding the chain while preserving the interface.

Protocols with `associatedtype` or `Self` requirements are called **PATs (Protocols with Associated Types)**. They cannot be used as `any Protocol` existentials without boxing overhead, and historically required manual type erasure for generic storage.

### Existential Containers (`any`)

Swift 5.7 unified the `any` keyword for existential types. An existential container stores:
1. A value buffer (inline for small values, pointer for large)
2. A pointer to the type's metadata
3. A protocol witness table (vtable of protocol method implementations)

Accessing a method through `any Protocol` incurs:
- A witness table lookup (one indirection)
- A potential heap allocation for the value buffer

### `some` Opaque Types

`some Protocol` (opaque return type) hides the concrete type from the caller but keeps it known to the compiler. This enables static dispatch and works with PATs. Used for property wrappers, SwiftUI `body`, function return types where the type is always the same.

### Manual Type Erasure Pattern

Before Swift 5.7, PATs required manual erasure:
1. Create a private protocol `_AnyProtocol` with generic methods replaced by closures
2. Create a generic `_AnyBox<T: Protocol>` that implements `_AnyProtocol` using the concrete type
3. Expose a public `AnyProtocol` struct that holds an `_AnyProtocol` box

This is the pattern `AnyPublisher`, `AnyIterator`, `AnySequence` follow.

### Swift 5.7+ Improvements

- `any Protocol` syntax makes existentials explicit and uniform
- Primary associated types (`Collection<Int>`) allow constrained existentials: `any Collection<Int>`
- Reduces need for manual erasure in many cases — you can now write `any Publisher<String, Error>` instead of `AnyPublisher<String, Error>` in many positions

### Performance Comparison

| Approach | Dispatch | Allocation | Type info at compile time |
|----------|----------|------------|--------------------------|
| Concrete type | Static | None extra | Full |
| `some Protocol` | Static | None extra | Hidden from caller |
| `any Protocol` | Dynamic (witness table) | May box | Erased |
| Manual `AnyX` | Dynamic (closure) | Heap (box) | Erased |

## 4. Practical Usage

```swift
import Combine
import Foundation

// ── AnyPublisher (standard library type erasure) ───────────────
class UserViewModel {
    // Exposes erased type — callers don't see the transformation chain
    var usernamePublisher: AnyPublisher<String, Never> {
        $username
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .eraseToAnyPublisher()   // type erasure happens here
    }

    @Published var username: String = ""
}

// ── Manual type erasure pattern ────────────────────────────────
protocol Drawable {
    associatedtype Canvas
    func draw(on canvas: Canvas)
}

// Step 1: Private box protocol
private protocol _DrawableBox {
    func _draw(on canvas: Any)
}

// Step 2: Generic concrete box
private struct _DrawableBoxImpl<D: Drawable>: _DrawableBox {
    let base: D
    func _draw(on canvas: Any) {
        guard let canvas = canvas as? D.Canvas else { return }
        base.draw(on: canvas)
    }
}

// Step 3: Public erased wrapper
struct AnyDrawable {
    private let box: _DrawableBox

    init<D: Drawable>(_ drawable: D) {
        box = _DrawableBoxImpl(base: drawable)
    }

    func draw(on canvas: Any) { box._draw(on: canvas) }
}

// Usage: heterogeneous array without generics in the collection type
var shapes: [AnyDrawable] = []

// ── `some` vs `any` in practice ──────────────────────────────
protocol Animal {
    var name: String { get }
    func sound() -> String
}

struct Dog: Animal { var name = "Rex";   func sound() -> String { "Woof" } }
struct Cat: Animal { var name = "Whiskers"; func sound() -> String { "Meow" } }

// `some` — one specific hidden type; efficient, static dispatch
func makeDefaultAnimal() -> some Animal { Dog() }

// `any` — runtime polymorphism; existential box
func allAnimals() -> [any Animal] { [Dog(), Cat()] }

// Iterate over existential array
for animal in allAnimals() {
    print("\(animal.name): \(animal.sound())")
}

// ── Constrained existential (Swift 5.7+) ──────────────────────
// Before: had to use AnyCollection<Int>
// After:
func sum(_ numbers: any Collection<Int>) -> Int {
    numbers.reduce(0, +)
}

print(sum([1, 2, 3]))   // 6
print(sum(Set([4, 5]))) // 9

// ── Type erasure for delegates with associated types ──────────
protocol DataProvider {
    associatedtype Item: Identifiable
    func provide() -> [Item]
}

// Erase for storage when concrete type isn't known at init time
struct AnyDataProvider<Item: Identifiable> {
    private let _provide: () -> [Item]

    init<P: DataProvider>(_ provider: P) where P.Item == Item {
        _provide = { provider.provide() }
    }

    func provide() -> [Item] { _provide() }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is type erasure and why is it needed in Swift?**

A: Type erasure is the practice of hiding a concrete type behind a wrapper that exposes only a protocol interface. It is needed because protocols with associated types cannot be used directly as variable types or collection element types in many contexts — their full generic signature would leak through the API. Type erasure collapses the full type to a simpler interface, enabling heterogeneous collections and stable API boundaries. `AnyPublisher` in Combine is the canonical example.

**Q: What is the difference between `some Protocol` and `any Protocol`?**

A: `some Protocol` is an opaque type where the compiler knows the exact concrete type but hides it from the caller — static dispatch, no boxing. `any Protocol` is an existential where the concrete type is truly unknown at compile time — dynamic dispatch via witness table, possible heap allocation. Use `some` for return types where the type doesn't vary; use `any` for collections or parameters where different concrete types may appear.

### Hard

**Q: Walk through the manual type erasure pattern.**

A: The standard approach has three components. First, a private protocol or closure-based interface that erases the generic parameter by representing operations as closures or `Any` parameters. Second, a generic private box type that captures a concrete conformer and implements the private interface by forwarding to it. Third, a public struct that stores the box as a protocol type, forwarding public method calls through it. This gives callers a non-generic API while internally maintaining type safety through the closures. Combine's `AnyPublisher`, Swift's `AnyIterator`, and `AnyHashable` all follow this pattern.

**Q: When should you prefer a generic parameter over an `any Protocol` existential?**

A: Prefer generic parameters (`<T: Protocol>`) for performance-sensitive code and when the concrete type is fully determined at the call site. Generic parameters allow specialisation, static dispatch, and inlining. Use `any Protocol` (existentials) when you genuinely need runtime polymorphism — e.g., a heterogeneous array of protocol values, or an API boundary where the caller varies the concrete type. The new `any` syntax in Swift 5.7 makes this choice explicit, documenting that dynamic dispatch is intentional.

### Expert

**Q: Explain how `AnyPublisher` is implemented internally in Combine and what overhead it adds.**

A: `AnyPublisher<Output, Failure>` wraps any `Publisher` whose `Output` and `Failure` types match. Internally it stores the concrete publisher in a heap-allocated box (using a type-erased `AnySubscription` / box protocol pattern). When a subscriber attaches, `receive(subscriber:)` is forwarded through the box to the concrete publisher. This adds one heap allocation (for the box) and one level of indirection (virtual dispatch through the box). The overhead is negligible for typical Combine pipelines — the asynchronous scheduling costs dominate — but in a synchronous hot path, prefer a concrete publisher type.

## 6. Common Issues & Solutions

**Issue: "Protocol can only be used as a generic constraint" error when trying to use a PAT as a variable type.**

Solution: In Swift 5.7+, use `any Protocol` explicitly. For older Swift, use the manual type erasure pattern. If possible, refactor the caller to use a generic parameter instead.

**Issue: Using `AnyPublisher` everywhere causes loss of useful error type information.**

Solution: Use typed error parameters where possible (`AnyPublisher<Value, MyError>`). Avoid widening to `Error` (existential) unless you truly have heterogeneous error types. Swift 6's typed throws may reduce this boilerplate.

**Issue: Existential boxing causing heap allocation in a tight loop.**

Solution: Replace `any Protocol` with a generic parameter. If the collection must hold mixed types, consider a tagged union (enum) instead — it has stack semantics and no extra allocation.

**Issue: `some` return type forces all code paths to return the same concrete type.**

Solution: If different code paths return different concrete types, `some` is not viable. Switch to `any Protocol`, a concrete enum wrapping variants, or a manual type-erased wrapper.

## 7. Related Topics

- [Generics](generics.md) — generic constraints as the alternative to type erasure
- [Protocol-Oriented Programming](protocol-oriented-programming.md) — protocols with associated types that motivate erasure
- [Property Wrappers](property-wrappers.md) — `@Published` uses erasure internally via `AnyPublisher`
- [Concurrency](../03-concurrency/index.md) — `AsyncStream` and `AnyAsyncSequence` use similar patterns
