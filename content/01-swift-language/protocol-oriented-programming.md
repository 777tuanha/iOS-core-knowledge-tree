# Protocol-Oriented Programming

## 1. Overview

Protocol-Oriented Programming (POP) is Swift's preferred design paradigm, introduced by Apple at WWDC 2015. Rather than inheriting behaviour through class hierarchies, POP composes behaviour through protocol conformances and protocol extensions. Protocols define contracts; protocol extensions provide default implementations; types — including structs, enums, and classes — conform to assemble the behaviour they need. This approach avoids the fragile base-class problem, supports value types, and encourages small, focused abstractions.

## 2. Simple Explanation

Think of protocols like job certifications. A "Licensed Driver" certification means you can drive. A "First-Aid Certified" means you can treat injuries. A person can hold both certifications at once — they are composed, not inherited from a single "SuperPerson" base class.

Protocol composition in Swift:
- Protocol = certification (contract)
- Protocol extension = included training manual (default implementation)
- Conforming type = person who holds the certifications

A struct can be both `Drawable` and `Animatable` without inheriting from any class.

## 3. Deep iOS Knowledge

### Protocols vs Inheritance

| | Class Inheritance | Protocol Composition |
|--|---|---|
| Type restriction | Classes only | Any type (struct, enum, class, actor) |
| Multiple parents | No (single inheritance) | Yes (unlimited protocols) |
| Default behaviour | Override methods | Protocol extensions |
| Coupling | Tight (subclass knows superclass) | Loose (type knows protocol) |
| Fragile base class | Yes | No |

### Protocol Extensions

Protocol extensions add method and property implementations to any conforming type without subclassing. They can provide default implementations and add computed properties. If a conforming type implements the same method, its version takes precedence.

```swift
protocol Greetable {
    var name: String { get }
    func greet() -> String  // optional to override
}

extension Greetable {
    func greet() -> String { "Hello, \(name)!" }  // default implementation
}
```

### Protocol Composition

A single parameter or variable can require conformance to multiple protocols using `&`:

```swift
func present(_ item: Drawable & Animatable) { ... }
```

This is more flexible than inheritance because unrelated types can both satisfy the composition.

### Static vs Dynamic Dispatch

When a concrete type is known at compile time (using a generic parameter `<T: Protocol>`), Swift uses **static dispatch** — the correct method is called directly without a lookup, enabling inlining and optimisation. When the type is unknown at compile time (`any Protocol` existential), Swift uses **dynamic dispatch** via a protocol witness table (similar to a vtable), adding a small lookup overhead.

Prefer generic parameters over existentials in performance-sensitive code.

### Self Requirements and `AnyObject`

Adding `Self` to a protocol requirement means implementations must return or accept their own type — useful for fluent builder APIs. Adding `: AnyObject` to a protocol restricts conformers to class types, enabling `weak` references to protocol-typed variables.

### Protocol Hierarchies

Protocols can refine other protocols. A conforming type must satisfy all requirements in the hierarchy:

```swift
protocol Animal {
    var name: String { get }
}

protocol Pet: Animal {
    var owner: String { get }
}
// Conforming to Pet requires both `name` and `owner`
```

## 4. Practical Usage

```swift
// ── Basic protocol + extension ─────────────────────────────────
protocol Identifiable {
    var id: UUID { get }
}

extension Identifiable {
    func isEqual(to other: some Identifiable) -> Bool {
        id == other.id
    }
}

struct Product: Identifiable {
    let id = UUID()
    var name: String
}

// ── Protocol composition ───────────────────────────────────────
protocol Serializable {
    func serialize() -> Data
}

protocol Cacheable {
    var cacheKey: String { get }
}

// Function accepts any type that is both Serializable and Cacheable
func cache<T: Serializable & Cacheable>(_ item: T, into store: CacheStore) {
    let data = item.serialize()
    store.set(data, forKey: item.cacheKey)
}

// Dummy types for compilation
class CacheStore { func set(_ d: Data, forKey k: String) {} }

// ── Default implementations for protocol requirements ──────────
protocol Logging {
    var logPrefix: String { get }
    func log(_ message: String)
}

extension Logging {
    var logPrefix: String { String(describing: type(of: self)) }

    func log(_ message: String) {
        print("[\(logPrefix)] \(message)")
    }
}

// Conformer gets log() for free; optionally overrides logPrefix
struct NetworkManager: Logging {
    // Uses default logPrefix = "NetworkManager"
    // Uses default log() implementation
}

struct AuthService: Logging {
    var logPrefix: String { "AUTH" }  // override just the prefix
}

// ── Retroactive conformance ────────────────────────────────────
// Add protocol conformance to a type you don't own
extension Int: Logging {
    // Adds log() to Int — useful in extensions/tests
}
// 42.log("Hello")  → "[Int] Hello"

// ── Protocol with associated type (generic protocol) ──────────
protocol DataSource {
    associatedtype Item
    func item(at index: Int) -> Item
    var count: Int { get }
}

struct ArrayDataSource<T>: DataSource {
    private let items: [T]
    init(_ items: [T]) { self.items = items }
    func item(at index: Int) -> T { items[index] }
    var count: Int { items.count }
}

// ── Static dispatch via generic (preferred over existential) ───
func processAll<DS: DataSource>(_ dataSource: DS) {
    for i in 0..<dataSource.count {
        print(dataSource.item(at: i))
    }
}

// ── AnyObject-constrained protocol for weak delegate ──────────
protocol ViewControllerDelegate: AnyObject {
    func didFinish()
}

class ChildViewController: UIViewController {
    weak var delegate: ViewControllerDelegate?  // weak possible because AnyObject

    func finish() {
        delegate?.didFinish()
        dismiss(animated: true)
    }
}

import UIKit  // for UIViewController above
```

