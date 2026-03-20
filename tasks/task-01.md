# Task 01: Index Category Structure + Missing Items Audit

## Overview

Two-part task to bring the knowledge tree into alignment with `Senior-iOS-Knowledge-Tree.md`:

- **Part 1** — Update each section's `index.md` to include a `## Subtopic Groups` section using the exact category names from the knowledge tree.
- **Part 2** — Identify and create missing topic files per section.

Source of truth: `Senior-iOS-Knowledge-Tree.md`
Files to update: `content/*/index.md` (20 files)

---

## Part 1 — Index Category Structure Updates

Each `index.md` must contain a `## Subtopic Groups` section listing the exact category names from the knowledge tree, with links to the relevant topic files grouped under each category.

| Section | Categories |
|---------|-----------|
| 01 Swift Language | Core Concepts · Generics & Protocols · Advanced Swift |
| 02 Memory Management | ARC · Closures · Memory Performance |
| 03 Concurrency | Legacy Concurrency · Modern Swift Concurrency · Concurrency Problems |
| 04 UI Frameworks | UIKit · SwiftUI · UI Architecture |
| 05 Reactive Programming | Combine · Concepts |
| 06 Architecture | Common Architectures · Design Principles · Dependency Injection · Modularization |
| 07 Networking | HTTP Basics · iOS Networking · Advanced Networking |
| 08 Data Persistence | Local Storage · Databases · Data Synchronization |
| 09 iOS Platform | App Lifecycle · System Capabilities · Platform Frameworks |
| 10 Dependency Management | Package Managers · Framework Types |
| 11 Testing & Quality | Testing Types · Testable Architecture · Tools |
| 12 Performance | Profiling Tools · Optimization Techniques |
| 13 App Startup & Runtime | App Launch Process · Startup Optimization · Runtime Behavior |
| 14 Security | Data Security · Network Security · App Security |
| 15 Design Patterns | Creational · Structural · Behavioral · iOS Patterns |
| 16 Refactoring | Code Smells · Refactoring Techniques |
| 17 Observability | Crash Reporting · Logging · Monitoring |
| 18 Accessibility | Core Accessibility · UI Support · Tools |
| 19 App Distribution | Code Signing · Entitlements · Distribution · Automation |
| 20 Mobile System Design | Architecture · Data Strategies · Large Scale Apps |

### Section-by-section category details

#### 01 Swift Language
- **Core Concepts**: value-types-reference-types, optionals, error-handling, closures-functions, type-system, swift-evolution
- **Generics & Protocols**: generics, protocols, protocol-oriented-programming, associated-types, existential-types
- **Advanced Swift**: property-wrappers, result-builders, result-type, keypath, dynamic-member-lookup, reflection-mirror

#### 02 Memory Management
- **ARC**: arc-basics, strong-weak-unowned, retain-cycles, memory-leaks
- **Closures**: capture-lists
- **Memory Performance**: instruments-memory, copy-on-write-optimization, memory-allocation-patterns

#### 03 Concurrency
- **Legacy Concurrency**: grand-central-dispatch, operation-queue, thread-safety
- **Modern Swift Concurrency**: async-await, structured-concurrency, actors, sendable, task-groups
- **Concurrency Problems**: data-races, deadlocks, priority-inversion

#### 04 UI Frameworks
- **UIKit**: uiviewcontroller-lifecycle, auto-layout, uicollectionview, custom-transitions, rendering-pipeline
- **SwiftUI**: swiftui-state-management, swiftui-layout, swiftui-performance, swiftui-interoperability
- **UI Architecture**: mvvm-swiftui, coordinator-pattern, view-composition

#### 05 Reactive Programming
- **Combine**: combine-basics, publishers-subscribers, combine-operators, combine-networking, combine-error-handling, combine-schedulers
- **Concepts**: reactive-streams, data-pipelines, data-binding

