# Startup Optimization

## 1. Overview

Startup optimization on iOS requires understanding both pre-main (dyld) and post-main (AppDelegate) phases, then applying the right technique to each bottleneck. The overarching strategy is: **do less** (eliminate unnecessary setup entirely), **do it later** (defer non-critical work past the first frame), and **do it faster** (use static linking, reduce class registration, pre-compute what can be cached). Apple's App Launch Instruments template measures cold launch end-to-end. MetricKit's `MXAppLaunchMetric` provides field data across the entire install base — a median cold launch time above 500 ms indicates a systemic problem. The key techniques are: converting dynamic frameworks to static, eliminating `+load` methods, deferring third-party SDK initialization, lazy-initializing expensive services, using `async` launch work that completes after the first frame, and caching first-launch compute results in `UserDefaults` or on disk.

## 2. Simple Explanation

Optimizing app startup is like streamlining a restaurant's pre-opening checklist. The current checklist takes 90 minutes: 40 minutes restocking the entire bar (initializing analytics SDKs for features the user hasn't touched yet), 30 minutes re-reading the entire menu aloud (loading unnecessary Storyboards), and 20 minutes reorganizing the wine cellar (ObjC runtime category attachment). The optimized version: open the restaurant in 5 minutes with just the essentials (crash reporter, root view controller), and have the sommelier restock the bar during the first lull (defer SDK setup to a background task). The customer sits down immediately and is served — the background work completes without anyone noticing.

## 3. Deep iOS Knowledge

### Strategy 1: Reduce Dynamic Framework Count

Each dynamic framework (`.framework` with a Mach-O dylib inside) costs 1–5 ms to load at launch, independent of its size, because dyld must: open the file, verify the code signature, map `__TEXT` and `__DATA`, apply rebasing, and perform binding. The system framework dylib cache (UIKit, Foundation, etc.) is pre-linked — those are free. Your third-party and internal dynamic frameworks are not.

Audit: `otool -L YourApp.app/YourApp | grep @rpath`

Target: ≤ 6 non-system dynamic frameworks. Convert internal frameworks to SPM static libraries:

```swift
// In Package.swift — force static linking
.library(name: "FeatureKit", type: .static, targets: ["FeatureKit"])
```

For CocoaPods: `use_frameworks! :linkage => :static` in the Podfile.

### Strategy 2: Eliminate `+load` Methods

Every `+load` runs synchronously before `main()`. Find all `+load` implementations:
```bash
grep -rn "+load" --include="*.m" .
```

Replace with `+initialize` (lazy) or explicit calls in `didFinishLaunchingWithOptions`.

For method swizzling (common use of `+load`), call the swizzle from `application(_:didFinishLaunchingWithOptions:)`:

```swift
func application(_ application: UIApplication,
                 didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    // Swizzle here instead of in +load
    UIViewController.swizzleViewDidAppear()
    return true
}
```

### Strategy 3: Defer Non-Critical SDK Initialization

Third-party SDKs (analytics, A/B testing, feature flags, ML model loading) do not need to be ready before the first frame. Defer them:

```swift
// Critical path — must complete before first frame
func application(_ app: UIApplication, ...) -> Bool {
    CrashReporter.start()          // must catch early crashes
    installRootViewController()    // must show UI
    return true
}

// Deferred — starts after first frame is rendered
func applicationDidBecomeActive(_ application: UIApplication) {
    Task.detached(priority: .utility) {
        await AnalyticsSDK.configure()
        await ABTestingSDK.fetchExperiments()
        await RemoteConfig.fetch()
    }
}
```

### Strategy 4: Lazy-Initialize Expensive Services

Services not needed until user action should initialize on first use:

```swift
final class ServiceContainer {
    // Lazy — created only if the user opens the camera
    lazy var cameraService = CameraService()
    // Lazy — created only if the user signs in
    lazy var authenticationManager = AuthenticationManager()
}
```

For singletons that initialize slowly: use a background `Task` to pre-warm them after launch, so by the time the user navigates to a feature, the service is ready:

```swift
// After first frame:
Task.detached(priority: .background) {
    _ = await DatabaseService.shared.preWarm()   // open SQLite, run migrations
}
```

### Strategy 5: Reduce ObjC Class Registration

Each ObjC class takes a small amount of time during the ObjC setup phase. Apps with thousands of ObjC classes (common when using large ObjC-based SDKs) can spend 50+ ms in ObjC setup. Strategies:
- Write new code in Swift (Swift types are not ObjC classes unless annotated).
- Audit large ObjC frameworks; prefer Swift replacements where available.
- Use `@_objcImplementation` in Swift to avoid duplicate ObjC/Swift registration.

### Strategy 6: Cache First-Run Work

Some initialization work is unavoidable on first launch but can be cached for subsequent launches. Examples:
- JSON configuration files: parse once, store the decoded struct in `UserDefaults` (via `Codable`).
- Database migrations: track schema version; don't re-run completed migrations.
- Asset catalog pre-rendering: render complex composite assets once and cache to disk.

```swift
struct CachedConfig: Codable {
    let featureFlags: [String: Bool]
    let builtAt: Date
}

func loadConfig() -> CachedConfig {
    if let cached = try? UserDefaults.standard.codable(CachedConfig.self, forKey: "cachedConfig"),
       cached.builtAt > Date().addingTimeInterval(-3600) {
        return cached   // use cache if < 1 hour old
    }
    let fresh = buildConfig()
    try? UserDefaults.standard.setCodable(fresh, forKey: "cachedConfig")
    return fresh
}
```

### Strategy 7: Optimize First View Controller

The root view controller's `viewDidLoad` runs on the critical path to first frame. Common issues:
- Large nib/storyboard deserialization.
- Synchronous database read for initial data.
- Creating all subviews upfront instead of using lazy loading.

Optimizations:
- Use a lightweight "splash" VC as root (just an image), then async-replace with the real root VC after data loads.
- Defer non-visible subview creation with `lazy var`.
- Load initial data with `async/await` and show a skeleton while loading.

### Measuring with MetricKit

```swift
import MetricKit

final class LaunchMetrics: NSObject, MXMetricManagerSubscriber {
    override init() {
        super.init()
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            if let launch = payload.applicationLaunchMetrics {
                // histogrammedTimeToFirstDraw: cold launch distribution
                let buckets = launch.histogrammedTimeToFirstDraw.bucketEnumerator
                // log p50, p90, p99 to your analytics backend
            }
        }
    }
}
```

## 4. Practical Usage

