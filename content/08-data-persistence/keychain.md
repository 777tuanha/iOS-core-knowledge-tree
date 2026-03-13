# Keychain

## 1. Overview

The Keychain is Apple's secure credential storage system. It stores small, sensitive data items — passwords, tokens, cryptographic keys, and certificates — using hardware-backed AES-256 encryption. Unlike `UserDefaults`, Keychain data persists across app installs (on device), can survive app deletion (with the right accessibility attribute), and is protected by the Secure Enclave on modern devices. iOS enforces access control at the kernel level: only the app that wrote an item (or apps in the same Keychain group) can read it. The C-level `Security` framework (`SecItem` API) is the underlying interface; most production code wraps it in a Swift abstraction.

## 2. Simple Explanation

The Keychain is like a safety-deposit box at a bank. Your app is the box owner — you have the key (your bundle ID / entitlement). The bank vault (Secure Enclave / OS security layer) ensures no other tenant can open your box, even if the device is connected to a computer. You can lock the box differently depending on when it should be openable: always (even when the device is locked), only when unlocked, or only after the user authenticates with Face ID. You can also add a deposit box to a shared vault (Keychain group) so your other apps can access it too.

## 3. Deep iOS Knowledge

### SecItem API

All Keychain operations use four C functions:

| Function | Operation |
|----------|-----------|
| `SecItemAdd(_:_:)` | Create a new item |
| `SecItemCopyMatching(_:_:)` | Read one or more items |
| `SecItemUpdate(_:_:)` | Update an existing item |
| `SecItemDelete(_:)` | Delete one or more items |

Each function takes a `CFDictionary` (query) containing item class, attributes, and search parameters.

### Item Classes

| Class | Use case |
|-------|---------|
| `kSecClassGenericPassword` | App tokens, passwords, arbitrary secrets |
| `kSecClassInternetPassword` | Passwords associated with a URL and username |
| `kSecClassCertificate` | X.509 certificates |
| `kSecClassKey` | Cryptographic keys (RSA, EC) |
| `kSecClassIdentity` | Certificate + private key pair |

For most iOS apps, `kSecClassGenericPassword` covers all use cases.

### Accessibility Attributes

Controls when the item is accessible — balancing security with usability:

| Attribute | Accessible when |
|-----------|----------------|
| `.afterFirstUnlock` | After first unlock after boot; survives background — **recommended for tokens** |
| `.whenUnlocked` | Only while device is unlocked (default) |
| `.whenPasscodeSetThisDeviceOnly` | Only if passcode is set; not transferred/backed up; most secure |
| `.afterFirstUnlockThisDeviceOnly` | Like `afterFirstUnlock` but not transferred to new devices |
| `.whenUnlockedThisDeviceOnly` | `whenUnlocked` + not transferred |

The `ThisDeviceOnly` variants are not migrated via iCloud Keychain or device backup — use these for device-bound secrets like device attestation keys.

### Keychain Groups (Sharing Between Apps)

By default, a Keychain item is accessible only to the app that created it (keyed by bundle ID). To share items between apps from the same developer:

1. Enable the **Keychain Sharing** capability in Xcode.
2. Add a shared group identifier (e.g., `com.mycompany.sharedKeychain`).
3. Set `kSecAttrAccessGroup` in all query dictionaries to the shared group.

This is used to share an auth token between a main app, a share extension, and a widget.

### Access Control — Biometrics

`SecAccessControlCreateWithFlags` adds biometric (Face ID / Touch ID) or device passcode requirements to individual items:

```swift
let access = SecAccessControlCreateWithFlags(
    nil,
    kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
    .userPresence,     // Face ID or passcode fallback
    nil
)!
```

With `.userPresence`, reading the item presents a system authentication prompt. If authentication fails, `errSecAuthFailed` is returned.

### iCloud Keychain

Setting `kSecAttrSynchronizable = kCFBooleanTrue` opts the item into iCloud Keychain sync across the user's devices. Do NOT use this for device-bound secrets (certificates, device keys). Tokens that should work on all the user's devices (e.g., a refresh token) are appropriate candidates.

### Error Codes

Common `OSStatus` values:

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `errSecSuccess` | Success |
| -25300 | `errSecItemNotFound` | Item does not exist |
| -25299 | `errSecDuplicateItem` | Item already exists |
| -128 | `errSecUserCanceled` | User cancelled biometric prompt |
| -25293 | `errSecAuthFailed` | Biometric/passcode auth failed |

## 4. Practical Usage