#### 06 Architecture
- **Common Architectures**: mvc, mvvm, viper, tca
- **Design Principles**: solid-principles, dry-yagni, separation-of-concerns, composition-over-inheritance
- **Dependency Injection**: dependency-injection, service-locator, di-containers
- **Modularization**: modular-architecture, swift-packages, layered-architecture

#### 07 Networking
- **HTTP Basics**: http-basics, rest-apis, graphql
- **iOS Networking**: urlsession, authentication, network-security
- **Advanced Networking**: websockets, background-networking, network-monitoring

#### 08 Data Persistence
- **Local Storage**: userdefaults, keychain, file-system
- **Databases**: core-data, swiftdata, sqlite, realm
- **Data Synchronization**: cloudkit, icloud-documents, data-migration

#### 09 iOS Platform
- **App Lifecycle**: app-lifecycle, background-modes, scene-management
- **System Capabilities**: push-notifications, app-extensions, siri-shortcuts
- **Platform Frameworks**: core-location, core-motion, avfoundation, healthkit, mapkit

#### 10 Dependency Management
- **Package Managers**: swift-package-manager, cocoapods, carthage
- **Framework Types**: static-vs-dynamic-frameworks

#### 11 Testing & Quality
- **Testing Types**: unit-testing, integration-testing, ui-testing, snapshot-testing, tdd
- **Testable Architecture**: dependency-injection-testing, mocking, test-doubles
- **Tools**: xctest, quick-nimble

#### 12 Performance
- **Profiling Tools**: instruments-time-profiler, instruments-allocations, energy-log
- **Optimization Techniques**: rendering-performance, launch-time-optimization, memory-optimization, battery-optimization

#### 13 App Startup & Runtime
- **App Launch Process**: app-launch-types, dyld-loading, static-initializers
- **Startup Optimization**: pre-main-optimization, post-main-optimization, launch-metrics
- **Runtime Behavior**: objc-runtime, method-swizzling, dynamic-dispatch

#### 14 Security
- **Data Security**: keychain-security, data-encryption, secure-storage
- **Network Security**: ssl-pinning, certificate-transparency, ats
- **App Security**: jailbreak-detection, code-obfuscation, secure-coding

#### 15 Design Patterns
- **Creational**: singleton, factory, builder, prototype
- **Structural**: adapter, decorator, facade, composite, proxy
- **Behavioral**: observer, strategy, command, template-method, iterator
- **iOS Patterns**: delegate, target-action, responder-chain, kvo

#### 16 Refactoring
- **Code Smells**: massive-view-controller, god-object, primitive-obsession, feature-envy
- **Refactoring Techniques**: extract-method, extract-class, replace-conditional-with-polymorphism, introduce-protocol

#### 17 Observability
- **Crash Reporting**: crash-reporting-tools, symbolication, crash-analysis
- **Logging**: structured-logging, oslog, remote-logging
- **Monitoring**: apm-tools, custom-metrics, alerting

#### 18 Accessibility
- **Core Accessibility**: voiceover, accessibility-api, semantic-labels
- **UI Support**: dynamic-type, color-contrast, focus-management
- **Tools**: accessibility-inspector, automated-accessibility-testing

#### 19 App Distribution
- **Code Signing**: certificates-profiles, entitlements, signing-workflow
- **Entitlements**: capabilities, app-groups, icloud-entitlements
- **Distribution**: app-store-connect, testflight, enterprise-distribution
- **Automation**: fastlane, ci-cd-distribution, automated-screenshots

#### 20 Mobile System Design
- **Architecture**: offline-first, sync-architecture, client-server-sync, api-driven-ui, feature-flags, remote-config
- **Data Strategies**: caching-strategies, data-modeling, pagination
- **Large Scale Apps**: modular-system-design, scalable-networking, performance-at-scale

---

## Part 2 — Missing Topic Files

Files that exist in `Senior-iOS-Knowledge-Tree.md` but are absent from the `content/` directory.

