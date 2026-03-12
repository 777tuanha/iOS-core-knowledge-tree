# Advanced Networking

## 1. Overview

Production iOS networking goes far beyond making a single request and decoding the response. Real apps must handle transient failures gracefully (retry with backoff), intercept requests for logging or authentication (URLProtocol), cache responses intelligently (URLCache), load paginated data efficiently, and keep the user experience coherent when the device goes offline. These patterns — retry strategies, request interceptors, caching policies, pagination, and offline handling — are what separate a robust networking layer from a fragile one, and they are a key indicator of senior engineering experience.

## 2. Simple Explanation

Imagine running a mail service for a mountain village. **Retry with backoff** is what the postman does when the road is blocked: waits a bit, tries again, waits longer if still blocked. **URLProtocol** is a checkpoint at the start of every road — it can inspect, log, or even redirect every letter before it leaves. **URLCache** is the village post office keeping copies of frequently-sent letters so the postman doesn't have to travel to the city for duplicates. **Pagination** is delivering a stack of letters in batches of 20 rather than dumping 10 000 at once. **Offline handling** is the postman noting which letters couldn't be delivered and retrying them automatically once the road reopens.

## 3. Deep iOS Knowledge

### Retry with Exponential Backoff and Jitter

A naive retry (immediate re-request on failure) causes **thundering herd** — many clients hammering a recovering server simultaneously. Exponential backoff spreads retries over time; jitter (random offset) prevents synchronised spikes.

```
attempt 1 → wait 1s  + jitter
attempt 2 → wait 2s  + jitter
attempt 3 → wait 4s  + jitter
attempt 4 → wait 8s  + jitter
```

**What to retry**: 5xx server errors, `URLError.timedOut`, `URLError.networkConnectionLost`, 429 (after `Retry-After` delay). **Never retry POST without an idempotency key** — it may create duplicate resources.

```swift
struct RetryPolicy {
    let maxAttempts: Int
    let baseDelay: TimeInterval          // seconds
    let maxDelay: TimeInterval

    func delay(for attempt: Int) -> TimeInterval {
        let exponential = baseDelay * pow(2.0, Double(attempt))
        let jitter = Double.random(in: 0...exponential * 0.3)
        return min(exponential + jitter, maxDelay)
    }
}
```

### URLProtocol — Request Interceptors

`URLProtocol` sits at the bottom of the URL loading system. Every `URLSession` request passes through registered `URLProtocol` subclasses before hitting the network. Uses: logging, mocking (unit tests with no real network), injecting auth headers, and throttle simulation.

**Registration**:
- Session-level (preferred): `config.protocolClasses = [MyProtocol.self]`
- Global (affects `URLSession.shared` — use carefully): `URLProtocol.registerClass(MyProtocol.self)`

A `URLProtocol` subclass must implement four methods:

| Method | Purpose |
|--------|---------|
| `canInit(with:)` | Return `true` if this protocol handles the request |
| `canonicalRequest(for:)` | Return (optionally modified) canonical request |
| `startLoading()` | Begin fetching; call client methods to deliver data/response/completion |
| `stopLoading()` | Cancel in-flight work |

### URLCache — HTTP Response Caching

`URLCache` is the system HTTP cache. It stores `CachedURLResponse` objects keyed by `URLRequest`. It respects `Cache-Control` response headers automatically when `requestCachePolicy = .useProtocolCachePolicy`.

**Key cache policies**:

| Policy | Behaviour |
|--------|-----------|
| `.useProtocolCachePolicy` | Honour `Cache-Control` and `Expires` (default) |
| `.returnCacheDataElseLoad` | Use cached data if present, ignoring freshness; fall back to network |
| `.returnCacheDataDontLoad` | Use cache only — fail if not cached (offline mode) |
| `.reloadIgnoringLocalCacheData` | Always fetch from network |
| `.reloadRevalidatingCacheData` | Conditional GET with `If-None-Match` / `If-Modified-Since` |

**Manual cache configuration**:
```swift
let cache = URLCache(
    memoryCapacity: 20 * 1_024 * 1_024,   // 20 MB
    diskCapacity:  150 * 1_024 * 1_024,   // 150 MB
    directory: nil                          // default system directory
)
let config = URLSessionConfiguration.default
config.urlCache = cache
config.requestCachePolicy = .useProtocolCachePolicy
```

