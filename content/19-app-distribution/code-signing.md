# Code Signing

## 1. Overview

Code signing cryptographically binds an app binary to a developer or team identity, enabling iOS to verify who built the app and whether it has been tampered with since signing. The system has three components: **certificates** (X.509 public-key certificates stored in Keychain that identify a developer or team), **provisioning profiles** (plist files embedded in the app that bind an App ID, certificates, and device UDIDs to define where and how an app can run), and **signing identities** (a certificate paired with its private key in macOS Keychain — the private key signs the binary; the certificate allows iOS to verify the signature). Automatic signing in Xcode manages this for most teams; manual signing is needed for advanced configurations (multiple targets, custom entitlements per environment, CI machines without Keychain access).

## 2. Simple Explanation

Code signing is like a notarised letter: the notary (Apple) gives a developer a stamp (certificate). When you write a letter (build an app), you stamp it. The recipient (iOS) can verify the stamp is genuine and the letter hasn't been altered. A provisioning profile is the permission slip that says "this stamp is allowed to be used at this address (App ID) and sent to these people (devices)." Without a matching permission slip, iOS refuses to run the app even if the stamp is valid.

## 3. Deep iOS Knowledge

### Certificates

**Types:**
- **Apple Development**: signs debug builds for running on registered devices during development.
- **Apple Distribution**: signs builds for TestFlight, App Store, and Enterprise — one per team (shared via private key export).

**Lifecycle:**
1. Generate a Certificate Signing Request (CSR) from Keychain Access → Certificate Assistant.
2. Upload to developer.apple.com → Certificates, Identifiers & Profiles.
3. Apple signs it and returns the certificate.
4. Install in macOS Keychain — paired with the private key from step 1.

**Private key export**: to share a distribution certificate across a team or CI machines, export the certificate + private key as a `.p12` file (password-protected) from Keychain Access. Import it on any machine that needs to sign.

### Provisioning Profiles

A provisioning profile is a signed plist containing:
- **App ID**: the bundle identifier (explicit: `com.example.App` or wildcard: `com.example.*`).
- **Certificates**: the list of developer certificates allowed to sign with this profile.
- **Devices** (development and Ad Hoc only): UDID list of registered devices.
- **Entitlements**: the capabilities the profile grants (push, iCloud, App Groups).
- **Expiry**: profiles expire after 1 year; expired profiles prevent installation.

**Profile types:**

| Type | Who can install | Use |
|------|----------------|-----|
| Development | Registered devices only | Debug builds |
| Ad Hoc | Registered devices only (up to 100) | Beta testing without TestFlight |
| App Store | Anyone (via App Store / TestFlight) | Production / TestFlight |
| Enterprise | Anyone within the organisation | Internal apps (no App Review) |

### How Signing Works at Build Time

1. Xcode compiles the app and generates the `.app` bundle.
2. The codesign tool hashes every file in the bundle.
3. The hash is signed with the private key from the signing identity.
4. The signature is stored in `_CodeSignature/CodeResources` inside the bundle.
5. The selected provisioning profile is copied into the bundle as `embedded.mobileprovision`.
6. On device, iOS verifies the signature against the certificate in the profile and checks the device UDID is listed (for development/Ad Hoc profiles).

### Automatic vs Manual Signing

**Automatic signing** (Xcode → Signing & Capabilities → "Automatically manage signing"):
- Xcode creates/renews certificates and profiles via the Apple Developer Portal API.
- Recommended for most teams and local development.
- Limitations: doesn't work on CI machines without Apple ID credentials; can conflict with multiple targets.

**Manual signing**:
- Choose a specific signing identity and provisioning profile in Xcode build settings.
- Required for CI/CD (use `match` to sync profiles via a private Git repo or S3 — see [Fastlane & CI/CD](fastlane-cicd.md)).
- Required when distributing multiple flavours (dev/staging/prod) that use different App IDs or entitlements.

### Build Settings

```
CODE_SIGN_IDENTITY = "Apple Distribution: Acme Corp (TEAM_ID)"
PROVISIONING_PROFILE_SPECIFIER = "com.acme.App AppStore"
DEVELOPMENT_TEAM = "XXXXXXXX"
```

Override per configuration:

```
// Xcode build settings via xcconfig:
CODE_SIGN_IDENTITY[config=Debug] = Apple Development
CODE_SIGN_IDENTITY[config=Release] = Apple Distribution
PROVISIONING_PROFILE_SPECIFIER[config=Debug] = com.acme.App Development
PROVISIONING_PROFILE_SPECIFIER[config=Release] = com.acme.App AppStore
```

### Diagnosing Signing Failures

Common errors:

| Error | Cause | Fix |
|-------|-------|-----|
| "No matching provisioning profile found" | Profile doesn't match App ID or is expired | Regenerate profile in portal; run `match` to sync |
| "Code signing is required for product type" | Archive build lacks distribution certificate | Install `.p12` and correct provisioning profile |
| "The identity used to sign the executable is no longer valid" | Certificate expired or revoked | Create new certificate via portal |
| "Provisioning profile doesn't include the [X] entitlement" | Entitlement not enabled in App ID | Enable capability in App ID; regenerate profile |

```bash
# Inspect an installed provisioning profile:
security cms -D -i ~/Library/MobileDevice/Provisioning\ Profiles/<uuid>.mobileprovision

# List signing identities in Keychain:
security find-identity -v -p codesigning

# Verify a signed app:
codesign -dv --verbose=4 /path/to/App.app
```

## 4. Practical Usage

```swift
// This is build configuration via xcconfig files — not Swift code.
// xcconfig files are assigned to build configurations in Xcode target settings.

// ── Debug.xcconfig ────────────────────────────────────────────
// CODE_SIGN_IDENTITY = Apple Development
// PROVISIONING_PROFILE_SPECIFIER = com.acme.App Development
// DEVELOPMENT_TEAM = XXXXXXXX

// ── Release.xcconfig ──────────────────────────────────────────
// CODE_SIGN_IDENTITY = Apple Distribution
// PROVISIONING_PROFILE_SPECIFIER = com.acme.App AppStore
// DEVELOPMENT_TEAM = XXXXXXXX
```

```bash
# ── Manual archive and export from the command line ───────────

# 1. Archive
xcodebuild archive \
  -scheme MyApp \
  -configuration Release \
  -archivePath build/MyApp.xcarchive \
  CODE_SIGN_STYLE=Manual \
  PROVISIONING_PROFILE_SPECIFIER="com.acme.App AppStore"

# 2. Export IPA (ExportOptions.plist specifies method and entitlements)
xcodebuild -exportArchive \
  -archivePath build/MyApp.xcarchive \
  -exportOptionsPlist ExportOptions.plist \
  -exportPath build/output/
```

