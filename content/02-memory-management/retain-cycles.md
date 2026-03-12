# Retain Cycles

## 1. Overview

A retain cycle (also called a reference cycle) occurs when two or more objects hold strong references to each other, preventing any of them from ever reaching a zero reference count. ARC cannot free these objects — they become memory leaks. Retain cycles are one of the most common memory bugs in iOS development and the primary reason for using `weak` and `unowned` references. Identifying cycle patterns, detecting them with Instruments, and applying the correct fix is a core iOS engineering skill.

## 2. Simple Explanation

Imagine two neighbours, Alice and Bob, who each have a key to the other's house. Neither will move out until the other moves out first. But the other won't move out until they move out first — a deadlock. Neither leaves, the houses are never freed.

A retain cycle in code works exactly the same way:
- Object A has a strong reference to Object B (A holds B's key)
- Object B has a strong reference to Object A (B holds A's key)
- Setting both external references to `nil` still leaves each at retain count 1 — neither is freed

## 3. Deep iOS Knowledge

### Common Cycle Patterns

#### Pattern 1: Delegate Cycle
A child object holds a strong reference back to its delegate (the parent).

```
Parent → Child (strong, owns child)
Child  → Parent (strong via delegate property — cycle!)
```

Fix: `weak var delegate: ProtocolName?`

#### Pattern 2: Closure Capture
A closure stored on an object captures `self` strongly.

```
Object → closure property (strong, owns closure)
Closure → self (strong capture — cycle!)
```

Fix: `[weak self]` or `[unowned self]` capture list.

#### Pattern 3: Parent-Child Back-Reference
A child holds a strong reference to its parent to call back or access shared state.

```
Parent → [Child] (strong array — owns children)
Child  → Parent  (strong back-reference — cycle!)
```

Fix: `unowned var parent: Parent` (if child's lifetime ≤ parent's).

#### Pattern 4: Timer
`Timer` retains its target strongly. If `self` holds the timer strongly:

```
self → timer (strong, stored property)
Timer → self (strong target — cycle!)
```

Fix: Invalidate the timer in `viewDidDisappear` or `deinit`, or use a proxy/block-based timer.

#### Pattern 5: NotificationCenter
`NotificationCenter.addObserver(forName:object:queue:using:)` returns an `NSObjectProtocol` token that must be stored and removed. If the closure captures `self` strongly and `self` holds the token strongly:

```
self → token (strong)
Token → closure (strong)
Closure → self (strong capture — cycle!)
```

Fix: `[weak self]` in the closure and always remove the observer (`NotificationCenter.default.removeObserver(token)` or `invalidate`).

### Why ARC Cannot Break Cycles

ARC uses reference counting, not tracing. It can only free an object when its count reaches zero. In a cycle, the objects mutually maintain each other's count above zero — ARC has no mechanism to detect "these objects are only reachable from each other." Tracing garbage collectors (JVM, Go) can detect this because they traverse the live object graph from roots; ARC deliberately avoids that overhead.

### Detection with Instruments

**Instruments → Leaks:**
- Leaks scans the heap periodically for objects with no path from a GC root (main thread stack, global variables)
- Shows leaked object type, size, and allocation backtrace
- The "Cycles & Roots" view renders the reference graph visually

**Instruments → Allocations:**
- Persistent objects that should be freed appear in the "All Heap Allocations" list
- Filter by class name; check whether count keeps growing as you navigate

**Debug Memory Graph (Xcode):**
- Run app → Debug Navigator → Memory Graph button (grid icon)
- Shows a live object graph with purple leak indicators
- Click a suspected object to see all incoming/outgoing references
- Fastest tool for diagnosing cycles during development

### Using `weak var` in Tests

```swift
func testNoCycle() {
    weak var weakSelf: MyClass?
    do {
        let obj = MyClass()
        weakSelf = obj
    }
    XCTAssertNil(weakSelf, "MyClass leaked — possible retain cycle")
}
```

## 4. Practical Usage

```swift
// ── Pattern 1: Fix delegate cycle ────────────────────────────
protocol TableManagerDelegate: AnyObject {
    func tableManagerDidSelectItem(_ item: String)
}

class TableManager {
    weak var delegate: TableManagerDelegate?   // weak breaks the cycle

    func select(_ item: String) {
        delegate?.tableManagerDidSelectItem(item)
    }
}

class ViewController: UIViewController, TableManagerDelegate {
    var tableManager: TableManager?

    override func viewDidLoad() {
        super.viewDidLoad()
        tableManager = TableManager()
        tableManager?.delegate = self  // VC → manager (strong), manager → VC (weak)
    }

    func tableManagerDidSelectItem(_ item: String) {
        print("Selected: \(item)")
    }
}

import UIKit

// ── Pattern 2: Fix closure cycle ─────────────────────────────
class ProfileViewModel {
    var name = "Alice"
    var onUpdate: (() -> Void)?

    func setupCycle() {
        // BAD: strong capture — cycle: self → onUpdate, onUpdate → self
        // onUpdate = { self.name = "updated" }

        // GOOD: weak capture
        onUpdate = { [weak self] in
            self?.name = "updated"
        }
    }
    deinit { print("ProfileViewModel freed") }
}

// ── Pattern 3: Fix parent-child back-reference ────────────────
class Document {
    var sections: [Section] = []

    func addSection(title: String) {
        sections.append(Section(title: title, document: self))
    }
    deinit { print("Document freed") }
}

class Section {
    let title: String
    unowned let document: Document   // unowned: section can't outlive its document

    init(title: String, document: Document) {
        self.title = title
        self.document = document
    }
    deinit { print("Section '\(title)' freed") }
}

// ── Pattern 4: Fix Timer cycle ────────────────────────────────
class Ticker {
    private var timer: Timer?
    private var count = 0

    func start() {
        // Block-based Timer does not retain self
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            self?.count += 1
        }
    }

    func stop() { timer?.invalidate(); timer = nil }
    deinit { stop(); print("Ticker freed") }
}

// ── Pattern 5: Fix NotificationCenter cycle ───────────────────
class DataController {
    private var observer: NSObjectProtocol?

    func startObserving() {
        observer = NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in             // weak prevents the cycle
            self?.clearCache()
        }
    }

    func stopObserving() {
        if let obs = observer {
            NotificationCenter.default.removeObserver(obs)
            observer = nil
        }
    }

    private func clearCache() { print("Cache cleared") }
    deinit { stopObserving() }
}

// ── Unit test to verify no leak ───────────────────────────────
import XCTest

class RetainCycleTests: XCTestCase {
    func testProfileViewModelNoLeak() {
        weak var weakVM: ProfileViewModel?
        do {
            let vm = ProfileViewModel()
            vm.setupCycle()
            weakVM = vm
        }
        XCTAssertNil(weakVM, "ProfileViewModel leaked — check closure capture")
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a retain cycle and why does it cause a memory leak?**

A: A retain cycle occurs when two or more objects hold strong references to each other, creating a loop. ARC frees an object when its reference count reaches zero. In a cycle, each object keeps the other's count at 1 or more — even after all external references are removed. The count never reaches zero, so neither object is freed, and the memory is permanently leaked for the lifetime of the app.

**Q: How do you detect a retain cycle?**

A: Several tools: Xcode's Debug Memory Graph (live, visual reference graph with leak indicators), Instruments → Leaks (heap scan with cycle visualisation), and unit tests using `weak var` to assert that objects are nil after their scope ends. Adding `print("freed")` in `deinit` is also a quick sanity check during development.

### Hard

**Q: Why does adding `[weak self]` to a closure sometimes still cause a leak?**

A: `[weak self]` makes the closure's reference to `self` weak, breaking one direction of the cycle. But if the cycle involves additional links — for example, `self` holds an object `A`, and `A` holds the closure — the cycle may persist through a different path. Always trace the full reference graph. Common mistake: capturing `self` weakly but not capturing other objects that themselves hold `self` strongly. Another pitfall: a closure stored in a collection owned by `self` — the collection holds the closure (strong), the closure captures `self` (now weak — but the collection is still retained through `self`'s ownership). In that case, `[weak self]` is correct but the closure must also handle `self` being nil.

**Q: When should you use `unowned` instead of `weak` to break a cycle?**

A: `unowned` is appropriate when you can guarantee that the referenced object's lifetime strictly contains the reference holder's lifetime — the referenced object will never be deallocated before the holder. The most common valid case: a child object with an `unowned` reference to its parent, where the parent owns the child and will always outlive it. Using `unowned` when the guarantee doesn't hold results in a crash (accessing a deallocated object), whereas `weak` would safely return nil. When in doubt, use `weak`.

### Expert

**Q: Describe how to find a non-obvious retain cycle using Instruments → Allocations.**

A: Enable "Record Reference Counts" in Allocations settings before profiling. Reproduce the scenario that should release the object (e.g., navigate away from a view controller). In the Allocations list, filter by the class you expect to be released. If it persists, click the object to open its history. Look for the last `retain` that was not matched by a `release`. Click the backtrace to identify the code that retains the object — often a notification observer block, a completion handler, or a cached closure. Correlate with the Debug Memory Graph for a visual confirmation of which object is holding the strong reference.

## 6. Common Issues & Solutions

**Issue: View controller dismissed but not deallocated — `deinit` never called.**

Solution: Open the Debug Memory Graph. Look for a purple warning icon on the VC. Trace incoming strong references. Common culprits: `NotificationCenter` observer not removed, a timer still running, a closure in a network layer capturing `self` strongly, or a singleton holding a reference to the VC.

**Issue: Adding `[weak self]` breaks functionality — code inside the closure does nothing after the first navigation.**

Solution: The closure's work is valid only while `self` exists. If work should happen regardless, extract it from the view-controller closure: pass a model/service reference (which has a longer lifetime) instead of `self`, and let the closure operate on that.

**Issue: Timer fires after `deinit` — crash on deallocated object.**

Solution: Invalidate the timer before `deinit` is reached, typically in `viewDidDisappear` or an explicit `stop()` method. Using a block-based Timer with `[weak self]` inside the block provides an additional safety net, but invalidation is still required.

**Issue: Instruments shows leak but the class name is a private internal type.**

Solution: The leaked object may be an internal buffer or a type-erased wrapper rather than your own class. Look at the allocation backtrace to trace back to your code. Often the root cause is a closure or property wrapper that indirectly references your object.

## 7. Related Topics

- [ARC](arc.md) — how reference counting works and why cycles are undetectable by ARC
- [Closures & Capture Lists](closures-capture-lists.md) — `[weak self]`, `[unowned self]`, escaping closures
- [Weak vs Unowned](../01-swift-language/weak-vs-unowned.md) — choosing the right non-strong reference
- [ARC Basics](../01-swift-language/arc-basics.md) — foundational lifecycle and deinit
