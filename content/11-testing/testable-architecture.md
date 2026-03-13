# Testable Architecture

## 1. Overview

Testable architecture is the set of design choices that make code easy to test in isolation: constructor injection so dependencies can be replaced, protocol-based types so real implementations can be swapped for fakes, and clear layer separation so business logic has no dependency on UIKit or the network. The canonical test double taxonomy — **stub** (returns hardcoded values), **mock** (verifies calls were made), **spy** (wraps real implementation + records calls), **fake** (lightweight working alternative) — provides a vocabulary for choosing the right double for each test scenario. Beyond XCTest, **Quick** and **Nimble** provide BDD-style spec syntax and an expressive assertion library that makes test intent clearer.

## 2. Simple Explanation

Testable architecture is like building a car with removable, standardised parts. The engine (business logic) connects to the fuel system (network) via a standardised fuel connector (protocol). In the real car, a real fuel pump fulfils the connector. In the test garage, a test rig (fake or stub) uses the same connector to provide controlled fuel. You can then test the engine's behaviour at 50%, 100%, and 0% fuel without needing a real pump. If the engine is welded directly to the real pump (tight coupling), you can't test it without starting the whole car — slow, brittle, and dangerous.

## 3. Deep iOS Knowledge

### Test Double Taxonomy

| Type | Behaviour | Records calls? | Working implementation? | Use for |
|------|-----------|---------------|------------------------|---------|
| **Stub** | Returns hardcoded values | No | No | Providing input data |
| **Mock** | Verifies specific calls were made | Yes | No | Verifying interactions |
| **Spy** | Wraps real implementation + records | Yes | Yes (delegates) | Observing side effects |
| **Fake** | Simplified working implementation | No | Yes (simplified) | In-memory stores, fast replacements |
| **Dummy** | Satisfies type requirements, not used | No | No | Filling parameter slots |

### Dependency Injection for Testability

Constructor injection is the most testable pattern — all dependencies are explicit and replaceable:

```swift
// Tight coupling — not testable
class FeedViewModel {
    private let service = NetworkService()    // hard-coded; cannot replace
}

// Constructor injection — testable
class FeedViewModel {
    private let service: FeedServiceProtocol   // protocol = seam for test double
    init(service: FeedServiceProtocol) { self.service = service }
}
```

### Protocol Seams

A **seam** is a point where the implementation can be replaced without changing the calling code. Protocols are the primary seam mechanism in Swift:

```swift
// Protocol defines the contract
protocol FeedServiceProtocol {
    func fetchPosts() async throws -> [Post]
    func deletePost(id: String) async throws
}

// Production implementation
class FeedService: FeedServiceProtocol { /* real URLSession calls */ }

// Test stub
class StubFeedService: FeedServiceProtocol {
    var stubbedPosts: [Post] = []
    func fetchPosts() async throws -> [Post] { stubbedPosts }
    func deletePost(id: String) async throws { }
}

// Test mock (also verifies interactions)
class MockFeedService: FeedServiceProtocol {
    var fetchCallCount = 0
    var deleteCallCount = 0
    var deletedIDs: [String] = []
    var postsToReturn: [Post] = []
    var errorToThrow: Error?

    func fetchPosts() async throws -> [Post] {
        fetchCallCount += 1
        if let error = errorToThrow { throw error }
        return postsToReturn
    }

    func deletePost(id: String) async throws {
        deleteCallCount += 1
        deletedIDs.append(id)
    }
}
```

### Fake Implementations

A fake has real (simplified) behaviour — suitable when the production implementation is too slow or has side effects:

```swift
// Fake in-memory repository (real behaviour, no disk I/O)
class FakeUserRepository: UserRepositoryProtocol {
    private var store: [String: User] = [:]

    func save(_ user: User) async throws { store[user.id] = user }
    func fetch(id: String) async throws -> User? { store[id] }
    func fetchAll() async throws -> [User] { Array(store.values) }
    func delete(id: String) async throws { store.removeValue(forKey: id) }
}
```

### Quick / Nimble

**Quick** provides BDD-style spec syntax (`describe`, `context`, `it`). **Nimble** provides expressive matchers.

