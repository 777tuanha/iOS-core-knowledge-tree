# UI Testing

## 1. Overview

UI tests (XCUITest) drive the app through the accessibility layer — the same way VoiceOver interacts with the UI — simulating real user input: taps, swipes, text entry, device rotation. They provide the highest confidence level: a passing UI test means the full app stack (network, database, business logic, navigation, rendering) worked end-to-end. The tradeoff is cost: UI tests are 10–100x slower than unit tests, are inherently flaky (timing, animation, device state), and break on unrelated UI changes. Production suites use UI tests sparingly — typically a critical path (login → main feature → logout) and a handful of regression tests for previously-broken flows. `XCUIApplication`, `XCUIElement`, and `XCUIElementQuery` are the primary APIs.

## 2. Simple Explanation

XCUITest is a robot that uses your app exactly like a real user, but it's blind — it navigates by labels and accessibility identifiers, not by pixel positions. You tell the robot: "Tap the button labelled 'Sign In'", "Type 'alice@email.com' in the text field with identifier 'emailField'", "Wait until the label 'Welcome, Alice' appears." The robot drives a real app process (a separate process from the test) and reports pass/fail based on whether the expected elements appeared and actions succeeded.

## 3. Deep iOS Knowledge

### XCUITest Architecture

XCUITest runs the test code in a **separate process** from the app under test. Communication happens through the accessibility service:

```
XCUITest process              App process
(test code)         ←IPC→    (your app)
XCUIApplication            UIApplication
XCUIElement               UIView / UIControl
```

This means: test code cannot access app objects directly (no `@testable import`). State is communicated via launch arguments, launch environment, accessibility labels, and the accessibility tree.

### XCUIApplication

```swift
let app = XCUIApplication()

// Configure before launch
app.launchArguments = ["--uitesting", "--reset-state"]
app.launchEnvironment = ["MOCK_NETWORK": "1"]

// Launch / terminate
app.launch()           // launch fresh
app.activate()         // bring to foreground if already running
app.terminate()

// Query elements
app.buttons["Sign In"]                          // by label
app.textFields["emailField"]                    // by accessibility identifier
app.staticTexts.matching(identifier: "title").firstMatch
app.tables.cells.element(boundBy: 0)            // first cell in any table
```

### XCUIElement Interactions

```swift
let button = app.buttons["Submit"]
button.tap()
button.doubleTap()
button.press(forDuration: 1.0)    // long press

let field = app.textFields["username"]
field.tap()
field.typeText("alice@example.com")
field.clearAndTypeText("new text")    // custom extension

// Swipe
app.swipeUp()
app.tables.swipeDown()

// Scroll to element
app.tables.cells["TargetCell"].scrollIntoView()
```

### Existence and Waiting

```swift
// Check existence (does not wait)
XCTAssertTrue(app.buttons["Submit"].exists)

// Wait for element (recommended — handles animation delays)
let predicate = NSPredicate(format: "exists == true")
let button = app.buttons["Submit"]
expectation(for: predicate, evaluatedWith: button)
waitForExpectations(timeout: 5)

// Cleaner: XCTNSPredicateExpectation via waitForExistence
XCTAssertTrue(app.buttons["Submit"].waitForExistence(timeout: 5))
```

### Accessibility Identifiers

Accessibility labels are for VoiceOver users and change with localisation. Accessibility identifiers are stable, non-localised, and specifically for testing:

```swift
// In production UIKit code:
button.accessibilityIdentifier = "loginButton"
emailField.accessibilityIdentifier = "emailTextField"

// In SwiftUI:
Button("Sign In") { login() }
    .accessibilityIdentifier("loginButton")

TextField("Email", text: $email)
    .accessibilityIdentifier("emailTextField")
```

**Never use accessibility labels for test queries** — they change with localisation.

### Page Object Pattern

Encapsulate element access in page objects to avoid duplicated element queries and to isolate UI tests from layout changes:

```swift
struct LoginPage {
    let app: XCUIApplication

    var emailField: XCUIElement { app.textFields["emailTextField"] }
    var passwordField: XCUIElement { app.secureTextFields["passwordTextField"] }
    var signInButton: XCUIElement { app.buttons["signInButton"] }
    var errorLabel: XCUIElement { app.staticTexts["errorLabel"] }

    @discardableResult
    func login(email: String, password: String) -> FeedPage {
        emailField.tap()
        emailField.typeText(email)
        passwordField.tap()
        passwordField.typeText(password)
        signInButton.tap()
        return FeedPage(app: app)
    }

    var isDisplayed: Bool { signInButton.exists }
}

struct FeedPage {
    let app: XCUIApplication
    var postCells: XCUIElementQuery { app.tables.cells }
    var isDisplayed: Bool { app.navigationBars["Feed"].exists }
}
```

### Launch Arguments for Test Configuration

Use launch arguments to put the app in a known state:

```swift
// In test:
app.launchArguments = ["--uitesting", "--reset-keychain", "--mock-api"]

// In app (AppDelegate / App):
if CommandLine.arguments.contains("--uitesting") {
    // Disable animations for faster, more reliable tests
    UIView.setAnimationsEnabled(false)
}
if CommandLine.arguments.contains("--reset-keychain") {
    Credentials.clearAll()
}
if CommandLine.arguments.contains("--mock-api") {
    // Use MockURLProtocol globally
    URLSessionConfiguration.default.protocolClasses = [MockURLProtocol.self]
}
```

### Disabling Animations

Animations cause flakiness in UI tests — elements appear and disappear asynchronously. Disable them in the app when launched for testing:

```swift
// In production AppDelegate:
override func application(_ app: UIApplication,
                           didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    if ProcessInfo.processInfo.arguments.contains("--uitesting") {
        UIView.setAnimationsEnabled(false)
    }
    return true
}
```

### XCUITest Reliability Tips

- Prefer `waitForExistence(timeout:)` over `exists` for elements that appear after transitions.
- Use `isHittable` (not just `exists`) before tapping — an element can exist but be covered by another view.
- Avoid hardcoded `sleep` — replace with element existence waits.
- Use stable `accessibilityIdentifier`s, not localised text.
- Isolate tests: launch fresh app, reset state via launch arguments.
- Run UI tests on a dedicated physical device or consistent simulator configuration in CI.

## 4. Practical Usage

