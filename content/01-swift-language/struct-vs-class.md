# Struct vs Class

## 1. Overview

Swift provides both `struct` and `class` as nominal types for encapsulating data and behaviour. Choosing between them is one of the most consequential design decisions in Swift: it determines value vs reference semantics, inheritance capability, memory layout, mutability model, and thread-safety profile. Apple's Swift guidelines recommend defaulting to `struct` and reaching for `class` only when a specific class-only feature is required.

## 2. Simple Explanation

Think of a `struct` as a form you fill in and hand out as photocopies. Everyone gets their own copy; changes to one copy never affect any other. A `class` is like a shared whiteboard in a conference room — everyone works on the same surface, so every change is immediately visible to all participants.

- `struct` → photocopy (each recipient is independent)
- `class` → shared whiteboard (all participants see every change)

## 3. Deep iOS Knowledge

### Value Semantics (struct)

Structs use value semantics: assignment, function arguments, and collection insertions all produce independent copies. Mutation is only possible on `var` bindings, and only via `mutating` methods, making accidental mutation visible at the call site.

Benefits:
- No accidental aliasing bugs
- Thread-safe reads without locks (each thread has its own copy)
- Compiler can optimise away copies via COW or register allocation
- Conformance to `Sendable` is automatic when all stored properties are `Sendable`

### Reference Semantics (class)

Classes use reference semantics: all copies of a variable point to the same heap-allocated instance. Mutation is visible from every reference, which enables shared mutable state but also introduces aliasing risk.

Key class-only capabilities:
- **Inheritance** — subclassing and method overriding
- **`deinit`** — run cleanup logic when the last reference drops
- **Identity** — `===` operator to check pointer equality
- **Objective-C interoperability** — `@objc`, `NSObject` subclassing, KVO

### Protocol Conformance Differences

Both structs and classes can conform to protocols, but only classes can conform to `AnyObject`-constrained protocols. Mutating protocol requirements can only be satisfied by structs via `mutating` method declarations; classes satisfy them with regular methods.

### Inheritance Trade-offs

Struct inheritance is not supported. Structs achieve polymorphism through protocol composition, which is more explicit and avoids the fragile base-class problem. Class hierarchies are powerful but carry the risk of:
- Broken `super.method()` chains
- Unexpected method overrides
- Liskov Substitution Principle violations

### Mutability Model

| Context | `struct` | `class` |
|---------|---------|---------|
| `let` binding | Fully immutable (no property mutation) | Reference immutable, properties still mutable |
| `var` binding | Properties mutable via `mutating` methods | Properties always mutable (if `var`) |
| In a `class` property | Mutable if the property is `var` | Same as above |

### Memory Layout

Structs are inline in their owning container (stack frame, class field, array buffer). Classes are always heap-allocated; the variable holds a pointer. Accessing a class property therefore requires a heap load, which can miss CPU cache under pressure.

## 4. Practical Usage

```swift
// ── Struct: plain model data ──────────────────────────────────
struct User {
    let id: UUID
    var displayName: String
    var email: String
}

var alice = User(id: UUID(), displayName: "Alice", email: "a@example.com")
var copy = alice          // independent copy
copy.displayName = "Bob"
print(alice.displayName)  // "Alice" — unaffected

// ── Class: identity-bearing object with lifecycle ─────────────
class NetworkSession {
    private(set) var requestCount = 0

    func send(_ request: URLRequest) {
        requestCount += 1
        // ... actual networking
    }

    deinit {
        print("Session deallocated after \(requestCount) requests")
    }
}

let session = NetworkSession()
let aliased = session     // same instance
aliased.send(URLRequest(url: URL(string: "https://example.com")!))
print(session.requestCount) // 1 — visible through both references

// ── Protocol-based polymorphism (struct alternative to inheritance)
protocol Shape {
    var area: Double { get }
}

struct Circle: Shape {
    let radius: Double
    var area: Double { .pi * radius * radius }
}

struct Rectangle: Shape {
    let width, height: Double
    var area: Double { width * height }
}

func printArea(_ shape: Shape) {
    print("Area: \(shape.area)")
}

// ── Class hierarchy (use when inheritance is genuinely needed)
class Animal {
    var name: String
    init(name: String) { self.name = name }
    func speak() -> String { "" }
}

class Dog: Animal {
    override func speak() -> String { "Woof" }
}

// ── Struct with mutating method ───────────────────────────────
struct Counter {
    private(set) var value = 0
    mutating func increment() { value += 1 }   // must be mutating
    mutating func reset()     { value = 0 }
}

var counter = Counter()
counter.increment()
print(counter.value)  // 1

// Note: `let counter = Counter()` would make increment() a compile error
```

