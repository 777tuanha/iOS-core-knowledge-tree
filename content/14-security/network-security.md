# Network Security

## 1. Overview

Network security on iOS protects data in transit — preventing eavesdropping, man-in-the-middle (MITM) attacks, and traffic interception. Apple's App Transport Security (ATS) enforces a minimum TLS 1.2 with strong cipher suites for all `URLSession` connections by default, rejecting connections to HTTP endpoints and servers with weak TLS configurations. Certificate pinning and public-key pinning go beyond ATS: instead of trusting any certificate signed by any CA in the system trust store, the app explicitly specifies which certificate or public key it trusts for a given domain, preventing attacks where a rogue or compromised CA issues a fraudulent certificate for your server. The tradeoff: pinning requires a rotation strategy — a misconfigured pin can break the app for all users until an update ships.

## 2. Simple Explanation

TLS without pinning is like accepting any government-issued ID at the door — you check the signature is genuine, but any country's government can issue an ID for any person. Certificate pinning is like accepting only IDs from a specific city's DMV — even if a rogue government issues a fake ID that looks valid, you won't accept it because it's not from your trusted source. Public-key pinning is even stricter: you accept only IDs with this specific face photo, regardless of who issued them. The risk: if you lose your only trusted ID (certificate expiry) and the backup isn't ready, no one gets through the door.

## 3. Deep iOS Knowledge

### App Transport Security (ATS)

ATS is a networking policy system enforced at the `URLSession` level. By default:
- HTTP connections are blocked.
- TLS 1.2+ is required.
- Forward Secrecy cipher suites only (ECDHE key exchange).
- Certificates must not use SHA-1.

Exceptions are configured in `Info.plist` under `NSAppTransportSecurity`. Common exceptions (each requires justification in App Store review):

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <!-- Allow specific HTTP domain (e.g., for CDN without HTTPS) -->
    <key>NSExceptionDomains</key>
    <dict>
        <key>legacy-cdn.example.com</key>
        <dict>
            <key>NSExceptionAllowsInsecureHTTPLoads</key><true/>
            <key>NSExceptionMinimumTLSVersion</key><string>TLSv1.2</string>
        </dict>
    </dict>
    <!-- Disable ATS entirely (for developer tools, not production) -->
    <!-- <key>NSAllowsArbitraryLoads</key><true/> -->
</dict>
```

**Never** set `NSAllowsArbitraryLoads = true` in production — it disables all ATS protections.

### TLS Certificate Chain Validation

The default `URLSession` validation:
1. The certificate chain is verified to a trusted root CA in the iOS system trust store.
2. The hostname in the certificate matches the request hostname.
3. The certificate is not expired or revoked (OCSP checking).

This is strong against general MITM but not against a rogue CA or a compromised CA that signs a certificate for your domain.

### Certificate Pinning

Certificate pinning replaces (or supplements) the default CA verification with a check that the server presents a specific certificate. The pin is typically the `SubjectPublicKeyInfo` hash (public key pin) — more robust than the full certificate hash because the public key remains the same when a certificate is renewed.

**Implementation via `URLSessionDelegate`:**

```swift
// URLSession(configuration:delegate:delegateQueue:) — delegate receives auth challenges
func urlSession(_ session: URLSession,
                didReceive challenge: URLAuthenticationChallenge,
                completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
    // Only pin for server trust challenges
    guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
          let serverTrust = challenge.protectionSpace.serverTrust
    else {
        completionHandler(.performDefaultHandling, nil)
        return
    }

    // Evaluate the default chain first
    var error: CFError?
    guard SecTrustEvaluateWithError(serverTrust, &error) else {
        completionHandler(.cancelAuthenticationChallenge, nil)
        return
    }

    // Extract the leaf certificate's public key hash
    guard let leafCert = SecTrustGetCertificateAtIndex(serverTrust, 0) else {
        completionHandler(.cancelAuthenticationChallenge, nil)
        return
    }
    let publicKeyHash = publicKeySHA256(of: leafCert)

    // Compare against pinned hashes
    let pinnedHashes: Set<String> = [
        "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",   // current cert
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="    // backup cert (rotation)
    ]

    if pinnedHashes.contains(publicKeyHash) {
        completionHandler(.useCredential, URLCredential(trust: serverTrust))
    } else {
        completionHandler(.cancelAuthenticationChallenge, nil)
    }
}
```

### Computing the Public Key Hash

```swift
import CryptoKit

