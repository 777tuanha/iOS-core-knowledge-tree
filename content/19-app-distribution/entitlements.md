# Entitlements

## 1. Overview

Entitlements are key-value pairs embedded in the app binary at build time that declare which platform capabilities the app requires. They act as a contract between the app and the OS: iOS will only grant a capability (push notifications, Keychain access group sharing, App Groups, iCloud, background modes) if the entitlement is both present in the binary and matched by the provisioning profile. Entitlements are defined in a `.entitlements` file (a plist) in the Xcode project and are enabled per-target in Xcode's Signing & Capabilities tab. Each capability must also be enabled in the App ID on the developer portal — the provisioning profile reflects those permissions. Entitlements cross-cut code signing, app capabilities, and inter-process communication: App Groups enable data sharing between extensions and the host app; Keychain access groups enable credential sharing between multiple apps from the same team.

## 2. Simple Explanation

Entitlements are like entries on a backstage pass. The pass (provisioning profile) lists every room you're allowed to enter. The binary has its own list of rooms it claims to need. iOS compares the two lists at install time: if the binary asks for a room (entitlement) that's not on the pass, installation fails. If the pass lists rooms the binary doesn't need, that's fine — but unused capabilities don't help anyone and add to the audit surface.

## 3. Deep iOS Knowledge

### Entitlements File

Xcode manages the `.entitlements` plist automatically when you toggle capabilities in the Signing & Capabilities tab. You can also edit it directly.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Push Notifications -->
    <key>aps-environment</key>
    <string>production</string>           <!-- "development" for debug builds -->

    <!-- Keychain Sharing -->
    <key>keychain-access-groups</key>
    <array>
        <string>$(AppIdentifierPrefix)com.acme.App</string>
        <string>$(AppIdentifierPrefix)com.acme.shared</string>
    </array>

    <!-- App Groups -->
    <key>com.apple.security.application-groups</key>
    <array>
        <string>group.com.acme.App</string>
    </array>

    <!-- Associated Domains (Universal Links / Sign in with Apple) -->
    <key>com.apple.developer.associated-domains</key>
    <array>
        <string>applinks:acme.com</string>
        <string>webcredentials:acme.com</string>
    </array>

    <!-- Background Modes -->
    <key>UIBackgroundModes</key>
    <array>
        <string>remote-notification</string>
        <string>fetch</string>
    </array>
</dict>
</plist>
```

### Push Notifications

Push notifications require the `aps-environment` entitlement with value `development` (debug builds, APNs sandbox) or `production` (release builds, APNs production). In Xcode, enable Push Notifications under Signing & Capabilities — this adds the entitlement and enables it in the App ID.

**Registration flow:**

```swift
import UserNotifications

