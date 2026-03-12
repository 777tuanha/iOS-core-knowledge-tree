# Copy-on-Write

## 1. Overview

Copy-on-write (COW) is an optimization strategy used by Swift's standard library value types — `Array`, `Dictionary`, `Set`, and `String` — to avoid expensive copies when a value is shared but not mutated. Instead of copying storage immediately on assignment, multiple value-type variables share the same underlying buffer until one of them needs to mutate it. Only then is the buffer copied.

## 2. Simple Explanation

Imagine two people sharing a printed document. As long as neither writes on it, they can share the same physical copy. The moment one person wants to mark it up, the photocopy machine makes them a private copy first, and only then do they write on it.

Swift collections work the same way:

```swift
var a = [1, 2, 3]
var b = a       // no copy yet — a and b share the same buffer
b.append(4)     // NOW b gets its own private copy before mutating
```

`a` still contains `[1, 2, 3]`. The copy was deferred until it was actually needed.

## 3. Deep iOS Knowledge

### How COW Works Internally

Swift uses a **class-based buffer** inside the struct. Both the struct value and any copies share a reference to this buffer (a `ManagedBuffer` or similar). The key function is:

```swift
isKnownUniquelyReferenced(&buffer)
```

Before any mutation, the collection checks whether the buffer is uniquely referenced (i.e., only this variable holds it). If yes, it mutates in place. If no (shared), it copies the buffer first.

This means:
- **Reading** is always O(1) — no copy, just access through the shared buffer.
- **Mutating** shared storage is O(n) on first mutation, then O(1) for further mutations (the copy is now unique).

### ARC's Role

The reference count on the internal buffer drives COW. ARC increments the retain count each time a struct containing a buffer is copied. `isKnownUniquelyReferenced` returns `true` only when the retain count is exactly 1. Non-Swift (Objective-C) references are not counted, so `isUniquelyReferenced` only considers Swift references.

### Existentials and COW

When stored in an existential container (`any Sequence`), a collection may be heap-allocated. Accessing such values through a protocol witness table adds indirection but does not disable COW — the buffer sharing still applies.

### Performance Profile

| Operation         | Unique Buffer | Shared Buffer     |
|-------------------|---------------|-------------------|
| Read element      | O(1)          | O(1)              |
| Append (amortized)| O(1)          | O(n) first time   |
| Assignment        | O(1)          | O(1)              |
| Copy (eager)      | not triggered | not triggered     |

### Bridging to Objective-C

When a Swift `Array` bridges to `NSArray`, Swift may eagerly copy the buffer because Objective-C objects don't participate in Swift's `isKnownUniquelyReferenced` check. This is a common performance footgun when passing Swift arrays to legacy Obj-C APIs.

## 4. Practical Usage

```swift
// ── Standard library COW (automatic) ──────────────────────────

var original = [1, 2, 3, 4, 5]
var copy = original          // no buffer copy yet

copy[0] = 99                 // buffer copied here (COW triggers)

print(original[0])           // 1 — original unchanged
print(copy[0])               // 99

// ── Custom COW value type ──────────────────────────────────────

// Step 1: reference-type storage
final class _DataBuffer {
    var values: [Int]
    init(_ values: [Int]) { self.values = values }
    func copy() -> _DataBuffer { _DataBuffer(values) }
}

// Step 2: value-type wrapper
struct DataStore {
    private var _buffer: _DataBuffer

    init(_ values: [Int] = []) {
        _buffer = _DataBuffer(values)
    }

    // Ensure unique buffer before mutation
    private mutating func ensureUnique() {
        if !isKnownUniquelyReferenced(&_buffer) {
            _buffer = _buffer.copy()
        }
    }

    var count: Int { _buffer.values.count }

    subscript(index: Int) -> Int {
        get { _buffer.values[index] }
        set {
            ensureUnique()        // copy only if shared
            _buffer.values[index] = newValue
        }
    }

    mutating func append(_ value: Int) {
        ensureUnique()
        _buffer.values.append(value)
    }
}

// Usage
var store1 = DataStore([10, 20, 30])
var store2 = store1          // shares buffer
store2.append(40)            // buffer copied here
print(store1.count)          // 3 — store1 unchanged
print(store2.count)          // 4

// ── Detecting unintended copies in debug builds ───────────────

// Use Instruments → Allocations to track buffer heap allocations.
// A spike in allocations during a tight loop often indicates missed COW.
```

