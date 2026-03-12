# Value vs Reference Types

## 1. Overview

Swift divides all types into two fundamental categories: **value types** and **reference types**. Value types (structs, enums, tuples) are copied when assigned or passed. Reference types (classes, actors, closures) share a single instance through a reference. This distinction affects memory layout, thread safety, identity semantics, and overall application design.

## 2. Simple Explanation

Imagine a value type like a sticky note. When you give someone a copy, they get their own note — changes they make don't affect yours. A reference type is like a shared Google Doc with a link. Everyone holding the link sees the same document, and any change is visible to all.

In Swift:
- `struct` → sticky note (value type)
- `class` → Google Doc link (reference type)

## 3. Deep iOS Knowledge

### Value Types

Value types are allocated on the **stack** by default (though large structs or those inside heap-allocated containers can end up on the heap). Stack allocation is extremely fast — it's just a pointer offset. Value semantics guarantee that every variable holds its own independent copy.

Swift standard library collections (`Array`, `Dictionary`, `String`) are structs with **copy-on-write (COW)** semantics — they appear to copy eagerly but share storage until a mutation is needed.

Structs cannot participate in reference cycles, making them inherently safer in concurrent contexts (though `actor` isolation is still needed for mutable state shared across tasks).

### Reference Types

Classes use **reference counting (ARC)** for lifetime management. Each `init` increments the retain count; each deinit decrements it. When the count reaches zero, `deinit` is called and memory is released.

Multiple references to the same instance mean mutations are visible everywhere that reference exists — useful for shared state but dangerous without careful synchronisation.

Key class-only capabilities:
- Inheritance and polymorphism
- `deinit`
- Identity comparison (`===`)
- Objective-C interoperability

### When Swift Uses the Heap for Value Types

- A value type stored in a class property lives on the heap
- Closures that capture value types box them on the heap
- Existential containers for large value types use heap allocation

### Thread Safety

Value types copied between threads are safe because each thread owns its copy. Reference types require explicit synchronisation (locks, serial queues, `actor`) to avoid data races.

## 4. Practical Usage

```swift
// Value type — each variable is independent
struct Point {
    var x: Double
    var y: Double
}

var a = Point(x: 0, y: 0)
var b = a       // b is a copy
b.x = 10
print(a.x)      // 0 — a is unaffected

// Reference type — shared identity
class Counter {
    var count = 0
    func increment() { count += 1 }
}

let c1 = Counter()
let c2 = c1     // c2 points to the same instance
c2.increment()
print(c1.count) // 1 — mutation visible through c1

// Identity check — only valid for reference types
print(c1 === c2) // true

// Mixed: value type containing reference type
struct Config {
    var name: String
    var cache: NSCache<NSString, AnyObject>  // reference type inside struct
}
// Copying Config copies the struct, but `cache` is still shared!
// This is a "non-obvious sharing" pitfall.

// Protocol to abstract over both
protocol Resettable {
    mutating func reset()
}

extension Point: Resettable {
    mutating func reset() { x = 0; y = 0 }
}

extension Counter: Resettable {
    func reset() { count = 0 }   // no `mutating` needed for class
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a struct and a class in Swift?**

A: Structs are value types — copied on assignment. Classes are reference types — multiple variables can point to the same instance. Classes support inheritance and have `deinit`; structs do not. Classes require explicit memory management through ARC.

**Q: When would you choose a struct over a class?**

A: Prefer structs when the data is simple, should not be shared, and benefits from value semantics (e.g., model objects, view models in SwiftUI). Use classes when you need inheritance, shared mutable state, or Objective-C interop.

### Hard

**Q: A struct containing a class property is copied — is the copy truly independent?**

A: No. Copying the struct gives each copy its own struct storage, but the class property is a reference — both copies share the same class instance. Mutations to the class instance are visible from all struct copies. This is called "impure value semantics" or "non-obvious aliasing." To achieve true independence you must deep-copy the class instance, for example by implementing a copy method or using a value-type wrapper with COW.

**Q: How does Swift decide whether to allocate a value type on the stack or heap?**

A: Swift uses escape analysis. If a value does not escape the current scope (not stored in a global, not captured by a heap-allocated closure, not stored in a class property), the compiler allocates it on the stack. If it escapes, the value is boxed on the heap. Large value types inside existential containers (`any Protocol`) are always heap-allocated via the existential box.

### Expert

**Q: How do value and reference semantics interact with Swift's `Sendable` and structured concurrency model?**

A: Swift 5.5+ enforces data-race safety at compile time. `Sendable` marks types safe to pass across actor boundaries. Structs with all-`Sendable` properties are implicitly `Sendable` because each actor gets its own copy. Classes must either be immutable (`let` properties only) or be `actor`-isolated to be `Sendable`. Passing a non-`Sendable` class across actor boundaries is a compile-time warning (soon error), preventing data races. Value types with COW, like `Array`, are `Sendable` because the copy mechanism ensures independent buffers when the type parameter is `Sendable`.

## 6. Common Issues & Solutions

**Issue: Unexpected sharing when copying a struct that contains a class property.**

Solution: Audit every `struct` for reference-type properties. If mutation isolation is required, use COW by wrapping the class in a private holder and checking `isKnownUniquelyReferenced` before mutating.

**Issue: Retain cycles with closures capturing `self` of a class.**

Solution: Use `[weak self]` or `[unowned self]` capture lists in closures. Prefer `[weak self]` when the object may be deallocated before the closure fires.

**Issue: Treating a class as if it has value semantics and getting aliasing bugs.**

Solution: Make the type a `struct` if value semantics are needed, or define a `clone()` / copy method and use it explicitly. Document sharing intent clearly.

**Issue: Large value types causing excessive stack pressure.**

Solution: If a struct is over ~64–128 bytes and is frequently passed around, consider using a COW wrapper (like Swift's standard collections) or switching to a class.

## 7. Related Topics

- [Copy-on-Write](copy-on-write.md) — how Swift avoids unnecessary copies of value types
- [Memory Management](../02-memory-management/index.md) — ARC, retain cycles, and weak references
- [Concurrency](../03-concurrency/index.md) — Sendable, actors, and thread safety
