# Testing Accessibility

## 1. Overview

Accessibility testing verifies that an app's accessibility API implementation is correct — that VoiceOver navigates the UI in a logical order, that all interactive elements have labels and traits, and that colour contrast meets WCAG requirements. Three complementary approaches: **Accessibility Inspector** (Xcode's built-in tool — audits the accessibility tree, checks contrast, and simulates various accessibility settings), **VoiceOver manual testing** (the most accurate method — turn on VoiceOver and navigate the app as a real user would), and **XCTest automated assertions** (programmatic checks that elements exist, have correct labels, and meet contrast thresholds). Automated tests catch regressions; manual VoiceOver testing catches issues that are semantically correct but experientially wrong (e.g., a label that is technically present but confusing to hear).

## 2. Simple Explanation

Testing accessibility is like a building inspection for ramps and lifts. The inspector uses a checklist (Accessibility Inspector audit), physically tests each ramp (VoiceOver manual walkthrough), and occasionally runs automated compliance tests (XCTest assertions). A ramp might pass the checklist but still be too steep for a wheelchair in practice — manual testing catches what the checklist misses. Similarly, an automated audit might flag a missing label, but only a real VoiceOver session reveals that "Profile photo, image" is confusing when read in the context of the surrounding text.

## 3. Deep iOS Knowledge

### Accessibility Inspector

Accessibility Inspector is built into Xcode (Xcode → Open Developer Tool → Accessibility Inspector). It connects to a Simulator or real device and provides:

**Inspection mode**: click any element to see its `accessibilityLabel`, `accessibilityHint`, `accessibilityTraits`, `accessibilityValue`, and `accessibilityFrame`. Use this to debug why VoiceOver is reading the wrong thing.

**Audit mode**: Click the "Run Audit" button (triangle with exclamation mark). The audit checks:
- Missing accessibility labels on interactive elements.
- Small touch target sizes (minimum 44×44 pt).
- Clipped text.
- Colour contrast violations.

Each finding has a severity (warning vs error) and a "?" button linking to documentation.

**Simulation**: Toggle accessibility features (Increase Contrast, Reduce Transparency, Reduce Motion, Button Shapes, Grayscale, Smart Invert) in the Accessibility Inspector settings pane without going to Settings → Accessibility — useful for rapid iteration.

**Dynamic Type preview**: change the Category Size slider in the Inspector to preview all Dynamic Type sizes without restarting the app.

### VoiceOver Manual Testing

VoiceOver on Simulator:
```
Simulator menu → Device → Turn VoiceOver On/Off
Or: Hardware → Use Accessibility Inspector + Enable VoiceOver
```

VoiceOver on device:
```
Settings → Accessibility → VoiceOver → toggle
Or: triple-click the side button (if set as Accessibility Shortcut)
```

**Basic VoiceOver gestures**:
| Gesture | Action |
|---------|--------|
| Single swipe right | Next element |
| Single swipe left | Previous element |
| Double-tap | Activate (tap) |
| Three-finger swipe up | Scroll down |
| Three-finger swipe down | Scroll up |
| Two-finger z-shaped swipe | Escape / go back |
| Swipe up (on adjustable element) | Increment |
| Swipe down (on adjustable element) | Decrement |

**Testing checklist**:
1. Navigate through the entire screen with swipe-right only — every element should be reached, nothing skipped.
2. Every interactive element reads a meaningful label + trait ("Submit, button" not "Button" or silence).
3. The reading order is logical — left-to-right, top-to-bottom.
4. No duplicate focus (two elements for the same visual control).
5. After navigation (push/present), focus moves to the new screen's first element.
6. After dismissal, focus returns to the triggering element.
7. Custom actions (swipe up/down on a cell for delete/share) are accessible.
8. Form elements read their label + current value + trait ("Email, text field").

### XCTest Accessibility Assertions

XCTest's `XCUIElement` provides accessibility-aware queries for UI tests. For dedicated accessibility unit tests, use the `XCUIAccessibility` audit APIs (iOS 17+) or write assertion helpers:

```swift
// Check that all buttons on screen have accessibility labels
func test_allInteractiveElementsHaveLabels() {
    let app = XCUIApplication()
    app.launch()
    // iOS 17+ Accessibility Audits
    try app.performAccessibilityAudit()
}

// Check specific element has correct label and trait
func test_deleteButton_hasCorrectAccessibilityInfo() {
    let app = XCUIApplication()
    app.launch()
    let button = app.buttons["Delete post"]
    XCTAssertTrue(button.exists, "Delete button must be accessible")
    XCTAssertEqual(button.label, "Delete post")
}
```

**`performAccessibilityAudit()` (iOS 17+)**: runs the same checks as Accessibility Inspector's audit programmatically. Issues failing the audit throw an error with a description. Integrate into your UI test suite:

```swift
func test_feedScreen_passesAccessibilityAudit() throws {
    let app = XCUIApplication()
    app.launch()
    // Exclude specific audit types if needed:
    try app.performAccessibilityAudit(for: .all)
}
```

### Colour Contrast Checking

Automated colour contrast checking:
1. **Accessibility Inspector Audit** — flags contrast issues as "warnings".
2. **Snapshot + contrast computation**: capture a screenshot, compute contrast ratio between foreground and background pixels programmatically (WCAG formula).
3. **Design system rule**: enforce that all `UIColor` pairs used in the design system are pre-computed and verified in a unit test that fails if contrast < 4.5:1.

```swift
extension UIColor {
    // Relative luminance per WCAG 2.1
    var relativeLuminance: CGFloat {
        var r: CGFloat = 0; var g: CGFloat = 0; var b: CGFloat = 0; var a: CGFloat = 0
        getRed(&r, green: &g, blue: &b, alpha: &a)
        func linearise(_ c: CGFloat) -> CGFloat {
            c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * linearise(r) + 0.7152 * linearise(g) + 0.0722 * linearise(b)
    }

    func contrastRatio(with other: UIColor) -> CGFloat {
        let l1 = max(relativeLuminance, other.relativeLuminance)
        let l2 = min(relativeLuminance, other.relativeLuminance)
        return (l1 + 0.05) / (l2 + 0.05)
    }
}

// Unit test:
func test_bodyTextOnBackground_meetsWCAGAA() {
    let bodyTextColour = UIColor.label
    let backgroundColour = UIColor.systemBackground
    // Use light mode appearance for calculation:
    let ratio = bodyTextColour.resolvedColor(with: UITraitCollection(userInterfaceStyle: .light))
        .contrastRatio(with: backgroundColour.resolvedColor(with: UITraitCollection(userInterfaceStyle: .light)))
    XCTAssertGreaterThanOrEqual(ratio, 4.5, "Body text must meet WCAG AA contrast ratio")
}
```

## 4. Practical Usage