func publicKeySHA256(of certificate: SecCertificate) -> String {
    // Extract the public key data
    guard let publicKey = SecCertificateCopyKey(certificate),
          let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data?
    else { return "" }

    // Prepend the SubjectPublicKeyInfo header for RSA-2048 or EC keys
    // (required to match OpenSSL/browser pin format)
    let rsaHeader = Data([
        0x30, 0x82, 0x01, 0x22, 0x30, 0x0d, 0x06, 0x09,
        0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01,
        0x01, 0x05, 0x00, 0x03, 0x82, 0x01, 0x0f, 0x00
    ])
    let spki = rsaHeader + publicKeyData
    let hash = SHA256.hash(data: spki)
    return Data(hash).base64EncodedString()
}
```

### Generating Pins

Use OpenSSL on your certificate:
```bash
# From PEM certificate:
openssl x509 -in cert.pem -pubkey -noout | \
    openssl pkey -pubin -outform DER | \
    openssl dgst -sha256 -binary | \
    base64
```

### Pin Rotation Strategy

Pinning with a single certificate is a deployment risk — if the certificate expires or is revoked before you ship an update, the app breaks for all users. Best practices:
1. **Always pin two keys**: the current certificate and the backup (next certificate, already generated and stored securely).
2. **Set certificate validity to match your update cadence** — if your app updates every 3–4 months, certificates should be valid for at least 6 months.
3. **Host a pin transparency log**: a JSON endpoint (fetched infrequently) listing current + upcoming pins, signed by your code signing key. The app validates the signature before updating its local pin set.
4. **Grace period fallback**: if the pinned hash doesn't match and the device is online, optionally fetch the updated pin set from the transparency log endpoint before hard-failing.

### NSURLSession and Proxies

Debugging tools (Charles Proxy, mitmproxy) work by installing their root CA into the device trust store, then presenting their own certificate for your server's hostname. Certificate pinning defeats this — the proxy's certificate won't match the pinned hash. For testing in a pinned app: add the proxy's hash to the pinned set in debug builds using `#if DEBUG`. Never include the proxy CA in the app bundle for release builds.

## 4. Practical Usage

