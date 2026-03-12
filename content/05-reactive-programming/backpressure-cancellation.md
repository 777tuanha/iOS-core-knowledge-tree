# Backpressure & Cancellation

## 1. Overview

**Backpressure** is the mechanism by which a Combine `Subscriber` controls the rate at which a `Publisher` produces values — preventing fast publishers from overwhelming slow subscribers. **Cancellation** is the mechanism by which a subscription is terminated before its publisher completes. The `AnyCancellable` token is the primary handle for managing subscription lifetimes in iOS apps. Getting memory management right in Combine — storing tokens correctly, using `[weak self]` in closures, and cancelling appropriately — is critical for avoiding leaks and zombie subscriptions.

## 2. Simple Explanation

Imagine you've subscribed to a newspaper delivery. Backpressure is telling the delivery company "I only want one paper a day" — they respect your request and don't dump 50 papers on your doorstep. `AnyCancellable` is your cancellation notice — when you move house (your object is deallocated), you automatically cancel the subscription. If you throw away the cancellation notice before moving, the papers keep coming even though nobody is home (zombie subscription).

## 3. Deep iOS Knowledge

### Subscribers.Demand

`Subscribers.Demand` is the type used to signal how many more values a subscriber wants:

| Value | Meaning |
|-------|---------|
| `.unlimited` | Publisher can send as many values as it wants |
| `.max(n)` | Publisher can send at most n more values |
| `.none` | Publisher should send nothing for now |

Demand is **additive** — each `receive(_ input:)` return value adds to the existing demand. A subscriber that initially requests `.max(1)` and returns `.max(1)` on every `receive` effectively receives an unlimited stream.

### How Backpressure Flows

1. Subscriber calls `subscription.request(.max(1))` — requests one value.
2. Publisher emits one value; calls `subscriber.receive(value)`.
3. `receive` returns `.max(1)` — subscriber wants one more.
4. Publisher emits the next value. Repeat.

If `receive` returns `.none`, the publisher must stop until a new `request` arrives. Most built-in publishers buffer values when demand is temporarily zero; fast publishers that cannot buffer may drop values.

### .unlimited demand in practice

`sink` always requests `.unlimited` demand. This is safe for event-driven publishers (UI events, notifications) because events arrive at human speed. For high-frequency publishers (sensor data, game loops), `.unlimited` can cause issues — use `throttle`, `debounce`, or `buffer` operators to manage throughput.

### AnyCancellable

`AnyCancellable` is a type-erased `Cancellable` that calls `cancel()` when it is deallocated. It is the return value of `sink` and `assign`. There are three correct storage patterns:

```swift
// 1. Store in a Set for automatic lifetime management
var cancellables = Set<AnyCancellable>()
publisher.sink { ... }.store(in: &cancellables)

// 2. Store as a property for individual control
var subscription: AnyCancellable?
subscription = publisher.sink { ... }

// 3. Store in a collection if ordering matters
var cancellablesList = [AnyCancellable]()
cancellablesList.append(publisher.sink { ... })
```

When the `Set<AnyCancellable>` (or the property) is deallocated, all contained tokens cancel their subscriptions.

### Manual Cancellation

```swift
var token: AnyCancellable?
token = publisher.sink { value in
    if condition(value) {
        self.token = nil   // cancel by releasing the token
    }
}
```

Or explicitly: `token?.cancel()`. After cancellation, the subscriber receives no further values or completion events.

### Retain Cycles in Combine

The most common memory issue in Combine is a retain cycle between an object and its Combine subscription closure:

```
ViewController  ─strong→  Set<AnyCancellable>
                                │
                              sink closure
                                │
                          strong capture of VC
```

The `VC → AnyCancellable → closure → VC` cycle prevents the VC from deallocating. Fix: use `[weak self]` in the closure.

```swift
// Retain cycle — don't do this
publisher.sink { [self] value in   // or just capturing self
    self.updateUI(value)
}.store(in: &cancellables)

// Correct — use [weak self]
publisher.sink { [weak self] value in
    self?.updateUI(value)
}.store(in: &cancellables)
```

Exception: `assign(to:on:)` creates a retain cycle because it holds a strong reference to the target object. Use `assign(to: &$publishedProperty)` (iOS 14+) or `sink { [weak self] in self?.property = $0 }` instead.

### Cancelling Subscriptions on Lifecycle Events

In UIKit, cancel subscriptions when a VC disappears:
```swift
override func viewWillDisappear(_ animated: Bool) {
    super.viewWillDisappear(animated)
    cancellables.removeAll()   // cancel all subscriptions
}
```

