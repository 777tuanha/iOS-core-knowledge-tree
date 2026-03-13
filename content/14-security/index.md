# Security

## 1. Overview

iOS security is a layered system that Apple provides at the hardware, OS, and framework level — but apps must use the available APIs correctly to benefit from those protections. Application security covers three domains: **data security** (protecting data at rest using the Keychain, encrypted databases, and `NSFileProtection`), **network security** (protecting data in transit via ATS, TLS, and certificate/public-key pinning), and **app security** (hardening the app against reverse engineering, runtime manipulation, jailbroken devices, and common coding vulnerabilities). iOS apps are sandboxed, code-signed, and distributed through a verified App Store — these system-level controls provide a strong baseline. App developers build on top of that baseline by choosing the right storage API for sensitive data, enforcing TLS, and writing secure code that validates all inputs and uses APIs that prevent common vulnerabilities (SQL injection, XSS, buffer overflows).

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Data Security](data-security.md) | Keychain advanced usage, `CryptoKit` encryption, `NSFileProtection`, secure data deletion |
| 2 | [Network Security](network-security.md) | ATS configuration, TLS, certificate pinning, public-key pinning with `URLSession` |
| 3 | [App Security](app-security.md) | Jailbreak detection heuristics, code obfuscation, secure coding practices, input validation |

## 3. iOS Security Architecture

```
Hardware
├── Secure Enclave — stores biometric keys, device encryption keys
└── UID / GID fuses — hardware-fused keys for PBKDF2 stretching

OS / Kernel
├── Code signing — all code verified before execution
├── App sandboxing — each app isolated to its container
├── ASLR — randomised address space to frustrate exploitation
└── Non-executable stack + heap (XN bit)

Framework APIs (what app code uses)
├── Keychain Services — encrypted, access-controlled credential storage
├── CryptoKit — AES-GCM, ChaCha20, ECDH, Ed25519
├── NSFileProtection — per-file encryption tied to device lock state
├── Network (ATS) — enforces TLS 1.2+ for all network connections
└── LocalAuthentication — Face ID / Touch ID biometric gates
```

## 4. Common Attack Surfaces and Mitigations

| Attack surface | Mitigation |
|---------------|-----------|
| Credentials in UserDefaults | Move to Keychain |
| Sensitive data in plaintext files | Use NSFileProtection.complete |
| HTTP traffic | Enable ATS, enforce HTTPS |
| MITM / SSL stripping | Certificate or public-key pinning |
| Reverse-engineered API keys | Server-side secrets, not embedded in binary |
| Jailbroken device runtime manipulation | Jailbreak detection + integrity checks |
| SQL injection | Parameterised queries (never string interpolation) |
| Log leakage | Never log PII or tokens in production |

## 5. Related Topics

- [Keychain — Data Persistence](../08-data-persistence/keychain.md) — `SecItem` API and `kSecAttrAccessibleAfterFirstUnlock`
- [Advanced Networking](../07-networking/advanced-networking.md) — `URLSession` and network security
- [Testing — Testable Architecture](../11-testing/testable-architecture.md) — test doubles for security services
