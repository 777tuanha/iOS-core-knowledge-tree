# App Launch Process

## 1. Overview

When a user taps an iOS app icon, the OS creates a new process, maps the app's Mach-O binary into memory, and hands control to `dyld` — Apple's dynamic linker. `dyld` handles the entire pre-`main()` phase: mapping the `__TEXT` segment (the code pages, shared across processes, never dirty), applying ASLR rebasing to the `__DATA` segment, binding cross-dylib symbol references (ObjC selectors, Swift protocol witnesses, C function pointers), running Objective-C runtime registration (`+load`, category attachment), and executing C++ static initializers. Only after all of this does `main()` run, which calls `UIApplicationMain`, which triggers `AppDelegate.didFinishLaunchingWithOptions`, which installs the root view controller, which finally commits the first `CATransaction` to produce the first visible frame. Understanding each phase is essential for diagnosing slow cold-launch times and for knowing where optimization efforts will have the most impact.

## 2. Simple Explanation

Launching an app is like opening a new restaurant. Before the first customer can eat (first rendered frame): the health inspector checks the building (dyld verifies code signatures), suppliers deliver stock and set up the kitchen (dynamic libraries are mapped and linked), the kitchen staff learn today's menu (`+load` and static initializers run), and the manager unlocks the front door and seats the first customer (`AppDelegate.didFinishLaunching` runs and installs the root VC). The faster you can complete the pre-opening work, the sooner the first customer is served. The big wins come from reducing the kitchen setup time (`+load` work and static initializers) and reducing the number of suppliers making deliveries (dynamic framework count).

## 3. Deep iOS Knowledge

### dyld 3 and dyld 4

Modern iOS uses **dyld 4** (introduced iOS 16) and the **dyld shared cache** — all system frameworks (`UIKit`, `Foundation`, `SwiftUI`) are pre-linked into a single shared cache file on disk, loaded read-only. This means system framework linking cost is essentially zero at launch. The remaining cost is resolving your app's own dylibs and any third-party dynamic frameworks.

**dyld closure / launch closure**: dyld pre-computes a "closure" (a binary description of all bindings for a given app binary) and caches it. The closure is invalidated whenever the app binary changes (e.g., after an update). The first cold launch after install or update is slower because the closure must be rebuilt.

### Pre-main Phases in Detail

**1. Mach-O loading**
The kernel maps the app binary's `__TEXT` segment (executable code) as read-only and the `__DATA` segment (globals, pointers) as copy-on-write. `__TEXT` is shared across processes — if two apps use the same dylib, they share the same physical pages for `__TEXT`.

**2. Rebasing**
ASLR (Address Space Layout Randomization) places the binary at a random base address each launch. All absolute pointers in `__DATA` must be adjusted by the slide value — this is "rebasing." Minimizing the size of `__DATA` (fewer global objects, fewer indirection levels) reduces rebase time.

**3. Binding**
Symbol references that cross dylib boundaries (e.g., your app calling `UIViewController` from UIKit) are resolved: dyld looks up each symbol in the target dylib's export trie and writes the resolved address into your `__DATA` section. Fewer dynamic frameworks = fewer bindings = faster launch.

**4. ObjC Runtime**
The ObjC runtime scans all `__objc_classlist`, `__objc_catlist`, and `__objc_protolist` sections:
- Registers each class.
- Attaches categories to their target classes.
- Calls `+load` on every class and category that implements it.

**`+load` is dangerous for launch performance**: it runs synchronously in the pre-main phase, on the main thread, under a global lock. Any work in `+load` — including `dispatch_once`, lock contention, file I/O — blocks all other initialization. Even 1 ms per `+load` method × 100 methods = 100 ms of blocked startup. Replace `+load` with `+initialize` (called lazily on first message send to the class) or with explicit setup in `application(_:didFinishLaunchingWithOptions:)`.

**5. C++ Static Initializers**
Functions marked `__attribute__((constructor))` and constructors of global C++ objects run here. These are common in C++ libraries embedded via SPM or CocoaPods. Profile with `DYLD_PRINT_STATISTICS=1` to see time spent in static initializers.

**6. Swift runtime initialization**
Swift global variables with non-trivial initializers, protocol witness tables, and metadata are registered. Swift's global initializers are lazy by default (unlike C++) — they run on first access, not at binary load time.

### Measuring Pre-main Time

```bash
# Set environment variable in scheme diagnostics
DYLD_PRINT_STATISTICS=1
# Or more detailed:
DYLD_PRINT_STATISTICS_DETAILS=1
```

Instruments: **App Launch** template — shows the full pre-main + post-main timeline with the frame budget overlaid.

Sample `DYLD_PRINT_STATISTICS` output:
```
Total pre-main time: 248.32 milliseconds (100.0%)
         dylib loading time:  84.20 milliseconds (33.9%)
        rebase/binding time:  12.11 milliseconds (4.9%)
            ObjC setup time:  42.83 milliseconds (17.2%)
           initializer time: 109.18 milliseconds (44.0%)
           slowest intializers:
             libSystem.B.dylib :   3.31 milliseconds (1.3%)
               libglInterpose.dylib :  40.22 milliseconds (16.2%)
                     MyApp :  65.71 milliseconds (26.5%)
```

