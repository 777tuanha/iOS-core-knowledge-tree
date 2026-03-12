# ARC — Deep Dive

## 1. Overview

Automatic Reference Counting (ARC) is Swift's compile-time memory management system for class instances. The compiler analyses object lifetimes and inserts `retain` (increment count) and `release` (decrement count) instructions at the Swift Intermediate Language (SIL) level. When the count reaches zero, `deinit` runs and the memory is freed — deterministically, with no garbage-collection pause. This topic covers how ARC works internally, what the compiler does, how ownership conventions reduce retain/release traffic, and how to use Instruments to find leaks and unexpected retentions.

## 2. Simple Explanation

Think of ARC as a library's borrowing desk. Every time someone borrows a book, the desk stamps a card. When it's returned, the stamp is crossed out. When zero stamps remain, the book goes back on the shelf (freed). The desk (compiler) automatically adds the stamp and cross-out operations when you write borrow/return code — you never do it manually.

The "desk" operates at compile time. By the time your app runs, the stamp-and-cross-out instructions are already baked into the machine code. There is no runtime scanning or pausing.

## 3. Deep iOS Knowledge

### Swift Intermediate Language (SIL)

Before compiling to machine code, the Swift compiler produces SIL — a typed, SSA-form IR. ARC operations appear explicitly in SIL:

- `strong_retain` — increment the retain count
- `strong_release` — decrement; if 0, call `deinit` and free
- `load [copy]` — load a value and retain it
- `destroy_value` — release at end of scope

You can inspect SIL with `swiftc -emit-sil -O source.swift | grep retain`.

### ARC Optimisation Passes

The compiler runs several ARC-specific optimisation passes:

1. **Redundant retain/release elimination** — a pair `retain(x); release(x)` with no intervening escaping call is removed entirely.
2. **Code motion** — `release` calls are moved as early as possible (after the last use of the value), freeing memory sooner.
3. **Peephole optimisations** — adjacent operations on the same object are merged.
4. **Ownership SSA (OSSA)** — the modern SIL pipeline assigns explicit ownership to every value, enabling aggressive elimination of redundant ARC operations.

### Ownership Conventions

Swift uses **+0 / +1 ownership conventions** to reduce retain/release traffic on function boundaries:

- **+0 (borrow/guaranteed)**: the callee borrows the value; no retain needed at the call site. Used for most function arguments.
- **+1 (owned)**: the callee takes ownership. Used for `init` returns, `@owned` parameters, and closures that capture values.

These conventions are part of Swift's calling convention and are visible in SIL as `@guaranteed` and `@owned` annotations.

### Reference Count Storage

The reference count is stored in the object's header alongside the type metadata pointer. Swift uses a 64-bit header word on 64-bit platforms, with bits partitioned for strong, unowned, and weak counts. When the strong count hits zero, the object is destroyed but the header (side table) may remain until the weak count also drops to zero.

### Autorelease Pools

