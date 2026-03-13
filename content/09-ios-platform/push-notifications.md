# Push Notifications

## 1. Overview

Push notifications allow a server to deliver timely information to a device even when the app is not running. Apple's infrastructure for this is APNs (Apple Push Notification service) — a persistent, encrypted connection between Apple's servers and every iPhone. The iOS framework for creating, scheduling, and responding to notifications is `UserNotifications` (UNUserNotificationCenter). Modern push architecture supports alert notifications (user-visible banners, sounds, badges), silent pushes (invisible; wake app for background fetch), rich notifications (images, video via Notification Service Extension), and custom notification UIs (Notification Content Extension). Understanding APNs token management, notification categories and actions, and the extension points is essential for production push implementations.

## 2. Simple Explanation

Push notifications are like a postal service between your server and the user's device. Your server writes a letter (payload), hands it to the post office (APNs), which delivers it to the exact device (via the device token — a postal address). iOS decides whether to show the letter (based on user permission), rings a bell or shows a banner, and optionally wakes your app to process it. You can attach photos to the letter (rich notifications via a Notification Service Extension) or design a custom envelope (Notification Content Extension for a custom UI).

## 3. Deep iOS Knowledge

### APNs Architecture

```
Your Server
    │  JSON payload + device token
    ▼  (HTTP/2 + mutual TLS or token auth)
APNs Servers  ──────────────────────────────────► Device
                                                     │
                                                     ▼
                                               iOS delivers
                                               notification
```

**Device token**: a unique, APNs-assigned identifier for the (app, device) pair. Tokens can change — after app reinstall, device restore, or OS update. Always upload the latest token to your server.

**Authentication**: APNs supports two authentication methods:
- **Token-based (JWT)**: one p8 key file per team; no expiry; recommended.
- **Certificate-based**: per-app .p12 certificate; expires annually; legacy.

### Payload Structure

```json
{
  "aps": {
    "alert": {
      "title": "New Message",
      "body": "Alice: Hey, are you free tonight?"
    },
    "badge": 3,
    "sound": "default",
    "content-available": 1,
    "mutable-content": 1,
    "category": "MESSAGE_CATEGORY",
    "thread-id": "conversation-42",
    "interruption-level": "active"
  },
  "message_id": "msg_789",
  "sender_id": "user_42"
}
```

Key fields:
- `content-available: 1` — silent push; wakes app in background.
- `mutable-content: 1` — triggers Notification Service Extension to modify the notification before display.
- `category` — links to a `UNNotificationCategory` defining action buttons.
- `thread-id` — groups notifications in Notification Center.
- `interruption-level` — `passive`, `active`, `time-sensitive`, `critical` (requires entitlement).

### Requesting Permission

```swift
UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
    guard granted else { return }
    DispatchQueue.main.async {
        UIApplication.shared.registerForRemoteNotifications()
    }
}
```

Permission is requested once. If the user denies, subsequent calls don't show the dialog — use `UNUserNotificationCenter.current().getNotificationSettings` to check current status before requesting.

### Notification Categories and Actions

Categories define the set of action buttons shown on a notification:

```swift
let replyAction = UNTextInputNotificationAction(
    identifier: "REPLY_ACTION",
    title: "Reply",
    options: [],
    textInputButtonTitle: "Send",
    textInputPlaceholder: "Type a reply..."
)

let markReadAction = UNNotificationAction(
    identifier: "MARK_READ",
    title: "Mark as Read",
    options: [.authenticationRequired]  // requires device unlock
)

let messageCategory = UNNotificationCategory(
    identifier: "MESSAGE_CATEGORY",
    actions: [replyAction, markReadAction],
    intentIdentifiers: [],
    options: .customDismissAction
)

UNUserNotificationCenter.current().setNotificationCategories([messageCategory])
```

### UNUserNotificationCenterDelegate

```swift
class NotificationHandler: NSObject, UNUserNotificationCenterDelegate {

    // Called when a notification is delivered while app is in foreground
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                 willPresent notification: UNNotification,
                                 withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .badge])   // show even in foreground
    }

    // Called when user taps notification or action button
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                 didReceive response: UNNotificationResponse,
                                 withCompletionHandler completionHandler: @escaping () -> Void) {
        defer { completionHandler() }
        let userInfo = response.notification.request.content.userInfo

        switch response.actionIdentifier {
        case UNNotificationDefaultActionIdentifier:
            // User tapped the notification body
            handleDeepLink(from: userInfo)
        case "REPLY_ACTION":
            let textResponse = response as? UNTextInputNotificationResponse
            sendReply(text: textResponse?.userText ?? "", userInfo: userInfo)
        case "MARK_READ":
            markAsRead(userInfo: userInfo)
        default: break
        }
    }
}
```

