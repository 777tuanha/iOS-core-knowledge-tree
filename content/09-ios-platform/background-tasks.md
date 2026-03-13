# Background Tasks

## 1. Overview

iOS aggressively suspends apps when they move to the background to preserve battery and CPU resources. The Background Tasks framework (`BGTaskScheduler`) provides two controlled execution windows: `BGAppRefreshTask` (short periodic refreshes — fetching headlines, updating widgets) and `BGProcessingTask` (longer CPU-intensive work on charging — database compaction, ML model training, image processing). Beyond these, background execution is available through specialised channels: background `URLSession` (network transfers that continue without the app), VoIP push (PushKit), and location updates. Understanding the execution budget, scheduling rules, and the simulator testing tools is essential for reliable background behaviour.

## 2. Simple Explanation

The OS is a strict building manager who cuts power to empty offices (suspended apps) to save electricity. The Background Tasks framework is the scheduling desk where you book a maintenance slot in advance: "Please give me 30 seconds around midnight to check for new mail" (`BGAppRefreshTask`) or "Please give me 10 minutes when the building is plugged in to reorganise the filing room" (`BGProcessingTask`). The OS decides the exact timing based on usage patterns, battery level, and device load — you can only set the earliest possible start time. If you don't reschedule before your slot ends, you won't get another one.

## 3. Deep iOS Knowledge

### BGTaskScheduler Overview

`BGTaskScheduler` is the central API for scheduling background execution. Tasks must be registered at launch and submitted with a request.

**Registration flow**:
1. Declare task identifiers in `Info.plist` under `BGTaskSchedulerPermittedIdentifiers`.
2. Call `BGTaskScheduler.shared.register(forTaskWithIdentifier:using:launchHandler:)` in `AppDelegate.application(_:didFinishLaunchingWithOptions:)` — before the app finishes launching.
3. Submit a `BGTaskRequest` from `sceneDidEnterBackground` (or any foreground moment).

### Task Types

| Class | Max runtime | Requires charging | Use case |
|-------|------------|-------------------|---------|
| `BGAppRefreshTaskRequest` | ~30 seconds | No | Feed refresh, widget update, badge count |
| `BGProcessingTaskRequest` | Minutes | Yes (configurable) | DB maintenance, ML inference, media processing |

**BGAppRefreshTask**: The OS honours the request based on usage patterns — it learns when the user typically opens the app and pre-fetches before that time. The actual execution window may be shorter than 30 seconds if the system is under load. The task has an `expirationHandler` closure that fires shortly before the budget ends.

**BGProcessingTask**: Requires `requiresExternalPower = true` (recommended; set `false` only for lightweight tasks). Can request `requiresNetworkConnectivity = true`. Runs for several minutes — exact duration is OS-determined.

### Registering and Scheduling

```swift
// In AppDelegate.didFinishLaunchingWithOptions:
BGTaskScheduler.shared.register(
    forTaskWithIdentifier: "com.app.refresh",
    using: nil  // nil = main queue
) { task in
    handleRefreshTask(task as! BGAppRefreshTask)
}

// Schedule from sceneDidEnterBackground:
func scheduleRefresh() {
    let request = BGAppRefreshTaskRequest(identifier: "com.app.refresh")
    request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)   // no earlier than 15 min
    try? BGTaskScheduler.shared.submit(request)
}
```

### Task Handler Pattern

```swift
func handleRefreshTask(_ task: BGAppRefreshTask) {
    // Schedule the next refresh BEFORE doing work (system may kill after expiration)
    scheduleRefresh()

    let operation = FeedRefreshOperation()

    // Called when the OS decides the task must end
    task.expirationHandler = {
        operation.cancel()
    }

    operation.completionBlock = {
        task.setTaskCompleted(success: !operation.isCancelled)
    }

    OperationQueue.main.addOperation(operation)
}
```

