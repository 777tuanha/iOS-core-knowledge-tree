# XCFrameworks

## 1. Overview

An XCFramework (`.xcframework`) is Apple's binary distribution format for frameworks that must run on multiple platforms and architectures simultaneously. It replaces the older "fat binary" (universal) framework approach, which could not accommodate architectures with the same name on different platforms — specifically the collision between `arm64` on physical devices and `arm64` on Apple Silicon Macs running iOS Simulator. An XCFramework is a directory bundle containing one pre-built framework or static library per platform/architecture slice, with an `Info.plist` manifest that tells Xcode which slice to use when building. XCFrameworks are the correct format for distributing closed-source SDKs, Carthage dependencies, and SPM binary targets.

## 2. Simple Explanation

Imagine you're shipping a piece of furniture that must work in both left-hand and right-hand homes. A fat binary is like packing a single piece that tries to accommodate both configurations inside itself — but if both configurations happen to use the same bolt size (arm64), it becomes impossible to tell them apart when unpacking. An XCFramework is like shipping the furniture in two clearly labelled boxes — "Left-Hand Home" and "Right-Hand Home" — with a guide card (Info.plist) telling the installer which box to open. Xcode reads the guide card and uses exactly the right variant for the current build target.

## 3. Deep iOS Knowledge

### XCFramework Bundle Structure

```
MyFramework.xcframework/
├── Info.plist                              ← manifest: maps platforms to slices
├── ios-arm64/                              ← physical iOS devices (arm64)
│   └── MyFramework.framework/
│       ├── MyFramework                     ← dylib or static archive
│       ├── Headers/
│       ├── Modules/
│       │   ├── module.modulemap
│       │   └── MyFramework.swiftmodule/
│       └── Info.plist
├── ios-arm64_x86_64-simulator/             ← iOS Simulator (arm64 + x86_64)
│   └── MyFramework.framework/
│       └── ...
└── macos-arm64_x86_64/                     ← macOS (optional)
    └── MyFramework.framework/
        └── ...
```

The slice directory names encode `<platform>-<arch>[-<variant>]`. Common slices:

| Slice directory | Platform |
|----------------|---------|
| `ios-arm64` | iOS physical device |
| `ios-arm64_x86_64-simulator` | iOS Simulator (Apple Silicon + Intel Mac) |
| `macos-arm64_x86_64` | macOS universal |
| `tvos-arm64` | tvOS device |
| `watchos-arm64_arm64_32` | watchOS device |

### Why Fat Binaries Failed for Simulator

Before XCFramework, vendors shipped "fat" (universal) frameworks containing multiple architecture slices merged with `lipo`. This worked when device = `arm64` and Simulator = `x86_64`. After Apple Silicon Macs introduced `arm64` for the Simulator, a fat framework would contain two `arm64` slices — indistinguishable by `lipo`. XCFramework solves this by keeping slices in separate directories with platform metadata.

### Creating an XCFramework

**Step 1 — Archive each platform slice**:

```bash
# Device slice
xcodebuild archive \
  -scheme MyFramework \
  -destination "generic/platform=iOS" \
  -archivePath "build/MyFramework-iOS.xcarchive" \
  SKIP_INSTALL=NO \
  BUILD_LIBRARY_FOR_DISTRIBUTION=YES

# Simulator slice
xcodebuild archive \
  -scheme MyFramework \
  -destination "generic/platform=iOS Simulator" \
  -archivePath "build/MyFramework-Sim.xcarchive" \
  SKIP_INSTALL=NO \
  BUILD_LIBRARY_FOR_DISTRIBUTION=YES
```

**Step 2 — Combine into XCFramework**:

```bash
xcodebuild -create-xcframework \
  -framework "build/MyFramework-iOS.xcarchive/Products/Library/Frameworks/MyFramework.framework" \
  -framework "build/MyFramework-Sim.xcarchive/Products/Library/Frameworks/MyFramework.framework" \
  -output "output/MyFramework.xcframework"
```

For static libraries (`.a`), use `-library` and `-headers` flags instead of `-framework`.

### Code Signing XCFrameworks

Xcode 12+ requires XCFrameworks to be signed when distributed. Sign with a Developer ID certificate (for direct distribution) or let Xcode re-sign with the app's certificate at embed time.

```bash
# Sign the xcframework:
codesign --timestamp -s "Developer ID Application: Company Name (TEAMID)" \
  output/MyFramework.xcframework
```

