# Actors

## 1. Overview

`actor` is a Swift reference type (introduced in Swift 5.5) that protects its mutable state from concurrent access by serialising all access through its **executor** — a serial queue-like mechanism that ensures only one caller accesses the actor's state at a time. Actors provide data-race safety enforced at **compile time**: the compiler rejects code that accesses actor-isolated state from outside the actor without `await`. The `MainActor` global actor confines UI code to the main thread. The `Sendable` protocol marks types safe to send across concurrency boundaries. Together these form Swift's high-level concurrency safety model.

## 2. Simple Explanation

An `actor` is like a personal assistant with a single phone line. Anyone can call them (send messages), but they take calls one at a time in order. While they're handling your request, no one else can interrupt. You don't need to worry about two callers giving conflicting instructions at the same time — the assistant serialises everything.

Unlike a `class` protected by a lock, you don't hold the lock across a function call. Instead, you "call" the actor (with `await`) and step back while they handle your request — freeing you to do other things in the meantime.

## 3. Deep iOS Knowledge

### Actor Isolation

Every stored property and method of an `actor` is **isolated** to that actor by default. To access them from outside, you must `await` — signalling that you may need to suspend until the actor is free. The compiler statically enforces this:

```swift
actor Counter {
    var value = 0
    func increment() { value += 1 }  // isolated — no await needed internally
}

let c = Counter()
await c.increment()  // from outside: must await
```

### nonisolated

Mark methods or properties `nonisolated` to indicate they don't access actor state and can be called without `await`. Useful for implementing protocol requirements that aren't async, or for computed properties that derive from value-type state:

```swift
actor Logger {
    let id: String               // 'let' constants are implicitly nonisolated
    nonisolated func tag() -> String { "[\(id)]" }  // safe — no mutable state
}
```

### MainActor

`@MainActor` is a global actor backed by the main thread's serial executor. It provides compile-time enforcement that UIKit/SwiftUI code runs on the main thread. You can apply it to:
- **A whole class**: `@MainActor class ViewModel { }`
- **A method**: `@MainActor func updateUI() { }`
- **A property**: `@MainActor var label: UILabel`

All `await`-resumed continuations inside a `@MainActor` function run on the main thread — no `DispatchQueue.main.async` needed.

### Global Actors

A global actor is a singleton actor used as an annotation (`@SomeActor`). `MainActor` is the only built-in global actor, but you can define your own:

```swift
@globalActor
actor DatabaseActor {
    static let shared = DatabaseActor()
}

@DatabaseActor func saveRecord(_ record: Record) async { }
```

### Sendable

`Sendable` is a marker protocol indicating a type is safe to transfer across concurrency boundaries (actor-to-actor, task-to-task). Types that conform to `Sendable` must guarantee no shared mutable state:
- Value types (structs, enums) with `Sendable` stored properties are implicitly `Sendable`.
- Actors are `Sendable` (they serialise their own state).
- Classes can be `Sendable` only if they are immutable (all `let` properties) or internally synchronised.

In strict concurrency mode (`-strict-concurrency=complete`), the compiler warns when non-`Sendable` values cross concurrency boundaries.

### Actor Reentrancy

An actor is **reentrant**: while an actor is awaiting (suspended at an `await` point inside one of its own methods), another caller can run a different method on the same actor. This prevents deadlocks but means actor state can change between `await` points:

```swift
actor BankAccount {
    var balance: Double = 1000

    func transfer(amount: Double, to other: BankAccount) async {
        guard balance >= amount else { return }
        balance -= amount                  // (1) deducted
        await other.deposit(amount)        // (2) suspended here — another transfer can run!
        // At (3), balance may have changed again due to reentrancy
    }

    func deposit(_ amount: Double) {
        balance += amount
    }
}
```

The fix: complete all state reads and writes **before** the first `await`, or validate preconditions again after each `await`.

### Actor vs Class + Serial Queue