**Key rules**:
- Call `task.setTaskCompleted(success:)` exactly once — the OS uses this to track success rate and adjusts scheduling priority.
- Reschedule the next request at the start of the handler, not the end — the handler may be killed before it finishes.
- Complete quickly within the budget; defer large work to `BGProcessingTask`.

### Background URLSession

Background URL sessions continue network transfers after the app is suspended or killed. The OS manages the transfer in a separate process.

When the transfer completes, the OS relaunches the app (or wakes it if suspended) and calls:
```swift
func application(_ application: UIApplication,
                 handleEventsForBackgroundURLSession identifier: String,
                 completionHandler: @escaping () -> Void) {
    backgroundCompletionHandler = completionHandler
    // Recreate URLSession with matching identifier to receive delegate callbacks
}
```

Full details in [URLSession](../07-networking/urlsession.md).

### Silent Push Notifications

A silent push (`content-available: 1`, no `alert`/`sound`/`badge`) wakes a suspended app for ~30 seconds to fetch new content. The app must have **Background App Refresh** capability enabled.

```swift
func application(_ application: UIApplication,
                 didReceiveRemoteNotification userInfo: [AnyHashable: Any],
                 fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
    // Fetch new content, then call:
    completionHandler(.newData)   // or .noData, .failed
}
```

Call the `completionHandler` within ~30 seconds or the OS terminates the process. The OS tracks your completion result to learn whether silent pushes for your app are productive.

### Legacy Background Modes

Some apps declare background execution modes in `Info.plist` (`UIBackgroundModes`):

| Mode | Use case |
|------|---------|
| `audio` | Continuous audio playback (music, podcast) |
| `location` | Continuous GPS tracking (navigation) |
| `voip` | VoIP (use PushKit instead) |
| `remote-notification` | Silent push handling |
| `fetch` | Legacy background fetch (replaced by BGAppRefreshTask) |
| `processing` | Required for BGProcessingTask |

### Testing Background Tasks in Simulator

Use the LLDB debugger command to simulate task launch:
```
e -l objc -- (void)[[BGTaskScheduler sharedScheduler] _simulateLaunchForTaskWithIdentifier:@"com.app.refresh"]
```
Or use Xcode's Background Tasks debug gauge. Pause at a breakpoint in `sceneDidEnterBackground`, then run the command in the LLDB console.

## 4. Practical Usage