For XCFrameworks embedded in an app via SPM binary target, Xcode signs all embedded binaries during the archive step — you do not need to pre-sign.

### SPM Binary Targets

XCFrameworks are the distribution format for SPM `.binaryTarget`:

```swift
// Remote (downloaded from URL):
.binaryTarget(
    name: "MyFramework",
    url: "https://releases.example.com/MyFramework-2.1.0.xcframework.zip",
    checksum: "sha256-hash-of-zip-file"
)

// Local (path relative to Package.swift):
.binaryTarget(
    name: "MyFramework",
    path: "Frameworks/MyFramework.xcframework"
)
```

The remote variant must point to a `.zip` containing the `.xcframework` at its root. The checksum is the SHA-256 of the zip archive (not the xcframework directory).

```bash
# Compute checksum for Package.swift:
swift package compute-checksum MyFramework-2.1.0.xcframework.zip
```

### Including Resources in XCFrameworks

XCFrameworks themselves cannot contain resource bundles. The standard pattern is to ship a separate `MyFramework_Resources.bundle` alongside the XCFramework and reference it in the SPM target's `resources` array, or instruct CocoaPods consumers to include the bundle via `resource_bundles` in the Podspec.

### Verifying an XCFramework

```bash
# Inspect the Info.plist:
cat MyFramework.xcframework/Info.plist

# Check architectures in each slice:
lipo -info "MyFramework.xcframework/ios-arm64/MyFramework.framework/MyFramework"
# → architecture: arm64

lipo -info "MyFramework.xcframework/ios-arm64_x86_64-simulator/MyFramework.framework/MyFramework"
# → architectures: arm64 x86_64

# Verify code signature:
codesign -dv --verbose=4 MyFramework.xcframework
```

## 4. Practical Usage

```bash
#!/bin/bash
# ── Full XCFramework build script ─────────────────────────────
set -e

SCHEME="NetworkKit"
FRAMEWORK_NAME="NetworkKit"
OUTPUT_DIR="build"
XCFRAMEWORK_PATH="$OUTPUT_DIR/$FRAMEWORK_NAME.xcframework"

# Clean previous build
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# ── Step 1: Archive iOS device ────────────────────────────────
xcodebuild archive \
  -scheme "$SCHEME" \
  -destination "generic/platform=iOS" \
  -archivePath "$OUTPUT_DIR/${FRAMEWORK_NAME}-iOS.xcarchive" \
  SKIP_INSTALL=NO \
  BUILD_LIBRARY_FOR_DISTRIBUTION=YES \
  | xcpretty

# ── Step 2: Archive iOS Simulator ────────────────────────────
xcodebuild archive \
  -scheme "$SCHEME" \
  -destination "generic/platform=iOS Simulator" \
  -archivePath "$OUTPUT_DIR/${FRAMEWORK_NAME}-Sim.xcarchive" \
  SKIP_INSTALL=NO \
  BUILD_LIBRARY_FOR_DISTRIBUTION=YES \
  | xcpretty

# ── Step 3: Create XCFramework ────────────────────────────────
xcodebuild -create-xcframework \
  -framework "$OUTPUT_DIR/${FRAMEWORK_NAME}-iOS.xcarchive/Products/Library/Frameworks/${FRAMEWORK_NAME}.framework" \
  -framework "$OUTPUT_DIR/${FRAMEWORK_NAME}-Sim.xcarchive/Products/Library/Frameworks/${FRAMEWORK_NAME}.framework" \
  -output "$XCFRAMEWORK_PATH"

echo "✓ Created $XCFRAMEWORK_PATH"

# ── Step 4: Sign ──────────────────────────────────────────────
SIGN_IDENTITY="Developer ID Application: My Company (ABCDE12345)"
codesign --timestamp -s "$SIGN_IDENTITY" "$XCFRAMEWORK_PATH"
echo "✓ Signed $XCFRAMEWORK_PATH"

# ── Step 5: Zip for SPM distribution ─────────────────────────
ZIP_PATH="$OUTPUT_DIR/${FRAMEWORK_NAME}-2.1.0.xcframework.zip"
pushd "$OUTPUT_DIR" > /dev/null
zip -r "../${ZIP_PATH}" "${FRAMEWORK_NAME}.xcframework"
popd > /dev/null

# ── Step 6: Compute checksum for Package.swift ───────────────
CHECKSUM=$(swift package compute-checksum "$ZIP_PATH")
echo "✓ Checksum: $CHECKSUM"
echo ""
echo "Add to Package.swift:"
echo ".binaryTarget("
echo "    name: \"$FRAMEWORK_NAME\","
echo "    url: \"https://cdn.example.com/${FRAMEWORK_NAME}-2.1.0.xcframework.zip\","
echo "    checksum: \"$CHECKSUM\""
echo ")"
```

