# Operation & OperationQueue

## 1. Overview

`Operation` and `OperationQueue` are Objective-C-era Foundation classes that provide a higher-level, object-oriented concurrency model built on top of GCD. An `Operation` is an object that encapsulates a unit of work, complete with a state machine (pending → ready → executing → finished/cancelled), support for dependencies between operations, and cooperative cancellation. An `OperationQueue` manages a collection of operations and dispatches them to an underlying thread pool, respecting dependencies and a configurable maximum concurrency level.

## 2. Simple Explanation

Think of an `OperationQueue` as a construction site manager. Each `Operation` is a work order — it has a status (waiting, in progress, done, cancelled), may depend on other work orders being finished first, and can be cancelled if the project changes.

GCD is like giving workers sticky notes with instructions. It is fast and simple, but notes don't know about each other. Operations are work orders in a filing system — they can say "don't start me until Order #5 is complete", and if the client cancels the project, you can recall all outstanding orders at once.

## 3. Deep iOS Knowledge

### Operation State Machine

An `Operation` moves through states in order:

```
isReady → isExecuting → isFinished
                ↓
           isCancelled
```

- **isReady**: all dependencies have finished.
- **isExecuting**: the operation is currently running.
- **isFinished**: the operation completed (successfully or by cancellation).
- **isCancelled**: `cancel()` was called. The operation must check this flag itself and stop work — cancellation is cooperative, not preemptive.

For `BlockOperation` and subclasses that override `main()`, the queue manages state transitions automatically. For async operations (overriding `start()`), you must manually post KVO notifications for `isExecuting` and `isFinished`.

### BlockOperation

`BlockOperation` wraps one or more closures. All closures run concurrently (on GCD) and the operation is not finished until all complete. You can add blocks after creation with `addExecutionBlock(_:)`.

### Custom Operation Subclass

Override `main()` for synchronous work:
```swift
class ParseOperation: Operation {
    var inputData: Data?
    var result: [String] = []

    override func main() {
        guard !isCancelled, let data = inputData else { return }
        // parse...
        result = parse(data)
    }
}
```

For asynchronous operations, override `start()` and manually manage `isExecuting`/`isFinished` with KVO.

### Dependencies

`addDependency(_:)` creates a happens-before relationship: the dependent operation will not start until all its dependencies are finished (or cancelled). Dependencies can span queues.

| Property | Purpose |
|----------|---------|
| `addDependency(op)` | This operation waits for `op` to finish |
| `removeDependency(op)` | Remove the dependency |
| `dependencies` | All registered dependency operations |

**Caution**: circular dependencies cause a deadlock — neither operation ever becomes ready.

### Cancellation

Calling `queue.cancelAllOperations()` sets `isCancelled` on every operation in the queue. Operations that haven't started are removed; running operations must periodically check `isCancelled` and stop. Finished operations ignore cancellation.

### maxConcurrentOperationCount

Setting this to 1 makes the queue serial (executes one operation at a time). Setting it to `OperationQueue.defaultMaxConcurrentOperationCount` lets the system decide (usually based on CPU cores and QoS).

### Comparison to GCD

| Feature | GCD | OperationQueue |
|---------|-----|---------------|
| Abstraction level | Low (closures, queues) | High (objects with lifecycle) |
| Dependencies | Manual (groups/semaphores) | First-class (`addDependency`) |
| Cancellation | Cooperative via `WorkItem` | Cooperative via `isCancelled` flag |
| Max concurrency | Semaphore-based hack | `maxConcurrentOperationCount` |
| Observation | None | KVO on `isExecuting`, `isFinished` |
| Retry / replay | Manual | Override `start()` |
| Overhead | Lower | Higher (ObjC runtime, KVO) |

Use `OperationQueue` when you need: dependency graphs, per-operation cancellation, observable state, or the ability to replay/resubmit operations. Use GCD for simple fire-and-forget async work.

## 4. Practical Usage

