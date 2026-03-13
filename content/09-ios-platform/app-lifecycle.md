# App Lifecycle

## 1. Overview

The iOS app lifecycle describes the sequence of states an app passes through from launch to termination, and the system callbacks that fire at each transition. Understanding the lifecycle is foundational: it determines when to start and stop work, when to save state, when the UI is visible, and when the app may be silently killed. Pre-iOS 13, a single `UIApplicationDelegate` handled all lifecycle events. iOS 13 introduced `UISceneDelegate`, splitting process-level events (handled by `AppDelegate`) from scene/window-level events (handled by `SceneDelegate`), enabling multiple simultaneous windows on iPad. SwiftUI apps use the `App` protocol, which maps to both delegates internally.

## 2. Simple Explanation

The app lifecycle is like a stage performance. The **AppDelegate** is the theatre manager — it handles the building opening (process launch), the fire alarm (push notifications, background tasks), and the building closing (process termination). The **SceneDelegate** is the stage manager for each individual stage (window/scene) — raising the curtain (scene becoming active), dimming the lights (scene going to background), and lowering the curtain (scene disconnection). The audience (user) interacts with the stage, not the building. Modern iOS supports multiple stages (multi-window on iPad), which is why they were separated.

## 3. Deep iOS Knowledge

### UIApplication States

| State | Description | Callbacks |
|-------|-------------|-----------|
| **Not Running** | Process not started or terminated | — |
| **Foreground Inactive** | On screen but not receiving touch events (during transition, call overlay) | `sceneWillResignActive` |
| **Foreground Active** | On screen, receiving events | `sceneDidBecomeActive` |
| **Background** | Off screen; limited CPU time (~30s) | `sceneDidEnterBackground` |
| **Suspended** | Process exists in memory; no CPU; killed without notice by OS | — |

**Key distinction**: Suspended apps are not running — they cannot execute code. The OS may kill a suspended app at any time without calling any callback. State that must survive must be persisted before entering background.

### AppDelegate Responsibilities (iOS 13+)

With scene support, `UIApplicationDelegate` handles **process-level** events only:

```swift
@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    // ── Process launch ─────────────────────────────────────
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Register services, configure 3rd-party SDKs, set up logging
        // Do NOT access the window here — scenes haven't been created yet
        return true
    }

    // ── Push notification token ────────────────────────────
    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) { }

    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) { }

    // ── Background URL session ─────────────────────────────
    func application(_ application: UIApplication,
                     handleEventsForBackgroundURLSession identifier: String,
                     completionHandler: @escaping () -> Void) { }

    // ── Scene configuration (iOS 13+) ─────────────────────
    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
    }

    func application(_ application: UIApplication,
                     didDiscardSceneSessions sceneSessions: Set<UISceneSession>) { }
}
```

### SceneDelegate Responsibilities

`UIWindowSceneDelegate` handles **window/scene-level** events — everything related to a specific window:

| Method | Fires when |
|--------|-----------|
| `scene(_:willConnectTo:options:)` | Scene created; set up window and root VC |
| `sceneDidBecomeActive(_:)` | Scene enters foreground active state |
| `sceneWillResignActive(_:)` | Interruption begins (incoming call, system alert) |
| `sceneDidEnterBackground(_:)` | Scene fully backgrounded; last chance to persist state |
| `sceneWillEnterForeground(_:)` | Scene about to return to foreground |
| `sceneDidDisconnect(_:)` | Scene session released from memory (not process termination) |

### Scene Lifecycle vs Process Lifecycle

On iPad with multi-window, a user can have two instances of the same app open simultaneously — two separate `UIScene` objects, each with its own `SceneDelegate`. The `AppDelegate` fires once per process; `SceneDelegate` fires once per scene.

`sceneDidDisconnect` does NOT mean the app is terminating — the scene is released from memory while the process may keep running. Persist scene-specific state in `NSUserActivity` for state restoration.

### State Restoration

Save scene state so the app can restore it when the user returns (even after a process kill):

```swift
// In SceneDelegate
func stateRestorationActivity(for scene: UIScene) -> NSUserActivity? {
    return view.userActivity   // the current NSUserActivity set on the root view controller
}

func scene(_ scene: UIScene, restoreInteractionStateWith stateRestorationActivity: NSUserActivity) {
    // Restore navigation state, selected tab, scroll position, etc.
}
```

### SwiftUI App Protocol

SwiftUI apps use `@main` + `App` instead of AppDelegate/SceneDelegate directly:

```swift
@main
struct MyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

`@UIApplicationDelegateAdaptor` lets you keep an `AppDelegate` for push registration and background session handling while using the SwiftUI App protocol.

### Launch Options

`launchOptions` dictionary in `didFinishLaunchingWithOptions` contains the reason the app was launched:

| Key | Meaning |
|-----|---------|
| `.remoteNotification` | Launched by tapping a push notification |
| `.url` | Launched by a deep link URL |
| `.shortcutItem` | Launched from a home screen quick action |
| `.bluetoothCentrals` / `.bluetoothPeripherals` | Relaunched for Bluetooth state restoration |
| `.location` | Relaunched for significant location change |

### applicationWillTerminate

Called **only** when the app is in the **foreground** when terminated (e.g., user force-quits). If the app is in the background and the OS kills it, this method is NOT called. Treat it as a best-effort, not a guarantee.

## 4. Practical Usage

```swift
import UIKit

// ── AppDelegate — minimal modern setup ────────────────────────
class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        configureAppearance()
        registerForPushNotifications(application)
        return true
    }

    private func configureAppearance() {
        UINavigationBar.appearance().tintColor = .systemBlue
    }

    private func registerForPushNotifications(_ application: UIApplication) {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async { application.registerForRemoteNotifications() }
        }
    }

    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        // Send token to your server
        print("Device token: \(token)")
    }

    // Scene configuration
    func application(_ application: UIApplication,
                     configurationForConnecting session: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        UISceneConfiguration(name: "Default Configuration", sessionRole: session.role)
    }
}

// ── SceneDelegate — window setup + lifecycle ──────────────────
class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
               options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        let window = UIWindow(windowScene: windowScene)
        window.rootViewController = MainTabBarController()
        window.makeKeyAndVisible()
        self.window = window

        // Handle deep link delivered at launch
        if let urlContext = connectionOptions.urlContexts.first {
            handle(url: urlContext.url)
        }
    }

    func sceneDidBecomeActive(_ scene: UIScene) {
        // Resume timers, refresh UI, start animations
        UIApplication.shared.applicationIconBadgeNumber = 0  // clear badge
    }

    func sceneWillResignActive(_ scene: UIScene) {
        // Pause timers, pause game, save in-progress work
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        // ← Most important: persist data here
        try? CoreDataStack.shared.viewContext.save()
        scheduleBackgroundRefresh()
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        // Undo background UI changes (hide sensitive content, restore)
    }

    // State restoration
    func stateRestorationActivity(for scene: UIScene) -> NSUserActivity? {
        return (window?.rootViewController as? StateRestorable)?.currentActivity
    }

    func scene(_ scene: UIScene, restoreInteractionStateWith activity: NSUserActivity) {
        (window?.rootViewController as? StateRestorable)?.restore(from: activity)
    }

    // Deep link while app is running
    func scene(_ scene: UIScene, openURLContexts urlContexts: Set<UIOpenURLContext>) {
        guard let url = urlContexts.first?.url else { return }
        handle(url: url)
    }

    private func handle(url: URL) {
        DeepLinkRouter.shared.route(url)
    }

    private func scheduleBackgroundRefresh() {
        let request = BGAppRefreshTaskRequest(identifier: "com.app.refresh")
        request.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }
}

// ── SwiftUI entry point with AppDelegate adapter ──────────────
import SwiftUI

@main
struct MyApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: phase) { newPhase in
            switch newPhase {
            case .active:     break               // resumed
            case .inactive:   break               // interrupted
            case .background:
                try? CoreDataStack.shared.viewContext.save()
            @unknown default: break
            }
        }
    }
}