```swift
import Foundation
import Security

// ── Generic Keychain wrapper ──────────────────────────────────
enum KeychainError: Error {
    case itemNotFound
    case duplicateItem
    case invalidData
    case unexpectedStatus(OSStatus)
}

struct KeychainItem {
    let service: String                          // identifies the app/context
    let account: String                          // identifies the specific secret
    let accessGroup: String?                     // nil → app-private; set for shared groups

    init(service: String, account: String, accessGroup: String? = nil) {
        self.service = service
        self.account = account
        self.accessGroup = accessGroup
    }

    // ── Write / Update ───────────────────────────────────────
    func save(_ value: String) throws {
        guard let data = value.data(using: .utf8) else { throw KeychainError.invalidData }
        try save(data)
    }

    func save(_ data: Data) throws {
        // Try to update first; if not found, add new
        let query = baseQuery()
        let attributes: [String: Any] = [kSecValueData as String: data]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)

        if status == errSecItemNotFound {
            var addQuery = baseQuery()
            addQuery[kSecValueData as String] = data
            addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            status = SecItemAdd(addQuery as CFDictionary, nil)
        }

        guard status == errSecSuccess else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    // ── Read ─────────────────────────────────────────────────
    func read() throws -> Data {
        var query = baseQuery()
        query[kSecMatchLimit as String]       = kSecMatchLimitOne
        query[kSecReturnData as String]       = kCFBooleanTrue
        query[kSecReturnAttributes as String] = kCFBooleanTrue

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        switch status {
        case errSecSuccess:
            guard let dict = result as? [String: Any],
                  let data = dict[kSecValueData as String] as? Data else {
                throw KeychainError.invalidData
            }
            return data
        case errSecItemNotFound:
            throw KeychainError.itemNotFound
        default:
            throw KeychainError.unexpectedStatus(status)
        }
    }

    func readString() throws -> String {
        let data = try read()
        guard let string = String(data: data, encoding: .utf8) else {
            throw KeychainError.invalidData
        }
        return string
    }

    // ── Delete ───────────────────────────────────────────────
    func delete() throws {
        let query = baseQuery()
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    // ── Private ──────────────────────────────────────────────
    private func baseQuery() -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String:       kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        if let group = accessGroup {
            query[kSecAttrAccessGroup as String] = group
        }
        return query
    }
}

// ── Token storage convenience layer ──────────────────────────
enum Credentials {
    private static let accessToken   = KeychainItem(service: "com.myapp.auth", account: "access_token")
    private static let refreshToken  = KeychainItem(service: "com.myapp.auth", account: "refresh_token")

    static func saveTokens(access: String, refresh: String) throws {
        try accessToken.save(access)
        try refreshToken.save(refresh)
    }

    static func accessToken() throws -> String  { try accessToken.readString() }
    static func refreshToken() throws -> String { try refreshToken.readString() }

    static func clearAll() {
        try? accessToken.delete()
        try? refreshToken.delete()
    }
}

// Usage:
// try Credentials.saveTokens(access: "eyJ...", refresh: "r_abc123")
// let token = try Credentials.accessToken()
// Credentials.clearAll()   // on logout

// ── Biometric-protected item ──────────────────────────────────
func saveBiometricItem(secret: Data, label: String) throws {
    let access = SecAccessControlCreateWithFlags(
        nil,
        kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
        .userPresence,      // Face ID or passcode fallback
        nil
    )!

    let query: [String: Any] = [
        kSecClass as String:              kSecClassGenericPassword,
        kSecAttrService as String:        "com.myapp.biometric",
        kSecAttrAccount as String:        label,
        kSecValueData as String:          secret,
        kSecAttrAccessControl as String:  access,
        kSecUseDataProtectionKeychain as String: true
    ]

    let status = SecItemAdd(query as CFDictionary, nil)
    guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
}

// ── iCloud Keychain (synchronisable) ─────────────────────────
func saveToiCloudKeychain(value: String, key: String) throws {
    guard let data = value.data(using: .utf8) else { throw KeychainError.invalidData }

    // Delete existing synchronisable item first (duplicates must include synchronizable in query)
    let deleteQuery: [String: Any] = [
        kSecClass as String:              kSecClassGenericPassword,
        kSecAttrService as String:        "com.myapp.cloud",
        kSecAttrAccount as String:        key,
        kSecAttrSynchronizable as String: kCFBooleanTrue!
    ]
    SecItemDelete(deleteQuery as CFDictionary)

    let addQuery: [String: Any] = [
        kSecClass as String:              kSecClassGenericPassword,
        kSecAttrService as String:        "com.myapp.cloud",
        kSecAttrAccount as String:        key,
        kSecValueData as String:          data,
        kSecAttrSynchronizable as String: kCFBooleanTrue!,
        kSecAttrAccessible as String:     kSecAttrAccessibleAfterFirstUnlock
    ]
    let status = SecItemAdd(addQuery as CFDictionary, nil)
    guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: Why should you store authentication tokens in the Keychain rather than UserDefaults?**

A: `UserDefaults` stores data as a plain plist file on disk — it is protected only by the app sandbox, not encrypted. Any tool with sandbox access (e.g., an iTunes backup on a non-encrypted Mac, or a jailbroken device) can read it. The Keychain encrypts data with AES-256, and on modern devices the encryption keys are protected by the Secure Enclave. Access is enforced by the OS kernel — no other app can read your Keychain items unless you explicitly share them via a Keychain group. Additionally, the Keychain persists across app reinstalls (unless explicitly deleted), which means you can restore a user's session after they reinstall the app — something UserDefaults cannot do.

**Q: What is a Keychain accessibility attribute and which should you use for an auth token?**

A: The accessibility attribute controls when the item can be read. For a background-accessible auth token (one that a background URLSession task needs to attach to a request even while the device is locked), use `kSecAttrAccessibleAfterFirstUnlock`. This makes the item accessible after the first unlock following a device reboot, covering both foreground and background app states. Avoid `kSecAttrAccessibleAlways` (deprecated) and prefer `ThisDeviceOnly` variants for items that should not roam to other devices. For highly sensitive keys that should only be accessible when the screen is unlocked, use `kSecAttrAccessibleWhenUnlocked`.

### Hard

**Q: How do you share Keychain items between your main app and a widget extension?**

A: Enable the **Keychain Sharing** capability in Xcode for both the main app target and the extension target, using the same Keychain group identifier (e.g., `com.mycompany.sharedKeychain`). In every `SecItem` query that needs to be shared, set `kSecAttrAccessGroup` to that identifier. Items written with this access group are visible to all apps and extensions with the same entitlement. Without the access group key, each target writes to its own private namespace (keyed by the process's application identifier). Note: the group identifier must be prefixed with the Team ID in the entitlement file (`<TeamID>.com.mycompany.sharedKeychain`), but in code you reference it without the Team ID prefix.

**Q: How does biometric authentication integrate with Keychain, and what happens when Face ID fails?**

A: Items can be protected with `SecAccessControlCreateWithFlags` using flags like `.userPresence` (Face ID with passcode fallback), `.biometryAny` (Face ID or Touch ID, no passcode fallback), or `.biometryCurrentSet` (fails if enrolled biometrics change — used for secure keys). When `SecItemCopyMatching` is called for a biometric-protected item, the system presents a Face ID/Touch ID prompt. The `LAContext` used for the prompt can be pre-evaluated and injected into the query via `kSecUseAuthenticationContext` to avoid duplicate prompts. On authentication failure (`errSecAuthFailed`) or user cancellation (`errSecUserCanceled`), your code must handle the error — typically by falling back to a passcode prompt or locking the session.

### Expert

**Q: What are the risks of using `kSecAttrSynchronizable = true` for storing auth tokens?**

A: Synchronisable items are synced to iCloud Keychain and thus to all the user's Apple devices. Risks: (1) **Token leakage across devices**: a token issued for an iPhone can be used from the user's Mac or iPad — depending on your backend's token binding model, this may be acceptable or a security issue. (2) **Delayed revocation**: if you revoke a token server-side, the old token still exists on other synced devices until iCloud sync propagates. (3) **Backup exposure**: iCloud Keychain is encrypted end-to-end but adds a cloud attack surface vs. device-only storage. (4) **`ThisDeviceOnly` mismatch**: synchronisable items cannot use `ThisDeviceOnly` accessibility attributes — the OS will reject the combination. The recommendation: use synchronisable Keychain for user-facing credentials (passwords, long-lived refresh tokens) where multi-device access is desired, and `ThisDeviceOnly` for device-bound keys (attestation, signing keys, session-bound access tokens).

## 6. Common Issues & Solutions

**Issue: `errSecItemNotFound` (-25300) even though the item was saved.**

Solution: The query used to read doesn't match the query used to write. Check that `kSecAttrService`, `kSecAttrAccount`, and `kSecAttrAccessGroup` are identical in both queries. A missing `kSecAttrAccessGroup` defaults to the app's private namespace — if the writer set a group and the reader didn't, they look in different namespaces.

**Issue: Keychain item is deleted when the user reinstalls the app.**

Solution: By default, Keychain items survive reinstallation on device. However, on Simulator they are cleared on reinstall, and if the device is erased, items are cleared. If you see deletion on real device reinstall, verify the item was not written with `.whenPasscodeSetThisDeviceOnly` (which can be cleared when the passcode is removed) and confirm no `SecItemDelete` is called at launch.

**Issue: `errSecDuplicateItem` (-25299) when trying to save.**

Solution: An item with the same `kSecAttrService` + `kSecAttrAccount` already exists. Either delete before adding, or use `SecItemUpdate` to modify the existing item. The recommended pattern is: try update first; if `errSecItemNotFound`, then add.

**Issue: Biometric prompt does not appear — returns `errSecInteractionNotAllowed`.**

Solution: Keychain operations that require user interaction cannot run in a background thread without an `LAContext`. Create an `LAContext`, call `evaluatePolicy(_:localizedReason:reply:)` first, then pass the context to the Keychain query via `kSecUseAuthenticationContext`. Also ensure the app is in the foreground — biometric prompts are not presented for background processes.

## 7. Related Topics

- [UserDefaults](userdefaults.md) — for non-sensitive preferences
- [File System](file-system.md) — for larger encrypted data (NSFileProtection)
- [Data Synchronization](data-sync.md) — iCloud Keychain as a sync mechanism
- [Dependency Injection](../06-architecture/dependency-injection.md) — inject a Keychain protocol for testable credential storage