```swift
import Foundation

// ── BlockOperation with dependencies ───────────────────────────
let downloadOp = BlockOperation {
    print("Downloading image...")
    // simulate download
}

let processOp = BlockOperation {
    print("Processing image...")
    // processOp won't start until downloadOp finishes
}
processOp.addDependency(downloadOp)

let saveOp = BlockOperation {
    print("Saving to disk...")
}
saveOp.addDependency(processOp)

let queue = OperationQueue()
queue.name = "com.app.imagePipeline"
queue.maxConcurrentOperationCount = 4

queue.addOperations([downloadOp, processOp, saveOp], waitUntilFinished: false)

// ── Custom synchronous Operation subclass ──────────────────────
class ResizeOperation: Operation {
    let image: UIImage
    let targetSize: CGSize
    private(set) var resized: UIImage?

    init(image: UIImage, targetSize: CGSize) {
        self.image = image
        self.targetSize = targetSize
    }

    override func main() {
        guard !isCancelled else { return }

        // Do work — check isCancelled periodically in long operations
        let renderer = UIGraphicsImageRenderer(size: targetSize)
        resized = renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: targetSize))
        }

        guard !isCancelled else {
            resized = nil   // discard result if cancelled mid-way
            return
        }
    }
}

// ── Cancelling all operations on view disappear ─────────────────
class ImageListViewController: UIViewController {
    let imageQueue = OperationQueue()

    override func viewDidLoad() {
        super.viewDidLoad()
        imageQueue.maxConcurrentOperationCount = 3
        imageQueue.qualityOfService = .userInitiated
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        imageQueue.cancelAllOperations()  // user navigated away — no need to continue
    }

    func loadImage(url: URL) {
        let op = BlockOperation { [weak self] in
            guard let self, !Thread.current.isCancelled else { return }
            // download & decode...
            DispatchQueue.main.async {
                // update cell
            }
        }
        imageQueue.addOperation(op)
    }
}

// ── Wrapping OperationQueue in async/await ──────────────────────
// For bridging legacy Operation pipelines into modern async code:
func processImage(_ image: UIImage) async -> UIImage {
    await withCheckedContinuation { continuation in
        let op = ResizeOperation(image: image, targetSize: CGSize(width: 200, height: 200))
        op.completionBlock = {
            continuation.resume(returning: op.resized ?? image)
        }
        OperationQueue().addOperation(op)
    }
}

// ── Main-queue OperationQueue for serialised UI work ───────────
let mainQueue = OperationQueue.main  // equivalent to DispatchQueue.main
mainQueue.addOperation {
    // this runs on the main thread
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `Operation.cancel()` and actually stopping the operation?**

A: `cancel()` sets the `isCancelled` flag to `true` — it does not preemptively interrupt running code. The operation's `main()` (or `start()`) method must periodically check `isCancelled` and return early when it is `true`. This cooperative model means you must design your operations to be cancellation-aware, particularly in loops or after each significant chunk of work. An operation that ignores `isCancelled` will run to completion even after `cancel()` is called.

**Q: What does `addDependency` do?**

A: It creates a happens-before relationship. The dependent operation will not enter the executing state until all operations it depends on have reached the finished state (whether they succeeded or were cancelled). Dependencies can cross queue boundaries — you can add a dependency on an operation in a different `OperationQueue`. The queue monitors the dependency's `isFinished` KVO property to know when to promote the dependent to ready.

### Hard

**Q: How do you implement an asynchronous `Operation` subclass that wraps an async callback-based API?**

A: Override `start()` (not `main()`), manage `isExecuting` and `isFinished` manually via KVO, and set `isAsynchronous` to return `true`. When the callback fires, set `isExecuting = false` and `isFinished = true`. The KVO notifications signal to the queue that the operation is done:

```swift
class AsyncFetchOperation: Operation {
    private var _executing = false { willSet { willChangeValue(forKey: "isExecuting") }
                                     didSet  { didChangeValue(forKey: "isExecuting") } }
    private var _finished  = false { willSet { willChangeValue(forKey: "isFinished") }
                                     didSet  { didChangeValue(forKey: "isFinished") } }
    override var isAsynchronous: Bool { true }
    override var isExecuting: Bool    { _executing }
    override var isFinished:  Bool    { _finished }

    override func start() {
        guard !isCancelled else { _finished = true; return }
        _executing = true
        URLSession.shared.dataTask(with: URL(string: "https://example.com")!) { [weak self] _, _, _ in
            self?._executing = false
            self?._finished  = true
        }.resume()
    }
}
```

Without the correct KVO, the queue will think the operation finishes immediately after `start()` returns, causing dependent operations to start prematurely.

### Expert

**Q: Compare the overhead and appropriate use cases of `OperationQueue` versus `withTaskGroup` in Swift Concurrency.**

A: `OperationQueue` carries ObjC runtime overhead (KVO, NSObject allocation, lock-based state machine per operation) and is best suited to use cases requiring observable state, complex dependency graphs, or integration with legacy ObjC code. `withTaskGroup` is a pure Swift structured concurrency primitive that multiplexes onto the cooperative thread pool — child tasks suspend (not block) when waiting, consuming no thread. This makes `withTaskGroup` dramatically more efficient for high-concurrency scenarios (thousands of tasks), as it avoids thread explosion entirely. `withTaskGroup` also composes naturally with `async/await` and provides cooperative cancellation via `Task.checkCancellation()`. Choose `OperationQueue` for dependency graphs with rich lifecycle observation, legacy API bridging, or ObjC interop. Choose `withTaskGroup` for new Swift code doing fan-out parallel work where the cooperative thread pool is available.

## 6. Common Issues & Solutions

**Issue: Dependent operation starts before its dependency finishes.**

Solution: Ensure the dependency operation properly sets `isFinished` to `true`. For async operations, this requires manual KVO. Verify by adding a `completionBlock` to the dependency and logging the order.

**Issue: `cancelAllOperations()` doesn't stop running operations.**

Solution: Operations must check `isCancelled` periodically inside `main()`. Add `guard !isCancelled else { return }` at each loop iteration or after each significant step.

**Issue: Circular dependency — queue deadlocks and no operations ever run.**

Solution: Never create dependency cycles (A depends on B, B depends on A). Review the dependency graph. Instruments → System Trace or a thread backtrace will show all operations stuck in the `isReady == false` state.

**Issue: Memory leak — operations retained by the queue long after completion.**

Solution: Operations are removed from the queue when they finish. If they linger, verify `isFinished` is being set to `true`. For custom async operations, check that the KVO mechanism is correct and that the completion callback always fires.

## 7. Related Topics

- [GCD & Dispatch Queues](gcd-dispatch-queue.md) — lower-level alternative OperationQueue builds on
- [DispatchGroup, Semaphore & Barrier](dispatch-group-semaphore.md) — GCD coordination primitives
- [Task & TaskGroup](task-taskgroup.md) — modern Swift alternative to Operation dependencies
- [Concurrency Problems](concurrency-problems.md) — deadlocks from circular dependencies
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — `[weak self]` inside `BlockOperation`
