# Concurrency Problems

## 1. Overview

Concurrency bugs are among the hardest to reproduce and debug: they are timing-dependent, environment-sensitive, and often disappear under a debugger. The four classic problems are **race conditions** (concurrent unsynchronised state access), **deadlocks** (circular wait), **thread explosion** (exhausting the thread pool), and **priority inversion** (a high-priority task blocked by a low-priority task holding a resource). Understanding the root cause of each, the detection tools, and the correct fix is essential for production iOS engineering and a standard interview deep-dive area.

## 2. Simple Explanation

**Race condition**: Two people edit the same document simultaneously without knowing about each other — one person's changes overwrite the other's.

**Deadlock**: Two cars at a single-lane bridge from opposite sides, each waiting for the other to back up first. Neither moves.

**Thread explosion**: A post office where every parcel requires hiring a new postal worker. After 64 parcels the warehouse is full of idle workers waiting on slow deliveries, and no new workers can be hired.

**Priority inversion**: The CEO (high priority) needs a report that a summer intern (low priority) is preparing, but the intern is stuck waiting for the printer held by a middle manager (medium priority). The CEO waits while lower-priority work blocks higher-priority work.

## 3. Deep iOS Knowledge

### Race Condition

A race condition occurs when two or more threads access shared mutable state without synchronisation, and the result depends on the order of execution.

**Types:**
- **Read-write race**: One thread reads while another writes — reads get torn values.
- **Write-write race**: Two threads write simultaneously — final value is indeterminate.
- **Check-then-act race**: Thread A checks a condition, Thread B modifies it before Thread A acts on the result.

**Detection tools:**
- **Thread Sanitiser (TSan)**: Instruments every memory access and reports races at runtime. Enable in the Xcode scheme (Diagnostics → Thread Sanitiser). TSan adds ~2× runtime overhead — use in testing, not production.
- **Swift Strict Concurrency** (`-strict-concurrency=complete`): Static analysis that flags potential data races at compile time in Swift Concurrency code.

**Fixes:**
- Protect shared mutable state with a serial `DispatchQueue`, a lock (`NSLock`, `os_unfair_lock`), or an `actor`.
- Prefer immutability — value types passed across threads can't race.
- Use `actor` for new Swift code.

### Deadlock

A deadlock requires all four Coffman conditions simultaneously:
1. **Mutual exclusion**: A resource is held exclusively.
2. **Hold and wait**: A thread holds one resource and waits for another.
3. **No preemption**: Resources can't be forcibly taken.
4. **Circular wait**: Thread A waits for Thread B's resource; Thread B waits for Thread A's.

**Common iOS patterns that deadlock:**
- `DispatchQueue.main.sync { }` called from the main thread.
- `queue.sync { queue.sync { } }` — re-entrant sync on the same serial queue.
- Two serial queues doing `sync` into each other from their own work blocks.
- `OperationQueue` with circular dependencies.

**Detection:**
- Xcode debugger → pause all threads → inspect thread backtraces for threads blocked in `dispatch_sync` or lock acquisition.
- Instruments → System Trace → look for threads stuck in kernel `__psynch_mutexwait` or `DISPATCH_WAIT_FOR_QUEUE`.

**Fixes:**
- Eliminate `sync` calls that could form cycles; prefer `async`.
- Never call `main.sync` from the main thread.
- Use lock ordering: always acquire locks in the same global order across all threads.
- Swift actors prevent deadlock structurally — suspension replaces lock-and-hold.

### Thread Explosion

GCD maintains a thread pool. When all threads are blocked (on `sync`, `semaphore.wait`, or a blocking I/O call), GCD creates new threads to handle new submissions — up to a per-process cap (typically 64 threads). Beyond the cap, new work items queue but threads cannot be created, starving the system.

Each thread consumes:
- ~512 KB of stack space (configurable)
- Kernel resources for scheduling
- CPU time for context switching

**Common cause**: submitting many async tasks that immediately block on a semaphore or synchronous I/O, combined with a backlog of queued work waiting for threads.

**Detection:**
- Instruments → Threads — count the live threads; > 30–40 threads is suspicious.
- Xcode debug navigator → CPU → threads panel.
- Crash reports showing "Unable to allocate kernel memory for thread" or `KERN_RESOURCE_SHORTAGE`.

