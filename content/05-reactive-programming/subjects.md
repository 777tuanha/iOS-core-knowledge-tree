# Subjects

## 1. Overview

A `Subject` is a special Combine `Publisher` that also exposes an imperative `send(_:)` method, allowing code outside the reactive pipeline to push values into it. Subjects are the primary bridge between the traditional iOS imperative world (delegates, callbacks, target-action) and the Combine reactive world. There are two concrete `Subject` types: `PassthroughSubject` (stateless — only forwards values to current subscribers) and `CurrentValueSubject` (stateful — holds the latest value and replays it to new subscribers).

## 2. Simple Explanation

Imagine a radio station. A regular Combine publisher is a pre-recorded broadcast — you tune in and hear whatever was recorded. A `Subject` is a live broadcast: the DJ (your imperative code) can push any sound into the microphone at any time, and all current listeners (subscribers) hear it in real time. `PassthroughSubject` is pure live radio — if you tune in mid-show, you missed what was said before. `CurrentValueSubject` is like a digital radio that also shows the currently playing track — even if you tune in late, you see the current state immediately.

## 3. Deep iOS Knowledge

### PassthroughSubject

```swift
let subject = PassthroughSubject<String, Never>()
```

- **Stateless**: No stored value. Subscribers receive only values emitted after they subscribe.
- **Use case**: Events with no meaningful "current state" — button taps, network responses, notifications.
- Sends completion when `send(completion: .finished)` is called, after which further `send` calls are ignored.

### CurrentValueSubject

```swift
let subject = CurrentValueSubject<String, Never>("")
```

- **Stateful**: Holds the current value in `.value`. New subscribers immediately receive this value upon subscription.
- Mutable via `.value` property or `.send(_:)`.
- **Use case**: State that always has a current value — authentication status, user settings, selection state.

### PassthroughSubject vs CurrentValueSubject

| | PassthroughSubject | CurrentValueSubject |
|--|---|---|
| Stores current value? | No | Yes |
| New subscriber gets? | Nothing (only future values) | Current value immediately |
| Mutable via | `.send(_:)` only | `.send(_:)` or `.value = x` |
| Analogy | Live event | State variable |

### @Published vs CurrentValueSubject

`@Published var x: T` is essentially a `CurrentValueSubject<T, Never>` wrapped in a property wrapper. The main differences:
- `@Published` can only be used inside a class (accessed via `$x`).
- `CurrentValueSubject` can be used anywhere, including as a standalone or injected object.
- `@Published` does not expose a `send(completion:)` method — it never completes.
- `CurrentValueSubject` can complete or fail, making it more flexible for representing finite streams.

### Thread Safety

`Subject` is **not** thread-safe by default. Calling `send(_:)` from multiple threads concurrently without synchronisation is a data race. If multiple threads need to send values to the same subject, protect access with a serial queue or an actor:

```swift
actor SafeSubject<T, E: Error> {
    private let subject: PassthroughSubject<T, E>
    init() { subject = PassthroughSubject() }
    func send(_ value: T) { subject.send(value) }
    var publisher: AnyPublisher<T, E> { subject.eraseToAnyPublisher() }
}
```

### Erasing to AnyPublisher

When exposing a subject as part of a public API, erase it to `AnyPublisher` to prevent callers from calling `send`:

```swift
class ViewModel {
    private let _events = PassthroughSubject<Event, Never>()
    var events: AnyPublisher<Event, Never> { _events.eraseToAnyPublisher() }

    func triggerEvent(_ event: Event) {
        _events.send(event)   // only ViewModel can push; callers can only subscribe
    }
}
```

### Bridging Delegates and Callbacks

Subjects are ideal for wrapping legacy APIs:

```swift
class LocationPublisher: NSObject, CLLocationManagerDelegate {
    private let locationSubject = PassthroughSubject<CLLocation, Never>()
    var locationPublisher: AnyPublisher<CLLocation, Never> {
        locationSubject.eraseToAnyPublisher()
    }

    func locationManager(_ manager: CLLocationManager,
                         didUpdateLocations locations: [CLLocation]) {
        if let location = locations.last {
            locationSubject.send(location)   // push delegate callback into pipeline
        }
    }
}
```

