# Distribution

## 1. Overview

iOS app distribution covers the pipeline from a signed archive to users' devices through three channels: **TestFlight** (Apple's beta distribution platform — up to 10,000 external testers with crash reporting and opt-in feedback, no device registration required), **App Store** (production distribution via App Review — review typically takes 1–3 days for new submissions and 24 hours for updates), and **Enterprise distribution** (in-house apps for large organisations enrolled in the Apple Developer Enterprise Program — bypasses App Review but requires an MDM or direct download mechanism). Each channel has distinct signing requirements, review processes, and limitations. App Store Connect is the central portal for all three: managing metadata, screenshots, pricing, TestFlight groups, and App Review submissions. Understanding the review guidelines and common rejection reasons is as important as understanding the technical submission process.

## 2. Simple Explanation

Distribution channels are like different publishing routes for a book. TestFlight is like sending advance copies to reviewers — quick, controlled, and testers can give direct feedback. The App Store is like a commercial publisher — there's an editorial review process (App Review) to ensure quality, but once approved, anyone can buy/download. Enterprise distribution is like printing books in-house for company employees — no external review, but you manage the printing and delivery yourself, and only your employees can get it.

## 3. Deep iOS Knowledge

### TestFlight

TestFlight distributes pre-release builds to internal and external testers via App Store Connect.

**Internal testing:**
- Up to 100 internal testers (must be members of the App Store Connect team).
- Builds available immediately after processing (~5–15 minutes for bitcode re-compilation).
- No App Review required.
- Testers install via the TestFlight app.

**External testing:**
- Up to 10,000 external testers — email invites or a public link.
- Requires Beta App Review (usually same-day, less thorough than full App Review).
- Builds expire after 90 days.
- Crash reports and tester feedback (screenshots + comments) visible in App Store Connect.

**Build lifecycle:**
1. Upload `.ipa` via Xcode Organizer, `xcodebuild`, or `altool`/`notarytool`.
2. App Store Connect processes the build (~5–20 min).
3. Add build to a TestFlight group.
4. Testers receive email or notification.

**Managing feedback:**

TestFlight crash reports are symbolicated using the dSYM uploaded during the build. Enable automatic dSYM upload in the build phase or use Fastlane:

```bash
fastlane pilot upload --ipa ./build/MyApp.ipa --skip_waiting_for_build_processing
```

### App Store Submission

