# Stack vs Heap

## 1. Overview

Every value your program uses lives in one of two places: the **stack** or the **heap**. The stack is fast, automatically managed, and limited in size. The heap is flexible, manually managed via ARC, and can hold arbitrarily sized objects. Swift's type system strongly influences which region is used: value types (structs, enums) default to the stack; reference types (classes, actors) always live on the heap. Understanding allocation mechanics helps you write code that avoids unnecessary heap pressure, reduces ARC overhead, and achieves optimal cache performance.

## 2. Simple Explanation

Think of the stack as a stack of sticky notes on your desk — you add a note on top when you need it, and peel it off when you're done. It's instant. The heap is like a filing cabinet across the room — you can store anything there, in any order, but you have to walk over to it, find a free drawer, label it, and remember to file it back when done.

- **Stack**: instant access, automatic cleanup, limited size, last-in-first-out
- **Heap**: flexible, any size, ARC manages lifetime, slower access

## 3. Deep iOS Knowledge

### Stack Allocation

The stack is a contiguous region of memory per thread. Stack frames are pushed on function entry and popped on return. Allocating on the stack is O(1) — just decrement the stack pointer.

Properties:
- Allocation: move a register (stack pointer decrement) — effectively free
- Deallocation: automatic on scope exit (stack pointer increment)
- Size limit: typically 1–8 MB per thread (main thread: 8 MB on iOS, background: 512 KB)
- Locality: consecutive frames are adjacent in memory — excellent cache behaviour
- Thread safety: each thread has its own stack — no synchronisation needed

### Heap Allocation

The heap is a shared pool of memory managed by the allocator (`malloc`/`free` under the hood, plus ARC on top). Allocation involves finding a free block of the right size.

Properties:
- Allocation: `malloc` call, search free list, update metadata — ~50–100 ns typically
- Deallocation: ARC decrement; if zero, `free` — involves locking
- Size: limited only by available RAM
- Locality: heap objects can be scattered — may cause cache misses
- Thread safety: `malloc` uses a lock or per-CPU arenas; ARC retain/release uses atomics

### What Goes Where

| Type | Where | Notes |
|------|-------|-------|
| `struct` / `enum` local variable | Stack | Unless captured by escaping closure or stored in class |
| `class` instance | Heap | Always; variable holds a pointer |
| `actor` instance | Heap | Same as class |
| `struct` stored in a `class` property | Heap (inline) | Embedded in the class's allocation |
| `struct` captured by escaping closure | Heap | Compiler boxes it in a heap-allocated cell |
| `struct` in existential container (large) | Heap | Inline buffer overflows for >3 words; spills to heap |
| Function arguments (value types) | Stack (copy) | Unless `inout`, which passes a pointer |
| Global/static variables | Data segment | Neither stack nor heap |

### Escape Analysis

The Swift compiler performs **escape analysis** to determine whether a value escapes its defining scope. A value "escapes" if it is:
- Stored in a heap-allocated container (class property, array element on the heap)
- Captured by an escaping closure
- Passed as an `inout` to a function that stores it

If a value does not escape, the compiler can allocate it on the stack even if it has reference-type backing (e.g., small class instances in local scope with no escaping references).

### Existential Containers

When a value type is stored behind a protocol existential (`any Drawable`), Swift uses a 3-word inline buffer. Values that fit (≤ 3 machine words, ~24 bytes on 64-bit) are stored inline — no heap allocation. Values larger than 3 words are heap-allocated and the buffer stores a pointer. This is called "existential boxing."

```
Existential container layout (5 words total):
[ value word 0 | value word 1 | value word 2 | metadata pointer | witness table pointer ]
```

Passing large structs through protocol existentials repeatedly can cause unexpected heap allocations and performance degradation.

### Performance Impact

Cache misses from heap indirection are often more costly than the ARC operations themselves. A struct stored inline in an array is contiguous in memory — iterating is cache-friendly. An array of class pointers requires following each pointer to a potentially distant heap location — cache-unfriendly.

Use Instruments → Allocations to measure heap allocation rate. Instruments → Time Profiler with "hide system libraries" off can reveal cache miss hotspots.

## 4. Practical Usage

