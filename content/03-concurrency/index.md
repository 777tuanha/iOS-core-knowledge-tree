# Concurrency

## Overview

Concurrency in iOS means executing multiple tasks at the same time — or at least appearing to — to keep the UI responsive and make full use of multi-core hardware. iOS provides a layered set of concurrency tools: from the low-level **Grand Central Dispatch (GCD)** C API, to the object-oriented **Operation/OperationQueue** layer, to the modern Swift **async/await** and **structured concurrency** model introduced in Swift 5.5 / iOS 15.

Concurrency is one of the most tested interview topics because it sits at the intersection of correctness (race conditions, deadlocks) and performance (thread utilisation, responsiveness). This section covers every layer of the stack and the tradeoffs between them.

## Topics in This Section

- [GCD & Dispatch Queues](gcd-dispatch-queue.md) — serial vs concurrent queues, QoS classes, global vs custom queues, `async`/`sync`
- [DispatchGroup, Semaphore & Barrier](dispatch-group-semaphore.md) — coordinating multiple async tasks, `DispatchSemaphore`, reader-writer lock
- [Operation & OperationQueue](operation-queue.md) — dependency graphs, cancellation, `BlockOperation`, comparison to GCD
- [async/await](async-await.md) — suspension points, `async let`, bridging callbacks with `withCheckedContinuation`
- [Task & TaskGroup](task-taskgroup.md) — task lifecycle, priorities, structured vs unstructured, cancellation
- [Actors](actors.md) — `actor` isolation, `MainActor`, `nonisolated`, `Sendable`, reentrancy
- [Concurrency Problems](concurrency-problems.md) — race conditions, deadlocks, thread explosion, priority inversion

## Key Concepts at a Glance

| Concept | One-line summary |
|---------|-----------------|
| GCD | C-level thread pool managed by the OS; queues dispatch work items |
| Serial queue | One task at a time; guarantees ordering |
| Concurrent queue | Multiple tasks simultaneously; ordering not guaranteed |
| QoS | Quality-of-service hint used by the scheduler to prioritise work |
| DispatchGroup | Coordinate completion of multiple async tasks |
| DispatchSemaphore | Limit concurrent access to a resource |
| DispatchBarrier | Exclusive write access in a concurrent queue |
| Operation | Object-based work unit with lifecycle (ready/executing/finished/cancelled) |
| async/await | Swift syntax that suspends a function without blocking a thread |
| Structured concurrency | Tasks form a tree; parent waits for children; cancellation propagates |
| Actor | Reference type that serialises access to its mutable state |
| MainActor | Global actor that confines work to the main thread |
| Sendable | Protocol marking types safe to cross concurrency domain boundaries |
| Race condition | Two threads read/write shared state concurrently with no synchronisation |
| Deadlock | Two or more threads wait for each other indefinitely |

## Concurrency Tool Decision Map

```
Need to dispatch work off the main thread?
│
├─ One-off task, no dependencies → GCD async (DispatchQueue.global().async)
│
├─ Multiple tasks to wait for together → DispatchGroup / async let / TaskGroup
│
├─ Complex dependency graph / cancellable objects → OperationQueue
│
├─ Limit concurrent access → DispatchSemaphore or actor
│
└─ Writing new Swift code (iOS 15+)?
   ├─ Simple background work → Task { }
   ├─ Fan-out parallel work → withTaskGroup
   └─ Shared mutable state → actor
```

## Relationship to Other Sections

- **Memory Management**: Closures passed to GCD capture `self`; without `[weak self]`, they create retain cycles — see [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md).
- **Swift Language**: `weak` and `unowned` references frequently appear in async callbacks — see [Weak vs Unowned](../01-swift-language/weak-vs-unowned.md).
- **UI Frameworks**: All UIKit/SwiftUI updates must happen on the main thread; `@MainActor` enforces this at compile time — see [UI Frameworks](../04-ui-frameworks/index.md).
