# Unit Testing

## 1. Overview

A unit test exercises a single unit of behaviour in complete isolation — no network calls, no disk I/O, no real dependencies. Each test is a precise, fast specification of what one function or method should do given a specific input. XCTest is Apple's built-in testing framework, fully integrated into Xcode with first-class async/await support since Xcode 14. Well-written unit tests follow the Arrange-Act-Assert (or Given-When-Then) pattern, have descriptive names that document behaviour, clean up state in `tearDown`, and run in milliseconds. A large suite of fast unit tests is the foundation of a reliable CI pipeline — slow tests are skipped; flaky tests are ignored.

## 2. Simple Explanation

A unit test is like a quality-control inspector on a factory line who tests each part before it's assembled into the product. The inspector doesn't care about the whole car — just the one bolt they're checking. They bring a new bolt (set up), apply a specific amount of torque (the action), and measure whether it meets the spec (assert). If the measurement passes, the bolt is good. If not, the report clearly says "Bolt XYZ failed torque test at step 3" — not "car didn't start."

## 3. Deep iOS Knowledge

### XCTest Structure

```swift
import XCTest
@testable import MyModule   // @testable exposes internal symbols

final class UserServiceTests: XCTestCase {

    // SUT (System Under Test) + dependencies
    var sut: UserService!
    var mockRepository: MockUserRepository!

    // ── Lifecycle ────────────────────────────────────────────
    override func setUp() async throws {
        // Runs before EACH test
        mockRepository = MockUserRepository()
        sut = UserService(repository: mockRepository)
    }

    override func tearDown() async throws {
        // Runs after EACH test — clear state to prevent leaks
        sut = nil
        mockRepository = nil
    }

    override class func setUp() {
        // Runs ONCE before all tests in the class
        super.setUp()
    }

    override class func tearDown() {
        // Runs ONCE after all tests in the class
        super.tearDown()
    }
}
```

`@testable import` exposes `internal` symbols without making them `public`. Do not use it in production code.

### Naming Convention

Test names should read as specifications:
```
func test_<unit>_<condition>_<expectedResult>()
func test_fetchUser_whenUserExists_returnsUser()
func test_fetchUser_whenNetworkFails_throwsNetworkError()
func test_login_withInvalidCredentials_returnsUnauthorized()
```

This makes the test report self-documenting — failures tell you exactly what broke.

### Assertions

| Assertion | Use |
|-----------|-----|
| `XCTAssertEqual(a, b)` | Equality |
| `XCTAssertNotEqual(a, b)` | Inequality |
| `XCTAssertNil(x)` | Nil check |
| `XCTAssertNotNil(x)` | Non-nil check |
| `XCTAssertTrue(cond)` | Boolean true |
| `XCTAssertFalse(cond)` | Boolean false |
| `XCTAssertGreaterThan(a, b)` | Ordering |
| `XCTAssertThrowsError(try fn())` | Throws any error |
| `XCTAssertNoThrow(try fn())` | Does not throw |
| `XCTFail("message")` | Unconditional failure |

All assertions accept an optional `message:` and `file:`/`line:` parameters for custom failure messages.

### Async/Await Tests

XCTest supports `async` test methods natively:

```swift
func test_fetchUser_returnsExpectedUser() async throws {
    // Given
    mockRepository.stubbedUser = User(id: "42", name: "Alice")

    // When
    let user = try await sut.fetchUser(id: "42")

    // Then
    XCTAssertEqual(user.name, "Alice")
}
```

**Throwing tests**: if the function throws unexpectedly, the test fails with the error as the failure message — no need for `XCTAssertNoThrow` wrappers.

### Testing Combine Publishers

Use `XCTestExpectation` or the `values` async sequence:

```swift
// Using async values (clean)
func test_searchResults_updatesOnQuery() async throws {
    var results: [[String]] = []
    let cancellable = sut.$searchResults
        .dropFirst()   // drop initial empty value
        .prefix(1)
        .sink { results.append($0) }

    sut.search(query: "swift")
    try await Task.sleep(nanoseconds: 100_000_000)   // 100ms

    XCTAssertEqual(results.first, ["Swift Programming", "SwiftUI"])
    cancellable.cancel()
}

// Using expectation (classic)
func test_publisherEmitsValue() {
    let expectation = expectation(description: "publisher emits")
    var received: String?
    let cancellable = sut.namePublisher
        .sink { received = $0; expectation.fulfill() }

    sut.updateName("Alice")
    waitForExpectations(timeout: 1)

    XCTAssertEqual(received, "Alice")
    cancellable.cancel()
}
```

### Performance Tests

`measure` records CPU time and reports the baseline:

```swift
func test_sortPerformance() {
    let items = (0..<10_000).map { Item(id: $0, value: String($0)) }.shuffled()
    measure {
        _ = items.sorted { $0.value < $1.value }
    }
}

// With options — measure memory:
func test_parsePerformance() {
    let data = largeJSONData()
    let options = XCTMeasureOptions()
    options.iterationCount = 5
    measure(metrics: [XCTMemoryMetric(), XCTCPUMetric()], options: options) {
        _ = try? JSONDecoder().decode([Post].self, from: data)
    }
}
```

### Test Doubles in Unit Tests

Unit tests replace all real dependencies with test doubles. Full taxonomy in [Testable Architecture](testable-architecture.md). Summary:

- **Stub**: returns hardcoded values.
- **Mock**: records calls for verification.
- **Fake**: simplified working implementation (e.g., in-memory store).
- **Spy**: wraps real implementation + records calls.

### XCTUnwrap

Safely unwraps optionals — fails the test (rather than crashing) if nil:

```swift
let result = try XCTUnwrap(sut.lastError as? NetworkError)
XCTAssertEqual(result, .unauthorized)
```

### Skipping Tests

```swift
func test_featureRequiringiOS17() throws {
    try XCTSkipUnless(ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 17,
                      "Requires iOS 17")
    // Test code here
}
```

## 4. Practical Usage

