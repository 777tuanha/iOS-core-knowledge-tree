# CocoaPods & Carthage

## 1. Overview

CocoaPods and Carthage are the two major third-party dependency managers that predate Swift Package Manager. **CocoaPods** is a centralised, workspace-based manager — the dominant tool for the past decade, with thousands of published libraries (Podspecs). It modifies the Xcode project, creates a workspace, builds all dependencies as frameworks at compile time, and handles transitive dependencies automatically. **Carthage** takes a decentralised, minimal-integration approach: it builds pre-compiled frameworks from GitHub repositories and requires you to manually add them to build phases. Carthage never modifies your `.xcodeproj`. Both are in maintenance mode for most new projects, with SPM now covering most use cases, but understanding them is essential for maintaining existing codebases.

## 2. Simple Explanation

**CocoaPods** is a full-service moving company: you give it a list of what you need (Podfile), it fetches everything, assembles the furniture (builds frameworks), and even sets up the rooms for you (modifies your Xcode workspace). You just open the `.xcworkspace` it creates. **Carthage** is a parts supplier: you tell it what kits to order (Cartfile), it builds the kits for you, and hands you the boxes (`.framework` files). You then put the boxes on the shelves yourself (drag them into Xcode). Less hand-holding, more control.

## 3. Deep iOS Knowledge

### CocoaPods — Architecture

CocoaPods manages dependencies through three artefacts:

| File | Purpose | Commit? |
|------|---------|---------|
| `Podfile` | Declares dependencies and configuration | Yes |
| `Podfile.lock` | Pins exact resolved versions | Yes (apps); No (libraries) |
| `Pods/` directory | Downloaded sources and build products | No — add to `.gitignore` |
| `.xcworkspace` | Generated workspace containing app + Pods project | No (auto-generated) |

### Podfile Structure

```ruby
platform :ios, '16.0'
use_frameworks!          # link as dynamic frameworks; omit for static

workspace 'MyApp'

target 'MyApp' do
  # Dependencies
  pod 'Alamofire',    '~> 5.8'         # up to next major
  pod 'GRDB.swift',   '~> 6.0'
  pod 'Kingfisher',   '>= 7.0', '< 8'  # explicit range
  pod 'CryptoSwift',  :git => 'https://github.com/krzyzanowskim/CryptoSwift.git',
                      :tag => '1.8.0'  # pin to tag

  target 'MyAppTests' do
    inherit! :search_paths              # inherit app pods without re-linking
    pod 'OHHTTPStubs/Swift', '~> 9.0'
  end
end

# Post-install hook — modify build settings after generation
post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '16.0'
      config.build_settings['SWIFT_VERSION'] = '5.0'
    end
  end
end
```

### pod install vs pod update

| Command | Effect |
|---------|--------|
| `pod install` | Installs versions recorded in `Podfile.lock`; resolves new/changed entries only |
| `pod update [PodName]` | Fetches the latest version satisfying constraints; updates `Podfile.lock` |
| `pod update` | Updates ALL pods to latest — use cautiously |

**Rule**: always run `pod install` on CI and fresh clones. Run `pod update <PodName>` when intentionally upgrading a specific library.

### use_frameworks! and Static Pods

`use_frameworks!` (dynamic linking) was required before Xcode 9 for Swift pods. Modern CocoaPods supports static frameworks:

```ruby
use_frameworks! :linkage => :static   # static linking (faster startup, larger binary)
# or per-pod:
pod 'SomeLibrary', :linkage => :dynamic
```

**Static pods** do not require embedding in the app bundle and have zero runtime startup cost — preferred when not targeting App Extensions.

### Podspec

A `.podspec` file describes a publishable library. Required for open-source pods and for distributing private pods via a private Specs repo or `:path =>`:

```ruby
Pod::Spec.new do |s|
  s.name         = 'NetworkKit'
  s.version      = '1.2.0'
  s.summary      = 'Thin URLSession wrapper'
  s.homepage     = 'https://github.com/company/NetworkKit'
  s.license      = { :type => 'MIT' }
  s.author       = 'Company'
  s.platform     = :ios, '16.0'
  s.source       = { :git => 'https://github.com/company/NetworkKit.git', :tag => s.version }
  s.source_files = 'Sources/**/*.swift'
  s.swift_version = '5.9'
  s.dependency 'Alamofire', '~> 5.8'
end
```

### Carthage — Architecture

Carthage resolves and builds dependencies but leaves Xcode project integration manual.

**Cartfile**:
```
github "Alamofire/Alamofire" ~> 5.8
github "groue/GRDB.swift" ~> 6.0
git "https://github.com/company/PrivateLib.git" "1.0.0"
```

**Cartfile.resolved**: lock file — commit for apps.

**Workflow**:
```bash
# Build all dependencies for iOS (arm64 + x86_64 Simulator):
carthage update --platform iOS --use-xcframeworks

# Bootstrap from lock file (equivalent to pod install):
carthage bootstrap --platform iOS --use-xcframeworks
```

