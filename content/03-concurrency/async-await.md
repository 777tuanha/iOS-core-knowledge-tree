# async/await

## 1. Overview

`async`/`await` is Swift's built-in syntax for writing asynchronous code that reads like synchronous code. Introduced in Swift 5.5 (iOS 15), it replaces callback chains and Combine pipelines for most async use cases. A function marked `async` can **suspend** — it pauses execution without blocking its thread, allowing the thread to do other work. When the awaited value is ready, the function resumes, potentially on a different thread. This is part of Swift's **structured concurrency** model, where asynchronous work forms a tree of tasks with well-defined lifetimes.

## 2. Simple Explanation

Imagine you're a chef (a thread) and you put a dish in the oven (an async operation). With traditional callbacks, you'd have to stand next to the oven and do nothing else until the timer rings. With `async/await`, you set the oven timer, walk away, and let the kitchen manager (the Swift runtime) tap you on the shoulder when the dish is ready — meanwhile you're free to chop vegetables for another order.

Critically, `await` doesn't freeze you — it frees you. The thread is released to do other work; you (the logical task) just sleep until the oven timer fires.

## 3. Deep iOS Knowledge

### Suspension Points

Every `await` is a **potential suspension point** — the function may or may not actually suspend depending on whether the awaited value is immediately available. If it suspends, the thread is released back to the pool. When the awaited work completes, the Swift runtime reschedules the continuation — possibly on a different thread (unless bound to an actor or the main actor).

### async let — Parallel Async Calls

`async let` starts a child task immediately and continues executing the parent. The `await` on the binding is where the parent waits. This enables structured parallelism:

```swift
async let profile = fetchProfile()   // starts immediately
async let posts   = fetchPosts()     // starts immediately, runs in parallel
let (p, q) = await (profile, posts)  // wait for both
```

Without `async let`, sequential `await` calls would run one after the other.

### Bridging Callback APIs with withCheckedContinuation

`withCheckedContinuation` wraps a callback-based API into an `async` function. The closure receives a `CheckedContinuation`; you call `resume(returning:)` or `resume(throwing:)` exactly once when the callback fires.

"Checked" adds a runtime assertion that `resume` is called exactly once — very helpful during development. `withUnsafeContinuation` skips the check for performance in production-critical paths.

### Structured Concurrency Model

In structured concurrency:
- Every async task has a parent.
- The parent cannot finish until all its children finish.
- Cancelling a parent automatically cancels all children.
- Errors propagate up the tree.

This tree structure prevents "fire and forget" tasks that outlive their context, eliminating a whole class of bugs present in GCD/callback code.

### Actor Executor & Thread Hopping

When you `await` a function on a different actor, the Swift runtime **hops threads** after the suspension — your continuation may resume on the actor's executor, not the original thread. This is transparent to your code but important for understanding execution order and for debugging stack traces.

### Cooperative vs Preemptive

Swift's concurrency model is **cooperative** — tasks yield at `await` points. There is no preemptive scheduling. This means a tight CPU loop with no `await` will never yield. For CPU-intensive work, use `Task.yield()` periodically to give the runtime a chance to schedule other tasks.

### Comparison to GCD

| Feature | GCD callbacks | async/await |
|---------|--------------|-------------|
| Thread blocking | `sync` blocks; `async` returns immediately | `await` suspends without blocking a thread |
| Composition | Nested callbacks ("callback hell") | Sequential readable code |
| Error handling | Pass error in callback | Native `throws` |
| Cancellation | Manual flag checks | `Task.isCancelled` / `checkCancellation()` |
| Structured lifetime | No | Yes — tasks scoped to their parent |

## 4. Practical Usage

```swift
import Foundation

// ── Basic async function with error propagation ─────────────────
func fetchUser(id: String) async throws -> User {
    let url = URL(string: "https://api.example.com/users/\(id)")!
    let (data, response) = try await URLSession.shared.data(from: url)

    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
        throw APIError.badResponse
    }
    return try JSONDecoder().decode(User.self, from: data)
}

// ── Sequential awaits (one after the other) ────────────────────
func loadUserDashboard(id: String) async throws -> Dashboard {
    let user    = try await fetchUser(id: id)        // waits for user first
    let posts   = try await fetchPosts(for: user)    // then fetches posts
    return Dashboard(user: user, posts: posts)
}

// ── async let for parallel execution ───────────────────────────
func loadUserDashboardFast(id: String) async throws -> Dashboard {
    async let user  = fetchUser(id: id)       // both start immediately
    async let posts = fetchPostsById(id: id)  // runs in parallel with user fetch

    // await both — whichever finishes last determines the total time
    return try await Dashboard(user: user, posts: posts)
}

// ── Bridging a callback API with withCheckedContinuation ────────
func legacyFetch(url: URL, completion: @escaping (Data?, Error?) -> Void) {
    URLSession.shared.dataTask(with: url) { data, _, error in
        completion(data, error)
    }.resume()
}

func fetchData(from url: URL) async throws -> Data {
    try await withCheckedThrowingContinuation { continuation in
        legacyFetch(url: url) { data, error in
            if let error {
                continuation.resume(throwing: error)    // must call exactly once
            } else if let data {
                continuation.resume(returning: data)    // must call exactly once
            } else {
                continuation.resume(throwing: APIError.noData)
            }
        }
    }
}

// ── Calling async code from synchronous context ─────────────────
// Use Task { } to bridge from non-async code (e.g., viewDidLoad)
class ProfileViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        Task {
            do {
                let user = try await fetchUser(id: "42")
                // After await, execution continues here (may be on different thread)
                await MainActor.run {
                    self.displayUser(user)    // ensure UI update on main thread
                }
            } catch {
                print("Failed: \(error)")
            }
        }
    }

    func displayUser(_ user: User) {}
}

// ── Task.yield() for CPU-bound work ────────────────────────────
func processLargeDataset(_ items: [Int]) async -> [Int] {
    var results: [Int] = []
    for (index, item) in items.enumerated() {
        results.append(item * item)

        // Yield every 1000 items to let other tasks run
        if index % 1000 == 0 {
            await Task.yield()
        }
    }
    return results
}

// Stubs
struct User: Decodable {}
struct Dashboard { init(user: User, posts: [String]) {} }
enum APIError: Error { case badResponse, noData }
func fetchPosts(for user: User) async throws -> [String] { [] }
func fetchPostsById(id: String) async throws -> [String] { [] }
```