```xml
<!-- ExportOptions.plist for App Store export -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>                  <!-- app-store / ad-hoc / enterprise / development -->
    <key>teamID</key>
    <string>XXXXXXXXXX</string>
    <key>uploadBitcode</key>
    <false/>
    <key>uploadSymbols</key>
    <true/>
    <key>signingStyle</key>
    <string>manual</string>
    <key>provisioningProfiles</key>
    <dict>
        <key>com.acme.App</key>
        <string>com.acme.App AppStore</string>
    </dict>
</dict>
</plist>
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a provisioning profile and why is it needed?**

A: A provisioning profile is a signed file (produced by Apple's developer portal) that authorises an app to run in a specific context. It contains: the App ID (bundle identifier) the profile applies to, the list of developer certificates whose signatures it trusts, the UDIDs of registered devices (for development and Ad Hoc profiles), the entitlements the app is allowed to use, and an expiry date. iOS checks all four conditions at install time: the app's signature must be valid, the certificate must be in the profile, the device UDID must be listed (for dev/Ad Hoc), and the entitlements in the binary must not exceed those in the profile. Provisioning profiles exist because Apple needs a mechanism to control which apps can run on which devices — it's the enforcement layer between the developer portal permissions and the device.

**Q: What is the difference between a development certificate and a distribution certificate?**

A: A **development certificate** (Apple Development) is used to sign debug builds and allows the app to run on devices registered to your developer account. Multiple team members can each have their own development certificate. A **distribution certificate** (Apple Distribution) is used to sign builds intended for TestFlight, App Store, or Enterprise distribution. It's typically shared across the team (by exporting the `.p12` private key file) because only one distribution certificate per team is needed. Distribution-signed apps can be uploaded to App Store Connect or distributed via Enterprise MDM; they cannot be installed via Xcode.

### Hard

**Q: How does code signing prevent tampering with an app binary?**

A: At build time, the `codesign` tool computes a cryptographic hash (SHA-256) of every file in the `.app` bundle — executables, frameworks, resources, Info.plist. These hashes are stored in `_CodeSignature/CodeResources`. The tool then signs a root hash with the developer's private key. The signature is tied to the public key in the certificate, which Apple itself has signed. At install and launch time, iOS: (1) verifies Apple's signature on the certificate (trust chain), (2) uses the certificate's public key to verify the developer's signature on the bundle, (3) rehashes each file and compares against the stored hashes. If any file has changed since signing — even a single byte — the hash comparison fails and iOS refuses to run the app. This makes it cryptographically infeasible to modify an app (inject malware, alter resources) without invalidating the signature.

**Q: How do you manage certificates and provisioning profiles on a team with 10 developers and a CI/CD pipeline?**

A: Use **Fastlane `match`**: it stores all certificates and provisioning profiles in an encrypted Git repository (or S3 bucket). Each developer and the CI machine runs `fastlane match development` or `fastlane match appstore` to fetch and install the shared certificates. This ensures every machine uses the same signing identities. The workflow: (1) One team member creates the certificates and profiles via `fastlane match` on first run — they're encrypted with a passphrase and pushed to the private repo. (2) All other developers and CI runners decrypt and install them by running `match` with the passphrase (stored as a secret in CI). (3) When a profile expires or a new device is added, one developer runs `fastlane match --force_for_new_devices` to regenerate and re-push. No manual portal management, no email-sharing `.p12` files.

### Expert

**Q: A CI machine is signing with the correct certificate and provisioning profile but the build fails with "entitlement not supported." How do you diagnose and fix this?**

A: Three-step diagnosis: (1) **Extract the entitlements from the binary**: `codesign -d --entitlements :- /path/to/App.app` — compare these to what's in the provisioning profile (`security cms -D -i embedded.mobileprovision | grep -A 20 Entitlements`). Any entitlement in the binary that's absent from the profile causes the error. (2) **Check the App ID capabilities** in developer.apple.com — the capability (e.g., Push Notifications, App Groups) must be enabled there before regenerating the profile. If the App ID uses a wildcard (`com.example.*`), some capabilities (Push Notifications, iCloud, Sign in with Apple) cannot be used and require switching to an explicit App ID. (3) **Regenerate the provisioning profile** after enabling the capability in the App ID. On a CI machine using `match`: run `fastlane match appstore --force` to regenerate and commit the updated profile to the match repo, then re-run the CI pipeline. Common root cause in CI: a developer enabled a capability locally (Xcode auto-signed and updated the profile on their machine) but the `match` repo was never updated — so CI uses the stale profile that lacks the new entitlement.

## 6. Common Issues & Solutions

**Issue: "Your build settings specify a provisioning profile with the UUID '…', however, no such provisioning profile was found."**

Solution: The profile exists in the portal but hasn't been downloaded to this machine. Run `fastlane match` to sync all profiles, or in Xcode: Preferences → Accounts → download manual profiles. If the profile is missing from the portal, it may have been deleted — regenerate it.

**Issue: Archive succeeds on developer machine but fails on CI with "No identity found in keychain."**

Solution: The CI machine's Keychain doesn't have the signing identity (certificate + private key). Using `match`: ensure the `MATCH_PASSWORD` secret is set in CI and `fastlane match appstore --readonly` runs as a pre-step. Without `match`: export the `.p12` from the developer machine, upload as a CI secret, and import with `security import certificate.p12 -k ~/Library/Keychains/login.keychain -P "$P12_PASSWORD" -T /usr/bin/codesign`.

## 7. Related Topics

- [Entitlements](entitlements.md) — capabilities enabled in the provisioning profile
- [Fastlane & CI/CD](fastlane-cicd.md) — `match` for certificate and profile management
- [Distribution](distribution.md) — how signed archives are uploaded and distributed
- [Security — App Security](../14-security/app-security.md) — code signing as an integrity mechanism
