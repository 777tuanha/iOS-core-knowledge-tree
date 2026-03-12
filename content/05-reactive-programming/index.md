# Reactive Programming

## Overview

Reactive programming models computation as streams of values over time. In iOS, Apple's first-party reactive framework is **Combine** (introduced iOS 13 / Swift 5.1). Combine provides a declarative Swift API for processing values asynchronously: a `Publisher` emits values, `Operator`s transform them, and a `Subscriber` receives them. The framework handles threading, memory management (via `AnyCancellable`), backpressure, and error propagation consistently across the entire pipeline.

Combine bridges the gap between callback-based UIKit/Foundation APIs and the modern async/await model. It excels at **data binding** (connecting model changes to UI), **event transformation** (debounce, throttle, merge, zip), and **coordinating multiple async sources** into a single pipeline.

## Topics in This Section

- [Publishers & Subscribers](publishers-subscribers.md) — Publisher/Subscriber protocols, subscription lifecycle, built-in publishers (Just, Future, Deferred, Timer, NotificationCenter)
- [Operators](operators.md) — Transforming (map, flatMap, compactMap), filtering (filter, removeDuplicates), combining (merge, zip, combineLatest), timing (debounce, throttle, delay)
- [Subjects](subjects.md) — PassthroughSubject, CurrentValueSubject, differences, bridging imperative code to reactive pipelines
- [Backpressure & Cancellation](backpressure-cancellation.md) — Demand, Subscribers.Demand, AnyCancellable, cancellation propagation, memory management
- [Combine Networking](combine-networking.md) — dataTaskPublisher, tryMap, decode, retry, error recovery
- [Combine + UIKit & SwiftUI](combine-swiftui-uikit.md) — data binding, KVO publishers, @Published, sink in UIKit, Combine vs async/await

## Combine Architecture

```
Publisher  ──operator──  operator  ──────  Subscriber
   │                                           │
emits Output,                         receives Output,
Failure values                        Completion or Failure
```

Every Combine pipeline has three type parameters:
- `Output` — the type of value emitted.
- `Failure` — the type of error (`Never` if the publisher cannot fail).
- The `Subscriber`'s `Input` must match the publisher's `Output`.

## Key Concepts at a Glance

| Concept | One-line summary |
|---------|-----------------|
| Publisher | A type that can emit a sequence of values over time |
| Subscriber | A type that receives and processes values from a Publisher |
| Operator | A method on Publisher that transforms the stream, returning a new Publisher |
| Subject | A Publisher you can push values into imperatively |
| AnyCancellable | A token that cancels a subscription when deallocated |
| Backpressure | A mechanism for Subscribers to control how fast Publishers emit values |
| sink | The most common Subscriber — closure-based, handles values and completion |
| assign | Subscriber that assigns values to a key path on an object |
| Demand | The Subscriber's signal for how many more values it wants |

## Reactive Programming Decision Map

```
Need to respond to async value changes over time?
│
├─ Single async value (network call, database read)
│   ├─ New code, iOS 15+   → async/await (simpler, structured)
│   └─ Legacy API / Combine existing pipeline → Future<Output, Error>
│
├─ Multiple events over time (button taps, text changes)
│   └─ Combine: Subject or @Published + operators
│
├─ Combine multiple async sources
│   ├─ Wait for all to finish   → combineLatest / zip
│   └─ Use first result         → merge
│
├─ Data binding (model → UI)
│   ├─ SwiftUI   → @Published + ObservableObject (built on Combine)
│   └─ UIKit     → sink { [weak self] in self?.label.text = $0 }
│
└─ Rate limiting user input
    └─ debounce / throttle on TextField publisher
```

## Relationship to Other Sections

- **Concurrency**: Combine predates async/await; many patterns overlap. Combine's `Future` bridges to `async/await` via `values` property (iOS 15+). See [async/await](../03-concurrency/async-await.md).
- **Memory Management**: `AnyCancellable` uses ARC — store subscriptions in a `Set<AnyCancellable>` to keep them alive. See [Retain Cycles](../02-memory-management/retain-cycles.md).
- **UI Frameworks**: `@Published` in `ObservableObject` is implemented on top of Combine. See [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md).
