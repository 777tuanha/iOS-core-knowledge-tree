# GCD & Dispatch Queues

## 1. Overview

Grand Central Dispatch (GCD) is Apple's C-level concurrency framework. It manages a pool of POSIX threads and lets you describe units of work (blocks/closures) that should be executed on queues. The OS scheduler decides which thread actually runs each block, freeing you from thread lifecycle management. GCD underpins most concurrency in iOS — even `OperationQueue` and (historically) `URLSession` use it internally.

## 2. Simple Explanation

Imagine a post office with a single counter (serial queue) versus many open windows (concurrent queue). At the single counter, each customer is served one at a time in order — no confusion about who gets served next. At the multi-window post office, many customers are helped simultaneously, but no one can predict which window you'll reach first.

GCD is the post office manager. You drop off parcels (work items) at the queue counter, and the manager assigns postal workers (threads) to handle them. You never hire or fire postal workers yourself.

## 3. Deep iOS Knowledge

### Queue Types

| Type | Behaviour | Typical use |
|------|-----------|-------------|
| Serial | One item at a time, FIFO | Protecting a resource from concurrent access |
| Concurrent | Multiple items simultaneously | Parallel read-only work |
| Main queue | Serial, always on the main thread | UI updates |

### Global (System) Concurrent Queues

Apple provides pre-built concurrent queues at five QoS levels:

```swift
DispatchQueue.global(qos: .userInteractive)  // animations, direct user response
DispatchQueue.global(qos: .userInitiated)    // user-triggered, result needed quickly
DispatchQueue.global(qos: .default)          // general background work
DispatchQueue.global(qos: .utility)          // progress bars, long operations
DispatchQueue.global(qos: .background)       // prefetch, maintenance (invisible)
```

You never own global queues — they are singletons shared across the process.

### Quality of Service (QoS)

QoS is a hint to the scheduler. It affects:
- **Thread priority** — higher QoS gets more CPU time when resources are scarce.
- **Timer coalescing** — lower QoS work may be delayed to coalesce with other low-priority work, saving battery.
- **Thread creation policy** — the system spawns more threads for high-QoS queues under load.

QoS can be **promoted**: if a high-QoS task is waiting for a result from a low-QoS queue, the system temporarily raises the QoS of the waiting queue (priority boosting).

### async vs sync Dispatch

| Method | Calling thread | Risk |
|--------|---------------|------|
| `async` | Returns immediately; work runs later | None to caller |
| `sync` | Blocks caller until work completes | Deadlock if dispatching to own queue |

**Deadlock rule**: never call `sync` on a queue from work already running on that same queue.

### Custom vs Global Queues

Prefer **custom queues** for work that touches a specific resource — you get a meaningful label (visible in Xcode/Instruments), and you can control the queue type, QoS, and target queue.

```swift
let dbQueue = DispatchQueue(label: "com.app.database", qos: .userInitiated)
let imageQueue = DispatchQueue(label: "com.app.images", attributes: .concurrent)
```

Prefer **global queues** for one-off background tasks where you don't need the extra control.

### Target Queues

Every custom queue has a **target queue** (default: `DispatchQueue.global(qos:)` matching its QoS). Setting a target queue chains queues so that all work ultimately runs on the target. This enables hierarchy-based QoS propagation and is used to implement priority queues and queue activation.

### DispatchWorkItem

A `DispatchWorkItem` wraps a closure with additional capabilities: cancellation, notification on completion, and wait. Cancellation is cooperative — you must check `isCancelled` inside the item.

## 4. Practical Usage