// ── Reading app state programmatically ────────────────────────
extension UIApplication {
    var isInForeground: Bool {
        applicationState != .background
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between AppDelegate and SceneDelegate, and why were scenes introduced?**

A: Pre-iOS 13, `UIApplicationDelegate` handled both process-level events (launch, push token, background URL sessions) and the app's single window. iOS 13 introduced `UISceneDelegate` to support multiple simultaneous windows on iPad — each window is an independent `UIWindowScene` with its own lifecycle. `AppDelegate` now handles only process-level events that happen once per process (launch, push registration, background URL session completion), while `SceneDelegate` handles window-level events that can happen independently per scene (window creation, becoming active/inactive, backgrounding, state restoration). An iPad app with two windows has one `AppDelegate` firing process events but two independent `SceneDelegate` instances firing scene events.

**Q: What is the difference between `sceneDidEnterBackground` and `applicationWillTerminate`?**

A: `sceneDidEnterBackground` fires reliably every time the scene moves off screen — this is where you must persist state, because the OS may kill the suspended process at any time without calling any further methods. `applicationWillTerminate` fires only when the app is terminated while it is still **in the foreground** — for example, when the user force-quits from the app switcher while the app is visible. If the OS kills a background-suspended app due to memory pressure, `applicationWillTerminate` is NOT called. This is why you cannot rely on `applicationWillTerminate` for critical saves; `sceneDidEnterBackground` is the correct hook.

### Hard

**Q: How does `sceneDidDisconnect` differ from app termination, and what does it mean for state persistence?**

A: `sceneDidDisconnect` fires when the system releases a scene session from memory — typically when the user swipes the scene away in the app switcher, or when the OS decides to free memory. Critically, this does **not** terminate the app process — the process continues running and other scenes remain active. The scene can be reconnected later (e.g., the user re-opens the app), at which point `scene(_:willConnectTo:options:)` fires again. State that should survive a reconnect must be stored in `NSUserActivity` via `stateRestorationActivity(for:)` so the SceneDelegate can restore it in `scene(_:restoreInteractionStateWith:)`. Heavy in-memory state (caches, loaded data) can be rebuilt from the persistent store on reconnect — the scene doesn't need to hold it across disconnects.

**Q: How should you handle a deep link URL when the app is launched cold via that URL vs when it's already running?**

A: Two separate entry points: (1) **Cold launch**: the URL arrives in `UIScene.ConnectionOptions.urlContexts` passed to `scene(_:willConnectTo:options:)`. Handle it after setting up the window and root view controller. (2) **Already running**: the URL arrives in `scene(_:openURLContexts:)`. Both paths should route to the same handler function. In SwiftUI, use `.onOpenURL { url in ... }` on the `WindowGroup` — this fires in both cases. In both UIKit and SwiftUI, avoid performing deep navigation before the window is ready; post navigation to the next run loop tick if needed to ensure the view hierarchy is fully built.

### Expert

**Q: Describe the exact sequence of lifecycle callbacks when a user switches from App A to App B and back.**

A: **App A → background**: (1) `sceneWillResignActive` — becoming inactive (brief transition state). (2) `sceneDidEnterBackground` — fully backgrounded; OS takes snapshot of UI. App A process moves to suspended state (no CPU). **App B launch** (if not running): (3) `AppDelegate.application(_:didFinishLaunchingWithOptions:)`. (4) `scene(_:willConnectTo:options:)`. (5) `sceneWillEnterForeground`. (6) `sceneDidBecomeActive`. **User returns to App A**: (7) `sceneWillEnterForeground` fires in App A — app is about to become visible. (8) `sceneDidBecomeActive` — App A is interactive again. App B receives: (9) `sceneWillResignActive` → (10) `sceneDidEnterBackground`. The OS snapshot taken at step 2 is what's shown in the app switcher — this is why you should hide sensitive information (bank balance, passwords) in `sceneWillResignActive` and restore it in `sceneDidBecomeActive`.

## 6. Common Issues & Solutions

**Issue: `UIApplication.shared.windows.first` returns `nil` or the wrong window.**

Solution: On iOS 15+ with scene support, use `UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap { $0.windows }.first { $0.isKeyWindow }`. Accessing `UIApplication.shared.windows` is deprecated and returns all windows unfiltered.

**Issue: State restoration is not working — the app always starts fresh.**

Solution: Ensure `stateRestorationActivity(for:)` returns a non-nil `NSUserActivity` with a `activityType` string. The activity must be registered in `NSUserActivityTypes` in `Info.plist`. Also confirm `scene(_:restoreInteractionStateWith:)` is implemented and actually applies the state before the view appears.

**Issue: `applicationWillTerminate` is used to save Core Data — data is occasionally lost.**

Solution: Move saves to `sceneDidEnterBackground` — this fires reliably before the app is suspended. `applicationWillTerminate` is not called on background termination (the most common kind). Save incrementally after each mutation rather than in a single termination hook.

**Issue: Deep link opens the app but navigation doesn't occur.**

Solution: The navigation is attempted before the root view controller's view hierarchy is loaded. Defer the deep link handling to the next run loop cycle: `DispatchQueue.main.async { DeepLinkRouter.shared.route(url) }` — this ensures `viewDidLoad` has fired on the root VC before navigation commands are issued.

## 7. Related Topics

- [Background Tasks](background-tasks.md) — scheduling BGAppRefreshTask from `sceneDidEnterBackground`
- [Push Notifications](push-notifications.md) — device token registration in AppDelegate
- [Deep Links & Universal Links](deep-links-universal-links.md) — handling URLs in scene(_:openURLContexts:)
- [UIViewController Lifecycle](../04-ui-frameworks/uiviewcontroller-lifecycle.md) — VC lifecycle within the app lifecycle
- [Core Data](../08-data-persistence/core-data.md) — saving context in `sceneDidEnterBackground`