| Feature | `actor` | `class` + serial `DispatchQueue` |
|---------|---------|----------------------------------|
| Compile-time enforcement | Yes | No |
| Reentrancy | Safe (cooperative) | Depends on implementation |
| async/await integration | Native | Manual (`sync`/`async`) |
| Sendable support | Built-in | Manual |
| Thread | Cooperative pool | GCD thread pool |

## 4. Practical Usage

```swift
import Foundation

// ── Basic actor for thread-safe state ──────────────────────────
actor ImageCache {
    private var cache: [URL: Data] = [:]

    func store(_ data: Data, for url: URL) {
        cache[url] = data               // no locks needed — actor serialises
    }

    func data(for url: URL) -> Data? {
        cache[url]                      // reads are also serialised
    }

    nonisolated func cacheKey(for url: URL) -> String {
        url.absoluteString              // no actor state — callable without await
    }
}

// Usage from async context
let cache = ImageCache()
await cache.store(imageData, for: imageURL)
let data = await cache.data(for: imageURL)

// ── @MainActor for UI view models ──────────────────────────────
@MainActor
class UserViewModel: ObservableObject {
    @Published var name: String = ""
    @Published var isLoading: Bool = false

    func loadUser(id: String) async {
        isLoading = true                // on main thread — safe for @Published
        defer { isLoading = false }

        do {
            let user = try await fetchUser(id: id)   // suspends; may hop threads
            name = user.displayName                  // resumes on MainActor — safe
        } catch {
            print("Error: \(error)")
        }
    }
}

// ── Reentrancy — guard against state changes after await ────────
actor Wallet {
    var balance: Int = 100

    func withdraw(amount: Int) async throws {
        // Validate BEFORE the await
        guard balance >= amount else { throw WalletError.insufficientFunds }

        balance -= amount               // mutate before any await

        // Any await here would allow another method to run
        await logTransaction(amount: -amount)  // reentrancy window is fine now
    }

    private func logTransaction(amount: Int) async {
        // simulated async logging
    }
}

// ── Sendable — crossing actor boundaries ───────────────────────
// This struct is Sendable (all stored properties are value types)
struct Message: Sendable {
    let id: UUID
    let text: String
}

actor MessageStore {
    func add(_ message: Message) {
        // Message crosses the actor boundary — must be Sendable
    }
}

// ── Custom global actor ────────────────────────────────────────
@globalActor
actor NetworkActor {
    static let shared = NetworkActor()
}

@NetworkActor
func performRequest(url: URL) async throws -> Data {
    // Isolated to NetworkActor — one request at a time
    let (data, _) = try await URLSession.shared.data(from: url)
    return data
}

// ── Calling actor from non-async context ──────────────────────
class LegacyController {
    let cache = ImageCache()

    func prefetch(url: URL) {
        Task {
            let data = try? await URLSession.shared.data(from: url).0
            if let data {
                await cache.store(data, for: url)
            }
        }
    }
}

// Stubs
var imageData = Data()
var imageURL = URL(string: "https://example.com/image.png")!
struct User { var displayName: String = "" }
func fetchUser(id: String) async throws -> User { User() }
enum WalletError: Error { case insufficientFunds }
```

## 5. Interview Questions & Answers

### Basic

**Q: What problem does `actor` solve compared to using a class with a serial `DispatchQueue`?**

A: Both serialise access to shared mutable state, but `actor` does it with **compile-time enforcement**. The compiler rejects code that accesses actor-isolated properties from outside without `await` — you can't accidentally forget the queue. With a class + serial queue, accessing a property without dispatching through the queue is a silent runtime bug. Additionally, actors integrate natively with `async/await`, use the cooperative thread pool (suspending instead of blocking), and work automatically with `Sendable` checking.

**Q: What is `@MainActor` and why is it preferred over `DispatchQueue.main.async`?**

