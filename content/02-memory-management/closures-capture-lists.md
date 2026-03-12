# Closures & Capture Lists

## 1. Overview

Closures in Swift automatically capture variables from their surrounding scope. By default, closures capture reference types strongly (incrementing the retain count) and value types by copy. A **capture list** — written as `[weak self]`, `[unowned dependency]`, or `[value = expression]` — explicitly controls how each variable is captured, preventing retain cycles and managing ownership. Understanding escaping vs non-escaping closures, autoclosure, and the interaction with ARC is essential for safe, leak-free asynchronous code.

## 2. Simple Explanation

Imagine you're heading out to a meeting and you need a reference to your notebook. You have three options:
- **Strong capture** — you take the notebook itself. It can't be thrown away while you have it.
- **`[weak]` capture** — you take a photocopy of the cover address. If someone throws the notebook away, your copy becomes blank (nil). You check before using it.
- **`[unowned]` capture** — you write the shelf number on your hand. You guarantee the notebook will still be there when you return. If it's not, you crash into empty air.

Value capture is like writing down the current page number — you get a snapshot of the value at the moment of capture, not a live reference.

## 3. Deep iOS Knowledge

### How Closures Capture Variables

When a closure refers to a variable in its enclosing scope, the compiler determines whether to:
1. **Copy** the value (for value types with no mutation via the closure)
2. **Create a heap-allocated box** for the variable if the closure may mutate it or if the type is a reference type (the box is shared between the closure and the original scope)

Reference types (class instances) are captured as strong references by default.

### Escaping vs Non-Escaping

- **Non-escaping closure** (`@noescape`, default before Swift 3, now inferred): the closure is guaranteed to execute before the function returns. The compiler does not need to retain `self` — it knows the caller's stack frame is valid for the closure's duration. Enables `self.` to be omitted inside the closure.
- **Escaping closure** (`@escaping`): the closure may outlive the function call — stored in a property, dispatched to a queue, passed to an async API. The closure must retain everything it uses because those objects may no longer be on the stack when the closure fires. This is where retain cycles typically occur.

```swift
func withEscaping(completion: @escaping () -> Void) {
    DispatchQueue.global().async { completion() }  // closure outlives function
}

func withNonEscaping(action: () -> Void) {
    action()  // called immediately, stack is valid
}
```

### Capture List Syntax

```swift
{ [weak self, unowned coordinator, count = self.count] in
    // self is Optional<Self>, automatically zeroed on deallocation
    // coordinator is non-optional, crashes if accessed after dealloc
    // count is a copy of self.count at closure-creation time
}
```

Multiple captures in one list, comma-separated.

### `[weak self]` Pattern

Most common fix for retain cycles. `self` becomes `Self?` inside the closure. Two idiomatic access patterns:

```swift
// Pattern A: guard-let (re-binds self for the rest of the closure)
networkTask.resume { [weak self] result in
    guard let self else { return }
    self.updateUI(with: result)
}

// Pattern B: optional chaining (use when only a few calls needed)
button.tapHandler = { [weak self] in
    self?.viewModel?.submit()
}
```

### `[unowned self]` Pattern

Use only when the closure's lifetime is strictly contained within `self`'s lifetime:

```swift
// Safe: the lazy closure is part of self and cannot outlive it
lazy var fullName: String = { [unowned self] in
    "\(self.firstName) \(self.lastName)"
}()
```

### Value Capture in Capture Lists

Force a value-type snapshot at closure creation time:

```swift
var counter = 0
let snapshot = { [counter] in print(counter) }  // captures current value
counter = 99
snapshot()  // prints 0, not 99
```

Without the capture list, the closure would capture the variable's storage box and print 99.

### Autoclosure

`@autoclosure` wraps an expression in a closure automatically at the call site. Used for lazy evaluation and short-circuit operators:

```swift
func assert(_ condition: @autoclosure () -> Bool, _ message: @autoclosure () -> String) {
    if !condition() { print(message()) }  // message only evaluated if condition fails
}

assert(array.count > 0, "Array is empty")  // expression, not closure literal
```

## 4. Practical Usage

