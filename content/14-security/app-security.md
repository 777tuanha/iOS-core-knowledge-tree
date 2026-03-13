# App Security

## 1. Overview

App security encompasses the techniques used to harden an iOS app against runtime manipulation, reverse engineering, and exploitation of code vulnerabilities. iOS provides a strong baseline: code signing (every binary is verified before execution), sandboxing (apps cannot access each other's data), and ASLR + non-executable memory (making buffer overflow exploitation harder). App developers extend this baseline by detecting jailbroken devices (where the sandbox is compromised), applying code obfuscation to raise the bar for reverse engineering, and following secure coding practices — input validation, parameterised queries, avoiding logging PII, and using memory-safe APIs. These are defense-in-depth measures, not silver bullets — a determined attacker with physical device access can circumvent most software-only defenses. The goal is to make attacks expensive enough that the risk/reward ratio deters casual or opportunistic attackers.

## 2. Simple Explanation

An iOS app is like a store in a mall with security guards (iOS sandboxing). On a normal iPhone, the guards prevent one store's staff from entering another store's back room. On a jailbroken phone, the guards have been bribed — anyone can go anywhere. Jailbreak detection is like the store manager checking whether the security guards are still at their posts. Code obfuscation is like writing price tags in a secret code — a competitor can still read them if they try hard enough, but casual snoopers give up quickly. Secure coding practices are the store not leaving the safe combination written on a sticky note on the register (not logging passwords) and checking IDs at the door before serving alcohol (validating user input).

## 3. Deep iOS Knowledge

### iOS Security Baseline

| Mechanism | What it does |
|-----------|-------------|
| Code signing | Every binary verified by the OS before execution — prevents unsigned code |
| Sandboxing | Each app confined to its container — can't read other apps' data |
| ASLR | Binary base address randomised per launch — reduces exploitability |
| XN (Execute Never) | Stack and heap are non-executable — prevents shellcode injection |
| SIP / SEP | Secure Enclave Processor — hardware-isolated key storage and biometrics |
| Pointer authentication (PAC) | ARM8.3 — pointer signatures catch memory corruption |

### Jailbreak Detection

A jailbreak compromises the iOS security model by patching the kernel to disable code signing and sandbox enforcement. Detection heuristics (use multiple — any single one can be bypassed):

**File system checks:**
- `/Applications/Cydia.app` — the primary jailbreak app store
- `/usr/sbin/sshd` — OpenSSH installed by many jailbreaks
- `/bin/bash` — not present on a stock iOS device
- `/etc/apt` — APT package manager directory
- `/private/var/lib/apt/` — APT data directory

**Sandbox escape check:**
- Attempt to write outside the app's container: `open("/private/jailbreak_test", O_CREAT | O_WRONLY, 0644)` — should fail on a stock device.
- Call `fork()` — sandboxed apps cannot fork.

**Dynamic library injection check:**
- Scan `_dyld_image_count()` / `_dyld_get_image_name(i)` for known jailbreak dylibs: `MobileSubstrate.framework`, `CydiaSubstrate`, `SubstrateLoader.dylib`.

**URL scheme check:**
- `UIApplication.shared.canOpenURL(URL(string: "cydia://")!)` — Cydia registers this scheme.

**Symbolic link check:**
- `/Applications` is a symlink on jailbroken devices (points to `/var/stash/Applications`).

**Limitations**: All of these checks can be bypassed by sophisticated jailbreak tools (e.g., Liberty Lite patches the file system checks; `FLEX` patches method calls). Use **AppAttest** for cryptographic device integrity verification that is much harder to spoof.

### Anti-Debugging

Debuggers (LLDB, Frida) attach to a process and can read memory, set breakpoints, and call arbitrary functions. Anti-debugging is a cat-and-mouse game — determined attackers will bypass it. Use defensively (as a signal, not a hard block):

```swift
// Check if a debugger is attached via sysctl
func isDebuggerAttached() -> Bool {
    var mib = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
    var info = kinfo_proc()
    var size = MemoryLayout<kinfo_proc>.size
    sysctl(&mib, 4, &info, &size, nil, 0)
    return (info.kp_proc.p_flag & P_TRACED) != 0
}
```

### Code Obfuscation

**String obfuscation**: hardcoded strings (API endpoints, encryption constants, SDK keys) are visible via `strings` binary or a disassembler. Obfuscation encrypts string constants at compile time and decrypts them at runtime. Tools: `SwiftShield` (renames Swift symbols), custom build plugin using XOR or substitution ciphers on string literals.

**Control flow obfuscation**: adds opaque predicates and dead code paths to confuse static analysis. This is high-effort, low-return for most apps — reserve for DRM or high-value financial apps.

**Symbol stripping**: Release builds strip debug symbols by default. Ensure `STRIP_SWIFT_SYMBOLS = YES` and `DEPLOYMENT_POSTPROCESSING = YES` in build settings — removes readable Swift symbol names from the binary.

**Practical note**: obfuscation raises the bar but does not prevent a determined reverse engineer with runtime access (Frida, LLDB). Focus obfuscation on the most sensitive strings (API keys that cannot be server-proxied, license verification logic).

### Secure Coding Practices

**Input validation:**
- Never construct SQL using string interpolation — use parameterised queries (`?` placeholders in GRDB/SQLite).
- Validate and sanitise all user input before use in URLs, SQL, file paths, or HTML.
- Use `URL(string:)` + validate scheme — never pass arbitrary URL strings to `openURL`.

**Avoiding log leakage:**
```swift
// Bad: PII in log
print("Login attempt for user: \(email) with password: \(password)")

// Good: no PII, no secrets
Logger.auth.debug("Login attempt for user ID: \(userID.prefix(4))***")
```

Use `os_log` with `%{private}s` format specifier in production: the value is redacted from Console.app logs unless explicitly captured with a privileged profile.

**Preventing URL scheme hijacking:**
- Use Universal Links for sensitive flows (password reset, OAuth callbacks) — not custom URL schemes. Custom schemes can be registered by any app, enabling a malicious app to intercept your scheme. Universal Links are verified via the AASA file on your domain.

**Jailbreak response:**
- Do not crash on jailbreak detection — this enables a binary patch. Instead, degrade gracefully: disable biometric authentication, prevent sensitive data from being displayed, log a security event to your backend, and prompt the user to use a non-jailbroken device for sensitive actions.

### App Permissions Hygiene

- Request only the permissions you need and at the moment they're needed (never at launch unless required for core functionality).
- Use `NSLocationWhenInUseUsageDescription` instead of `NSLocationAlwaysUsageDescription` unless background location is a core feature.
- Revoke sensitive entitlements (e.g., `com.apple.developer.networking.networkextension`) from builds that don't use them.

## 4. Practical Usage

```swift
import Foundation
import UIKit

// ── Jailbreak detection ────────────────────────────────────────
final class IntegrityChecker {

    static func isDeviceCompromised() -> Bool {
        return checkSuspiciousFiles()
            || checkSandboxEscape()
            || checkSuspiciousDylibs()
            || checkFork()
    }

    // ── 1. Suspicious file system paths ───────────────────────
    private static func checkSuspiciousFiles() -> Bool {
        let suspiciousPaths = [
            "/Applications/Cydia.app",
            "/usr/sbin/sshd",
            "/bin/bash",
            "/etc/apt",
            "/private/var/lib/apt/",
            "/usr/bin/ssh",
            "/var/cache/apt",
            "/Library/MobileSubstrate/MobileSubstrate.dylib"
        ]
        return suspiciousPaths.contains { FileManager.default.fileExists(atPath: $0) }
    }

    // ── 2. Sandbox escape via file write ──────────────────────
    private static func checkSandboxEscape() -> Bool {
        let path = "/private/jailbreak_canary_\(UUID().uuidString)"
        do {
            try "test".write(toFile: path, atomically: true, encoding: .utf8)
            try FileManager.default.removeItem(atPath: path)
            return true   // write succeeded outside sandbox
        } catch {
            return false   // failed as expected on stock device
        }
    }

    // ── 3. Injected jailbreak dylibs ──────────────────────────
    private static func checkSuspiciousDylibs() -> Bool {
        let suspicious = ["MobileSubstrate", "CydiaSubstrate", "SubstrateLoader",
                          "cycript", "libhooker", "TweakInject"]
        let count = _dyld_image_count()
        for i in 0..<count {
            if let name = _dyld_get_image_name(i) {
                let imageName = String(cString: name)
                if suspicious.contains(where: { imageName.contains($0) }) {
                    return true
                }
            }
        }
        return false
    }

    // ── 4. fork() — not allowed in sandboxed apps ─────────────
    private static func checkFork() -> Bool {
        let pid = fork()
        if pid >= 0 {
            if pid > 0 { kill(pid, SIGTERM) }
            return true   // fork succeeded — sandbox broken
        }
        return false
    }
}

// ── Usage: degrade gracefully rather than hard-crash ──────────
final class SecurityPolicyEnforcer {
    static func evaluate(in viewController: UIViewController) {
        guard IntegrityChecker.isDeviceCompromised() else { return }

        // Log security event (without PII)
        Logger.security.warning("Compromised device detected — restricting sensitive features")

        // Show advisory (not a hard block — it can be patched)
        let alert = UIAlertController(
            title: "Security Warning",
            message: "This device may be compromised. Sensitive features have been disabled for your protection.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        viewController.present(alert, animated: true)

        // Disable sensitive UI
        NotificationCenter.default.post(name: .securityThreatDetected, object: nil)
    }
}

// ── Anti-debugging check ───────────────────────────────────────
func isDebuggerAttached() -> Bool {
    var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
    var info = kinfo_proc()
    var size = MemoryLayout.size(ofValue: info)
    let result = sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0)
    guard result == 0 else { return false }
    return (info.kp_proc.p_flag & P_TRACED) != 0
}

// ── Preventing SQL injection with parameterised queries ────────
// Using GRDB:
// BAD: string interpolation — injectable
// try db.execute(sql: "SELECT * FROM posts WHERE author = '\(author)'")

// GOOD: parameterised — safe
// try db.execute(sql: "SELECT * FROM posts WHERE author = ?", arguments: [author])

// ── Private logging with os_log ───────────────────────────────
import os

let securityLog = Logger(subsystem: "com.myapp.security", category: "auth")

func logLoginAttempt(email: String, success: Bool) {
    // %{private} — value is redacted in system logs unless profiling with consent
    securityLog.info("Login attempt success=\(success) email=\(email, privacy: .private)")
}

extension Notification.Name {
    static let securityThreatDetected = Notification.Name("securityThreatDetected")
}
```

## 5. Interview Questions & Answers

### Basic

**Q: Why should you not store authentication tokens in `UserDefaults` or `NSLog` output?**

A: `UserDefaults` stores data in a plist file in the app's container directory. On an unencrypted iTunes/Finder backup (any iOS backup that the user hasn't specifically encrypted), this file is accessible in plaintext. On a jailbroken device, any app with root access can read the file. `NSLog` output is written to the system log, accessible from Console.app and diagnostic reports — other apps on the device can read the system log in older iOS versions, and crash reports/diagnostic data sent to developers may contain log output. Store tokens in the Keychain, which is excluded from backups and encrypted with device-specific keys. Remove sensitive values from all log statements — use `privacy: .private` with `os_log`.

