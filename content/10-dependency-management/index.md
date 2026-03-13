# Dependency Management

## Overview

Dependency management is how an iOS project incorporates third-party libraries, internal SDKs, and shared code — and how it controls their versioning. The iOS ecosystem has three package managers: **Swift Package Manager** (SPM, Apple's official tool, deeply integrated into Xcode), **CocoaPods** (the long-dominant community manager, workspace-based), and **Carthage** (a decentralised, build-artifact-focused alternative). Understanding how each works under the hood — not just how to run `pod install` — is essential for diagnosing build failures, managing compile times, and making informed architectural choices.

Equally important is understanding what gets linked into your binary: **static libraries** (copied into the app at link time, no startup cost), **dynamic frameworks** (shared at runtime, loaded on demand, required for App Extensions), and **XCFrameworks** (Apple's multi-architecture binary distribution format for simulators and devices). These choices affect app launch time, binary size, code signing, and the distribution of closed-source SDKs.

## Topics in This Section

- [Swift Package Manager](swift-package-manager.md) — Package.swift manifest, targets and products, local and remote packages, binary targets, resource bundles, version resolution
- [CocoaPods & Carthage](cocoapods-carthage.md) — Podfile/Podspec, pod install vs update, workspace integration, Cartfile, pre-built framework workflow, migration considerations
- [Static Libraries & Dynamic Frameworks](static-dynamic-frameworks.md) — Linker mechanics, startup time impact, symbol visibility, when to use each, module maps
- [XCFrameworks](xcframeworks.md) — Multi-architecture bundles, creating with xcodebuild, SPM binary targets, code signing, distributing closed-source SDKs

## Package Manager Comparison

| Dimension | SPM | CocoaPods | Carthage |
|-----------|-----|-----------|---------|
| Integration | Native Xcode | Workspace (.xcworkspace) | Build phases (drag-drop) |
| Manifest | `Package.swift` | `Podfile` | `Cartfile` |
| Build control | Xcode builds sources | CocoaPods builds frameworks | You build; use pre-built |
| Binary support | Yes (binary targets) | Limited | Yes (pre-built .framework) |
| Centralised registry | No (Git URLs) | Yes (trunk / podspec repo) | No (Git URLs) |
| Apple support | First-party | Third-party | Third-party |
| IDE integration | Deep (autocomplete, preview) | Good (post-install) | Minimal |
| Swift-only friendly | Yes | Yes | Yes |
| Trend | Dominant for new projects | Legacy; large ecosystem | Declining |

## Framework Type Comparison

| Type | Linked at | Loaded at | Startup cost | Copy per target | Extension safe |
|------|-----------|-----------|-------------|-----------------|---------------|
| Static library (`.a`) | Compile/link time | — | Zero | Yes (per app binary) | Yes |
| Dynamic framework (`.framework`) | Runtime | App launch | Per-framework | Shared (once) | Yes (required) |
| XCFramework (`.xcframework`) | Depends on contents | Depends | Depends | Depends | Depends |

## Decision Guide

```
New project or adding a new dependency?
  └─ Use SPM first — native Xcode integration, no extra tooling

Must support an existing CocoaPods-only library?
  └─ CocoaPods or wait for SPM port

Distributing a closed-source SDK to external developers?
  └─ XCFramework (arm64 device + arm64 Simulator + x86_64 Simulator)

Library used only within the app binary (no extensions)?
  └─ Static library preferred — zero startup cost

Library needed by app + extension (or as a plugin loaded at runtime)?
  └─ Dynamic framework required
```

## Relationship to Other Sections

- **Architecture / Modularization**: SPM is the backbone of multi-module app architecture — see [Modularization](../06-architecture/modularization.md).
- **Testing**: SPM test targets and test-only dependencies; mocking frameworks (OHHTTPStubs, Quick/Nimble) — see [Testing](../11-testing/index.md).
- **Concurrency**: Swift Concurrency requires minimum deployment targets that affect dependency compatibility — see [async/await](../03-concurrency/async-await.md).