## 5. Interview Questions & Answers

### Basic

**Q: What are the main differences between a struct and a class in Swift?**

A: Structs are value types — each variable gets its own independent copy. Classes are reference types — variables share a single heap-allocated instance. Classes additionally support inheritance, `deinit`, `===` identity comparison, and Objective-C interop. Structs are default-immutable when bound to `let`; a class `let` binding still allows mutation of its properties.

**Q: Why does Apple recommend preferring structs?**

A: Structs eliminate aliasing bugs, are naturally thread-safe for reads, and avoid accidental shared state. They also tend to have better performance due to stack allocation and cache locality. The Swift standard library uses structs for nearly all collection and model types.

### Hard

**Q: A `let` binding on a class instance doesn't prevent mutation of its properties — why?**

A: `let` makes the reference itself constant (you cannot reassign it to a different instance), but it does not affect the mutability of the instance's `var` properties. The class lives on the heap; `let` only locks the pointer. For a struct, `let` prevents any mutation because the struct's storage is inline with the variable — making the variable constant makes all nested properties constant too.

**Q: Can a struct conform to a protocol that has a class-only constraint? What happens?**

A: No. A protocol declared as `protocol Foo: AnyObject` (or with `class` keyword in older Swift) can only be conformed to by class types. Attempting to conform a struct to such a protocol is a compile-time error. The same applies to protocols in Combine (`ObservableObject`) which constrain conformers to classes.

### Expert

**Q: Describe a scenario where switching from a class to a struct causes a subtle correctness issue.**

A: Suppose a delegate pattern where multiple objects hold a reference to a shared delegate. If the delegate is converted from a class to a struct, every holder gets its own copy. Calling a mutating method on one copy doesn't update the others — effectively breaking the shared-notification contract. Similarly, observer patterns, undo managers, and any design relying on shared mutable state break when the shared object becomes a value type. The fix is to keep identity-bearing, lifecycle-owning objects as classes and only use structs for pure data.

## 6. Common Issues & Solutions

**Issue: Accidentally mutating a struct stored as `let`, causing a compile error.**

Solution: Change the binding to `var`, or if mutation should not be allowed, audit the design — `let` on a struct is enforcing the correct constraint.

**Issue: Class with many subclasses becomes hard to maintain (fragile base class).**

Solution: Refactor into protocol + composition. Extract shared behaviour into protocol extensions and use `struct` or `final class` conformers. Mark base classes `final` where subclassing is not intended.

**Issue: Thread-safety bug when sharing a class instance between queues.**

Solution: Protect mutable state with a serial `DispatchQueue`, `NSLock`, or — in Swift Concurrency — an `actor`. Alternatively, reconsider whether the type should be a struct, letting each thread work on its own copy.

**Issue: Class `deinit` not being called — suspected retain cycle.**

Solution: Add `[weak self]` or `[unowned self]` capture lists in closures that reference `self`. Use Instruments → Leaks or add a print statement in `deinit` to confirm deallocation.

## 7. Related Topics

- [Value vs Reference Types](value-vs-reference.md) — foundational semantics underlying struct vs class
- [Copy-on-Write](copy-on-write.md) — how structs avoid expensive copies
- [ARC Basics](arc-basics.md) — how class lifetimes are managed
- [Protocol-Oriented Programming](protocol-oriented-programming.md) — struct-based alternative to inheritance
- [Memory Management](../02-memory-management/index.md) — retain cycles and class lifetime