```swift
import Foundation
import UIKit

// ── Retain cycle: BAD ─────────────────────────────────────────
class FeedViewController: UIViewController {
    var loadCompletion: (() -> Void)?

    func loadFeed() {
        // BAD: strong capture → cycle: self → loadCompletion → self
        loadCompletion = {
            self.tableView.reloadData()  // strong self
        }
    }

    var tableView = UITableView()
}

// ── Fix with [weak self] ───────────────────────────────────────
class FeedViewControllerFixed: UIViewController {
    var loadCompletion: (() -> Void)?

    func loadFeed() {
        loadCompletion = { [weak self] in
            self?.tableView.reloadData()   // safe; no cycle
        }
    }

    var tableView = UITableView()
}

// ── Escaping vs non-escaping ──────────────────────────────────
class SearchViewModel {
    var query = ""

    // Non-escaping: no capture list needed; compiler knows stack is valid
    func validate(using check: (String) -> Bool) -> Bool {
        check(query)  // can omit self. here
    }

    // Escaping: stored for later use; must handle self lifetime
    var onQueryChanged: ((String) -> Void)?

    func updateQuery(_ q: String) {
        query = q
        onQueryChanged?(q)
    }
}

// ── Value capture snapshot ────────────────────────────────────
func makePrinters() -> [() -> Void] {
    var closures: [() -> Void] = []
    for i in 0..<3 {
        closures.append { [i] in print(i) }  // captures snapshot of i
    }
    return closures
}

let printers = makePrinters()
printers.forEach { $0() }  // prints 0, 1, 2 (not all 2 without capture list)

// ── Capturing multiple values ─────────────────────────────────
class OrderManager {
    var orderId = UUID()
    var service: NetworkService?

    func submitOrder() {
        let id = orderId  // capture value, not self.orderId
        service?.post(id: id) { [weak self, id] result in
            // self is weak — VC may be gone
            // id is a value snapshot — always valid
            guard let self else { return }
            self.handleResult(result, for: id)
        }
    }

    private func handleResult(_ result: Result<Data, Error>, for id: UUID) {}
}

class NetworkService {
    func post(id: UUID, completion: @escaping (Result<Data, Error>) -> Void) {}
}

// ── @autoclosure for lazy evaluation ─────────────────────────
func log(_ level: LogLevel, _ message: @autoclosure () -> String) {
    guard level >= .current else { return }  // message() only called if needed
    print(message())
}

enum LogLevel: Comparable {
    case debug, info, error
    static var current: LogLevel = .info
}

log(.debug, "Expensive: \(UUID().uuidString)")  // expression only evaluated if debug

// ── Unowned in lazy property ──────────────────────────────────
class DocumentEditor {
    var title = "Untitled"
    // Closure is part of self; self outlives the lazy property
    lazy var titleView: UILabel = { [unowned self] in
        let label = UILabel()
        label.text = self.title
        return label
    }()
}

// ── guard let self (modern Swift shorthand) ───────────────────
class ImageProcessor {
    func processAsync(data: Data, completion: @escaping (UIImage?) -> Void) {
        DispatchQueue.global().async { [weak self] in
            guard let self else { completion(nil); return }
            // `self` is non-optional here; safe to call without `?`
            let image = self.decode(data)
            DispatchQueue.main.async { completion(image) }
        }
    }

    private func decode(_ data: Data) -> UIImage? { UIImage(data: data) }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a capture list in a Swift closure and why is it needed?**

A: A capture list appears before the closure parameters (`{ [weak self] in ... }`) and controls how surrounding variables are captured. Without a capture list, reference types are captured strongly by default, potentially creating retain cycles. The list specifies `weak` (optional, zeroed on dealloc) or `unowned` (non-optional, assumes object outlives closure) for reference types, or value-type snapshots. It is needed to break cycles and to snapshot values at closure-creation time.

**Q: What is the difference between an escaping and non-escaping closure?**

A: A non-escaping closure (default) is called during the function's execution — it cannot outlive the function call. This lets the compiler skip retaining `self` and allows `self.` to be omitted. An escaping closure (`@escaping`) may be stored and called after the function returns (e.g., stored in a property, dispatched asynchronously). Escaping closures must retain everything they use, and they require explicit `self.` to remind you that a strong capture is happening.

### Hard

**Q: Explain what happens when you capture a `var` in a closure without a capture list.**

A: The closure captures the variable's **storage box** — a heap-allocated reference to the variable. Both the closure and the enclosing scope share this box. Mutating the variable inside the closure is visible outside, and vice versa. This is different from capturing the value at creation time. To get a snapshot of the current value, use a capture list: `[x]` copies the value at the moment the closure is created.

**Q: Can a non-escaping closure cause a retain cycle?**

A: In theory, no — a non-escaping closure is not stored beyond the function call, so it cannot form a persistent cycle. In practice, if a non-escaping closure is used to initialise a stored property (e.g., inside a `lazy` initialiser that doesn't use `[unowned self]`), it can create a temporary strong cycle. But since the closure doesn't outlive the `lazy` property's first access, the cycle resolves immediately. The real risk is always with `@escaping` closures.

### Expert

**Q: In Swift Concurrency, do `async` closures capture `self` strongly by default? How does `@MainActor` affect this?**

A: Yes, `async` closures (including `Task { }` blocks) capture `self` strongly by default — they are escaping. This means you can still create retain cycles with `Task { self.doWork() }`. The fix is the same: `Task { [weak self] in await self?.doWork() }`. `@MainActor` changes the execution context (closures run on the main thread) but does not affect capture semantics — it does not automatically weaken captures. One nuance: structured concurrency tasks (created with `async let` or task groups) have structured lifetimes bounded by the parent task, which limits cycle risk, but unstructured `Task { }` detached tasks still carry the full escaping risk.

## 6. Common Issues & Solutions

**Issue: `guard let self` fails to compile in older Swift — requires `guard let self = self`.**

Solution: The shorthand `guard let self` (without `= self`) was introduced in Swift 5.3. For older targets, use `guard let self = self else { return }`.

**Issue: Closure with `[weak self]` does nothing even though the object exists.**

Solution: Ensure `guard let self else { return }` is not returning prematurely. Check that `self` is still in memory at the time the closure fires — add a `print("self is \(String(describing: self))")` before the guard to debug.

**Issue: Autoclosure causes confusing compiler error "expression is not callable".**

Solution: `@autoclosure` wraps the expression as `() -> T`. Passing an explicit closure literal `{ expression }` to an `@autoclosure` parameter is a type error — pass the expression directly without braces.

**Issue: Value captured in closure does not reflect later mutations.**

Solution: This is the intended behaviour of capture lists (`[count]`). If you need the live value, remove it from the capture list and access it via `self.count` (ensuring `self` is still alive with `[weak self]`).

## 7. Related Topics

- [Retain Cycles](retain-cycles.md) — the cycles that capture lists are designed to break
- [ARC](arc.md) — how strong captures increment retain counts
- [Weak vs Unowned](../01-swift-language/weak-vs-unowned.md) — semantics of the two non-strong capture modes
- [Concurrency](../03-concurrency/index.md) — Task closures and structured concurrency lifetimes
