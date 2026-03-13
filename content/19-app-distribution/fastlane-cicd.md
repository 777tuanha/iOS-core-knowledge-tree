# Fastlane & CI/CD

## 1. Overview

Fastlane is a Ruby-based automation tool that wraps Xcode's command-line tools (`xcodebuild`, `xcrun altool`, `agvtool`) and the App Store Connect API into composable actions called **actions** and **lanes**. Core tools: `match` (certificate and provisioning profile sync via an encrypted Git repo), `gym` (build and archive), `scan` (run tests), `pilot` (upload and manage TestFlight builds), and `deliver` (upload metadata, screenshots, and submit for App Review). Fastlane is integrated into CI/CD pipelines (GitHub Actions, Bitrise, CircleCI, Xcode Cloud) to make distribution repeatable and auditable. A CI/CD pipeline for iOS automates the chain: pull → install dependencies → run tests → build → sign → upload to TestFlight or App Store → notify. The goal is that any team member can trigger a release with a single command or git push, without knowing the details of code signing or App Store Connect navigation.

## 2. Simple Explanation

Fastlane is a recipe book for app distribution. Each action is a single step (bake a cake, apply icing). A lane is a complete recipe (birthday cake = bake + ice + add candles). `match` is the shared pantry: all team members and CI machines go to the same pantry to get the same ingredients (certificates, profiles) — nobody bakes with different flour. CI/CD is the automated kitchen: every time a new recipe card arrives (git push), the kitchen automatically follows it start-to-finish without a human needing to watch.

## 3. Deep iOS Knowledge

### Fastlane match

`match` is the recommended approach for team certificate management. It stores all certificates and provisioning profiles encrypted in a private Git repository (or S3/Google Cloud Storage).

**Setup:**
```bash
fastlane match init    # configures storage backend and creates Matchfile
fastlane match development   # creates/fetches dev certificate + profiles
fastlane match appstore      # creates/fetches distribution certificate + App Store profiles
fastlane match adhoc         # Ad Hoc profiles
```

**Matchfile:**
```ruby
git_url("git@github.com:acme/ios-certs.git")
storage_mode("git")
type("appstore")          # default type
app_identifier(["com.acme.App", "com.acme.App.NotificationExtension"])
username("ci@acme.com")   # Apple ID for portal access (or use API key)
```

**On CI: read-only mode** — prevents CI from accidentally modifying shared certs:
```bash
fastlane match appstore --readonly
```

**Rotating a certificate**: when the distribution certificate expires (1 year), run `fastlane match appstore --force` on a developer machine. `match` revokes the old cert, creates a new one, re-generates all profiles, and pushes to the encrypted repo. CI runners automatically pick up the new cert on next run.

### Fastlane gym

`gym` wraps `xcodebuild archive` + `xcodebuild -exportArchive`:

```ruby
gym(
  scheme: "MyApp",
  configuration: "Release",
  export_method: "app-store",           # "ad-hoc" | "enterprise" | "development"
  output_directory: "./build",
  output_name: "MyApp.ipa",
  export_options: {
    provisioningProfiles: {
      "com.acme.App" => "match AppStore com.acme.App",
      "com.acme.App.NotificationServiceExtension" =>
        "match AppStore com.acme.App.NotificationServiceExtension"
    }
  },
  xcargs: "OTHER_SWIFT_FLAGS='-D RELEASE'"   # additional build flags
)
```

### Fastlane scan

`scan` runs the test suite and generates JUnit XML reports for CI consumption:

```ruby
scan(
  scheme: "MyAppTests",
  device: "iPhone 16 Pro",
  output_types: "junit,html",
  output_directory: "./test-results",
  result_bundle: true,           # generates .xcresult for Xcode Cloud / GitHub
  fail_build: true               # fail the lane if any test fails
)
```

### Fastlane pilot

`pilot` manages TestFlight builds:

```ruby
pilot(
  ipa: "./build/MyApp.ipa",
  skip_waiting_for_build_processing: true,    # don't block CI while Apple processes
  distribute_external: true,
  groups: ["Beta Testers", "QA Team"],
  changelog: "See CHANGELOG.md for details",
  beta_app_feedback_email: "beta@acme.com",
  notify_external_testers: true
)
```

### Fastlane deliver

`deliver` uploads metadata and submits to App Review:

```ruby
deliver(
  ipa: "./build/MyApp.ipa",
  metadata_path: "./metadata",              # localised metadata per language
  screenshots_path: "./screenshots",         # per-device screenshots
  submit_for_review: true,
  automatic_release: false,                 # manual release toggle in ASC
  phased_release: true,
  submission_information: {
    export_compliance_uses_encryption: true,
    export_compliance_is_exempt: true       # HTTPS-only encryption (exempt)
  },
  precheck_include_in_app_purchases: false
)
```

### CI/CD Pipeline with GitHub Actions

**Structure:**
```
.github/
└── workflows/
    ├── test.yml        # runs on every PR
    ├── beta.yml        # runs on push to develop
    └── release.yml     # runs on push to main / manual trigger
```

**GitHub Actions workflow — beta lane:**
```yaml
# .github/workflows/beta.yml
name: Beta

on:
  push:
    branches: [develop]

jobs:
  beta:
    runs-on: macos-15
    steps:
      - uses: actions/checkout@v4

      - name: Set up Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.3'
          bundler-cache: true   # caches gems from Gemfile.lock

      - name: Install dependencies
        run: bundle install

      - name: Set up SSH for match
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.MATCH_SSH_PRIVATE_KEY }}

      - name: Run tests
        run: bundle exec fastlane scan
        env:
          DEVELOPER_DIR: /Applications/Xcode_16.app

      - name: Build and upload to TestFlight
        run: bundle exec fastlane beta
        env:
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
          APP_STORE_CONNECT_API_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          APP_STORE_CONNECT_API_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          APP_STORE_CONNECT_API_KEY_CONTENT: ${{ secrets.ASC_KEY_CONTENT }}
          DEVELOPER_DIR: /Applications/Xcode_16.app
```

### Fastfile Structure

```ruby
# fastlane/Fastfile

default_platform(:ios)

platform :ios do

  before_all do
    # Set up App Store Connect API authentication (preferred over Apple ID)
    app_store_connect_api_key(
      key_id: ENV["APP_STORE_CONNECT_API_KEY_ID"],
      issuer_id: ENV["APP_STORE_CONNECT_API_ISSUER_ID"],
      key_content: ENV["APP_STORE_CONNECT_API_KEY_CONTENT"],
      is_key_content_base64: true
    )
  end

  # ── Test lane ────────────────────────────────────────────────
  lane :test do
    scan(
      scheme: "MyAppTests",
      device: "iPhone 16 Pro",
      output_types: "junit",
      output_directory: "./test-results"
    )
  end

  # ── Beta lane (TestFlight) ────────────────────────────────────
  lane :beta do
    # Sync certificates and profiles
    match(type: "appstore", readonly: true)

    # Increment build number using CI run number
    increment_build_number(build_number: ENV["GITHUB_RUN_NUMBER"] || Time.now.to_i)

    # Build
    gym(
      scheme: "MyApp",
      configuration: "Release",
      export_method: "app-store"
    )

    # Upload to TestFlight
    pilot(
      skip_waiting_for_build_processing: true,
      distribute_external: false,
      changelog: changelog_from_git_commits(merge_commit_filtering: "exclude_merges")
    )

    # Notify Slack
    slack(
      message: "New beta build uploaded to TestFlight :rocket:",
      channel: "#ios-releases",
      slack_url: ENV["SLACK_WEBHOOK_URL"]
    ) if ENV["SLACK_WEBHOOK_URL"]
  end

  # ── Release lane (App Store) ──────────────────────────────────
  lane :release do
    ensure_git_status_clean

    # Sync certificates
    match(type: "appstore", readonly: true)

    # Run tests
    test

    # Bump version (marketing version from git tag or manual input)
    version = prompt(text: "Version number: ") unless ENV["VERSION"]
    increment_version_number(version_number: ENV["VERSION"] || version)
    increment_build_number(build_number: ENV["GITHUB_RUN_NUMBER"] || Time.now.to_i)

    # Build
    gym(
      scheme: "MyApp",
      configuration: "Release",
      export_method: "app-store"
    )

    # Upload and submit
    deliver(
      submit_for_review: true,
      phased_release: true,
      automatic_release: false
    )

    # Tag
    add_git_tag(tag: "v#{get_version_number}")
    push_git_tags
  end

  # ── Error handler ─────────────────────────────────────────────
  error do |lane, exception|
    slack(
      message: "Lane :#{lane} failed: #{exception.message}",
      success: false,
      channel: "#ios-releases",
      slack_url: ENV["SLACK_WEBHOOK_URL"]
    ) if ENV["SLACK_WEBHOOK_URL"]
  end

end
```