```swift
// ── Package.swift with binary target + wrapper target ─────────
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AnalyticsPackage",
    platforms: [.iOS(.v16)],
    products: [
        // Expose a Swift wrapper (not the binary directly) so
        // consumers import a stable public API we control:
        .library(name: "Analytics", targets: ["Analytics"])
    ],
    targets: [
        // The binary xcframework:
        .binaryTarget(
            name: "AnalyticsCore",
            url: "https://cdn.example.com/AnalyticsCore-3.0.0.xcframework.zip",
            checksum: "a3f8e9..."
        ),
        // A thin Swift wrapper providing a stable public API:
        .target(
            name: "Analytics",
            dependencies: ["AnalyticsCore"],   // depends on binary
            path: "Sources/Analytics"
        )
    ]
)

// ── Wrapper source (Sources/Analytics/Analytics.swift) ────────
import AnalyticsCore

// Re-export only the stable parts of the binary SDK
public struct Analytics {
    public static func track(_ event: String, properties: [String: Any] = [:]) {
        AnalyticsCore.AnalyticsSDK.track(event: event, properties: properties)
    }

    public static func identify(userID: String) {
        AnalyticsCore.AnalyticsSDK.setUserID(userID)
    }
}
```

```swift
// ── Consuming an XCFramework directly (CocoaPods/Carthage) ────
// In Podfile:
// pod 'MyFramework', :vendored_frameworks => 'Frameworks/MyFramework.xcframework'

// In Xcode directly:
// Target → General → Frameworks, Libraries, and Embedded Content
// → + → Add Files → select MyFramework.xcframework
// → Set to "Embed & Sign" for dynamic, "Do Not Embed" for static

// ── Checking which slice Xcode selected ───────────────────────
// Product → Show Build Log → search "MyFramework.xcframework"
// Should show the selected slice directory name
```

## 5. Interview Questions & Answers

### Basic

**Q: What problem does XCFramework solve that a fat (universal) binary cannot?**

A: A fat binary (created with `lipo`) merges multiple architecture slices into a single file. Before Apple Silicon Macs, device = `arm64` and Simulator = `x86_64` — two distinct architectures, distinguishable in a fat binary. Apple Silicon Macs run the iOS Simulator as `arm64`, colliding with the device's `arm64`. A fat binary cannot contain two `arm64` slices without ambiguity. XCFramework solves this by storing slices in separate platform-labelled directories (`ios-arm64/` for device, `ios-arm64_x86_64-simulator/` for Simulator) with an `Info.plist` manifest that tells Xcode which directory to use based on the build target. This also enables including macOS, tvOS, and watchOS variants in a single distributable.

**Q: What is `BUILD_LIBRARY_FOR_DISTRIBUTION` and why is it required for XCFrameworks?**

A: `BUILD_LIBRARY_FOR_DISTRIBUTION = YES` instructs the Swift compiler to generate a `.swiftinterface` file — a stable, text-based module interface — alongside the binary `.swiftmodule`. A `.swiftmodule` is tied to the exact Swift compiler version that produced it; a consumer using a different Swift version cannot import it. A `.swiftinterface` is forward-compatible — future Swift compilers can parse it and reconstruct the module interface. Without it, an XCFramework is unusable as soon as the consumer updates to a new Xcode/Swift version. For any XCFramework you plan to distribute (publicly or internally), always build with `BUILD_LIBRARY_FOR_DISTRIBUTION = YES`.

### Hard

**Q: How do you distribute an XCFramework via Swift Package Manager and what security measure must you implement?**

