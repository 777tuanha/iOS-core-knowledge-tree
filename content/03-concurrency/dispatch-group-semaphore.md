# DispatchGroup, Semaphore & Barrier

## 1. Overview

GCD dispatches individual work items efficiently, but many real problems require coordinating *groups* of concurrent tasks: wait for all of them, limit how many run at once, or ensure exclusive access during a write. Three GCD primitives address these needs: **DispatchGroup** (wait for a set of tasks to all finish), **DispatchSemaphore** (limit concurrency or signal between threads), and **DispatchBarrier** (mutual exclusion within a concurrent queue). Together they cover the vast majority of synchronisation patterns needed before Swift's structured concurrency was introduced.

## 2. Simple Explanation

**DispatchGroup** is like a group project tracker. Every student (task) checks in when they start (`enter`) and checks out when they finish (`leave`). When all students have checked out, the teacher is notified (`notify`) that the project is done.

**DispatchSemaphore** is a parking lot with a fixed number of spaces. When a car (thread) enters, it takes a space (`wait`). When it leaves, it frees the space (`signal`). If the lot is full, incoming cars idle at the gate until a space opens up.

**DispatchBarrier** is a one-lane bridge in the middle of a multi-lane highway. Regular traffic (concurrent reads) flows freely on either side, but when a barrier truck (write) needs to cross, all other traffic stops until it finishes.

## 3. Deep iOS Knowledge

### DispatchGroup

A `DispatchGroup` tracks an internal counter:
- `enter()` increments the counter.
- `leave()` decrements it.
- When the counter reaches zero, the group fires its registered `notify` blocks (and unblocks any threads calling `wait()`).

You can use groups with work submitted via `group:` parameter or manually with `enter`/`leave` for non-GCD async APIs (e.g., `URLSession`).

| Method | Behaviour |
|--------|-----------|
| `group.async(queue:) { }` | Submits and auto-pairs enter/leave |
| `group.enter()` / `group.leave()` | Manual pairing — must be balanced |
| `group.notify(queue:) { }` | Callback when count reaches zero |
| `group.wait()` | Blocks calling thread until count reaches zero |
| `group.wait(timeout:)` | Returns `.success` or `.timedOut` |

**Important**: `enter` and `leave` must always be balanced. An extra `leave` beyond a matching `enter` crashes with `EXC_BAD_INSTRUCTION`.

### DispatchSemaphore

A semaphore wraps an integer count:
- `wait()` decrements the count; if count was already 0, it blocks.
- `signal()` increments the count; if a thread is waiting, it is unblocked.

Common uses:
1. **Binary semaphore (count = 1)** — mutual exclusion, similar to a mutex.
2. **Counting semaphore (count = N)** — limit concurrent access to a pool of N resources.
3. **Signalling** — one thread waits for another to finish a specific step.

Using a semaphore to block a thread is still "blocking a thread" — it wastes a thread from the GCD pool. Prefer `DispatchGroup.notify` or `async/await` when you don't need synchronous waiting.

### DispatchBarrier

Submitted via `queue.async(flags: .barrier) { }` or `queue.sync(flags: .barrier) { }` on a **custom concurrent** queue. A barrier item:
1. Waits until all currently-executing items in the queue finish.
2. Executes exclusively — no other items run while it is active.
3. After it finishes, concurrent execution resumes.

This creates a **reader-writer lock** pattern: multiple readers run concurrently, but each writer gets exclusive access.

**Important**: barriers have no effect on global (system) concurrent queues — only custom concurrent queues. Submitting a barrier to a global queue causes it to run as a normal (non-exclusive) async item.

### Combining Group and Semaphore

A semaphore can act as a signal from an async callback back to a synchronous caller — a pattern sometimes called "sync-wrapping an async API". This must never be done on the main thread (deadlock risk) or inside a narrow thread pool context.

## 4. Practical Usage

