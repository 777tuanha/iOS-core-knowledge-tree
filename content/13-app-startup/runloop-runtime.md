# RunLoop & Runtime

## 1. Overview

The **RunLoop** is the event-processing engine at the heart of iOS's main thread. It is a loop that waits for events (touch inputs, timer fires, network callbacks, display link callbacks), dispatches them to registered handlers, and then sleeps until the next event arrives — preventing the thread from exiting while also never wasting CPU cycles in a busy-wait. Every thread can have a RunLoop, but only the main thread's RunLoop starts automatically; background thread RunLoops must be started manually. The RunLoop operates in **modes** — distinct sets of input sources and observers — that determine which sources are active at a given time. Understanding the RunLoop is essential for diagnosing and fixing hangs, timer misfires, scroll interruption bugs, and `CADisplayLink` behavior. The **runtime** layer — ObjC message dispatch, Swift dynamic dispatch, and the Swift concurrency cooperative scheduler — overlays the RunLoop and determines how code executes once the RunLoop delivers an event.

## 2. Simple Explanation

A RunLoop is like a hotel concierge who never leaves the lobby. The concierge stands at the front desk waiting for guests to arrive with requests (events). When a guest arrives (a touch event, a timer fires), the concierge handles the request, then waits again. When the hotel is quiet (no events), the concierge doesn't pace around burning energy — they stand still doing nothing (the thread sleeps). The hotel has different modes: "conference mode" (only conference guests are served — other guests wait) and "normal mode" (everyone is served). A `CADisplayLink` is like a clock on the wall that triggers a request every 16 ms — the concierge handles it as a regular request each time it fires.

## 3. Deep iOS Knowledge

### RunLoop Structure

```
RunLoop
├── Modes (sets of sources + observers)
│   ├── .default  — normal operation: timers, custom sources
│   ├── .tracking — UIScrollView tracking: suppresses .default timers
│   ├── .common   — meta-mode: runs in both .default and .tracking
│   └── custom modes (e.g., "NSModalPanelRunLoopMode")
│
├── Input Sources
│   ├── Port-based (mach_msg): network callbacks, inter-thread messages
│   └── Custom (CFRunLoopSource): manual signal
│
├── Timer Sources
│   └── NSTimer / CFRunLoopTimer — fires after a time interval
│
└── Observers
    ├── kCFRunLoopEntry — about to process events
    ├── kCFRunLoopBeforeWaiting — about to sleep
    ├── kCFRunLoopAfterWaiting — woke from sleep
    └── kCFRunLoopExit — RunLoop about to exit
```

### RunLoop Iteration

A single RunLoop iteration:
1. **Notify observers**: `kCFRunLoopEntry` (on first run).
2. **Process timers**: fire any timers whose fire date has passed.
3. **Process input sources**: handle all pending mach port messages, CFRunLoopSource signals.
4. **Notify observers**: `kCFRunLoopBeforeWaiting`.
5. **Sleep**: the thread blocks on `mach_msg` waiting for the next event.
6. **Notify observers**: `kCFRunLoopAfterWaiting` (woke up).
7. **Process the wakeup source**: the timer/port/source that woke the RunLoop.
8. Repeat.

The key insight: UIKit touch events arrive as mach port messages that wake the RunLoop. `CADisplayLink` is a special timer tied to the display's VSYNC signal. `DispatchQueue.main.async` posts a message to the main queue's port, waking the RunLoop.

### RunLoop Modes and Scroll

**`UITrackingRunLoopMode`** (`.tracking`) is active while the user is actively scrolling a `UIScrollView`. During tracking mode, only tracking-mode sources fire — **`NSTimer`s registered in `.default` mode do not fire during scroll**. This is why a `Timer.scheduledTimer(...)` may appear to pause during scrolling. To fire during scroll, schedule the timer in `.common` mode:

```swift
RunLoop.main.add(timer, forMode: .common)
```

This is a common source of bugs in apps that use timers to drive animations or progress updates — the animation freezes during scroll.

### NSTimer and CADisplayLink

`NSTimer`: fires at a specified interval, tolerates coalescing by the system (runs slightly late to optimize power). Not suitable for frame-accurate animation. `NSTimer` retains its `target` strongly — a common source of retain cycles.

`CADisplayLink`: synchronised to the display's refresh rate (60 or 120 Hz). Use for smooth frame-by-frame animation, custom drawing, or anything that must update every display frame. Always pair with `invalidate()` in `deinit`.