**Q: What is jailbreaking and why does it affect your app's security model?**

A: Jailbreaking is a privilege escalation exploit that patches the iOS kernel to disable code signing enforcement and sandbox restrictions. On a jailbroken device: (1) Any code can run without an Apple signature, enabling injection of malicious dylibs into your app's process. (2) The sandbox is bypassed — other processes can read your app's Keychain items, UserDefaults, and files. (3) Tools like Frida and Cycript can attach to your app, inspect memory at runtime, hook Swift/ObjC methods, and modify app behaviour. (4) SSL Kill Switch can bypass certificate pinning by patching the system's TLS verification functions. Jailbreak detection signals that you cannot trust the security model your app was designed for, allowing you to degrade sensitive features and alert users.

### Hard

**Q: How does Frida work and what can it do to a running iOS app?**

A: Frida is a dynamic instrumentation toolkit that injects a JavaScript engine (V8) into a target process via `task_for_pid` or by injecting a dylib through Cydia Substrate (on jailbroken devices). Once injected, it can: (1) Intercept and replace any Objective-C method using `ObjC.classes.ClassName['- methodName'].implementation = ...`. (2) Hook any exported C/Swift symbol using `Interceptor.attach`. (3) Read and write process memory at arbitrary addresses. (4) Call any function in the process with arbitrary arguments. (5) Intercept `URLSession` network calls, decrypt SSL traffic, modify requests/responses. Mitigations: detect the Frida server port (TCP 27042), scan for the `frida-agent` dylib in the image list, check for known Frida strings in memory. These are bypassable, but they raise the cost of analysis.

