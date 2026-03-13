# UserDefaults

## 1. Overview

`UserDefaults` is Apple's key-value store for persisting small amounts of data — user preferences, feature flags, onboarding state, and lightweight scalars. It stores data as a property list (plist) file in the app sandbox's `Library/Preferences/` directory and keeps a synchronised in-memory cache so reads are fast. `UserDefaults` is not a database: it loads the entire domain into memory at launch and flushes the whole plist atomically on write. This makes it unsuitable for large or frequently-mutating data. For iOS 14+ and SwiftUI, `@AppStorage` provides a property-wrapper layer over `UserDefaults` with automatic view invalidation.

## 2. Simple Explanation

Think of `UserDefaults` as a sticky-note board in your kitchen. You write short reminders ("dark mode: on", "last login: Jan 15") on individual sticky notes. When you need to check a preference, you glance at the board — it's always visible in the room (in memory). The entire board is saved to a single paper (plist file) whenever you make changes. Because the whole board is one piece of paper, it would be impractical to write a novel on sticky notes — they're for quick, small reminders, not detailed records.

## 3. Deep iOS Knowledge

### Storage Mechanism

`UserDefaults` serialises values to a plist dictionary keyed by `String`. The plist is stored in `<App Sandbox>/Library/Preferences/<bundle-id>.plist`. At launch, the system reads the plist into an in-memory cache (`UserDefaults` object). Reads are served from memory; writes go to memory immediately and are flushed to disk on a background thread (or when the app moves to the background).

**Supported value types** (plist-compatible): `Bool`, `Int`, `Float`, `Double`, `String`, `Data`, `Date`, `URL`, `Array`, `Dictionary`, and `NSNumber`. Custom types must be encoded to `Data` first.

### Standard vs Suite

| Type | Usage | File location |
|------|-------|--------------|
| `UserDefaults.standard` | App-specific preferences | `<bundle-id>.plist` |
| `UserDefaults(suiteName:)` | Shared between app and extensions (App Group) | `<suite-name>.plist` in group container |

App Groups require an entitlement (`com.apple.security.application-groups`) and the same suite name in both the app and its extensions (widget, share extension, etc.).

### @AppStorage (SwiftUI)

`@AppStorage` is a property wrapper that reads from and writes to `UserDefaults` and triggers SwiftUI view updates on change:

```swift
@AppStorage("is_dark_mode") var isDarkMode: Bool = false
@AppStorage("selected_tab", store: UserDefaults(suiteName: "group.com.app"))
var selectedTab: Int = 0
```

Supported types: `Bool`, `Int`, `Double`, `String`, `URL`, `Data`, and `RawRepresentable` where `RawValue` is one of these.

### @Observable and UserDefaults

With the `@Observable` macro (iOS 17+), persist observable properties with the `@ObservationIgnored` + `UserDefaults` pattern, or use a dedicated `UserDefaultsBacked` property wrapper.

### Thread Safety

`UserDefaults` is **thread-safe for reads and writes** from any thread. The in-memory cache is protected by an internal lock. However, you should not rely on writes being immediately durable — they are flushed asynchronously. Call `synchronize()` only if you need immediate disk flush (e.g., before a crash in a CLI tool). In a typical iOS app, `synchronize()` is unnecessary and deprecated in spirit.

### Key Naming and Organisation

Use reverse-DNS style keys to avoid collisions:
```
"com.myapp.onboarding.hasSeenWelcome"
"com.myapp.user.preferredLanguage"
```

Group related keys in an extension or enum to prevent key string duplication:

```swift
extension UserDefaults {
    enum Key {
        static let hasSeenOnboarding = "com.myapp.hasSeenOnboarding"
        static let preferredTheme    = "com.myapp.preferredTheme"
        static let badgeCount        = "com.myapp.badgeCount"
    }
}
```

### Storing Custom Codable Types

`UserDefaults` cannot store arbitrary types directly. Encode them to `Data`:

```swift
extension UserDefaults {
    func setCodable<T: Encodable>(_ value: T, forKey key: String) {
        let data = try? JSONEncoder().encode(value)
        set(data, forKey: key)
    }

    func codable<T: Decodable>(_ type: T.Type, forKey key: String) -> T? {
        guard let data = data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
}
```

### What NOT to Store in UserDefaults

- **Sensitive data** (passwords, tokens, keys) — the plist is not encrypted; use Keychain instead.
- **Large data** (images, documents) — the entire plist loads into memory; use the file system.
- **Frequently-mutating counters** at high frequency — every write triggers a disk flush; use an in-memory counter and persist periodically.
- **Complex relational data** — use Core Data or SQLite.

## 4. Practical Usage