**Fixes:**
- Replace `semaphore.wait()` with `OperationQueue.maxConcurrentOperationCount`.
- Replace blocking threads with `async/await` and Swift Concurrency's cooperative pool.
- Limit queue depth before submission rather than after (don't submit 1000 tasks then throttle with a semaphore).

### Priority Inversion

Priority inversion occurs when a high-priority task is blocked on a resource held by a low-priority task. On a busy system, the scheduler gives CPU to medium-priority tasks, starving the low-priority task — which means the high-priority task never gets unblocked.

**GCD mitigates this** with **priority inheritance / boosting**: when a high-QoS task submits `sync` to a lower-QoS queue, GCD temporarily raises the effective QoS of the target queue to match the submitting task.

**Swift Concurrency mitigates this** via **task priority escalation**: when a high-priority task awaits a lower-priority task, the runtime raises the lower task's effective priority.

**Remaining risk areas:**
- `os_unfair_lock` supports priority inheritance; `NSLock`/`pthread_mutex` do not by default.
- `DispatchSemaphore` does not support priority inheritance — avoid using semaphores as mutexes in real-time / high-priority contexts.
- Background `URLSession` tasks can starve foreground downloads if the session is misconfigured.

**Detection:**
- Instruments → System Trace → CPU Usage lane — look for high-priority thread (red) waiting while medium-priority thread (yellow) runs holding the resource.

### Summary Table

| Problem | Root cause | Key detection tool | Primary fix |
|---------|-----------|-------------------|-------------|
| Race condition | Unsynchronised shared mutable state | TSan, strict concurrency | `actor`, serial queue, lock |
| Deadlock | Circular lock acquisition / `sync` cycle | Thread backtrace, System Trace | Eliminate sync cycles; use `async` |
| Thread explosion | Many blocked threads exhausting pool | Instruments Threads, crash logs | `OperationQueue` max count; Swift Concurrency |
| Priority inversion | Low-priority lock holder; no inheritance | System Trace CPU lane | `os_unfair_lock`; GCD sync (auto-boosting) |

## 4. Practical Usage

```swift
import Foundation

// ── Race condition: WRONG (no synchronisation) ─────────────────
class UnsafeCounter {
    var count = 0

    // Called from multiple threads simultaneously — data race!
    func increment() {
        count += 1   // read-modify-write is NOT atomic on any platform
    }
}

// ── Race condition: FIXED with actor ───────────────────────────
actor SafeCounter {
    var count = 0
    func increment() { count += 1 }   // serialised by actor
    func value() -> Int { count }
}

// ── Race condition: FIXED with serial queue ─────────────────────
class QueueSafeCounter {
    private var count = 0
    private let queue = DispatchQueue(label: "com.app.counter")

    func increment() {
        queue.async { self.count += 1 }
    }

    func value() -> Int {
        queue.sync { count }
    }
}

// ── Deadlock: WRONG ────────────────────────────────────────────
func deadlockExample() {
    // Never do this from the main thread
    DispatchQueue.main.sync {    // blocks main thread waiting for main queue
        print("Never reached")  // main queue can't dequeue — main thread is blocked
    }
}

// ── Deadlock: FIXED ────────────────────────────────────────────
func noDeadlock() {
    if Thread.isMainThread {
        // Already on main thread — call directly
        updateUI()
    } else {
        DispatchQueue.main.async { self.updateUI() }
    }
}
// Or simply always use async:
func safeUpdate() {
    DispatchQueue.main.async { self.updateUI() }  // safe from any thread
}

// ── Thread explosion: WRONG (semaphore rate-limiter) ───────────
func downloadAllWrong(urls: [URL]) {
    let semaphore = DispatchSemaphore(value: 4)
    for url in urls {
        DispatchQueue.global().async {
            semaphore.wait()         // up to (urls.count - 4) threads blocked here
            defer { semaphore.signal() }
            _ = try? Data(contentsOf: url)
        }
    }
    // With 1000 URLs: 996 threads sitting idle, consuming stack memory
}

// ── Thread explosion: FIXED with OperationQueue ─────────────────
func downloadAllFixed(urls: [URL]) {
    let queue = OperationQueue()
    queue.maxConcurrentOperationCount = 4   // queue holds work, not threads

    for url in urls {
        queue.addOperation {
            _ = try? Data(contentsOf: url)  // only 4 threads ever run at once
        }
    }
}

// ── Thread explosion: FIXED with TaskGroup ──────────────────────
func downloadAllAsync(urls: [URL]) async {
    await withTaskGroup(of: Void.self) { group in
        var inFlight = 0
        for url in urls {
            if inFlight >= 4 {
                await group.next()   // suspend (not block) until one completes
                inFlight -= 1
            }
            group.addTask {
                _ = try? await URLSession.shared.data(from: url)
            }
            inFlight += 1
        }
    }
}

// ── Priority inversion: use os_unfair_lock (supports PI) ────────
import os

class PriorityAwareCache {
    private var storage: [String: Data] = [:]
    private var lock = os_unfair_lock()   // supports priority inheritance

    func value(for key: String) -> Data? {
        os_unfair_lock_lock(&lock)
        defer { os_unfair_lock_unlock(&lock) }
        return storage[key]
    }

    func setValue(_ data: Data, for key: String) {
        os_unfair_lock_lock(&lock)
        defer { os_unfair_lock_unlock(&lock) }
        storage[key] = data
    }
}

func updateUI() {}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a race condition and how do you prevent it in Swift?**

A: A race condition occurs when two or more threads access shared mutable state concurrently without synchronisation, and the result depends on thread scheduling order. In Swift, prevention options are: (1) Use an `actor` — the compiler enforces that all access is serialised and requires `await` from outside. (2) Use a serial `DispatchQueue` — dispatch all reads and writes through it. (3) Use a lock (`os_unfair_lock`, `NSLock`) — simpler but requires manual discipline. (4) Use immutable value types — structs copied across threads can't race. Thread Sanitiser (TSan) detects races at runtime.

**Q: Describe a deadlock scenario in iOS and how to fix it.**

A: Classic scenario: calling `DispatchQueue.main.sync { }` from the main thread. The main thread blocks waiting for the submitted block to execute, but the block can't execute because the main queue's thread (the main thread) is blocked. It's a circular wait. Fix: always use `async` when dispatching to any queue from within that same queue. Never call `.sync` on the current queue, and never call `DispatchQueue.main.sync` from the main thread.

### Hard

**Q: How does GCD prevent priority inversion, and what are its limitations?**

A: GCD implements **automatic QoS boosting**: when you call `queue.sync { }` from a higher-QoS context, GCD temporarily raises the effective QoS of the target queue to match the caller's. This prevents the scheduler from starving the target queue's work in favour of unrelated medium-priority tasks. However, GCD's boosting only helps for `sync` dispatches — it does not propagate through `DispatchSemaphore.wait()`, which has no knowledge of the waiting task's priority. `os_unfair_lock` (the lowest-level lock Apple exposes) supports kernel-level priority inheritance. `NSLock` wraps `pthread_mutex` without priority inheritance by default. For critical high-priority-to-low-priority lock interactions, prefer `os_unfair_lock` or design with actors and Swift Concurrency, which handle priority escalation natively.

**Q: What is thread explosion and how does Swift Concurrency avoid it?**

A: Thread explosion occurs when many GCD work items block on synchronous operations (semaphores, I/O), causing GCD to create new threads to keep the pool moving — eventually exhausting the 64-thread cap and degrading performance. Swift Concurrency uses a **cooperative thread pool** sized to the number of CPU cores. Tasks `await` (suspend) instead of blocking threads. A suspended task releases its thread immediately, making it available for other ready tasks. No matter how many tasks are awaiting, only `N` threads (N ≈ CPU cores) are active at once. This is fundamentally more scalable than the GCD blocking model for high-concurrency workloads.

### Expert

**Q: How does Thread Sanitiser detect races, and why can it produce false positives?**

A: TSan instruments every memory read and write at compile time, inserting shadow memory accesses that track which thread last accessed each memory location and what synchronisation primitives were used. At runtime, TSan uses a happens-before analysis based on synchronisation events (lock acquire/release, thread fork/join, signal/wait) to determine whether two conflicting accesses (at least one being a write) could have occurred without one happening-before the other. If so, it's a race. False positives arise when: (1) custom synchronisation is used that TSan doesn't understand (e.g., a spin lock using atomic operations without TSan instrumentation); (2) `@unchecked Sendable` is used to assert safety that TSan can't verify; (3) intentional benign races (e.g., a flag read without sync that is only written once at startup). The Swift team added TSan annotations (`_swift_tsan_acquire`) to Swift's own synchronisation primitives so TSan understands them, but custom C-level atomics may still produce false positives.

## 6. Common Issues & Solutions

**Issue: App crashes intermittently with EXC_BAD_ACCESS — no consistent stack trace.**

Solution: Enable Thread Sanitiser (TSan) in the Xcode scheme. Run the affected user flow. TSan will pin down the exact memory location and the two racing accesses with their stack traces. Fix with an `actor` or serial queue around the shared state.

**Issue: App hangs — spinning wheel, no crash.**

Solution: Pause all threads in Xcode debugger and examine backtraces. Look for threads blocked in `dispatch_sync`, `semaphore_wait`, or `pthread_mutex_lock`. Identify the circular dependency and break it with `async`.

**Issue: Background image processing UI is janky even though work is on a background queue.**

Solution: Check Instruments → Time Profiler. Look for unexpected main-thread work during the operation. Confirm the background queue is not submitting `sync` to the main queue inside the loop. Also verify QoS — `.background` queues are throttled on battery; use `.utility` for user-visible progress.

**Issue: Network requests time out on devices but work in Simulator.**

Solution: This is often a thread explosion or priority inversion issue. On device the GCD thread pool is smaller and throttling is more aggressive. Profile with Instruments → System Trace on device. Look for thread pool exhaustion (all threads sleeping on semaphores) or low-priority network tasks being starved by medium-priority work.

## 7. Related Topics

- [GCD & Dispatch Queues](gcd-dispatch-queue.md) — sync/async, QoS — the source of many deadlock and explosion patterns
- [DispatchGroup, Semaphore & Barrier](dispatch-group-semaphore.md) — semaphore misuse leads to thread explosion
- [Actors](actors.md) — compiler-enforced solution to race conditions
- [Task & TaskGroup](task-taskgroup.md) — cooperative pool eliminates thread explosion
- [Operation & OperationQueue](operation-queue.md) — `maxConcurrentOperationCount` to limit thread use
