# Crash Reporting

## 1. Overview

A crash is an unrecoverable error that causes the OS to terminate the app process. On iOS, crashes originate from three sources: **signal-based crashes** (hardware exceptions translated to Unix signals — `EXC_BAD_ACCESS`/`SIGSEGV` for null pointer dereferences or use-after-free; `SIGABRT` for abort calls; `SIGILL` for illegal instruction), **ObjC/Swift runtime exceptions** (`NSException` — unrecognised selector, index out of range, forced unwrap of nil), and **watchdog kills** (the OS terminates the app for exceeding time limits in launch, background execution, or UI responsiveness). A crash report (`.ips` file) contains the exception type, crash address, device info, and the call stack of every thread — but in unsymbolicated form (hexadecimal addresses). **Symbolication** translates those addresses back into function names, file names, and line numbers using the dSYM (debug symbol) file for the exact build. Crashlytics (Firebase), Sentry, and Apple's native crash organizer all provide symbolication and grouping.

## 2. Simple Explanation

A crash report without symbolication is like a map with GPS coordinates but no street names — you know something happened at `0x00000001002a4bc0` but not which function. The dSYM file is the legend that translates those coordinates into addresses like `FeedViewController.loadPosts() line 47`. Without the matching dSYM (exact build, exact UUID), the map is unreadable. Crashlytics uploads the dSYM during your CI build, matches it to incoming crash reports by UUID, and gives you the human-readable stack trace automatically. The same crash occurring 500 times gets grouped into one issue with an "affected users" count — so you know if it's a one-off or a widespread problem.

## 3. Deep iOS Knowledge

### Crash Types

| Exception type | Common cause |
|----------------|-------------|
| `EXC_BAD_ACCESS (SIGSEGV)` | Null pointer dereference, use-after-free, stack overflow |
| `EXC_BAD_ACCESS (SIGBUS)` | Unaligned memory access |
| `SIGABRT` | `fatalError()`, `precondition()`, `assert()` failure, NSException |
| `SIGILL` | Force unwrap of nil (`!` on nil Optional) → Swift runtime trap |
| `EXC_CRASH (SIGKILL)` | Watchdog kill, OOM, or user force-quit |
| `EXC_ARITHMETIC` | Division by zero (integer) |

### Reading a Crash Report

A crash report (.ips or .crash file) contains:

```
Incident Identifier: [UUID]
Hardware Model:      iPhone14,2
OS Version:          iPhone OS 17.4 (21E236)
Exception Type:      EXC_CRASH (SIGABRT)
Exception Subtype:   SIGABRT
Triggered by Thread: 0

Thread 0 name: Dispatch queue: com.apple.main-thread
Thread 0 Crashed:
0   libswiftCore.dylib          0x00000001974a1234 _assertionFailure + 120
1   MyApp                       0x0000000100234bc0 0x100000000 + 0x234bc0
2   MyApp                       0x00000001002289a4 0x100000000 + 0x2289a4
...
```

After symbolication, frame 1 becomes:
```
1   MyApp   FeedViewModel.loadPosts() + 47   FeedViewModel.swift:89
```

**Key fields:**
- **Exception Type + Subtype**: the crash category.
- **Triggered by Thread**: which thread crashed.
- **Thread 0 Crashed**: the stack trace. Frame 0 is the crash site; higher frames are callers.
- **Binary Images**: the load addresses of all binaries — needed for symbolication.

### Watchdog Kills (0x8badf00d)

The exception code `0x8badf00d` ("ate bad food") means the watchdog killed the app for exceeding time limits:
- Launch: ~20 seconds to call `applicationDidFinishLaunching` return.
- Background task: exceeding the allowed background execution time.
- Foreground responsiveness: main thread unresponsive for too long.

These appear in crash reports as `EXC_CRASH (SIGKILL)` with exception subtype `0x8badf00d`. They do not have a useful stack trace — the crash address is the watchdog kill, not the hung code. Use Time Profiler to find what was blocking the main thread.