## 5. Interview Questions & Answers

### Basic

**Q: What is protocol-oriented programming and how does it differ from OOP?**

A: POP composes behaviour through protocol conformances and protocol extensions rather than class inheritance. Any type — struct, enum, or class — can participate. OOP centres on class hierarchies where behaviour is inherited from superclasses. POP avoids the fragile base-class problem, works with value types, supports multiple protocol conformance (vs single inheritance), and encourages smaller, focused contracts.

**Q: What is a protocol extension and what can it do?**

A: A protocol extension adds method and property implementations to all types that conform to the protocol. It can provide default implementations of protocol requirements (which conformers can override) and can add additional utility methods not declared in the protocol. Constraints can restrict which conformers receive an extension (`extension Collection where Element: Numeric`).

### Hard

**Q: What is the difference between a protocol used as a generic constraint versus an existential?**

A: As a generic constraint (`func foo<T: Flyable>(_ t: T)`), the concrete type is known at compile time. Swift uses static dispatch, can inline the method, and may specialise the generic for performance. As an existential (`func foo(_ t: any Flyable)`), the concrete type is erased into an existential container at runtime with a protocol witness table for dynamic dispatch. Existentials also impose heap allocation for value types larger than ~3 words. Generic constraints are preferred for performance-sensitive paths; existentials are needed when the concrete type varies at runtime.

**Q: Can you add a stored property in a protocol extension?**

A: No. Protocol extensions can only add computed properties and method implementations — they cannot add stored properties or modify the memory layout of conforming types. Stored properties must be declared in the protocol requirement itself and then stored by each conforming type. Workarounds include using associated objects (for classes) or adding an extra stored property to each conforming type.

### Expert

**Q: Explain the diamond problem in protocol composition and how Swift handles it.**

A: The diamond problem occurs when two protocols both provide a default implementation of the same method, and a type conforms to both. Unlike class multiple-inheritance (where this causes ambiguity in C++), Swift resolves it statically: if the conforming type declares its own implementation, that wins. If it doesn't, and two protocol extensions provide conflicting defaults, the compiler emits an error — requiring the conforming type to disambiguate by providing its own implementation. Swift does not silently pick one; it forces explicit resolution. If one protocol refines the other, the more specific refinement's default wins.

## 6. Common Issues & Solutions

**Issue: "Protocol can only be used as a generic constraint because it has Self or associated type requirements" error.**

Solution: The protocol cannot be used directly as an `any Protocol` existential in older Swift. Upgrade to Swift 5.7+ and use `any Protocol` syntax explicitly, or refactor to a generic parameter `<T: Protocol>`. If the associated type truly varies at runtime, consider type erasure (see `type-erasure.md`).

**Issue: Default implementation in a protocol extension is not called — conformer's version runs instead.**

Solution: This is correct behaviour — conformer implementations shadow extension defaults. If the extension method should always run alongside the conformer's implementation, extract the shared logic into a separate protocol requirement and call it from the extension's default.

**Issue: Adding conformance to a third-party type causes conflicts when two modules do the same.**

Solution: Avoid retroactive conformances to types you don't own where possible. If required, place them in a single, centralised file and ensure only one module declares the conformance. Swift 5.7+ warns about retroactive conformances to prompt better organisation.

**Issue: Protocol with many default implementations becomes a "god protocol" — hard to reason about.**

Solution: Split into smaller, focused protocols. Use protocol composition at usage sites rather than one catch-all protocol. Each protocol should have a single reason to change.

## 7. Related Topics

- [Generics](generics.md) — generic constraints and associated types complement POP
- [Type Erasure](type-erasure.md) — erasing associated types for heterogeneous collections
- [Struct vs Class](struct-vs-class.md) — why POP often replaces class inheritance for structs
- [Value vs Reference Types](value-vs-reference.md) — POP enables value types to carry behaviour