### Initial View Controller Setup

In Storyboard-based apps: the Storyboard's initial view controller is instantiated from the nib archive — `initWithCoder:` runs, then `viewDidLoad` on the first VC. The Storyboard XML is parsed and all scene objects are deserialized.

In code-only apps: the window and root VC are created programmatically in `didFinishLaunchingWithOptions` or `scene(_:willConnectTo:options:)`. This is faster (no XML parse) but requires more boilerplate.

### Cold vs Warm vs Hot Launch

| Type | Cause | Cost |
|------|-------|------|
| Cold | App not in memory, page cache empty | Highest (full dyld + IO) |
| Warm | App not in memory, page cache warm | Medium (no IO, dyld still runs) |
| Hot | App suspended in memory | Near-zero (process resume) |

Instruments' App Launch template measures **cold launch**. To force a cold launch: reboot the device, then launch once (to warm the page cache), then reboot again and test.

## 4. Practical Usage

```swift
// ── Dangerous: work in +load ───────────────────────────────────
// DO NOT DO THIS — runs synchronously before main(), holds a global lock
@objc class BadSetup: NSObject {
    override class func load() {
        // Anything here blocks launch
        URLSession.shared.dataTask(with: URL(string: "https://config.api")!) { _, _, _ in }.resume()
    }
}

// ── Better: +initialize (lazy, called on first use) ────────────
@objc class GoodSetup: NSObject {
    override class func initialize() {
        super.initialize()
        // Called only when GoodSetup is first messaged — not at launch
        // Still on main thread, so keep it short
    }
}

// ── Best: explicit setup in AppDelegate ───────────────────────
@main
final class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Only setup needed before first frame — keep < 100ms total

        // Critical: configure crash reporter first (needs to catch early crashes)
        CrashReporter.configure()

        // Deferred setup — not needed for first frame
        Task.detached(priority: .utility) {
            await AnalyticsService.shared.configure()
            await RemoteConfig.shared.fetch()
        }

        return true
    }
}

// ── Measuring launch time from main() ─────────────────────────
// In main.swift (or @main struct):
let launchStart = Date()

// In viewDidAppear of the first visible VC:
override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
    if let start = AppDelegate.launchStart {
        let elapsed = Date().timeIntervalSince(start)
        MetricsLogger.log("app_launch_time", value: elapsed)
        AppDelegate.launchStart = nil  // log only once
    }
}

// ── Checking dylib count in your binary ───────────────────────
// Terminal: otool -L /path/to/YourApp.app/YourApp
// Each @rpath/Something.framework line = one dynamic framework to load
// Target: < 6 dynamic frameworks (excluding system cache)

// ── Deferring Storyboard-heavy flows ──────────────────────────
// The onboarding flow is only needed for new users — don't instantiate it at launch
final class RootRouter {
    func makeRootViewController(for user: User?) -> UIViewController {
        if let user {
            // Returning user — instantiate feed directly (fast, no storyboard parse)
            return FeedViewController(user: user)
        } else {
            // New user — onboarding storyboard is loaded lazily here, not at app start
            return UIStoryboard(name: "Onboarding", bundle: nil)
                .instantiateInitialViewController()!
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is `dyld` and what does it do during app launch?**

A: `dyld` (the dynamic linker/loader) is the first code that runs in an iOS app process before `main()`. It is responsible for: (1) **Loading dylibs** — mapping the app binary and all dependent dynamic libraries (frameworks) into the process's virtual address space; (2) **Rebasing** — adjusting all absolute pointers in `__DATA` segments because ASLR places binaries at random base addresses each launch; (3) **Binding** — resolving cross-dylib symbol references (e.g., calls from your app to UIKit functions) by looking up addresses in exported symbol tables; (4) **ObjC setup** — registering all classes, attaching categories, and calling `+load` methods; (5) **C++ static initializers** — running `__attribute__((constructor))` functions and global C++ object constructors. Only after all of this completes does `main()` run.

**Q: What is the difference between `+load` and `+initialize` in Objective-C, and why does it matter for launch performance?**

A: `+load` is called on every class and category that implements it, **at dyld initialization time**, before `main()` runs, synchronously on the main thread, while holding a global ObjC runtime lock. All `+load` methods across all frameworks run before the app starts. `+initialize` is called lazily — the first time a message is sent to the class (or a subclass). Implications for launch: `+load` methods add directly to pre-main time and can cause deadlocks if they acquire locks that interact with the global runtime lock. `+initialize` amortises the cost to when the class is first used. Rule: avoid `+load` entirely in app code; use `+initialize` for lightweight class-level setup, and `application(_:didFinishLaunchingWithOptions:)` for everything else.

### Hard

**Q: How do you measure and reduce the pre-main launch time of an iOS app?**

A: Measurement: set `DYLD_PRINT_STATISTICS=1` in the scheme's environment variables (or `DYLD_PRINT_STATISTICS_DETAILS=1` for a per-initializer breakdown). This prints the time breakdown: dylib loading, rebase/binding, ObjC setup, and C++ initializer time, with the slowest initializers named. Use Instruments' App Launch template for a visual timeline. Reduction: (1) **Reduce dynamic framework count** — every `@rpath` framework in `otool -L` output adds ~1–5 ms of dylib loading. Convert rarely-changed internal frameworks to static libraries (SPM `type: .static`). (2) **Eliminate `+load`** — find all `+load` implementations with `grep -r "+load" --include="*.m"` or Xcode's call hierarchy. Replace with `+initialize` or explicit `didFinishLaunchingWithOptions` calls. (3) **Reduce C++ static initializers** — C++ libraries (e.g., OpenSSL, Realm, some analytics SDKs) have global constructors. Use `nm -m binary | grep "__ZN"` to list C++ symbols. Profile the initializer time in `DYLD_PRINT_STATISTICS_DETAILS`. (4) **Reduce ObjC class count** — thousands of registered classes slow down category attachment. Prefer Swift types for new code.

**Q: What is the dyld launch closure and when is it invalidated?**

A: The dyld launch closure is a pre-computed binary record that describes all the work dyld needs to do for a specific app binary: which dylibs to load, all rebase/bind operations, ObjC class registrations. dyld builds this closure on the first cold launch (or after an app update) and caches it, making subsequent launches faster — the closure replaces the full symbol-resolution work with a compact, pre-computed record. The closure is invalidated whenever the app binary changes (after an App Store update or TestFlight build install), when any of the dependent dylibs change (an OS update), or when the device reboots (the cache is in a volatile region). This is why the first launch after an app update is slower — the closure is rebuilt. You cannot control closure invalidation, but you can reduce its rebuild cost by having fewer dylibs and fewer ObjC classes.

### Expert

**Q: Design a launch time optimization strategy for an app that currently takes 1.8 seconds to reach the first frame on a cold launch.**

A: Systematic four-phase approach: (1) **Profile first**: run Instruments App Launch template on a physical device (never simulator) with a Release build. Identify whether the bottleneck is pre-main (dyld) or post-main (AppDelegate setup). The App Launch template shows a flame graph with a 400 ms reference line. (2) **Pre-main reduction**: if dylib loading dominates, use `otool -L` to audit dynamic frameworks. Convert non-SDK internal frameworks to SPM static targets. If initializer time dominates, use `DYLD_PRINT_STATISTICS_DETAILS=1` to identify the slow initializer and eliminate or defer it. Target < 100 ms pre-main. (3) **AppDelegate triage**: in `didFinishLaunchingWithOptions`, log the duration of each setup call. Any call > 5 ms is a candidate for deferral. Move non-critical setup (analytics configuration, remote config fetch, A/B test loading, image cache warm-up) into a `Task.detached(priority: .utility)` started from `didFinishLaunching`. The task runs after the first frame is displayed — the user sees a responsive UI immediately. (4) **View hierarchy optimization**: if the first VC's `viewDidLoad` is slow (Storyboard parse, heavy layout), switch to programmatic UI, defer subview creation with `lazy var`, and use skeleton screens while data loads asynchronously. Iterate with Instruments after each change; target < 400 ms total cold launch and < 200 ms warm launch.

## 6. Common Issues & Solutions

**Issue: App is killed by the watchdog during launch with a crash log showing `0x8badf00d` exception code.**

Solution: `0x8badf00d` ("ate bad food") is the watchdog kill code — the app took too long on the main thread during launch or state transition (the limit is ~20 seconds for launch). Look in the crash log for the main thread backtraces showing which function was blocking. Common causes: synchronous network call in `didFinishLaunchingWithOptions`, blocking wait for a serial queue from the main thread, or a deadlock in a third-party SDK initializer. Move all async work to background threads and ensure `didFinishLaunchingWithOptions` returns quickly.

**Issue: `DYLD_PRINT_STATISTICS` shows initializer time dominated by a third-party SDK.**

Solution: The SDK has C++ global constructors or `+load` methods. Options: (1) Contact the SDK vendor — some SDKs provide a "configure manually" API that defers their initializer. (2) If the SDK is via SPM, check if it can be built as a static library (removes one dylib, but static initializers still run). (3) Wrap the SDK in a lazy-initialized facade: create a singleton that initialises the SDK on first method call rather than at app launch. If the SDK is only used after the user performs a specific action (e.g., plays a video), this defers the cost entirely.

**Issue: Launch time is fast on simulator but slow on device.**

Solution: Simulator uses the host Mac's CPU and memory — it is significantly faster and has no dylib loading overhead (system frameworks are available natively on the Mac). Always measure launch time on a real device using the App Launch Instruments template. Also ensure you're testing a Release build — Debug builds have disabled optimizations and much slower startup.

## 7. Related Topics

- [Startup Optimization](startup-optimization.md) — techniques derived from launch process understanding
- [RunLoop & Runtime](runloop-runtime.md) — what runs after launch
- [Static Libraries & Dynamic Frameworks](../10-dependency-management/static-dynamic-frameworks.md) — dylib count and startup cost
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — `didFinishLaunchingWithOptions` structure
- [Instruments & Profiling](../12-performance/instruments-profiling.md) — App Launch Instruments template
