# Structural Patterns

## 1. Overview

Structural patterns deal with **how classes and objects are composed** to form larger structures — making incompatible interfaces compatible, adding behaviour without subclassing, simplifying complex subsystems, and treating individual objects and compositions uniformly. The four GoF structural patterns most relevant to iOS are: **Adapter** (wrap a third-party or legacy interface to match what your code expects), **Decorator** (add behaviour by wrapping, without changing the wrapped object), **Facade** (provide a simple interface to a complex subsystem), and **Composite** (treat a single item and a collection of items with the same interface). These patterns are prominent throughout UIKit and Swift — `UIView` is a Composite (a view contains views), `UINavigationController` is a Facade over the navigation stack, and third-party SDK wrappers are typically Adapters.

## 2. Simple Explanation

**Adapter**: you buy a US power adapter that converts a European socket into a US plug. The wall socket interface hasn't changed; the device interface hasn't changed; the adapter makes them compatible. **Decorator**: you order a plain coffee, then add a sleeve (warmth), a lid (spill-proof), and a cup holder (grip) — each is a wrapper that adds one capability without altering the coffee itself. **Facade**: a hotel concierge is a facade over the hotel's complex operations (kitchen, housekeeping, transport) — you ask for "dinner and a taxi" and the concierge coordinates everything; you don't interact with each department directly. **Composite**: a file system where a folder and a single file both respond to "get size" — you treat them identically whether you're dealing with one file or a folder containing thousands.

## 3. Deep iOS Knowledge

### Adapter

The Adapter pattern converts one interface into another. In iOS, this most commonly appears when:
- Wrapping a third-party SDK to depend on your own protocol (so you can swap SDKs without changing call sites).
- Making an Objective-C delegate into a Swift `AsyncSequence` or Combine publisher.
- Adapting a callback-based API to `async/await`.

Swift's `withCheckedContinuation` / `withCheckedThrowingContinuation` is the idiomatic async adapter.

### Decorator

The Decorator pattern adds behaviour by wrapping an object that conforms to the same protocol. Each decorator forwards calls to the wrapped object and adds its own processing. This is more flexible than subclassing — decorators can be combined in any order at runtime.

iOS examples: `UIScrollView` decorates `UIView` with scrolling; `UIButton` decorates `UIControl` with press handling. In networking: `LoggingURLProtocol` wraps `URLSession`, adding logging before forwarding.

### Facade

A Facade provides a simplified API over a complex subsystem of multiple classes. It hides the subsystem's internals from the client — the client only knows the facade.

iOS examples: `UINavigationController` (facade over a stack + transitions), `AVPlayer` (facade over audio session + item + layer pipeline), `URLSession` (facade over TCP connection + TLS + HTTP parsing).

### Composite

The Composite pattern lets you treat individual objects and compositions of those objects through the same interface. A node can be a leaf or a container of more nodes.

iOS examples: `UIView` (a view is a composite of subviews — `addSubview`, `subviews`, `removeFromSuperview` work identically on `UIView` and `UIStackView`). SwiftUI's `View` protocol — `VStack` and `Text` both conform to `View`; a `VStack` is a composite of `View`s.

## 4. Practical Usage