```swift
import XCTest

// ── Login flow UI test ────────────────────────────────────────
final class LoginUITests: XCTestCase {
    var app: XCUIApplication!
    var loginPage: LoginPage!

    override func setUp() async throws {
        continueAfterFailure = false    // stop after first failure
        app = XCUIApplication()
        app.launchArguments = ["--uitesting", "--reset-state", "--mock-api"]
        app.launch()
        loginPage = LoginPage(app: app)
    }

    override func tearDown() async throws {
        app.terminate()
        app = nil
    }

    func test_login_withValidCredentials_showsFeed() {
        // Given: mock API returns success for these credentials
        XCTAssertTrue(loginPage.isDisplayed)

        // When
        let feedPage = loginPage.login(email: "user@test.com", password: "password123")

        // Then
        XCTAssertTrue(feedPage.isDisplayed, "Feed should be visible after login")
        XCTAssertFalse(loginPage.isDisplayed, "Login screen should be dismissed")
    }

    func test_login_withInvalidCredentials_showsErrorMessage() {
        // Given: mock API returns 401 for invalid credentials
        loginPage.emailField.tap()
        loginPage.emailField.typeText("bad@test.com")
        loginPage.passwordField.tap()
        loginPage.passwordField.typeText("wrongpassword")
        loginPage.signInButton.tap()

        // Then
        XCTAssertTrue(loginPage.errorLabel.waitForExistence(timeout: 3))
        XCTAssertEqual(loginPage.errorLabel.label, "Invalid email or password")
        XCTAssertTrue(loginPage.isDisplayed, "Should stay on login screen")
    }

    func test_login_emptyEmail_disablesSignInButton() {
        // Sign in button should be disabled when email is empty
        XCTAssertFalse(loginPage.signInButton.isEnabled)

        loginPage.emailField.tap()
        loginPage.emailField.typeText("user@test.com")
        loginPage.passwordField.tap()
        loginPage.passwordField.typeText("pass")

        XCTAssertTrue(loginPage.signInButton.isEnabled)
    }
}

// ── Feed flow UI test ─────────────────────────────────────────
final class FeedUITests: XCTestCase {
    var app: XCUIApplication!
    var feedPage: FeedPage!

    override func setUp() async throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting", "--skip-login", "--mock-api"]
        app.launch()
        feedPage = FeedPage(app: app)
    }

    override func tearDown() async throws { app.terminate() }

    func test_feedLoads_displaysPostCells() {
        XCTAssertTrue(feedPage.isDisplayed)
        XCTAssertGreaterThan(feedPage.postCells.count, 0,
                             "Feed should display at least one post")
    }

    func test_tapPost_navigatesToDetail() {
        let firstCell = feedPage.postCells.element(boundBy: 0)
        XCTAssertTrue(firstCell.waitForExistence(timeout: 3))
        firstCell.tap()

        let detailPage = PostDetailPage(app: app)
        XCTAssertTrue(detailPage.isDisplayed, "Post detail should open")
    }

    func test_pullToRefresh_reloadsContent() {
        let table = app.tables.element
        table.swipeDown()   // pull-to-refresh gesture
        // Wait for loading indicator to disappear
        let spinner = app.activityIndicators.element
        XCTAssertFalse(spinner.waitForExistence(timeout: 5) && spinner.exists,
                       "Spinner should disappear after refresh")
    }
}

// ── Page objects ──────────────────────────────────────────────
struct LoginPage {
    let app: XCUIApplication
    var emailField: XCUIElement    { app.textFields["emailTextField"] }
    var passwordField: XCUIElement { app.secureTextFields["passwordTextField"] }
    var signInButton: XCUIElement  { app.buttons["signInButton"] }
    var errorLabel: XCUIElement    { app.staticTexts["authErrorLabel"] }
    var isDisplayed: Bool          { signInButton.waitForExistence(timeout: 2) }

    @discardableResult
    func login(email: String, password: String) -> FeedPage {
        emailField.tap(); emailField.typeText(email)
        passwordField.tap(); passwordField.typeText(password)
        signInButton.tap()
        return FeedPage(app: app)
    }
}

struct FeedPage {
    let app: XCUIApplication
    var postCells: XCUIElementQuery { app.tables.cells }
    var isDisplayed: Bool           { app.navigationBars["Feed"].waitForExistence(timeout: 5) }
}

struct PostDetailPage {
    let app: XCUIApplication
    var isDisplayed: Bool { app.navigationBars["Post Detail"].waitForExistence(timeout: 3) }
}

// ── XCUIElement helper ────────────────────────────────────────
extension XCUIElement {
    func clearAndTypeText(_ text: String) {
        guard let currentValue = value as? String, !currentValue.isEmpty else {
            typeText(text); return
        }
        // Select all + delete existing text
        tap()
        let selectAllMenu = XCUIApplication().menuItems["Select All"]
        if selectAllMenu.waitForExistence(timeout: 1) {
            selectAllMenu.tap()
            typeText(text)
        } else {
            // Fallback: triple-tap to select all
            tap(withNumberOfTaps: 3, numberOfTouches: 1)
            typeText(text)
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `accessibilityLabel` and `accessibilityIdentifier` and which should you use for UI tests?**

A: `accessibilityLabel` is the human-readable description of a UI element read aloud by VoiceOver — it changes with localisation (different languages have different labels). `accessibilityIdentifier` is a programmer-defined string that identifies an element for testing and automation; it is not localised and does not change. Always use `accessibilityIdentifier` for UI test element queries. Using `accessibilityLabel` makes tests brittle — they break when the app is localised or when copy is edited. Also avoid querying by element index (`cells.element(boundBy: 0)`) for anything other than the first item in a known-size list — indices are fragile when the list reorders.

**Q: What does `continueAfterFailure = false` do and why should you set it in UI tests?**

A: By default (`continueAfterFailure = true`), XCTest continues running assertions after one fails, potentially causing subsequent assertions to crash or produce misleading errors. For UI tests, a failure in the first step (e.g., "Sign In button not found") means all subsequent steps are invalid — the test is navigating a different state than expected. Setting `continueAfterFailure = false` stops the test at the first failure, producing a cleaner, more actionable error message. It also prevents cascading failures that are hard to diagnose. Set it in `setUp` for all UI test classes.

### Hard

**Q: How do you use launch arguments to make UI tests deterministic when the app normally fetches from a remote API?**

A: Pass a launch argument (e.g., `--mock-api`) that the app reads in `didFinishLaunchingWithOptions`. When the flag is present, the app installs `MockURLProtocol` on `URLSessionConfiguration.default.protocolClasses` globally, or switches to an in-memory mock repository. The mock returns fixture data from bundled JSON files or hard-coded responses. This ensures every UI test run sees the same data regardless of network availability, server state, or API changes. A complementary pattern: use `--reset-state` to clear UserDefaults and Keychain so each test starts from a known (logged-out, empty) state. Combining both produces fully deterministic, repeatable UI tests. The app code that reads launch arguments should be guarded (`#if DEBUG`) to ensure it cannot execute in production builds.

