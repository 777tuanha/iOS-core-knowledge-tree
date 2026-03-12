# ARC Basics

## 1. Overview

Automatic Reference Counting (ARC) is Swift's memory management model for class instances (reference types). The compiler automatically inserts `retain` and `release` calls at compile time — there is no runtime garbage collector. When an object's reference count drops to zero, ARC calls `deinit` and frees the memory. Understanding ARC is fundamental to writing leak-free iOS applications and reasoning about object lifetimes.

## 2. Simple Explanation

Think of a shared rental car. Every person who picks up the keys increments a counter at the rental desk. When someone returns the keys, the counter drops. When the counter reaches zero — no one has the keys anymore — the car goes back to the lot and is recycled.

ARC works the same way with objects:
- Every new reference to an object → counter goes up (retain)
- Reference goes away (variable deallocated, reassigned, goes out of scope) → counter goes down (release)
- Counter hits zero → `deinit` called, memory freed

## 3. Deep iOS Knowledge

### Retain / Release Mechanics

ARC operates at **compile time**. The compiler analyses your source code and inserts `objc_retain` and `objc_release` calls at the appropriate points. There is no stop-the-world garbage collection pause — memory is freed immediately and deterministically when the last reference drops.

Key operations:
- `retain` — increment the reference count
- `release` — decrement the reference count; if it reaches 0, deallocate
- `autorelease` — defer the release until the current `AutoreleasePool` drains (mainly relevant in Objective-C interop)

### Strong References (Default)

Every regular (`var` or `let`) reference to a class instance is a **strong reference**. As long as at least one strong reference exists, the object stays alive.

```
Object lifecycle:
  init called → retain count = 1
  new reference assigned → retain count = 2
  one reference goes out of scope → retain count = 1
  last reference goes out of scope → retain count = 0 → deinit → freed
```

### `deinit`

Classes can define a `deinit` method that runs just before the instance is freed. Use it to:
- Release C-level resources (`free`, `close`)
- Remove notification centre observers
- Cancel timers or network requests
- Print debug messages to confirm deallocation

`deinit` is not available on structs or enums (they are not reference-counted).

### Retain Count Inspection

You should not rely on a specific retain count number in production code (it is an implementation detail), but during debugging:
- Instruments → Allocations track object lifetimes
- Instruments → Leaks detect objects that are never freed
- `CFGetRetainCount` can print approximate counts (avoid in production)

### ARC vs Garbage Collection

| Feature | ARC | GC (e.g., JVM) |
|---------|-----|----------------|
| When memory is freed | Immediately on last release | Non-deterministic |
| Pause / latency | None | Stop-the-world pauses possible |
| Overhead | Per-retain/release instruction | Periodic scan overhead |
| Cycles | Must be broken manually | GC can collect cycles |
| Determinism | `deinit` called at known point | Finalizer timing uncertain |

### ARC in Multithreading

Retain/release operations are atomic on all Apple platforms — incrementing and decrementing the retain count is thread-safe. However, **reading and writing the object's own properties is not automatically thread-safe**. ARC only protects the count itself.

## 4. Practical Usage

