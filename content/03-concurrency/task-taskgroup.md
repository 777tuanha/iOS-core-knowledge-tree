# Task & TaskGroup

## 1. Overview

`Task` and `TaskGroup` are the core building blocks of Swift's structured concurrency model. A `Task` is a unit of asynchronous work that runs concurrently with other tasks, carries a priority, can be cancelled, and participates in the task tree. A `TaskGroup` fans out multiple child tasks from a parent, waits for all of them to complete, and propagates cancellation and errors automatically. Together they provide the structured, tree-based approach to concurrency that replaces ad-hoc GCD and OperationQueue patterns for new Swift code.

## 2. Simple Explanation

A `Task` is like an employee you hire to do one job. You give them a job description (the closure), a priority (urgent vs. low), and you can fire them early if the project changes (cancel). When the employee finishes or is fired, they report back to you.

A `TaskGroup` is like a project manager who hires a team of employees for parallel work. The project manager doesn't leave the meeting room until all employees are done — and if the project gets cancelled, the manager fires all employees immediately.

The key insight: in structured concurrency, **employees can't outlive their manager**. You can never lose track of background work.

## 3. Deep iOS Knowledge

### Task Lifecycle

```
created → running ⇄ suspended → finished
                 ↓
             cancelled
```

A `Task` runs immediately when created. It suspends at `await` points, releasing its thread. It resumes when awaited work completes. Cancellation is cooperative — calling `task.cancel()` sets a flag; the task must check `Task.isCancelled` or call `try Task.checkCancellation()` to respond.

### Structured vs Unstructured Tasks

| Type | Created by | Inherits actor? | Inherits priority? | Cancellation |
|------|-----------|----------------|-------------------|-------------|
| Structured child task | `async let`, `withTaskGroup` | Yes | Yes | Cancelled with parent |
| Unstructured task | `Task { }` | Yes (captures current actor) | Yes | Independent |
| Detached task | `Task.detached { }` | No | No | Independent |

**Structured child tasks** (inside `withTaskGroup`) form the task tree. They are the preferred model.

**Unstructured tasks** (`Task { }`) are launched when you need to bridge from a non-async context (e.g., `viewDidLoad`). They inherit the current actor and priority but are not children of any parent task — you must cancel them manually or store the handle.

**Detached tasks** (`Task.detached { }`) are fully independent. They don't inherit actor or priority. Use sparingly — they're the least structured option.

### Task Priority

| Priority | Maps to GCD QoS | Use |
|----------|----------------|-----|
| `.high` | `.userInteractive` | User-facing immediate work |
| `.userInitiated` | `.userInitiated` | User-triggered, result needed soon |
| `.medium` | `.default` | General background |
| `.low` | `.utility` | Long operations |
| `.background` | `.background` | Maintenance, prefetch |
| `.utility` | `.utility` | Alias for `.low` |

Priority escalation works: a high-priority task awaiting a low-priority task will boost the low-priority task's effective priority.

### TaskGroup

`withTaskGroup(of:)` creates a group of child tasks that all return the same type. `withThrowingTaskGroup(of:)` allows child tasks to throw.

Key rules:
- `group.addTask { }` launches a child task immediately.
- Iterate the group with `for await result in group { }` to collect results as they complete.
- If any child throws (in `withThrowingTaskGroup`), the group cancels remaining children and rethrows.
- The group is automatically awaited at the end of the `withTaskGroup` body — you can't escape the group.

### Task Cancellation

Cancellation is **cooperative and recursive**:
- `task.cancel()` sets `isCancelled` on the task and all its structured children.
- `await` on a cancelled task throws `CancellationError` automatically for Swift stdlib async functions.
- Call `try Task.checkCancellation()` explicitly in CPU-bound loops.
- `Task.isCancelled` provides a non-throwing check.

### Actor Inheritance

`Task { }` inherits the actor of the enclosing scope. Inside a `@MainActor` context, `Task { }` also runs on the main actor — which can be a trap: you may accidentally do background work on the main thread. Use `Task.detached { }` or call a non-isolated async function to escape.

