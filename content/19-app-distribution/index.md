# App Distribution

## 1. Overview

App distribution is the end-to-end pipeline that takes a compiled iOS app from a developer's machine to users' devices. It requires understanding four interconnected systems: **code signing** (cryptographic certificates and provisioning profiles that prove an app's origin and authorise it to run on specific devices), **entitlements** (capability declarations embedded in the binary that gate access to platform features like push notifications, Keychain sharing, and App Groups), **distribution channels** (TestFlight for beta, App Store for production, Enterprise for internal apps), and **automation** (Fastlane and CI/CD pipelines that eliminate manual steps and make distribution repeatable). Every iOS developer must understand how these systems interact: an app that builds locally can fail to install on a device because of a misconfigured provisioning profile, or fail App Review because of an entitlement not matching the App ID configuration.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Code Signing](code-signing.md) | Certificates (development vs distribution), provisioning profiles, signing identities, Xcode automatic signing |
| 2 | [Entitlements](entitlements.md) | Push notifications, Keychain access groups, App Groups, iCloud, associated domains |
| 3 | [Distribution](distribution.md) | TestFlight, App Store Connect, App Review, Enterprise distribution, Ad Hoc |
| 4 | [Fastlane & CI/CD](fastlane-cicd.md) | Fastlane tools (`cert`, `sigh`, `gym`, `pilot`, `deliver`), GitHub Actions workflow, `match` for certificate management |

## 3. Distribution Pipeline

```
Source code
    ↓
Build (xcodebuild / Xcode)
    ↓
Code Sign (Developer certificate + Provisioning Profile + Entitlements)
    ↓
Archive (.xcarchive)
    ↓
Export IPA (Ad Hoc / App Store / Enterprise)
    ↓
Upload to App Store Connect / TestFlight / MDM
    ↓
Users
```

## 4. Quick Reference

| Concept | Key Detail |
|---------|-----------|
| Development certificate | Signs builds for device debugging — tied to a specific developer |
| Distribution certificate | Signs builds for TestFlight / App Store / Enterprise — usually one per team |
| Provisioning profile | Binds app ID + certificate + device UDIDs (dev/ad hoc) or no devices (App Store) |
| Entitlements | Embedded in the binary at build time; must match App ID capabilities |
| TestFlight | Up to 10,000 external testers; builds expire after 90 days |
| App Store | Requires App Review; production distribution |
| Enterprise | In-house distribution without App Store; requires Apple Developer Enterprise Program |

## 5. Related Topics

- [Security — Data Security](../14-security/data-security.md) — Keychain used via entitlements
- [Security — App Security](../14-security/app-security.md) — code signing as integrity mechanism
- [Testing — UI Testing](../11-testing/ui-testing.md) — CI pipelines run tests before distribution