## 5. Interview Questions & Answers

### Basic

**Q: What does `await` do — does it block the thread?**

A: No. `await` is a **suspension point** — the current task suspends and releases its thread back to the pool. The thread is free to execute other tasks while the awaited operation runs. When the awaited result is ready, the Swift runtime reschedules the continuation (the code after the `await`) on an appropriate thread. This is fundamentally different from `DispatchQueue.sync`, which truly blocks the thread.

**Q: What is `withCheckedContinuation` used for?**

A: It bridges callback-based (non-async) APIs into `async` functions. You call `withCheckedContinuation` inside an `async` function, and the closure receives a `CheckedContinuation`. You must call `resume(returning:)` or `resume(throwing:)` exactly once inside the callback of the legacy API. The "checked" variant adds a runtime assertion that `resume` is called exactly once, which helps catch bugs during development. When `resume` is called, the suspended `async` function resumes.

### Hard

**Q: What is the difference between sequential `await` and `async let`?**

A: Sequential `await` runs async operations one after another — the second doesn't start until the first finishes. `async let` starts a child task immediately in the background, while the current task continues executing. When you later `await` the `async let` binding, you wait only if the child hasn't finished yet. For independent operations that can run in parallel (e.g., fetching a user and their posts simultaneously), `async let` can halve the total time. For operations with a data dependency (you need the user's ID to fetch posts), sequential `await` is correct.

**Q: How does structured concurrency's task tree prevent common async bugs?**

A: In structured concurrency, every task has a parent scope. The parent cannot leave its scope until all child tasks finish. This guarantees: (1) no orphaned tasks that outlive their context (a common GCD bug where a completion block fires after the owning object is deallocated); (2) automatic cancellation propagation — cancelling the parent cancels all children, so you can't leak background work when a view disappears; (3) error propagation — if any child task throws, the error propagates to the parent, which cancels remaining siblings. GCD and callbacks have none of these guarantees by default.

### Expert

**Q: Explain how thread hopping works after an `await` and why it matters for UI code.**

A: When a task suspended at `await` resumes, the Swift runtime schedules the continuation on the executor of the function currently awaited. If you're calling into a non-actor async function, the continuation may resume on any thread in the cooperative pool — not necessarily the one you suspended from. If you're calling a function isolated to an actor (e.g., a `@MainActor` method), you'll resume on that actor's executor. This matters for UI code: if you `await` a background task inside a `@MainActor` function, the continuation after the `await` automatically resumes on the main actor — no `DispatchQueue.main.async` needed. However, if you `await` inside an unstructured `Task { }` started from a `@MainActor` context, the task inherits that context and all awaits resume on the main actor unless you explicitly hop off with a non-isolated async call.

## 6. Common Issues & Solutions

**Issue: UI update after `await` runs on a background thread, causing a UIKit crash.**

Solution: Wrap the update in `await MainActor.run { }`, or mark the function `@MainActor`. In Xcode, enable the Main Thread Checker (enabled by default) — it will flag off-main UIKit access at runtime.

**Issue: `withCheckedContinuation` crashes or hangs — "continuation resumed more than once" / never resumes.**

Solution: Ensure `resume` is called exactly once. Use `defer` if the callback has multiple paths. If the legacy API can call the callback multiple times (e.g., a streaming API), use `AsyncStream` instead of a continuation.

**Issue: Sequential `await` is slow — two independent network calls take twice as long.**

Solution: Replace sequential `await` calls with `async let` to run them in parallel. If there are more than two, use `withTaskGroup`.

**Issue: `async` function called from `viewDidLoad` — compiler error "expression is 'async' but is not marked with 'await'".**

Solution: Wrap the call in `Task { }` to bridge from the synchronous context. The `Task` creates an unstructured task that runs concurrently and does not need `await` at the call site.

## 7. Related Topics

- [Task & TaskGroup](task-taskgroup.md) — structured task management building on async/await
- [Actors](actors.md) — how async functions relate to actor isolation and thread safety
- [GCD & Dispatch Queues](gcd-dispatch-queue.md) — the layer async/await replaces for most use cases
- [Concurrency Problems](concurrency-problems.md) — race conditions that async/await helps prevent
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — capture semantics in async closures
