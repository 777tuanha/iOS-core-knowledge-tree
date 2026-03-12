# Publishers & Subscribers

## 1. Overview

`Publisher` and `Subscriber` are the two fundamental protocols of Combine. A `Publisher` declares that it can emit a sequence of typed values (`Output`) and a typed error (`Failure`) over time, eventually completing or failing. A `Subscriber` registers interest in those values and receives them, plus a completion event. The connection between them — a `Subscription` — manages lifetime and backpressure. Understanding this three-party handshake is the foundation of all Combine usage.

## 2. Simple Explanation

Think of a Publisher as a newspaper printing press. You (the Subscriber) call the press to subscribe. The press sends you a subscription card (Subscription). You fill in how many papers you want (Demand). The press starts delivering papers (values). Eventually the press shuts down (completion) or catches fire (failure). You can cancel your subscription at any time with the cancellation token (AnyCancellable).

## 3. Deep iOS Knowledge

### The Publisher Protocol

```swift
protocol Publisher {
    associatedtype Output
    associatedtype Failure: Error
    func receive<S: Subscriber>(subscriber: S)
        where S.Input == Output, S.Failure == Failure
}
```

The only requirement is `receive(subscriber:)`. All operators are extensions on this protocol. The `Output` and `Failure` associated types define what the publisher emits.

`Failure == Never` means the publisher cannot fail — common for UI events and `@Published` properties.

### The Subscriber Protocol

```swift
protocol Subscriber: CustomCombineIdentifierConvertible {
    associatedtype Input
    associatedtype Failure: Error
    func receive(subscription: Subscription)   // called once on subscribe
    func receive(_ input: Input) -> Subscribers.Demand  // called for each value
    func receive(completion: Subscribers.Completion<Failure>)  // called once at end
}
```

The Subscriber's `Input` must match the Publisher's `Output`, and their `Failure` types must match.

### The Subscription Protocol and Backpressure

```swift
protocol Subscription: Cancellable {
    func request(_ demand: Subscribers.Demand)
}
```

After `receive(subscription:)` is called, the Subscriber **must** call `subscription.request(_:)` to signal how many values it wants. This is the backpressure mechanism — the Publisher sends at most as many values as demanded. `Subscribers.Demand` can be `.max(n)`, `.unlimited`, or `.none`.

### Subscription Lifecycle

```
Publisher.subscribe(subscriber)
    │
    ▼
Publisher calls subscriber.receive(subscription:)
    │
    ▼
Subscriber calls subscription.request(.unlimited)   ← demand signal
    │
    ▼
Publisher calls subscriber.receive(value)  ×N        ← for each emitted value
    │
    ▼
Publisher calls subscriber.receive(completion:)      ← .finished or .failure(Error)
    │
    ▼
subscription is cancelled / released
```

### Built-in Publishers

| Publisher | Emits | Fails |
|-----------|-------|-------|
| `Just(value)` | Single value, then finishes | Never |
| `Empty()` | Nothing, completes immediately | Never |
| `Fail(error)` | Nothing, fails immediately | Yes |
| `Future { promise in }` | Single async value | Yes |
| `Deferred { publisher }` | Evaluates publisher lazily at subscribe time | — |
| `[1,2,3].publisher` | Each element, then finishes | Never |
| `Timer.publish(every:on:in:)` | Current date at interval | Never |
| `NotificationCenter.publisher(for:)` | Notification on post | Never |
| `URLSession.dataTaskPublisher(for:)` | (Data, URLResponse) | URLError |
| `@Published var x` | Each new value of x | Never |

### AnyPublisher and Type Erasure

Concrete publisher types expose their full type (e.g., `Publishers.Map<URLSession.DataTaskPublisher, Data>`). Use `eraseToAnyPublisher()` to hide implementation details:

```swift
func fetchData(url: URL) -> AnyPublisher<Data, URLError> {
    URLSession.shared.dataTaskPublisher(for: url)
        .map(\.data)
        .eraseToAnyPublisher()          // hides the concrete pipeline type
}
```

### sink and assign

`sink` is the most common subscriber:

```swift
publisher
    .sink(
        receiveCompletion: { completion in
            switch completion {
            case .finished: print("Done")
            case .failure(let error): print("Error: \(error)")
            }
        },
        receiveValue: { value in
            print("Received: \(value)")
        }
    )
```

`assign(to:on:)` assigns values to a property via key path:

```swift
publisher
    .assign(to: \.title, on: viewController)
```

`assign(to:)` (iOS 14+) assigns to a `@Published` var without creating a retain cycle:

```swift
publisher
    .assign(to: &viewModel.$displayName)  // & binds the inout Binding
```

### Future

`Future` wraps a single async value in a Combine publisher:

```swift
func fetchUser(id: String) -> Future<User, Error> {
    Future { promise in
        UserService.fetch(id: id) { result in
            promise(result)             // call promise with .success or .failure
        }
    }
}
```

**Important**: `Future` executes its closure **immediately on creation** (not lazily). Wrap it in `Deferred` to defer execution until subscription.

### Deferred

```swift
func fetchUserDeferred(id: String) -> AnyPublisher<User, Error> {
    Deferred {
        Future { promise in
            UserService.fetch(id: id) { promise($0) }
        }
    }
    .eraseToAnyPublisher()
}
```

Now the network call starts only when a subscriber subscribes — not when the publisher is created.

## 4. Practical Usage

```swift
import Combine
import Foundation

var cancellables = Set<AnyCancellable>()

// ── Just — emit a single value ────────────────────────────────
Just(42)
    .sink { value in print("Got: \(value)") }   // prints "Got: 42" then completes
    .store(in: &cancellables)                    // store the token to keep subscription alive

// ── Array publisher — emit each element ──────────────────────
[1, 2, 3, 4, 5].publisher
    .map { $0 * $0 }                             // square each value
    .sink { print($0) }                          // prints 1, 4, 9, 16, 25
    .store(in: &cancellables)

// ── Future — wrap a callback-based API ────────────────────────
func fetchNumber() -> Future<Int, Never> {
    Future { promise in
        DispatchQueue.global().asyncAfter(deadline: .now() + 0.5) {
            promise(.success(42))                // resolve the future
        }
    }
}

fetchNumber()
    .sink { print("Future resolved: \($0)") }
    .store(in: &cancellables)

// ── Deferred Future — lazy execution ─────────────────────────
func lazyFetch() -> AnyPublisher<Int, Never> {
    Deferred {                                   // closure runs at subscribe time
        Future { promise in
            print("Starting work...")
            promise(.success(99))
        }
    }
    .eraseToAnyPublisher()
}

let publisher = lazyFetch()     // "Starting work..." NOT printed yet
publisher
    .sink { print("Received: \($0)") }  // NOW "Starting work..." prints
    .store(in: &cancellables)

// ── Timer publisher ───────────────────────────────────────────
let timerPublisher = Timer
    .publish(every: 1.0, on: .main, in: .common)
    .autoconnect()                               // connect automatically on subscription

let timerCancellable = timerPublisher
    .sink { date in print("Tick: \(date)") }

DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
    timerCancellable.cancel()                    // stop after 3 seconds
}

// ── NotificationCenter publisher ─────────────────────────────
NotificationCenter.default
    .publisher(for: UIApplication.didBecomeActiveNotification)  // Combine publisher for notifications
    .sink { _ in print("App became active") }
    .store(in: &cancellables)

// ── URLSession dataTaskPublisher ─────────────────────────────
let url = URL(string: "https://api.example.com/data")!

URLSession.shared
    .dataTaskPublisher(for: url)                 // Publisher<(Data, URLResponse), URLError>
    .map(\.data)                                 // extract Data
    .decode(type: [String: String].self, decoder: JSONDecoder())
    .receive(on: DispatchQueue.main)             // deliver result on main thread
    .sink(
        receiveCompletion: { completion in
            if case .failure(let error) = completion {
                print("Error: \(error)")
            }
        },
        receiveValue: { dict in print("Received: \(dict)") }
    )
    .store(in: &cancellables)

// ── AnyPublisher — type-erased return ────────────────────────
func search(query: String) -> AnyPublisher<[String], Never> {
    Just(["result1", "result2"])                 // placeholder
        .eraseToAnyPublisher()
}

// ── assign(to:) on @Published (iOS 14+) ──────────────────────
class ViewModel: ObservableObject {
    @Published var name: String = ""
    private var cancellables = Set<AnyCancellable>()

    init() {
        // Assign directly to @Published — no retain cycle, no stored AnyCancellable
        Just("Alice")
            .assign(to: &$name)                 // & passes inout; no need to store token
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a Publisher and a Subject in Combine?**

A: A Publisher is a type that produces values for subscribers to receive — subscribers observe it but cannot push values into it. A Subject is a special Publisher that also exposes an imperative `send(_:)` method, allowing you to inject values into the pipeline from outside. Subjects bridge traditional imperative code (callbacks, delegate methods) into the reactive Combine pipeline. `PassthroughSubject` and `CurrentValueSubject` are the two concrete Subject types.

**Q: What is `AnyCancellable` and why must you store it?**

A: `AnyCancellable` is a Combine subscription token. When it is deallocated, the subscription is cancelled and the publisher stops delivering values. If you don't store the token returned by `sink` or `assign`, it is immediately deallocated, cancelling the subscription before any values arrive. The idiomatic pattern is `store(in: &cancellables)` where `cancellables` is a `Set<AnyCancellable>` property on the owning object — the subscriptions live as long as the owner does.

### Hard

**Q: Explain the Publisher-Subscriber-Subscription three-party handshake.**

A: (1) You call `publisher.subscribe(subscriber)`. (2) The publisher calls `subscriber.receive(subscription:)`, passing a `Subscription` object. (3) The subscriber calls `subscription.request(.unlimited)` (or a specific demand count) — without this call, the publisher sends nothing. This is the backpressure signal. (4) For each emitted value, the publisher calls `subscriber.receive(_ input:)`, which returns a new `Subscribers.Demand` indicating how many more values are wanted (used for dynamic backpressure). (5) When the publisher completes or fails, it calls `subscriber.receive(completion:)`. The subscription is then released. This design makes the contract explicit: no values arrive until the subscriber requests them.

**Q: What is the difference between `Future` and `Deferred<Future>`?**

A: `Future` executes its closure — and starts the underlying async work — **immediately when created**, regardless of whether anyone has subscribed. This means creating a `Future` in a function that no one calls `sink` on will still start the work. `Deferred` wraps any publisher and delays its creation until a subscriber actually subscribes. `Deferred { Future { ... } }` is the correct pattern for lazy async operations: the work only starts when someone subscribes, matching the expected semantics of a function that returns a publisher.

### Expert

**Q: How does backpressure work in Combine and when is it relevant in iOS apps?**

A: Backpressure is the mechanism by which a Subscriber controls the rate at which a Publisher produces values. After receiving the `Subscription`, a Subscriber calls `subscription.request(_:)` with a `Subscribers.Demand` (`.max(1)`, `.max(n)`, or `.unlimited`). The Publisher must not send more values than demanded. For each value received, `receive(_ input:)` returns an additional Demand increment. In practice, most iOS Combine pipelines use `.unlimited` demand (via `sink`) — this is safe when the publisher is event-driven (UI events, notifications) because events naturally arrive at a human pace. Backpressure becomes important when a publisher can generate values much faster than a subscriber can process them — e.g., a high-frequency sensor publisher feeding into a slow database write. In those cases, operators like `throttle` and `debounce` implement effective backpressure at the operator level without needing custom Subscriber implementations.

## 6. Common Issues & Solutions

**Issue: Subscription fires and immediately cancels — no values received.**

Solution: The `AnyCancellable` token was not stored. Assign the result of `sink` / `assign` to a property or add it to a `Set<AnyCancellable>`.

**Issue: `Future` starts network work even though no one subscribed yet.**

Solution: Wrap the `Future` in `Deferred { }`. This defers closure execution until the first subscription.

**Issue: `assign(to:on:)` creates a retain cycle in a ViewModel.**

Solution: Use `assign(to: &$publishedProperty)` (iOS 14+) instead — it does not retain `self`. Alternatively, use `sink { [weak self] in self?.property = $0 }`.

**Issue: Publisher completes before subscriber receives all values.**

Solution: Check that the subscription token is stored. Also verify that no `first()` or `prefix(_:)` operators are limiting the output unexpectedly.

## 7. Related Topics

- [Operators](operators.md) — transform, filter, and combine publishers
- [Subjects](subjects.md) — imperatively push values into a pipeline
- [Backpressure & Cancellation](backpressure-cancellation.md) — AnyCancellable, demand, memory management
- [Combine Networking](combine-networking.md) — dataTaskPublisher in practice
- [async/await](../03-concurrency/async-await.md) — modern alternative for single async values
- [Retain Cycles](../02-memory-management/retain-cycles.md) — assign vs sink retain cycle patterns