**Q: How do you structure UI tests to minimise flakiness caused by animations and async loading?**

A: Four techniques: (1) **Disable animations**: set `UIView.setAnimationsEnabled(false)` in the app when launched with `--uitesting`. This eliminates the most common source of flakiness — transitions that temporarily hide elements. (2) **Use `waitForExistence(timeout:)`**: never assert `element.exists` directly for elements that appear after a navigation or network call. Always wait with a reasonable timeout (2–5s for animations, 10s for network-dependent elements). (3) **Mock the network**: as above — synchronous mock delivery means UI elements appear without any real network delay. (4) **`isHittable` before `tap()`**: an element can exist but be obscured by an animation overlay. Check `element.isHittable` before tapping — if not hittable, wait or scroll. Page objects can encapsulate this retry logic.

### Expert

**Q: How would you structure a UI test suite for a large app with 50+ screens to keep it maintainable and fast?**

A: Five principles: (1) **Critical path only**: UI tests cover only the most important user journeys (onboarding, login, core purchase flow, logout). Detailed edge cases belong in unit/integration tests. Aim for 20–50 UI tests total, not 500. (2) **Page object pattern** for every screen: encapsulate element access in structs. Changes to an element's identifier require updating one place (the page object), not every test. (3) **Shared setup via base classes**: a `LoggedInUITestCase` base class launches the app in a logged-in state; a `OnboardingUITestCase` launches in a fresh state. Tests inherit the appropriate base. (4) **Parallel execution**: Xcode Cloud and most CI systems support running UI test suites on multiple simulators in parallel. Structure tests so they are stateless (reset via launch arguments) and can run in any order. (5) **Test result bundles and screenshots on failure**: configure `recordFailure` or enable automatic screenshots on test failure for faster post-failure debugging without re-running.

## 6. Common Issues & Solutions

**Issue: `element.waitForExistence(timeout: 5)` always returns `false` even though the element is visible.**

Solution: The element's `accessibilityIdentifier` doesn't match what the test queries. Use Xcode's Accessibility Inspector or the UI test recording feature to discover the actual identifier. Also check that the element is in the accessibility tree — some custom views need `isAccessibilityElement = true`.

**Issue: UI tests pass on local machine but fail intermittently on CI.**

Solution: Likely causes: animations not disabled (CI devices may be slower), hardcoded timeouts too short for CI hardware, or test state not reset between runs. Add `--uitesting` argument to disable animations, increase wait timeouts from 2s to 5s for CI, and ensure each test resets to a known state via `--reset-state`.

**Issue: Tapping a button with `app.buttons["Submit"].tap()` fails with "Element is not hittable."**

Solution: The button exists but is not in the visible, tappable area — it may be behind a keyboard, an overlay, or off-screen. Dismiss the keyboard first (`app.keyboards.buttons["Return"].tap()`), scroll the button into view (`button.scrollIntoView()`), or wait for any covering overlay to dismiss before tapping.

## 7. Related Topics

- [Unit Testing](unit-testing.md) — fast, isolated tests that complement UI tests
- [Integration Testing](integration-testing.md) — middle layer; test network+DB without full UI
- [Snapshot Testing](snapshot-testing.md) — visual regression testing complementing UI tests
- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — launch arguments read in `didFinishLaunchingWithOptions`
- [Deep Links & Universal Links](../09-ios-platform/deep-links-universal-links.md) — test deep link routing via `app.open(url)` in XCUITest