### Section 01 – Swift Language
| Category | Missing file |
|----------|-------------|
| Generics & Protocols | `associated-types.md` |
| Generics & Protocols | `existential-types.md` |
| Advanced Swift | `result-type.md` |
| Advanced Swift | `keypath.md` |
| Advanced Swift | `dynamic-member-lookup.md` |
| Advanced Swift | `reflection-mirror.md` |

### Section 02 – Memory Management
| Category | Missing file |
|----------|-------------|
| Memory Performance | `copy-on-write-optimization.md` |
| Memory Performance | `memory-allocation-patterns.md` |

### Section 03 – Concurrency
All knowledge-tree items covered by existing files. ✓

### Section 04 – UI Frameworks
| Category | Missing file |
|----------|-------------|
| UIKit | `rendering-pipeline.md` |

### Section 05 – Reactive Programming
| Category | Missing file |
|----------|-------------|
| Concepts | `reactive-streams.md` |
| Concepts | `data-pipelines.md` |
| Concepts | `data-binding.md` |

### Section 06 – Architecture
| Category | Missing file |
|----------|-------------|
| Design Principles | `separation-of-concerns.md` |
| Design Principles | `composition-over-inheritance.md` |
| Dependency Injection | `service-locator.md` |
| Dependency Injection | `di-containers.md` |
| Modularization | `layered-architecture.md` |

### Section 07 – Networking
All knowledge-tree items covered. ✓

### Section 08 – Data Persistence
| Category | Missing file |
|----------|-------------|
| Data Synchronization | `data-migration.md` |

### Section 09 – iOS Platform
| Category | Missing file |
|----------|-------------|
| Platform Frameworks | `mapkit.md` |

### Section 10 – Dependency Management
All knowledge-tree items covered. ✓

### Section 11 – Testing & Quality
| Category | Missing file |
|----------|-------------|
| Tools | `xctest.md` |
| Tools | `quick-nimble.md` |
| Testable Architecture | `mocking.md` |
| Testable Architecture | `test-doubles.md` |

### Section 12 – Performance
| Category | Missing file |
|----------|-------------|
| Profiling Tools | `energy-log.md` |

### Section 13 – App Startup & Runtime
All knowledge-tree items covered. ✓

### Section 14 – Security
All knowledge-tree items covered. ✓

### Section 15 – Design Patterns
All knowledge-tree items covered. ✓

### Section 16 – Refactoring
All knowledge-tree items covered. ✓

### Section 17 – Observability
All knowledge-tree items covered. ✓

### Section 18 – Accessibility
All knowledge-tree items covered. ✓

### Section 19 – App Distribution
All knowledge-tree items covered. ✓

### Section 20 – Mobile System Design
| Category | Missing file |
|----------|-------------|
| Architecture | `api-driven-ui.md` |
| Architecture | `feature-flags.md` |
| Architecture | `remote-config.md` |

---

## Summary of Missing Files

Total missing files: **24**

| Section | Count |
|---------|-------|
| 01 Swift Language | 6 |
| 02 Memory Management | 2 |
| 04 UI Frameworks | 1 |
| 05 Reactive Programming | 3 |
| 06 Architecture | 5 |
| 08 Data Persistence | 1 |
| 09 iOS Platform | 1 |
| 11 Testing & Quality | 4 |
| 12 Performance | 1 |
| 20 Mobile System Design | 3 |
| **Total** | **27** |

> Note: Sections 03, 07, 10, 13, 14, 15, 16, 17, 18, 19 require no new topic files.

---

## Completion Checklist

- [ ] Part 1: All 20 `index.md` files updated with `## Subtopic Groups` section
- [ ] Part 2: All 27 missing topic files created with appropriate content
- [ ] All category names match exactly with `Senior-iOS-Knowledge-Tree.md`
- [ ] All new topic files follow existing file conventions (frontmatter, headings, etc.)