### OOM Terminations

Out-of-memory kills do not produce a crash report. The OS sends `SIGKILL` with no exception code visible to crash reporters. Detect via:
- MetricKit's `MXCrashDiagnostic` with `terminationReason = .applicationNotResponding` or `.outOfMemory`.
- Checking `didReceiveMemoryWarning` — if the app is killed after warnings, peak memory exceeded the device limit.

### dSYM Management

Every release build generates a dSYM folder at build time. The dSYM must match the exact binary UUID — different builds, even from the same source, have different UUIDs.

**Uploading dSYMs:**

For App Store builds, Xcode uploads dSYMs to Apple when `DWARF_WITH_DSYM` is enabled. Crashlytics fetches them via the Apple Developer API if you enable "Debug Information Format = DWARF with dSYM File" and configure the dSYM upload run script.

Manual upload:
```bash
# Crashlytics CLI
./FirebaseCrashlytics/run upload-symbols -gsp GoogleService-Info.plist -p ios MyApp.app.dSYM

# Or via fastlane
fastlane run upload_symbols_to_crashlytics dsym_path:"./build/MyApp.app.dSYM"
```

**Finding the UUID of a binary:**
```bash
dwarfdump --uuid MyApp.app.dSYM/Contents/Resources/DWARF/MyApp
# → UUID: A1B2C3D4-... (arm64)
```

### Crashlytics (Firebase)

Crashlytics is the most widely used iOS crash reporter. Integration:
1. Add `FirebaseCrashlytics` via SPM or CocoaPods.
2. Configure the dSYM upload run script in Build Phases.
3. Call `FirebaseApp.configure()` at the very beginning of `didFinishLaunchingWithOptions` — before any other SDK.
4. Optionally attach custom keys and log messages: `Crashlytics.crashlytics().setCustomValue("alice", forKey: "username")`.

Crashlytics groups crashes by stack trace similarity (not by exact address) — crashes at different addresses but with the same call path are grouped together.

### MetricKit Crash Diagnostics

`MXCrashDiagnostic` (iOS 14+) delivers crash reports from MetricKit's daily diagnostic payload — these are post-symbolicated by the system and include hang diagnostics and OOM information that third-party reporters miss.

```swift
func didReceive(_ payloads: [MXDiagnosticPayload]) {
    for payload in payloads {
        for crash in payload.crashDiagnostics ?? [] {
            let stackTrace = crash.callStackTree
            // log or upload stackTrace
        }
    }
}
```

## 4. Practical Usage

