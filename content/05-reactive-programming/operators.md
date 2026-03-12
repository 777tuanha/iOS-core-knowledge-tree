# Operators

## 1. Overview

Operators are methods defined on `Publisher` that return new publishers, transforming the stream of values flowing through a Combine pipeline. They are the core vocabulary of reactive programming: they map, filter, combine, time-gate, and error-handle values declaratively. Because each operator returns a new `Publisher`, operators chain naturally — creating a readable, composable data pipeline from source to subscriber.

## 2. Simple Explanation

Think of a Combine pipeline as a water treatment plant. Operators are the individual processing stations the water passes through: a filter station (removes impurities), a purification station (transforms water quality), a blending station (mixes two sources), a flow regulator (controls the rate). Each station receives water from the previous one and passes treated water to the next. The final output — clean, processed water — is what the subscriber receives.

## 3. Deep iOS Knowledge

### Operator Categories

Combine's operators fall into five categories:

| Category | Examples |
|----------|---------|
| Transforming | `map`, `flatMap`, `compactMap`, `scan`, `reduce`, `replaceNil` |
| Filtering | `filter`, `removeDuplicates`, `first`, `last`, `drop`, `prefix` |
| Combining | `merge`, `zip`, `combineLatest`, `switchToLatest` |
| Error Handling | `catch`, `retry`, `replaceError`, `assertNoFailure` |
| Timing | `debounce`, `throttle`, `delay`, `timeout`, `measureInterval` |
| Threading | `receive(on:)`, `subscribe(on:)` |
| Lifecycle | `handleEvents`, `print`, `share`, `multicast` |

### Transforming Operators

**map**: Apply a transform function to each value.
```swift
[1, 2, 3].publisher.map { $0 * 2 }   // emits 2, 4, 6
```

**flatMap**: Transform each value into a new publisher and flatten the results. The inner publisher's output becomes the outer pipeline's output. Used for chaining async operations:
```swift
userIDPublisher
    .flatMap { id in fetchUser(id: id) }   // each id → fetch → User
```
`flatMap(maxPublishers:)` limits concurrent inner subscriptions — important for controlling concurrency.

**compactMap**: Like `map`, but drops `nil` values (analogous to `compactMap` on sequences).
```swift
["1", "abc", "3"].publisher
    .compactMap { Int($0) }   // emits 1, 3 — "abc" dropped
```

**scan**: Accumulate values like `reduce`, but emits intermediate results:
```swift
[1, 2, 3, 4].publisher
    .scan(0) { acc, value in acc + value }   // emits 1, 3, 6, 10
```

### Filtering Operators

**filter**: Pass only values matching a predicate.

**removeDuplicates**: Drop consecutive equal values — essential for performance, prevents unnecessary UI updates when the same value is published twice:
```swift
$searchText
    .removeDuplicates()   // don't re-trigger search if text hasn't changed
```

**first(where:) / last(where:)**: Take only the first/last matching value, then complete.

**dropFirst(_:) / prefix(_:)**: Skip or take a fixed number of values.

### Combining Operators

**merge**: Combines multiple publishers of the same type. Emits values from any publisher as they arrive. Completes when **all** source publishers complete.
```swift
merge(publisher1, publisher2)   // values from either arrive in temporal order
```

**zip**: Pairs values from two publishers in order — emits only when both have emitted a new value. Used to combine two parallel async results. Completes when either publisher completes.
```swift
zip(userPublisher, postsPublisher)   // emits (User, [Post]) pairs
```

**combineLatest**: Emits a tuple of the **latest value** from each publisher whenever any one emits. Requires each publisher to have emitted at least one value before the first combined emission. Perfect for form validation:
```swift
combineLatest($email, $password)
    .map { email, password in isValid(email) && password.count >= 8 }
    .assign(to: \.isLoginEnabled, on: viewModel)
```