```swift
import UIKit

// ── Optimized AppDelegate — minimal critical path ──────────────
@UIApplicationMain
final class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?
    private var launchStart: CFAbsoluteTime = 0

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        launchStart = CFAbsoluteTimeGetCurrent()

        // ── 1. Critical setup only ─────────────────────────────
        setupCrashReporter()       // ← must be first, catches early crashes
        setupRootViewController()  // ← shows UI immediately

        // ── 2. Defer everything else ──────────────────────────
        schedulePostLaunchWork()

        return true
    }

    // Called after the app is visible and responsive
    func applicationDidBecomeActive(_ application: UIApplication) {
        let elapsed = CFAbsoluteTimeGetCurrent() - launchStart
        MetricsLogger.record(event: "cold_launch", duration: elapsed)
    }

    // ── Critical setup helpers ─────────────────────────────────
    private func setupCrashReporter() {
        // Fast — registers a signal handler, no network call
        CrashReporter.install()
    }

    private func setupRootViewController() {
        window = UIWindow(frame: UIScreen.main.bounds)
        // Lightweight root — shows immediately, real content loads async
        window?.rootViewController = SplashViewController()
        window?.makeKeyAndVisible()
    }

    // ── Deferred work — runs after first frame ─────────────────
    private func schedulePostLaunchWork() {
        Task.detached(priority: .utility) {
            // These run concurrently on the cooperative thread pool
            async let _ = AnalyticsService.shared.configure()
            async let _ = ABTestingService.shared.fetchExperiments()
            async let _ = RemoteConfigService.shared.fetch()
            // After all three complete, notify root VC to transition to main content
            await MainActor.run {
                NotificationCenter.default.post(name: .postLaunchSetupComplete, object: nil)
            }
        }
    }
}

// ── SplashViewController — minimal first frame ─────────────────
final class SplashViewController: UIViewController {
    private let logoImageView = UIImageView(image: UIImage(named: "AppLogo"))

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        view.addSubview(logoImageView)
        logoImageView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            logoImageView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            logoImageView.centerYAnchor.constraint(equalTo: view.centerYAnchor)
        ])
        // Listen for deferred setup completion
        NotificationCenter.default.addObserver(
            self, selector: #selector(transitionToMain),
            name: .postLaunchSetupComplete, object: nil
        )
    }

    @objc private func transitionToMain() {
        // Transition to main content after deferred setup
        let mainVC = FeedViewController()
        UIView.transition(
            with: view.window!,
            duration: 0.3,
            options: .transitionCrossDissolve
        ) {
            self.view.window?.rootViewController = mainVC
        }
    }
}

// ── Method swizzling at the right time (not in +load) ─────────
extension UIViewController {
    static func swizzleViewDidAppear() {
        let original = #selector(UIViewController.viewDidAppear(_:))
        let swizzled = #selector(UIViewController.swizzled_viewDidAppear(_:))
        guard let originalMethod = class_getInstanceMethod(UIViewController.self, original),
              let swizzledMethod = class_getInstanceMethod(UIViewController.self, swizzled)
        else { return }
        method_exchangeImplementations(originalMethod, swizzledMethod)
    }

    @objc private func swizzled_viewDidAppear(_ animated: Bool) {
        swizzled_viewDidAppear(animated)   // calls original (swapped)
        AnalyticsService.shared.logScreenView(type(of: self))
    }
}

extension Notification.Name {
    static let postLaunchSetupComplete = Notification.Name("postLaunchSetupComplete")
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the most impactful single change you can make to reduce iOS app launch time?**

A: For most apps with multiple third-party SDKs, the highest-impact change is **deferring non-critical SDK initialization past the first frame**. Analytics SDKs (Firebase Analytics, Amplitude), A/B testing frameworks (Optimizely, Statsig), and marketing SDKs (AppsFlyer, Adjust) each take 10–100 ms to initialize, and none of them need to be ready before the user sees the first screen. Moving them from `didFinishLaunchingWithOptions` to `applicationDidBecomeActive` (or a `Task.detached` started from `didFinishLaunching`) eliminates their contribution to launch time entirely. The second most impactful change for apps with many internal dynamic frameworks is converting them to static libraries, reducing dylib loading time.

**Q: How does converting a dynamic framework to a static library improve launch time?**

A: Each dynamic framework requires `dyld` to: open the `.dylib` file, verify its code signature, map its segments into the process, apply rebase fixups, and resolve bound symbols. This overhead is roughly 1–5 ms per framework, independent of the framework's code size. A static library, in contrast, is linked directly into the app binary at build time — it becomes part of the main Mach-O binary's `__TEXT` segment and has zero per-library dyld overhead at launch. The tradeoff: static libraries increase the app binary size slightly (no deduplication across apps on disk), but this rarely matters. The startup win is real and measurable, especially for apps with 10+ internal frameworks.

### Hard

**Q: How do you defer database migration to not block the first frame, while ensuring the app doesn't show stale data?**

A: Three-step approach: (1) **Version check before migration**: on launch, read the stored schema version from `UserDefaults`. If it matches the current version, the migration is not needed — proceed directly to the root VC with the current data. (2) **Migration on a blocking splash**: if migration is needed, show a splash/loading screen on the main thread, then perform the migration on a `Task.detached`. The splash screen prevents the user from interacting with stale data while the migration runs. Show a progress indicator for long migrations. (3) **Async-replace root VC**: after migration completes, `await MainActor.run { replaceRootVC(with: mainFeedVC) }`. This keeps the main thread free during the migration (no frame drops) while guaranteeing the user never sees the app with an incompatible schema. For zero-migration launches (the common case), the migration check is a single `UserDefaults` read — effectively free.

**Q: How do you prevent `+load` methods in third-party Objective-C libraries from slowing your app's launch?**

A: You can't prevent third-party `+load` methods from running — they are called by the ObjC runtime before `main()` and you have no hook to intercept them. Your options: (1) **Profile first**: use `DYLD_PRINT_STATISTICS_DETAILS=1` to identify which library's initializers are slow. (2) **Convert to static linking**: a static library's `+load` methods still run, but eliminating a dynamic framework removes its dylib loading overhead. The initializer time may remain. (3) **Replace the SDK**: if the SDK's initializer is unacceptably slow and no deferred-init API exists, evaluate alternatives. (4) **Binary frameworks**: some SDKs offer XCFramework builds that are pre-optimized — check whether a newer version has improved launch performance. (5) **Conditional linking**: if the SDK is only needed in some build variants (e.g., internal testing SDKs), exclude it from release builds using build configuration conditionals.

### Expert

**Q: How would you structure a large iOS app with 15 feature teams so that each team can build their module independently without increasing app launch time?**

A: Modular architecture with static-by-default linking: (1) **Module structure**: each feature team owns an SPM package with `type: .static` libraries. Features are only code — no `+load`, no global state initializers. Each feature registers itself with a central `FeatureRegistry` via a declarative registration (a struct conforming to `Feature` protocol), not a `+load`. (2) **Registration without `+load`**: use a code-generation step (build plugin) that generates a `registerAllFeatures()` function listing every feature. This function is called once in `AppDelegate`, not at binary load time. (3) **Lazy feature initialization**: each feature's heavy setup (its view hierarchy, its services) is created only when the user navigates to that feature. The app-level `FeatureRegistry` maps routes to feature builders; the builder creates the VC on demand. (4) **Launch-critical module only**: the launch-critical module (splash screen, authentication, root tab bar) is kept minimal and independently buildable. Changing a feature team's module does not require relinking or re-profiling the launch-critical module. (5) **CI launch budget**: a CI job runs the App Launch Instruments template on every merge to `main`. If the cold launch P90 increases by more than 20 ms compared to the baseline, the merge is rejected. This prevents teams from inadvertently adding `+load` or heavy initializers.

## 6. Common Issues & Solutions

**Issue: Launch time improved in development but is slow in production (App Store builds).**

Solution: App Store builds include additional steps not present in local Release builds: app thinning (bitcode/asset catalog slicing), entitlement embedding, and App Store receipt validation. These can add a few hundred ms to the first-ever cold launch after install. Additionally, the dyld launch closure is always cold on first install — this is unavoidable. Profile the App Store build on a clean device using TestFlight + Instruments to get production-representative measurements.

**Issue: Deferring SDK setup to `applicationDidBecomeActive` causes the SDK to fire setup on every foreground (e.g., after a phone call).**

Solution: Add a `hasConfiguredSDKs` flag: `private var hasPerformedPostLaunchSetup = false`. In `applicationDidBecomeActive`, guard with `guard !hasPerformedPostLaunchSetup else { return }`, then set the flag before calling setup. This ensures setup runs exactly once — on the first foreground after launch.

**Issue: The app shows a blank white screen for 300 ms before the root view controller appears.**

Solution: The white flash is the default window background before the root VC's view is installed. Fix: set `window.backgroundColor = UIColor.systemBackground` (or your app's launch screen background colour) immediately after creating the window, before `makeKeyAndVisible`. Also ensure the LaunchScreen storyboard background colour matches the root VC's background — a mismatch is visible as a colour flash during the transition.

## 7. Related Topics

- [App Launch Process](app-launch-process.md) — pre-main phases to understand what to optimize
- [RunLoop & Runtime](runloop-runtime.md) — post-launch scheduling
- [Static Libraries & Dynamic Frameworks](../10-dependency-management/static-dynamic-frameworks.md) — static vs dynamic linking tradeoffs
- [Lazy Loading](../12-performance/lazy-loading.md) — lazy initialization patterns
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — `didFinishLaunchingWithOptions` timing