### Xcode Cloud

Apple's native CI/CD integrated into Xcode and App Store Connect. Workflows defined in Xcode, triggered by git events. Xcode Cloud handles code signing automatically using the team's certificates. Suited for teams who want zero CI infrastructure management. Limitations: fewer customisation options than GitHub Actions, costs are metered by compute hours, no self-hosted runners.

## 4. Practical Usage

```ruby
# Gemfile — pins Fastlane and plugin versions
source "https://rubygems.org"

gem "fastlane", "~> 2.220"
gem "cocoapods", "~> 1.15"

# fastlane/Appfile — app identity
app_identifier("com.acme.App")
apple_id("ci@acme.com")
team_id("XXXXXXXXXX")

# fastlane/Matchfile
git_url("git@github.com:acme/ios-certs.git")
type("appstore")
app_identifier([
  "com.acme.App",
  "com.acme.App.NotificationServiceExtension",
  "com.acme.App.ShareExtension"
])
```

```bash
# ── One-time match bootstrap (run by a team admin) ────────────
fastlane match appstore   # creates certs + profiles for all app_identifiers
fastlane match development

# ── Routine developer setup on a new machine ─────────────────
fastlane match development --readonly   # installs without modifying portal

# ── Force-regenerate after certificate expiry ─────────────────
fastlane match appstore --force        # revoke old, create new, push to repo

# ── Running a lane locally ────────────────────────────────────
bundle exec fastlane beta              # use bundle exec to respect Gemfile.lock
bundle exec fastlane release VERSION=2.5.0
```

## 5. Interview Questions & Answers

### Basic

**Q: What does `fastlane match` solve and how does it work?**

A: `fastlane match` solves the problem of certificate and provisioning profile inconsistency across a team. Without it, each developer generates their own certificates, and CI machines require manual `.p12` imports. `match` establishes a single source of truth: all certificates and profiles are stored encrypted (using `openssl`) in a private Git repository (or S3/GCS). When any developer or CI machine runs `fastlane match`, it: (1) decrypts and downloads the existing certificate and profile from the repo, (2) installs them in the macOS Keychain and `~/Library/MobileDevice/Provisioning Profiles`, (3) optionally updates Xcode project settings to reference the correct profiles. If a cert is expired or doesn't exist yet, `match` creates it via the App Store Connect API and pushes it encrypted to the repo. The passphrase (`MATCH_PASSWORD`) is the only secret that needs to be shared — everything else is derived from it.

**Q: What is the difference between `gym`, `pilot`, and `deliver` in Fastlane?**

A: They cover three different stages of distribution: **`gym`** is the build step — it calls `xcodebuild archive` and `xcodebuild -exportArchive` to produce a signed `.ipa`. It handles the signing configuration, export options, and build settings. **`pilot`** is the TestFlight step — it uploads the `.ipa` to App Store Connect, manages TestFlight groups, sends notifications to testers, and (optionally) waits for processing to complete. It's used for beta distribution. **`deliver`** is the App Store submission step — it uploads metadata (description, keywords, release notes), screenshots, and the build, then optionally submits for App Review. It reads from a `metadata/` directory structure with one folder per locale. A complete release lane typically calls all three: `gym` → `pilot` (or skip and call `deliver` directly for a production submission).

### Hard

**Q: How do you increment build numbers correctly on CI to avoid TestFlight rejections?**

A: TestFlight rejects builds with a CFBundleVersion (build number) that's ≤ the previously uploaded build for the same CFBundleShortVersionString (marketing version). Three strategies: (1) **CI run number**: use the CI environment's monotonically increasing run counter — `increment_build_number(build_number: ENV["GITHUB_RUN_NUMBER"])`. GitHub Actions, Bitrise, and CircleCI all provide unique sequential numbers. This is the simplest and most reliable approach. (2) **Unix timestamp**: `increment_build_number(build_number: Time.now.to_i)` — always increasing but not human-readable. (3) **Latest build number from App Store Connect**: query the API for the current max build number and increment: Fastlane's `latest_testflight_build_number` action fetches it automatically. Never commit the build number change to the main branch — the CI build number should be set at build time, not stored in `Info.plist` in source control (or use a separate `BuildNumber.xcconfig` that's `.gitignored`). The marketing version (`CFBundleShortVersionString`) is stored in source control and bumped manually (or via the release lane) at the start of a new version.

