# Data Security

## 1. Overview

Data security on iOS protects sensitive information at rest — preventing an attacker with physical access to the device, or access to an unencrypted backup, from reading credentials, personal data, or encryption keys. The primary tools are: the **Keychain** (the correct storage for secrets — credentials, tokens, encryption keys), **CryptoKit** (Swift-native symmetric and asymmetric cryptography), **NSFileProtection** (per-file encryption tied to the device's lock state), and secure data lifecycle practices (scrubbing memory, excluding sensitive files from backups, avoiding logging PII). Common mistakes — storing tokens in `UserDefaults`, using `Data(contentsOf:)` with no file protection, or embedding API keys in the binary — expose data to backup extraction, file-system inspection on jailbroken devices, and reverse engineering.

## 2. Simple Explanation

Think of your iPhone as a safe with multiple compartments. The Keychain is the deep vault — a safe within the safe, protected by the device's hardware encryption keys and biometric lock. Even if someone copies the entire device filesystem (via an unencrypted backup), the Keychain data is still encrypted with device-specific keys that cannot be extracted. `NSFileProtection.complete` puts a file behind the vault door — the file is encrypted while the phone is locked and can only be read after the user unlocks the device. `UserDefaults` and the app's Documents folder are the unlocked drawer on the desk — convenient, but not protected beyond the device's full-disk encryption, and accessible from iTunes backups.

## 3. Deep iOS Knowledge

### Keychain vs UserDefaults

| Property | Keychain | UserDefaults |
|----------|----------|--------------|
| At-rest encryption | Hardware-backed, Secure Enclave | Standard full-disk encryption only |
| Accessible from backup | No (by default) | Yes — plaintext in backup |
| Persists after app delete | Yes (unless `secAttrAccessible` = `.whenPasscodeSet`) | No |
| Access control | Biometric, passcode, device lock | None |
| Thread safety | Yes | Yes |
| Best for | Credentials, tokens, private keys | Preferences, flags |

### CryptoKit

Apple's `CryptoKit` framework (iOS 13+) provides modern, memory-safe cryptography:

- **AES-GCM**: authenticated encryption (confidentiality + integrity + authenticity).
- **ChaCha20-Poly1305**: alternative to AES-GCM, faster on devices without AES hardware instructions.
- **ECDH (Curve25519)**: key agreement for end-to-end encryption.
- **Ed25519**: digital signatures.
- **HMAC-SHA256/384/512**: message authentication codes.
- **SHA-256/384/512**: cryptographic hashing.
- **HKDF**: key derivation from a shared secret.

Never use: `CommonCrypto` ECB mode, `SecRandom` for key derivation, `MD5`/`SHA1` for security-sensitive hashing.

### NSFileProtection Levels

| Level | When accessible |
|-------|----------------|
| `.complete` | Only when device is unlocked |
| `.completeUnlessOpen` | Accessible if file was open when locked; new files require unlock |
| `.completeUntilFirstUserAuthentication` | After first unlock since reboot (default for most files) |
| `.none` | Always accessible (no protection) |

For sensitive files, use `.complete`. For files that background tasks must read (e.g., database): `.completeUntilFirstUserAuthentication`. The protection class is set as an extended attribute on the file — it doesn't change the file's format.

### Secure Data Deletion

In-memory sensitive data (passwords, keys) should be zeroed after use. Swift's `Data` and `String` do not guarantee zeroing on deallocation. Use `SecureBytes` or `UnsafeMutableRawBufferPointer` with `memset_s`:

```swift
// Zero-fill before releasing
func zeroise(_ data: inout Data) {
    data.withUnsafeMutableBytes { ptr in
        memset_s(ptr.baseAddress, ptr.count, 0, ptr.count)
    }
}
```

### Binary Secret Protection

Never embed API secrets directly in the binary. Strings in a Mach-O binary are trivially extracted with `strings MyApp.app/MyApp`. Mitigations:
1. Server-side proxy: the app calls your server, which calls the third-party API with the secret.
2. Obfuscate constants at compile time (build-time XOR or string splitting) — not cryptographically secure but raises the bar.
3. Fetch secrets from a secure server at runtime (authenticate the request with a hardware-attested device check via `DeviceCheck` or `AppAttest`).

### App Attest

`DCAppAttestService` (iOS 14+) cryptographically proves to your server that the request originates from a genuine, unmodified iOS app on a real Apple device. This prevents credential stuffing and API abuse from bots:

1. Generate an attestation key: `DCAppAttestService.shared.generateKey`.
2. Attest the key against Apple's servers.
3. Send subsequent requests with an assertion — your server verifies the assertion using Apple's public key, proving the request came from the legit app.

## 4. Practical Usage

```swift
import CryptoKit
import Security

// ── AES-GCM encryption / decryption ───────────────────────────
struct EncryptedPayload: Codable {
    let nonce: Data       // 12-byte random nonce
    let ciphertext: Data  // encrypted data + authentication tag (last 16 bytes)
}

enum DataEncryptor {

    /// Encrypts `plaintext` with `key` using AES-GCM (256-bit).
    static func encrypt(_ plaintext: Data, using key: SymmetricKey) throws -> EncryptedPayload {
        let nonce = AES.GCM.Nonce()   // 12 random bytes
        let sealedBox = try AES.GCM.seal(plaintext, using: key, nonce: nonce)
        return EncryptedPayload(
            nonce: Data(nonce),
            ciphertext: sealedBox.ciphertext + sealedBox.tag   // append tag
        )
    }

    /// Decrypts `payload` with `key`, verifying the authentication tag.
    static func decrypt(_ payload: EncryptedPayload, using key: SymmetricKey) throws -> Data {
        let nonce = try AES.GCM.Nonce(data: payload.nonce)
        // Last 16 bytes = tag; preceding bytes = ciphertext
        let ciphertext = payload.ciphertext.dropLast(16)
        let tag = payload.ciphertext.suffix(16)
        let sealedBox = try AES.GCM.SealedBox(nonce: nonce, ciphertext: ciphertext, tag: tag)
        return try AES.GCM.open(sealedBox, using: key)
    }
}

// ── Deriving a key from a passphrase ──────────────────────────
func deriveKey(from passphrase: String, salt: Data) -> SymmetricKey {
    let passphraseBytes = Data(passphrase.utf8)
    // PBKDF2 with SHA-256, 100,000 iterations (NIST recommendation)
    return SymmetricKey(data: HKDF<SHA256>.deriveKey(
        inputKeyMaterial: SymmetricKey(data: passphraseBytes),
        salt: salt,
        outputByteCount: 32
    ))
}

// ── Storing an encryption key in the Keychain ─────────────────
func storeKey(_ key: SymmetricKey, tag: String) throws {
    let keyData = key.withUnsafeBytes { Data($0) }
    let query: [CFString: Any] = [
        kSecClass: kSecClassGenericPassword,
        kSecAttrAccount: tag,
        kSecValueData: keyData,
        kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
    ]
    let status = SecItemAdd(query as CFDictionary, nil)
    if status == errSecDuplicateItem {
        let update: [CFString: Any] = [kSecValueData: keyData]
        SecItemUpdate(query as CFDictionary, update as CFDictionary)
    } else if status != errSecSuccess {
        throw NSError(domain: NSOSStatusErrorDomain, code: Int(status))
    }
}

// ── NSFileProtection on a sensitive file ──────────────────────
func writeProtected(data: Data, to url: URL) throws {
    try data.write(to: url, options: .atomic)
    try (url as NSURL).setResourceValue(
        URLFileProtection.complete,   // only accessible when unlocked
        forKey: .fileProtectionKey
    )
}

// ── Secure memory zeroing ──────────────────────────────────────
func withSensitiveData<T>(_ data: Data, body: (Data) -> T) -> T {
    var mutableData = data
    defer {
        mutableData.withUnsafeMutableBytes { ptr in
            guard let base = ptr.baseAddress else { return }
            memset_s(base, ptr.count, 0, ptr.count)
        }
    }
    return body(mutableData)
}

// ── Checking if UserDefaults contains plaintext tokens (audit) ─
func auditUserDefaultsForSecrets() {
    let knownSensitiveKeys = ["authToken", "sessionID", "password", "apiKey"]
    for key in knownSensitiveKeys {
        if UserDefaults.standard.string(forKey: key) != nil {
            assertionFailure("⚠️ Sensitive value '\(key)' found in UserDefaults — move to Keychain")
        }
    }
}

// ── Ed25519 digital signature ──────────────────────────────────
func signAndVerify() throws {
    let privateKey = Curve25519.Signing.PrivateKey()
    let publicKey = privateKey.publicKey

    let message = Data("Important message".utf8)
    let signature = try privateKey.signature(for: message)

    let isValid = publicKey.isValidSignature(signature, for: message)
    assert(isValid, "Signature verification failed")
}
```

## 5. Interview Questions & Answers

### Basic

**Q: Where should an iOS app store an OAuth access token and why?**

A: In the **Keychain** with `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`. The Keychain is encrypted with device-specific hardware keys derived from the Secure Enclave — it cannot be read from device backups (even unencrypted backups), and it is not accessible to other apps (without a shared Keychain group). `UserDefaults` stores data in a plist file inside the app container — readable from unencrypted iTunes/Finder backups, accessible to file-system tools on jailbroken devices, and not protected beyond full-disk encryption. The `ThisDeviceOnly` suffix prevents the token from syncing to iCloud Keychain — important for short-lived access tokens that should not survive a device restore.

**Q: What does `NSFileProtection.complete` do and when should you use it?**

A: `NSFileProtection.complete` encrypts the file with a per-file key that is wrapped with the user's passcode-derived key. The file key is available only when the device is unlocked — when the device is locked, the key is purged from memory and the file is inaccessible. Use it for files containing sensitive user data: encrypted database WAL files, private keys exported to disk, health data exports, financial documents. Do not use it for database files that background tasks must read (e.g., BGAppRefreshTask runs while the device may be locked) — use `.completeUntilFirstUserAuthentication` instead, which keeps the file accessible after the first unlock since reboot.

### Hard

**Q: What is AES-GCM and why should you use it instead of AES-CBC for encrypting user data?**

A: AES-GCM (Galois/Counter Mode) provides **authenticated encryption**: it simultaneously encrypts data (confidentiality via AES-CTR) and computes an authentication tag (integrity + authenticity via GHASH). Decryption fails with an error if the ciphertext or associated data has been tampered with. AES-CBC (Cipher Block Chaining) provides only confidentiality — it does not authenticate. A CBC-encrypted ciphertext can be bit-flipped by an attacker without the recipient detecting the tampering (padding oracle attacks, CBC malleability attacks). AES-GCM is the standard choice in modern protocols (TLS 1.3, iOS CryptoKit). The `AES.GCM.open` call in CryptoKit throws if the tag doesn't match, ensuring the app never processes tampered data. Always use a fresh random nonce (12 bytes from `AES.GCM.Nonce()`) for each encryption — reusing a nonce with the same key is catastrophic (it reveals the keystream).

**Q: How does `DCAppAttestService` protect your API from abuse, and what are its limitations?**

A: `DCAppAttestService` generates a device-specific attestation key pair in the Secure Enclave. Apple's servers sign the public key, creating an attestation certificate that binds the key to: the App ID, the device's UDID, the iOS version, and the fact that the device has not been jailbroken (as determined by Apple's server-side assessment). Your server receives the attestation certificate and can verify it against Apple's public key, confirming the request came from a legitimate, unmodified instance of your app on a real Apple device. Limitations: (1) Apple's assessment is not a guarantee — sophisticated jailbreaks may pass attestation. (2) It requires network availability — first-time key generation and attestation require an internet connection. (3) Attestation keys are bound to the device; they are lost if the app is uninstalled (unless backed up to iCloud, which requires careful handling). (4) Rate limits: Apple imposes attestation rate limits per device/app, so this cannot be called on every API request — use assertions for individual calls after initial attestation.

### Expert

**Q: Design an end-to-end encrypted messaging feature for an iOS app where the server cannot read message content.**

A: Four-layer architecture: (1) **Key generation**: on account creation, generate a Curve25519 key pair (`Curve25519.KeyAgreement.PrivateKey`) per user on-device. Store the private key in the Keychain with `.whenPasscodeSetThisDeviceOnly` and biometric access control. Upload only the public key to the server. (2) **Message encryption (sender)**: when Alice sends to Bob, fetch Bob's public key from the server. Perform ECDH key agreement: `try alicePrivate.sharedSecretFromKeyAgreement(with: bobPublic)`. Derive a symmetric key using HKDF: `sharedSecret.hkdfDerivedSymmetricKey(using: SHA256.self, salt: Data(), sharedInfo: Data(), outputByteCount: 32)`. Encrypt the message with AES-GCM. Send the ciphertext + Alice's public key (needed by Bob to reproduce the ECDH) to the server. (3) **Decryption (receiver)**: Bob's device fetches the ciphertext and Alice's public key. Performs the same ECDH to derive the shared secret. Decrypts with AES-GCM — the authentication tag verifies integrity. (4) **Key rotation and forward secrecy**: use the Signal protocol's Double Ratchet algorithm (or a simplified version with per-message ephemeral keys) for forward secrecy — compromise of one message key does not compromise past or future keys. The server stores only ciphertext and public keys — it cannot decrypt messages, making it resilient to server-side breaches.

## 6. Common Issues & Solutions

**Issue: CryptoKit throws an error when decrypting data that was encrypted on a different device.**

Solution: The key must be the same on both devices. If you're generating a key on-device and not sharing it, decryption on another device will always fail — this is expected. If you need cross-device encryption (e.g., synced notes), derive the key from a shared secret (user password + server-stored salt using PBKDF2/HKDF), or use asymmetric ECDH with the receiver's public key. Also check that the nonce stored with the ciphertext is correctly serialised and deserialised — a truncated or misaligned nonce causes AES-GCM to fail.

**Issue: App is rejected because it uses encryption (US export compliance).**

Solution: Apps using standard encryption (AES, RSA, TLS) must declare this in the App Store Connect export compliance section. For apps using only standard OS-provided encryption (HTTPS, Keychain, CloudKit), check "Yes, but I only use encryption that is exempt" — standard OS encryption is exempt from EAR (Export Administration Regulations). Apps implementing their own non-exempt encryption (custom protocols, VPN) need an ERN (Encryption Registration Number).

## 7. Related Topics

- [Keychain — Data Persistence](../08-data-persistence/keychain.md) — `SecItem` API, biometric access control
- [Network Security](network-security.md) — TLS and certificate pinning
- [App Security](app-security.md) — protecting the binary and runtime
- [File System](../08-data-persistence/file-system.md) — `NSFileProtection` and backup exclusion
