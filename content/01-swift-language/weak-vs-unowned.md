# Weak vs Unowned

## 1. Overview

`weak` and `unowned` are non-strong reference qualifiers that break retain cycles in ARC-managed code. A `weak` reference becomes `nil` when the referenced object is deallocated; it is always declared as `Optional`. An `unowned` reference does not become `nil` — it assumes the referenced object will outlive the reference holder. Choosing the wrong qualifier causes either unnecessary `Optional` unwrapping (`weak`) or crashes from dangling pointers (`unowned`).

## 2. Simple Explanation

Imagine you lend someone your contact card.

- **`weak`** is like a sticky note with a phone number: if the person moves away (deallocation), you check the note and find it blank — no crash, just `nil`.
- **`unowned`** is like an engraved plaque on their office door with their name: you assume they're still there. If they've left and you knock on the door anyway, you get a crash — the plaque points to an empty office.

Use `weak` when the referenced object might be gone. Use `unowned` when you are certain it will outlive you.

## 3. Deep iOS Knowledge

### How `weak` Works

A `weak` reference is stored in a side table rather than inline. When the object is deallocated, ARC zeroes every `weak` reference that points to it. This zeroing is thread-safe. Because the value can become `nil`, `weak` references are always typed as `Optional`.

- Declared as: `weak var delegate: SomeDelegate?`
- Access pattern: `guard let d = delegate else { return }`
- Safe: accessing a `weak` reference after deallocation returns `nil`

### How `unowned` Works

An `unowned` reference skips the side table. It is stored as a raw pointer (or a tagged pointer in the unowned table for safe `unowned`). Two flavours exist:

1. **`unowned(safe)`** (default `unowned`): Accessing after deallocation triggers a Swift runtime trap with a clear error message. This is safer than a dangling pointer crash.
2. **`unowned(unsafe)`**: Truly a raw pointer — accessing after deallocation is undefined behaviour and will likely corrupt memory silently. Only use when you have external guarantees and need every nanosecond.

Declared as: `unowned let parent: ParentClass`

### When to Use Which

| Situation | Use |
|-----------|-----|
| Delegate pattern (view holds delegate, delegate may be deallocated) | `weak` |
| Child → parent back-reference (parent owns child, child outlives parent? no) | `unowned` |
| Closure capturing `self` where self may be deallocated before closure runs | `weak` |
| Closure capturing `self` guaranteed alive for closure's life (e.g., same object) | `unowned` |
| You are not certain of the lifetime relationship | `weak` (safer default) |

### `weak` in Closures

```swift
networkManager.fetch { [weak self] result in
    guard let self else { return }  // modern Swift: re-binds self
    self.handleResult(result)
}
```

The guard prevents work when `self` is gone. Without it, the closure silently does nothing, which is often the correct behaviour for view controllers that may have been dismissed.

### `unowned` in Closures

```swift
// Safe only if self is guaranteed alive during the closure's lifetime
let formatter = NumberFormatter()
let format: (Double) -> String = { [unowned formatter] value in
    formatter.string(from: NSNumber(value: value)) ?? ""
}
```

Useful in lazy property initialisers and short-lived closures where the owning object's lifetime contains the closure's lifetime.

### `unowned` vs `unowned(unsafe)` Performance

Standard `unowned` (safe) uses a second side-table entry to detect use-after-deallocation. `unowned(unsafe)` eliminates this overhead but is dangerous. In practice, the cost difference is negligible; only use `unowned(unsafe)` in ultra-hot paths with verified lifetime guarantees.

## 4. Practical Usage