```swift
import Foundation

// ── DispatchGroup: wait for multiple network requests ──────────
func fetchDashboard(completion: @escaping () -> Void) {
    let group = DispatchGroup()
    let queue = DispatchQueue.global(qos: .userInitiated)

    group.enter()
    fetchUser { _ in
        group.leave()                 // must always be called, even on error
    }

    group.enter()
    fetchPosts { _ in
        group.leave()
    }

    group.enter()
    fetchNotifications { _ in
        group.leave()
    }

    // notify fires on the specified queue when all three have left
    group.notify(queue: .main) {
        completion()                  // safe to update UI here
    }
}

// ── DispatchGroup with group.async ─────────────────────────────
func processBatch(items: [String]) {
    let group = DispatchGroup()

    for item in items {
        // group.async automatically calls enter before and leave after the block
        group.async(queue: .global(qos: .utility)) {
            process(item: item)
        }
    }

    // Synchronously wait with a timeout (avoid on main thread)
    let result = group.wait(timeout: .now() + 5)
    if result == .timedOut {
        print("Batch timed out")
    }
}

// ── DispatchSemaphore: limit concurrent downloads ──────────────
func downloadAll(urls: [URL]) {
    let semaphore = DispatchSemaphore(value: 3)  // max 3 simultaneous downloads
    let queue = DispatchQueue.global(qos: .utility)

    for url in urls {
        queue.async {
            semaphore.wait()                 // block if 3 downloads already active
            defer { semaphore.signal() }     // always release, even on error
            download(url: url)
        }
    }
}

// ── DispatchSemaphore: sync-wrap an async API (background only) ─
func syncFetch(url: URL) -> Data? {
    // WARNING: never call this from the main thread — it will deadlock.
    var result: Data?
    let semaphore = DispatchSemaphore(value: 0)

    URLSession.shared.dataTask(with: url) { data, _, _ in
        result = data
        semaphore.signal()            // unblock the waiting thread
    }.resume()

    semaphore.wait()                  // block until dataTask calls signal
    return result
}

// ── Reader-Writer lock using DispatchBarrier ────────────────────
class ThreadSafeArray<T> {
    private var storage: [T] = []
    // MUST be a custom concurrent queue — not global!
    private let queue = DispatchQueue(
        label: "com.app.safeArray",
        attributes: .concurrent
    )

    func read() -> [T] {
        queue.sync { storage }        // concurrent reads allowed
    }

    func append(_ element: T) {
        queue.async(flags: .barrier) {
            self.storage.append(element)  // exclusive write
        }
    }

    func removeAll() {
        queue.async(flags: .barrier) {
            self.storage.removeAll()      // exclusive write
        }
    }
}

// Stubs
func fetchUser(completion: @escaping (String?) -> Void) { completion(nil) }
func fetchPosts(completion: @escaping ([String]?) -> Void) { completion(nil) }
func fetchNotifications(completion: @escaping ([String]?) -> Void) { completion(nil) }
func process(item: String) {}
func download(url: URL) {}
```

## 5. Interview Questions & Answers

### Basic

**Q: What does `DispatchGroup.notify` do and how does it differ from `wait`?**

A: `notify(queue:execute:)` registers a closure that is called asynchronously on the specified queue when the group's counter reaches zero — the calling thread is not blocked. `wait()` blocks the calling thread until the counter reaches zero. `notify` is almost always preferable because it does not occupy a thread while waiting. `wait` is useful in rare cases where you need a synchronous API, must be called from a background thread, and cannot use a completion callback.

**Q: What is a `DispatchSemaphore` and what is the initial count parameter?**

A: A `DispatchSemaphore` is a synchronisation primitive wrapping a counter. `wait()` decrements the counter; if it was already 0, the calling thread blocks until another thread calls `signal()`. `signal()` increments the counter. The initial count you pass to `DispatchSemaphore(value:)` is the number of concurrent accesses allowed before blocking begins. A value of 0 means the first `wait` blocks immediately until a `signal` arrives — useful as a one-shot signal. A value of N limits concurrency to N simultaneous accessors.