**switchToLatest**: When a publisher-of-publishers emits a new inner publisher, subscribes to the new one and cancels the previous. Used to implement "cancel previous search, start new one":
```swift
$searchText
    .map { query in searchPublisher(query: query) }  // returns Publisher each time
    .switchToLatest()   // only subscribes to most recent search publisher
```

### Error Handling Operators

**catch**: Replace a failed publisher with a fallback publisher:
```swift
dataPublisher
    .catch { _ in Just(cachedData) }   // on failure, return cached data
```

**retry(_:)**: Re-subscribe to the upstream publisher up to N times on failure:
```swift
networkPublisher
    .retry(3)   // try up to 4 times total (1 + 3 retries)
```

**replaceError(with:)**: Absorb errors and emit a default value:
```swift
networkPublisher
    .replaceError(with: [])   // on error, emit empty array
```

### Timing Operators

**debounce**: Waits for the publisher to go quiet for a specified interval before emitting the last value. Classic use case: search-as-you-type.
```swift
$searchText
    .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
```

**throttle**: Emits at most one value per interval — takes either the first or last value in each window.
```swift
buttonTapPublisher
    .throttle(for: .seconds(1), scheduler: RunLoop.main, latest: false)
```

**delay**: Shifts every value forward in time by a fixed interval.

**timeout**: Completes with an error if no value arrives within an interval.

### Threading Operators

**subscribe(on:)**: Specifies the scheduler (thread/queue) where the subscription occurs — i.e., where upstream work runs. Applied once per pipeline, typically to move the source's work off the main thread.

**receive(on:)**: Specifies the scheduler where downstream values are delivered. Applied just before a subscriber that must run on a specific thread (usually `.main` before UI updates).

```swift
URLSession.shared.dataTaskPublisher(for: url)
    .subscribe(on: DispatchQueue.global())    // subscribe/upstream on background
    .receive(on: DispatchQueue.main)          // deliver values on main thread
    .sink { ... }
```

### share and multicast

By default, each `sink`/`assign` creates an independent subscription — two subscribers trigger two separate upstream operations (two network requests). `share()` multicasts an upstream publisher to multiple subscribers:

```swift
let shared = networkPublisher.share()
shared.sink { handleResult($0) }.store(in: &cancellables)
shared.sink { logResult($0) }.store(in: &cancellables)
// Only ONE network request is made
```

`multicast(subject:)` gives more control — you call `connect()` manually to start the upstream work.

## 4. Practical Usage