```swift
import Foundation

// ── 1. Main-thread UI update after background work ─────────────
func loadUserProfile(id: String) {
    // Move heavy work off the main thread
    DispatchQueue.global(qos: .userInitiated).async {
        let profile = fetchProfile(id: id)  // simulated network/DB call

        // All UIKit updates must happen on the main queue
        DispatchQueue.main.async {
            self.updateUI(with: profile)
        }
    }
}

// ── 2. Serial queue as a lightweight mutex ──────────────────────
class Cache {
    private var store: [String: Data] = [:]
    // Serial queue serialises all reads and writes — no data races
    private let queue = DispatchQueue(label: "com.app.cache")

    func set(_ data: Data, for key: String) {
        queue.async {
            self.store[key] = data        // safe: only one writer at a time
        }
    }

    func get(key: String) -> Data? {
        // sync: we need the return value before we continue
        queue.sync { store[key] }
    }
}

// ── 3. Concurrent queue for parallel reads ─────────────────────
class ImageStore {
    private var images: [String: UIImage] = [:]
    private let queue = DispatchQueue(
        label: "com.app.images",
        attributes: .concurrent       // multiple readers at once
    )

    func image(for key: String) -> UIImage? {
        queue.sync { images[key] }    // concurrent reads — fine
    }

    func setImage(_ image: UIImage, for key: String) {
        // Use barrier to get exclusive access for writes
        queue.async(flags: .barrier) {
            self.images[key] = image  // exclusive: no reads/writes during this
        }
    }
}

// ── 4. DispatchWorkItem with cancellation ──────────────────────
var searchWorkItem: DispatchWorkItem?

func search(query: String) {
    searchWorkItem?.cancel()          // cancel previous search

    let item = DispatchWorkItem {
        guard !Thread.current.isCancelled else { return }
        let results = performSearch(query: query)
        guard !(self.searchWorkItem?.isCancelled ?? false) else { return }
        DispatchQueue.main.async { self.showResults(results) }
    }
    searchWorkItem = item
    DispatchQueue.global(qos: .userInitiated).async(execute: item)
}

// ── 5. sync dispatch for thread-safe property access ───────────
class Settings {
    private var _value = 0
    private let queue = DispatchQueue(label: "com.app.settings")

    var value: Int {
        get { queue.sync { _value } }
        set { queue.async { self._value = newValue } }  // async write is fine
    }
}

// Helper stubs used above
func fetchProfile(id: String) -> String { id }
func performSearch(query: String) -> [String] { [] }
extension NSObject {
    func updateUI(with profile: String) {}
    func showResults(_ results: [String]) {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a serial and a concurrent dispatch queue?**

A: A serial queue executes one work item at a time in FIFO order — the next item does not start until the current one finishes. A concurrent queue can run multiple items simultaneously on different threads. Serial queues are commonly used to protect shared mutable state; concurrent queues are used for independent, parallelisable work where ordering does not matter.

**Q: What are the QoS classes in GCD and why do they matter?**

A: QoS (Quality of Service) classes are hints to the OS scheduler: `.userInteractive` (highest — animations), `.userInitiated` (user-triggered, near-instant), `.default`, `.utility` (long operations with visible progress), `.background` (invisible maintenance), and `.unspecified`. They determine thread priority and timer coalescing. Using the right QoS keeps the UI responsive by giving background work proportionally less CPU time.

### Hard

**Q: How does GCD prevent thread explosion?**

A: GCD uses a **thread pool** with a cap (typically 64 threads per process). When you submit work with `async`, GCD only creates a new thread if all existing threads are blocked and the pool limit has not been reached. If you have many concurrent tasks all blocked on I/O or `sync` calls, GCD may eventually hit the cap, and new submissions are queued waiting for a thread. This is why you should prefer `async` over `sync` for potentially-blocking work and avoid holding threads with long blocking operations — instead, use `DispatchSemaphore` or structured concurrency, which suspends without occupying a thread.

**Q: What is a target queue and how does it affect QoS propagation?**

A: Every custom `DispatchQueue` has a target queue — by default, the global queue matching its QoS. When work submitted to a custom queue is scheduled, it ultimately runs on the target queue's thread pool. You can set a custom target queue via `DispatchQueue(label:target:)` or `setTarget(queue:)`. This allows you to create a hierarchy: a set of serialised operations that all funnel into one shared concurrent queue, or a group of queues that inherit QoS from a single authoritative queue. The target queue also propagates synchronisation for `DispatchSpecificKey` storage.

### Expert

**Q: Explain how GCD's `sync` on the main queue from the main thread causes a deadlock, and describe a pattern where this deadlock is non-obvious.**

A: `DispatchQueue.main.sync { }` submits a work item to the main queue and blocks the calling thread until it completes. If the caller is already on the main thread, the main thread is blocked waiting for the item to be dequeued — but the main queue won't dequeue anything because its thread (the main thread) is blocked. This is a simple case. A non-obvious case: a library calls a completion handler synchronously on the calling thread, and you call it from the main thread; internally the library dispatches `main.sync` to post the result — instant deadlock. Another: a `sync` dispatch into a custom serial queue A, inside a block already running on queue A (re-entrant `sync`) — GCD serial queues are not re-entrant. The fix is always to use `async` when the return value is not immediately needed, or restructure so the main thread is never the target of a `sync` from itself.

## 6. Common Issues & Solutions

**Issue: UI freezes — heavy work accidentally runs on the main thread.**

Solution: Profile with Instruments → Time Profiler. Look for long frames (> 16 ms) in the main thread stack. Move database queries, image decoding, and network parsing to `DispatchQueue.global()`.

**Issue: Data race on shared mutable state — crashes or incorrect values.**

Solution: Protect the state with a serial queue (all reads and writes go through the queue). For read-heavy workloads use a concurrent queue with `.barrier` for writes. In Swift 5.7+ with strict concurrency, migrate to an `actor`.

**Issue: `sync` deadlock — app hangs with no crash.**

Solution: Enable Thread Sanitiser (TSan) and the main-thread checker. Never call `DispatchQueue.main.sync` from the main thread. Avoid `sync` on any queue from inside a block already running on that queue.

**Issue: Work submitted to `.background` QoS runs too slowly on a plugged-in device but is acceptable on battery.**

Solution: That is expected behaviour — `.background` is throttled when the device is under battery-saving constraints. Move time-sensitive work to `.utility` or `.userInitiated`.

## 7. Related Topics

- [DispatchGroup, Semaphore & Barrier](dispatch-group-semaphore.md) — coordinating multiple async dispatches
- [Operation & OperationQueue](operation-queue.md) — higher-level alternative to GCD
- [async/await](async-await.md) — modern replacement for GCD callbacks
- [Concurrency Problems](concurrency-problems.md) — race conditions, deadlocks, thread explosion
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — `[weak self]` in async blocks
