# Integration Testing

## 1. Overview

Integration tests verify that multiple real components work correctly together — a ViewModel with a real Repository, a Repository with a real database, or a networking layer with a mocked-but-realistic HTTP server. Unlike unit tests (which replace all dependencies with test doubles), integration tests exercise the actual collaboration between components, catching bugs that arise at boundaries: data mapping errors, SQL constraint violations, serialisation mismatches, and concurrency issues between layers. The key technique is **selective mocking**: replace only the boundary that would be slow, non-deterministic, or destructive (real network, real file system with side effects) while keeping real implementations for everything else. A well-structured integration test suite typically uses an in-memory database, a `URLProtocol`-based mock server, and real business logic.

## 2. Simple Explanation

A unit test checks that a single machine part works in isolation on a test bench. An integration test assembles two or three real parts together and checks that they work as a sub-assembly. You still control the inputs — you don't use the real engine, but you use real gears and a real gearbox. The goal is to find mismatches at the joins: a gear that's the right shape but the wrong tooth pitch, or a gearbox that's mechanically correct but leaks fluid when two parts seal against each other.

## 3. Deep iOS Knowledge

### What to Mock vs What to Keep Real

| Layer | Integration test approach |
|-------|--------------------------|
| Network (URLSession) | Replace with `MockURLProtocol` or local HTTP server |
| Database (Core Data / GRDB) | Use in-memory store — real schema, no disk I/O |
| File system | Use temp directory; clean up in `tearDown` |
| Keychain | Use a test Keychain group or in-memory fake |
| Business logic (ViewModel, Repository) | **Real** — this is what you're testing |
| External services (Analytics, Crash reporting) | Replace with no-op stubs |

### Mocking the Network with URLProtocol

`MockURLProtocol` intercepts `URLSession` requests and returns canned responses without hitting the network. Register it per-session (not globally) to avoid polluting other tests:

```swift
final class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = MockURLProtocol.requestHandler else {
            client?.urlProtocol(self, didFailWithError: URLError(.unknown)); return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
```

Build the `URLSession` with `MockURLProtocol` registered:
```swift
let config = URLSessionConfiguration.ephemeral
config.protocolClasses = [MockURLProtocol.self]
let session = URLSession(configuration: config)
```

### In-Memory Core Data

Pass an in-memory store to avoid touching the file system:

```swift
let container = NSPersistentContainer(name: "MyApp")
container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
container.loadPersistentStores { _, error in
    XCTAssertNil(error, "Store should load without error")
}
```

Or use `PersistenceController.preview` (described in [Core Data](../08-data-persistence/core-data.md)) which already uses `/dev/null`.

### In-Memory GRDB

```swift
let db = try DatabaseQueue()   // DatabaseQueue() with no path = in-memory
try AppDatabase.migrator.migrate(db)
```

### Testing Repository + Database Together

This is the sweet spot for integration tests: the repository uses real SQL, the schema is real, but no file is written to disk:

```swift
final class PostRepositoryIntegrationTests: XCTestCase {
    var db: DatabaseQueue!
    var sut: PostRepository!

    override func setUp() async throws {
        db = try DatabaseQueue()
        try AppDatabase.migrator.migrate(db)
        sut = PostRepository(db: db)
    }

    override func tearDown() async throws {
        db = nil
        sut = nil
    }
}
```

### Testing ViewModel + Network Together

A ViewModel integration test uses a real ViewModel with a real Repository but a mock URLSession. This catches: JSON decoding mismatches, error propagation chains, and state machine bugs at the ViewModel–Repository boundary.

### Async Integration Tests

Use `async throws` test methods. For Combine pipelines, collect values via `publisher.values` async sequence or `XCTestExpectation`.

### Test Fixtures

Load realistic JSON responses from test bundle files instead of hardcoding in test code:

```swift
func loadFixture(named name: String, extension ext: String = "json") -> Data {
    let bundle = Bundle(for: type(of: self))
    let url = bundle.url(forResource: name, withExtension: ext)!
    return try! Data(contentsOf: url)
}
```

## 4. Practical Usage

