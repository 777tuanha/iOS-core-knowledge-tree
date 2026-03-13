# Testing & Quality

## Overview

Testing is the engineering discipline that verifies code does what it should, prevents regressions, and gives teams the confidence to refactor and ship. iOS testing spans four layers: **unit tests** (pure logic, single function, no I/O), **integration tests** (multiple real components together — real database, real URLSession with mocked network), **UI tests** (simulate user interaction through the entire app via XCUITest), and **snapshot tests** (pixel-level regression detection for UI components). Effective testing requires a **testable architecture**: dependency injection so collaborators can be replaced with test doubles, protocol-based design so real implementations can be swapped for fakes, and clear separation between logic (ViewModel, Interactor) and side effects (network, database).

Apple's primary testing framework is **XCTest**, integrated directly into Xcode. **Quick** and **Nimble** are popular third-party frameworks providing BDD-style spec syntax and expressive matchers. **XCUITest** drives the UI through the accessibility layer. **swift-snapshot-testing** (Point-Free) captures view snapshots and fails when they change unexpectedly.

## Topics in This Section

- [Unit Testing](unit-testing.md) — XCTest structure, assertions, async/await tests, performance tests, test lifecycle
- [Integration Testing](integration-testing.md) — testing real components together, URLProtocol network mocking, in-memory Core Data, GRDB testing
- [UI Testing](ui-testing.md) — XCUITest, accessibility identifiers, page object pattern, launch arguments, CI reliability
- [Snapshot Testing](snapshot-testing.md) — swift-snapshot-testing library, recording vs asserting, inline snapshots, CI workflow
- [Testable Architecture](testable-architecture.md) — test doubles (stub/mock/spy/fake), protocol-based DI, Quick/Nimble BDD syntax, TDD workflow

## Testing Pyramid

```
        ▲  Fewer, slower, more brittle
        │
        │  ┌────────────────────────┐
        │  │     UI Tests (XCUITest) │  ← End-to-end; full app; expensive
        │  └────────────────────────┘
        │  ┌────────────────────────┐
        │  │   Integration Tests    │  ← Real components; mock network/disk
        │  └────────────────────────┘
        │  ┌────────────────────────┐
        │  │     Unit Tests         │  ← Pure logic; fast; isolated
        │  └────────────────────────┘
        │
        ▼  More, faster, more reliable
```

## Test Type Comparison

| Type | Speed | Isolation | Confidence | Fragility |
|------|-------|-----------|------------|----------|
| Unit | Very fast (< 1ms) | Complete | Logic only | Very low |
| Integration | Fast (< 100ms) | Partial | Component boundary | Low |
| UI (XCUITest) | Slow (1–10s) | None | End-to-end | High |
| Snapshot | Fast (< 50ms) | Partial | Visual regression | Medium |

## XCTest Quick Reference

```swift
// Test class structure
class MyTests: XCTestCase {
    var sut: SystemUnderTest!     // SUT = System Under Test

    override func setUp() async throws {
        sut = SystemUnderTest()
    }

    override func tearDown() async throws {
        sut = nil
    }

    func test_descriptiveName_expectedOutcome() {
        // Given / When / Then
    }
}

// Key assertion families
XCTAssertEqual(a, b)
XCTAssertNil(x)
XCTAssertTrue(condition)
XCTAssertThrowsError(try fn())
XCTAssertNoThrow(try fn())
await fulfillment(of: [expectation], timeout: 2)

// Performance
measure { /* code to benchmark */ }
```

## Relationship to Other Sections

- **Architecture**: Testable code requires separation of concerns — see [SOLID Principles](../06-architecture/solid-principles.md) and [Dependency Injection](../06-architecture/dependency-injection.md).
- **Concurrency**: Async test patterns for `async/await` and Combine — see [async/await](../03-concurrency/async-await.md).
- **Networking**: MockURLProtocol for network tests — see [Advanced Networking](../07-networking/advanced-networking.md).
- **Dependency Management**: Quick/Nimble, swift-snapshot-testing are SPM dependencies — see [Swift Package Manager](../10-dependency-management/swift-package-manager.md).