**Q: What is `AppAttest` and how is it more reliable than software jailbreak detection?**

A: `DCAppAttestService` (AppAttest) uses the Secure Enclave to generate a cryptographic attestation that proves: the requesting device is a genuine Apple device (not an emulator), the app binary matches the App ID registered with Apple, and (optionally, via risk analysis) the device shows no signs of compromise. The attestation is signed by Apple's private key, which is stored in hardware — it cannot be forged by a jailbreak tool. The app generates an attestation key in the Secure Enclave, Apple's servers sign it (after validating the hardware attestation), and subsequent API calls include a cryptographic "assertion" signed by that key. Your server validates the assertion using Apple's public key. Because the Secure Enclave is isolated from the main CPU even on a jailbroken device, and because the signing key never leaves the enclave, a jailbroken device cannot forge a valid assertion. Limitation: AppAttest requires an internet connection on first attestation, and Apple does not guarantee 100% detection — some compromised devices may still pass.

### Expert

**Q: Design a security architecture for a banking app that needs to prevent screen recording, protect session tokens, and detect runtime tampering.**

A: Six-layer approach: (1) **Screen recording prevention**: set `UIWindow.isSecure = true` (or apply to specific views with `UITextField.isSecureTextEntry`) — iOS blurs secure windows in the app switcher and in screen recordings. For transaction confirmation screens, additionally check `UIScreen.main.isCaptured` and hide sensitive values if `true`. (2) **Session token protection**: store tokens in Keychain with `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` + `SecAccessControl` requiring biometric authentication for each read. This means stolen tokens are useless without the user's face/fingerprint. Short session token TTL (15 min) with silent refresh. (3) **Runtime tampering detection**: check `isDebuggerAttached()` and `IntegrityChecker.isDeviceCompromised()` at app launch and before sensitive operations. Verify the app binary's hash against an expected value (computed at build time, stored obfuscated) — a modified binary has a different hash. (4) **AppAttest for API requests**: all transaction APIs require an AppAttest assertion header. The backend validates with Apple's API — rejects requests from non-attested or compromised devices. (5) **Certificate pinning**: as described in [Network Security](network-security.md) — SPKI pinning with two keys and pin rotation mechanism. (6) **Anomaly detection**: log security events (jailbreak detection, failed attestations, pin mismatches, repeated biometric failures) to the backend. Implement server-side rate limiting and account lockout. Alert the security team on anomalous patterns (e.g., 100 attestation failures from a single device).

