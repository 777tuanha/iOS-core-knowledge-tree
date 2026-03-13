# App Startup & Runtime

## 1. Overview

App startup performance directly affects first impressions and App Store ratings — Apple's heuristic is that apps taking longer than 400 ms to reach the first frame are at risk of watchdog termination. Understanding startup means understanding how the OS loads the app binary: `dyld` (the dynamic linker) processes `__TEXT` segments, resolves symbol stubs, and runs `+load` / `__attribute__((constructor))` initializers before `main()` is called. After `main()`, the app initializes its frameworks, runs `AppDelegate.didFinishLaunchingWithOptions`, and installs the root view controller before the first `CATransaction` commit renders a frame. The runtime layer — the RunLoop — then drives all subsequent event processing, timer firing, and display callbacks until the app is terminated. Optimizing startup and understanding runtime scheduling are essential for apps with aggressive launch time requirements and for diagnosing intermittent hangs and watchdog kills.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [App Launch Process](app-launch-process.md) | dyld, dynamic library loading, `+load` vs `+initialize`, pre-main vs post-main phases, launch stages |
| 2 | [Startup Optimization](startup-optimization.md) | Reducing pre-main time, lazy initialization, deferred work, minimizing dynamic frameworks |
| 3 | [RunLoop & Runtime](runloop-runtime.md) | RunLoop anatomy, modes, sources, observers, main thread scheduling, event processing |

## 3. App Launch Phases

```
dyld load
├── Map __TEXT segment (read-only, shared, no cost)
├── Map __DATA segment (copy-on-write, dirty memory)
├── Rebase (ASLR pointer fixups)
├── Bind (symbol lookups across dylibs)
├── ObjC runtime registration (+load, categories)
└── C++ static initialisers (__attribute__((constructor)))

main()
└── UIApplicationMain / @main
    ├── AppDelegate.didFinishLaunchingWithOptions
    │   ├── Third-party SDK setup (Firebase, Crashlytics...)
    │   ├── URLSession / networking setup
    │   └── Root VC installation
    └── First CATransaction commit → first frame rendered

Warm launch (subsequent launches):
└── Most dylibs and __TEXT already in page cache
    └── Typically 2–3× faster than cold launch
```

## 4. Launch Time Budget

| Phase | Target |
|-------|--------|
| Pre-main (dyld + `+load`) | < 100 ms |
| `didFinishLaunchingWithOptions` | < 100 ms |
| First frame rendered | < 400 ms total (cold) |
| Watchdog kill threshold | ~20 seconds (background launch) |

## 5. Related Topics

- [Performance — Instruments](../12-performance/instruments-profiling.md) — App Launch Instruments template
- [Dependency Management — Static vs Dynamic](../10-dependency-management/static-dynamic-frameworks.md) — dylib count and startup time
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — `didFinishLaunchingWithOptions` and scene setup
- [Concurrency — async/await](../03-concurrency/async-await.md) — async launch work
