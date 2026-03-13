# Static Libraries & Dynamic Frameworks

## 1. Overview

Every dependency added to an iOS app must be linked into the final binary — either statically (at link time, becoming part of the app executable) or dynamically (at runtime, as a separate `.dylib` loaded during app launch). This choice affects startup time, binary size, memory footprint, and compatibility with App Extensions. A **static library** (`.a`) is an archive of compiled object files merged into the app binary at link time — it has zero runtime loading cost. A **dynamic framework** (`.framework` containing a `.dylib`) is a separate executable loaded by the dynamic linker (`dyld`) at app startup — each one adds to the launch time. Understanding linker mechanics is essential for diagnosing slow app launches, duplicate symbol errors, and App Extension compatibility issues.

## 2. Simple Explanation

Imagine you're building a house (app). **Static libraries** are like ordering prefabricated wall panels — they arrive before construction, are cut and merged directly into your walls (the app binary), and once the house is built, there's no trace of where they came from. The house is bigger but self-contained. **Dynamic frameworks** are like ordering appliances that are installed separately — each appliance (`.dylib`) arrives on moving day (app launch) and must be plugged in by an electrician (the dynamic linker). Every appliance adds a few seconds to move-in day; if you have 20 appliances, move-in takes a while.

## 3. Deep iOS Knowledge

### Static Libraries (`.a` / `.o`)

A static library is an archive of compiled object files created by the archiver (`ar`). At link time, the linker copies only the object files actually referenced by the app into the final Mach-O binary.

**Characteristics**:
- Merged into the app binary at link time.
- No runtime loading cost — symbols are resolved at compile time.
- Each app target that uses the library gets its own copy of the code.
- Cannot be shared between app and App Extension (both get their own copy — this is fine for App Extensions).
- Resources (images, nibs) are NOT included — must be in a separate resource bundle.
- Swift static libraries generate a `.swiftmodule` for the module interface.

**Creating a static library**:
```bash
# Compile to object files:
swiftc -c Sources/*.swift -module-name NetworkKit -emit-module -O
# Archive:
ar rcs libNetworkKit.a *.o
# Or with Xcode: set "Mach-O Type" to "Static Library"
```

### Dynamic Frameworks (`.framework`)

A dynamic framework is a directory bundle containing:
```
NetworkKit.framework/
├── NetworkKit            ← the dylib (Mach-O dynamic library)
├── Headers/              ← public headers (ObjC/C)
├── Modules/
│   ├── module.modulemap
│   └── NetworkKit.swiftmodule/
└── Info.plist
```

The dylib is linked at runtime by `dyld`. The linker records a load command in the app binary listing the framework's install name (`@rpath/NetworkKit.framework/NetworkKit`). At launch, `dyld` searches the runpath (`@rpath`) for the framework.

**Characteristics**:
- Separate binary on disk; loaded at launch by `dyld`.
- Every dynamic framework adds ~1–5ms to app startup (measured by `DYLD_PRINT_STATISTICS`).
- Code is NOT duplicated between app and extension — shared at the OS level within the same app bundle.
- **Required for App Extensions**: extensions cannot statically link the same code as the app — they are separate processes.
- Resources bundled inside the `.framework`.
- `@rpath` must include `@executable_path/Frameworks` for app-embedded frameworks.

### Startup Time Impact

`dyld` measures pre-`main()` launch time. Each dynamic framework adds:
- **Parsing Mach-O headers**: ~0.1ms per framework.
- **Symbol binding**: resolving all symbols in the framework — scales with symbol count.
- **Initialiser execution**: `+load` methods, C++ static initialisers.

**Apple's recommendation**: fewer than 6 dynamic frameworks for a fast launch. More than 12 measurably slows launches on older devices.

**Measuring**: enable `DYLD_PRINT_STATISTICS=1` in the scheme's environment variables, or use Xcode's App Launch instrument.

### Module Maps

A module map (`module.modulemap`) defines how C/Objective-C headers map to a Swift module:

```
module NetworkKit {
    header "NetworkKit.h"
    export *
}
```

Swift uses the module map to allow `import NetworkKit` from Swift code. SPM generates module maps automatically for C targets. Xcode generates them for framework targets.

### Symbol Visibility

**Static libraries**: all symbols are visible within the linking binary unless marked hidden with `__attribute__((visibility("hidden")))` or the `-fvisibility=hidden` compiler flag. Unexported symbols from a static library can cause duplicate symbol errors if two static libraries both include the same header/implementation.

**Dynamic frameworks**: symbols are exported (visible) or unexported (private). Use the `EXPORTED_SYMBOLS_FILE` build setting to control which symbols are exported. Swift `public` / `open` types are exported; `internal` and `private` are not.