**Manual invalidation**:
```swift
URLCache.shared.removeCachedResponse(for: request)
URLCache.shared.removeAllCachedResponses()
```

**Stale-while-revalidate**: Return cached (possibly stale) data immediately while fetching a fresh copy in the background, then update UI on completion. This pattern requires manual implementation since `URLCache` doesn't natively support it — read the cache, emit stale data, then fetch and update.

### Pagination Patterns

| Pattern | Key field | iOS use case |
|---------|-----------|-------------|
| Offset-based | `?offset=20&limit=20` | Simple list APIs |
| Page-based | `?page=3&per_page=20` | Admin/web-facing APIs |
| Cursor-based | `?after=eyJpZCI6NDJ9` | High-velocity feeds (Twitter, Instagram) |
| Link header | `Link: <url>; rel="next"` | GitHub API, RFC 5988 standard |

**Cursor-based** is preferred for production feeds: it remains stable under insertions/deletions, which cause offset-based results to skip or repeat items.

**AsyncSequence pagination**: model a paginated resource as an `AsyncSequence` — each call to `next()` fetches the next page transparently.

### Offline Handling with NWPathMonitor

`NWPathMonitor` (Network framework) replaces the legacy `Reachability` library. It provides real-time network path status including interface type (Wi-Fi, cellular, loopback).

```swift
import Network

class NetworkMonitor {
    private let monitor = NWPathMonitor()
    private(set) var isConnected = true

    func start() {
        monitor.pathUpdateHandler = { [weak self] path in
            self?.isConnected = path.status == .satisfied
        }
        monitor.start(queue: DispatchQueue(label: "NetworkMonitor"))
    }

    func stop() { monitor.cancel() }
}
```

**Request queuing for offline**: maintain a queue of pending operations; drain when connectivity is restored. For critical mutations (POST/PATCH), persist the queue to disk (UserDefaults, Core Data, or a JSON file in the Documents directory) so they survive app termination.

## 4. Practical Usage