```swift
// ── Stack allocation: struct local variable ───────────────────
func computeDistance() -> Double {
    struct Point { var x, y: Double }       // on the stack
    let p1 = Point(x: 0, y: 0)
    let p2 = Point(x: 3, y: 4)
    return sqrt((p2.x - p1.x) * (p2.x - p1.x) + (p2.y - p1.y) * (p2.y - p1.y))
}

// ── Heap allocation: class instance ──────────────────────────
class Node {
    var value: Int
    var next: Node?
    init(_ value: Int) { self.value = value }
}

let head = Node(10)  // always on the heap

// ── Struct forced to heap: captured by escaping closure ───────
func makeCounter() -> () -> Int {
    var count = 0  // escapes to heap when captured below
    return {
        count += 1  // count is in a heap-allocated box shared here
        return count
    }
}

let counter = makeCounter()
print(counter())  // 1
print(counter())  // 2

// ── Existential boxing: small vs large struct ─────────────────
struct SmallPoint { var x, y: Double }        // 2 words → inline in existential
struct BigTransform { var matrix: (Double, Double, Double, Double,
                                   Double, Double, Double, Double,
                                   Double, Double, Double, Double,
                                   Double, Double, Double, Double) }  // 16 words → heap

func printArea(_ shape: any CustomStringConvertible) { print(shape) }

let p = SmallPoint(x: 1, y: 2)       // no heap alloc when stored in existential
// let t = BigTransform(...)          // heap alloc when stored in existential

// ── Avoid existential boxing with generics ────────────────────
// Prefer generic parameter (static dispatch, no boxing):
func processShape<S: CustomStringConvertible>(_ shape: S) {
    print(shape)  // S is known at compile time; no existential box
}

processShape(p)   // SmallPoint, no boxing, potentially inlined

// ── Stack size awareness for recursive algorithms ─────────────
// Deep recursion consumes stack frames — risk of stack overflow.
// Iterative solutions with explicit stacks use heap (safe for deep trees):
func iterativeDepth(of node: Node?) -> Int {
    var stack: [(Node, Int)] = []           // heap-allocated array
    if let root = node { stack.append((root, 1)) }
    var maxDepth = 0
    while !stack.isEmpty {
        let (current, depth) = stack.removeLast()
        maxDepth = Swift.max(maxDepth, depth)
        if let next = current.next { stack.append((next, depth + 1)) }
    }
    return maxDepth
}

// ── Measuring allocations ─────────────────────────────────────
// In code (rough measurement, not for production):
import Foundation

func countAllocations(block: () -> Void) {
    // Use Instruments → Allocations for accurate measurement.
    // This pattern is for illustrative purposes only.
    let before = mach_absolute_time()
    block()
    let after = mach_absolute_time()
    print("Elapsed: \(after - before) mach ticks")
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between stack and heap allocation?**

A: The stack is a per-thread, LIFO region where local variables and function frames are allocated by simply adjusting a pointer — extremely fast and automatically reclaimed on scope exit. The heap is a shared pool managed by `malloc`/ARC, used for objects that need dynamic lifetimes or sizes. Heap allocation requires finding free memory, updating metadata, and eventually running ARC's retain/release — slower and potentially contended.

**Q: Do Swift structs always live on the stack?**

A: No, structs default to the stack for local variables, but end up on the heap when: stored as a property of a class (embedded in the class's heap allocation), captured by an escaping closure (boxed into a heap cell), or stored in a heap-allocated collection. The compiler uses escape analysis to determine the actual allocation site.

### Hard

**Q: What is an existential container and when does it cause a heap allocation?**

A: When a value type is used where an `any Protocol` existential is expected, Swift stores it in a fixed-size container (5 machine words). The first 3 words are an inline value buffer. If the value fits (≤ 3 words / ~24 bytes on 64-bit), no extra allocation occurs. If the value is larger, Swift allocates a separate heap buffer and stores a pointer in the inline buffer. This "existential boxing" happens silently and can cause unexpected allocation spikes when large structs are passed through generic protocol boundaries.

**Q: How does escape analysis in Swift decide whether to allocate a local variable on the stack or heap?**

A: The Swift compiler analyses the variable's uses through the control flow graph. If the variable never "escapes" — never stored in a class property, never captured by an escaping closure, never passed to a function that stores it beyond the call — it can be allocated on the stack. Once the compiler detects an escape path, it inserts a heap allocation and modifies all subsequent accesses to go through the heap pointer. In optimised builds (`-O`), the compiler may partially eliminate boxes when escape paths are provably unreachable or when the value is small enough to pass in registers.

### Expert

**Q: Describe a situation where switching from `class` to `struct` increases heap allocations, not decreases them.**

A: When a struct contains reference-type fields (class instances), copying the struct copies the struct's inline fields but the reference-type fields remain on the heap — their retain counts simply increase. If the struct is large and copied frequently (e.g., placed in a heterogeneous array as `any Protocol` existential that overflows the inline buffer), switching from a class to a struct introduces existential boxing on each use. Another scenario: a struct with COW semantics (custom copy-on-write) that is copied in many places will trigger a heap allocation of the backing buffer on each write — potentially more allocations than a single heap-allocated class instance that mutates in place. The correct tool is Instruments → Allocations, not intuition.

## 6. Common Issues & Solutions

**Issue: Stack overflow crash in a recursive function processing deep data structures.**

Solution: Replace recursion with an iterative algorithm using an explicit stack (a heap-allocated `Array` or `LinkedList`). Heap allocations can grow as large as available RAM; the thread stack is limited (~512 KB on background threads).

**Issue: Performance regression when protocol-typed parameter causes heap allocation in a hot loop.**

Solution: Replace `any Protocol` existential with a generic parameter `<T: Protocol>`. This eliminates existential boxing and enables static dispatch and specialisation. Verify with Instruments → Allocations that the allocation rate drops.

**Issue: Large struct stored in a dictionary as `[String: any Codable]` causes unexpected allocations.**

Solution: Use a concrete type parameter or typed wrapper to avoid existential boxing. If heterogeneous storage is required, consider an enum with associated values — it stores inline without boxing.

**Issue: App uses more memory than expected — Allocations shows many small heap objects.**

Solution: Look for frequently created class instances that could be structs. Check for closure boxes from frequently-created escaping closures. Use object pooling for high-frequency short-lived objects. Review whether protocol existentials in hot paths could be replaced with generics.

## 7. Related Topics

- [ARC](arc.md) — ARC manages heap object lifetimes
- [Value vs Reference Types](../01-swift-language/value-vs-reference.md) — how Swift's type system maps to stack/heap
- [Copy-on-Write](../01-swift-language/copy-on-write.md) — COW uses a heap buffer inside a stack-allocated struct
- [Generics](../01-swift-language/generics.md) — generics avoid existential boxing via static dispatch
- [Performance](../12-performance/index.md) — Instruments profiling for allocation analysis