A: `@MainActor` is a global actor that confines code to the main thread. When applied to a class or method, the compiler ensures all accesses are on the main thread. After an `await` inside a `@MainActor` function, the continuation automatically resumes on the main thread — no explicit `DispatchQueue.main.async` needed. This eliminates a class of bugs where developers forget to dispatch UI updates back to the main thread after a background operation.

### Hard

**Q: What is actor reentrancy and how can it lead to bugs?**

A: An actor is reentrant: while it is suspended at an `await` point inside one of its own methods, other callers can run different methods on the same actor. The actor remains safe from data races (it still serialises all method execution), but it can observe unexpected state changes. For example: a method reads a property value, `await`s an async operation, and then reads the property again — the value may have changed because another method ran during the suspension. The fix is to read all necessary state **before** the first `await` and avoid assuming state is unchanged after a suspension point.

**Q: How does `Sendable` relate to actors?**

A: `Sendable` is a protocol marking types safe to pass across concurrency boundaries (actor-to-actor, task handoffs). Actors enforce that values sent to them are `Sendable` — if you try to send a non-`Sendable` class instance to an actor, the compiler (in strict concurrency mode) will warn because the sender could retain a reference to the shared mutable state, defeating the actor's protection. Value types (structs, enums) with `Sendable` stored properties are automatically `Sendable`. Classes must be explicitly marked and must either be immutable or internally synchronised. Actors themselves are `Sendable` because they protect their own state.

### Expert

**Q: Describe a scenario where two actors can deadlock, and how Swift's cooperative model prevents it.**

A: In traditional locking (mutexes), Actor A holds a lock and calls into Actor B, which tries to acquire Actor A's lock — classic deadlock. Swift actors cannot deadlock in this way because they use `await`, not blocking locks. When Actor A calls `await actorB.someMethod()`, Actor A suspends — it does not hold any lock that Actor B would need. Actor B can freely run and even call back into Actor A (queuing behind any ongoing work). The cooperative model eliminates lock-hold-and-wait, which is one of the four necessary conditions for deadlock. The tradeoff is reentrancy: because Actor A suspends rather than holding a lock, Actor A's state can change while it's waiting, requiring careful design around `await` points.

## 6. Common Issues & Solutions

**Issue: Accessing actor property from a synchronous context — compiler error "expression is 'async' but is not marked with 'await'".**

Solution: Wrap the access in `Task { }` or make the calling function `async`. If the property is a constant (`let`), mark it `nonisolated` to allow synchronous access.

**Issue: Reentrancy bug — double withdrawal from a wallet actor.**

Solution: Complete all state validation and mutation **before** the first `await`. If you must read state after an `await`, re-validate the preconditions.

**Issue: `@MainActor` class method calling an async function that hops off the main thread — UI update after `await` runs on wrong thread.**

Solution: This should not happen with `@MainActor` — continuations after `await` inside a `@MainActor` function resume on the main actor. Verify that the class is correctly annotated and not calling `Task.detached { }`, which loses the actor context.

**Issue: Non-`Sendable` value passed to actor triggers compiler warning in strict concurrency.**

Solution: Make the type conform to `Sendable`. For value types, add explicit conformance. For classes, either make all properties `let` and the class `final`, or use `@unchecked Sendable` with an internal lock (document why it's safe).

## 7. Related Topics

- [async/await](async-await.md) — the async calling convention that actors use
- [Task & TaskGroup](task-taskgroup.md) — how tasks interact with actor isolation
- [Concurrency Problems](concurrency-problems.md) — race conditions that actors prevent
- [ARC](../02-memory-management/arc.md) — actors are reference types; ARC manages their lifetime
- [Weak vs Unowned](../01-swift-language/weak-vs-unowned.md) — capture semantics when closures reference actors
- [UI Frameworks](../04-ui-frameworks/index.md) — `@MainActor` and UIKit/SwiftUI thread requirements