```swift
import Foundation
import Network

// ── Retry with exponential backoff ────────────────────────────
struct RetryPolicy {
    let maxAttempts: Int
    let baseDelay: TimeInterval
    let maxDelay: TimeInterval

    static let `default` = RetryPolicy(maxAttempts: 3, baseDelay: 1.0, maxDelay: 30.0)

    func delay(for attempt: Int) -> TimeInterval {
        let exponential = baseDelay * pow(2.0, Double(attempt))
        let jitter = Double.random(in: 0...(exponential * 0.3))
        return min(exponential + jitter, maxDelay)
    }
}

extension URLSession {
    func data(for request: URLRequest, retryPolicy: RetryPolicy) async throws -> (Data, URLResponse) {
        var attempt = 0
        while true {
            do {
                let result = try await data(for: request)
                return result
            } catch {
                attempt += 1
                guard attempt < retryPolicy.maxAttempts, shouldRetry(error: error) else { throw error }
                let delay = retryPolicy.delay(for: attempt)
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            }
        }
    }

    private func shouldRetry(error: Error) -> Bool {
        guard let urlError = error as? URLError else { return false }
        return [.timedOut, .networkConnectionLost, .notConnectedToInternet]
            .contains(urlError.code)
    }
}

// Usage:
// let (data, response) = try await URLSession.shared.data(for: request, retryPolicy: .default)

// ── URLProtocol — logging interceptor ─────────────────────────
class LoggingURLProtocol: URLProtocol {
    private var dataTask: URLSessionDataTask?

    override class func canInit(with request: URLRequest) -> Bool {
        // Prevent infinite loop — mark handled requests to skip them
        return URLProtocol.property(forKey: "LoggingHandled", in: request) == nil
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        // Mark the request so this protocol doesn't intercept it again
        let mutableRequest = (request as NSURLRequest).mutableCopy() as! NSMutableURLRequest
        URLProtocol.setProperty(true, forKey: "LoggingHandled", in: mutableRequest)

        print("→ \(mutableRequest.httpMethod ?? "GET") \(mutableRequest.url?.absoluteString ?? "")")
        let start = Date()

        let session = URLSession(configuration: .default)
        dataTask = session.dataTask(with: mutableRequest as URLRequest) { [weak self] data, response, error in
            guard let self else { return }
            let elapsed = Date().timeIntervalSince(start)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            print("← \(status) (\(String(format: "%.2f", elapsed))s)")

            if let error {
                self.client?.urlProtocol(self, didFailWithError: error)
                return
            }
            if let response { self.client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .allowed) }
            if let data    { self.client?.urlProtocol(self, didLoad: data) }
            self.client?.urlProtocolDidFinishLoading(self)
        }
        dataTask?.resume()
    }

    override func stopLoading() { dataTask?.cancel() }
}

// Register per-session:
// let config = URLSessionConfiguration.default
// config.protocolClasses = [LoggingURLProtocol.self]
// let session = URLSession(configuration: config)

// ── URLProtocol — mock for unit tests ─────────────────────────
class MockURLProtocol: URLProtocol {
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

// In tests:
// MockURLProtocol.requestHandler = { _ in
//     let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: nil)!
//     return (response, mockData)
// }
// let config = URLSessionConfiguration.ephemeral
// config.protocolClasses = [MockURLProtocol.self]
// let session = URLSession(configuration: config)

// ── Cursor-based pagination with AsyncSequence ────────────────
struct Page<T: Decodable>: Decodable {
    let items: [T]
    let nextCursor: String?
}

struct PaginatedSequence<T: Decodable>: AsyncSequence {
    typealias Element = [T]

    private let makeRequest: (String?) -> URLRequest
    private let session: URLSession
    private let decoder: JSONDecoder

    init(session: URLSession = .shared, makeRequest: @escaping (String?) -> URLRequest) {
        self.session = session
        self.makeRequest = makeRequest
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    struct AsyncIterator: AsyncIteratorProtocol {
        private let sequence: PaginatedSequence<T>
        private var cursor: String?
        private var done = false

        init(_ sequence: PaginatedSequence<T>) { self.sequence = sequence }

        mutating func next() async throws -> [T]? {
            guard !done else { return nil }
            let request = sequence.makeRequest(cursor)
            let (data, _) = try await sequence.session.data(for: request)
            let page = try sequence.decoder.decode(Page<T>.self, from: data)
            cursor = page.nextCursor
            done = page.nextCursor == nil
            return page.items
        }
    }

    func makeAsyncIterator() -> AsyncIterator { AsyncIterator(self) }
}

// Usage — load all posts page by page:
// let pages = PaginatedSequence<Post> { cursor in
//     var components = URLComponents(string: "https://api.example.com/posts")!
//     if let cursor { components.queryItems = [URLQueryItem(name: "after", value: cursor)] }
//     return URLRequest(url: components.url!)
// }
// for try await posts in pages { display(posts) }

// ── NWPathMonitor — connectivity tracking ─────────────────────
final class NetworkMonitor {
    static let shared = NetworkMonitor()
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "com.app.network-monitor")

    @Published private(set) var isConnected: Bool = true
    @Published private(set) var connectionType: NWInterface.InterfaceType = .other

    private init() {}

    func start() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isConnected = path.status == .satisfied
                self?.connectionType = path.availableInterfaces
                    .first?.type ?? .other
            }
        }
        monitor.start(queue: queue)
    }

    func stop() { monitor.cancel() }
}

// ── Request queue for offline-first mutations ──────────────────
struct PendingRequest: Codable {
    let url: URL
    let method: String
    let headers: [String: String]
    let body: Data?
}

actor RequestQueue {
    private var pending: [PendingRequest] = []
    private let storageURL: URL

    init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        storageURL = docs.appendingPathComponent("pending_requests.json")
        load()
    }

    func enqueue(_ request: URLRequest) {
        let pending = PendingRequest(
            url: request.url!,
            method: request.httpMethod ?? "GET",
            headers: request.allHTTPHeaderFields ?? [:],
            body: request.httpBody
        )
        self.pending.append(pending)
        persist()
    }

    func flush(using session: URLSession) async {
        guard !pending.isEmpty else { return }
        var remaining: [PendingRequest] = []
        for item in pending {
            var request = URLRequest(url: item.url)
            request.httpMethod = item.method
            item.headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
            request.httpBody = item.body
            do {
                _ = try await session.data(for: request)
            } catch {
                remaining.append(item)   // keep failed requests for next flush
            }
        }
        pending = remaining
        persist()
    }

    private func persist() {
        let data = try? JSONEncoder().encode(pending)
        try? data?.write(to: storageURL)
    }

    private func load() {
        guard let data = try? Data(contentsOf: storageURL) else { return }
        pending = (try? JSONDecoder().decode([PendingRequest].self, from: data)) ?? []
    }
}

// ── Stale-while-revalidate pattern ────────────────────────────
actor StaleWhileRevalidateCache {
    private let urlCache: URLCache
    private let session: URLSession
    private let decoder: JSONDecoder

    init(session: URLSession = .shared) {
        self.session = session
        self.urlCache = URLCache(
            memoryCapacity: 20 * 1_024 * 1_024,
            diskCapacity: 100 * 1_024 * 1_024
        )
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    /// Returns cached value immediately (if available), then fetches fresh data.
    /// The caller receives two values via AsyncStream — first stale, then fresh.
    func fetch<T: Decodable>(_ type: T.Type, request: URLRequest) -> AsyncStream<T> {
        AsyncStream { continuation in
            Task {
                // 1. Emit stale cached value immediately
                if let cached = urlCache.cachedResponse(for: request),
                   let stale = try? decoder.decode(T.self, from: cached.data) {
                    continuation.yield(stale)
                }

                // 2. Fetch fresh value from network
                do {
                    let (data, response) = try await session.data(for: request)
                    let cached = CachedURLResponse(response: response, data: data)
                    urlCache.storeCachedResponse(cached, for: request)
                    if let fresh = try? decoder.decode(T.self, from: data) {
                        continuation.yield(fresh)
                    }
                } catch { /* network failure — stale data still displayed */ }

                continuation.finish()
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is exponential backoff and why should you add jitter?**

A: Exponential backoff is a retry strategy where the wait time between attempts doubles on each failure: 1s, 2s, 4s, 8s, up to a maximum cap. This prevents hammering a server that is already under stress. Without jitter (a random offset added to each delay), all clients that received the same error at the same time will retry in lockstep — every 1s, every 2s, etc. — creating periodic spikes that prevent the server from stabilising. Adding jitter spreads retries randomly across the delay window, smoothing server load and giving it a real chance to recover. In iOS, you should only retry idempotent operations (GET, PUT, DELETE) and 5xx errors / `URLError.timedOut`. Never automatically retry POST without an idempotency key.

**Q: What is URLProtocol and what can you use it for?**

A: `URLProtocol` is an abstract class that sits between `URLSession` and the actual network. Every URL request passes through a chain of registered `URLProtocol` subclasses. By subclassing it, you can: (1) **Log** all outgoing requests and incoming responses without modifying the call sites. (2) **Mock** network responses in unit tests — return fake `HTTPURLResponse` + `Data` without hitting the real network. (3) **Inject auth headers** at a single interception point rather than at every request builder. (4) **Throttle or simulate latency** for testing slow network conditions. The cleanest approach registers the protocol per-session via `URLSessionConfiguration.protocolClasses` to avoid polluting `URLSession.shared` and all other sessions.

### Hard

**Q: Compare cursor-based, offset-based, and page-based pagination. When should you use each?**

A: **Offset-based** (`?offset=40&limit=20`) is simple and supported by most SQL databases with `LIMIT`/`OFFSET`. The problem: if items are inserted or deleted while the user is scrolling, results shift — the user may see the same item twice (when an item is deleted, earlier items slide into the offset range) or skip an item. **Page-based** (`?page=3&per_page=20`) is semantically cleaner for human-readable UIs but has the same instability problem. **Cursor-based** uses an opaque pointer (e.g., an encoded item ID or timestamp) as the continuation token. The server returns items after that cursor, making results stable under insertions and deletions. It is the correct choice for real-time feeds (social, chat). The tradeoff: you cannot jump to an arbitrary page — you must iterate from the start. In iOS, model cursor pagination as an `AsyncSequence` that calls `next()` when the user scrolls near the bottom of the list, fetching and appending the next batch transparently.

**Q: How does `URLCache` work, and when does it NOT cache even when configured?**

A: `URLCache` stores `CachedURLResponse` objects keyed by `URLRequest`. It caches responses automatically when: the request is a GET, the response is HTTP 200–206/301/304/307/410, and `Cache-Control` allows caching (`max-age`, `public`, or no `no-store` directive). Common reasons caching fails even when configured: (1) The response includes `Cache-Control: no-store` or `Cache-Control: no-cache` — the system honours these. (2) The request cache policy is `.reloadIgnoringLocalCacheData` — always bypasses cache. (3) The request is not GET (POST/PUT responses are not cached). (4) The response is HTTPS but the server sends `Cache-Control: private` without a configured shared cache. (5) Memory + disk capacity are set to zero (the default for `.ephemeral` configuration). Manual control is available via `urlCache.storeCachedResponse(_:for:)` (write) and `urlCache.removeCachedResponse(for:)` (invalidate).

### Expert

**Q: How would you design an offline-first networking layer for an iOS app that must sync mutations when connectivity is restored?**

A: An offline-first layer has four components: (1) **Connectivity monitoring** using `NWPathMonitor` to track real-time path status. (2) **A request queue** — an `actor`-isolated data structure that enqueues failed mutations (POST/PATCH/DELETE with idempotency keys) and persists them to disk (so they survive app termination). (3) **A flush mechanism** — when connectivity is restored (`NWPathMonitor` fires `pathUpdateHandler` with `.satisfied`), drain the queue by replaying each persisted request. Remove succeeded requests; keep failed ones for the next attempt, with backoff. (4) **A stale-while-revalidate read layer** — return cached data from `URLCache` immediately for a fast UI, then fetch fresh data in the background and update the UI when it arrives. Critical correctness details: idempotency keys prevent duplicate mutations on retry; persisted requests must include all headers (auth token at enqueue time may differ from replay time — consider re-fetching the current token on flush); ordering matters for dependent mutations (e.g., create post then add comment — preserve order in the queue). For complex apps, `Core Data` or a local SQLite database as the source of truth (with background sync) is more robust than a raw request queue.

## 6. Common Issues & Solutions

**Issue: Retry logic retries a POST, creating duplicate server-side records.**

Solution: Only auto-retry idempotent methods (GET, PUT, DELETE, HEAD). For POST, use an **idempotency key**: generate a `UUID` per request and send it as a header (`Idempotency-Key: <UUID>`). The server deduplicates requests with the same key. On retry, send the same UUID — the server detects the duplicate and returns the original response without creating a new record.

**Issue: URLProtocol interceptor causes an infinite loop of requests.**

Solution: The interceptor creates a new internal `URLSession` to forward the request, which triggers the same `URLProtocol` again. Fix: mark the request as already handled using `URLProtocol.setProperty(true, forKey: "handled", in: mutableRequest)` before forwarding, and return `false` in `canInit(with:)` for requests with that property set.

**Issue: NWPathMonitor reports `.satisfied` but HTTPS requests still fail.**

Solution: `.satisfied` means a network path exists, not that the specific server is reachable (e.g., the user is connected to a captive portal Wi-Fi that hasn't been authenticated). `NWPathMonitor` cannot detect reachability to a specific host. Handle `URLError.notConnectedToInternet` and `URLError.networkConnectionLost` errors at the request level; treat `NWPathMonitor` as a hint to update UI, not as a guarantee of end-to-end connectivity.

**Issue: Cached responses are returned for API endpoints that should always reflect the latest data.**

Solution: Set `requestCachePolicy = .reloadIgnoringLocalCacheData` for mutation-sensitive endpoints, or have the server send `Cache-Control: no-store` on responses that must not be cached. Alternatively, manually invalidate the cache entry after a successful write operation: `URLCache.shared.removeCachedResponse(for: affectedRequest)`. For fine-grained control, use a custom `URLCache` subclass that applies different policies based on the URL path.

## 7. Related Topics

- [URLSession](urlsession.md) — the networking primitives that retry, cache, and interceptor patterns wrap
- [HTTP & REST Basics](http-rest-basics.md) — idempotency, status codes, Retry-After header
- [Codable & JSON](codable-json.md) — decoding paginated response bodies
- [async/await](../03-concurrency/async-await.md) — retry loops and AsyncSequence pagination use structured concurrency
- [Data Persistence](../08-data-persistence/index.md) — offline queues and local caches bridge networking and persistence