```swift
import Quick
import Nimble

class FeedViewModelSpec: QuickSpec {
    override func spec() {
        describe("FeedViewModel") {
            var sut: FeedViewModel!
            var mockService: MockFeedService!

            beforeEach {
                mockService = MockFeedService()
                sut = FeedViewModel(service: mockService)
            }

            afterEach {
                sut = nil
                mockService = nil
            }

            describe("loadPosts") {
                context("when the service succeeds") {
                    beforeEach {
                        mockService.postsToReturn = [Post(id: "1", title: "Hello")]
                        await sut.loadPosts()
                    }
                    it("publishes the posts") {
                        expect(sut.posts).to(haveCount(1))
                        expect(sut.posts.first?.title).to(equal("Hello"))
                    }
                    it("sets isLoading to false") {
                        expect(sut.isLoading).to(beFalse())
                    }
                }

                context("when the service throws an error") {
                    beforeEach {
                        mockService.errorToThrow = NetworkError.unauthorized
                        await sut.loadPosts()
                    }
                    it("sets an error message") {
                        expect(sut.errorMessage).toNot(beNil())
                    }
                    it("does not publish posts") {
                        expect(sut.posts).to(beEmpty())
                    }
                }
            }
        }
    }
}
```

**Nimble matchers**:
```swift
expect(value).to(equal(42))
expect(array).to(haveCount(3))
expect(string).to(beginWith("Hello"))
expect(string).to(contain("world"))
expect(optional).to(beNil())
expect(optional).toNot(beNil())
expect(value).to(beGreaterThan(0))
expect { try throwingFn() }.to(throwError())
expect { try throwingFn() }.to(throwError(NetworkError.unauthorized))
// Async:
await expect { try await asyncFn() }.to(equal("result"))
```

### Test-Driven Development (TDD)

TDD follows a Red-Green-Refactor cycle:
1. **Red** — write a failing test for the next behaviour.
2. **Green** — write the minimum code to make it pass.
3. **Refactor** — clean up without breaking tests.

Benefits: forces small, focused changes; design emerges naturally (code is designed to be testable from the start); provides a regression safety net. In practice, many iOS engineers use TDD for pure logic (ViewModel, business rules) and test-after for UI components.

### Testing @MainActor ViewModels

```swift
@MainActor
final class FeedViewModelTests: XCTestCase {
    var sut: FeedViewModel!

    override func setUp() async throws {
        sut = FeedViewModel(service: MockFeedService())
    }

    func test_loadPosts() async throws {
        await sut.loadPosts()
        XCTAssertFalse(sut.isLoading)
    }
}
```

Mark the test class `@MainActor` when the SUT is `@MainActor` — prevents "actor-isolated property can only be accessed on the main actor" warnings.

### Verifying No Unexpected Interactions

Mocks should assert that only the expected calls were made:

```swift
// At end of test:
XCTAssertEqual(mockService.fetchCallCount, 1, "Should fetch exactly once")
XCTAssertEqual(mockService.deleteCallCount, 0, "Should not delete anything")
XCTAssertTrue(mockService.deletedIDs.isEmpty)
```

## 4. Practical Usage