```swift
final class CounterAnimation {
    private var displayLink: CADisplayLink?

    func start() {
        displayLink = CADisplayLink(target: self, selector: #selector(tick))
        displayLink?.add(to: .main, forMode: .common)   // fires during scroll too
    }

    @objc private func tick(_ link: CADisplayLink) {
        // link.timestamp: time of the current frame
        // link.duration: time per frame (1/60 or 1/120)
        updateAnimation(progress: computeProgress(at: link.timestamp))
    }

    func stop() {
        displayLink?.invalidate()
        displayLink = nil
    }

    deinit { stop() }
}
```

### Main Thread Scheduling

The main RunLoop processes one event at a time. Heavy work in any event handler blocks subsequent events — this is the source of main thread jank. The key points:

- `DispatchQueue.main.async` enqueues a block on the main queue. The RunLoop's next iteration will dequeue and execute it.
- `DispatchQueue.main.sync` (from a background thread) blocks the calling thread until the block runs on the main thread — never call this from the main thread (deadlock).
- Multiple `DispatchQueue.main.async` calls in a tight loop are batched and processed across multiple RunLoop iterations — each iteration processes all pending items in the queue.

### Swift Concurrency and the RunLoop

Swift concurrency's `@MainActor` serialises code on the main actor — conceptually the main thread. Internally, continuations are delivered as work items to the main thread's dispatch queue, which wakes the RunLoop as a normal queue event. `Task { @MainActor in }` is equivalent to `DispatchQueue.main.async { }` in scheduling terms, but composable with structured concurrency.

Background tasks run on the **cooperative thread pool** — a fixed-size pool of threads managed by the Swift runtime. The pool size is proportional to the number of CPU cores. `Task.detached` and `actor` methods run on this pool. The pool does not use a RunLoop — instead, it uses `dispatch_async` on concurrent queues.

### ObjC Runtime: Message Dispatch

`objc_msgSend` is the entry point for every ObjC method call. It looks up the method implementation in the class's method cache (fast path: hash table lookup, 1–2 ns), or if not cached, traverses the class hierarchy (slow path). Swift methods on `@objc`-bridged types also go through `objc_msgSend`. Pure Swift methods use a static vtable dispatch (for `class` types) or direct call (for `struct`/`final class` methods) — faster than ObjC message dispatch.

### Detecting Hangs

A **hang** is a period where the main thread is blocked and the RunLoop cannot process new events. iOS measures hangs using MetricKit:

- **Hang rate**: percentage of seconds the app was hung (main thread blocked > 250 ms).
- **Hang duration histogram**: distribution of hang durations.

Hangs show up in Instruments as gaps in the main thread lane of the Time Profiler. Common causes:
- `DispatchQueue.main.sync` called from a queue that the main thread is waiting for (deadlock).
- Semaphore wait on the main thread.
- Synchronous file I/O (`Data(contentsOf:)`) on the main thread.
- Lock contention — main thread waiting for a lock held by a background thread.

## 4. Practical Usage

