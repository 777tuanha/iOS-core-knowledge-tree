# Snapshot Testing

## 1. Overview

Snapshot testing captures the rendered output of a UI component — as an image, an HTML string, or a text description — and compares it against a stored reference snapshot on subsequent runs. Any visual difference fails the test. The primary Swift library for this is **swift-snapshot-testing** by Point-Free, which supports UIView, UIViewController, SwiftUI views, CALayer, and even arbitrary `Encodable` types (as JSON snapshots). Snapshot tests are fast (no app launch, no network, no database), catch unintended visual regressions that unit tests miss, and document the intended appearance of components. The tradeoff: they require a record/assert workflow, must be regenerated on intentional design changes, and can be flaky if rendering depends on the device screen scale or OS version.

## 2. Simple Explanation

A snapshot test is like a security photo system for your UI. The first time a test runs in "record" mode, it takes a photo of the component (the reference snapshot). Every subsequent run compares the current rendering to that photo pixel-by-pixel. If someone accidentally changes the button colour or shifts a label, the photo doesn't match and the test fails — showing you a diff image of exactly what changed. When a designer intentionally changes the look, you re-run in record mode to update the reference photos.

## 3. Deep iOS Knowledge

### swift-snapshot-testing

**Point-Free's `swift-snapshot-testing`** is the standard library. Add via SPM:
```swift
.package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.15.0")
```

Core API:
```swift
import SnapshotTesting

// Assert snapshot (compare to stored reference)
assertSnapshot(of: view, as: .image)

// Record new reference (first run, or after intentional change)
assertSnapshot(of: view, as: .image, record: true)

// Or set globally in setUp:
isRecording = true
```

### Snapshot Strategies

`swift-snapshot-testing` uses typed strategies (`Snapshotting<Value, Format>`):

| Strategy | What it captures |
|----------|-----------------|
| `.image` | Pixel-accurate PNG of the view |
| `.image(precision: 0.99)` | Allow 1% pixel difference (anti-aliasing tolerance) |
| `.image(size: CGSize)` | Render at specific size |
| `.image(traits:)` | Specific trait collection (dark mode, dynamic type) |
| `.recursiveDescription` | Accessibility tree as text (stable across platforms) |
| `.dump` | Text dump of a value (struct/class) |
| `.json` | JSON representation of Encodable |

### File Storage

Reference snapshots are stored as `__Snapshots__/TestClassName/testMethodName.1.png` relative to the test source file. Commit them to source control — they are part of the test specification.

### Dark Mode and Dynamic Type Variants

Test multiple appearances with different trait collections:

```swift
assertSnapshot(of: vc,
               as: .image(on: .iPhone13Pro),
               named: "light")

assertSnapshot(of: vc,
               as: .image(on: .iPhone13Pro(.portrait),
                          traits: .init(userInterfaceStyle: .dark)),
               named: "dark")

assertSnapshot(of: vc,
               as: .image(on: .iPhone13Pro,
                          traits: .init(preferredContentSizeCategory: .accessibilityExtraLarge)),
               named: "largeText")
```

### SwiftUI Snapshots

SwiftUI views need to be wrapped for snapshotting:

```swift
let view = FeedCardView(post: Post.stub)
    .environment(\.colorScheme, .dark)

assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13Pro)))
```

`layout` options:
- `.fixed(width:height:)` — explicit size
- `.sizeThatFits` — intrinsic size
- `.device(config:)` — simulated device frame

### Inline Snapshots

`swift-snapshot-testing` 1.15+ supports inline snapshots — the snapshot string is written directly into the source file:

```swift
assertInlineSnapshot(of: model, as: .json) {
    """
    {
      "id" : "42",
      "name" : "Alice"
    }
    """
}
```

On first run (or with `isRecording = true`), the framework writes the snapshot string into the source code. This keeps snapshots next to the tests — useful for `Codable` model serialisation tests.

### CI Considerations

- **Device screen scale**: a snapshot taken on a 3× device differs from a 1× device. Fix the scale in the test: `UITraitCollection(displayScale: 2)`, or always run tests on the same simulator configuration.
- **Font rendering**: system fonts render slightly differently across OS versions. Use `precision: 0.98` to allow minor differences, or use `.recursiveDescription` (text-based) for font-sensitive components.
- **Regenerating on intentional changes**: run tests with `isRecording = true` (or set `record: true`), commit the updated snapshots, then revert the recording flag.
- **CI environment**: run snapshot tests only on a pinned simulator (e.g., "iPhone 15 Pro, iOS 17.4") — different simulators produce different renderings.

## 4. Practical Usage