A: Declare a `.binaryTarget` in `Package.swift` with: `name` (the module name importable in Swift), `url` (HTTPS URL to a `.zip` containing the `.xcframework` at its root), and `checksum` (SHA-256 hash of the `.zip` file, computed with `swift package compute-checksum`). When SPM resolves the package, it downloads the zip, hashes it, and compares against the declared checksum — refusing to proceed if they differ. This prevents supply-chain attacks where the file at the URL is replaced maliciously. Security requirements: (1) Use HTTPS only (SPM rejects HTTP). (2) Host on infrastructure you control — do not depend on third-party CDNs you cannot audit. (3) Tag each release, update the URL and checksum in `Package.swift` for every release. (4) Optionally sign the XCFramework with a Developer ID certificate before zipping, and document the signing identity so consumers can verify.

**Q: What is the difference between embedding an XCFramework as "Embed & Sign" vs "Do Not Embed"?**

A: This choice mirrors the static vs dynamic distinction. If the XCFramework's slice contains a **dynamic framework** (`.dylib`), it must be embedded — set to "Embed & Sign." The framework is copied into `YourApp.app/Frameworks/` and `dyld` loads it at runtime. If the slice is a **static library** (`.a`), the code is linked into the app binary at build time — "Do Not Embed" is correct. Embedding a static XCFramework wastes space (the code is already in the binary) and may cause App Store upload errors. Xcode's "Embed & Sign" also re-signs the binary with the app's distribution certificate, which is required for App Store submission.

### Expert

**Q: How would you set up a CI pipeline to build and distribute an XCFramework for an internal SDK, ensuring reproducible builds and version traceability?**

A: A robust pipeline has five stages: (1) **Version tagging**: every release is tagged in Git (`git tag 2.1.0 && git push origin 2.1.0`). The CI pipeline triggers on tags. (2) **Build**: archive both slices (`xcodebuild archive` for device and Simulator) with `SKIP_INSTALL=NO BUILD_LIBRARY_FOR_DISTRIBUTION=YES`. Create the XCFramework with `xcodebuild -create-xcframework`. (3) **Sign**: code-sign with a stable Developer ID certificate stored in CI's secrets store (Keychain or CI vault). (4) **Distribute**: zip the XCFramework, compute the SHA-256 checksum, upload to a versioned CDN path (`https://cdn.internal/sdk/2.1.0/SDK.xcframework.zip`). Never overwrite an existing release URL — use immutable versioned URLs. (5) **Update Package.swift**: create a PR in the consuming app's repository that bumps the binary target's `url` and `checksum` to the new version. Automating step 5 with a bot (GitHub Actions creating a PR) ensures the consuming team reviews and tests before merging, maintaining version traceability in the app's git history.

## 6. Common Issues & Solutions

**Issue: "Framework 'MyFramework' not found" when running on Simulator after adding XCFramework.**

Solution: The XCFramework does not include a Simulator slice. Verify `Info.plist` lists `ios-arm64_x86_64-simulator`. Rebuild by running both archives and re-creating the XCFramework. Also check `lipo -info` on the Simulator slice — it should list both `arm64` and `x86_64`.

**Issue: Xcode warns "MyFramework.xcframework is not signed" at build time.**

Solution: Sign the XCFramework with `codesign --timestamp -s "Developer ID Application: ..."` before distribution. On App Store builds, Xcode will re-sign embedded binaries with the distribution certificate — the pre-signature is mainly for Notarisation and CI verification.

**Issue: SPM checksum mismatch error when team members resolve the package.**

Solution: The zip file at the URL changed (different contents, different compression) between the time the checksum was computed and when team members resolved. Re-download the zip, recompute the checksum with `swift package compute-checksum`, update `Package.swift`, and commit. Use immutable CDN URLs (include version in path) to prevent this.

**Issue: "Module compiled with Swift X.Y cannot be imported by Swift X.Z" for binary target.**

Solution: The XCFramework was built without `BUILD_LIBRARY_FOR_DISTRIBUTION = YES`, so no `.swiftinterface` was generated. Rebuild with the flag, replace the distribution artifact, and update `Package.swift` with the new checksum.

## 7. Related Topics

- [Static Libraries & Dynamic Frameworks](static-dynamic-frameworks.md) — XCFramework slices are static or dynamic
- [Swift Package Manager](swift-package-manager.md) — `.binaryTarget` in Package.swift
- [CocoaPods & Carthage](cocoapods-carthage.md) — Carthage `--use-xcframeworks`; vendored frameworks in Podspecs
- [Modularization](../06-architecture/modularization.md) — XCFramework as a pre-built module in a modular architecture