```swift
import Foundation
import UIKit
import Combine

// ── Adapter: Wrap a callback API as async ─────────────────────
protocol LocationService {
    func currentLocation() async throws -> Coordinate
}

struct Coordinate { let lat: Double; let lon: Double }

// Existing third-party SDK with callback API
final class LegacyLocationSDK {
    func fetchLocation(completion: @escaping (Double, Double, Error?) -> Void) {
        // … SDK implementation
    }
}

// Adapter wraps LegacyLocationSDK and conforms to LocationService
final class LocationServiceAdapter: LocationService {
    private let sdk = LegacyLocationSDK()

    func currentLocation() async throws -> Coordinate {
        try await withCheckedThrowingContinuation { continuation in
            sdk.fetchLocation { lat, lon, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: Coordinate(lat: lat, lon: lon))
                }
            }
        }
    }
}

// ── Adapter: Combine publisher wrapping delegate ──────────────
protocol ImageLoader {
    var imagePublisher: AnyPublisher<UIImage, Error> { get }
}

// Wraps a third-party image loader that uses a delegate
final class SDKImageLoaderAdapter: NSObject, ImageLoader {
    private let subject = PassthroughSubject<UIImage, Error>()
    lazy var imagePublisher: AnyPublisher<UIImage, Error> = subject.eraseToAnyPublisher()

    func load(url: URL) {
        // Call SDK, forward to subject in its callback
        // sdk.loadImage(url, delegate: self)
    }
    // In delegate callback:
    // subject.send(image) / subject.send(completion: .failure(error))
}

// ── Decorator: Logging network layer ──────────────────────────
protocol NetworkClient {
    func fetch(_ request: URLRequest) async throws -> Data
}

final class URLSessionNetworkClient: NetworkClient {
    func fetch(_ request: URLRequest) async throws -> Data {
        let (data, _) = try await URLSession.shared.data(for: request)
        return data
    }
}

// Decorator adds logging; wraps any NetworkClient
final class LoggingNetworkClient: NetworkClient {
    private let wrapped: NetworkClient

    init(wrapping client: NetworkClient) { wrapped = client }

    func fetch(_ request: URLRequest) async throws -> Data {
        let start = CFAbsoluteTimeGetCurrent()
        print("[Network] → \(request.httpMethod ?? "GET") \(request.url?.path ?? "")")
        do {
            let data = try await wrapped.fetch(request)
            let ms = (CFAbsoluteTimeGetCurrent() - start) * 1000
            print("[Network] ← \(data.count) bytes in \(String(format: "%.0f", ms))ms")
            return data
        } catch {
            print("[Network] ✗ \(error)")
            throw error
        }
    }
}

// Stack decorators at composition root:
// let client: NetworkClient = LoggingNetworkClient(
//     wrapping: RetryingNetworkClient(
//         wrapping: URLSessionNetworkClient()
//     )
// )

// ── Decorator: Retrying network client ────────────────────────
final class RetryingNetworkClient: NetworkClient {
    private let wrapped: NetworkClient
    private let maxRetries: Int

    init(wrapping client: NetworkClient, maxRetries: Int = 3) {
        wrapped = client; self.maxRetries = maxRetries
    }

    func fetch(_ request: URLRequest) async throws -> Data {
        var lastError: Error?
        for attempt in 1...maxRetries {
            do {
                return try await wrapped.fetch(request)
            } catch {
                lastError = error
                if attempt < maxRetries {
                    try? await Task.sleep(nanoseconds: UInt64(pow(2.0, Double(attempt)) * 500_000_000))
                }
            }
        }
        throw lastError!
    }
}

// ── Facade: Analytics Facade ──────────────────────────────────
// Hides Firebase, Mixpanel, and internal logging behind one API
final class AnalyticsFacade {
    private let firebase: FirebaseAnalyticsClient
    private let mixpanel: MixpanelClient
    private let internalLogger: InternalEventLogger

    init() {
        firebase = FirebaseAnalyticsClient()
        mixpanel = MixpanelClient()
        internalLogger = InternalEventLogger()
    }

    func logEvent(_ event: AppEvent) {
        firebase.log(name: event.rawValue, parameters: event.parameters)
        mixpanel.track(event: event.rawValue, properties: event.parameters)
        internalLogger.record(event)
    }
}

// Call site never knows about the three backends:
// AnalyticsFacade.shared.logEvent(.feedLoaded(postCount: posts.count))

// ── Composite: SwiftUI View tree ──────────────────────────────
// SwiftUI's View protocol is itself a composite pattern example
// Both Text and VStack conform to View; they're used identically

struct CompositeExampleView: View {
    var body: some View {
        VStack {       // Composite — contains child Views
            Text("Header")     // Leaf
            HStack {           // Composite
                Text("Left")   // Leaf
                Text("Right")  // Leaf
            }
        }
    }
}

// Custom composite: a view hierarchy that renders recursively
indirect enum MenuItem {
    case leaf(title: String, action: () -> Void)
    case group(title: String, children: [MenuItem])
}

struct MenuView: View {
    let item: MenuItem

    var body: some View {
        switch item {
        case .leaf(let title, let action):
            Button(title) { action() }
        case .group(let title, let children):
            DisclosureGroup(title) {
                ForEach(children.indices, id: \.self) { i in
                    MenuView(item: children[i])   // recursive composite
                }
            }
        }
    }
}

// Placeholder types for compilation:
final class FirebaseAnalyticsClient { func log(name: String, parameters: [String: Any]) {} }
final class MixpanelClient { func track(event: String, properties: [String: Any]) {} }
final class InternalEventLogger { func record(_ event: AppEvent) {} }
enum AppEvent: String {
    case feedLoaded
    var parameters: [String: Any] { [:] }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the Adapter pattern and give an example from iOS SDK?**

A: The Adapter pattern converts the interface of a class into another interface that clients expect. It lets classes with incompatible interfaces work together. iOS SDK example: `UITableViewDiffableDataSource` adapts the data model (an `NSDiffableDataSourceSnapshot` of hashable items) to the `UITableViewDataSource` protocol that `UITableView` requires — you don't need to implement `numberOfSections` and `cellForRow` because the diffable data source adapts your model to those methods. Another example: `withCheckedContinuation` adapts callback-based APIs to Swift's `async/await` — the continuation is an adapter between the completion handler interface and the suspension-based async interface.

**Q: What is the Facade pattern? How does `AVPlayer` use it?**

A: A Facade provides a simplified, unified interface to a complex subsystem of multiple classes, hiding the subsystem's complexity from clients. `AVPlayer` is a facade over: `AVURLAsset` (the media source), `AVPlayerItem` (decoding pipeline, buffering state, tracks), `AVPlayerLayer` (the CALayer for video rendering), `AVAudioSession` (audio routing), and the underlying `AudioToolbox` and `VideoToolbox` frameworks. Instead of managing all of these individually, clients interact with just `AVPlayer.play()`, `AVPlayer.pause()`, and `AVPlayer.rate` — the player facade coordinates the subsystem internally. The Facade pattern is appropriate when you have a complex subsystem that clients should not need to understand in full to use.

### Hard

**Q: How does the Decorator pattern differ from subclassing for adding behaviour, and when should you prefer it?**

A: Subclassing adds behaviour at compile time — a `LoggingViewController: UIViewController` always has logging; you cannot create a non-logging version of the same class without a separate type. Decoration adds behaviour at runtime — you compose `LoggingNetworkClient(wrapping: URLSessionNetworkClient())` for production and `URLSessionNetworkClient()` alone for tests. Decorators follow the open/closed principle: you extend behaviour by adding a new decorator class rather than modifying existing classes. Prefer decorators over subclassing when: (1) you need to combine multiple behaviours independently (Logging + Retry + Caching on any `NetworkClient` implementation, in any combination); (2) you're decorating a class from a library you don't control (you can't subclass a `final` class); (3) the decorating logic is orthogonal to the core logic and should be reusable across multiple types. Prefer subclassing only when you need access to `protected` (internal) state of the parent class that isn't exposed through the protocol.

**Q: Describe a real-world use of the Composite pattern in a SwiftUI or UIKit app.**

A: In UIKit, `UIView` is the canonical Composite — both a leaf `UILabel` and a container `UIStackView` respond to `addSubview`, `removeFromSuperview`, `frame`, `layoutIfNeeded`, and `drawHierarchy(in:afterScreenUpdates:)` through the same `UIView` interface. A render pass, layout pass, or hit-test recursion operates uniformly on the entire tree. In SwiftUI, the `View` protocol is the composite interface — both a `Text` leaf and a `VStack` container conform to `View`, allowing the layout engine to recursively compute sizes and positions without caring whether a node is a leaf or a container. In app code, the Composite pattern is useful for: (1) Document/outline structures (folders + files, each conforming to `DocumentNode`). (2) Rendering pipelines where a `CompositeRenderer` calls `render(in:)` on each child. (3) Validation rule trees where a `CompositeRule` validates by checking all child rules.

### Expert

**Q: Design a networking stack that composes Logging, Retry, Caching, and Authentication decorators, and explain how to order them.**

A: Stack from innermost to outermost: `URLSessionNetworkClient` → `AuthDecorator` → `CachingDecorator` → `RetryDecorator` → `LoggingDecorator`. Ordering rationale: (1) **Auth decorator wraps URLSession** — it injects the `Authorization` header into the request and handles 401 responses by refreshing the token and retrying once. It must be inside the cache to ensure that only authenticated requests are cached, and inside retry to ensure the token refresh happens as part of the retry logic. (2) **Caching decorator** — wraps the authenticated client. A cache hit short-circuits all downstream decorators (no network call, no logging of the real request). Cache storage uses the authenticated response. (3) **Retry decorator** — wraps the cache. A retry attempts the cache decorator again — if the first attempt gets a network error and the cache has a stale entry, the cache could serve the stale response on retry. Configure retry to not retry on 401 (handled by AuthDecorator) or 404 (not retryable). (4) **Logging decorator** is outermost — it sees the final request (with auth headers) and the final response (from cache or network). This ensures the log accurately reflects what the app sent and received. Compose at the app's dependency container: `let client: NetworkClient = LoggingNetworkClient(wrapping: RetryingNetworkClient(wrapping: CachingNetworkClient(wrapping: AuthenticatingNetworkClient(wrapping: URLSessionNetworkClient()))))`

## 6. Common Issues & Solutions

**Issue: Decorator causes a stack overflow — the decorator wraps itself.**

Solution: Each decorator must wrap a different instance. A common mistake: `let client = LoggingNetworkClient(wrapping: client)` where `client` is the same variable (wrapping itself in a cycle). Build the chain with explicit intermediates: `let base = URLSessionNetworkClient(); let authenticated = AuthNetworkClient(wrapping: base); let logged = LoggingNetworkClient(wrapping: authenticated)`.

**Issue: Facade hides errors from the subsystem, making debugging harder.**

Solution: The Facade should not swallow errors silently. Either let errors propagate (throws or `Result`), or translate them into a facade-level error enum that preserves the cause. Use `os_log` inside the facade for diagnostic logging without exposing internal types to the caller. If needed, provide an optional `debugMode` on the facade that exposes subsystem details.

## 7. Related Topics

- [Creational Patterns](creational-patterns.md) — factories that produce adaptable types
- [Behavioral Patterns](behavioral-patterns.md) — Strategy pattern for interchangeable algorithms
- [iOS-Specific Patterns](ios-patterns.md) — Delegate as a structural callback pattern
- [Advanced Networking](../07-networking/advanced-networking.md) — LoggingURLProtocol as Adapter/Decorator
