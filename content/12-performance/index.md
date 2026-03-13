# Performance

## 1. Overview

Performance engineering on iOS involves two complementary disciplines: **profiling** (measuring where time and memory are spent with Instruments) and **optimization** (applying targeted techniques to eliminate bottlenecks). The golden rule is measure first, optimise second — premature optimisation wastes time and introduces bugs. Instruments ships with Xcode and provides hardware-accurate data: CPU time broken down per thread and function, heap allocations with full call stacks, retain/release lifecycle of every object, energy impact across CPU/GPU/network/location, and more. Optimisation techniques span memory layout (value types, avoiding heap fragmentation), threading (offloading work from the main thread), algorithmic complexity (choosing the right data structure), and deferred work (lazy loading and prefetching strategies).

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Instruments & Profiling](instruments-profiling.md) | Time Profiler, Allocations, Leaks, Energy Log, Xcode Gauges |
| 2 | [Memory Optimization](memory-optimization.md) | Value vs reference types, ARC patterns, memory pressure, Instruments Allocations workflow |
| 3 | [Main Thread Optimization](main-thread-optimization.md) | Identifying main-thread work, async offloading, `Task.detached`, serial queue patterns |
| 4 | [Efficient Data Structures](efficient-data-structures.md) | Array vs Set vs Dictionary complexity, `ContiguousArray`, lazy sequences, `NSCache` |
| 5 | [Lazy Loading](lazy-loading.md) | `lazy var`, lazy sequences, on-demand image loading, prefetching, `UITableViewDataSourcePrefetching` |

## 3. Key Concepts Map

```
Performance
├── Profiling (measure first)
│   ├── Time Profiler  → CPU time per symbol
│   ├── Allocations    → heap objects, persistent vs transient
│   ├── Leaks          → unreachable but retained objects
│   └── Energy Log     → CPU + GPU + network + location cost
│
└── Optimization (fix bottlenecks)
    ├── Memory
    │   ├── Prefer value types (stack allocation)
    │   ├── Reduce ARC traffic (avoid shared mutable state)
    │   └── Respond to memory warnings (purge caches)
    ├── Threading
    │   ├── Keep main thread ≤ 16ms per frame (60 fps)
    │   └── Offload heavy work to background actors/queues
    ├── Data structures
    │   ├── O(1) lookup → Set / Dictionary
    │   └── Sequential access → Array / ContiguousArray
    └── Deferred work
        ├── lazy var (compute on first access)
        └── Prefetch (load before needed)
```

## 4. Profiling Workflow

1. **Profile, don't guess** — attach Instruments before writing any optimisation.
2. **Use a device** — simulator CPU and memory behaviour differ from hardware.
3. **Release build** — compile with optimisations (`-O`); debug builds are 3–10× slower.
4. **Fix the heaviest flame first** — Time Profiler self-time shows where CPU actually spends time.
5. **Verify with a second profile** — confirm the fix improves the metric.

## 5. Performance Budget (60 fps)

| Budget | Limit |
|--------|-------|
| Frame render time | 16.67 ms |
| App launch (cold) | < 400 ms to first frame |
| App launch (warm) | < 200 ms |
| Scroll jank threshold | Any frame > 16.67 ms |
| Memory warning threshold | Device-dependent (~700 MB on iPhone 15) |

## 6. Related Topics

- [App Startup & Runtime](../13-app-startup/index.md) — dyld load time, startup optimisation
- [Concurrency — async/await](../03-concurrency/async-await.md) — offloading work from the main thread
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — prefetching and cell reuse
- [Memory Management](../02-memory-management/index.md) — ARC fundamentals