### Hard

**Q: Why does `DispatchBarrier` not work on global concurrent queues?**

A: Global queues are shared system resources used by the entire process (and possibly the OS). Apple does not allow private synchronisation on shared queues because it could block work submitted by other parts of the system. A barrier on a global queue would serialize not just your work but anyone else's work on that queue. Therefore, GCD silently ignores the `.barrier` flag on global queues and executes the block as a normal async submission. The fix is always to create a custom `DispatchQueue(label:attributes:.concurrent)` that you own, then use barriers on it.

**Q: How do you avoid a `DispatchGroup` counter imbalance and what happens if it occurs?**

A: Every `enter()` must have exactly one corresponding `leave()`, even in error paths. The standard pattern is to call `group.leave()` inside `defer { }` immediately after `enter()`, so the leave is guaranteed to execute regardless of how the scope exits. If there are more `leave()` calls than `enter()` calls (counter goes below zero), GCD raises a trap (`EXC_BAD_INSTRUCTION`) — it is a programming error and not catchable. If there are more `enter()` calls than `leave()` calls, the group never reaches zero and `notify`/`wait` never fire, causing a silent hang.

### Expert

**Q: Describe a scenario where using `DispatchSemaphore.wait()` inside a GCD block causes thread explosion, and explain the fix.**

A: Suppose you submit 100 tasks to `DispatchQueue.global()`, each of which calls `semaphore.wait()` with a limit of 3. The first 3 tasks acquire the semaphore and proceed; the remaining 97 are blocked inside their GCD work blocks. GCD sees 97 blocked threads and, to keep the system moving, creates new threads to handle new submissions — up to its 64-thread cap (and sometimes beyond, triggering the kernel's thread limit). The system now has dozens of threads doing nothing but sleeping on a semaphore, consuming stack memory and scheduler overhead. This is **thread explosion**. The fix: don't submit all 100 tasks at once. Use an `OperationQueue` with `maxConcurrentOperationCount = 3` (which holds work in an internal queue rather than occupying threads), or redesign using Swift Concurrency's `TaskGroup` with `withTaskGroup` and process at most 3 child tasks concurrently.

## 6. Common Issues & Solutions

**Issue: `group.notify` never fires — app hangs silently.**

Solution: Check for missing `group.leave()` calls. Every code path — including early returns and error paths — must call `leave()`. Use `defer { group.leave() }` immediately after `group.enter()` to guarantee balance.

**Issue: `DispatchSemaphore.wait()` on the main thread deadlocks.**

Solution: Never block the main thread with `semaphore.wait()`. Move the call to a background queue, or restructure the code to use a callback/`notify` pattern or `async/await`.

**Issue: Barrier flag on `DispatchQueue.global()` has no effect — writes race with reads.**

Solution: Replace the global queue with a custom `DispatchQueue(label:attributes:.concurrent)`. Only custom concurrent queues honour the `.barrier` flag.

**Issue: Thread explosion when using semaphore to rate-limit network requests.**

Solution: Use `OperationQueue.maxConcurrentOperationCount` instead of a semaphore, or batch submissions manually. Alternatively, use `async/await` with a `TaskGroup` and limit child tasks to the desired concurrency level.

## 7. Related Topics

- [GCD & Dispatch Queues](gcd-dispatch-queue.md) — foundation: queues, QoS, async/sync
- [Operation & OperationQueue](operation-queue.md) — better alternative for rate-limiting and dependency graphs
- [async/await](async-await.md) — modern replacement; `async let` parallels DispatchGroup fan-out
- [Task & TaskGroup](task-taskgroup.md) — structured alternative to DispatchGroup
- [Concurrency Problems](concurrency-problems.md) — deadlocks, thread explosion