```swift
import XCTest
import Quick
import Nimble
@testable import FeedFeature

// ── Mock with interaction verification ───────────────────────
class MockAnalyticsService: AnalyticsProtocol {
    struct Event: Equatable {
        let name: String
        let properties: [String: String]
    }
    private(set) var trackedEvents: [Event] = []

    func track(_ name: String, properties: [String: String]) {
        trackedEvents.append(Event(name: name, properties: properties))
    }

    func verify(event: String, properties: [String: String] = [:],
                file: StaticString = #file, line: UInt = #line) {
        XCTAssertTrue(
            trackedEvents.contains(Event(name: event, properties: properties)),
            "Expected event '\(event)' was not tracked. Tracked: \(trackedEvents)",
            file: file, line: line
        )
    }
}

// ── Spy wrapping real implementation ─────────────────────────
class SpyFeedRepository: FeedRepositoryProtocol {
    private let wrapped: FeedRepositoryProtocol
    private(set) var fetchCallCount = 0
    private(set) var lastFetchedPage: Int?

    init(wrapping: FeedRepositoryProtocol) { self.wrapped = wrapping }

    func fetchPosts(page: Int) async throws -> [Post] {
        fetchCallCount += 1
        lastFetchedPage = page
        return try await wrapped.fetchPosts(page: page)
    }
}

// ── Fake in-memory keychain ───────────────────────────────────
class FakeKeychain: KeychainProtocol {
    private var store: [String: String] = [:]

    func save(_ value: String, for key: String) throws { store[key] = value }
    func read(for key: String) throws -> String {
        guard let value = store[key] else { throw KeychainError.itemNotFound }
        return value
    }
    func delete(for key: String) throws { store.removeValue(forKey: key) }
}

// ── Quick / Nimble spec ───────────────────────────────────────
class AuthViewModelSpec: QuickSpec {
    override func spec() {
        describe("AuthViewModel") {
            var sut: AuthViewModel!
            var mockAuthService: MockAuthService!
            var fakeKeychain: FakeKeychain!
            var mockAnalytics: MockAnalyticsService!

            beforeEach {
                mockAuthService = MockAuthService()
                fakeKeychain = FakeKeychain()
                mockAnalytics = MockAnalyticsService()
                sut = AuthViewModel(
                    authService: mockAuthService,
                    keychain: fakeKeychain,
                    analytics: mockAnalytics
                )
            }

            describe("login") {
                context("with valid credentials") {
                    let email = "alice@example.com"
                    let password = "secure123"

                    beforeEach {
                        mockAuthService.tokenToReturn = "jwt-token-abc"
                        await sut.login(email: email, password: password)
                    }

                    it("calls auth service with correct credentials") {
                        expect(mockAuthService.lastLoginEmail).to(equal(email))
                        expect(mockAuthService.lastLoginPassword).to(equal(password))
                    }

                    it("stores token in keychain") {
                        let stored = try? fakeKeychain.read(for: "access_token")
                        expect(stored).to(equal("jwt-token-abc"))
                    }

                    it("tracks login event") {
                        mockAnalytics.verify(event: "user_login",
                                             properties: ["method": "email"])
                    }

                    it("sets isAuthenticated to true") {
                        expect(sut.isAuthenticated).to(beTrue())
                    }
                }

                context("with invalid credentials") {
                    beforeEach {
                        mockAuthService.errorToThrow = AuthError.invalidCredentials
                        await sut.login(email: "bad@test.com", password: "wrong")
                    }

                    it("sets error message") {
                        expect(sut.errorMessage).toNot(beNil())
                    }

                    it("does not store a token") {
                        let stored = try? fakeKeychain.read(for: "access_token")
                        expect(stored).to(beNil())
                    }

                    it("tracks login failure") {
                        mockAnalytics.verify(event: "login_failed")
                    }

                    it("does not authenticate") {
                        expect(sut.isAuthenticated).to(beFalse())
                    }
                }
            }

            describe("logout") {
                beforeEach {
                    try? fakeKeychain.save("existing-token", for: "access_token")
                    await sut.logout()
                }

                it("removes token from keychain") {
                    let stored = try? fakeKeychain.read(for: "access_token")
                    expect(stored).to(beNil())
                }

                it("sets isAuthenticated to false") {
                    expect(sut.isAuthenticated).to(beFalse())
                }
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a stub and a mock?**

A: A **stub** is a test double that returns hardcoded values — it provides pre-programmed responses to method calls. It answers the question "what should this dependency return?" A **mock** is a test double that records the calls made to it and allows the test to verify that specific interactions occurred — it answers the question "was this method called with the right arguments?" A stub is sufficient when you only need to control what the dependency returns. A mock is needed when the test wants to assert on side effects — "did the analytics service receive the correct event?" or "was the cache invalidated exactly once?" Many test doubles are hybrids that both return stubbed values and record interactions (sometimes called "mocking stubs" or simply mocks in practice).

**Q: Why should constructor injection be preferred over property injection for test doubles?**

A: Constructor injection makes dependencies explicit and mandatory — the object cannot be created without its dependencies, making it impossible to accidentally use a real dependency in a test. It also enforces immutability (dependencies can be stored as `let` constants). Property injection (setting `viewModel.service = mockService` after creation) allows the object to exist in an uninitialised state, can be missed (test forgets to inject the mock), and makes `let` constants impossible — the dependency must be `var`. The only legitimate use of property injection is for optional dependencies (delegates, notification targets) or for `@AppDelegate`-accessible services that can't be injected at construction time.

### Hard

**Q: How do you test a ViewModel that has side effects only observable via a published state change, without introducing timing dependencies?**

A: Two patterns: (1) **Async test with `await`**: if the ViewModel method is `async`, `await` it directly in the test — the `@Published` property is updated synchronously on the main actor when the async function completes. Assert after the `await`. (2) **Synchronous mock delivery**: if the ViewModel triggers a Combine pipeline, configure the mock dependency to deliver responses synchronously (call its completion handler immediately in the test). For `@Published` properties driven by synchronous operations, assertions are immediate — no wait needed. Avoid `XCTestExpectation` with `waitForExpectations(timeout: 1)` — this introduces a 1-second wall-clock dependency that makes the test suite slow and can hide race conditions. Reserve `XCTestExpectation` for genuinely asynchronous observations (NotificationCenter, delegate callbacks) that cannot be made synchronous.

**Q: When should you choose Quick/Nimble over plain XCTest?**

A: Quick/Nimble excel when: (1) Tests have complex setup hierarchies — `context` blocks allow shared setup for groups of related tests without duplicating `setUp` code. (2) The team has a BDD background and finds `it("sets isLoading to false")` more readable than `func test_loadPosts_whenServiceSucceeds_setsIsLoadingFalse`. (3) Nimble matchers (`haveCount`, `beginWith`, `throwError`) produce more informative failure messages than XCTest's `XCTAssertEqual`. Prefer plain XCTest when: the team is primarily Apple-ecosystem engineers (XCTest is deeply integrated with Xcode's test navigator and coverage); the project already has a large XCTest suite (mixing is confusing); or the simplicity of `func test_X()` is sufficient for the test complexity. Both are valid — choose consistently within a project.

### Expert

**Q: Design the test double infrastructure for a feature module that has five dependencies: a network service, a database repository, an analytics tracker, a keychain, and a user session provider.**

A: The infrastructure has three layers: (1) **Protocol layer**: each dependency is defined by a protocol (`NetworkServiceProtocol`, `PostRepositoryProtocol`, `AnalyticsProtocol`, `KeychainProtocol`, `SessionProtocol`). The production composition root creates the concrete types; test targets use test doubles. (2) **Test double library** (a separate `ModuleTests` SPM target or folder): `MockNetworkService` (records requests, returns configurable responses), `MockPostRepository` (in-memory `[String: Post]` dictionary, real behaviour), `MockAnalyticsService` (records events for verification), `FakeKeychain` (in-memory dictionary, real Keychain logic), `StubSession` (returns a fixed user). These are shared across unit tests and integration tests. (3) **Factory helpers**: `ModuleTestFactory.makeSUT(network:repository:analytics:keychain:session:)` with sensible defaults (all mocks) that individual tests override only for the dependency they're testing. This prevents tests from coupling to all five dependencies when they're testing one. The pattern reduces boilerplate from 5 lines of setup per test to 1, and makes it immediately clear which dependency a test actually exercises.

## 6. Common Issues & Solutions

**Issue: Test double must conform to a protocol with `associatedtype` — Swift won't allow it as a variable type.**

Solution: Use `any ProtocolName` (existential) in Swift 5.7+, or create a concrete generic wrapper (`AnyRepository<T>`). For test doubles, the simplest fix is to make the protocol non-generic — separate protocol methods by specialisation rather than using `associatedtype`. If the associatedtype is unavoidable, create a type-erased wrapper class.

**Issue: Mock verification at the end of the test is too granular — small refactors break tests.**

Solution: Over-specified mocks (asserting exact call count and argument values for every interaction) are brittle. Only assert on interactions that are the **subject of the test**. Move secondary interaction assertions into separate tests with clear names. For most tests, a stub (no interaction assertions) is sufficient — save mocks for tests specifically about side effects.

**Issue: Quick tests run correctly in Xcode but fail on CI with "QuickSpec subclass not found."**

Solution: Quick discovers specs via Objective-C runtime registration. Ensure the test target links Quick and Nimble correctly (not just the app target). In SPM, add Quick and Nimble to the `.testTarget`'s dependencies, not the main target. Also check that the test bundle is loaded — add `@testable import YourModule` even if not strictly needed, to ensure the bundle registers with the Objective-C runtime.

## 7. Related Topics

- [Unit Testing](unit-testing.md) — applying test doubles in XCTest
- [Integration Testing](integration-testing.md) — fakes and real components together
- [Dependency Injection](../06-architecture/dependency-injection.md) — constructor injection enables test doubles
- [SOLID Principles](../06-architecture/solid-principles.md) — Interface Segregation = small, mockable protocols
- [MVVM](../06-architecture/mvvm.md) — ViewModel with protocol-injected services is the canonical testable unit