## 4. Practical Usage

```swift
import Foundation

// ── Unstructured Task from synchronous context ─────────────────
class FeedViewController: UIViewController {
    private var loadTask: Task<Void, Never>?

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        loadTask = Task { [weak self] in      // inherits @MainActor from UIViewController
            await self?.loadFeed()
        }
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        loadTask?.cancel()                    // cancel if user navigates away
    }

    @MainActor
    func loadFeed() async {
        do {
            let items = try await fetchFeedItems()
            display(items)
        } catch is CancellationError {
            // user navigated away — do nothing
        } catch {
            showError(error)
        }
    }

    func display(_ items: [String]) {}
    func showError(_ error: Error) {}
}

// ── TaskGroup: parallel fetch with result collection ────────────
func fetchAllProfiles(ids: [String]) async throws -> [Profile] {
    try await withThrowingTaskGroup(of: Profile.self) { group in
        for id in ids {
            group.addTask {                   // each ID fetched concurrently
                try await fetchProfile(id: id)
            }
        }

        var profiles: [Profile] = []
        for try await profile in group {     // collect results as they arrive
            profiles.append(profile)
        }
        return profiles
    }
}

// ── Limiting concurrency inside a TaskGroup ─────────────────────
func downloadImages(urls: [URL], maxConcurrent: Int = 4) async throws -> [Data] {
    try await withThrowingTaskGroup(of: Data.self) { group in
        var results: [Data] = []
        var inFlight = 0

        for url in urls {
            if inFlight >= maxConcurrent {
                // Wait for one to finish before launching another
                if let data = try await group.next() {
                    results.append(data)
                    inFlight -= 1
                }
            }
            group.addTask { try await downloadData(from: url) }
            inFlight += 1
        }

        // Collect remaining
        for try await data in group {
            results.append(data)
        }
        return results
    }
}

// ── Task cancellation with checkCancellation ────────────────────
func processItems(_ items: [Int]) async throws -> [Int] {
    var results: [Int] = []
    for item in items {
        try Task.checkCancellation()         // throws CancellationError if cancelled
        let processed = await heavyProcess(item)
        results.append(processed)
    }
    return results
}

// ── Detached task to escape actor context ──────────────────────
@MainActor
class ViewModel {
    func startBackgroundSync() {
        // Task { } would run on MainActor — wrong for background work
        Task.detached(priority: .background) {
            // This runs off the main actor
            await performSync()
        }
    }
}

// ── async let for structured parallel calls ─────────────────────
func loadDashboard() async throws -> Dashboard {
    async let user    = fetchUser(id: "1")       // starts immediately
    async let metrics = fetchMetrics(userId: "1") // starts immediately

    return try await Dashboard(                  // waits for both
        user: user,
        metrics: metrics
    )
}

// Stubs
struct Profile {}
struct Dashboard { init(user: Profile, metrics: [String]) {} }
func fetchFeedItems() async throws -> [String] { [] }
func fetchProfile(id: String) async throws -> Profile { Profile() }
func downloadData(from url: URL) async throws -> Data { Data() }
func heavyProcess(_ item: Int) async -> Int { item }
func performSync() async {}
func fetchUser(id: String) async throws -> Profile { Profile() }
func fetchMetrics(userId: String) async throws -> [String] { [] }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `Task { }` and `Task.detached { }`?**

A: `Task { }` inherits the actor context and priority of the enclosing scope. If created inside a `@MainActor` function, the task also runs on the main actor. `Task.detached { }` creates a fully independent task with no inherited actor or priority — it starts with `.medium` priority and runs on the cooperative thread pool with no actor isolation. Detached tasks are useful for background work that must run off the main actor, but they lose the structured lifetime guarantees: they are not children of the enclosing scope.

**Q: How do you cancel a `Task` and how does the task respond?**

A: Call `task.cancel()` on the `Task` value returned when creating a task. This sets the `isCancelled` flag on the task (and all its structured children). The task must respond cooperatively: check `Task.isCancelled` in loops, or call `try Task.checkCancellation()` which throws `CancellationError` if the task is cancelled. Many Swift stdlib async functions (including `URLSession`) automatically throw `CancellationError` when the task is cancelled.

### Hard

**Q: How does `withTaskGroup` handle an error thrown by a child task?**

A: In `withThrowingTaskGroup`, if any child task throws, the group automatically cancels all remaining children and the error is rethrown when you `for try await` or `try await group.waitForAll()`. Remaining children receive a cancellation signal (their `isCancelled` becomes `true`) and are expected to clean up and exit. The group's body closure then exits with the thrown error. If you want to handle child errors individually (not propagate them), use `withTaskGroup` (non-throwing) and handle errors inside each child task, returning a `Result` type instead.

**Q: What does it mean for a `Task { }` to inherit the actor context, and when does this cause bugs?**

A: When you write `Task { }` inside a `@MainActor`-isolated function or class, the task closure is also isolated to `@MainActor`. All `await`-resumed continuations in that task run on the main thread. This is often correct (e.g., updating UI after an async call without needing `DispatchQueue.main.async`). The bug: you might accidentally perform long-running work inside a `Task { }` thinking it will run in the background, but it actually blocks the main actor between suspension points. If your task has no `await` (or calls CPU-bound non-async code), it runs entirely on the main thread. Fix: use `Task.detached { }` or call a `nonisolated` async function to move CPU work off the main actor.

### Expert

**Q: How would you implement a rate-limited concurrent download of 1000 images using TaskGroup, and how does it compare to using DispatchSemaphore?**

A: With `TaskGroup`, limit concurrency by controlling how many `addTask` calls are outstanding at once — wait for one child to finish before adding the next when you've hit your concurrency cap. This approach is superior to `DispatchSemaphore` because: (1) tasks suspend at `await` rather than blocking a thread — no thread explosion; (2) cancellation propagates automatically — if the parent is cancelled, all downloads stop immediately; (3) errors are structured — the first failure cancels remaining work and rethrows. With `DispatchSemaphore`, each blocked task holds a real thread from the GCD pool. For 1000 images with `semaphore(value: 4)`, you'd have 1000 queue submissions, 4 running, and up to 996 threads blocked in `semaphore.wait()` — potentially exhausting the 64-thread pool cap and causing thread explosion. The TaskGroup approach uses O(concurrency limit) threads regardless of total task count.

## 6. Common Issues & Solutions

**Issue: Task launched in `viewDidLoad` continues running after view is dismissed.**

Solution: Store the `Task` handle in a property and call `task.cancel()` in `viewDidDisappear` or `deinit`. Alternatively, use a scoped pattern where the task is a child of a `TaskGroup` managed by a `ViewModel` that is torn down with the view.

**Issue: `Task { }` inside `@MainActor` context runs CPU-bound work on the main thread, causing UI jank.**

Solution: Use `Task.detached { }` for CPU-bound work, or call a `nonisolated` async function that moves execution off the main actor.

**Issue: `withTaskGroup` results arrive out of order.**

Solution: That is expected — `for await result in group` yields results in completion order, not submission order. If you need ordered results, associate each task with its index: store results in a pre-allocated array by index, or collect `(index, value)` tuples.

**Issue: Child task error silently swallowed — other tasks continue running.**

Solution: Use `withThrowingTaskGroup` and `for try await` to propagate errors. If you use `withTaskGroup` with `Result` returns, explicitly check each result and handle failures.

## 7. Related Topics

- [async/await](async-await.md) — the syntax that Task and TaskGroup build on
- [Actors](actors.md) — how tasks interact with actor isolation
- [Operation & OperationQueue](operation-queue.md) — predecessor pattern for dependency graphs
- [DispatchGroup, Semaphore & Barrier](dispatch-group-semaphore.md) — GCD alternatives for coordination
- [Concurrency Problems](concurrency-problems.md) — cancellation, thread explosion, priority inversion
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — capture semantics in Task closures
