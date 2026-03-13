# Logging

## 1. Overview

Logging is the practice of recording events, errors, and diagnostic information from a running app. On iOS, the recommended system is Apple's **Unified Logging System (ULS)** — accessed via `os_log` (C API) or the Swift `Logger` type (introduced iOS 14). The ULS is performant (log calls are lazy — formatting only happens if the message will actually be recorded), privacy-respecting (dynamic values are redacted by default in system logs), and integrated with Console.app and Instruments. Structured logging — using categories, subsystems, and typed fields instead of unstructured strings — makes logs searchable and aggregatable. Log levels (`.debug`, `.info`, `.default`, `.error`, `.fault`) control which messages are stored and which are discarded. Good logging practice: log the event and its context at appropriate levels, never log PII or secrets, and distinguish between user-facing error states and internal diagnostic information.

## 2. Simple Explanation

Logging is like keeping a ship's log. The captain records: when the ship departed, what weather was encountered, navigational decisions, any engine problems, and whether any cargo was damaged — but never records the passengers' private conversations. The log is written in real time; if the ship sinks, investigators read the log to understand what happened. On iOS, `Logger` is the ship's log system: you write to it in real time, and when a bug report arrives or you connect Console.app, you read the entries to reconstruct what happened. The privacy redaction is the policy of not recording passengers' conversations — even if an engineer reads the log, sensitive values appear as `<private>` unless they explicitly unlock them.

## 3. Deep iOS Knowledge

### Logger (Swift) vs os_log (C)

`Logger` (iOS 14+) is the Swift-native API over `os_log`. Prefer `Logger` in new Swift code — it uses string interpolation with compile-time privacy guarantees. `os_log` (C-level) remains available for Objective-C code.

```swift
import os

// Create a logger — subsystem = app bundle ID, category = functional area
let logger = Logger(subsystem: "com.myapp", category: "networking")
let authLogger = Logger(subsystem: "com.myapp", category: "auth")
let dbLogger = Logger(subsystem: "com.myapp", category: "database")
```

### Log Levels

| Level | Use case | Stored to disk? | Default visibility |
|-------|----------|-----------------|-------------------|
| `.debug` | Verbose developer info | No | Only with active profiling session |
| `.info` | Informational events | No | Visible in Console with filter |
| `.default` (`.notice`) | Significant events | Yes (until rotated) | Visible in Console |
| `.error` | Recoverable errors | Yes | Always visible |
| `.fault` (`.critical`) | Programmer errors, data corruption | Yes, high priority | Always visible |

### Privacy Levels

Dynamic values in `Logger` interpolations are **private by default** — redacted as `<private>` in Console.app output on other devices. Options:

```swift
logger.info("User \(userID, privacy: .private) logged in")       // redacted externally
logger.info("Request to \(url, privacy: .public)")               // always visible
logger.info("Error code: \(errorCode, privacy: .public)")        // safe to expose
logger.info("Amount: \(amount, privacy: .sensitive)")            // masked in all contexts
```

Use `.public` only for non-sensitive data (URLs, error codes, status codes). Never use `.public` for user IDs, emails, names, or financial data.

### Subsystems and Categories

- **Subsystem**: the app's bundle ID (`"com.myapp"`) — identifies the app.
- **Category**: the functional area (`"networking"`, `"auth"`, `"database"`) — enables filtering in Console.

In Console.app: filter by subsystem to see only your app's logs; filter by category to focus on one area.

### Performance

`Logger` is designed to be used pervasively — even disabled log calls are near-zero cost because the string formatting is deferred until the message is actually consumed. The ULS writes to a compressed circular buffer in memory; writes to disk happen only for `.default` level and above. This means `.debug` and `.info` logs are low-cost when not being observed.

### OSLog Categories as Namespaces

Use a `Logger` extension to define all loggers in one place:

```swift
extension Logger {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.myapp"
    static let network = Logger(subsystem: subsystem, category: "network")
    static let auth    = Logger(subsystem: subsystem, category: "auth")
    static let ui      = Logger(subsystem: subsystem, category: "ui")
    static let db      = Logger(subsystem: subsystem, category: "database")
}
```

### Structured Logging Pattern

Structured logging emits key-value pairs that can be searched programmatically:

```swift
// Unstructured (hard to query):
logger.error("Login failed for user \(email) because \(error)")

// Structured (searchable by field):
logger.error("Login failed — reason: \(reason, privacy: .public) user: \(userID.prefix(4), privacy: .public)***")
```

For remote logging backends (Datadog, Logtail), serialize log entries as JSON:

```swift
struct LogEntry: Codable {
    let level: String
    let category: String
    let event: String
    let properties: [String: String]
    let timestamp: Date
    let sessionID: String
}
```

### Viewing Logs

**Console.app**: Filter by `com.myapp` subsystem. Connect device via cable for live streaming or click "Start" to capture. Use the search bar with `subsystem:com.myapp category:network` syntax.

**Xcode Console**: During a debug session, `Logger` output appears in the Xcode debug console. Use `po OSLog.disabled = false` to force-enable private data during debugging.