In SwiftUI, subscriptions in `@StateObject` viewmodels are automatically cancelled when the view leaves the tree (because the ViewModel is deallocated). For `task(_:)`, SwiftUI manages cancellation automatically.

### buffer Operator

`buffer(size:prefetch:whenFull:)` adds a bounded queue between a fast publisher and a slow subscriber:

```swift
fastPublisher
    .buffer(size: 100, prefetch: .byRequest, whenFull: .dropOldest)
    .sink { slowConsume($0) }
```

When the buffer is full, `whenFull` determines strategy: `.dropOldest`, `.dropNewest`, or `.customError`.

## 4. Practical Usage

```swift
import Combine
import Foundation

// ── Correct AnyCancellable storage ────────────────────────────
class DataViewController {
    private var cancellables = Set<AnyCancellable>()   // all subscriptions live here

    func bind(to viewModel: DataViewModel) {
        viewModel.$items
            .receive(on: DispatchQueue.main)
            .sink { [weak self] items in                // [weak self] avoids retain cycle
                self?.updateTable(items: items)
            }
            .store(in: &cancellables)                   // token stored — subscription lives

        viewModel.$error
            .compactMap { $0 }                          // filter nil errors
            .sink { [weak self] error in
                self?.showAlert(error: error)
            }
            .store(in: &cancellables)
    }

    private func updateTable(items: [String]) {}
    private func showAlert(error: Error) {}
}

class DataViewModel: ObservableObject {
    @Published var items: [String] = []
    @Published var error: Error?
}

// ── Individual cancellation ────────────────────────────────────
class PollingService {
    private var pollCancellable: AnyCancellable?

    func startPolling() {
        pollCancellable = Timer
            .publish(every: 5.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.poll()
            }
    }

    func stopPolling() {
        pollCancellable = nil    // setting to nil cancels and releases
    }

    private func poll() { print("Polling...") }
}

// ── Self-cancelling subscription ─────────────────────────────
class OneTimeLoader {
    private var cancellable: AnyCancellable?

    func loadOnce(from publisher: AnyPublisher<String, Never>) {
        cancellable = publisher
            .first()                        // take only the first value, then complete
            .sink { [weak self] value in
                print("Loaded: \(value)")
                self?.cancellable = nil     // release token — also cancels
            }
    }
}

// ── Avoiding the assign(to:on:) retain cycle ──────────────────
class ProfileViewModel: ObservableObject {
    @Published var displayName = ""
    private var cancellables = Set<AnyCancellable>()

    init() {
        let namePublisher = Just("Alice")

        // WRONG — retain cycle: assign(to:on:) holds strong reference to self
        // namePublisher.assign(to: \.displayName, on: self).store(in: &cancellables)

        // CORRECT option 1: assign(to:) on @Published (iOS 14+) — no cycle
        namePublisher.assign(to: &$displayName)

        // CORRECT option 2: sink with [weak self]
        namePublisher
            .sink { [weak self] name in self?.displayName = name }
            .store(in: &cancellables)
    }
}

// ── Custom Subscriber demonstrating demand control ─────────────
class BoundedSubscriber: Subscriber {
    typealias Input = Int
    typealias Failure = Never

    private var subscription: Subscription?
    private var received = 0
    private let limit = 3

    func receive(subscription: Subscription) {
        self.subscription = subscription
        subscription.request(.max(1))   // request one at a time — backpressure
    }

    func receive(_ input: Int) -> Subscribers.Demand {
        received += 1
        print("Received: \(input)")
        if received >= limit {
            subscription?.cancel()
            return .none               // no more values needed
        }
        return .max(1)                 // request exactly one more
    }

    func receive(completion: Subscribers.Completion<Never>) {
        print("Completed")
    }
}

let subscriber = BoundedSubscriber()
(1...100).publisher.subscribe(subscriber)
// Only prints: Received: 1, Received: 2, Received: 3 — then stops

// ── buffer for rate mismatch ─────────────────────────────────
let fastTimer = Timer.publish(every: 0.01, on: .main, in: .common).autoconnect()

fastTimer
    .buffer(size: 50, prefetch: .byRequest, whenFull: .dropOldest)
    .throttle(for: .seconds(1), scheduler: DispatchQueue.main, latest: true)
    .sink { date in print("Processed tick at \(date)") }
    .store(in: &cancellables)
```

## 5. Interview Questions & Answers

### Basic

**Q: What is `AnyCancellable` and what happens if you don't store it?**