`autoreleasepool { }` defers the release of Objective-C objects (and some bridged Swift objects) until the pool drains. Used in:
- Loops that create many short-lived Obj-C objects (e.g., `UIImage`, `NSData`)
- Background threads (which don't have a default autorelease pool beyond the run-loop drain)
- Performance-sensitive code interoperating with Obj-C frameworks

### Instruments: Finding Leaks

**Instruments → Leaks** template:
1. Run app under the Leaks instrument
2. Leaks tool periodically scans the heap for objects with no reachable strong references
3. A detected leak shows the object type, allocation backtrace, and current retain count
4. Click the leak to see the reference graph

**Instruments → Allocations** template for non-leak over-retention:
1. Enable "Record Reference Counts" in Allocations settings
2. Find the object in the object list
3. Click "History" to see every retain/release and its call stack
4. Look for unexpected retains that keep the count above zero longer than expected

## 4. Practical Usage

```swift
// ── Observing deinit to verify deallocation ────────────────────
class Resource {
    let name: String
    init(name: String) {
        self.name = name
        print("\(name) allocated")
    }
    deinit {
        print("\(name) deallocated")  // verify this fires
    }
}

// ── Scope-based lifetime ───────────────────────────────────────
func loadTemporaryData() {
    let r = Resource(name: "TempData")  // retain count = 1
    process(r)
    // r goes out of scope here → release → deinit
}

func process(_ r: Resource) {
    // r is passed +0 (borrow) — no extra retain in most cases
    print("Processing \(r.name)")
}

// ── Autorelease pool in a loop ─────────────────────────────────
func processImages(paths: [String]) {
    for path in paths {
        autoreleasepool {
            // UIImage is bridged Obj-C; autoreleased objects accumulate
            // without the pool, then drain at end of function.
            // With the pool, each image is released after each iteration.
            guard let image = UIImage(contentsOfFile: path) else { return }
            _ = image.jpegData(compressionQuality: 0.8)
        }
    }
}

import UIKit

// ── Inspecting SIL to verify ARC behaviour ────────────────────
// Run in terminal (not compiled into app):
// swiftc -emit-sil -O myfile.swift | grep -E "strong_retain|strong_release"
// Absence of retain/release on a hot path confirms ARC elimination.

// ── Weak reference to confirm deallocation in tests ───────────
class ViewModel {
    deinit { print("ViewModel freed") }
}

func testDeallocation() {
    weak var weakVM: ViewModel?
    do {
        let vm = ViewModel()
        weakVM = vm
        // use vm...
    } // vm deallocated here
    assert(weakVM == nil, "ViewModel leaked — check for retain cycles")
}

// ── Detecting retain via CFGetRetainCount (debug only) ────────
func debugRetainCount(_ obj: AnyObject) {
    // CFGetRetainCount is approximate and implementation-specific;
    // use only for quick investigation, never in production logic.
    print("Approx retain count: \(CFGetRetainCount(obj))")
}

// ── Background thread autorelease pool ────────────────────────
func backgroundWork() {
    DispatchQueue.global().async {
        // Background threads have no run-loop; autorelease objects
        // accumulate without an explicit pool.
        autoreleasepool {
            for _ in 0..<1000 {
                let s = NSString(string: "hello")
                _ = s.uppercased
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: How does ARC know when to free an object?**

A: ARC tracks a reference count for every class instance. Each strong reference assignment increments the count (retain). Each reference going away — variable going out of scope, being reassigned, or set to `nil` — decrements the count (release). When the count reaches zero, ARC calls `deinit` synchronously and frees the memory. The compiler inserts these retain/release calls at compile time based on static analysis of the code.

**Q: What is an autorelease pool and when do you need one?**

A: An autorelease pool defers the release of Objective-C-style autoreleased objects until the pool drains. On the main thread, the run loop automatically drains the pool each cycle. You need to add your own `autoreleasepool { }` in tight loops that create many Obj-C objects (e.g., `UIImage` in a processing loop) to prevent peak memory accumulation, and on background threads that lack a run loop.

### Hard

**Q: What are the +0 and +1 ownership conventions in Swift's ARC?**

A: They describe who is responsible for balancing the retain count at function boundaries. +1 (owned) means the callee receives an already-retained value and is responsible for releasing it — used for initialiser returns, `@owned` parameters, and capturing closures. +0 (guaranteed/borrow) means the callee borrows the value without a new retain — the caller guarantees the object stays alive for the duration of the call. Most function arguments use +0, which eliminates paired retain/release at call sites and is a significant optimisation in tight call chains.

**Q: How does the compiler eliminate redundant retain/release pairs?**

A: The ARC optimiser in the SIL pipeline performs dataflow analysis. If it can prove that between a `strong_retain` and the matching `strong_release` no code path causes the object to be deallocated (no calls to functions that might release it, no stores to unknown memory), the pair is redundant and can be removed. This is called retain/release pair elimination. The OSSA (Ownership SSA) pipeline in modern Swift enables even more aggressive elimination by encoding ownership precisely in the IR.

### Expert

**Q: Describe how the side table interacts with weak and unowned reference counts.**

A: When a weak reference is first taken to an object, Swift allocates a **side table** — a separate heap block associated with the object. The side table stores:
- The object pointer
- A weak reference count (number of active weak references)
- An unowned reference count

When the strong count reaches zero, the object's memory is freed (`deinit` is called), but the side table persists until the weak count also reaches zero. Accessing a `weak` reference checks the side table and returns `nil` if the strong count is zero. The side table is freed when both strong and weak counts are zero. `unowned` safe references use a separate inline count; accessing them after the strong count is zero traps. This design allows ARC to zero all weak references atomically without scanning the entire heap.

## 6. Common Issues & Solutions

**Issue: Memory grows unboundedly during image processing in a loop.**

Solution: Wrap the loop body in `autoreleasepool { }`. Instruments → Allocations will show memory spiking to a peak at the end of the loop instead of growing linearly — confirming the pool is working.

**Issue: App leaks memory — Instruments → Leaks shows objects accumulating.**

Solution: Click the leak entry to see the reference graph. Common causes: retain cycles in closures (missing `[weak self]`), strong delegate references (should be `weak var`), timer invalidation missed in `deinit`. Fix the cycle and re-run Leaks.

**Issue: `deinit` is called on a background thread, causing UIKit crash.**

Solution: Move UIKit work to `DispatchQueue.main.async`. Better: ensure UIKit-touching objects are only released on the main thread by keeping their last strong reference on the main thread (e.g., in a main-thread view controller or view model).

**Issue: Retain count unexpectedly high — object not freed after going out of scope.**

Solution: Enable "Record Reference Counts" in Instruments → Allocations and inspect the history. Look for closures that captured the object, collections (arrays, dictionaries, sets) that still hold it, or notification centre observers that retain the observer object.

## 7. Related Topics

- [Retain Cycles](retain-cycles.md) — patterns that prevent deallocation
- [Closures & Capture Lists](closures-capture-lists.md) — how closures affect retain counts
- [Stack vs Heap](stack-vs-heap.md) — ARC only applies to heap-allocated class instances
- [ARC Basics](../01-swift-language/arc-basics.md) — foundational overview in the Swift Language section
- [Weak vs Unowned](../01-swift-language/weak-vs-unowned.md) — non-strong references to break cycles