```swift
// ── Delegate with weak reference ─────────────────────────────
protocol ImageLoaderDelegate: AnyObject {
    func imageLoader(_ loader: ImageLoader, didLoad image: UIImage)
}

class ImageLoader {
    weak var delegate: ImageLoaderDelegate?   // weak — delegate may be gone

    func load(url: URL) {
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let self, let data, let image = UIImage(data: data) else { return }
            DispatchQueue.main.async {
                self.delegate?.imageLoader(self, didLoad: image)
            }
        }.resume()
    }
}

// ── Parent-child with unowned back-reference ──────────────────
class TreeNode {
    var value: Int
    var children: [TreeNode] = []
    unowned var parent: TreeNode   // parent always outlives child in this tree

    init(value: Int, parent: TreeNode) {
        self.value = value
        self.parent = parent
    }
}

// ── Closure capture: weak self ────────────────────────────────
class ViewController: UIViewController {
    var viewModel: ViewModel?

    override func viewDidLoad() {
        super.viewDidLoad()
        viewModel?.onUpdate = { [weak self] newData in
            // self might be nil if VC was dismissed before closure fires
            self?.refreshUI(with: newData)
        }
    }

    private func refreshUI(with data: Data) { /* update views */ }
}

// ── Closure capture: unowned (guarantee: timer owns self) ─────
class Animator {
    private var displayLink: CADisplayLink?

    func start() {
        // displayLink is owned by self; self outlives the displayLink callback
        displayLink = CADisplayLink(target: self, selector: #selector(tick))
        displayLink?.add(to: .main, forMode: .common)
    }

    @objc private func tick() {
        // `self` is guaranteed alive here because displayLink is owned by self
    }

    // Note: CADisplayLink has its own retain of target, so actually
    // weak is safer here — example shows the concept only.
    deinit { displayLink?.invalidate() }
}

// ── Guard vs if let pattern ───────────────────────────────────
class DataProcessor {
    private var session: URLSession?

    func process() {
        session?.dataTask(with: URL(string: "https://example.com")!) { [weak self] data, _, error in
            // Option 1: early return on nil
            guard let self else { return }
            self.handle(data: data, error: error)
        }.resume()
    }

    private func handle(data: Data?, error: Error?) { /* ... */ }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `weak` and `unowned`?**

A: Both break retain cycles by creating non-strong references. `weak` is always `Optional` and becomes `nil` when the referenced object is deallocated — safe for objects that may outlive you. `unowned` is non-optional and assumes the referenced object will always outlive the reference holder; accessing it after deallocation causes a runtime crash.

**Q: Why must `weak` references be declared as `var` and not `let`?**

A: Because ARC must be able to zero the reference when the object is deallocated. A `let` binding is immutable after initialisation. Since the reference must be capable of being set to `nil` by ARC, it must be `var`.

### Hard

**Q: When is it safe to use `unowned` instead of `weak` in a closure capture list?**

A: `unowned` is safe when the captured object's lifetime strictly contains the closure's lifetime — meaning the captured object can never be deallocated while the closure is still alive. A common valid pattern: a parent object creates a child, and the child stores a closure that captures the parent with `unowned` — since the child is owned by the parent, the parent will always outlive the child (and the closure). Typical examples: lazy property closures on the same object, and short-lived animation blocks created inside the owning view controller.

**Q: How does ARC zero a `weak` reference when the object is deallocated?**

A: Swift maintains a **side table** — a separate heap allocation per object that stores weak reference pointers, an unowned reference count, and other metadata. When the strong reference count reaches zero, before freeing the object, ARC iterates over the side-table entry and sets every recorded `weak` pointer to `nil`. This zeroing is done atomically. The side table itself is freed when both the strong count and the unowned count reach zero.

### Expert

**Q: Describe a subtle retain cycle involving `unowned` that can still cause issues.**

A: `unowned` breaks the retain cycle but can introduce a crash-on-access bug. Suppose a child object holds an `unowned` reference to its parent. If the parent is deallocated (perhaps due to another cycle being broken elsewhere, or unexpected ownership transfer), the child's `unowned` reference becomes a dangling pointer. Accessing it causes a runtime trap. The subtlety is that `unowned` communicates a lifetime contract — violating that contract silently changes a memory-management bug (leak) into a crash bug (dangling pointer). Prefer `weak` in any situation where the lifetime contract could change as the codebase evolves, and reserve `unowned` only for architecturally enforced parent-owns-child trees.

## 6. Common Issues & Solutions

**Issue: Closure with `[weak self]` does nothing after the view controller is dismissed.**

Solution: This is usually correct behaviour — if the VC is gone, there's nothing to update. If the work still needs to happen (e.g., writing to a database), move it outside the UI update closure or hold a strong reference to the relevant model/service, not the view controller.

**Issue: Using `unowned self` in an escaping closure that can outlive `self` — crash at runtime.**

Solution: Replace `unowned` with `weak` and add a `guard let self` check. The crash is a use-after-free; the fix is to make the reference optional and handle the nil case.

**Issue: Delegate retained strongly, preventing view controller deallocation.**

Solution: Declare the delegate property as `weak var delegate: ProtocolName?`. Ensure the protocol is constrained to `AnyObject` (or `class`) so `weak` can be applied.

**Issue: `weak` reference nil even though the object should still exist.**

Solution: Check where the only strong reference is held. If only a local variable, the object may be deallocated at the end of that scope. Store the object in a `var` or `let` at the appropriate scope to keep it alive.

## 7. Related Topics

- [ARC Basics](arc-basics.md) — how reference counting works
- [Retain Cycles](../02-memory-management/retain-cycles.md) — cycle patterns and detection
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — escaping closures, `[weak]`, `[unowned]`
- [Struct vs Class](struct-vs-class.md) — when to avoid reference types entirely
