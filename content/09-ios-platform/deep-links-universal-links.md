# Deep Links & Universal Links

## 1. Overview

Deep links allow external sources — other apps, websites, emails, QR codes, and push notifications — to open your app at a specific screen. iOS supports two mechanisms: **custom URL schemes** (e.g., `myapp://profile/42`) and **Universal Links** (standard HTTPS URLs like `https://myapp.com/profile/42` that open your app instead of the browser). Universal Links are strongly preferred in production: they work even if the app is not installed (falling back to the website), are phishing-resistant (require proof of domain ownership), and integrate cleanly with Handoff and Spotlight. `NSUserActivity` powers Handoff and Spotlight indexing. SwiftUI handles links via `.onOpenURL`.

## 2. Simple Explanation

Custom URL schemes are like a private phone extension — `myapp://` only works if the recipient (the app) is installed; anyone can claim to be `myapp://`. Universal Links are like a verified business address — `https://myapp.com/profile/42` is a real HTTPS URL that Apple verifies you own (via a JSON file on your server), so only your app can handle it. If the app isn't installed, the URL opens as a normal website. The `NSUserActivity` system is the handoff note — you write your current location ("viewing profile 42") on a note, and any other device with the app can pick up where you left off.

## 3. Deep iOS Knowledge

### Custom URL Schemes

Registered in `Info.plist` under `CFBundleURLTypes`. Any app can open your URL scheme — there is no security verification.

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array><string>myapp</string></array>
        <key>CFBundleURLName</key>
        <string>com.myapp.urlscheme</string>
    </dict>
</array>
```

**Security risk**: Other apps can register the same scheme and intercept links. Never pass sensitive tokens through URL scheme parameters.

### Universal Links

Universal Links are standard HTTPS URLs your app claims ownership of. Setup requires two steps:

**Step 1 — AASA file (Apple App Site Association)**

Host a JSON file at `https://yourdomain.com/.well-known/apple-app-site-association` (no `.json` extension). Must be served over HTTPS with a valid certificate:

```json
{
  "applinks": {
    "details": [
      {
        "appIDs": ["TEAMID.com.myapp"],
        "components": [
          { "/": "/profile/*", "comment": "Profile pages" },
          { "/": "/post/*" },
          { "/": "/invite/*" },
          { "?": { "ref": "?*" }, "comment": "Referral links" }
        ]
      }
    ]
  }
}
```

**Step 2 — Associated Domains entitlement**

In Xcode → Signing & Capabilities → Associated Domains, add:
```
applinks:yourdomain.com
```

The OS downloads and caches the AASA file during app installation (and periodically refreshes it). When the user taps `https://yourdomain.com/profile/42`, iOS checks the AASA cache and opens your app instead of Safari.

### Handling Universal Links in UIKit

```swift
// In SceneDelegate:
func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
    guard userActivity.activityType == NSUserActivityTypeBrowsingWeb,
          let url = userActivity.webpageURL else { return }
    DeepLinkRouter.shared.route(url)
}

// Also handle on cold launch in willConnectTo:
func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
           options connectionOptions: UIScene.ConnectionOptions) {
    // ...window setup...
    if let activity = connectionOptions.userActivities.first(where: { $0.activityType == NSUserActivityTypeBrowsingWeb }),
       let url = activity.webpageURL {
        DeepLinkRouter.shared.route(url)
    }
}
```