```swift
import XCTest
@testable import FeedFeature

// ── System Under Test ─────────────────────────────────────────
// FeedViewModel fetches posts from FeedRepository and publishes them

final class FeedViewModelTests: XCTestCase {
    var sut: FeedViewModel!
    var mockRepository: MockFeedRepository!

    override func setUp() async throws {
        mockRepository = MockFeedRepository()
        sut = FeedViewModel(repository: mockRepository)
    }

    override func tearDown() async throws {
        sut = nil
        mockRepository = nil
    }

    // ── Happy path ────────────────────────────────────────────
    func test_loadPosts_whenRepositorySucceeds_publishesPosts() async throws {
        // Given
        let expected = [Post(id: "1", title: "Hello"), Post(id: "2", title: "World")]
        mockRepository.postsToReturn = expected

        // When
        await sut.loadPosts()

        // Then
        XCTAssertEqual(sut.posts, expected)
        XCTAssertFalse(sut.isLoading)
        XCTAssertNil(sut.errorMessage)
    }

    // ── Loading state ─────────────────────────────────────────
    func test_loadPosts_setsIsLoadingDuringFetch() async throws {
        mockRepository.delay = 0.1   // 100ms delay to observe loading state
        mockRepository.postsToReturn = []

        var loadingStates: [Bool] = []
        let cancellable = sut.$isLoading.sink { loadingStates.append($0) }

        await sut.loadPosts()
        cancellable.cancel()

        // Should have been: false (initial) → true (loading) → false (done)
        XCTAssertEqual(loadingStates, [false, true, false])
    }

    // ── Error path ────────────────────────────────────────────
    func test_loadPosts_whenRepositoryFails_setsErrorMessage() async throws {
        // Given
        mockRepository.errorToThrow = NetworkError.serverError(statusCode: 500)

        // When
        await sut.loadPosts()

        // Then
        XCTAssertNotNil(sut.errorMessage)
        XCTAssertTrue(sut.posts.isEmpty)
        XCTAssertFalse(sut.isLoading)
    }

    // ── Pagination ────────────────────────────────────────────
    func test_loadMorePosts_appendsToExistingPosts() async throws {
        // Given: initial load
        mockRepository.postsToReturn = [Post(id: "1", title: "First")]
        await sut.loadPosts()

        // When: load more
        let nextPage = [Post(id: "2", title: "Second")]
        mockRepository.postsToReturn = nextPage
        await sut.loadMorePosts()

        // Then
        XCTAssertEqual(sut.posts.count, 2)
        XCTAssertEqual(sut.posts.last?.title, "Second")
    }

    // ── Idempotency ───────────────────────────────────────────
    func test_loadPosts_whenAlreadyLoading_doesNotStartSecondFetch() async throws {
        mockRepository.delay = 1.0   // slow response

        // Start first load (don't await)
        let firstLoad = Task { await self.sut.loadPosts() }

        // Attempt second load while first is in progress
        await sut.loadPosts()

        firstLoad.cancel()
        XCTAssertEqual(mockRepository.fetchCallCount, 1,
                       "Should not start a second fetch while one is in progress")
    }

    // ── Computed property ─────────────────────────────────────
    func test_hasContent_whenPostsEmpty_returnsFalse() {
        sut.posts = []
        XCTAssertFalse(sut.hasContent)
    }

    func test_hasContent_whenPostsNonEmpty_returnsTrue() {
        sut.posts = [Post(id: "1", title: "A")]
        XCTAssertTrue(sut.hasContent)
    }
}

// ── Mock repository ───────────────────────────────────────────
final class MockFeedRepository: FeedRepositoryProtocol {
    var postsToReturn: [Post] = []
    var errorToThrow: Error?
    var delay: TimeInterval = 0
    var fetchCallCount = 0

    func fetchPosts(page: Int) async throws -> [Post] {
        fetchCallCount += 1
        if delay > 0 {
            try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
        }
        if let error = errorToThrow { throw error }
        return postsToReturn
    }
}

// ── Testing a pure transformation function ────────────────────
final class PriceFormatterTests: XCTestCase {

    func test_format_zeroPrice_returnsFreeLabelString() {
        XCTAssertEqual(PriceFormatter.format(cents: 0), "Free")
    }

    func test_format_positiveCents_formatsAsDollarAmount() {
        XCTAssertEqual(PriceFormatter.format(cents: 1999), "$19.99")
    }

    func test_format_negativeCents_returnsEmpty() {
        XCTAssertEqual(PriceFormatter.format(cents: -1), "")
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What does `@testable import` do and when should you avoid it?**

A: `@testable import ModuleName` recompiles the module with all `internal` symbols exposed as if they were `public`, allowing test targets to access internals without making them part of the module's public API. Use it to test `internal` ViewModels, parsers, and utility functions from a test target in the same module. Avoid relying on it heavily — if you're testing many internal details, it's a signal that the internal structure is too fine-grained or that the public API is too thin. Prefer testing through the public interface whenever possible; `@testable` is a convenience for testing internal logic that's not appropriate to expose publicly.

**Q: What is the Arrange-Act-Assert pattern and why is it important?**

A: Arrange-Act-Assert (also Given-When-Then) is a structural pattern for writing clear, readable tests: **Arrange** sets up the preconditions and inputs; **Act** performs the single operation being tested; **Assert** verifies the expected outcome. Its importance: (1) Forces tests to be focused — one behaviour per test. (2) Makes tests self-documenting — any engineer can read the test and understand what it verifies. (3) Makes failure diagnosis faster — when a test fails, the assert section tells you exactly what expectation was violated. Tests without this pattern tend to test multiple things at once, have cryptic assertion messages, and require reading the implementation to understand why they failed.

### Hard

**Q: How do you test code that uses `async/await` in XCTest?**

A: Mark the test method as `async throws`: `func test_something() async throws { }`. XCTest runs async test methods on a Swift concurrency executor. Inside the test, `await` expressions work normally — the test runner waits for each `await` to complete before proceeding. Errors thrown by `try await` calls fail the test with the error as the message. For testing `@Published` properties or Combine publishers, either use `await` with `Task.sleep` (fragile) or better: expose an `async` function that completes when the observable state has been set, or use a helper that collects values from a publisher into an array using `publisher.values` async sequence. Avoid `expectation` + `waitForExpectations` for async/await code — it mixes two concurrency models.

**Q: What is the difference between `setUp()`, `setUp() async throws`, and `setUpWithError()`?**

A: `setUp()` is the original synchronous lifecycle method — no error throwing, runs before each test. `setUpWithError()` is a throwing variant that lets you propagate setup errors as test failures rather than crashing. `setUp() async throws` (Xcode 14+) combines both: it's async (can `await` in setup) and throwing. Use `setUp() async throws` for all new code — it's the most flexible. The async variant is essential when setup requires creating in-memory stores, loading test fixtures from disk, or performing any async operation. `tearDown() async throws` mirrors this for cleanup.

### Expert

**Q: How do you ensure unit tests remain fast as the test suite grows to thousands of tests?**

A: Speed comes from isolation and determinism: (1) **Zero real I/O**: replace all network calls, disk reads, and database queries with in-memory test doubles. Even fast I/O (10ms per test × 1000 tests = 10s) becomes a bottleneck at scale. (2) **No `sleep` or `waitForExpectations` with large timeouts**: use deterministic completion (call the mock's completion handler synchronously in tests, or use `Task { }` with immediate fulfillment). (3) **Parallelism**: enable `XCTest` parallel test execution (`Targets → Build → Parallelize` or `xcodebuild -parallel-testing-enabled YES`). Tests must be stateless — no shared mutable class-level state. (4) **Test target structure**: split large test suites into focused test targets per module. Xcode can build and run changed modules' tests in isolation. (5) **Avoid `@testable import` cascades**: if every test imports a monolithic module, any change triggers full recompilation. Local SPM packages with narrow API surfaces minimise recompilation scope.

## 6. Common Issues & Solutions

**Issue: Test passes in isolation but fails when the full suite runs.**

Solution: The test has a side effect that pollutes state for subsequent tests. Common culprits: shared singletons, `UserDefaults.standard`, static properties, `URLProtocol.registerClass`. Fix: reset singletons in `tearDown`, use `UserDefaults(suiteName:)` with a unique name per test and call `removePersistentDomain` in `tearDown`, and register `URLProtocol` per-session rather than globally.

**Issue: Async test times out even though the function completes.**

Solution: The async function dispatches its completion to `@MainActor` but the test is already on the main actor — a deadlock. Use `await Task.yield()` to yield to the run loop, or ensure the mock resolves synchronously before the await point. Also check for missed `await` — calling an `async` function without `await` schedules it but doesn't wait for it.

**Issue: `XCTAssertEqual` fails on `Equatable` structs despite values appearing identical.**

Solution: The type conforms to `Equatable` but some property is not included in the synthesised comparison — either a computed property or a stored property that breaks the `==` symmetry. Implement explicit `Equatable` conformance listing all relevant fields, or add a `XCTAssertEqual(a.relevantField, b.relevantField)` to diagnose which field differs.

## 7. Related Topics

- [Testable Architecture](testable-architecture.md) — test doubles, DI patterns, Quick/Nimble
- [Integration Testing](integration-testing.md) — testing multiple real components together
- [UI Testing](ui-testing.md) — XCUITest for end-to-end tests
- [Dependency Injection](../06-architecture/dependency-injection.md) — constructor injection enables test doubles
- [async/await](../03-concurrency/async-await.md) — async test patterns