A: `AnyCancellable` is a token returned by `sink` and `assign` that represents an active subscription. When it is deallocated, it automatically calls `cancel()` on the subscription, stopping value delivery. If you don't store the token — for example, discarding it with `_ = publisher.sink { ... }` or letting it fall out of scope — it is deallocated immediately and the subscription is cancelled before any values can arrive. The idiomatic solution is `.store(in: &cancellables)` where `cancellables` is a `Set<AnyCancellable>` property on the owning object.

**Q: What is Combine backpressure and how does `sink` handle it?**

A: Backpressure is the mechanism by which a subscriber signals how many values it wants from a publisher. The subscriber requests values via `Subscribers.Demand`. `sink` always requests `.unlimited` demand — it signals to the publisher that it will accept as many values as the publisher can produce. This is appropriate for event-driven publishers that produce values at a human-interaction rate. For fast producers, manage throughput with `debounce`, `throttle`, or `buffer` operators rather than with a custom subscriber demand.

### Hard

**Q: How does `assign(to:on:)` create a retain cycle and how do you fix it?**

A: `assign(to:on:)` stores a strong reference to the `on` object internally. If the `on` object also holds the `AnyCancellable` (e.g., via `store(in: &cancellables)` on the same object), there is a cycle: object → cancellable → assign → object. Even without explicit `store`, if the object's lifetime outlasts the subscription, `assign` keeps it alive via the strong reference. Fix: Use `assign(to: &$property)` (iOS 14+) — this form does not hold a strong reference; it binds to the `@Published` property's inout pointer and the subscription's lifetime is managed by the property wrapper, breaking the cycle. Alternatively, use `sink { [weak self] in self?.property = $0 }`.

**Q: Explain the difference between cancelling a subscription and the publisher completing.**

A: **Completion** is the publisher's decision to stop — it calls `subscriber.receive(completion: .finished)` or `receive(completion: .failure(_:))`. The subscriber is informed and can react (e.g., show an error). **Cancellation** is the subscriber's decision to stop receiving — `AnyCancellable.cancel()` terminates the subscription, and no completion event is delivered to the subscriber. After cancellation, the publisher's underlying work may or may not be stopped depending on the publisher (e.g., `URLSession.dataTaskPublisher` cancels its network task; a `Timer` publisher connected via `autoconnect` stops when all subscribers cancel). For cleanup purposes, treat cancellation as "I'm done here" — don't expect completion events after cancelling.

### Expert

**Q: Design a Combine-based rate limiter that processes at most 5 events per second from an unbounded source.**

A: Combine's `throttle(for:scheduler:latest:)` limits to one value per interval. For rate-limiting to N events per interval (not just 1), the approach is: (1) Use `collect(.byTimeOrCount(scheduler, timeGroupingStrategy: ..., count: 5))` to batch up to 5 events per second into an array. (2) `flatMap` each batch into individual publisher elements with a micro-delay between them. Or, for strict N-per-second, use a custom `Scheduler` or pair `buffer` with a `throttle`-based dispatcher. Another approach: `scan` to count events per time window, combined with `filter` to discard over-rate events. For production use, the simplest correct solution is `throttle` (one per interval) + `buffer` to queue excess events — this guarantees none are lost while still respecting rate limits.

## 6. Common Issues & Solutions

**Issue: Subscription fires values but then abruptly stops.**

Solution: The `AnyCancellable` was deallocated. Common cause: returned inside a function without being stored, or added to a temporary local `Set`. Ensure it's stored in an instance-level property or `Set<AnyCancellable>`.

**Issue: ViewController is not deallocating — memory leak.**

Solution: A `sink` closure captures `self` strongly, creating a retain cycle via `VC → Set<AnyCancellable> → closure → VC`. Add `[weak self]` to every `sink` and `handleEvents` closure that references `self`.

**Issue: `assign(to:on:)` leaking the target object.**

Solution: Migrate to `assign(to: &$publishedProperty)` (requires iOS 14+) or use `sink { [weak self] value in self?.property = value }`.

**Issue: Fast publisher causes UI jank.**

Solution: Add `throttle` or `debounce` before the `receive(on: .main)` step. These operators reduce the frequency of main-thread updates, keeping the run loop free for rendering.

## 7. Related Topics

- [Publishers & Subscribers](publishers-subscribers.md) — Subscription and Demand are defined here
- [Operators](operators.md) — throttle, debounce, and buffer manage effective backpressure
- [Subjects](subjects.md) — Subjects are cancelled just like other publishers
- [Retain Cycles](../02-memory-management/retain-cycles.md) — [weak self] patterns in sink closures
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — capture list mechanics