### Handling Deep Links in SwiftUI

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    DeepLinkRouter.shared.route(url)
                }
        }
    }
}
```

`.onOpenURL` handles both custom URL schemes and Universal Links (delivered as `NSUserActivity`).

### NSUserActivity — Handoff and Spotlight

`NSUserActivity` encodes the user's current context (screen, data, scroll position). It powers:
- **Handoff**: continue on another device.
- **Spotlight**: index app content for system search.
- **State restoration**: `SceneDelegate.stateRestorationActivity`.

```swift
// Advertise current activity from a view controller:
let activity = NSUserActivity(activityType: "com.myapp.viewProfile")
activity.title = "Alice's Profile"
activity.userInfo = ["user_id": "user_42"]
activity.webpageURL = URL(string: "https://myapp.com/profile/42")
activity.isEligibleForHandoff = true
activity.isEligibleForSearch = true
activity.isEligibleForPublicIndexing = false
userActivity = activity   // assign to UIViewController.userActivity
activity.becomeCurrent()
```

### Home Screen Quick Actions

Static (in `Info.plist`) and dynamic (`UIApplicationShortcutItem`) shortcuts appear on 3D Touch / long-press of the app icon:

```swift
// Create dynamic shortcut:
let shortcut = UIApplicationShortcutItem(
    type: "com.app.newPost",
    localizedTitle: "New Post",
    localizedSubtitle: nil,
    icon: UIApplicationShortcutIcon(systemImageName: "plus"),
    userInfo: nil
)
UIApplication.shared.shortcutItems = [shortcut]

// Handle in SceneDelegate:
func windowScene(_ windowScene: UIWindowScene,
                 performActionFor shortcutItem: UIApplicationShortcutItem,
                 completionHandler: @escaping (Bool) -> Void) {
    DeepLinkRouter.shared.route(shortcutItem: shortcutItem)
    completionHandler(true)
}
```

### Deep Link Router

Centralise all deep link handling in a single router to avoid scattered `if url.host == "..."` checks throughout the codebase:

```swift
enum DeepLink {
    case profile(userID: String)
    case post(postID: String)
    case invite(code: String)
    case unknown

    init(url: URL) {
        let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let path = url.path
        let params = Dictionary(
            uniqueKeysWithValues: components?.queryItems?.compactMap { ($0.name, $0.value ?? "") } ?? []
        )

        switch url.host {
        case "myapp.com", nil:
            if path.hasPrefix("/profile/") {
                let id = String(path.dropFirst("/profile/".count))
                self = id.isEmpty ? .unknown : .profile(userID: id)
            } else if path.hasPrefix("/post/") {
                let id = String(path.dropFirst("/post/".count))
                self = id.isEmpty ? .unknown : .post(postID: id)
            } else if path.hasPrefix("/invite/") {
                let code = String(path.dropFirst("/invite/".count))
                self = .invite(code: code)
            } else { self = .unknown }
        default: self = .unknown
        }
    }
}
```

## 4. Practical Usage

```swift
import UIKit
import SwiftUI

// ── Centralised Deep Link Router ──────────────────────────────
@MainActor
class DeepLinkRouter {
    static let shared = DeepLinkRouter()
    weak var coordinator: AppCoordinator?

    func route(_ url: URL) {
        let link = DeepLink(url: url)
        route(link)
    }

    func route(_ link: DeepLink) {
        switch link {
        case .profile(let userID):
            coordinator?.showProfile(userID: userID)
        case .post(let postID):
            coordinator?.showPost(postID: postID)
        case .invite(let code):
            coordinator?.handleInvite(code: code)
        case .unknown:
            break   // ignore unrecognised links
        }
    }
}

// ── SceneDelegate — all entry points funnel to router ────────
class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    var coordinator: AppCoordinator?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession,
               options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: windowScene)
        coordinator = AppCoordinator(window: window)
        coordinator?.start()
        self.window = window
        DeepLinkRouter.shared.coordinator = coordinator

        // URL scheme link on cold launch
        if let urlContext = connectionOptions.urlContexts.first {
            DeepLinkRouter.shared.route(urlContext.url)
        }
        // Universal Link on cold launch
        connectionOptions.userActivities
            .first { $0.activityType == NSUserActivityTypeBrowsingWeb }
            .flatMap { $0.webpageURL }
            .map { DeepLinkRouter.shared.route($0) }
    }

    // Universal Link while running
    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        guard let url = userActivity.webpageURL else { return }
        DeepLinkRouter.shared.route(url)
    }

    // URL scheme while running
    func scene(_ scene: UIScene, openURLContexts contexts: Set<UIOpenURLContext>) {
        contexts.first.map { DeepLinkRouter.shared.route($0.url) }
    }

    // Home screen quick action
    func windowScene(_ windowScene: UIWindowScene,
                     performActionFor shortcutItem: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        if shortcutItem.type == "com.app.newPost" {
            coordinator?.presentNewPost()
            completionHandler(true)
        } else {
            completionHandler(false)
        }
    }
}