```swift
import XCTest
import SnapshotTesting
@testable import DesignSystem

// ── UIView snapshot ───────────────────────────────────────────
final class PostCardViewSnapshotTests: XCTestCase {

    override func setUp() {
        super.setUp()
        // Uncomment to regenerate all snapshots:
        // isRecording = true
    }

    func test_postCard_defaultState() {
        let view = PostCardView()
        view.configure(with: .stub)
        view.frame = CGRect(x: 0, y: 0, width: 375, height: 120)

        assertSnapshot(of: view, as: .image)
    }

    func test_postCard_withLongTitle_wrapsCorrectly() {
        let post = Post.stub(title: "This is a very long title that should wrap to multiple lines in the card view")
        let view = PostCardView()
        view.configure(with: post)
        view.frame = CGRect(x: 0, y: 0, width: 375, height: 160)

        assertSnapshot(of: view, as: .image)
    }

    func test_postCard_darkMode() {
        let view = PostCardView()
        view.configure(with: .stub)
        view.frame = CGRect(x: 0, y: 0, width: 375, height: 120)
        view.overrideUserInterfaceStyle = .dark

        assertSnapshot(of: view,
                       as: .image(traits: .init(userInterfaceStyle: .dark)),
                       named: "darkMode")
    }
}

// ── UIViewController snapshot ─────────────────────────────────
final class LoginViewControllerSnapshotTests: XCTestCase {

    func test_loginScreen_initialState() {
        let vc = LoginViewController()
        _ = vc.view   // trigger viewDidLoad

        assertSnapshot(of: vc, as: .image(on: .iPhone13Pro))
    }

    func test_loginScreen_withError() {
        let vc = LoginViewController()
        _ = vc.view
        vc.showError("Invalid email or password")

        assertSnapshot(of: vc,
                       as: .image(on: .iPhone13Pro),
                       named: "withError")
    }
}

// ── SwiftUI View snapshot ─────────────────────────────────────
import SwiftUI

final class FeedViewSnapshotTests: XCTestCase {

    func test_feedRow_lightMode() {
        let view = FeedRowView(post: .stub)

        assertSnapshot(of: view,
                       as: .image(layout: .device(config: .iPhone13Pro)))
    }

    func test_feedRow_darkMode() {
        let view = FeedRowView(post: .stub)
            .environment(\.colorScheme, .dark)

        assertSnapshot(of: view,
                       as: .image(layout: .device(config: .iPhone13Pro)),
                       named: "dark")
    }

    func test_feedRow_accessibilityLargeText() {
        let view = FeedRowView(post: .stub)
            .environment(\.sizeCategory, .accessibilityLarge)

        assertSnapshot(of: view,
                       as: .image(layout: .sizeThatFits),
                       named: "largeText")
    }
}

// ── Codable JSON inline snapshot ──────────────────────────────
final class PostJSONSnapshotTests: XCTestCase {

    func test_post_encodesCorrectly() throws {
        let post = Post(id: "42", title: "Hello", authorName: "Alice",
                        publishedAt: Date(timeIntervalSince1970: 0))

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601

        assertInlineSnapshot(of: post, as: .json(encoder)) {
            """
            {
              "author_name" : "Alice",
              "id" : "42",
              "published_at" : "1970-01-01T00:00:00Z",
              "title" : "Hello"
            }
            """
        }
    }
}

// ── Test stubs ────────────────────────────────────────────────
extension Post {
    static var stub: Post {
        Post(id: "1", title: "Sample Post Title", authorName: "Alice",
             publishedAt: Date(timeIntervalSince1970: 1_700_000_000))
    }

    static func stub(title: String) -> Post {
        Post(id: "1", title: title, authorName: "Alice",
             publishedAt: Date(timeIntervalSince1970: 1_700_000_000))
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is snapshot testing and what types of bugs does it catch that unit tests miss?**

A: Snapshot testing captures the rendered output of a UI component and compares it to a stored reference on subsequent runs. It catches visual regressions that are invisible to unit tests: a colour that changed from `systemBlue` to `systemIndigo` due to an accidental constant change, a label that was clipped because a constraint was weakened, a layout that broke under Dynamic Type large text, or a dark mode style that wasn't applied to a new subview. Unit tests verify logic (the model is correct, the ViewModel produces the right data) but are blind to rendering. Snapshot tests provide a safety net for the visual layer at the cost of requiring maintenance when designs change intentionally.

**Q: What does the `record` flag do in `assertSnapshot` and when should you use it?**

A: When `record: true` (or `isRecording = true`), `assertSnapshot` writes the current rendering to disk as the reference snapshot and **always passes**. Use it when: (1) Adding a snapshot test for the first time — the reference doesn't exist yet. (2) A design change was intentional — you need to update the reference to match the new look. After recording, inspect the written `.png` files to confirm they look correct, then commit them and remove the `record: true` flag. Never leave `record: true` in committed code — every run would overwrite references and the test would never fail.

### Hard

**Q: Snapshot tests fail on CI but pass locally. What are the likely causes and how do you fix them?**

A: Four common causes: (1) **Different screen scale** — the local machine renders at 3× (Retina) while CI uses a 1× or 2× simulator. Fix: pin both environments to the same simulator model and OS version. Use `UITraitCollection(displayScale: 2.0)` to force a consistent scale in tests. (2) **Font rendering differences** — SF Pro renders slightly differently across OS versions. Use `precision: 0.98` or `0.99` to allow minor pixel differences, or use `.recursiveDescription` for font-sensitive tests. (3) **Date/time-dependent content** — any view displaying `Date.now` produces different snapshots each run. Replace live dates with fixed `Date(timeIntervalSince1970:)` stubs in test data. (4) **Missing `isRecording = false`** — someone accidentally left `record: true` in a commit; references on CI are overwritten each run and tests always pass locally (where the fresh snapshot matches itself). Audit snapshots in CI artifacts.

**Q: How do you test a SwiftUI component that displays different content based on an environment value (e.g., colour scheme or size category)?**

A: Use `swift-snapshot-testing`'s `image(layout:)` strategy combined with `.environment(_:_:)` modifiers on the view. Create named snapshots for each variant so they're stored separately: `assertSnapshot(of: view.environment(\.colorScheme, .dark), as: .image(layout: .device(config: .iPhone13Pro)), named: "dark")`. Group the variants in a single test function or split into separate functions depending on whether you want granular failure messages. For a design system component, snapshot all relevant variants systematically: light/dark, all Dynamic Type sizes, RTL layout (`environment(\.layoutDirection, .rightToLeft)`). Run these as part of a `DesignSystem` test target that's isolated from feature code — it rebuilds quickly when only the design system changes.

### Expert

**Q: Design a snapshot testing strategy for a component library that must be verified across iOS 16, iOS 17, iOS 18, light/dark mode, and five Dynamic Type sizes.**

A: Structure as a matrix test: (1) **Parameterised helper**: write a `snapshotAllVariants(of:name:)` helper that calls `assertSnapshot` for each combination — 3 OS versions × 2 colour schemes × 5 type sizes = 30 snapshots per component. Use `named:` parameter to give each combination a unique name (e.g., `"ios17-dark-xxxl"`). (2) **CI matrix**: run snapshot tests on three pinned simulators (one per OS version) in parallel. Each simulator set produces its own snapshot artifacts. References are stored in subdirectories by OS version: `__Snapshots__/ios16/`, `__Snapshots__/ios17/`. (3) **Reference management**: snapshots are committed to source control. Use a script that automatically opens a diff viewer (`ksdiff`, `Beyond Compare`) when tests fail, showing the expected vs actual image side by side. (4) **Precision tuning**: use `.image(precision: 0.98)` globally for the design system to tolerate sub-pixel font rendering differences. For exact colour verification (brand colour compliance), write separate unit tests asserting on `UIColor` values rather than pixels. (5) **Inline snapshots for models**: use inline JSON snapshots for Codable responses — these are OS-independent and avoid the per-OS snapshot matrix for data layer tests.

## 6. Common Issues & Solutions

**Issue: Snapshot test fails with "No reference was found" on first run.**

Solution: Run once with `isRecording = true` (or `record: true`) to generate the reference. The framework writes the file to `__Snapshots__/` relative to the test source file. Inspect the generated image, commit it, then remove the recording flag.

**Issue: Snapshot test fails for a view containing `Text(Date.now, style: .relative)`.**

Solution: The rendered text changes every second. Replace live dates with deterministic fixed dates in test stubs. For components that must display "time ago" text, inject a `Clock` or `Date` dependency into the view, and in tests pass `Date(timeIntervalSince1970: 1_700_000_000)`.

**Issue: Committed snapshots are 5 MB and slow down `git clone`.**

Solution: Store reference snapshots in Git LFS (Large File Storage) — `git lfs track "**/__Snapshots__/**/*.png"`. This keeps the repository clone fast while snapshots remain version-controlled. Alternatively, generate snapshot images in CI only and compare them in a separate artifact step rather than storing them in Git.

## 7. Related Topics

- [Unit Testing](unit-testing.md) — snapshot tests complement unit tests for the visual layer
- [UI Testing](ui-testing.md) — XCUITest tests behaviour; snapshot tests test appearance
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — snapshot each state transition of a SwiftUI view
- [UIView Lifecycle](../04-ui-frameworks/uiview-lifecycle.md) — `layoutIfNeeded()` before snapshotting to ensure correct layout