### Notification Service Extension

A `UNNotificationServiceExtension` intercepts notifications with `mutable-content: 1` before display. Uses: decrypt end-to-end encrypted content, download and attach media, modify title/body.

```swift
class NotificationService: UNNotificationServiceExtension {
    var contentHandler: ((UNNotificationContent) -> Void)?
    var bestAttemptContent: UNMutableNotificationContent?

    override func didReceive(_ request: UNNotificationRequest,
                             withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void) {
        self.contentHandler = contentHandler
        bestAttemptContent = request.content.mutableCopy() as? UNMutableNotificationContent

        // Download media attachment
        guard let urlString = request.content.userInfo["image_url"] as? String,
              let url = URL(string: urlString) else {
            contentHandler(request.content); return
        }

        downloadAttachment(url: url) { [weak self] attachment in
            if let attachment { self?.bestAttemptContent?.attachments = [attachment] }
            contentHandler(self?.bestAttemptContent ?? request.content)
        }
    }

    override func serviceExtensionTimeWillExpire() {
        // Called if the extension runs out of time (~30s budget)
        contentHandler?(bestAttemptContent ?? UNNotificationContent())
    }
}
```

### Notification Content Extension

A `UNNotificationContentExtension` provides a completely custom SwiftUI/UIKit view displayed when the user long-presses or force-touches a notification. Declared in `Info.plist` with `UNNotificationExtensionCategory`.

### Local Notifications

Schedule notifications from the device without a server:

```swift
let content = UNMutableNotificationContent()
content.title = "Water your plant"
content.body = "Fern needs water today"
content.sound = .default

// Time interval trigger
let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 3600, repeats: false)
// Calendar trigger
let components = DateComponents(hour: 9, minute: 0)
let calTrigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: true)
// Location trigger
let region = CLCircularRegion(center: homeCoordinate, radius: 100, identifier: "home")
let locTrigger = UNLocationNotificationTrigger(region: region, repeats: false)

let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
try await UNUserNotificationCenter.current().add(request)
```

## 4. Practical Usage