```swift
import XCTest
@testable import NetworkKit
@testable import FeedFeature

// ── Integration test: ViewModel + Repository + Mock Network ───
final class FeedIntegrationTests: XCTestCase {
    var sut: FeedViewModel!
    var repository: FeedRepository!
    var session: URLSession!

    override func setUp() async throws {
        // Real URLSession with mock protocol
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        session = URLSession(configuration: config)

        // Real repository using our mock session
        repository = FeedRepository(session: session, baseURL: URL(string: "https://api.test")!)

        // Real ViewModel
        sut = FeedViewModel(repository: repository)
    }

    override func tearDown() async throws {
        MockURLProtocol.requestHandler = nil
        sut = nil
        repository = nil
        session = nil
    }

    func test_loadFeed_withValidResponse_publishesPosts() async throws {
        // Given: mock server returns a valid JSON response
        let fixture = """
        {"data": [{"id": "1", "title": "Hello World", "author_name": "Alice"}]}
        """.data(using: .utf8)!

        MockURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.url?.path, "/feed")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Accept"), "application/json")
            let response = HTTPURLResponse(url: request.url!, statusCode: 200,
                                          httpVersion: nil, headerFields: nil)!
            return (response, fixture)
        }

        // When
        await sut.loadFeed()

        // Then
        XCTAssertEqual(sut.posts.count, 1)
        XCTAssertEqual(sut.posts.first?.title, "Hello World")
        XCTAssertEqual(sut.posts.first?.authorName, "Alice")  // snake_case mapping
    }

    func test_loadFeed_withMalformedJSON_setsErrorMessage() async throws {
        MockURLProtocol.requestHandler = { request in
            let badJSON = "{not valid json".data(using: .utf8)!
            let response = HTTPURLResponse(url: request.url!, statusCode: 200,
                                          httpVersion: nil, headerFields: nil)!
            return (response, badJSON)
        }

        await sut.loadFeed()

        XCTAssertNotNil(sut.errorMessage)
        XCTAssertTrue(sut.posts.isEmpty)
    }

    func test_loadFeed_with401_triggersSignOut() async throws {
        MockURLProtocol.requestHandler = { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 401,
                                          httpVersion: nil, headerFields: nil)!
            return (response, Data())
        }

        await sut.loadFeed()

        XCTAssertTrue(sut.isSignedOut)
    }
}

// ── Integration test: Repository + GRDB (in-memory) ──────────
import GRDB

final class PostRepositoryDBTests: XCTestCase {
    var db: DatabaseQueue!
    var sut: PostRepository!

    override func setUp() async throws {
        db = try DatabaseQueue()           // in-memory — no disk
        try AppDatabase.migrator.migrate(db)
        sut = PostRepository(db: db)
    }

    override func tearDown() async throws {
        db = nil; sut = nil
    }

    func test_insertAndFetch_roundTrip() async throws {
        // Given
        var post = Post(id: nil, title: "Test Post", body: "Body", authorId: 1,
                        publishedAt: Date(), isFeatured: false)

        // When
        try await sut.insert(&post)
        let fetched = try await sut.fetchAll()

        // Then
        XCTAssertEqual(fetched.count, 1)
        XCTAssertEqual(fetched.first?.title, "Test Post")
        XCTAssertNotNil(post.id)   // id set after insert
    }

    func test_fetchFeatured_returnsOnlyFeaturedPosts() async throws {
        var featured = Post(id: nil, title: "Featured", body: "", authorId: 1,
                            publishedAt: Date(), isFeatured: true)
        var regular  = Post(id: nil, title: "Regular", body: "", authorId: 1,
                            publishedAt: Date(), isFeatured: false)

        try await sut.insert(&featured)
        try await sut.insert(&regular)

        let result = try await sut.fetchFeatured()

        XCTAssertEqual(result.count, 1)
        XCTAssertEqual(result.first?.title, "Featured")
    }

    func test_delete_removesPostFromDatabase() async throws {
        var post = Post(id: nil, title: "ToDelete", body: "", authorId: 1,
                        publishedAt: Date(), isFeatured: false)
        try await sut.insert(&post)
        let id = try XCTUnwrap(post.id)

        try await sut.delete(id: id)

        let remaining = try await sut.fetchAll()
        XCTAssertTrue(remaining.isEmpty)
    }
}

// ── Integration test: Core Data ───────────────────────────────
import CoreData

final class NoteRepositoryCoreDataTests: XCTestCase {
    var container: NSPersistentContainer!
    var sut: NoteRepository!

    override func setUp() async throws {
        container = NSPersistentContainer(name: "MyApp")
        container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            container.loadPersistentStores { _, error in
                if let error { continuation.resume(throwing: error) }
                else { continuation.resume() }
            }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
        sut = NoteRepository(container: container)
    }

    func test_createAndFetch_persistsNote() async throws {
        try await sut.create(title: "Meeting Notes", body: "Discussed Q4 roadmap")
        let notes = try sut.fetchAll()
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(notes.first?.title, "Meeting Notes")
    }
}

// ── Fixture helper ────────────────────────────────────────────
extension XCTestCase {
    func loadFixture(named name: String, ext: String = "json") throws -> Data {
        let bundle = Bundle(for: type(of: self))
        let url = try XCTUnwrap(bundle.url(forResource: name, withExtension: ext),
                                "Fixture '\(name).\(ext)' not found in test bundle")
        return try Data(contentsOf: url)
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between a unit test and an integration test?**

A: A **unit test** exercises one unit in complete isolation — all collaborators are replaced with test doubles. It verifies that a single function, method, or class behaves correctly for a specific input. A **unit test should never touch disk, network, or a real database**. An **integration test** exercises multiple real components working together — a ViewModel with a real Repository, a Repository with a real (in-memory) database, or a network client with a mock HTTP server. It verifies that the components integrate correctly: that the ViewModel correctly maps errors from the Repository, that the Repository correctly transforms SQL rows into domain models, or that the JSON decoding survives a real API response shape. Integration tests catch boundary bugs that unit tests (with their simplified doubles) can miss.

**Q: Why use an in-memory database for integration tests rather than a real on-disk file?**

A: Two reasons: speed and isolation. An in-memory database is an order of magnitude faster — no filesystem I/O, no fsync. More importantly, each test gets a fresh, empty database created in `setUp` and discarded in `tearDown` — tests are completely isolated from each other with no risk of leftover data from a previous run affecting results. A real on-disk file requires careful cleanup (delete the file in `tearDown`), which can fail if a test crashes, leaving corrupted state for subsequent runs. In-memory databases are a no-cost way to get full test isolation with real schema validation, real constraints, and real query behaviour.

### Hard

**Q: How do you test that a ViewModel correctly handles a specific HTTP error status code end-to-end?**

A: Use `MockURLProtocol` registered on an `URLSessionConfiguration.ephemeral` instance (not globally — to avoid affecting other tests). Set `MockURLProtocol.requestHandler` to return an `HTTPURLResponse` with the desired status code (e.g., 429) and any relevant headers (`Retry-After`). Inject the mock `URLSession` into the real `Repository`, inject the real `Repository` into the real `ViewModel`. Call the ViewModel's load function and assert the resulting published state. This tests the full chain: network layer error detection → error propagation to Repository → Repository error mapping → ViewModel error handling → `@Published` state. Without `MockURLProtocol`, you'd either hit the real network (flaky, slow) or stub the Repository (missing the network→Repository mapping).

**Q: How do you test async Combine pipelines in integration tests without introducing timing-dependent waits?**

A: Prefer two approaches: (1) **`async` sequence**: convert the publisher to an `AsyncSequence` using `.values` and collect results in an `async throws` test. Use `.prefix(n)` to collect exactly `n` values, which terminates without a timeout once `n` values are received. (2) **Synchronous mock delivery**: configure the `MockURLProtocol` to deliver responses synchronously (it calls the client delegate methods in `startLoading` immediately, on the same thread). With synchronous delivery, Combine pipelines can often be observed without any async waiting — the downstream subscriber receives values before the `await` on the session call returns. Avoid `XCTestExpectation` with generous timeouts — they make the test suite slow and hide race conditions.

### Expert

**Q: Design an integration test strategy for a feature that involves: (a) fetching data from a REST API, (b) persisting to Core Data, and (c) displaying in a SwiftUI view.**

A: Test each boundary independently: (1) **Network → Decoder**: integration test with `MockURLProtocol` verifying that the real `JSONDecoder` (with `keyDecodingStrategy = .convertFromSnakeCase`) correctly maps the API's snake_case JSON to domain models. Use real fixture files from `Tests/Fixtures/` to avoid brittle inline strings. (2) **Decoder → Core Data**: integration test with an in-memory `NSPersistentContainer` verifying that the Repository correctly inserts decoded models into the correct entities, handles unique constraints, and fetches with the correct predicates. (3) **Core Data → ViewModel**: integration test verifying the ViewModel's `NSFetchedResultsController` (or `@FetchRequest`) correctly reflects inserted/deleted records. (4) **ViewModel → SwiftUI View**: snapshot test (with `swift-snapshot-testing`) against the ViewModel in a known state — doesn't require the full stack. (5) **End-to-end (optional)**: one XCUITest that installs the app with a mock server (via launch arguments enabling `MockURLProtocol` globally) and verifies the complete flow. Keep this to a minimal happy path — the detailed edge cases are covered at lower layers.

## 6. Common Issues & Solutions

**Issue: `MockURLProtocol` is not intercepting requests — real network calls are made.**

Solution: The mock protocol must be registered on the same `URLSessionConfiguration` instance used by the system under test. If the production code uses `URLSession.shared` (or creates its own `URLSession` internally), the mock won't intercept. Inject `URLSession` through constructor or environment — integration tests must control the session. Verify by setting `MockURLProtocol.requestHandler = nil` and checking for the "unexpected request" error.

**Issue: Core Data integration tests are slow — each test takes 200ms+.**

Solution: Loading a Core Data stack from disk is expensive. Use `/dev/null` as the store URL for all test stores, and share one container between tests in the same class (created in `class func setUp`) rather than recreating per test. Reset the store between tests with `NSBatchDeleteRequest` rather than recreating the stack.

**Issue: Integration tests pass locally but fail on CI with "fixture file not found."**

Solution: Test bundle resources must be listed in the test target's `Copy Bundle Resources` build phase (or SPM `testTarget` `resources` array). Fixtures in a subdirectory are not automatically included. Also check that the fixture files are included in the test target membership (not just the app target).

## 7. Related Topics

- [Unit Testing](unit-testing.md) — foundation of the test pyramid; test doubles
- [UI Testing](ui-testing.md) — full end-to-end layer above integration tests
- [Advanced Networking](../07-networking/advanced-networking.md) — `MockURLProtocol` implementation
- [Core Data](../08-data-persistence/core-data.md) — in-memory persistent container for testing
- [SQLite & Realm](../08-data-persistence/sqlite-realm.md) — in-memory DatabaseQueue for GRDB tests
