# Monitoring

## 1. Overview

Monitoring answers the question "how is the app performing for real users?" — not just "did it crash?" but "how fast does it launch for P95 users?", "what percentage complete the purchase funnel?", "which feature flag variant has better retention?". iOS monitoring spans three domains: **analytics** (discrete user events and conversion funnels — `user_tapped_buy`, `purchase_completed`), **performance metrics** (MetricKit's field-collected launch time, scroll hitch rate, hang rate, memory termination counts), and **feature flags / A/B testing** (controlled exposure of new behaviour to a percentage of users, with outcome metrics). Together these provide the data needed to make informed product, performance, and engineering decisions. The key discipline: instrument intentionally — only track events you will act on, and attach enough context to make the event actionable.

## 2. Simple Explanation

Analytics is the store's sales ledger — every time a customer buys something, the cashier records it. You can count total sales, identify which items are most popular, and trace which customer path leads to purchase. Performance metrics are the store's maintenance report — temperature, equipment uptime, customer wait time. Feature flags are the store's test-and-learn board — for the next two weeks, 50% of customers get the new checkout layout; you measure which group has better conversion before rolling it out to everyone. Together they tell you: what are customers doing, how well is the store running, and which changes should you keep?

## 3. Deep iOS Knowledge

### Analytics Events

An analytics event has three parts:
- **Name**: a concise snake_case string (`"feed_post_tapped"`, `"purchase_completed"`).
- **Properties**: a key-value dictionary with context (`"post_id": "abc"`, `"category": "tech"`).
- **Identity context**: user ID (hashed), session ID, app version, OS version — attached by the SDK automatically.

Best practices:
- Use a **tracking plan** (a spreadsheet or doc) that defines every event, its properties, and the owner. This prevents naming drift.
- Prefer **noun-verb naming**: `<object>_<action>` — `post_viewed`, `comment_submitted`, `payment_failed`.
- Log **funnels** end-to-end: `checkout_started → payment_details_entered → purchase_completed` (or `purchase_failed`). Drop-off between steps identifies friction.

### Funnel Analysis

A funnel tracks a sequence of steps and measures the conversion rate between each. Example purchase funnel:

| Step | Event | Users | Conversion |
|------|-------|-------|-----------|
| 1 | `cart_viewed` | 10,000 | 100% |
| 2 | `checkout_started` | 7,000 | 70% |
| 3 | `payment_details_entered` | 5,000 | 71% |
| 4 | `purchase_completed` | 3,500 | 70% |
| 4b | `purchase_failed` | 500 | 5% |

The 30% drop from cart_viewed to checkout_started is the biggest opportunity — investigate what users do instead (do they go to product detail? Compare alternatives?).

### MetricKit Performance Metrics

`MXMetricPayload` (delivered daily) contains production performance data aggregated across real user sessions:

| Metric | `MXMetricPayload` property |
|--------|--------------------------|
| Launch time (histogram) | `applicationLaunchMetrics.histogrammedTimeToFirstDraw` |
| Scroll hitch rate | `animationMetrics.scrollHitchTimeRatio` |
| Hang rate | `applicationResponsivenessMetrics.histogrammedAppHangTime` |
| Memory (peak) | `memoryMetrics.peakMemoryUsage` |
| CPU time | `cpuMetrics.cumulativeCPUTime` |
| Battery drain | `cellularConditionMetrics`, `displayMetrics` |
| Disk writes | `diskIOMetrics.cumulativeLogicalWrites` |

### Feature Flags

A feature flag is a boolean (or enum) value controlled by a remote configuration system that determines whether a code path is enabled. Flags enable:
- **Safe rollouts**: enable for 1% → 10% → 50% → 100% of users, monitoring metrics at each stage.
- **A/B testing**: randomly assign users to control/treatment, measure outcome metric (conversion, retention).
- **Kill switches**: disable a feature instantly in production without a release.
- **Beta access**: enable for internal users or beta testers only.

Popular iOS flag platforms: LaunchDarkly, Statsig, Optimizely, Firebase Remote Config (simpler, no assignment guarantee).

### Remote Config

Remote Config (Firebase, AWS AppConfig) allows non-flag configuration values to be changed without a release: API endpoint URLs, feature string copy, threshold values, image URLs. Combined with `UserDefaults` caching, fetched values persist across launches if the remote fetch fails.

### Alerting

Set automated alerts on key metrics:
- Crash-free rate drops below 99.5%.
- P99 cold launch time increases by > 200 ms compared to prior version.
- `purchase_completed` event count drops by > 10% in a rolling hour.
- Scroll hitch rate > 5% (from MetricKit).

## 4. Practical Usage

```swift
import Foundation

// ── Analytics event taxonomy ──────────────────────────────────
enum AnalyticsEvent {
    case feedViewed(postCount: Int)
    case postTapped(postID: String, source: String)
    case purchaseStarted(itemID: String, price: Decimal)
    case purchaseCompleted(orderID: String, total: Decimal, method: String)
    case purchaseFailed(reason: String, errorCode: String)
    case featureUsed(featureName: String)

    var name: String {
        switch self {
        case .feedViewed:          return "feed_viewed"
        case .postTapped:          return "post_tapped"
        case .purchaseStarted:     return "purchase_started"
        case .purchaseCompleted:   return "purchase_completed"
        case .purchaseFailed:      return "purchase_failed"
        case .featureUsed:         return "feature_used"
        }
    }

    var properties: [String: Any] {
        switch self {
        case .feedViewed(let count):         return ["post_count": count]
        case .postTapped(let id, let src):   return ["post_id": id, "source": src]
        case .purchaseStarted(let id, let p): return ["item_id": id, "price": p]
        case .purchaseCompleted(let id, let t, let m): return ["order_id": id, "total": t, "method": m]
        case .purchaseFailed(let r, let c):  return ["reason": r, "error_code": c]
        case .featureUsed(let n):            return ["feature_name": n]
        }
    }
}

// ── Analytics service protocol + facade ──────────────────────
protocol AnalyticsService {
    func track(_ event: AnalyticsEvent)
    func identify(userID: String, properties: [String: Any])
}

// Facade: routes events to multiple backends
final class AnalyticsFacade: AnalyticsService {
    private let backends: [AnalyticsService]

    init(backends: [AnalyticsService]) {
        self.backends = backends
    }

    func track(_ event: AnalyticsEvent) {
        backends.forEach { $0.track(event) }
    }

    func identify(userID: String, properties: [String: Any]) {
        backends.forEach { $0.identify(userID: userID, properties: properties) }
    }
}

// ── Feature flags ─────────────────────────────────────────────
protocol FeatureFlagService {
    func isEnabled(_ flag: FeatureFlag) -> Bool
    func variant(for experiment: Experiment) -> String
}

enum FeatureFlag: String {
    case newFeedAlgorithm = "new_feed_algorithm"
    case checkoutRedesign = "checkout_redesign"
    case videoAutoplay = "video_autoplay"
}

enum Experiment: String {
    case checkoutButtonColor = "checkout_button_color"
}

// Simple in-memory implementation (replace with Statsig/LaunchDarkly SDK in production)
final class RemoteFeatureFlags: FeatureFlagService {
    private var flags: [String: Bool] = [:]
    private var variants: [String: String] = [:]
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        loadCachedFlags()
    }

    func isEnabled(_ flag: FeatureFlag) -> Bool {
        flags[flag.rawValue] ?? false
    }

    func variant(for experiment: Experiment) -> String {
        variants[experiment.rawValue] ?? "control"
    }

    // Fetch updated values from remote config (call on app foreground)
    func refresh() async {
        guard let url = URL(string: "https://config.myapp.com/flags") else { return }
        guard let (data, _) = try? await URLSession.shared.data(from: url),
              let decoded = try? JSONDecoder().decode(FlagPayload.self, from: data)
        else { return }
        flags = decoded.flags
        variants = decoded.variants
        cacheFlagsToDisk()
    }

    private struct FlagPayload: Decodable {
        let flags: [String: Bool]
        let variants: [String: String]
    }

    private func loadCachedFlags() {
        if let cached = defaults.data(forKey: "feature_flags"),
           let decoded = try? JSONDecoder().decode(FlagPayload.self, from: cached) {
            flags = decoded.flags; variants = decoded.variants
        }
    }

    private func cacheFlagsToDisk() {
        let payload = FlagPayload(flags: flags, variants: variants)
        if let data = try? JSONEncoder().encode(payload) {
            defaults.set(data, forKey: "feature_flags")
        }
    }
}

// ── MetricKit subscriber ──────────────────────────────────────
import MetricKit

final class PerformanceMonitor: NSObject, MXMetricManagerSubscriber {

    override init() {
        super.init()
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            // Launch time histogram
            if let launch = payload.applicationLaunchMetrics {
                let histogram = launch.histogrammedTimeToFirstDraw
                // Extract P50, P95 from histogram buckets
                logLaunchMetrics(histogram: histogram, version: payload.metaData?.applicationBuildVersion ?? "")
            }

            // Scroll hitch ratio (higher = more janky scrolling)
            if let animation = payload.animationMetrics {
                let hitchRatio = animation.scrollHitchTimeRatio
                // Alert if > 0.05 (5%) — users will notice jank
                if hitchRatio > 0.05 {
                    AnalyticsBackend.track(event: "performance_hitch_alert",
                                           properties: ["hitch_ratio": hitchRatio])
                }
            }

            // Memory terminations (OOM kills)
            if let memory = payload.memoryMetrics {
                let peakMB = memory.peakMemoryUsage.converted(to: .megabytes).value
                AnalyticsBackend.track(event: "memory_peak",
                                       properties: ["peak_mb": peakMB])
            }
        }
    }

    private func logLaunchMetrics(histogram: MXHistogram<UnitDuration>, version: String) {
        var totalCount: Int = 0
        var cumulativeCount: Int = 0
        var p50: Double = 0; var p95: Double = 0
        let enumerator = histogram.bucketEnumerator
        var buckets: [(start: Double, count: Int)] = []
        while let bucket = enumerator.nextObject() as? MXHistogramBucket<UnitDuration> {
            let ms = bucket.bucketStart.converted(to: .milliseconds).value
            buckets.append((ms, bucket.bucketCount))
            totalCount += bucket.bucketCount
        }
        for bucket in buckets {
            cumulativeCount += bucket.count
            if p50 == 0 && Double(cumulativeCount) >= Double(totalCount) * 0.5 { p50 = bucket.start }
            if p95 == 0 && Double(cumulativeCount) >= Double(totalCount) * 0.95 { p95 = bucket.start }
        }
        AnalyticsBackend.track(event: "launch_time",
                               properties: ["p50_ms": p50, "p95_ms": p95, "version": version])
    }
}

// Placeholders:
enum AnalyticsBackend {
    static func track(event: String, properties: [String: Any]) {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between analytics events and performance metrics?**

A: **Analytics events** are discrete user actions or business outcomes: `post_viewed`, `purchase_completed`, `feature_used`. They are high-cardinality, tied to specific moments, and used to understand user behaviour, measure conversion funnels, and make product decisions. **Performance metrics** measure technical quality of the app experience: launch time, frame rate, memory usage, CPU time. MetricKit delivers these as aggregated histograms (not individual events) from the OS across the real user base. The two complement each other: analytics tells you what users are doing and whether they convert; performance metrics tell you how fast and smooth the experience is. A drop in purchase conversion combined with an increase in P95 checkout screen launch time suggests a performance regression is causing users to abandon checkout.

**Q: What is a feature flag and why should you use them instead of release-gating features?**

A: A feature flag is a configuration value (typically boolean) controlled remotely that determines whether a code path executes. Using flags instead of release-gating: (1) **Safe rollout**: deploy the code to 100% of users in production but enable it for only 1% initially. Monitor error rates and performance. Roll out to 10%, 50%, 100% — or roll back instantly by disabling the flag, with no App Store release required. (2) **A/B testing**: randomly assign users to two flag variants, measure the outcome metric (conversion, session length, retention). Ship only the winning variant. (3) **Kill switch**: if a feature causes an incident, disable it remotely for all users in seconds — no emergency release needed. (4) **Targeted access**: enable for internal beta users, specific geographic regions, or specific app versions. Feature flags decouple deployment (when code ships to devices) from release (when users can use the feature).

### Hard

**Q: How do you design a funnel analysis system that handles users abandoning mid-funnel across multiple sessions?**

A: Session-based funnels (steps must occur in the same session) miss users who start a funnel on day 1 and complete it on day 3. Cross-session funnels require: (1) **Persistent funnel state**: when a user completes step 1 (`checkout_started`), store the funnel start event in `UserDefaults` or a lightweight local DB with a timestamp and funnel ID. (2) **Completion window**: define a maximum window (e.g., 7 days) for completing the funnel. If step 2 (`purchase_completed`) occurs within 7 days with the same `userID` and `itemID`, the funnel conversion is recorded. (3) **Server-side attribution**: send all funnel events to the backend with `sessionID`, `userID` (hashed), `funnelID` (a UUID created at step 1), and `timestamp`. The backend joins events by `funnelID` to compute per-user conversion. (4) **Abandonment event**: if the funnel is not completed within the window, generate a `checkout_abandoned` event (triggered on the next app open after the window expires) with the step at which the user stopped — this identifies which step causes the most drop-off.

**Q: How does MetricKit differ from crash reporters like Crashlytics for observability?**

A: Crashlytics and MetricKit measure different things with different timing. **Crashlytics**: real-time, per-crash, report uploaded on next app launch. Provides full stack trace, custom keys/logs, user context. Used for actionable crash investigation — you get notified within minutes, see the exact line that crashed, and can group by version or device. **MetricKit**: batch, aggregated, delivered once per day by the OS. Provides statistical distributions (histograms) of performance metrics across the entire install base — not individual sessions. Covers metrics crash reporters miss: scroll hitch rate, hang rate, CPU/battery usage, OOM terminations (which have no crash report). Used for trend monitoring — you can see that P95 launch time degraded across all users of version 3.2 without needing a crash report from any specific user. Use both: Crashlytics for reactive debugging, MetricKit for proactive performance trend monitoring.

### Expert

**Q: Design a server-side feature flag system with client-side caching that works correctly offline and handles flag updates without requiring an app release.**

A: Five-component architecture: (1) **Remote source of truth**: a feature flag service (Statsig/LaunchDarkly or custom) stores flag definitions and user assignment rules. Flags have: `key`, `enabled` (global toggle), `percentage` (0–100 rollout), `targeting` (rules: userID hash, device type, app version, location). (2) **Client-side SDK**: the iOS SDK fetches the flag payload at app foreground (max once per 30 minutes) from the flags endpoint. The payload is a signed JSON document containing the evaluated flag values for this user (not the rules — the server evaluates rules and sends only the result). The signature is verified on device using a public key compiled into the binary. (3) **Persistent cache**: the fetched payload is stored in `UserDefaults` as `Codable` with a `fetchedAt` timestamp. On app launch, the cache is loaded synchronously — no network wait required. The cached payload is used for the entire session. (4) **Offline behaviour**: if the network fetch fails, the cached payload from the previous session is used. If no cache exists (first launch offline), all flags default to their `defaultValue` (specified in the local flag definition). This ensures the app behaves predictably offline. (5) **Assignment stability**: once a user is assigned to a variant (e.g., "treatment" for the checkout experiment), the assignment persists for the experiment's duration even if the percentage changes — the assignment is recorded server-side and returned in the payload regardless of the current rollout percentage.

## 6. Common Issues & Solutions

**Issue: Analytics events have inconsistent naming across different teams (some use camelCase, some use snake_case, some omit properties).**

Solution: Implement a **tracking plan** — a shared document (Notion, Airtable) or code-level `enum AnalyticsEvent` with associated values that defines every event, its properties, and which team owns it. Make the analytics facade accept only the typed `AnalyticsEvent` enum (not raw strings). New events require adding a case to the enum — this surfaces the naming decision at code review time. Run a linter in CI that checks for events in the tracking plan not present in the enum, and vice versa.

**Issue: Feature flags are fetched at launch but users see stale values for a long time during an active session.**

Solution: Balance staleness vs network calls: (1) Refresh flags on `applicationDidBecomeActive` (every foreground) with a minimum interval (e.g., skip if last fetch was < 5 minutes ago). (2) For kill-switch flags (used to disable a broken feature), check the flag value on every use — do not cache it per-session. (3) Use Server-Sent Events or WebSocket for near-real-time flag updates in high-stakes scenarios (financial apps, game events). (4) For A/B test flags, session-level caching is acceptable and expected — changing a user's variant mid-session would cause inconsistent UI.

## 7. Related Topics

- [Crash Reporting](crash-reporting.md) — complementary to performance monitoring
- [Logging](logging.md) — structured logs feed into monitoring pipelines
- [Performance — Instruments](../12-performance/instruments-profiling.md) — development-time performance monitoring
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — foreground/background hooks for flag refresh