```swift
import XCTest

// ── Accessibility audit in UI tests (iOS 17+) ─────────────────
final class FeedScreenAccessibilityTests: XCTestCase {

    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting", "--mock-api"]
        app.launch()
    }

    func test_feedScreen_passesAccessibilityAudit() throws {
        // Waits for the feed to load
        XCTAssertTrue(app.tables.firstMatch.waitForExistence(timeout: 5))
        // Runs Accessibility Inspector-equivalent audit programmatically
        try app.performAccessibilityAudit()
    }

    func test_loginScreen_passesAccessibilityAudit() throws {
        // Navigate to login
        app.launchArguments = ["--uitesting", "--logged-out"]
        app = XCUIApplication()
        app.launch()
        // Exclude small hit areas audit (acceptable for icon buttons in this app)
        try app.performAccessibilityAudit(for: [
            .dynamicType,
            .contrast,
            .textClipped,
            .elementDetection
            // Omitting .hitRegion
        ])
    }

    func test_postCell_likeButton_hasAccessibilityLabel() {
        let likeButton = app.buttons.matching(
            NSPredicate(format: "label BEGINSWITH 'Like'")
        ).firstMatch
        XCTAssertTrue(likeButton.waitForExistence(timeout: 3))
        XCTAssertFalse(likeButton.label.isEmpty, "Like button must have accessibility label")
    }

    func test_postCell_deleteAction_isAccessible() {
        // Custom swipe-to-delete action must appear as an accessibility action
        let cell = app.tables.cells.firstMatch
        XCTAssertTrue(cell.waitForExistence(timeout: 3))
        // The action appears in the accessibility actions list
        let deleteAction = cell.accessibilityActions?.first { $0.name == "Delete" }
        // Note: XCUIElement.accessibilityActions requires activating the element first
        cell.tap()   // focus
        // Verify the custom action by attempting to trigger it
        XCTAssertNotNil(deleteAction ?? cell.buttons["Delete"].firstMatch)
    }
}

// ── Snapshot + contrast unit test ────────────────────────────
final class ColourContrastTests: XCTestCase {

    func test_labelOnBackground_lightMode_meetsWCAGAA() {
        let text = UIColor.label
        let bg   = UIColor.systemBackground
        let light = UITraitCollection(userInterfaceStyle: .light)
        let ratio = text.resolvedColor(with: light)
                        .contrastRatio(with: bg.resolvedColor(with: light))
        XCTAssertGreaterThanOrEqual(ratio, 4.5, "label on systemBackground (light) must be ≥ 4.5:1")
    }

    func test_labelOnBackground_darkMode_meetsWCAGAA() {
        let text = UIColor.label
        let bg   = UIColor.systemBackground
        let dark = UITraitCollection(userInterfaceStyle: .dark)
        let ratio = text.resolvedColor(with: dark)
                        .contrastRatio(with: bg.resolvedColor(with: dark))
        XCTAssertGreaterThanOrEqual(ratio, 4.5, "label on systemBackground (dark) must be ≥ 4.5:1")
    }

    func test_brandPrimaryOnWhite_meetsWCAGAA() {
        let brandPrimary = UIColor(named: "BrandPrimary")!
        let white = UIColor.white
        let ratio = brandPrimary.contrastRatio(with: white)
        XCTAssertGreaterThanOrEqual(ratio, 4.5,
            "BrandPrimary (\(brandPrimary)) on white must meet WCAG AA. Current ratio: \(ratio)")
    }
}

extension UIColor {
    var relativeLuminance: CGFloat {
        var r: CGFloat = 0; var g: CGFloat = 0; var b: CGFloat = 0; var a: CGFloat = 0
        getRed(&r, green: &g, blue: &b, alpha: &a)
        func lin(_ c: CGFloat) -> CGFloat { c <= 0.04045 ? c/12.92 : pow((c+0.055)/1.055, 2.4) }
        return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
    }
    func contrastRatio(with other: UIColor) -> CGFloat {
        let l1 = max(relativeLuminance, other.relativeLuminance)
        let l2 = min(relativeLuminance, other.relativeLuminance)
        return (l1+0.05)/(l2+0.05)
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is Accessibility Inspector and what does its "Audit" feature check?**

A: Accessibility Inspector is a tool in Xcode (Xcode → Open Developer Tool → Accessibility Inspector) that connects to a Simulator or device and provides two main features. The **Inspection** view shows the accessibility properties of any element you point at — label, hint, value, traits, frame. Use it to debug VoiceOver reading issues. The **Audit** runs automated checks on the visible UI: missing accessibility labels on interactive elements (buttons, links with no label), touch target sizes smaller than 44×44 pt (minimum for reliable tapping), clipped text (text that's cut off by its container), and colour contrast violations (text/background pairs failing WCAG 4.5:1). Findings are listed as warnings or errors with descriptions. It's the fastest first pass for catching obvious issues — but manual VoiceOver testing is still required for experiential quality.

**Q: What gestures do you use to test an app with VoiceOver?**

A: The core VoiceOver testing gestures: **swipe right** = move to the next element (use this to navigate through every element on screen in order — every interactive element must be reachable and have a meaningful reading). **Swipe left** = previous element. **Double-tap** = activate the currently focused element (equivalent to a tap). **Two-finger swipe up/down** = scroll. **Two-finger Z gesture** = escape (equivalent to back button or dismiss). For adjustable elements (sliders, steppers): **swipe up** = increment, **swipe down** = decrement. For custom actions (delete, share): **swipe up/down while focused** on a cell opens the custom actions rotor. For modals: VoiceOver should automatically move focus to the modal on presentation; after dismissal, it should return to the triggering element.

### Hard

**Q: How do you integrate accessibility testing into a CI pipeline?**

A: Three layers: (1) **Automated audit tests** using `performAccessibilityAudit()` (iOS 17+) in the UI test target. These run on every PR and fail if any auditable issues (missing labels, contrast violations, clipped text) are present. Add these tests to your standard UI test suite. They run in ~10–30 seconds on a simulator. (2) **Colour contrast unit tests**: write a `ColourContrastTests` XCTestCase that checks every foreground/background colour pair in your design system using the WCAG luminance formula. These run in milliseconds as part of the regular unit test suite. (3) **Snapshot-based regression**: use `swift-snapshot-testing` with `.image(traits: .init(accessibilityContrast: .high))` to snapshot in high-contrast mode. Any unintended change to high-contrast appearance fails the snapshot test. For manual VoiceOver testing: create a structured QA checklist (screen by screen) that is run manually before each major release — not every PR, but at least each milestone.

**Q: How do you test Dynamic Type across all content size categories in an automated test?**

A: Use `XCUIApplication.launchArguments` or `UITraitCollection` overrides. For XCUITests: create one test function per critical category or parameterise: iterate over `UIContentSizeCategory.allCases` and snapshot each one using `swift-snapshot-testing` with `assertSnapshot(of: vc, as: .image(on: .iPhone13Pro, traits: UITraitCollection(preferredContentSizeCategory: category)), named: category.rawValue)`. In the Simulator, use the Accessibility Inspector's category size slider to manually test at each size. Also run Xcode's UI Testing with specific launch environment: `app.launchEnvironment["UIPreferredContentSizeCategoryName"] = UIContentSizeCategory.accessibilityExtraExtraLarge.rawValue` — this overrides the Dynamic Type setting for the test session without changing the system setting.

### Expert

**Q: You are building a design system for a large iOS app used by 2 million users, 15% of whom have enabled accessibility settings. Describe your accessibility testing strategy.**

A: Six-layer strategy: (1) **Unit-tested design tokens**: every colour pair, font combination, and spacing constant is a unit test. `ColourContrastTests` asserts all foreground/background combinations in the design system meet WCAG 2.1 AA. Spacing constants are tested to be ≥ 44 pt for touch targets. These run in CI on every commit. (2) **Component snapshot library**: for each design system component (button, card, text field), snapshot tests at: default Dynamic Type, `accessibilityExtraExtraExtraLarge`, dark mode, high contrast mode. 5 components × 4 variants = 20 snapshots. Snapshot drift fails CI. (3) **`performAccessibilityAudit()` in UI tests**: a dedicated `AccessibilitySmokeTests` target runs one test per major screen, calling `performAccessibilityAudit()`. This runs nightly on device farm (not every PR — too slow). Failures create GitHub issues automatically. (4) **VoiceOver regression checklist**: maintained as a Notion document with one row per screen. QA runs this before each release. Any screen marked "audio output changed" is escalated to the original author. (5) **Analytics for accessibility features**: log `UIAccessibility.isVoiceOverRunning`, `isReduceMotionEnabled`, `preferredContentSizeCategory` on session start. Know which 15% of users use which features — prioritise testing the most-used features first. (6) **User feedback channel**: in-app feedback form with an "Accessibility" category. Incoming reports are triaged weekly by the accessibility champion. Any P1 issue is escalated to the next sprint.

## 6. Common Issues & Solutions

**Issue: `performAccessibilityAudit()` fails with "element has no accessibility label" for a valid control.**

Solution: The control's accessibility label is set but the audit may be running before the view is fully configured (e.g., in a dynamic list, cells outside the visible area may not have their accessibility properties set). Ensure the test waits for content to load (`waitForExistence`) before calling `performAccessibilityAudit`. Also check that the failing element is not a decorative image that should have `isAccessibilityElement = false` — the audit flags images without labels even if they're decorative.

**Issue: Accessibility Inspector shows correct labels but VoiceOver reads something different.**

Solution: The element's `accessibilityAttributedLabel` (which supports formatting) may override `accessibilityLabel`. Check: `element.accessibilityAttributedLabel` in the Inspector's full attribute list. Also check for parent elements whose `accessibilityLabel` is set — if a container has `isAccessibilityElement = true` AND a label, it overrides all child labels. Set `isAccessibilityElement = false` on the container or remove its label.

## 7. Related Topics

- [Core Accessibility](core-accessibility.md) — properties the audit checks for
- [UI Support](ui-support.md) — Dynamic Type and contrast properties being tested
- [UI Testing](../11-testing/ui-testing.md) — `XCUIApplication` and page object pattern
- [Snapshot Testing](../11-testing/snapshot-testing.md) — snapshotting accessibility size variants