func requestPushPermission() {
    UNUserNotificationCenter.current().requestAuthorization(
        options: [.alert, .sound, .badge]
    ) { granted, error in
        guard granted else { return }
        DispatchQueue.main.async {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }
}

// AppDelegate — receives the device token
func application(_ application: UIApplication,
                 didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
    // Convert to hex string and send to server
    let tokenString = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
    // Upload tokenString to your push service
}
```

### Keychain Access Groups

By default, an app's Keychain items are in a private access group accessible only to that app. The `keychain-access-groups` entitlement allows multiple apps (with the same team ID prefix) to share Keychain items.

```swift
import Security

// Storing a credential in a shared access group
func saveSharedCredential(_ token: String, accessGroup: String) throws {
    let tokenData = Data(token.utf8)
    let query: [String: Any] = [
        kSecClass as String:           kSecClassGenericPassword,
        kSecAttrService as String:     "com.acme.authToken",
        kSecAttrAccount as String:     "currentUser",
        kSecAttrAccessGroup as String: accessGroup,  // e.g. "TEAMID.com.acme.shared"
        kSecValueData as String:       tokenData,
        kSecAttrAccessible as String:  kSecAttrAccessibleAfterFirstUnlock
    ]
    let status = SecItemAdd(query as CFDictionary, nil)
    guard status == errSecSuccess || status == errSecDuplicateItem else {
        throw KeychainError.writeFailed(status)
    }
}

// Reading from the shared group — works from any app in the same team
// with the same keychain-access-groups entitlement entry
func readSharedCredential(accessGroup: String) throws -> String? {
    let query: [String: Any] = [
        kSecClass as String:            kSecClassGenericPassword,
        kSecAttrService as String:      "com.acme.authToken",
        kSecAttrAccount as String:      "currentUser",
        kSecAttrAccessGroup as String:  accessGroup,
        kSecReturnData as String:       true,
        kSecMatchLimit as String:       kSecMatchLimitOne
    ]
    var result: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess, let data = result as? Data else { return nil }
    return String(data: data, encoding: .utf8)
}

enum KeychainError: Error { case writeFailed(OSStatus) }
```

### App Groups

App Groups allow data sharing (UserDefaults, files) between an app and its extensions (widgets, notification service extensions, share extensions) using a shared container.

```swift
import Foundation

// App Group identifier from entitlements
let appGroupID = "group.com.acme.App"

// Shared UserDefaults — accessible from the app AND any extension in the same group
let sharedDefaults = UserDefaults(suiteName: appGroupID)!

// Writing from the app
sharedDefaults.set("john@acme.com", forKey: "loggedInEmail")
sharedDefaults.synchronize()   // ensures write is flushed before extension reads

// Reading from a Widget extension (same App Group)
let email = UserDefaults(suiteName: appGroupID)?.string(forKey: "loggedInEmail")

// Shared file container — for larger data (e.g., shared Core Data store)
let sharedContainerURL = FileManager.default
    .containerURL(forSecurityApplicationGroupIdentifier: appGroupID)!
let dbURL = sharedContainerURL.appendingPathComponent("SharedDatabase.sqlite")
```

### Associated Domains

Required for Universal Links (deep links via HTTPS) and Sign in with Apple. The `associated-domains` entitlement lists the domains the app claims. iOS fetches `https://<domain>/.well-known/apple-app-site-association` to verify the app-domain relationship.

```swift
// Universal Link handling in SceneDelegate
func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
    guard userActivity.activityType == NSUserActivityTypeBrowsingWeb,
          let url = userActivity.webpageURL else { return }
    // Route the deep link URL
    AppCoordinator.shared.handleDeepLink(url)
}
```

### Entitlement Per-Configuration

Development builds need `aps-environment = development`; release builds need `production`. In Xcode, configure this with xcconfig files or build setting conditions:

```
// Use different entitlements files per configuration:
CODE_SIGN_ENTITLEMENTS[config=Debug] = MyApp/Debug.entitlements
CODE_SIGN_ENTITLEMENTS[config=Release] = MyApp/Release.entitlements
```

## 4. Practical Usage

```swift
import UserNotifications
import Foundation

// ── Push Notification Manager ──────────────────────────────────
final class PushNotificationManager {

    static let shared = PushNotificationManager()
    private init() {}

    // Call from AppDelegate.applicationDidFinishLaunching
    func setup() {
        UNUserNotificationCenter.current().delegate = self
    }

    func requestAuthorisation() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .badge, .sound])
            if granted {
                await MainActor.run {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
            return granted
        } catch {
            return false
        }
    }
}

extension PushNotificationManager: UNUserNotificationCenterDelegate {
    // Foreground notification display
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    // User tapped a notification
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        // Handle deep link from push payload
        if let urlString = userInfo["deeplink"] as? String,
           let url = URL(string: urlString) {
            AppCoordinator.shared.handleDeepLink(url)
        }
        completionHandler()
    }
}

// ── App Group shared storage ───────────────────────────────────
struct SharedAppState {
    private static let suite = UserDefaults(suiteName: "group.com.acme.App")!

    static var lastViewedArticleID: String? {
        get { suite.string(forKey: "lastArticle") }
        set { suite.set(newValue, forKey: "lastArticle") }
    }

    // Shared file URL — for Core Data, SQLite, or JSON written by app and read by widget
    static var sharedDatabaseURL: URL {
        FileManager.default
            .containerURL(forSecurityApplicationGroupIdentifier: "group.com.acme.App")!
            .appendingPathComponent("App.sqlite")
    }
}

// Placeholder to avoid compile error:
final class AppCoordinator {
    static let shared = AppCoordinator()
    func handleDeepLink(_ url: URL) {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is an entitlement and how does it differ from a permission (e.g., location access)?**

A: An **entitlement** is a build-time declaration embedded in the binary that grants access to a platform capability. It's checked by iOS at install time by comparing the binary's entitlements against the provisioning profile. Examples: `aps-environment` (push notifications), `keychain-access-groups` (Keychain sharing), App Groups. An entitlement is an all-or-nothing capability grant — there's no runtime prompt; either the app has it or it doesn't. A **permission** (e.g., `NSLocationWhenInUseUsageDescription`) is a runtime request the app makes to the user via a system dialog. The user can grant or revoke permissions at any time in Settings. Permissions also require entitlements in some cases (e.g., push notifications require both the `aps-environment` entitlement and the user granting notification permission at runtime), but most permissions (location, camera, contacts) require only the `Info.plist` usage description key, no entitlement.

**Q: How do App Groups enable data sharing between an app and its widget extension?**

A: App Groups create a shared file container on disk accessible to multiple processes from the same developer team. Both the host app and the widget extension declare the same App Group identifier (`group.com.acme.App`) in their respective entitlements. They can then: (1) share `UserDefaults` using `UserDefaults(suiteName: "group.com.acme.App")` — both processes read/write the same defaults database; (2) share files using `FileManager.default.containerURL(forSecurityApplicationGroupIdentifier:)` — e.g., a Core Data SQLite file written by the app and read by the widget for timeline entries; (3) share `NSUbiquitousKeyValueStore` for iCloud key-value sync (iCloud entitlement needed). Without App Groups, each extension runs in a sandboxed container that cannot access the host app's container.

### Hard

**Q: How do you configure different push notification environments (APNs sandbox vs production) for debug and release builds?**

A: The `aps-environment` entitlement controls which APNs environment the app communicates with. Development/debug builds must use `development` (APNs sandbox) — using `production` in a debug build fails silently (device tokens are not interchangeable between environments). Release builds must use `production`. The correct approach: maintain two separate `.entitlements` files — `Debug.entitlements` with `aps-environment = development` and `Release.entitlements` with `aps-environment = production`. In Xcode build settings, set `CODE_SIGN_ENTITLEMENTS[config=Debug]` and `[config=Release]` to point to the respective files. Both App IDs (if using separate app IDs per environment) or the same App ID (with a single push certificate covering both environments) can be used. APNs HTTP/2 push certificates are environment-specific — the development push certificate only works with APNs sandbox; the production push certificate only works with APNs production. Ensure your push backend also uses the correct certificate for each environment.

**Q: What is `keychain-access-groups` and when would you use it across multiple apps?**

A: `keychain-access-groups` is an entitlement that lists Keychain access group identifiers. By default, each app has one private access group (`$(AppIdentifierPrefix)$(CFBundleIdentifier)`) accessible only to itself. Adding additional groups to this entitlement allows sharing Keychain items between multiple apps that are: (a) from the same development team (same Team ID prefix), and (b) all have the same access group listed in their entitlements. Typical use case: a company ships a main app (`com.acme.App`) and a companion extension app (`com.acme.Keyboard`). After the user logs in via the main app, the auth token is stored in a shared Keychain group (`TEAMID.com.acme.shared`). The keyboard extension reads the token from the same group without requiring the user to log in again. Another use case: enterprise apps where multiple separate apps (separate bundle IDs, separate App Store entries) need to share credentials without server round-trips.

### Expert

**Q: Your app uses a Notification Service Extension to decrypt push content end-to-end. What entitlements does each process need and how do you share the decryption key securely?**

A: Three components with separate entitlements: (1) **Host app** — `aps-environment = production`, `keychain-access-groups` including a shared group (e.g., `TEAMID.com.acme.shared`), App Groups (`group.com.acme.App`). The app stores the user's decryption key (e.g., a symmetric key or private key) in the Keychain under the shared access group when the user logs in. (2) **Notification Service Extension** — same `aps-environment = production` (extensions inherit the host's push environment), same `keychain-access-groups` shared group, same App Groups. The extension reads the decryption key from the shared Keychain at `UNNotificationServiceExtension.didReceive(_:withContentHandler:)`. (3) **Key access**: use `kSecAttrAccessible = kSecAttrAccessibleAfterFirstUnlock` so the Keychain item is available even when the device is locked (the extension runs when the device may be locked). Do NOT use `kSecAttrAccessibleWhenUnlocked` — the extension may run before the user unlocks the device after a reboot. Architecture note: the shared Keychain group must be explicitly listed in both the app and extension entitlements files; both provisioning profiles must include the shared Keychain group (configured in the App ID on the developer portal). Both the app and extension must have the same team ID.

## 6. Common Issues & Solutions

**Issue: Push notifications work in debug but not in release builds.**

Solution: Check that `aps-environment` is `development` in the Debug entitlements file and `production` in the Release entitlements file. Confirm the backend push service is using the production APNs certificate/auth key for production builds and the sandbox certificate/auth key for debug. The device token from a production-signed app cannot be used with the APNs sandbox endpoint and vice versa — they are issued by different APNs environments.

**Issue: Keychain sharing fails — items written by the app cannot be read by the extension.**

Solution: Verify both targets have identical access group strings (including the Team ID prefix) in their entitlements files. Check that the shared Keychain group is enabled in the App ID in the developer portal and that both provisioning profiles have been regenerated after enabling it. Also verify the `kSecAttrAccessGroup` value in the Keychain query exactly matches the entitlement string — including the team ID prefix (`TEAMID.com.acme.shared`, not just `com.acme.shared`). The `$(AppIdentifierPrefix)` build setting resolves to the team ID at build time; in code, use the full expanded string.

## 7. Related Topics

- [Code Signing](code-signing.md) — provisioning profiles carry entitlement permissions
- [Distribution](distribution.md) — entitlements must match App ID for App Store submission
- [Security — Data Security](../14-security/data-security.md) — Keychain API for storing credentials
- [iOS Platform — Push Notifications](../09-ios-platform/background-modes.md) — push delivery pipeline