// ── SwiftUI — NavigationPath-based deep link handling ─────────
@MainActor
class NavigationState: ObservableObject {
    @Published var path = NavigationPath()

    func navigate(to link: DeepLink) {
        switch link {
        case .profile(let id): path.append(ProfileRoute(userID: id))
        case .post(let id):    path.append(PostRoute(postID: id))
        default: break
        }
    }
}

struct RootView: View {
    @StateObject private var nav = NavigationState()

    var body: some View {
        NavigationStack(path: $nav.path) {
            FeedView()
                .navigationDestination(for: ProfileRoute.self) { route in
                    ProfileView(userID: route.userID)
                }
                .navigationDestination(for: PostRoute.self) { route in
                    PostDetailView(postID: route.postID)
                }
        }
        .onOpenURL { url in
            nav.navigate(to: DeepLink(url: url))
        }
        .environmentObject(nav)
    }
}

// ── NSUserActivity for Handoff ────────────────────────────────
class ArticleViewController: UIViewController {
    var articleID: String = ""

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        advertiseActivity()
    }

    private func advertiseActivity() {
        let activity = NSUserActivity(activityType: "com.myapp.readArticle")
        activity.title = navigationItem.title
        activity.userInfo = ["article_id": articleID]
        activity.webpageURL = URL(string: "https://myapp.com/article/\(articleID)")
        activity.isEligibleForHandoff = true
        activity.isEligibleForSearch = true
        userActivity = activity
        activity.becomeCurrent()
    }

    override func updateUserActivityState(_ activity: NSUserActivity) {
        activity.addUserInfoEntries(from: ["article_id": articleID])
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a custom URL scheme and a Universal Link?**

A: A **custom URL scheme** (e.g., `myapp://profile/42`) is a string prefix registered in `Info.plist`. Any app can register the same scheme — there is no ownership verification. If the app is not installed, opening the URL fails silently or shows an error. **Universal Links** use standard HTTPS URLs (e.g., `https://myapp.com/profile/42`). Ownership is verified by Apple at install time via an AASA (Apple App Site Association) JSON file hosted on the domain. Only the app whose Team ID and bundle ID match the AASA file can handle the URL. If the app is not installed, the URL opens in Safari as a normal web page. Universal Links are strongly preferred for production because they are phishing-resistant, handle the not-installed case gracefully, and work seamlessly with Handoff.

**Q: What is the AASA file and where must it be hosted?**

A: The AASA (Apple App Site Association) file is a JSON document that declares which URL paths on your domain your app is entitled to handle. It must be hosted at `https://yourdomain.com/.well-known/apple-app-site-association` with no file extension, served over HTTPS with a valid CA-signed certificate. The file maps your Team ID + bundle ID to URL path patterns. iOS downloads and caches the AASA during app installation (and refreshes it periodically via Apple's CDN). If the AASA is malformed, missing, or served with an invalid certificate, Universal Links silently fall through to Safari — a common debugging frustration.

### Hard

**Q: How does Universal Link routing work when the app is not yet launched vs already running?**

A: **Not running (cold launch)**: iOS launches the app; `scene(_:willConnectTo:options:)` is called with `connectionOptions.userActivities` containing the `NSUserActivity` with `activityType == NSUserActivityTypeBrowsingWeb`. Extract `webpageURL` and route before the UI is visible — but defer actual navigation until after the window and root view controller are fully set up. **Already running (warm)**: `scene(_:continue:)` is called on the `UIWindowSceneDelegate` with the `NSUserActivity`. Route immediately. **Cold launch via custom URL scheme**: `connectionOptions.urlContexts` instead of `userActivities`. In SwiftUI, `.onOpenURL` fires in both cases, hiding the distinction. The router must handle both paths identically — the common mistake is handling only the warm path and missing cold-launch links.

**Q: Why should you never pass authentication tokens through deep link URL parameters?**

A: URL scheme parameters are visible in the URL string, which: (1) may be logged by the OS, analytics SDKs, or crash reporters; (2) can be intercepted by a malicious app that registers the same custom URL scheme; (3) appear in the device's clipboard if the user copies the link. For OAuth callbacks, use Universal Links rather than custom schemes (so no other app can intercept the callback), and exchange the code for a token server-side over HTTPS immediately. If you must use a custom scheme for OAuth (e.g., some older SDKs), use PKCE (Proof Key for Code Exchange) so a stolen code cannot be exchanged without the code verifier.

### Expert

**Q: How would you design a deep link routing system that handles all entry points (cold launch, warm launch, push notification tap, Spotlight, Handoff) in a unified way?**

A: A unified router has three components: (1) **`DeepLink` value type** that parses any URL or `NSUserActivity` into a typed enum (`case profile(userID:)`, `case post(postID:)`, etc.) with a failable initialiser. (2) **`DeepLinkRouter`** — a `@MainActor` singleton that receives any `DeepLink` and dispatches it to the current coordinator. It must tolerate being called before the coordinator is ready (queue the link and flush when the coordinator is set). (3) **Entry point adapters** in `SceneDelegate` (or SwiftUI `.onOpenURL` + `.onContinueUserActivity`) that all parse their input into a `DeepLink` and call the router. This ensures: consistent handling regardless of entry point; testability (pass a `DeepLink` directly to the router in unit tests); and correct behaviour on cold launch (link is queued, then applied once the window is ready). For NavigationStack-based SwiftUI apps, the coordinator maintains a `NavigationPath` that the router appends to — enabling multi-level deep navigation without knowing the current screen state.

## 6. Common Issues & Solutions

**Issue: Universal Links open in Safari instead of the app.**

Solution: Most commonly: (1) AASA file is not being served — check the URL, certificate, and content type. Use Apple's AASA Validator tool. (2) The URL path doesn't match any component in the AASA. (3) The Associated Domains entitlement is missing or has a typo. (4) The app was installed before the AASA was set up — reinstall the app so iOS re-fetches the AASA. (5) The user has opened the link in Safari and pressed "Open in Safari" — they've opted out; they must go to Settings → your app → Open Links to re-enable.

**Issue: Deep link fires but navigation doesn't happen — the wrong screen is shown.**

Solution: The deep link is processed before the root view controller's view hierarchy is ready. Use a small `DispatchQueue.main.async` delay or check `window?.rootViewController != nil` before navigating. For coordinator patterns, queue the pending link and apply it in `viewDidAppear` of the root view controller.

**Issue: `scene(_:continue:)` is not called for Universal Links.**

Solution: The delegate must be set as the scene's delegate in `Info.plist` (`UISceneSessionRoleApplication` → `UISceneDelegateClassName`). Also ensure the app has the Associated Domains entitlement (`applinks:yourdomain.com`) and the AASA file is correct. Test by opening the link with `open https://yourdomain.com/path` in Terminal while the Simulator is running.

## 7. Related Topics

- [App Lifecycle](app-lifecycle.md) — scene connection options deliver links on cold launch
- [Push Notifications](push-notifications.md) — routing from notification tap to deep link
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — Coordinator pattern for deep link navigation
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — NavigationPath for programmatic deep navigation