```swift
import UserNotifications
import UIKit

// ── Push notification manager ─────────────────────────────────
class PushNotificationManager: NSObject {
    static let shared = PushNotificationManager()

    func setup() {
        UNUserNotificationCenter.current().delegate = self
        registerCategories()
    }

    func requestPermission(completion: @escaping (Bool) -> Void) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            switch settings.authorizationStatus {
            case .authorized, .provisional:
                DispatchQueue.main.async {
                    UIApplication.shared.registerForRemoteNotifications()
                    completion(true)
                }
            case .notDetermined:
                UNUserNotificationCenter.current()
                    .requestAuthorization(options: [.alert, .badge, .sound]) { granted, _ in
                        DispatchQueue.main.async {
                            if granted { UIApplication.shared.registerForRemoteNotifications() }
                            completion(granted)
                        }
                    }
            case .denied, .ephemeral:
                completion(false)
            @unknown default:
                completion(false)
            }
        }
    }

    func registerDeviceToken(_ tokenData: Data) {
        let token = tokenData.map { String(format: "%02.2hhx", $0) }.joined()
        Task { try? await APIClient.shared.registerPushToken(token) }
    }

    private func registerCategories() {
        // Message category with reply + mark-read
        let reply = UNTextInputNotificationAction(
            identifier: "REPLY",
            title: "Reply",
            options: [],
            textInputButtonTitle: "Send",
            textInputPlaceholder: "Message..."
        )
        let markRead = UNNotificationAction(identifier: "MARK_READ", title: "Mark Read", options: [])
        let messageCategory = UNNotificationCategory(
            identifier: "MESSAGE",
            actions: [reply, markRead],
            intentIdentifiers: [],
            options: []
        )

        // Post like category
        let viewPost = UNNotificationAction(identifier: "VIEW_POST", title: "View Post", options: [.foreground])
        let likeCategory = UNNotificationCategory(
            identifier: "LIKE",
            actions: [viewPost],
            intentIdentifiers: [],
            options: []
        )

        UNUserNotificationCenter.current().setNotificationCategories([messageCategory, likeCategory])
    }
}

// ── UNUserNotificationCenterDelegate ─────────────────────────
extension PushNotificationManager: UNUserNotificationCenterDelegate {

    // Foreground presentation
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                 willPresent notification: UNNotification,
                                 withCompletionHandler handler: @escaping (UNNotificationPresentationOptions) -> Void) {
        handler([.banner, .sound, .badge])
    }

    // Response handling
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                 didReceive response: UNNotificationResponse,
                                 withCompletionHandler handler: @escaping () -> Void) {
        defer { handler() }
        let info = response.notification.request.content.userInfo

        switch response.actionIdentifier {
        case UNNotificationDefaultActionIdentifier:
            if let type = info["type"] as? String {
                DeepLinkRouter.shared.route(type: type, payload: info)
            }
        case "REPLY":
            let text = (response as? UNTextInputNotificationResponse)?.userText ?? ""
            guard let conversationId = info["conversation_id"] as? String else { break }
            Task { try? await MessageService.shared.sendReply(text: text, to: conversationId) }
        case "MARK_READ":
            guard let messageId = info["message_id"] as? String else { break }
            Task { try? await MessageService.shared.markRead(messageId: messageId) }
        default: break
        }
    }
}

// ── Notification Service Extension (separate target) ─────────
class NotificationService: UNNotificationServiceExtension {
    var contentHandler: ((UNNotificationContent) -> Void)?
    var bestAttemptContent: UNMutableNotificationContent?

    override func didReceive(_ request: UNNotificationRequest,
                             withContentHandler handler: @escaping (UNNotificationContent) -> Void) {
        contentHandler = handler
        guard let content = request.content.mutableCopy() as? UNMutableNotificationContent else {
            handler(request.content); return
        }
        bestAttemptContent = content

        // Decrypt E2E message body
        if let encrypted = content.userInfo["encrypted_body"] as? String {
            content.body = E2EDecryption.decrypt(encrypted) ?? content.body
        }

        // Download thumbnail attachment
        guard let urlString = content.userInfo["thumbnail_url"] as? String,
              let url = URL(string: urlString) else {
            handler(content); return
        }

        URLSession.shared.downloadTask(with: url) { localURL, _, _ in
            if let localURL,
               let attachment = try? UNNotificationAttachment(identifier: "thumbnail", url: localURL) {
                content.attachments = [attachment]
            }
            handler(content)
        }.resume()
    }

    override func serviceExtensionTimeWillExpire() {
        contentHandler?(bestAttemptContent ?? UNNotificationContent())
    }
}

// ── Managing pending / delivered notifications ────────────────
extension PushNotificationManager {
    // Remove delivered notifications for a specific conversation
    func clearNotifications(for conversationId: String) {
        UNUserNotificationCenter.current().getDeliveredNotifications { notifications in
            let toRemove = notifications
                .filter { ($0.request.content.userInfo["conversation_id"] as? String) == conversationId }
                .map { $0.request.identifier }
            UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: toRemove)
        }
    }

    // Update badge count
    func updateBadge(to count: Int) {
        UNUserNotificationCenter.current().setBadgeCount(count)
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the APNs device token and why might it change?**

A: The APNs device token is a unique identifier assigned by Apple that represents the (app, device) combination. Your server uses it to address push notifications to a specific device. The token can change when: the app is uninstalled and reinstalled, the device is restored from backup, the app is transferred to a different Apple Developer account, or (rarely) after a major iOS update. Your app must register for remote notifications at every launch (`UIApplication.shared.registerForRemoteNotifications()`) and upload the latest token to your server in `application(_:didRegisterForRemoteNotificationsWithDeviceToken:)`. If your server sends a push to an old, invalid token, APNs returns a `BadDeviceToken` error — your server should remove the stale token.

**Q: What is `mutable-content` and when would you use a Notification Service Extension?**

A: Setting `mutable-content: 1` in the APNs payload tells iOS to invoke a Notification Service Extension before displaying the notification. The extension has ~30 seconds to modify the `UNMutableNotificationContent`. Use cases: (1) **End-to-end encryption** — the payload carries an encrypted body; the extension decrypts it using a locally stored key before display (this is how WhatsApp/Signal handle E2E push). (2) **Rich media attachment** — download an image or video and attach it to the notification. (3) **Localisation** — the server sends a key; the extension looks up the localised string. (4) **Tracking** — increment an unread count in the shared app group before the notification is displayed. Without `mutable-content: 1`, the extension is never invoked.

### Hard

**Q: How does notification delivery change based on the app's foreground/background state?**

A: **App not running / background / suspended**: APNs delivers the notification; iOS displays it as a banner, sound, and/or badge without calling any app code. When the user taps, the app launches and `userNotificationCenter(_:didReceive:)` fires. **App in background with silent push** (`content-available: 1`): `application(_:didReceiveRemoteNotification:fetchCompletionHandler:)` fires, giving ~30 seconds of background execution. **App in foreground**: the notification is NOT shown automatically — iOS calls `userNotificationCenter(_:willPresent:withCompletionHandler:)` and your code decides the presentation options. Call `completionHandler([.banner, .sound])` to show it, or `completionHandler([])` to suppress it and handle the data silently. This delegate method fires only when the app is in the foreground.

**Q: What is notification grouping via `thread-id` and how do you remove notifications for a specific thread?**

A: `thread-id` is a string in the APNs payload that groups related notifications in Notification Center — e.g., all messages from the same conversation share a `thread-id` of the conversation ID. iOS stacks grouped notifications under a single header. To remove all displayed notifications for a thread (e.g., when the user reads the conversation): call `UNUserNotificationCenter.current().getDeliveredNotifications`, filter by your conversation ID in `userInfo`, collect their `request.identifier` values, and call `removeDeliveredNotifications(withIdentifiers:)`. For pending (scheduled but not yet delivered) notifications, use `removePendingNotificationRequests(withIdentifiers:)`.

### Expert

**Q: Design a push notification architecture for a chat app that supports E2E encryption and message preview in the lock screen.**

A: The challenge: the server cannot see message content (E2E), yet iOS must display a meaningful preview. Architecture: (1) **Server payload** contains the encrypted ciphertext, sender name (unencrypted metadata), and a hint like "New message from Alice" as the fallback body. `mutable-content: 1` is set. (2) **Notification Service Extension** receives the notification, retrieves the E2E decryption key from the Keychain (the extension shares the Keychain group with the main app), decrypts the ciphertext, and sets `content.body` to the plaintext. If decryption fails (key not available, device just restored), the fallback body "New message from Alice" is shown. (3) **Key management**: on every app launch, ensure the current device's private key is in the Keychain with `kSecAttrAccessibleAfterFirstUnlock` (so the extension can access it after first device unlock post-boot). (4) **Extension budget**: the extension has ~30 seconds. Decryption is synchronous and fast; no network calls needed. (5) **Notification Content Extension**: optional — shows the last N messages inline for quick reply without opening the app. The content extension reads from the shared App Group database.

## 6. Common Issues & Solutions

**Issue: Push notifications work in development but not production.**

Solution: Ensure your server is using the Production APNs endpoint (`api.push.apple.com`) rather than the sandbox endpoint (`api.sandbox.push.apple.com`). Also verify the p8 key or certificate is the production one. App Store and TestFlight builds use the production APNs environment; debug builds use sandbox.

**Issue: `userNotificationCenter(_:didReceive:)` is never called when the app is in the foreground.**

Solution: Implement `userNotificationCenter(_:willPresent:)` and set `UNUserNotificationCenter.current().delegate` before the app finishes launching (in `AppDelegate` or in the `App` init). `didReceive` only fires after the user interacts with the notification — `willPresent` fires for delivery in the foreground.

**Issue: Device token is nil or `registerForRemoteNotifications` fails silently.**

Solution: Ensure the Push Notifications capability is enabled in Xcode's Signing & Capabilities, and the provisioning profile includes the `aps-environment` entitlement. On Simulator, push notifications require iOS 16+ and specific Xcode tooling — test on a physical device for reliable registration.

**Issue: Notification Service Extension never fires.**

Solution: The payload must include `mutable-content: 1` (as an integer, not a string or boolean). The extension must be a separate target in the app, with its own bundle ID (typically `com.app.NotificationService`), and its `NSExtensionPrincipalClass` must point to your `UNNotificationServiceExtension` subclass in the extension's `Info.plist`.

## 7. Related Topics

- [App Lifecycle](app-lifecycle.md) — device token registration in AppDelegate; silent push handling
- [Background Tasks](background-tasks.md) — silent push vs BGAppRefreshTask for background wakeup
- [Deep Links & Universal Links](deep-links-universal-links.md) — routing from notification tap to in-app screen
- [Keychain](../08-data-persistence/keychain.md) — storing E2E keys accessible to Notification Service Extension