```swift
import Combine
import Foundation

var cancellables = Set<AnyCancellable>()

// ── Search pipeline with debounce + switchToLatest ─────────────
class SearchViewModel: ObservableObject {
    @Published var query = ""
    @Published var results: [String] = []

    init() {
        $query
            .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)  // wait for typing to stop
            .removeDuplicates()                   // skip if query hasn't changed
            .filter { !$0.isEmpty }               // don't search empty strings
            .map { query in                       // map to a publisher of results
                self.performSearch(query: query)
            }
            .switchToLatest()                     // cancel previous search, use newest
            .receive(on: DispatchQueue.main)       // deliver on main thread
            .assign(to: &$results)                // assign to @Published
    }

    private func performSearch(query: String) -> AnyPublisher<[String], Never> {
        // Simulated async search returning results after a delay
        Just(["Result for: \(query)"])
            .delay(for: .milliseconds(100), scheduler: DispatchQueue.global())
            .eraseToAnyPublisher()
    }
}

// ── Form validation with combineLatest ────────────────────────
class LoginFormViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isSubmitEnabled = false

    private var cancellables = Set<AnyCancellable>()

    init() {
        // Combine latest values of both fields — fires whenever either changes
        Publishers.CombineLatest($email, $password)
            .map { email, password in
                let emailValid = email.contains("@") && email.contains(".")
                let passwordValid = password.count >= 8
                return emailValid && passwordValid
            }
            .assign(to: &$isSubmitEnabled)
    }
}

// ── Zip two parallel async requests ──────────────────────────
func loadDashboard() -> AnyPublisher<(User, [Post]), Error> {
    let userPublisher = fetchUser()           // publisher<User, Error>
    let postsPublisher = fetchPosts()         // publisher<[Post], Error>

    return Publishers.Zip(userPublisher, postsPublisher)
        .eraseToAnyPublisher()                // emit (User, [Post]) when both complete
}

// ── Error handling with catch + retry ─────────────────────────
func resilientFetch(url: URL) -> AnyPublisher<Data, Never> {
    URLSession.shared.dataTaskPublisher(for: url)
        .retry(2)                             // retry up to 2 additional times on failure
        .map(\.data)
        .catch { _ in Just(Data()) }          // on persistent failure, return empty Data
        .eraseToAnyPublisher()
}

// ── scan for running total ────────────────────────────────────
[10, 20, 30, 40].publisher
    .scan(0, +)                               // 10, 30, 60, 100 — running sum
    .sink { print("Running total: \($0)") }
    .store(in: &cancellables)

// ── flatMap with maxPublishers to limit concurrency ───────────
let urls = [URL(string: "https://a.com")!, URL(string: "https://b.com")!]

urls.publisher
    .flatMap(maxPublishers: .max(2)) { url in         // at most 2 concurrent requests
        URLSession.shared.dataTaskPublisher(for: url)
            .map(\.data)
            .replaceError(with: Data())               // absorb individual errors
    }
    .sink { data in print("Got \(data.count) bytes") }
    .store(in: &cancellables)

// ── receive(on:) for UI updates ───────────────────────────────
func fetchAndDisplay(url: URL, label: UILabel) {
    URLSession.shared.dataTaskPublisher(for: url)
        .map(\.data)
        .compactMap { String(data: $0, encoding: .utf8) }
        .receive(on: DispatchQueue.main)              // ensure UI update on main thread
        .sink(
            receiveCompletion: { _ in },
            receiveValue: { text in label.text = text }
        )
        .store(in: &cancellables)
}

// ── share to avoid duplicate network requests ─────────────────
let sharedPublisher = URLSession.shared
    .dataTaskPublisher(for: URL(string: "https://api.example.com/data")!)
    .share()                                          // one request, multiple subscribers

sharedPublisher.sink { print("Subscriber A: \($0)") }.store(in: &cancellables)
sharedPublisher.sink { print("Subscriber B: \($0)") }.store(in: &cancellables)
// Only ONE network request fires

// Stubs
struct User {}
struct Post {}
class UILabel { var text: String? = nil }
func fetchUser() -> AnyPublisher<User, Error> { Just(User()).setFailureType(to: Error.self).eraseToAnyPublisher() }
func fetchPosts() -> AnyPublisher<[Post], Error> { Just([Post()]).setFailureType(to: Error.self).eraseToAnyPublisher() }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `map` and `flatMap` in Combine?**

A: `map` transforms each emitted value into a new value of a different type — the transformation is synchronous and returns a plain value. `flatMap` transforms each emitted value into a new **publisher**, then subscribes to that publisher and emits its values into the outer pipeline. `flatMap` is used when the transformation itself is asynchronous — e.g., turning a user ID into a network request that returns a `User`. The key difference: `map` wraps the transform result in the same publisher, `flatMap` unwraps (flattens) the inner publisher into the outer stream.

**Q: What does `removeDuplicates()` do and why is it important for UI binding?**

A: `removeDuplicates()` drops consecutive values that are equal to the previous value. Without it, every keystroke in a bound text field would trigger downstream work (network requests, database queries) even if the user typed and then immediately deleted a character, returning to the same string. By filtering out consecutive equal emissions, `removeDuplicates()` ensures downstream operators only fire when the value meaningfully changes, reducing unnecessary work and preventing flickering UI updates.

### Hard

**Q: What is the difference between `merge`, `zip`, and `combineLatest`?**

A: `merge(publisher1, publisher2)`: All publishers must have the same Output type. Values from any publisher are emitted immediately as they arrive, interleaved in time order. `zip(p1, p2)`: Publishers can have different Output types. Values are paired one-to-one — the first value from p1 pairs with the first from p2, the second with the second, etc. Emits only when both have produced a new value. `combineLatest(p1, p2)`: Each publisher can have a different Output. Emits the **latest** value from each publisher whenever **either** one emits — after both have emitted at least one value. Use `merge` when any source's events should flow through, `zip` when you need matched pairs (parallel tasks that should be combined), and `combineLatest` when you want a running combination of the most recent state from multiple sources (form validation, multi-filter UI).

**Q: What is `switchToLatest` and what problem does it solve?**

A: `switchToLatest` operates on a publisher-of-publishers (`Publisher where Output: Publisher`). When a new inner publisher is emitted, it unsubscribes from the previous inner publisher and subscribes to the new one. This solves the "superseded search" problem: if a user types quickly and each keystroke generates a new network request publisher, `switchToLatest` ensures only the most recent request's results arrive downstream — previous in-flight requests are cancelled. Without it, all responses would arrive and potentially overwrite results in wrong order (race condition).

### Expert

**Q: Explain the threading model of a Combine pipeline — what do `subscribe(on:)` and `receive(on:)` actually control?**

A: `subscribe(on:)` controls where the **upstream subscription work** begins — i.e., the thread on which the `receive(subscriber:)` call propagates up through the chain and where the publisher starts producing values. It should appear as early in the chain as possible. `receive(on:)` controls where **downstream values are delivered** — every call to `receive(_ input:)` and `receive(completion:)` on the downstream subscriber happens on the specified scheduler. In a typical network pipeline: `subscribe(on: DispatchQueue.global())` means the URL session task starts on a background queue; `receive(on: DispatchQueue.main)` means the final `sink` closure runs on the main thread. Note: `subscribe(on:)` has no effect on operators that themselves specify their scheduler (like `debounce(scheduler:)` or `Timer.publish(on:)`), which always deliver on their own scheduler.

## 6. Common Issues & Solutions

**Issue: `flatMap` triggers multiple concurrent network requests, overwhelming the server.**

Solution: Use `flatMap(maxPublishers: .max(n))` to limit concurrent inner subscriptions. For strictly serial execution (one at a time), use `maxPublishers: .max(1)`. Alternatively, use `switchToLatest` if only the most recent result matters.

**Issue: `combineLatest` doesn't emit until all publishers have emitted at least one value.**

Solution: This is expected behaviour. If you need an initial value before a publisher has emitted, prepend a default with `.prepend(initialValue)` or use `CurrentValueSubject` (which always holds a value) instead of a plain publisher.

**Issue: `debounce` fires on the wrong thread, causing a UIKit warning.**

Solution: Specify `scheduler: RunLoop.main` or `scheduler: DispatchQueue.main` in the `debounce` call. `debounce` delivers on the scheduler you provide — if you don't specify the main scheduler, values may arrive on a background thread.

**Issue: `retry` causes duplicate side effects (e.g., multiple POST requests).**

Solution: `retry` re-subscribes to the entire upstream chain — for a `dataTaskPublisher` that makes a POST, this creates a new POST for each retry. Use `retry` only for idempotent requests (GET). For non-idempotent requests, implement custom retry logic with `catch` + `Future`.

## 7. Related Topics

- [Publishers & Subscribers](publishers-subscribers.md) — the protocol layer operators are built on
- [Subjects](subjects.md) — imperative sources often used with operators
- [Combine Networking](combine-networking.md) — operators applied to network pipelines
- [Combine + UIKit & SwiftUI](combine-swiftui-uikit.md) — debounce/combineLatest in data binding