**Command line**:
```bash
# Stream logs from a connected device
xcrun simctl spawn booted log stream --predicate 'subsystem == "com.myapp"'

# Collect logs from device
xcrun devicectl device log collect --device <udid> --output device.logarchive
```

## 4. Practical Usage

```swift
import os
import Foundation

// ── Logger namespace ──────────────────────────────────────────
extension Logger {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.myapp"
    static let network   = Logger(subsystem: subsystem, category: "network")
    static let auth      = Logger(subsystem: subsystem, category: "auth")
    static let ui        = Logger(subsystem: subsystem, category: "ui")
    static let database  = Logger(subsystem: subsystem, category: "database")
    static let lifecycle = Logger(subsystem: subsystem, category: "lifecycle")
}

// ── Network layer logging ─────────────────────────────────────
final class APIClient {

    func fetch<T: Decodable>(_ request: URLRequest) async throws -> T {
        let url = request.url?.absoluteString ?? "unknown"
        Logger.network.debug("→ \(request.httpMethod ?? "GET", privacy: .public) \(url, privacy: .public)")

        let start = CFAbsoluteTimeGetCurrent()
        let (data, response) = try await URLSession.shared.data(for: request)
        let ms = (CFAbsoluteTimeGetCurrent() - start) * 1000

        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0

        if statusCode >= 400 {
            Logger.network.error("← HTTP \(statusCode, privacy: .public) \(url, privacy: .public) (\(String(format: "%.0f", ms), privacy: .public)ms)")
        } else {
            Logger.network.info("← HTTP \(statusCode, privacy: .public) \(data.count, privacy: .public)B (\(String(format: "%.0f", ms), privacy: .public)ms)")
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}

// ── Auth logging — PII kept private ──────────────────────────
final class AuthService {

    func login(email: String, password: String) async throws -> User {
        Logger.auth.info("Login attempt — email: \(email, privacy: .private)")
        do {
            let user = try await apiLogin(email: email, password: password)
            Logger.auth.info("Login success — userID: \(user.id, privacy: .private)")
            return user
        } catch let error as AuthError {
            Logger.auth.error("Login failed — reason: \(error.code, privacy: .public)")
            throw error
        }
    }

    private func apiLogin(email: String, password: String) async throws -> User { User(id: "u1") }
}

// ── Database logging ──────────────────────────────────────────
final class PostRepository {

    func fetchPosts(page: Int) async throws -> [Post] {
        Logger.database.debug("Fetching posts page=\(page, privacy: .public)")
        let posts: [Post] = [] // … actual fetch
        Logger.database.debug("Fetched \(posts.count, privacy: .public) posts")
        return posts
    }
}

// ── View lifecycle logging ────────────────────────────────────
class TrackedViewController: UIViewController {

    override func viewDidLoad() {
        super.viewDidLoad()
        Logger.lifecycle.debug("\(type(of: self), privacy: .public) viewDidLoad")
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        Logger.lifecycle.info("\(type(of: self), privacy: .public) appeared")
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        Logger.lifecycle.debug("\(type(of: self), privacy: .public) disappeared")
    }
}

// ── Remote log forwarder (send structured logs to backend) ────
final class RemoteLogger {
    private var buffer: [LogEntry] = []
    private let maxBuffer = 100

    func log(level: LogLevel, category: String, event: String, props: [String: String] = [:]) {
        let entry = LogEntry(
            level: level.rawValue,
            category: category,
            event: event,
            properties: props,
            timestamp: Date(),
            sessionID: Session.current.id
        )
        buffer.append(entry)
        if buffer.count >= maxBuffer { flush() }
    }

    func flush() {
        guard !buffer.isEmpty else { return }
        let batch = buffer
        buffer.removeAll(keepingCapacity: true)
        Task.detached(priority: .utility) {
            try? await LoggingBackend.upload(batch)
        }
    }
}

enum LogLevel: String { case debug, info, warning, error, critical }
struct LogEntry: Codable {
    let level: String; let category: String; let event: String
    let properties: [String: String]; let timestamp: Date; let sessionID: String
}
enum LoggingBackend {
    static func upload(_ entries: [LogEntry]) async throws {}
}
struct Session { static let current = Session(); let id = UUID().uuidString }
struct User { let id: String }
struct Post {}
enum AuthError: Error { case invalidCredentials; var code: String { "invalid_credentials" } }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `os_log` and `print()` for iOS logging?**

A: `print()` writes a plain string to standard output (stdout). It is visible only in the Xcode console during a debug session — it does not integrate with the Unified Logging System, has no privacy controls, is not filterable by category/subsystem, and has no log levels. In production (no debugger attached), `print()` output goes nowhere. `os_log` / `Logger` write to the Unified Logging System — a kernel-level logging infrastructure. Messages persist in a compressed circular buffer, are filterable in Console.app by subsystem/category/level, support `privacy: .private` redaction of sensitive fields, and remain available for post-mortem debugging without a debugger attached. `os_log` is near-zero cost when not being observed (no string formatting occurs). Use `Logger` in all production code; use `print()` only in quick debug experiments.

**Q: What does `privacy: .private` do in a `Logger` interpolation?**

A: `privacy: .private` marks an interpolated value as sensitive — it is redacted to `<private>` in Console.app and system log dumps unless captured with explicit developer consent (a special debugging profile or a live Xcode session). Without any privacy annotation, dynamic values (non-literal strings, integers, etc.) are `.private` by default in `Logger`. Only literal string values are `.public` by default. This means that if you write `Logger.auth.info("Login for user \(email)")`, the email is redacted in any external log capture. To make a value visible to system log consumers, you must explicitly mark it `.public`: `Logger.auth.info("Status: \(statusCode, privacy: .public)")`. This design prevents accidental PII leakage in logs without requiring developers to manually scrub every log statement.

### Hard

**Q: How do you send structured logs from an iOS app to a remote backend without impacting app performance?**

A: Four-component design: (1) **Buffered in-memory queue**: accumulate log entries in an in-memory array (not a persistent store) up to a `maxBuffer` count (e.g., 100 entries). Writing to the buffer is an O(1) append — negligible cost. (2) **Async flush**: when the buffer fills, or when `applicationDidEnterBackground` fires (the last reliable moment before suspension), flush the buffer via a `Task.detached(priority: .utility)` that serialises entries to JSON and POSTs to the logging backend. The detached task runs off the main thread — no impact on frame rendering. (3) **Background task extension**: call `UIApplication.beginBackgroundTask` before the flush to ensure it completes if the app moves to background mid-flush. End the task in the completion handler. (4) **Sampling for high-volume events**: for events that fire thousands of times per session (scroll position, mouse movement), sample 1-in-10 or 1-in-100. Log the sampling rate in the payload so the backend can correct counts. Never log every frame of a `CADisplayLink` callback.

**Q: How do you correlate logs across frontend (iOS) and backend when debugging a production issue?**

A: Use a **session ID** and **request correlation ID**: (1) Generate a `sessionID` (`UUID().uuidString`) at app launch and include it in every log entry and every outgoing API request header (`X-Session-ID`). (2) For each API request, generate a `requestID` (`UUID().uuidString`) and include it in the request header (`X-Request-ID`). The backend includes this ID in its response and in its own server-side logs. (3) To debug an issue: take the session ID from the Crashlytics crash report or user report, query the backend log system for all server-side events matching that session ID, and reconstruct the full timeline of client + server events. (4) For structured log aggregation: emit events as JSON with `sessionId`, `requestId`, `userId` (hashed), `timestamp`, and `event` fields — these can be joined across frontend and backend log tables in BigQuery, Datadog, or Splunk.

### Expert

**Q: Design a privacy-compliant logging system for a healthcare iOS app where logs may contain medical information.**

A: Five-layer architecture: (1) **Two-tier logging**: client-side `Logger` (ULS) for development-only diagnostics — all health-related fields use `privacy: .private` and are never uploaded. A separate `AuditLogger` class emits compliance-required events (login, record access, data export) to the backend — these are the only logs that leave the device. (2) **Field classification**: define an enum `LogField` with `.safe` (can be logged), `.pii` (user identifier, hashed before logging), `.phi` (Protected Health Information — never logged remotely, redacted to a category like "diagnosis_viewed" without the actual diagnosis). (3) **Consent-gated logging**: extended diagnostics (beyond minimum audit trail) require explicit user consent. Store consent status in Keychain. If consent is not given, only audit-required events are sent. (4) **Audit log integrity**: each audit entry is signed with an HMAC using a key derived from the device's Secure Enclave. This ensures audit logs cannot be tampered with after the fact. (5) **Data residency**: audit logs are uploaded to a region-specific endpoint (EU users → EU servers, US users → US servers) to comply with GDPR / HIPAA data residency requirements. The endpoint is determined at login from the user's jurisdiction profile.

## 6. Common Issues & Solutions

**Issue: Logs show as `<private>` in Console.app even though the data is not sensitive.**

Solution: By default, dynamic values are private. Add `privacy: .public` to the interpolation: `logger.info("Status: \(code, privacy: .public)")`. For development, you can also enable a logging configuration profile that makes all private data visible on a specific device — install the Apple Logging profile from the developer documentation onto the test device.

**Issue: Logger output floods the Xcode console and hides important messages.**

Solution: Use log levels correctly — `.debug` for verbose output, `.info` for significant events. In the Xcode console, use the filter bar to filter by category: type the category name (e.g., "networking") to show only that category. Alternatively, use Console.app (which has richer filtering) instead of the Xcode console for log analysis. Also consider making `.debug` logs conditional on a flag: `if FeatureFlags.verboseLogging { Logger.network.debug(...) }`.

## 7. Related Topics

- [Crash Reporting](crash-reporting.md) — Crashlytics log breadcrumbs complement system logs
- [Monitoring](monitoring.md) — analytics events alongside diagnostic logs
- [Security — Data Security](../14-security/data-security.md) — PII protection in logs
- [Testing — Unit Testing](../11-testing/unit-testing.md) — testing log output via mock loggers