Output: `Carthage/Build/iOS/*.xcframework` (with `--use-xcframeworks`).

Manual integration: add each `.xcframework` to the app target's "Frameworks, Libraries, and Embedded Content" in Xcode. For dynamic frameworks, add a "Copy Files" build phase or use `--use-xcframeworks` (recommended — handles simulator slices automatically).

### Carthage vs CocoaPods vs SPM

| Concern | CocoaPods | Carthage | SPM |
|---------|-----------|---------|-----|
| Modifies Xcode project | Yes | No | Yes (adds package ref) |
| Build speed | Slow (builds from source each clean) | Faster (pre-built) | Fast (Xcode caches) |
| Transitive deps | Automatic | Automatic | Automatic |
| Private repos | Specs repo or :path | Git URL | Git URL |
| App Extensions | With `use_frameworks!` | Yes | Yes |
| Active development | Maintenance mode | Declining | Active (Apple) |

### Migrating from CocoaPods/Carthage to SPM

1. Check if the library has an SPM-compatible `Package.swift` (most modern libraries do).
2. Remove the pod from `Podfile`; run `pod install` to deintegrate.
3. In Xcode, File → Add Package Dependencies → paste the library's Git URL.
4. Fix any import path differences (module names occasionally differ).
5. Update `Bundle.module` vs `Bundle(for:)` resource access patterns.

## 4. Practical Usage

```ruby
# ── Production Podfile example ────────────────────────────────
platform :ios, '16.0'
use_frameworks! :linkage => :static   # static = faster launch

inhibit_all_warnings!   # suppress warnings from pod source

target 'MyApp' do
  # Networking
  pod 'Alamofire',   '~> 5.8'
  pod 'Kingfisher',  '~> 7.0'   # image loading

  # Analytics (binary-only; use vendored framework)
  pod 'Firebase/Analytics', '~> 10.0'
  pod 'Firebase/Crashlytics'

  # Development-only
  pod 'Reveal-SDK', :configurations => ['Debug']

  target 'MyAppTests' do
    inherit! :search_paths
    pod 'OHHTTPStubs/Swift', '~> 9.0'
    pod 'Quick',   '~> 7.0'
    pod 'Nimble',  '~> 12.0'
  end

  target 'MyAppUITests' do
    # UI test targets usually need no additional pods
  end
end

post_install do |installer|
  # Ensure all pods target the same iOS version to prevent linker warnings
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = '16.0'
    end
  end

  # Enable module stability for XCFramework distribution
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['BUILD_LIBRARY_FOR_DISTRIBUTION'] = 'YES'
    end
  end
end
```

```bash
# ── CocoaPods CI workflow ─────────────────────────────────────
# Install exact versions from Podfile.lock (never pod update on CI):
bundle exec pod install --deployment --clean-install

# Lint a podspec before publishing:
pod spec lint NetworkKit.podspec --allow-warnings

# Publish to CocoaPods trunk:
pod trunk push NetworkKit.podspec

# ── Carthage workflow ─────────────────────────────────────────
# First run / update dependencies:
carthage update --platform iOS --use-xcframeworks

# Subsequent runs (from Cartfile.resolved — fast):
carthage bootstrap --platform iOS --use-xcframeworks

# Build a single dependency:
carthage update Alamofire --platform iOS --use-xcframeworks

# Diagnose build failure:
carthage update --platform iOS --use-xcframeworks --verbose
```