### Common Linker Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `duplicate symbol _XYZ` | Two static libs include the same `.o` file | Ensure header is included only once; use `@_implementationOnly` import |
| `ld: framework not found XYZ` | Framework not in search path or not embedded | Add to "Frameworks, Libraries, and Embedded Content"; check `FRAMEWORK_SEARCH_PATHS` |
| `dyld: Library not loaded` | Embedded dynamic framework missing from `.app/Frameworks/` | Set "Embed & Sign" not "Do Not Embed" |
| `ld: can't open output file` | Disk space or permissions | Check disk space; clean DerivedData |

### BUILD_LIBRARY_FOR_DISTRIBUTION

Enabling `BUILD_LIBRARY_FOR_DISTRIBUTION = YES` generates a `.swiftinterface` file alongside the `.swiftmodule`. A `.swiftinterface` is a stable, text-based interface that allows the framework to be imported by any Swift version, not just the one that compiled it. Required for: distributing binary frameworks, XCFrameworks, and SPM binary targets.

### App Extension Safe APIs

App Extensions run in a separate process and cannot use certain APIs (`UIApplication.shared`, `+load` with UIKit, etc.). Set `APPLICATION_EXTENSION_API_ONLY = YES` on frameworks used by extensions — the compiler verifies that no extension-unsafe APIs are called.

## 4. Practical Usage

```swift
// ── Checking linkage in Xcode build settings ──────────────────
// Target → Build Settings → Linking → Mach-O Type:
// "Static Library"    → .a
// "Dynamic Library"   → .dylib (inside .framework)
// "Relocatable Object File" → .o (rarely used directly)

// ── SPM: explicit static vs dynamic ──────────────────────────
// In Package.swift:
products: [
    .library(name: "NetworkKit", type: .static, targets: ["NetworkKit"]),
    // or:
    .library(name: "NetworkKit", type: .dynamic, targets: ["NetworkKit"]),
    // or (let consumer decide — Xcode chooses static by default):
    .library(name: "NetworkKit", targets: ["NetworkKit"])
]

// ── Measuring dyld startup time ───────────────────────────────
// In Xcode Scheme → Run → Arguments → Environment Variables:
// DYLD_PRINT_STATISTICS = 1
// Output in console:
// Total pre-main time: 312.23 milliseconds (100.0%)
//   dylib loading time: 176.54 milliseconds (56.5%)
//   rebase/binding time:  18.22 milliseconds (5.8%)
//   ObjC setup time:      22.31 milliseconds (7.1%)
//   initializer time:     95.16 milliseconds (30.4%)

// ── Duplicate symbol resolution ───────────────────────────────
// If two static libraries both link the same C library:
// Use @_implementationOnly for imports that should not re-export:

// In NetworkKit's internals:
@_implementationOnly import zlib   // zlib symbols NOT re-exported to consumers

// ── Checking if a framework is static or dynamic ──────────────
// In Terminal:
// file path/to/Framework.framework/Framework
// → "Mach-O universal binary" → dynamic (for multiple archs)
// → "current ar archive" → static
// Or check LOAD_COMMANDS:
// otool -L path/to/Framework.framework/Framework
// Dynamic shows @rpath entries; static shows nothing (linked at compile time)

// ── App Extension API safety ──────────────────────────────────
// In framework target Build Settings:
// APPLICATION_EXTENSION_API_ONLY = YES
// Then this will fail to compile in the framework:
// UIApplication.shared.openURL(...)  → compile error: not available in extensions
```