```swift
// ── Basic lifecycle ───────────────────────────────────────────
class Connection {
    let id: Int
    init(id: Int) {
        self.id = id
        print("Connection \(id) created")   // retain count = 1
    }
    deinit {
        print("Connection \(id) released")  // count hit 0
    }
}

do {
    let c1 = Connection(id: 1)  // count = 1
    let c2 = c1                 // count = 2 (strong reference)
    _ = c2                      // suppress unused-variable warning
}
// scope ends → c2 goes away (count = 1) → c1 goes away (count = 0) → deinit

// ── Strong reference keeps object alive ──────────────────────
class Cache {
    var storage: [String: Data] = [:]
}

var primary: Cache? = Cache()   // count = 1
var secondary = primary         // count = 2
primary = nil                   // count = 1 — still alive
secondary = nil                 // count = 0 → deinit

// ── deinit for resource cleanup ──────────────────────────────
class FileHandle {
    private let descriptor: Int32

    init(path: String) {
        descriptor = open(path, O_RDONLY)
    }

    deinit {
        close(descriptor)   // deterministic resource release
    }
}

// ── Retain cycle (problem — will not deallocate) ──────────────
class Parent {
    var child: Child?
    deinit { print("Parent freed") }
}

class Child {
    var parent: Parent?         // strong → creates a cycle
    deinit { print("Child freed") }
}

var p: Parent? = Parent()
var c: Child?  = Child()
p!.child = c                   // p → c, count(c) = 2
c!.parent = p                  // c → p, count(p) = 2
p = nil                        // count(p) = 1 — NOT freed
c = nil                        // count(c) = 1 — NOT freed
// Neither deinit is called — leak!

// Fix: make one side weak (see weak-vs-unowned.md)
// var parent: weak Parent?

// ── Autorelease pool (Obj-C interop / tight loops) ────────────
for _ in 0..<10_000 {
    autoreleasepool {
        // Any Obj-C objects autoreleased inside here are freed
        // at the end of each iteration rather than at the end
        // of the outer function's autorelease pool.
        let image = UIImage(named: "large_asset")
        _ = image?.pngData()
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is ARC and how does it differ from garbage collection?**

A: ARC (Automatic Reference Counting) is a compile-time memory management strategy. The compiler inserts retain and release calls around object usage. Memory is freed immediately and deterministically when the reference count reaches zero. Garbage collectors use a runtime scan to find unreachable objects and free them non-deterministically, which can cause pause latency. ARC cannot collect reference cycles; garbage collectors can.

**Q: When is `deinit` called?**

A: `deinit` is called automatically by ARC exactly when the reference count of a class instance drops to zero — i.e., all strong references to the instance have gone away. It is called synchronously on the thread that released the last reference. There is no guarantee about which thread that is, so `deinit` code must not assume the main thread.

### Hard

**Q: Why can't ARC automatically break retain cycles?**

A: ARC is a reference-counting scheme, not a tracing garbage collector. It only tracks counts, not the object graph. A cycle (A → B → A) keeps both counts at ≥ 1 indefinitely — neither drops to zero — so neither object is freed. Detecting cycles requires graph traversal, which ARC deliberately avoids to maintain O(1) retain/release cost. The programmer must break cycles explicitly using `weak` or `unowned` references.

**Q: Is retain/release thread-safe in Swift?**

A: The retain and release operations themselves are atomic — they use lock-free atomic instructions on the reference count field. So ARC-level operations are thread-safe. However, the data stored inside the object is not automatically thread-safe. If two threads simultaneously read and write a property, that is a data race. ARC prevents use-after-free bugs (by keeping the object alive) but does not prevent data races within the object.

### Expert

**Q: Explain how the Swift compiler decides where to insert retain and release calls.**

A: The compiler performs a dataflow analysis pass called ARC optimisation. It tracks each reference through the control flow graph and inserts:
- A `retain` at the point where a strong reference is created (variable initialisation, function argument passing)
- A `release` at the last use of each reference within a scope

The optimiser then applies several passes:
1. **Redundant retain/release elimination** — if an object is retained and released with no intervening escaping call, the pair can be removed.
2. **Code motion** — release calls can be moved earlier (as soon as the last use) to free memory sooner.
3. **Ownership conventions** — Swift uses `+1` ownership for returned values from `init` and factory methods, and `+0` (borrowing) for function arguments, reducing retain/release traffic on function boundaries.

The result is that Swift typically requires fewer retain/release calls than Objective-C's manual reference counting.

## 6. Common Issues & Solutions

**Issue: Object not being deallocated — `deinit` never printed.**

Solution: Add a `deinit` print statement and check with Instruments → Leaks. The most common cause is a retain cycle via a strong closure capture or a strong delegate reference. Use `[weak self]` in closures and `weak var delegate` for delegate properties.

**Issue: `deinit` called on the wrong thread, causing main-thread-only UIKit operations to crash.**

Solution: Dispatch main-thread work in `deinit` to `DispatchQueue.main.async`. Alternatively, redesign so that cleanup that needs the main thread happens in an explicit lifecycle method (`viewDidDisappear`, `cancel()`) rather than `deinit`.

**Issue: High memory usage in a tight loop processing many objects.**

Solution: Wrap loop body in `autoreleasepool { }` to drain Objective-C autoreleased objects (e.g., `UIImage`, `NSData`) after each iteration rather than letting them accumulate until the outer pool drains.

**Issue: Retain count unexpectedly high when debugging — object never freed.**

Solution: Use Instruments → Allocation track + "Record Reference Counts" to see every retain/release and which call stack performed them. Look for unexpected retains from closures, collections, or notification observers.

## 7. Related Topics

- [Weak vs Unowned](weak-vs-unowned.md) — breaking retain cycles with non-strong references
- [Retain Cycles](../02-memory-management/retain-cycles.md) — patterns that create cycles and how to fix them
- [ARC Deep Dive](../02-memory-management/arc.md) — compiler insertions, assembly inspection, Instruments
- [Struct vs Class](struct-vs-class.md) — why value types don't need ARC
- [Memory Management](../02-memory-management/index.md) — full memory section overview