## 5. Interview Questions & Answers

### Basic

**Q: What is copy-on-write and which Swift types use it?**

A: COW is a lazy-copy optimization where multiple variables share the same backing storage until a mutation occurs. Swift's standard collection types — `Array`, `Dictionary`, `Set`, and `String` — implement COW. Assignment is O(1); the actual buffer copy only happens on the first mutation of a shared value.

**Q: Is copying a Swift `Array` always expensive?**

A: No. Due to COW, assigning an array to a new variable is O(1) — only a pointer to the shared buffer is copied. The buffer is duplicated only when one of the owners mutates it, and only at that point does the cost become O(n).

### Hard

**Q: How would you implement COW in a custom Swift type?**

A: Wrap mutable state in a `final class` (the buffer). The struct holds a reference to this class. Before every `mutating` operation, call `isKnownUniquelyReferenced(&buffer)`. If it returns `false` (buffer is shared), copy the class instance first. This pattern mirrors how `Array` works internally. The `final` keyword is important — it prevents subclassing, which would complicate the uniqueness check.

**Q: Why does COW break when bridging to Objective-C?**

A: `isKnownUniquelyReferenced` only counts Swift ARC references. When a Swift `Array` is bridged to `NSArray`, Objective-C retains the buffer with its own reference count mechanism, which Swift's check cannot see. Because Swift can't verify uniqueness in that scenario, it may conservatively copy the buffer, negating the COW benefit and causing unexpected O(n) work.

### Expert

**Q: In a high-throughput data pipeline, you notice that mutating a large array inside a loop is causing repeated O(n) copies despite there being only one logical owner. What could cause this?**

A: Several subtle issues can break COW uniqueness even with a single logical owner:

1. **Captured by a closure**: if the array is captured by an `@escaping` closure, ARC retains the buffer, making the retain count > 1 even inside the same scope.
2. **Passed to a non-inout parameter**: Swift passes value types by copy to functions (unless `inout`). If an intermediate function receives the array by value, ARC sees two owners momentarily.
3. **Stored in an `Any` or existential**: boxing the array can add an extra retain.
4. **Objective-C bridging in the hot path**: even a single call to an Obj-C method that touches the array can trigger a copy.

Fix: use `inout` parameters, avoid capturing the array in closures on the hot path, and profile with Instruments → Allocations to observe buffer allocation events.

## 6. Common Issues & Solutions

**Issue: Surprising O(n) mutation cost in a tight loop.**

Solution: Keep the array locally scoped and avoid assigning it to other variables, capturing it in closures, or passing it by value while in the loop. An `inout` parameter preserves the unique-reference guarantee across call boundaries.

**Issue: Custom COW type not working — buffer is always copied.**

Solution: Ensure the buffer class is `final`. Non-final classes have subclass potential that makes `isKnownUniquelyReferenced` always return `false`. Also ensure the buffer reference is stored as `var`, not `let`.

**Issue: Memory usage higher than expected for multiple array copies.**

Solution: Check whether some copies are being mutated immediately, triggering early COW. Defer mutations or batch them so shared buffers persist longer.

**Issue: String COW and bridging to NSString causing performance issues.**

Solution: Avoid repeated conversions between `String` and `NSString` in hot paths. If Obj-C interop is required, do one conversion and store the `NSString` rather than re-bridging on every call.

## 7. Related Topics

- [Value vs Reference Types](value-vs-reference.md) — the foundation COW builds upon
- [Memory Management](../02-memory-management/index.md) — ARC and how retain counts drive COW
- [Performance](../12-performance/index.md) — profiling allocations with Instruments