## 4. Practical Usage

```swift
import Combine
import Foundation

var cancellables = Set<AnyCancellable>()

// ── PassthroughSubject — stateless event bus ───────────────────
let tapSubject = PassthroughSubject<Void, Never>()

tapSubject
    .sink { print("Button tapped") }
    .store(in: &cancellables)

tapSubject.send()   // prints "Button tapped"
tapSubject.send()   // prints "Button tapped"

// No stored value — subscriber who joined after the first send misses it
let lateSub = tapSubject.sink { print("Late subscriber received tap") }
// lateSub will only receive FUTURE taps, not past ones

// ── CurrentValueSubject — stateful stream ────────────────────
let authSubject = CurrentValueSubject<Bool, Never>(false)

// Subscriber immediately gets current value (false)
authSubject
    .sink { isLoggedIn in
        print("Auth status: \(isLoggedIn ? "logged in" : "logged out")")
    }
    .store(in: &cancellables)
// prints "Auth status: logged out" immediately

authSubject.send(true)   // prints "Auth status: logged in"

// Read current value synchronously
print("Currently logged in: \(authSubject.value)")   // true

// Mutate directly
authSubject.value = false   // triggers subscribers

// ── Exposing read-only publisher from private subject ─────────
class EventBus {
    private let _events = PassthroughSubject<String, Never>()

    // Callers get AnyPublisher — cannot call send() from outside
    var events: AnyPublisher<String, Never> {
        _events.eraseToAnyPublisher()
    }

    func publish(_ event: String) {
        _events.send(event)
    }

    func shutdown() {
        _events.send(completion: .finished)   // signal no more events
    }
}

let bus = EventBus()
bus.events
    .sink { print("Event: \($0)") }
    .store(in: &cancellables)

bus.publish("UserLoggedIn")
bus.publish("ProfileUpdated")
bus.shutdown()
// Further publish calls are ignored after completion

// ── Bridging a delegate to Combine ────────────────────────────
import CoreLocation

class LocationService: NSObject, CLLocationManagerDelegate {
    private let locationSubject = PassthroughSubject<CLLocation, Error>()
    private let manager = CLLocationManager()

    var locations: AnyPublisher<CLLocation, Error> {
        locationSubject.eraseToAnyPublisher()
    }

    override init() {
        super.init()
        manager.delegate = self
        manager.startUpdatingLocation()
    }

    func locationManager(_ manager: CLLocationManager,
                         didUpdateLocations locations: [CLLocation]) {
        locations.forEach { locationSubject.send($0) }   // push into pipeline
    }

    func locationManager(_ manager: CLLocationManager,
                         didFailWithError error: Error) {
        locationSubject.send(completion: .failure(error))   // propagate error
    }
}

// ── CurrentValueSubject as observable state ───────────────────
class AppState {
    // Subjects as state — alternative to @Published for non-class contexts
    let themeSubject = CurrentValueSubject<ColorTheme, Never>(.light)
    let fontSizeSubject = CurrentValueSubject<CGFloat, Never>(16.0)

    // Computed publisher: combine theme and font size
    var displayConfig: AnyPublisher<(ColorTheme, CGFloat), Never> {
        Publishers.CombineLatest(themeSubject, fontSizeSubject)
            .eraseToAnyPublisher()
    }
}

enum ColorTheme { case light, dark }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `PassthroughSubject` and `CurrentValueSubject`?**

A: `PassthroughSubject` is stateless — it has no stored value. Subscribers only receive values emitted after they subscribe. If no one is subscribed when `send` is called, the value is lost. `CurrentValueSubject` stores the most recently emitted value. New subscribers immediately receive this current value on subscription, making it appropriate for state (something that always has a current value). You can also read `CurrentValueSubject.value` synchronously, which is not possible with `PassthroughSubject`. In practice: use `PassthroughSubject` for events (button taps, notifications), use `CurrentValueSubject` for state (authentication status, selected item).

**Q: How do you prevent callers from sending values into a Subject you expose from a class?**

A: Erase the Subject to `AnyPublisher` before exposing it: `var events: AnyPublisher<Event, Never> { _events.eraseToAnyPublisher() }`. The internal `PassthroughSubject` (or `CurrentValueSubject`) is stored as a private property. Callers receive only the `AnyPublisher` interface, which has no `send` method. The class itself controls when values enter the pipeline via its private `send` calls.

### Hard

**Q: How does `@Published` relate to `CurrentValueSubject`?**

A: `@Published` is implemented on top of Combine's publisher machinery and behaves similarly to `CurrentValueSubject<T, Never>`. Both hold a current value and emit it to new subscribers. Key differences: `@Published` is a property wrapper — it requires being declared inside a class and is accessed via the `$` prefix. It cannot emit a completion event and has no `send(completion:)` method. `CurrentValueSubject` is a standalone object that can be stored anywhere, can emit errors, and can complete. For `ObservableObject` view models, `@Published` is idiomatic. For injectable state containers or non-class contexts, `CurrentValueSubject` is more flexible.

**Q: A Subject receives `send` calls from multiple threads. What happens?**

A: This is a data race — `Subject` is not thread-safe. Concurrent `send` calls can corrupt internal state. The fix: serialise access. Options: (1) Use a serial `DispatchQueue` and dispatch `send` calls to it. (2) Use an `actor` to wrap the subject (as shown in the example). (3) Use `@Published` inside a `@MainActor` class, ensuring all sends happen on the main thread. (4) Use the `receive(on:)` operator downstream to coalesce values onto a single thread — this doesn't protect the send, but if all senders happen to be on the same thread, it's safe.

### Expert

**Q: Design a type-safe event bus using Subjects that supports multiple event types without a common base type.**

A: Use a generic `EventBus<Event>` where `Event` is constrained to `Hashable`. Internally, maintain a dictionary from `ObjectIdentifier` (or a typed key) to `PassthroughSubject`. Each event type gets its own subject. Publishers expose typed `AnyPublisher<EventType, Never>` and the send method accepts the specific type: `func send<E: AppEvent>(_ event: E)`. The subscriber side: `bus.publisher(for: LoginEvent.self).sink { ... }`. This gives compile-time type safety — subscribers only receive the exact event type they register for — without boxing everything into an `Any`-typed envelope. The tradeoff is that the bus must store subjects in a `[String: Any]` (or use `AnyHashable` keys) to support heterogeneous event types, so some runtime casting is required internally, isolated to the bus implementation.

## 6. Common Issues & Solutions

**Issue: `PassthroughSubject` values are lost — subscriber receives nothing.**

Solution: The subscriber was added after `send` was called, or the `AnyCancellable` token was not stored. For state that must be received by late subscribers, switch to `CurrentValueSubject`.

**Issue: Calling `subject.send()` after `send(completion:)` has no effect.**

Solution: This is correct behaviour — once a Subject has completed or failed, it ignores all further `send` calls. If you need to restart, create a new Subject instance.

**Issue: Memory leak — Subject holds strong reference to subscriber via closure.**

Solution: Use `[weak self]` in the `sink` closure. The Subject retains its subscribers for the lifetime of the subscription. If the subscriber's closure captures `self` strongly, and `self` holds the `AnyCancellable`, there is a retain cycle: VC → cancellable → Subject → closure → VC. Use `[weak self]` or `assign(to: &$property)` (which breaks the cycle).

**Issue: Multiple subscribers receive values in a non-deterministic order.**

Solution: Subjects deliver to subscribers in the order they subscribed, on the thread that called `send`. If order matters, maintain a single subscriber or use `share()` with a multicast subject to control dispatch.

## 7. Related Topics

- [Publishers & Subscribers](publishers-subscribers.md) — Subject conforms to Publisher
- [Operators](operators.md) — operators applied to subject outputs
- [Backpressure & Cancellation](backpressure-cancellation.md) — AnyCancellable lifetime for subject subscriptions
- [Combine + UIKit & SwiftUI](combine-swiftui-uikit.md) — Subject as an event source for UI binding
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — @Published as the SwiftUI equivalent