```bash
# ── Create a universal static library (arm64 + x86_64) ────────
xcodebuild archive \
  -scheme NetworkKit \
  -destination "generic/platform=iOS" \
  -archivePath build/NetworkKit-iOS.xcarchive \
  SKIP_INSTALL=NO BUILD_LIBRARY_FOR_DISTRIBUTION=YES

xcodebuild archive \
  -scheme NetworkKit \
  -destination "generic/platform=iOS Simulator" \
  -archivePath build/NetworkKit-Sim.xcarchive \
  SKIP_INSTALL=NO BUILD_LIBRARY_FOR_DISTRIBUTION=YES

# Combine into XCFramework (see xcframeworks.md for full steps)
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the main difference between a static library and a dynamic framework in terms of app startup time?**

A: A static library's code is merged into the app binary at link time — `dyld` sees it as part of the main executable and pays no per-framework loading cost at startup. A dynamic framework is a separate `.dylib` loaded by `dyld` at app launch. Every dynamic framework adds approximately 1–5ms of pre-`main()` time for loading, parsing, symbol binding, and running initialisers. An app with 20 dynamic frameworks can add 50–100ms+ to its launch time on older devices — a perceptible delay. Apple recommends fewer than 6 dynamic frameworks for responsive launches. Static linking is preferred for performance; dynamic linking is required when the same binary must be shared between the app and an App Extension.

**Q: Why do App Extensions require dynamic frameworks for shared code?**

A: An App Extension (widget, share extension, keyboard, etc.) runs as a separate process from the host app. A static library's code is physically compiled into a single executable — you cannot have two separate processes (app and extension) share the same static copy. Each would need its own copy, which is fine for most code, but for a large framework this doubles binary size. More importantly, some code needs to be shared with a live object (e.g., a shared data store using Core Data). Dynamic frameworks solve this: both the app and the extension embed the same `.framework` in the `.app` bundle, and the OS loads one shared copy of the code into both processes (sharing the text segment via virtual memory mapping). The extension links against the app's embedded framework using `@executable_path/../Frameworks`.

### Hard

**Q: What causes "duplicate symbol" linker errors and how do you resolve them?**

A: A duplicate symbol error occurs when the linker finds two object files (from different translation units or static libraries) that define the same symbol. Common causes: (1) A header defines a function or variable without `static` or `inline` — including it in multiple `.m` files creates one definition per `.m`, and the archiver includes all of them. (2) Two static libraries both embed the same third-party static library (e.g., both embed OpenSSL). (3) A class category or extension is defined in both the app target and a pod. Resolutions: (1) Mark inline/helper functions as `static` or move them to a `.c/.m` file with a header declaration only. (2) Use `@_implementationOnly import` in Swift to avoid re-exporting symbols from implementation dependencies. (3) Ensure each static dependency is included only once in the link graph — use `OTHER_LDFLAGS = -ObjC` carefully and only where needed. (4) Use dynamic frameworks for shared code when two separate targets must both use it.

**Q: What is `BUILD_LIBRARY_FOR_DISTRIBUTION` and what does it generate?**

A: `BUILD_LIBRARY_FOR_DISTRIBUTION = YES` instructs the Swift compiler to generate a `.swiftinterface` file alongside the `.swiftmodule`. A `.swiftmodule` is a binary format tied to the exact Swift compiler version — a framework built with Swift 5.9 cannot be imported by a project using Swift 6.0. A `.swiftinterface` is a text-based, versioned module interface that the Swift compiler can use to reconstruct the module regardless of the compiler version that produced it. This is required for: distributing pre-built frameworks across Swift releases, XCFrameworks shipped in SPM binary targets, and any framework that must remain compatible as teams upgrade Xcode. Without it, binary framework consumers must recompile from source on every Swift version bump.

### Expert

**Q: Describe the exact `dyld` load process for a dynamic framework and what you can do to minimise its impact on app launch.**

A: When the OS launches your app, `dyld` processes all `LC_LOAD_DYLIB` load commands in the app's Mach-O binary: (1) **Find**: locate each `.dylib` by searching `@rpath` (typically `@executable_path/Frameworks`). (2) **Map**: memory-map the dylib's TEXT and DATA segments using `mmap`. (3) **Rebase**: if the dylib was not loaded at its preferred address (ASLR), adjust all internal pointers (rebasing). (4) **Bind**: resolve all external symbol references — find each imported function/class in the providing framework and write its address into the DATA segment. (5) **Initialise**: run `+load` methods and C++ static initialisers. Steps 3–5 scale with symbol count. Minimisation strategies: (1) Reduce the number of dynamic frameworks — merge small frameworks into one or convert to static. (2) Move initialisation work out of `+load` into `+initialize` or lazy loading. (3) Use `__attribute__((constructor))` only when necessary. (4) Enable `DEAD_CODE_STRIPPING = YES` to eliminate unused code, reducing the symbol table size. (5) Use the App Launch instrument to identify which framework's initialiser is consuming the most time.

## 6. Common Issues & Solutions

**Issue: `dyld: Library not loaded: @rpath/NetworkKit.framework/NetworkKit` at runtime.**

Solution: The dynamic framework is not embedded in the app bundle. Select the app target → General → Frameworks, Libraries, and Embedded Content → set the framework to "Embed & Sign" (not "Do Not Embed"). The framework must be physically present at `YourApp.app/Frameworks/NetworkKit.framework` at runtime.

**Issue: Static library works in the app but causes a linker error in the App Extension target.**

Solution: The static library uses `APPLICATION_EXTENSION_API_ONLY = NO` (default) but calls extension-unsafe APIs. Set `APPLICATION_EXTENSION_API_ONLY = YES` on the library target and fix any API violations, or use conditional compilation (`#if canImport(UIKit) && !EXTENSION_BUILD`).

**Issue: Xcode reports "missing required module 'XYZ'" for a static library.**

Solution: The static library's `.swiftmodule` files are not in the `SWIFT_INCLUDE_PATHS`. Add the path to the `.swiftmodule` directory in the consuming target's Swift Include Paths. For SPM, this is handled automatically.

## 7. Related Topics

- [Swift Package Manager](swift-package-manager.md) — `.library(type: .static/.dynamic)` in Package.swift
- [CocoaPods & Carthage](cocoapods-carthage.md) — `use_frameworks!` controls static vs dynamic linkage
- [XCFrameworks](xcframeworks.md) — wraps static or dynamic slices for multi-platform distribution
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — startup time directly affected by dynamic framework count