```swift
import BackgroundTasks
import UIKit

// ── Info.plist — BGTaskSchedulerPermittedIdentifiers ──────────
// Add both identifiers to the array

// ── AppDelegate ───────────────────────────────────────────────
class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        registerBackgroundTasks()
        return true
    }

    private func registerBackgroundTasks() {
        // App Refresh Task
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.app.feed-refresh",
            using: nil
        ) { task in
            FeedRefreshManager.shared.handleRefreshTask(task as! BGAppRefreshTask)
        }

        // Processing Task
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: "com.app.db-maintenance",
            using: nil
        ) { task in
            DatabaseMaintenanceManager.shared.handleProcessingTask(task as! BGProcessingTask)
        }
    }
}

// ── Feed Refresh Manager ──────────────────────────────────────
class FeedRefreshManager {
    static let shared = FeedRefreshManager()
    private let refreshIdentifier = "com.app.feed-refresh"

    func scheduleRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: refreshIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)  // earliest: 15 minutes
        do {
            try BGTaskScheduler.shared.submit(request)
        } catch BGTaskScheduler.Error.unavailable {
            // Background App Refresh disabled by user in Settings
        } catch {
            print("Failed to schedule refresh: \(error)")
        }
    }

    func handleRefreshTask(_ task: BGAppRefreshTask) {
        scheduleRefresh()      // ← reschedule FIRST

        let task_local = task  // capture for expiration handler

        Task {
            do {
                try await FeedService.shared.fetchLatest()
                task_local.setTaskCompleted(success: true)
            } catch {
                task_local.setTaskCompleted(success: false)
            }
        }

        task.expirationHandler = {
            // OS is ending our time — cancel work and mark incomplete
            task_local.setTaskCompleted(success: false)
        }
    }
}

// ── Database Maintenance Manager ──────────────────────────────
class DatabaseMaintenanceManager {
    static let shared = DatabaseMaintenanceManager()
    private let processingIdentifier = "com.app.db-maintenance"

    func scheduleMaintenance() {
        let request = BGProcessingTaskRequest(identifier: processingIdentifier)
        request.requiresExternalPower = true        // only when charging
        request.requiresNetworkConnectivity = false // no network needed
        request.earliestBeginDate = Date(timeIntervalSinceNow: 60 * 60)  // earliest: 1 hour

        try? BGTaskScheduler.shared.submit(request)
    }

    func handleProcessingTask(_ task: BGProcessingTask) {
        scheduleMaintenance()   // reschedule

        let taskRef = task
        Task.detached(priority: .background) {
            do {
                try await DatabaseMaintenance.vacuum()
                try await DatabaseMaintenance.rebuildIndexes()
                try await DatabaseMaintenance.deleteExpiredRecords()
                taskRef.setTaskCompleted(success: true)
            } catch {
                taskRef.setTaskCompleted(success: false)
            }
        }

        task.expirationHandler = {
            taskRef.setTaskCompleted(success: false)
        }
    }
}

// ── Silent push handler ───────────────────────────────────────
extension AppDelegate {
    func application(_ application: UIApplication,
                     didReceiveRemoteNotification userInfo: [AnyHashable: Any],
                     fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
        guard let type = userInfo["type"] as? String else {
            completionHandler(.noData); return
        }

        Task {
            do {
                switch type {
                case "new_message":
                    let count = try await MessageService.shared.fetchUnread()
                    completionHandler(count > 0 ? .newData : .noData)
                default:
                    completionHandler(.noData)
                }
            } catch {
                completionHandler(.failed)
            }
        }
    }
}

// ── Schedule on background ────────────────────────────────────
// Called from SceneDelegate.sceneDidEnterBackground:
func applicationDidEnterBackground() {
    FeedRefreshManager.shared.scheduleRefresh()
    DatabaseMaintenanceManager.shared.scheduleMaintenance()
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `BGAppRefreshTask` and `BGProcessingTask`?**

A: `BGAppRefreshTask` is designed for short periodic work — typically fetching new data (news feed, weather, badge count). It runs for approximately 30 seconds, does not require charging, and the OS schedules it based on the user's usage patterns (it learns to run just before the user typically opens the app). `BGProcessingTask` is for longer, potentially CPU-intensive work like database maintenance, downloading large files, or running ML inference. It typically requires the device to be charging (`requiresExternalPower = true`) and can run for several minutes. The OS decides the exact timing for both — you only set the earliest possible start time. Both must be registered at app launch and must be declared in `Info.plist` under `BGTaskSchedulerPermittedIdentifiers`.

**Q: Why must you reschedule the next background task at the start of the handler, not the end?**

A: The OS may kill the task before the handler completes — due to expiration, system memory pressure, or user force-quitting. If you schedule the next request at the end of the handler and the handler is killed, no future task is ever scheduled. By rescheduling at the start, the next task is guaranteed to be submitted regardless of whether the current run completes. This is the standard pattern: schedule next, do work, call `setTaskCompleted(success:)`.

### Hard

**Q: How does the OS decide when to run a BGAppRefreshTask, and what affects scheduling priority?**

A: The OS uses **machine learning** to predict when the user will next open the app, then schedules the refresh just before that time to maximise freshness. Factors that influence scheduling: (1) **Usage patterns** — an app opened every morning at 7 AM gets scheduled around 6:45 AM. (2) **Task success rate** — consistently calling `setTaskCompleted(success: true)` improves priority; `false` degrades it. (3) **Battery level** — tasks are deferred or skipped on low battery. (4) **User setting** — Background App Refresh can be disabled per-app in Settings, completely preventing execution. (5) **earliestBeginDate** — a later date tells the OS not to start before that time (a floor, not a target). The OS may defer tasks significantly beyond `earliestBeginDate` if conditions aren't favorable — this is why you can't rely on precise timing for background work.

**Q: How do silent push notifications compare to BGAppRefreshTask for triggering background work?**

A: Both wake a suspended app for ~30 seconds of background execution. Key differences: **Silent push** is externally triggered — your server decides when to send it, providing precise control. It requires an APNs payload with `content-available: 1` and the `remote-notification` background mode. The OS may throttle delivery if your app sends too many silent pushes or if the device is in low-power mode (Low Power Mode and Do Not Disturb can suppress them). **BGAppRefreshTask** is proactively scheduled by the app and scheduled by the OS at system-determined times based on usage patterns — the server has no involvement. Silent push is better when the server has new data that needs immediate delivery (new message, score update). BGAppRefreshTask is better for periodic polling that doesn't need server coordination.

### Expert

**Q: Design a background sync architecture that reliably updates content while respecting iOS background execution limits.**

A: A robust architecture layers multiple mechanisms: (1) **BGAppRefreshTask** as the primary periodic refresh — schedule on every `sceneDidEnterBackground`, handle with incremental fetching (only deltas since last sync), reschedule immediately. Budget: 30 seconds. (2) **Silent push** for server-triggered urgency — when new content arrives on the server, push a silent notification to wake the app immediately. Fallback for when BGAppRefreshTask is delayed. (3) **Background URLSession** for large downloads (audio, video, documents) — the actual bytes transfer even when the app is killed; the app is woken only on completion. (4) **BGProcessingTask** for heavy post-processing — once data is downloaded, run extraction/indexing/compression when charging. Combine all with: NWPathMonitor connectivity observation (sync when network becomes available in foreground), persistent request queue for mutations (in case sync is interrupted), and incremental sync tokens (server change tokens or timestamps) so each execution picks up exactly where the last one stopped. The key invariant: every execution path calls `setTaskCompleted` and reschedules, so the system always has accurate success statistics to maintain scheduling priority.

## 6. Common Issues & Solutions

**Issue: BGAppRefreshTask handler is never called.**

Solution: Check that (1) the identifier matches exactly between `Info.plist`, `register(forTaskWithIdentifier:)`, and the submitted request; (2) the task is registered in `AppDelegate.didFinishLaunchingWithOptions` — registration after launch is ignored; (3) Background App Refresh is enabled in Settings → General → Background App Refresh for your app; (4) use the LLDB simulator command to force the task and verify the handler fires.

**Issue: `BGTaskScheduler.shared.submit` throws `BGTaskScheduler.Error.unavailable`.**

Solution: Background App Refresh is disabled by the user in Settings, or the device is in Low Power Mode. This is expected and should be handled gracefully — catch the error and skip scheduling rather than crashing. Do not present UI from this error; it's a normal user choice.

**Issue: `setTaskCompleted` is never called, causing the OS to not schedule future tasks.**

Solution: Every code path in the task handler must call `setTaskCompleted(success:)` — including the `expirationHandler`. Wrap the handler body in a `do/catch` with `setTaskCompleted(success: false)` in the `catch`. Use a `defer` block or a completion-tracking flag to ensure it's called exactly once.

**Issue: Background processing finishes in the simulator but never runs on device.**

Solution: On device, the OS controls scheduling and may defer tasks by hours. Use the Xcode Background Tasks debug feature (Debug → Simulate Background Fetch) for integration testing. For production validation, check Console.app for `backgroundtaskd` logs that show whether your task was scheduled and launched.

## 7. Related Topics

- [App Lifecycle](app-lifecycle.md) — schedule background tasks from `sceneDidEnterBackground`
- [Push Notifications](push-notifications.md) — silent push for server-triggered background wakeup
- [URLSession](../07-networking/urlsession.md) — background URLSession for transfers during suspension
- [Advanced Networking](../07-networking/advanced-networking.md) — offline request queue combined with background refresh
- [Data Synchronization](../08-data-persistence/data-sync.md) — background sync architecture