```swift
import Foundation
import UIKit

// ── Timer that fires during scroll (.common mode) ─────────────
final class CountdownTimer {
    private var timer: Timer?
    private(set) var remaining: Int = 60
    var onTick: ((Int) -> Void)?

    func start() {
        timer = Timer(timeInterval: 1.0,
                      target: self,
                      selector: #selector(tick),
                      userInfo: nil,
                      repeats: true)
        // .common = active in both .default AND .tracking (scroll) modes
        RunLoop.main.add(timer!, forMode: .common)
    }

    @objc private func tick() {
        remaining -= 1
        onTick?(remaining)
        if remaining == 0 { stop() }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    deinit { stop() }
}

// ── CADisplayLink for smooth value animation ──────────────────
final class SpringAnimator {
    private var displayLink: CADisplayLink?
    private var startTime: CFTimeInterval = 0
    private var duration: Double = 0.4
    var onUpdate: ((CGFloat) -> Void)?
    var onComplete: (() -> Void)?

    func animate(duration: Double = 0.4) {
        self.duration = duration
        startTime = CACurrentMediaTime()
        displayLink = CADisplayLink(target: self, selector: #selector(step))
        displayLink?.add(to: .main, forMode: .common)
    }

    @objc private func step(_ link: CADisplayLink) {
        let elapsed = link.timestamp - startTime
        let progress = min(elapsed / duration, 1.0)
        let eased = springEasing(t: CGFloat(progress))
        onUpdate?(eased)
        if progress >= 1.0 {
            displayLink?.invalidate()
            displayLink = nil
            onComplete?()
        }
    }

    private func springEasing(t: CGFloat) -> CGFloat {
        // Simple spring approximation
        let c4 = (2 * .pi) / 3
        if t == 0 { return 0 }
        if t == 1 { return 1 }
        return pow(2, -10 * t) * sin((t * 10 - 0.75) * c4) + 1
    }

    deinit {
        displayLink?.invalidate()
    }
}

// ── RunLoop observer for pre-sleep bookkeeping ────────────────
func installRunLoopObserver() {
    let observer = CFRunLoopObserverCreateWithHandler(
        kCFAllocatorDefault,
        CFRunLoopActivity.beforeWaiting.rawValue,
        true,   // repeats
        0       // order
    ) { observer, activity in
        // Runs just before the main RunLoop sleeps
        // Useful for: flushing analytics batches, saving drafts
        Analytics.shared.flushIfNeeded()
    }
    CFRunLoopAddObserver(CFRunLoopGetMain(), observer, .commonModes)
}

// ── Detecting main thread blocks ──────────────────────────────
final class HangDetector {
    private let threshold: TimeInterval = 0.25   // 250ms = reportable hang
    private var pingTimer: Timer?
    private var lastPing: Date = .now
    private var monitorQueue = DispatchQueue(label: "hang-detector")

    func start() {
        // Ping the main thread every 100ms
        pingTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.lastPing = Date()   // this line runs on main thread
        }
        RunLoop.main.add(pingTimer!, forMode: .common)

        // Check from background: if the main thread hasn't pinged in > threshold, log a hang
        monitorQueue.async { [weak self] in
            while true {
                Thread.sleep(forTimeInterval: 0.1)
                guard let self else { return }
                let gap = Date().timeIntervalSince(self.lastPing)
                if gap > self.threshold {
                    // Log hang with current main thread stack trace
                    self.reportHang(duration: gap)
                }
            }
        }
    }

    private func reportHang(duration: TimeInterval) {
        // In production: log to Crashlytics/Sentry with main thread backtrace
        print("⚠️ Main thread hang detected: \(String(format: "%.2f", duration))s")
    }
}

// ── Background thread with explicit RunLoop ───────────────────
// Needed for: NSTimer on a background thread, NSURLConnection (legacy), etc.
final class BackgroundRunLoopThread: Thread {
    private var runLoop: RunLoop?

    override func main() {
        runLoop = RunLoop.current
        // Add a port-based source to keep the RunLoop alive (otherwise it exits immediately)
        let port = NSMachPort()
        runLoop?.add(port, forMode: .default)
        runLoop?.run()   // blocks until RunLoop is stopped
    }

    func schedule(timer: Timer) {
        runLoop?.add(timer, forMode: .default)
    }

    func stop() {
        runLoop?.perform { CFRunLoopStop(CFRunLoopGetCurrent()) }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a RunLoop and why does iOS need one?**

A: A RunLoop is a thread-lifecycle mechanism that keeps a thread alive and responsive without busy-waiting. Without a RunLoop, `main()` would return immediately after setup, terminating the process. The RunLoop puts the thread to sleep (blocking on `mach_msg`) until an event arrives — a touch input, a timer fire, a dispatch queue item, a network callback — processes it, then sleeps again. This means the main thread uses zero CPU when idle (no spinning). The main thread's RunLoop is started automatically by `UIApplicationMain`; background threads only have a RunLoop if you explicitly create and run one (needed for `NSTimer` on a background thread, or for legacy run-loop-based networking).

**Q: Why does an `NSTimer` pause during UIScrollView scrolling, and how do you fix it?**

A: `NSTimer.scheduledTimer(...)` schedules the timer in `.default` RunLoop mode. When the user scrolls a `UIScrollView`, the RunLoop switches to `.tracking` mode — only input sources registered in `.tracking` mode fire. Timers in `.default` mode are suspended until scrolling ends and the RunLoop returns to `.default`. Fix: add the timer to `.common` mode: `RunLoop.main.add(timer, forMode: .common)`. The `.common` mode is a meta-mode that includes both `.default` and `.tracking` — sources in `.common` fire regardless of which mode the RunLoop is currently in. The same fix applies to `CADisplayLink`: add it with `forMode: .common` to ensure animation callbacks continue during scroll.

### Hard

**Q: How does `DispatchQueue.main.async` interact with the RunLoop?**

A: `DispatchQueue.main` is backed by a mach port. When you call `DispatchQueue.main.async { }`, the block is enqueued and a message is sent to the main queue's mach port. This message wakes the main RunLoop (which was sleeping on `mach_msg`). The RunLoop's next iteration processes the mach port event, which dequeues and executes the pending blocks. Key implication: if you call `DispatchQueue.main.async` 1000 times in a tight loop, all 1000 blocks will be enqueued, but they are executed one RunLoop iteration at a time (all pending blocks are drained in one RunLoop wakeup). This means a large batch of `DispatchQueue.main.async` calls can delay the RunLoop's ability to process other events (touches, timer fires) until the queue is drained. For progressive UI updates, prefer batching with `CATransaction` or a single `reloadData` call.

**Q: What is a deadlock involving the main RunLoop and how does it manifest?**

A: The classic main-thread deadlock: background thread calls `DispatchQueue.main.sync { }`, which blocks the background thread waiting for the main thread to execute the block; simultaneously, the main thread is waiting for the background thread (via a `semaphore.wait()`, `DispatchQueue(label:).sync { }`, or `OperationQueue` dependency). Neither thread can proceed. The app hangs indefinitely — the main RunLoop never processes the `sync` submission because it's blocked, and the background thread never unblocks because the main thread is blocked. In Instruments Time Profiler, this shows as the main thread stuck in `__dispatch_main_queue_drain_queue_one` or `semaphore_wait_trap` indefinitely. Fix: never call `DispatchQueue.main.sync` from a queue that the main thread might block on. Use `async` instead, or restructure with `async/await` and `await MainActor.run { }`.

### Expert

**Q: How does the RunLoop interact with Swift concurrency's `@MainActor`?**

A: `@MainActor` in Swift concurrency is implemented using the main thread's dispatch queue (`DispatchQueue.main`) as its executor. When a suspended task resumes on `@MainActor`, the runtime schedules a work item on `DispatchQueue.main`. This work item is delivered as a mach port message that wakes the main RunLoop, which then executes the item in its current iteration. The implication: `@MainActor` continuations are subject to the same RunLoop-mode restrictions as `DispatchQueue.main.async` — they won't fire if the RunLoop is blocked for other reasons. Additionally, long-running synchronous code in a `@MainActor` function still blocks the main thread and all RunLoop event processing, just like any other main-thread work. Swift concurrency does not automatically yield the main actor between `await` calls within a function — only at explicit `await` suspension points does the main RunLoop get a chance to process other events. For fine-grained main-thread yielding, use `await Task.yield()`.

## 6. Common Issues & Solutions

**Issue: `NSTimer` stops firing after a while even though it was scheduled correctly.**

Solution: The timer's `target` is probably nil — `NSTimer` holds a strong reference to its target, but if the target was deallocated without calling `timer.invalidate()`, the timer fires against a nil target and does nothing (or crashes in older OS versions). Fix: call `timer.invalidate()` in `deinit` of the target object. Alternatively, use `Timer.scheduledTimer(withTimeInterval:repeats:block:)` with `[weak self]` in the closure to avoid the retain cycle, and call `invalidate()` when done.

**Issue: Custom view animation using `CADisplayLink` causes the app's frame rate to drop from 120 to 60 Hz on ProMotion devices.**

Solution: `CADisplayLink` defaults to `preferredFramesPerSecond = 0` which means "as fast as possible" — on ProMotion displays this should be 120 Hz. If the animation is running at 60 Hz, check: (1) Is the `CADisplayLink` added with `.common` mode? (2) Is the animation computation in the callback taking > 8 ms (ProMotion budget)? Profile with the Core Animation instrument. (3) Use `CADisplayLink.preferredFrameRateRange` (iOS 15+) to specify `.high` preference: `displayLink.preferredFrameRateRange = CAFrameRateRange(minimum: 60, maximum: 120, preferred: 120)`.

**Issue: App receives memory warnings and becomes unresponsive, but Instruments shows no allocation growth.**

Solution: The unresponsiveness is likely due to the main RunLoop being overloaded, not memory. After a memory warning, if the app starts aggressively releasing and re-fetching resources (cache miss storm), the main thread may be flooded with `DispatchQueue.main.async` completions. Profile with Instruments Time Profiler while triggering the warning — if the main thread queue depth is large and it takes seconds to drain, throttle the re-fetch rate using a `DispatchWorkItem` debounce or a rate-limited semaphore on the background fetch queue.

## 7. Related Topics

- [App Launch Process](app-launch-process.md) — how the RunLoop is started
- [Startup Optimization](startup-optimization.md) — deferring work past the first RunLoop iteration
- [Main Thread Optimization](../12-performance/main-thread-optimization.md) — keeping the RunLoop iteration fast
- [Concurrency — async/await](../03-concurrency/async-await.md) — `@MainActor` and the cooperative pool
- [Core Animation](../09-ios-platform/core-animation.md) — `CADisplayLink` and the display pipeline