## 6. Common Issues & Solutions

**Issue: Jailbreak detection is triggering for users on non-jailbroken devices (false positives).**

Solution: The file system checks are too broad. Some enterprise MDM solutions or developer devices have files in unusual paths that match your detection patterns. Narrow the checks: check for Cydia-specific paths (`/Applications/Cydia.app`, not just `/Applications`), check for Cydia's URL scheme (`cydia://`), and weight multiple weak signals rather than any single check triggering. Log which check triggered for each detection to tune the false positive rate.

**Issue: App is rejected for using `fork()` in jailbreak detection.**

Solution: Apple's App Store review may flag `fork()` usage. Alternative: use only file system checks and dylib injection checks. `fork()` is a strong signal but not essential if you have three or four other checks. Replace with a Mach-O image scan for jailbreak dylib names — this avoids the POSIX process creation APIs that flag App Review.

**Issue: SSL Kill Switch bypasses certificate pinning in a release build.**

Solution: SSL Kill Switch hooks `SecTrustEvaluateWithError` at the Objective-C/C level via Cydia Substrate. It is only effective on jailbroken devices. Pair certificate pinning with jailbreak detection: if a jailbreak is detected, disable network access to sensitive APIs entirely (not just degrade). For extra hardening, implement pinning at a lower level using `nw_tcp_create_connection` with custom certificate validation rather than the higher-level `URLSession` delegate, which is a more common hook target.

## 7. Related Topics

- [Data Security](data-security.md) — Keychain and CryptoKit for data at rest
- [Network Security](network-security.md) — certificate pinning and ATS
- [Testing — Testable Architecture](../11-testing/testable-architecture.md) — mocking security services in tests
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — entry points where integrity checks should run