```swift
import Foundation
import CryptoKit

// ── Pinning-aware URLSession ───────────────────────────────────
final class PinnedURLSession: NSObject, URLSessionDelegate {

    static let shared: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        return URLSession(
            configuration: config,
            delegate: PinnedURLSession(),
            delegateQueue: nil
        )
    }()

    // MARK: - URLSessionDelegate

    func urlSession(_ session: URLSession,
                    didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust
        else {
            completionHandler(.performDefaultHandling, nil)
            return
        }

        // Step 1: validate standard chain
        var cfError: CFError?
        guard SecTrustEvaluateWithError(serverTrust, &cfError) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Step 2: check public key hash
        guard let leaf = SecTrustGetCertificateAtIndex(serverTrust, 0) else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        let computedHash = PinnedURLSession.spkiHash(of: leaf)

        #if DEBUG
        // Allow Charles/mitmproxy in debug builds
        let debugAllowed: Set<String> = ["YOUR_PROXY_HASH="]
        if debugAllowed.contains(computedHash) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
            return
        }
        #endif

        let pinnedHashes: Set<String> = PinnedURLSession.loadPins()
        if pinnedHashes.contains(computedHash) {
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            // Log pin failure (without crashing) for monitoring
            Logger.security.error("Pin mismatch for \(challenge.protectionSpace.host)")
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    // MARK: - Helpers

    private static func spkiHash(of certificate: SecCertificate) -> String {
        guard let pubKey = SecCertificateCopyKey(certificate),
              let keyData = SecKeyCopyExternalRepresentation(pubKey, nil) as Data?
        else { return "" }
        let hash = SHA256.hash(data: keyData)
        return Data(hash).base64EncodedString()
    }

    /// Load pins from a bundled JSON file (updatable via OTA config in production)
    private static func loadPins() -> Set<String> {
        guard let url = Bundle.main.url(forResource: "Pins", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let pins = try? JSONDecoder().decode([String].self, from: data)
        else {
            return ["BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB="]   // fallback
        }
        return Set(pins)
    }
}

// ── ATS Info.plist configuration ──────────────────────────────
// In Info.plist (for development environment only):
// <key>NSAppTransportSecurity</key>
// <dict>
//     <key>NSExceptionDomains</key>
//     <dict>
//         <key>localhost</key>
//         <dict>
//             <key>NSExceptionAllowsInsecureHTTPLoads</key><true/>
//         </dict>
//     </dict>
// </dict>

// ── Forcing TLS 1.3 (recommendation for new APIs) ─────────────
extension URLSessionConfiguration {
    static var secure: URLSessionConfiguration {
        let config = URLSessionConfiguration.ephemeral
        // ATS already enforces TLS 1.2 minimum; TLS 1.3 is negotiated automatically
        // when both client and server support it (iOS 12+, modern servers)
        config.tlsMinimumSupportedProtocolVersion = .TLSv13
        return config
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is App Transport Security and what does it protect against?**

A: App Transport Security (ATS) is a security feature built into iOS that enforces minimum security standards for all outbound network connections made by `URLSession` (and APIs built on top of it). It requires: HTTPS (no plaintext HTTP), TLS 1.2 or higher, Forward Secrecy cipher suites (ECDHE), and certificates signed by a trusted CA. ATS protects against passive eavesdropping (an attacker reading HTTP traffic on the same network), downgrade attacks (forcing TLS to a weaker version with exploitable vulnerabilities), and weak encryption. It does not protect against MITM attacks from a rogue CA or a compromised CA — that requires certificate or public-key pinning on top of ATS.

**Q: What is the difference between certificate pinning and public-key pinning?**

A: Both techniques extend the default CA-based trust model by comparing a server-specific value against a locally pinned reference. **Certificate pinning** compares the full X.509 certificate — the entire DER-encoded bytes (or its hash). It is most specific but breaks when the certificate is renewed, even if the underlying key pair remains the same. **Public-key pinning** compares only the `SubjectPublicKeyInfo` (SPKI) portion — the public key itself and its algorithm identifier. It survives certificate renewals as long as the server keeps the same key pair, which is common with automated certificate management (Let's Encrypt, ACM). In practice, SPKI pinning (with two pins — current + backup) is recommended because it is robust through normal certificate renewal cycles while still blocking rogue-CA attacks.

### Hard

**Q: How do you implement certificate pinning without breaking the app when a certificate needs to be rotated?**

A: Four-step rotation strategy: (1) **Two-pin policy**: always embed two SPKI hashes in the app — the current certificate's public key and the next certificate's public key (generated in advance). When deploying the new certificate, the backup pin matches it, so clients that haven't updated yet still connect successfully. (2) **Pin update mechanism**: host a signed JSON document at a well-known endpoint listing the current + upcoming pins. The app fetches this infrequently (daily, cached) and verifies the document's signature against a public key compiled into the app binary. This allows pin updates without an app store release. (3) **Expiry monitoring**: alert your infrastructure team when a certificate is within 60 days of expiry. Generate the replacement key pair and prepare the updated pin document at 90 days. Ship an app update with the new backup pin before rotating the live certificate. (4) **Hard-fail vs soft-fail**: the app should hard-fail (reject the connection) on a pin mismatch — soft-failing (falling back to CA validation) defeats the purpose. Log pin failures to your security monitoring system — a spike in failures may indicate a MITM attack in progress.

**Q: How can an attacker intercept a pinned HTTPS connection, and how do you defend against it?**

A: Three attack vectors: (1) **SSL stripping with a proxy + system trust store manipulation**: if the attacker convinces the user to install their proxy CA into the device's trust store (via MDM or manual installation), and your pinning only checks the chain without verifying the leaf, the attacker's certificate may pass. Defend: verify the leaf certificate or SPKI, not just the chain. (2) **Jailbreak-based SSL bypass**: tools like `SSL Kill Switch 2` patch `SecTrustEvaluateWithError` to always return success on jailbroken devices, bypassing your delegate entirely. Defend: detect jailbreaks before making network calls; terminate sensitive sessions if jailbreak is detected. (3) **Repackaged app with modified pins**: an attacker repackages the app with different pinned hashes. Defend: use `AppAttest` to verify the app is the authentic signed version before trusting its network calls; verify binary integrity with the App Attest assertion on each request.

### Expert

**Q: Design a network security architecture for a financial app that requires zero tolerance for MITM attacks and must not break during certificate rotation.**

A: Five-layer architecture: (1) **ATS as baseline**: enforce in `Info.plist` with no exceptions — TLS 1.2+ required. (2) **SPKI pinning with three pins**: current key, backup key (next rotation), and an emergency backup key stored offline in an HSM. Implement in `URLSession` delegate with hard-fail on mismatch. (3) **Dynamic pin updates**: a `/api/security/pins` endpoint, signed with ECDSA using a key compiled into the binary (not derived from any server certificate). The app fetches this endpoint daily, verifies the signature, and caches the result with a 7-day TTL. Pin updates are pushed here before certificate rotation. (4) **Certificate Transparency enforcement**: require `SCTValidationResult` on all connections (Apple enforces this since iOS 16). This prevents issuance of rogue certificates without public audit trail visibility. (5) **AppAttest for API requests**: all financial API requests include an `AppAttest` assertion header. The backend verifies the assertion using Apple's API before processing the request — this prevents bots and script-based attacks even if they somehow obtain valid TLS. Add anomaly detection: if a device sends 100 failed attestations, block it.

## 6. Common Issues & Solutions

**Issue: App crashes or shows a network error after certificate rotation.**

Solution: The pinned hash no longer matches the new certificate's public key. Immediate fix: ship an emergency app update with the new certificate's SPKI hash in the pins. For future rotation: follow the two-pin + dynamic pin update strategy described above. If the old certificate is still valid, re-deploy the old certificate temporarily to restore service while the update propagates.

**Issue: Certificate pinning is blocking legitimate connections during development (Charles Proxy).**

Solution: Add `#if DEBUG` conditional logic in the `URLSessionDelegate` that either allows all connections (no pinning) or includes the Charles root CA hash in the accepted set. Never include this in release builds — use `CONFIGURATION` build setting checks or a `DEBUG` flag. Alternatively, use a development-only backend subdomain with a different certificate that has a development pin, keeping the production pin list clean.

**Issue: `SecTrustEvaluateWithError` returns success but the server presents an expired certificate.**

Solution: `SecTrustEvaluateWithError` evaluates the certificate chain including expiry. If it's returning success for an expired cert, it may be using a pinned/test certificate with `SecTrustSetAnchorCertificates` overriding the default evaluation. Review the trust evaluation code — ensure you're not calling `SecTrustSetVerifyDate` with a past date or `SecTrustSetAnchorCertificates` with a self-signed test cert that bypasses date validation.

## 7. Related Topics

- [Data Security](data-security.md) — CryptoKit for encrypting data before transmission
- [App Security](app-security.md) — jailbreak detection affecting network trust
- [Advanced Networking](../07-networking/advanced-networking.md) — URLSession configuration and interceptors
- [Keychain](../08-data-persistence/keychain.md) — storing private keys used in network authentication
