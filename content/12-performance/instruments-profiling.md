# Instruments & Profiling

## 1. Overview

Instruments is Apple's performance-analysis suite bundled with Xcode. It attaches to a running app (on device or simulator) and samples or traces system activity at hardware level. The four most important templates for iOS performance work are: **Time Profiler** (CPU time per function), **Allocations** (heap object lifecycle), **Leaks** (unreachable retain cycles), and **Energy Log** (battery drain from CPU/GPU/network/location). Instruments runs against a **Release** build with compiler optimisations enabled — profiling a Debug build gives artificially inflated numbers. Xcode's Debug Navigator also provides real-time gauges (CPU, memory, disk, network) for quick sanity checks without a full Instruments session. The output of a profiling session is an `.trace` file that can be shared, archived, and diffed across builds.

## 2. Simple Explanation

Profiling with Instruments is like adding timing gates to a race course. Without gates, you know the car finished in 2 minutes but not which corner was slow. Time Profiler puts a gate at every function — now you know corner 3 took 1.4 of those 2 minutes. Allocations is the pit crew tracking every tyre fitted and removed — it tells you which object is being created 50,000 times per scroll. Leaks finds tyres that were fitted but never removed and are now blocking the garage. Energy Log is the fuel gauge — it shows whether the engine or the air conditioning is draining the tank.

## 3. Deep iOS Knowledge

### Time Profiler

Time Profiler samples the call stack of every thread at a configurable interval (default: 1 ms). It reports **self time** (time spent in a function itself, excluding callees) and **total time** (including all callees). Self time is the key metric — high self time in a function means that function itself is the bottleneck, not something it calls.

**Workflow:**
1. Open Instruments: Xcode → Product → Profile (⌘I) → Time Profiler.
2. Press Record. Reproduce the slow scenario.
3. Stop recording. Select the time range of interest in the timeline.
4. In the call tree, enable **"Hide System Libraries"** to focus on app code.
5. Sort by **Self Time (%)** descending. The top entry is the heaviest symbol.
6. Double-click a symbol → opens the source file at the hot line.

**Key settings:**
- **Call Tree → Separate by Thread**: see which thread owns each cost.
- **Call Tree → Invert Call Tree**: shows leaves (the actual hot functions) at the top.
- **High Frequency**: reduce sample interval to 0.25 ms for finer granularity.

### Allocations

Allocations tracks every `malloc`/`free` and every Objective-C/Swift allocation. It distinguishes:

- **Persistent**: objects alive right now.
- **Transient**: objects created and released — high counts indicate allocation churn.
- **All heap allocations**: the cumulative count since launch.

**Heap Shot workflow (finding leaks after a user action):**
1. Perform the baseline action (e.g., load the feed).
2. Click **Mark Heap** → Heap Shot 1.
3. Perform the action again.
4. Click **Mark Heap** → Heap Shot 2.
5. The delta between shots shows objects created in step 3 that were not released — candidates for leaks or unnecessary retention.

**Generation Analysis**: switch to "Generations" mode to track which objects survive a mark. Surviving generations that grow unboundedly indicate a memory leak.

### Leaks

Leaks scans the heap for **unreachable objects** — objects with a retain count > 0 but no strong reference path from a root (stack variable, global, or static). It runs automatically while you use the app. A red bar in the Leaks timeline means leaked objects were detected.

**Reading a Leak:**
1. Click a red bar in the timeline.
2. The Cycles & Roots panel shows the retain cycle graph — which object holds a strong reference to which.
3. The call stack shows where the leaked object was allocated.

**Common patterns detected:**
- `NotificationCenter` observer not removed before `deinit`.
- Delegate stored as `strong` instead of `weak`.
- `Timer` with a strong `target:` reference to its owner.
- Closure capturing `self` strongly in a property that `self` also holds.

### Energy Log

Energy Log aggregates power consumption across four subsystems — CPU, GPU, network (Wi-Fi/cellular), and location — into a timeline. It shows **High / Medium / Low / Overhead** energy levels per second. Useful for diagnosing battery drain in background processing, location apps, and video playback features.

Key patterns to look for:
- **CPU spikes during scroll** → rendering or data processing on main thread.
- **Network bursts on a timer** → unnecessary polling; switch to push/WebSocket.
- **GPS always-on** → change to `significantLocationChanges` or reduce accuracy.
- **GPU always active** → off-screen rendering or continuous `CADisplayLink` work.

### Xcode Debug Gauges

Xcode's Debug Navigator (⌘7) shows real-time gauges while running in debug mode:

| Gauge | What it shows |
|-------|--------------|
| CPU | % usage per core |
| Memory | Heap + dirty pages; warns on memory pressure |
| Disk | Read/write bytes/s |
| Network | Bytes sent/received |
| GPU | Frame rate, GPU utilisation |
| Energy Impact | Composite score (Low/Medium/High) |

Gauges are not as accurate as Instruments (no symbolication, sampled infrequently) but are useful for immediate feedback during development.

### Flame Graph vs Call Tree

Instruments shows a call tree by default. Flip to **Flame Graph** view (the icon in the toolbar) for a visual representation where width = time and rows = stack depth. Flame graphs make it immediately obvious which subtree dominates — the widest block is the bottleneck.

### Profiling on Device vs Simulator

| Aspect | Device | Simulator |
|--------|--------|-----------|
| CPU timing | Accurate (real ARM) | Inflated (x86/ARM host) |
| Memory pressure | Real (limited RAM) | No pressure (uses host RAM) |
| GPU | Real Metal pipeline | Emulated |
| Thermal throttling | Yes | No |
| Recommendation | **Always** for release profiling | OK for quick iteration |

## 4. Practical Usage

```swift
// ── Forcing a Release build for profiling ─────────────────────
// Edit scheme → Run → Build Configuration → Release
// This enables -O and -whole-module-optimization

// ── Instrumenting custom code with os_signpost ────────────────
import os.signpost

extension Logger {
    static let rendering = Logger(subsystem: "com.myapp", category: "rendering")
}

// Mark a performance-sensitive interval
func renderFeed(posts: [Post]) {
    let signpostID = OSSignpostID(log: .default)
    os_signpost(.begin, log: .default, name: "renderFeed", signpostID: signpostID,
                "post count: %d", posts.count)
    defer {
        os_signpost(.end, log: .default, name: "renderFeed", signpostID: signpostID)
    }

    for post in posts {
        renderCell(post: post)
    }
}

// os_signpost intervals appear as coloured bars in the Time Profiler timeline
// alongside the call tree — showing exactly when the interval started/ended

// ── Detecting main-thread violations ──────────────────────────
// Enable the "Main Thread Checker" in the scheme diagnostics:
// Edit Scheme → Run → Diagnostics → ✓ Main Thread Checker
// This crashes the app (in debug) when UIKit APIs are called off-main-thread

// ── Allocations: reducing churn in a hot path ─────────────────
// Before: allocates a new array per call
func hotPath(items: [Item]) -> [String] {
    return items.map { $0.name }   // new Array allocation every time
}

// After: pre-allocated buffer
func hotPath(items: [Item], into buffer: inout [String]) {
    buffer.removeAll(keepingCapacity: true)   // reuse the allocation
    for item in items {
        buffer.append(item.name)
    }
}

// ── Using MetricKit for production performance data ────────────
import MetricKit

// MetricKit delivers on-device performance reports aggregated daily
final class MetricsManager: NSObject, MXMetricManagerSubscriber {

    override init() {
        super.init()
        MXMetricManager.shared.add(self)
    }

    // Called daily with aggregate metrics from the previous 24 hours
    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            if let launchMetrics = payload.applicationLaunchMetrics {
                let resumeTime = launchMetrics.applicationResumeTime
                    .histogrammedTimeToFirstDraw.bucketEnumerator
                // Log or upload to analytics
                _ = resumeTime
            }

            if let animMetrics = payload.animationMetrics {
                let scrollHitch = animMetrics.scrollHitchTimeRatio
                // scrollHitch > 0.05 (5%) is considered poor
                _ = scrollHitch
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between Time Profiler and Allocations in Instruments?**

A: Time Profiler answers "where does the CPU spend time?" by sampling call stacks at a fixed interval (typically 1 ms) and reporting the percentage of samples each function appeared in. It identifies slow code paths — functions with high self-time are the performance bottleneck. Allocations answers "what is being created on the heap and how much memory does it consume?" by tracing every `malloc`/`free`. It identifies allocation churn (many short-lived objects that stress the allocator and cause GC-like pauses in the retain/release system) and memory growth (persistent objects accumulating over time). Use Time Profiler for jank and slow operations; use Allocations for memory growth and over-allocation.

**Q: Why must you profile on a Release build rather than a Debug build?**

A: Debug builds compile with `-Onone` (no optimisations) to improve debuggability — the compiler does not inline functions, does not eliminate dead code, and keeps every variable on the stack. This makes Debug builds 3–10× slower than Release builds. Profiling a Debug build will identify bottlenecks that don't exist in production (optimised-away code appears expensive) and miss bottlenecks that do exist (inlined code doesn't appear as a separate entry in the call tree). Always profile a Release build (or a custom "Profile" configuration derived from Release) to get production-accurate timing data.

### Hard

**Q: How do you use Heap Shots in Allocations to find a memory leak that doesn't appear in the Leaks instrument?**

A: The Leaks instrument only finds objects that are unreachable (no strong reference path from a root). A logical leak — an object that is reachable but should have been released — won't appear in Leaks. Heap Shots detect these: perform the action expected to be leak-free (e.g., open a modal, dismiss it), mark the heap, repeat several times. After 5 iterations, if the same class appears in each heap delta with growing count, it's a logical leak — something is retaining it (a cache, an array, a notification observer) that should have removed its reference when the modal was dismissed. Use the "Object Details" panel to see the allocation call stack and the "Responsible Library" to narrow to app code.

**Q: What does `os_signpost` add to a profiling session and when should you use it?**

A: `os_signpost` emits timestamped events into the unified logging system that Instruments visualises as labelled intervals or points in the Time Profiler timeline. Without signposts, the call tree shows raw function names — you can see `renderFeed` took 80 ms but can't correlate it with "which specific batch of posts?" or "did this include the network wait?" With signposts you can bracket an operation with `.begin`/`.end` and include metadata (e.g., post count, batch index) as a format string. The interval appears as a coloured bar in the Custom Instruments lane, making it easy to align timing with user interactions and identify which invocation of `renderFeed` was slow. Use signposts in any performance-sensitive code path you regularly profile — image decoding, diffable data source snapshots, JSON parsing, and cell configuration are common targets.

### Expert

**Q: How would you set up a continuous performance regression detection pipeline for an iOS app?**

A: Four layers: (1) **MetricKit** in production: subscribe to `MXMetricManagerSubscriber` and upload daily payloads (launch time histograms, hitch rate, hang rate, memory termination count) to a backend. Plot these metrics on a dashboard per build version — a spike in the scroll hitch ratio after a specific commit identifies the regression. (2) **XCTest performance tests** in CI: use `measure(metrics: [XCTCPUMetric(), XCTMemoryMetric(), XCTClockMetric()])` for key operations (JSON decode of a 1000-item feed, diffable snapshot application, Core Data batch insert). Set a baseline and tolerance; the test fails if the metric exceeds `baseline × (1 + tolerance)`. Check these baselines into source control. (3) **Instruments automation** via `xctrace`: `xctrace record --template "Time Profiler" --device <id> --launch -- <app-path>` runs a headless Time Profiler session from the command line. Parse the `.trace` with `xctrace export --input recording.trace --output trace.xml` and script checks on self-time of critical symbols. (4) **Allocation budgets**: write a test that creates N cells, measures peak memory, and fails if peak exceeds the budget (e.g., "FeedViewController with 100 posts must fit in < 50 MB working set").

## 6. Common Issues & Solutions

**Issue: Time Profiler shows all time in `objc_msgSend` or `dyld_stub_binder`.**

Solution: Enable **"Hide System Libraries"** in the Call Tree settings. These entries are system infrastructure — the actual bottleneck is in the caller above them. Invert the call tree (Call Tree → Invert Call Tree) to surface the leaf functions that are actually consuming time.

**Issue: Leaks instrument shows no leaks but memory grows continuously.**

Solution: This is a logical leak (reachable but should be released). Use Heap Shots: mark the heap before and after repeating an action. Objects that appear in every delta are accumulated without being released. Common cause: a cache (NSCache, Dictionary) with no eviction policy, or an append-only array used as an event log.

**Issue: Instruments shows accurate data on the simulator but not on the device.**

Solution: The device and simulator use different CPU architectures. Build and profile directly on the device for accurate measurements. Also check that the app is built with `Release` configuration — simulator Debug builds are especially misleading because the host machine's CPU is much faster than the device's ARM core.

## 7. Related Topics

- [Memory Optimization](memory-optimization.md) — Allocations findings lead to memory optimisation
- [Main Thread Optimization](main-thread-optimization.md) — Time Profiler findings lead to threading work
- [App Startup & Runtime](../13-app-startup/index.md) — launch time profiling with Instruments App Launch template
- [Core Animation](../09-ios-platform/core-animation.md) — GPU profiling for off-screen rendering
- [Memory Management — ARC](../02-memory-management/arc-memory-management.md) — Leaks findings map to ARC retain cycles