**Submission checklist:**
1. **App metadata**: name, subtitle, description, keywords, support URL, privacy policy URL.
2. **Screenshots**: required for every supported device family (iPhone 6.5", iPhone 5.5", iPad Pro 12.9" — required even if iPad is not a primary target).
3. **App Review information**: demo credentials for reviewers (if login-gated), reviewer notes.
4. **Privacy details**: data collection declarations (App Privacy nutrition label) — required for all apps.
5. **Export compliance**: HTTPS encryption requires an ITSAppUsesNonExemptEncryption declaration.
6. **Build**: uploaded `.ipa` with `aps-environment = production` entitlement and App Store provisioning profile.

**Common rejection reasons:**

| Reason | Guideline | Fix |
|--------|-----------|-----|
| Crashes during review | 2.1 | Fix the crash; provide reviewer notes if it's environment-dependent |
| Login-gated without demo credentials | 2.1 | Add username/password in Review Notes |
| Requesting unnecessary permissions | 5.1.1 | Remove entitlements and usage descriptions not used by the app |
| Guideline 4.2 — minimum functionality | 4.2 | Apps must not be trivially thin; add value beyond a web clip |
| Privacy policy missing or inaccessible | 5.1.1 | Host the policy publicly; add URL to App Store listing |
| Inaccurate screenshots | 2.3.3 | Screenshots must match the current build |
| Inadequate data deletion mechanism | 5.1.1 | If the app collects personal data, provide in-app account deletion |

**Phased release**: gradually roll out an update to a percentage of users over 7 days (10% → 20% → 50% → 100%). Useful for catching post-launch crashes before 100% rollout. Can be paused in App Store Connect.

### Enterprise Distribution

Apple Developer Enterprise Program ($299/year, requires organisation verification) allows distributing apps outside the App Store using:

**Methods:**
1. **MDM (Mobile Device Management)**: the organisation's MDM server (Jamf, Workspace ONE) pushes the `.ipa` to enrolled devices — no user interaction required.
2. **Direct download**: host the `.plist` and `.ipa` on a web server; users tap a custom `itms-services://` link to install.
3. **Internal marketplace**: custom internal App Store portal served over HTTPS.

**Signing:** Enterprise builds use the Enterprise distribution certificate and an In-House provisioning profile (no device UDIDs — any device can install). The profile must be kept current (1-year expiry).

**Risk:** Enterprise certificates can be revoked by Apple (as happened with public misuse cases). If the certificate is revoked, all apps signed with it stop launching immediately on all devices.

### Ad Hoc Distribution

- Signs an `.ipa` with the distribution certificate and an Ad Hoc provisioning profile.
- Maximum 100 registered device UDIDs per profile.
- Distribution outside App Store: email the `.ipa`, use a service like Diawi or Firebase App Distribution.
- Use case: testing on specific devices not enrolled in TestFlight; device farm testing (Bitrise, AWS Device Farm).

### App Store Connect API

Automate submissions using the App Store Connect REST API (or Fastlane which wraps it):

```bash
# Fastlane deliver (upload metadata + screenshots + build)
fastlane deliver \
  --ipa ./build/MyApp.ipa \
  --metadata_path ./metadata \
  --screenshots_path ./screenshots \
  --submit_for_review \
  --automatic_release

# Fastlane pilot (TestFlight upload)
fastlane pilot upload \
  --ipa ./build/MyApp.ipa \
  --distribute_external true \
  --groups "Beta Testers" \
  --changelog "Bug fixes and performance improvements"
```

## 4. Practical Usage

```bash
# ── App Store submission workflow ──────────────────────────────

# 1. Archive
xcodebuild clean archive \
  -scheme MyApp \
  -configuration Release \
  -archivePath ./build/MyApp.xcarchive

# 2. Export IPA
xcodebuild -exportArchive \
  -archivePath ./build/MyApp.xcarchive \
  -exportOptionsPlist ./ExportOptions-AppStore.plist \
  -exportPath ./build/output/

# 3. Validate (optional — catches common issues before upload)
xcrun altool --validate-app \
  --file ./build/output/MyApp.ipa \
  --type ios \
  --apiKey "$APP_STORE_KEY_ID" \
  --apiIssuer "$APP_STORE_ISSUER_ID"

# 4. Upload
xcrun altool --upload-app \
  --file ./build/output/MyApp.ipa \
  --type ios \
  --apiKey "$APP_STORE_KEY_ID" \
  --apiIssuer "$APP_STORE_ISSUER_ID"
```

```ruby
# ── Fastfile: full release lane ────────────────────────────────
lane :release do
  # Ensure clean working directory
  ensure_git_status_clean

  # Bump version number
  increment_build_number

  # Run tests
  run_tests(scheme: "MyAppTests")

  # Build and sign
  gym(
    scheme: "MyApp",
    configuration: "Release",
    export_method: "app-store",
    export_options: {
      provisioningProfiles: {
        "com.acme.App" => "com.acme.App AppStore"
      }
    }
  )

  # Upload to TestFlight
  pilot(
    distribute_external: true,
    groups: ["External Beta"],
    changelog: changelog_from_git_commits
  )

  # Tag the release
  add_git_tag(tag: "v#{get_version_number}")
  push_git_tags
end
```

```swift
// ── In-app version check (compare installed vs App Store version) ──
struct AppStoreVersionChecker {
    // Calls the iTunes Lookup API to get the current App Store version
    static func checkForUpdate(bundleID: String) async throws -> String? {
        let url = URL(string: "https://itunes.apple.com/lookup?bundleId=\(bundleID)")!
        let (data, _) = try await URLSession.shared.data(from: url)
        let response = try JSONDecoder().decode(AppStoreLookupResponse.self, from: data)
        return response.results.first?.version
    }
}

struct AppStoreLookupResponse: Decodable {
    let results: [AppStoreResult]
}

struct AppStoreResult: Decodable {
    let version: String
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between TestFlight internal and external testing?**

A: **Internal testing** is limited to members of your App Store Connect team (up to 100 people — developers, testers, managers with team roles). Builds become available to internal testers immediately after App Store Connect processes the upload — no review required. **External testing** opens the beta to up to 10,000 external users who are not team members — invited via email or a public TestFlight link. External builds require **Beta App Review** before being distributed. Beta review is usually completed same-day and checks for crashes and guideline violations. Builds expire after 90 days regardless of test type. Both types support crash reporting via the TestFlight app and feedback submission (screenshots + comments) visible in App Store Connect.

**Q: What is a phased release and when should you use it?**

A: A phased release gradually rolls out an App Store update over 7 days: 1% → 2% → 5% → 10% → 20% → 50% → 100%. Apple determines which users receive the update based on automatic update settings — users who manually update always receive it immediately regardless of phase. Use phased release when: the update has significant changes (new onboarding flow, modified network protocol) where a silent crash in 1% of users is far better than 100% being affected; when you want to monitor crash rates (via Xcode Organizer or Crashlytics) and rollback or investigate before full rollout. You can pause a phased release for up to 30 days in App Store Connect if a critical issue is discovered. A phased release does not support A/B testing — it's a sequential roll-out to random users, not a split test.

### Hard

**Q: How do you handle the 90-day TestFlight expiry for long-running beta programs?**

A: Three strategies: (1) **Automated build uploads**: set up CI/CD (Fastlane `pilot` in a scheduled pipeline) to upload a new build weekly or bi-weekly. This keeps a fresh build available without manual intervention. Each upload increments the build number and resets the 90-day clock. (2) **Build versioning discipline**: ensure CFBundleVersion (build number) is always incremented — TestFlight rejects builds with duplicate build numbers. Use the CI build number (`$BUILD_NUMBER` from CI environment or `agvtool next-version`). (3) **Communicate expiry to testers**: use TestFlight's What to Test notes to inform testers of the build's approximate expiry date and ask them to update. App Store Connect also notifies testers via email when a new build is available.

**Q: What happens when an Enterprise distribution certificate is revoked?**

A: All apps on all devices signed with that certificate stop launching immediately — iOS displays "Unable to verify app" or the app simply fails to open. The revocation takes effect as soon as Apple revokes the certificate (often within minutes) and the device checks certificate validity. Recovery: (1) generate a new Enterprise distribution certificate, (2) re-sign all distributed apps with the new certificate and regenerate the In-House provisioning profile, (3) redistribute all apps via MDM or your internal distribution mechanism. Users cannot install updates automatically — you must push new builds. This is why Enterprise distribution is not recommended for large-scale consumer deployments. To mitigate: monitor your certificate expiry date (1 year) and renew 30–60 days before expiry to avoid disruption; maintain a record of all distributed app versions so you can re-sign them quickly.

### Expert

**Q: Design an App Store submission pipeline that supports three environments (dev/staging/prod) with per-environment code signing, automated version bumping, and TestFlight + App Store release lanes.**

A: Five-component pipeline: (1) **Per-environment app IDs**: `com.acme.App` (production), `com.acme.App.staging` (staging), `com.acme.App.dev` (dev). Three separate App IDs in the portal with corresponding provisioning profiles managed by `fastlane match`. Separate bundle IDs allow all three to be installed simultaneously. (2) **Xcconfig build settings**: `Debug.xcconfig`, `Staging.xcconfig`, `Release.xcconfig` — each specifies `CODE_SIGN_ENTITLEMENTS`, `PRODUCT_BUNDLE_IDENTIFIER`, `PROVISIONING_PROFILE_SPECIFIER`. Staging and Release share the distribution certificate; Debug uses a development certificate. (3) **Fastlane lanes**: `lane :beta` (staging app ID, App Store profile, uploads to TestFlight staging group); `lane :release` (production app ID, App Store profile, uploads to TestFlight then submits for App Review). Both lanes call `increment_build_number` using the CI build number (`ENV["BUILD_NUMBER"]`) and commit/tag the version bump. (4) **CI workflow** (GitHub Actions): `develop` branch → triggers `beta` lane; `main` branch → triggers `release` lane. `match` fetches certificates from the encrypted Git repo using `MATCH_PASSWORD` secret. (5) **Automated metadata**: `fastlane deliver` reads `metadata/` directory (localised descriptions, release notes from `CHANGELOG.md`, screenshots from `screenshots/`) and uploads to App Store Connect. Screenshots are generated once using `fastlane snapshot` (running Xcode UI tests with `XCUIScreenshotCapture`) and committed to the repo.

## 6. Common Issues & Solutions

**Issue: App Store binary was rejected for "Missing Privacy Manifest" or "Required Reason API".**

Solution: Starting with iOS 17 / Xcode 15, Apple requires a `PrivacyInfo.xcprivacy` file for apps and SDKs that use certain APIs (UserDefaults, file timestamps, system boot time, disk space, active keyboard list). Add the privacy manifest file to your app target with the correct `NSPrivacyAccessedAPITypes` entries for each API you use. Third-party SDKs must also provide their own `PrivacyInfo.xcprivacy` — update all SDKs to versions that include it. Xcode's "Generate Privacy Report" (Product → Archive → Distribute → Generate Privacy Report) shows which APIs your app and SDKs access.

**Issue: Build upload to TestFlight fails with "Authentication failed."**

Solution: Use App Store Connect API keys instead of Apple ID credentials — they don't expire and work on CI machines. Create an API key in App Store Connect → Users and Access → Keys with App Manager role. Download the `.p8` file and store the Key ID and Issuer ID as CI secrets. With Fastlane: set `APP_STORE_CONNECT_API_KEY_ID`, `APP_STORE_CONNECT_API_ISSUER_ID`, and `APP_STORE_CONNECT_API_KEY_CONTENT` environment variables.

## 7. Related Topics

- [Code Signing](code-signing.md) — signing the build before distribution
- [Entitlements](entitlements.md) — capability declarations required for App Review
- [Fastlane & CI/CD](fastlane-cicd.md) — automating the full distribution pipeline
- [Observability — Crash Reporting](../17-observability/crash-reporting.md) — TestFlight crash reports and symbolication