```swift
import Foundation
import SwiftUI

// ── Key namespace to avoid string duplication ──────────────────
extension UserDefaults {
    enum Key: String {
        case hasSeenOnboarding   = "com.app.hasSeenOnboarding"
        case preferredTheme      = "com.app.preferredTheme"
        case lastSyncDate        = "com.app.lastSyncDate"
        case userId              = "com.app.userId"
        case notificationBadge   = "com.app.notificationBadge"
    }

    // Typed accessors
    var hasSeenOnboarding: Bool {
        get { bool(forKey: Key.hasSeenOnboarding.rawValue) }
        set { set(newValue, forKey: Key.hasSeenOnboarding.rawValue) }
    }

    var lastSyncDate: Date? {
        get { object(forKey: Key.lastSyncDate.rawValue) as? Date }
        set { set(newValue, forKey: Key.lastSyncDate.rawValue) }
    }
}

// ── @AppStorage in SwiftUI ────────────────────────────────────
enum AppTheme: String, CaseIterable {
    case system, light, dark
}

struct SettingsView: View {
    @AppStorage("com.app.preferredTheme") private var theme: String = AppTheme.system.rawValue
    @AppStorage("com.app.notificationBadge") private var badgeCount: Int = 0

    var body: some View {
        Form {
            Picker("Theme", selection: $theme) {
                ForEach(AppTheme.allCases, id: \.rawValue) { t in
                    Text(t.rawValue.capitalized).tag(t.rawValue)
                }
            }
            Text("Badge count: \(badgeCount)")
            Button("Reset badge") { badgeCount = 0 }
        }
    }
}

// ── App Group Suite (shared with widget extension) ────────────
extension UserDefaults {
    static let appGroup = UserDefaults(suiteName: "group.com.myapp")!
}

// Widget reads the same value the app writes:
UserDefaults.appGroup.set(42, forKey: "widgetData")
let widgetValue = UserDefaults.appGroup.integer(forKey: "widgetData")

// ── Storing Codable types ──────────────────────────────────────
struct UserProfile: Codable {
    let id: String
    let displayName: String
    let avatarURL: URL?
}

extension UserDefaults {
    var cachedProfile: UserProfile? {
        get { codable(UserProfile.self, forKey: "com.app.cachedProfile") }
        set { setCodable(newValue, forKey: "com.app.cachedProfile") }
    }

    func setCodable<T: Encodable>(_ value: T?, forKey key: String) {
        guard let value else { removeObject(forKey: key); return }
        set(try? JSONEncoder().encode(value), forKey: key)
    }

    func codable<T: Decodable>(_ type: T.Type, forKey key: String) -> T? {
        guard let data = data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
}

// ── Observing changes with Combine ───────────────────────────
import Combine

class PreferenceObserver: ObservableObject {
    @Published var hasSeenOnboarding: Bool

    private var cancellable: AnyCancellable?

    init(defaults: UserDefaults = .standard) {
        hasSeenOnboarding = defaults.bool(forKey: UserDefaults.Key.hasSeenOnboarding.rawValue)

        // KVO publisher on UserDefaults
        cancellable = NotificationCenter.default
            .publisher(for: UserDefaults.didChangeNotification)
            .map { _ in defaults.bool(forKey: UserDefaults.Key.hasSeenOnboarding.rawValue) }
            .receive(on: DispatchQueue.main)
            .assign(to: \.hasSeenOnboarding, on: self)
    }
}

// ── Resetting to defaults (useful in testing / logout) ────────
func resetUserDefaults() {
    let domain = Bundle.main.bundleIdentifier!
    UserDefaults.standard.removePersistentDomain(forName: domain)
    UserDefaults.standard.synchronize()
}

// ── Feature flags backed by UserDefaults ──────────────────────
@propertyWrapper
struct UserDefault<T> {
    let key: String
    let defaultValue: T
    let store: UserDefaults

    init(_ key: String, defaultValue: T, store: UserDefaults = .standard) {
        self.key = key
        self.defaultValue = defaultValue
        self.store = store
    }

    var wrappedValue: T {
        get { store.object(forKey: key) as? T ?? defaultValue }
        set { store.set(newValue, forKey: key) }
    }
}

enum FeatureFlags {
    @UserDefault("ff.newFeedLayout", defaultValue: false)
    static var newFeedLayout: Bool

    @UserDefault("ff.videoAutoplay", defaultValue: true)
    static var videoAutoplay: Bool
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is UserDefaults and what types of data should you store in it?**

A: `UserDefaults` is a key-value store backed by a plist file in the app's `Library/Preferences/` directory. It keeps an in-memory cache for fast reads and flushes changes to disk asynchronously. You should store: user preferences (theme, language), feature flags, onboarding completion flags, and small scalar values like last-used tab index or badge counts. The data must be plist-compatible: `Bool`, `Int`, `Double`, `String`, `Data`, `Date`, `URL`, `Array`, or `Dictionary`. For custom types, encode them to `Data` with `JSONEncoder` first. You should NOT store sensitive data (use Keychain), large binary data (use the file system), or structured relational data (use Core Data / SQLite).

**Q: How do you share UserDefaults data between an iOS app and a widget extension?**

A: Create a `UserDefaults` with a shared App Group suite name: `UserDefaults(suiteName: "group.com.myapp")`. Both the app target and the extension target must have the App Group entitlement configured with the same identifier in Xcode's Signing & Capabilities. Reads and writes on the suite-named instance go to the shared group container (`Library/Preferences/<suite-name>.plist`) rather than the app's private container, making the data visible to both processes. In SwiftUI, pass the suite to `@AppStorage`: `@AppStorage("key", store: UserDefaults(suiteName: "group.com.myapp"))`.

### Hard

**Q: Why is storing large objects in UserDefaults a performance problem?**

A: `UserDefaults` loads the entire plist domain into memory at app launch and keeps it there. Every read is an in-memory dictionary lookup — fast. But every write atomically serialises the entire domain back to disk as a single plist file. If the plist is large (hundreds of KB), this means: (1) Slower launch — the OS must deserialise the plist into memory. (2) Larger write amplification — changing one boolean re-writes the entire file. (3) Memory waste — the full content stays resident for the app's lifetime. The plist format itself is also inefficient for large binary payloads. For anything larger than a few KB, store a reference (file path or record ID) in UserDefaults and keep the actual data in the file system or a database.

**Q: What is the difference between `UserDefaults.standard` and a suite-named instance?**

A: `UserDefaults.standard` stores data in the app's private `Library/Preferences/<bundle-id>.plist`, inaccessible to other processes. A suite-named instance (`UserDefaults(suiteName: "group.com.myapp")`) stores data in the App Group's shared container, accessible to the app and all extensions in the same group. The suite-named instance also reads from multiple domains in order: the provided suite, then `.standard`, then system defaults — so it can be used to override standard defaults for testing or multi-tenancy. One important detail: if `suiteName` is the app's own bundle ID, the call returns `nil` and `standard` is used instead.

### Expert

**Q: How would you design a type-safe, testable abstraction over UserDefaults?**

A: Define a protocol that mirrors the necessary operations (get/set for each key type), create a concrete implementation backed by `UserDefaults`, and a mock implementation backed by an in-memory dictionary for tests. Key design decisions: (1) Use an enum for key names to prevent string duplication and enable exhaustive handling. (2) Expose typed properties via computed vars on the protocol rather than raw `Any` accessors. (3) Inject the dependency into view models and services rather than accessing `UserDefaults.standard` directly — this makes tests deterministic since the mock starts empty. (4) For `@AppStorage` in SwiftUI views, accept that `@AppStorage` cannot be easily mocked; move preference-dependent logic into the ViewModel which uses the injectable protocol. This way SwiftUI views remain thin (just display the ViewModel's `@Published` state) and all logic is testable.

## 6. Common Issues & Solutions

**Issue: Data written in the app is not visible in the widget extension.**

Solution: The app and extension are using separate `UserDefaults` domains. Switch both to `UserDefaults(suiteName: "group.com.myapp")` and verify the App Group entitlement is active on both targets in Xcode.

**Issue: `@AppStorage` value is not updating the SwiftUI view when changed from code.**

Solution: `@AppStorage` observes the `UserDefaults` key via KVO. Ensure the value is set on the **same `UserDefaults` instance and store** as the `@AppStorage` declaration. If you write via `UserDefaults.standard.set(...)` but `@AppStorage` uses a custom store, they won't sync.

**Issue: Sensitive token accidentally stored in UserDefaults is readable from the file system.**

Solution: Move it to the Keychain immediately. The plist file in `Library/Preferences/` is not encrypted (only protected by the sandbox and file system permissions). The Keychain uses hardware-backed AES encryption and is the correct location for all credentials, tokens, and cryptographic keys.

**Issue: UserDefaults changes are lost after the app is force-quit.**

Solution: This is rare but can occur if the app is killed before the background flush completes. For critical state that must survive force-quit, call `UserDefaults.standard.synchronize()` immediately after writing. In modern iOS, `synchronize()` is mostly a no-op as the OS manages flush timing — the real fix is to not store critical transactional state in UserDefaults; use Core Data or a database with WAL mode for durability guarantees.

## 7. Related Topics

- [Keychain](keychain.md) — secure alternative for sensitive values
- [File System](file-system.md) — for binary data and documents too large for UserDefaults
- [Core Data](core-data.md) — for structured relational data
- [Data Synchronization](data-sync.md) — syncing UserDefaults-backed state via iCloud Key-Value Store
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — `@AppStorage` in context of SwiftUI state wrappers