```swift
import Firebase
import FirebaseCrashlytics

// ── Crash reporter setup — first thing in didFinishLaunching ──
@main
final class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ app: UIApplication,
                     didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Must be first — catches crashes during subsequent setup
        FirebaseApp.configure()

        // Attach stable, non-PII user context for crash grouping
        if let userID = AuthService.shared.currentUserID {
            Crashlytics.crashlytics().setUserID(userID)
        }

        Crashlytics.crashlytics().setCustomValue(
            Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "unknown",
            forKey: "app_version"
        )

        return true
    }
}

// ── Recording non-fatal errors (caught exceptions) ─────────────
func fetchFeed() async {
    do {
        let posts = try await repository.fetchPosts()
        await MainActor.run { viewModel.posts = posts }
    } catch {
        // Non-fatal: log to Crashlytics for tracking frequency
        Crashlytics.crashlytics().record(error: error)
        await MainActor.run { viewModel.errorMessage = error.userFacingMessage }
    }
}

// ── Custom log messages before a crash site ────────────────────
// These appear in the "Logs" tab of a Crashlytics issue
func processPayment(order: Order) {
    Crashlytics.crashlytics().log("Processing payment for order \(order.id)")
    Crashlytics.crashlytics().setCustomValue(order.total.description, forKey: "order_total")
    // … payment logic
}

// ── MetricKit crash diagnostics subscriber ────────────────────
import MetricKit

final class DiagnosticsSubscriber: NSObject, MXMetricManagerSubscriber {
    override init() {
        super.init()
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        for payload in payloads {
            // Crash diagnostics (including hang and OOM)
            for crash in payload.crashDiagnostics ?? [] {
                let report = CrashReport(
                    reason: crash.terminationReason?.description ?? "unknown",
                    stackTrace: crash.callStackTree.jsonRepresentation().description
                )
                AnalyticsBackend.uploadCrashReport(report)
            }
            // Hang diagnostics — main thread unresponsive > 250ms
            for hang in payload.hangDiagnostics ?? [] {
                AnalyticsBackend.uploadHangReport(
                    duration: hang.hangDuration,
                    stackTrace: hang.callStackTree.jsonRepresentation().description
                )
            }
        }
    }
}

// Placeholder:
struct CrashReport { let reason: String; let stackTrace: String }
enum AnalyticsBackend {
    static func uploadCrashReport(_ r: CrashReport) {}
    static func uploadHangReport(duration: Measurement<UnitDuration>, stackTrace: String) {}
}
struct Order { let id: String; let total: Decimal }
protocol RepositoryProtocol { func fetchPosts() async throws -> [Post] }
struct Post {}
final class ViewModel: ObservableObject { @Published var posts: [Post] = []; @Published var errorMessage: String? = nil }
extension Error { var userFacingMessage: String { localizedDescription } }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is symbolication and why is it necessary for crash reports?**

A: Symbolication is the process of translating hexadecimal memory addresses in a crash report into human-readable function names, file names, and line numbers. iOS app binaries in production are compiled with optimisations and stripped of debug symbols — the binary contains only machine code with no embedded source information. The mapping from addresses to symbols lives in the dSYM (debug symbol) file generated at compile time. Without the matching dSYM, a crash report shows only `0x0000000100234bc0 + 0x00000001002289a4` — undebuggable. With the matching dSYM (UUID must match exactly), Crashlytics/Sentry translates these to `FeedViewModel.loadPosts() FeedViewModel.swift:89`. The dSYM must be preserved and uploaded for every released build — losing it makes that build's crashes permanently unreadable.

**Q: What does the exception code `0x8badf00d` mean in a crash report?**

A: `0x8badf00d` ("ate bad food") is Apple's watchdog kill code. It means the OS terminated the app because it exceeded the allowed time for a specific phase of its lifecycle — most commonly during app launch (`application(_:didFinishLaunchingWithOptions:)` taking longer than ~20 seconds) or during a background task (exceeding the execution time budget). Unlike typical crashes, watchdog kills don't have a meaningful crash address or stack trace pointing to the problematic code — the OS kills the process externally. To diagnose: use Instruments' Time Profiler to reproduce the scenario and identify what was blocking the main thread or what background task ran over time.

### Hard

**Q: How do you debug an EXC_BAD_ACCESS crash in production when the stack trace is cryptic?**

A: Four-step approach: (1) **Symbolicate properly**: ensure the dSYM for the exact build UUID is uploaded. Use `atos -o MyApp.dSYM/Contents/Resources/DWARF/MyApp -arch arm64 -l <load_address> <crash_address>` to manually symbolicate suspicious frames. (2) **Enable Zombie Objects in development**: Xcode Scheme → Diagnostics → ✓ Zombie Objects — this catches use-after-free (messages sent to deallocated objects) by leaving a "zombie" in place that logs which class was deallocated. This turns a cryptic `EXC_BAD_ACCESS` into an explicit log message. (3) **Address Sanitizer**: Xcode Scheme → Diagnostics → Address Sanitizer — catches heap use-after-free, buffer overflows, and stack corruption at the exact point they occur during development. (4) **Add non-fatal breadcrumbs**: add `Crashlytics.crashlytics().log(...)` calls in the suspected code path before the crash — these appear in the Crashlytics "Logs" tab and show the last actions before the crash, even when the stack trace is unhelpful.

**Q: How do you track OOM (out-of-memory) kills when they don't produce crash reports?**

A: OOM kills don't produce `.ips` crash reports — the OS sends `SIGKILL` with no opportunity for the crash reporter to run. Approaches: (1) **MetricKit**: `MXCrashDiagnostic` includes OOM terminations in its diagnostic payload. The `terminationReason` field will indicate OOM. This gives aggregated OOM counts but not per-incident stack traces. (2) **Previous-launch detection**: on next launch, check if `UIApplication.shared.applicationState == .background` was the state when the previous session ended (saved in `UserDefaults`). If the app was in foreground and launched fresh (not resumed), and no crash report was filed, it may have been an OOM kill. Libraries like Bugsnag and Sentry implement this heuristic. (3) **Memory pressure monitoring**: log `UIApplication.didReceiveMemoryWarningNotification` occurrences. High frequency before session terminations correlates with OOM risk. (4) **Instruments VM Tracker**: in development, profile peak dirty memory usage and compare to device RAM limits.

### Expert

**Q: Design a crash reporting strategy for a financial app where PII must never appear in crash reports, and crash data must be retained for 2 years for compliance.**

A: Four-layer strategy: (1) **PII stripping before reporting**: create a `CrashContext` struct with explicitly safe fields only (`userID: String` as a hashed opaque identifier, `screenName: String`, `appVersion: String`, `featureFlags: [String: Bool]`). Never include email, name, account numbers, or any raw user input. Use `Crashlytics.crashlytics().setUserID(sha256(userID))` — a hash is reversible by your server but not by someone reading a crash report dump. (2) **Custom crash reporter integration**: use Crashlytics for real-time alerting and grouping, but simultaneously pipe crash reports to your own backend (using `MXDiagnosticPayload` via MetricKit and a Crashlytics crash-report listener). Your backend stores them in encrypted storage with 2-year retention. (3) **Compliance audit trail**: log each crash upload event to your compliance system — who accessed the report, when, and why. Implement role-based access control on the crash report storage: only on-call engineers can view raw stack traces during incident response. (4) **Symbolication pipeline**: store dSYMs in a private S3 bucket with lifecycle policies (2-year retention). Run an automated symbolication job on every inbound crash report using `atos` or `symbolicatecrash`. Symbolicated reports are stored separately from raw reports — access to unsymbolicated reports is restricted.

## 6. Common Issues & Solutions

**Issue: Crashlytics shows crashes but the stack traces are unsymbolicated (just hex addresses).**

Solution: The dSYM was not uploaded for this build. Check: (1) Is the Build Phase "Run Script" for Crashlytics present and after "Compile Sources"? (2) Was the build made with "Debug Information Format = DWARF with dSYM File" in Release configuration? (3) Is Bitcode enabled? If so, Apple recompiles the binary and a new dSYM is generated — download it from App Store Connect under the build's "Download dSYM" button and upload manually. Use `dwarfdump --uuid` to verify the dSYM UUID matches the crashing binary's UUID from the crash report.

**Issue: Crashes appear grouped together in Crashlytics but are actually different bugs.**

Solution: Crashlytics groups by call stack similarity — if two different bugs crash at the same low-level function (e.g., `objc_msgSend`, `malloc`), they may be incorrectly grouped. Click into the individual crash reports and look at the full stack trace. Add custom keys that distinguish the crash context. If needed, use Sentry's fingerprinting customisation — you can override the grouping key to include a custom attribute that separates unrelated issues.

## 7. Related Topics

- [Logging](logging.md) — log breadcrumbs before crash sites
- [Monitoring](monitoring.md) — MetricKit metrics complement crash reports
- [App Startup — Launch Process](../13-app-startup/app-launch-process.md) — 0x8badf00d watchdog kills
- [Memory Optimization](../12-performance/memory-optimization.md) — preventing OOM crashes
- [Security — Data Security](../14-security/data-security.md) — protecting PII in crash reports