```swift
// ── Accessing a CocoaPods resource bundle ─────────────────────
// When a pod has resources, CocoaPods creates a separate bundle
// named <PodName>.bundle alongside the framework:
let podBundle = Bundle(for: SomePodClass.self)
    .url(forResource: "SomePod", withExtension: "bundle")
    .flatMap { Bundle(url: $0) }
let image = UIImage(named: "icon", in: podBundle, compatibleWith: nil)
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `pod install` and `pod update`?**

A: `pod install` reads `Podfile.lock` and installs the exact versions recorded there. For pods not yet in the lock file (newly added entries), it resolves the latest version satisfying the Podfile constraint and records it. `pod update [PodName]` ignores `Podfile.lock` for the specified pod (or all pods if no name is given) and fetches the latest version satisfying the Podfile constraint, then updates `Podfile.lock`. Use `pod install` on CI and on fresh clones to get reproducible builds. Use `pod update` when you intentionally want to upgrade a library. Never run bare `pod update` without a pod name on CI — it upgrades all dependencies, breaking reproducibility.

**Q: What does `use_frameworks!` do in a Podfile and when should you avoid it?**

A: `use_frameworks!` tells CocoaPods to build each pod as a dynamic framework (`.framework` containing a dylib) rather than a static library. This was historically required for Swift pods because the Swift standard library was not statically linked before Xcode 7. Today, `use_frameworks!` with dynamic linking adds startup time (each framework is loaded at launch) and requires all frameworks to be embedded in the app bundle, increasing size. Modern best practice is `use_frameworks! :linkage => :static` — pods are compiled as static libraries wrapped in framework format, retaining the module system without the startup cost. Avoid bare `use_frameworks!` (dynamic) unless a specific pod requires dynamic linking (e.g., some Firebase SDKs, pods using `+load` for registration patterns).

### Hard

**Q: How does CocoaPods handle transitive dependencies and what happens when two pods require conflicting versions of the same dependency?**

A: CocoaPods uses a dependency resolver (Molinillo) that finds a set of versions satisfying all constraints simultaneously. When pod A requires `Lib ~> 1.0` and pod B requires `Lib ~> 2.0`, the resolver cannot find a version satisfying both and reports a conflict error. Resolution options: (1) Update one of the conflicting pods — newer versions often relax their dependency constraints. (2) Use `:git` with a `:commit` or `:tag` pointing to a fork that widens the constraint. (3) Remove one of the conflicting pods and find an alternative. (4) Use `pod deintegrate` and migrate the conflicting pods to SPM where binary targets or forks are more manageable. Unlike npm, CocoaPods cannot include two versions of the same pod simultaneously — all consumers must agree on a single version.

**Q: Why is Carthage's approach of pre-built frameworks faster for CI than CocoaPods building from source?**

A: CocoaPods rebuilds all pods from source on every clean build (and after `DerivedData` is cleared, which CI often does). For large dependency graphs (10–20 pods), this can add 5–15 minutes to every CI build. Carthage builds frameworks once and caches them in `Carthage/Build/`. CI can cache the `Carthage/Build/` directory between runs — if `Cartfile.resolved` hasn't changed, no rebuild is needed. The tradeoff: Carthage requires manual integration (drag-drop into Xcode), doesn't handle transitive dependencies automatically (each dependency and its dependencies must be built separately), and building `--use-xcframeworks` for multi-architecture targets on every developer machine on first setup can take considerable time.

### Expert

**Q: You have a CocoaPods-based app that you want to migrate to SPM. What is your strategy for a codebase with 30 pods, some of which don't have SPM support?**

A: A phased migration reduces risk: (1) **Audit**: list all 30 pods; check if each has a `Package.swift` (most popular pods added SPM support by 2021–2022). Categorise as: SPM-ready, SPM-in-progress (may need a fork), or SPM-incompatible (likely binary-only pods like Firebase, proprietary SDKs). (2) **Hybrid phase**: add SPM packages for SPM-ready pods while keeping the remaining ones in CocoaPods. Both can coexist in the same Xcode project. (3) **Binary targets**: for SDKs with no source (Firebase provides XCFrameworks), use SPM `.binaryTarget` pointing to their pre-built XCFramework ZIP. (4) **Forks**: for libraries that need minor fixes to support SPM, fork and add `Package.swift`. Submit a PR upstream. (5) **Remaining CocoaPods**: last resort — keep a minimal Podfile for truly incompatible dependencies. (6) **Validate**: run `pod install` from scratch on a clean clone; run all tests; check no duplicate symbols (mixing static and dynamic linking of the same library). (7) **Remove CocoaPods entirely** once all pods are migrated. Commit `Package.resolved` and remove `Pods/`, `Podfile.lock`, `.xcworkspace` (if generated solely by CocoaPods) from the repo.

## 6. Common Issues & Solutions

**Issue: `[!] Unable to find a specification for 'PodName'` after `pod install`.**

Solution: Run `pod repo update` to refresh the local CocoaPods spec repo cache. The pod may have been published after your last cache update. For private pods, ensure the private spec repo is added: `pod repo add MySpecs https://...`.

**Issue: Carthage `Build Failed` with "Module compiled with Swift X cannot be imported by Swift Y."**

Solution: Carthage builds frameworks using the current Xcode's Swift toolchain. If the pre-built framework was built with a different Swift version than your app, the binary is incompatible. Run `carthage update` to rebuild from source with the current Swift version. Enable `BUILD_LIBRARY_FOR_DISTRIBUTION = YES` in the library's Xcode scheme to generate a `.swiftinterface` file — this enables binary compatibility across Swift versions.

**Issue: Duplicate symbols linker error after migrating a pod to SPM.**

Solution: The library is being included twice — once via CocoaPods and once via SPM. Remove it from one source. Also check for CocoaPods subspecs that may pull in the same dependency as an SPM transitive dependency.

**Issue: CocoaPods `post_install` hook is too slow on CI.**

Solution: Cache the entire `Pods/` directory keyed on `Podfile.lock`'s SHA-256. If the hash hasn't changed, skip `pod install` entirely. Use `--clean-install` flag only on cache miss.

## 7. Related Topics

- [Swift Package Manager](swift-package-manager.md) — the preferred modern alternative
- [XCFrameworks](xcframeworks.md) — Carthage `--use-xcframeworks` output; binary pod distribution
- [Static Libraries & Dynamic Frameworks](static-dynamic-frameworks.md) — `use_frameworks!` linkage choice
- [Modularization](../06-architecture/modularization.md) — replacing pods with local SPM packages