**Q: How do you set up a CI pipeline that signs with match on a fresh macOS runner without an Apple ID?**

A: Use the **App Store Connect API key** (not Apple ID) for all portal operations: create an API key in App Store Connect → Users and Access → Keys with App Manager role. Download the `.p8` private key file. Store the Key ID, Issuer ID, and base64-encoded key content as CI secrets. In the Fastfile: `app_store_connect_api_key(key_id:, issuer_id:, key_content:, is_key_content_base64: true)` — call this in `before_all`. For `match`: the API key is used for portal operations (downloading/creating profiles); the `MATCH_PASSWORD` secret decrypts the Git repo contents. SSH access to the private match repo is configured via `MATCH_SSH_PRIVATE_KEY` secret. The workflow: (1) CI runner checks out the repo, (2) `webfactory/ssh-agent` loads the match SSH key, (3) `fastlane match appstore --readonly` downloads and installs certs, (4) `gym` builds and signs using the installed profile, (5) `pilot` uploads using the API key — no Apple ID credentials needed anywhere.

### Expert

**Q: Design a multi-app Fastlane setup for a suite of 3 iOS apps (main app + 2 companion apps) that share a certificate but have separate App IDs, extensions, and release schedules.**

A: Four-component design: (1) **Single `match` repo with per-app profiles**: `app_identifier(["com.acme.Main", "com.acme.Main.Widget", "com.acme.Notes", "com.acme.Keyboard"])` — one distribution certificate for all apps (shared via `match`); separate App Store provisioning profiles per bundle ID. (2) **Per-app Fastfile lanes**: a shared `Fastfile` with a `build_app(app_id:, scheme:)` helper action; top-level lanes `release_main`, `release_notes`, `release_keyboard` that call it with the appropriate parameters. Alternatively, use a `Fastfile` that reads the target app from an environment variable (`APP_TARGET = ENV["APP_TARGET"]`) — CI passes `APP_TARGET=Main` or `APP_TARGET=Notes`. (3) **Separate GitHub Actions workflows**: `release-main.yml`, `release-notes.yml`, `release-keyboard.yml` — triggered manually via `workflow_dispatch` with a `version` input. They set `APP_TARGET` and `VERSION` environment variables before calling `bundle exec fastlane release`. All three share the same secrets (MATCH_PASSWORD, ASC API key) because they use the same team. (4) **Shared metadata structure**: `metadata/main/`, `metadata/notes/`, `metadata/keyboard/` — each with localised descriptions and screenshots. The `deliver` action is called with the appropriate `metadata_path` and `screenshots_path` per app. This avoids a separate repo per app while keeping release pipelines independent.

## 6. Common Issues & Solutions

**Issue: `fastlane match` fails with "Could not find a valid certificate" after rotating.**

Solution: Another team member or CI run may have revoked the certificate while regenerating — check App Store Connect → Certificates for the current valid certificate. Run `fastlane match appstore --force` from one developer machine only (others should use `--readonly`) to create a new certificate and push to the match repo. Ensure the MATCH_PASSWORD environment variable is identical on all machines — a typo in the password causes decryption failures that look like missing certificates.

**Issue: CI fails at the `gym` step with "User interaction not allowed" when accessing Keychain.**

Solution: The macOS CI runner's Keychain is locked or requires a password prompt. Fix with: `security unlock-keychain -p "" ~/Library/Keychains/login.keychain` before running `gym`. Some CI providers (Bitrise, GitHub Actions hosted runners) handle this automatically; self-hosted runners may not. Also set the Keychain's lock timeout to a high value so it doesn't re-lock during a long build: `security set-keychain-settings -lut 7200 ~/Library/Keychains/login.keychain`.

## 7. Related Topics

- [Code Signing](code-signing.md) — certificates and profiles managed by `match`
- [Distribution](distribution.md) — TestFlight and App Store submission via `pilot` and `deliver`
- [Testing — UI Testing](../11-testing/ui-testing.md) — `scan` runs UI tests in the CI pipeline
- [Observability — Crash Reporting](../17-observability/crash-reporting.md) — dSYM upload in the CI pipeline
