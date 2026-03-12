# URLSession

## 1. Overview

`URLSession` is Apple's high-level networking API, providing a unified interface for HTTP/HTTPS requests, file downloads and uploads, WebSocket connections, and background transfers. It manages connection pooling, TLS negotiation, authentication challenges, cookies, caching, and HTTP/2 multiplexing automatically. In modern Swift it integrates natively with async/await via `data(for:)`, `download(for:)`, and `upload(for:from:)`. Understanding URLSession's architecture — configurations, task types, delegate callbacks, and background sessions — is foundational for all iOS networking work.

## 2. Simple Explanation

`URLSession` is like a courier company. You give the company a delivery request (`URLRequest`) — the address (URL), the package type (method), and any customs forms (headers). The company handles all the logistics: finding the address (DNS), opening a road (TCP connection), securing the truck (TLS), and delivering the package. When delivery is complete, the company calls you back (completion handler or async return) with the reply. You can have one courier company per app (`URLSession.shared`) or create your own with custom rules (`URLSessionConfiguration`).

## 3. Deep iOS Knowledge

### URLSession Architecture

```
URLSession
  ├── URLSessionConfiguration  (session-level settings)
  ├── URLSessionDelegate       (session-level events: auth, metrics)
  └── URLSessionTask subclasses:
        ├── URLSessionDataTask       (data in memory)
        ├── URLSessionDownloadTask   (file to disk, resumable)
        ├── URLSessionUploadTask     (data/file → server)
        ├── URLSessionStreamTask     (TCP/TLS stream)
        └── URLSessionWebSocketTask  (WebSocket)
```

### URLSessionConfiguration

The configuration controls session-level behaviour and is set once at creation — it cannot be changed after the session is initialised.

| Configuration type | Description |
|-------------------|-------------|
| `.default` | Disk-persistent cache, cookies, credentials |
| `.ephemeral` | No persistence — cache/cookies/credentials in memory only; cleared on session release |
| `.background(withIdentifier:)` | Transfers continue after app is suspended or terminated |

Key properties:
```swift
let config = URLSessionConfiguration.default
config.timeoutIntervalForRequest = 30      // per-request timeout (default 60s)
config.timeoutIntervalForResource = 300    // total resource timeout
config.waitsForConnectivity = true         // queue request until network available
config.httpAdditionalHeaders = ["User-Agent": "MyApp/1.0"]  // added to every request
config.urlCache = URLCache(memoryCapacity: 20_000_000, diskCapacity: 100_000_000)
config.requestCachePolicy = .useProtocolCachePolicy  // honour Cache-Control
config.httpMaximumConnectionsPerHost = 6   // limit concurrent connections
```

### Task Types

**URLSessionDataTask** — fetches data directly into memory. Standard for API calls.

**URLSessionDownloadTask** — writes response to a temporary file. Essential for large files (video, documents) because it doesn't hold the entire file in memory. Supports **resumable downloads** with resume data:
```swift
let resumeData = task.cancel(byProducingResumeData:)
// later:
let resumedTask = session.downloadTask(withResumeData: resumeData)
```

**URLSessionUploadTask** — sends data or a file to the server. Preferred over a data task with a body for large uploads because it streams the body rather than loading it into memory.

**URLSessionWebSocketTask** — bidirectional WebSocket connection. Supports `send(_:)`, `receive()`, and `sendPing(pongReceiveHandler:)`.

### URLRequest Configuration

```swift
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.httpBody = try JSONEncoder().encode(body)
request.timeoutInterval = 15           // overrides session-level timeout for this request
request.cachePolicy = .reloadIgnoringLocalCacheData   // bypass cache
```

### async/await API (iOS 15+)

```swift
// Data task
let (data, response) = try await URLSession.shared.data(for: request)

// Download task
let (localURL, response) = try await URLSession.shared.download(for: request)

// Upload task
let (data, response) = try await URLSession.shared.upload(for: request, from: bodyData)

// Bytes (streaming)
let (asyncBytes, response) = try await URLSession.shared.bytes(for: request)
for try await byte in asyncBytes { /* process byte by byte */ }
```

All async methods throw `URLError` on network failure. They are automatically cancelled when the enclosing `Task` is cancelled — no `AnyCancellable` needed.

### Completion Handler API (pre-iOS 15 / callback style)

```swift
let task = URLSession.shared.dataTask(with: request) { data, response, error in
    if let error { /* handle */ return }
    guard let data, let response else { return }
    // validate + decode
}
task.resume()   // tasks start suspended — must call resume()
```

**Important**: Completion handlers are called on an arbitrary background queue — always dispatch UI updates to the main queue.

### URLSession Delegate

For fine-grained control: authentication, upload progress, redirect handling, metrics.

```swift
class NetworkDelegate: NSObject, URLSessionDataDelegate, URLSessionTaskDelegate {

    // Authentication challenge (basic auth, client certificate)
    func urlSession(_ session: URLSession,
                    task: URLSessionTask,
                    didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        // Certificate pinning happens here
        completionHandler(.performDefaultHandling, nil)
    }

    // Upload/download progress
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    didSendBodyData bytesSent: Int64,
                    totalBytesSent: Int64,
                    totalBytesExpectedToSend: Int64) {
        let progress = Double(totalBytesSent) / Double(totalBytesExpectedToSend)
        print("Upload progress: \(progress)")
    }

    // HTTP redirect
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(request)   // nil to block redirect
    }
}
```

### Background Sessions

Background sessions allow transfers to continue after the app is suspended or terminated by the OS.

```swift
// Create a background session with a unique identifier
let config = URLSessionConfiguration.background(withIdentifier: "com.myapp.uploads")
config.isDiscretionary = true          // allow OS to schedule at optimal time
config.sessionSendsLaunchEvents = true // wake app when transfer completes
let bgSession = URLSession(configuration: config, delegate: self, delegateQueue: nil)

// In AppDelegate — handle background session completion
func application(_ application: UIApplication,
                 handleEventsForBackgroundURLSession identifier: String,
                 completionHandler: @escaping () -> Void) {
    backgroundCompletionHandler = completionHandler
}

// In URLSessionDelegate
func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
    DispatchQueue.main.async {
        backgroundCompletionHandler?()   // tell system all events are processed
        backgroundCompletionHandler = nil
    }
}
```

### Metrics

`URLSessionTaskMetrics` provides detailed timing breakdowns: DNS lookup, TCP connect, TLS handshake, request sent, response start, response end. Accessed via `URLSessionTaskDelegate.urlSession(_:task:didFinishCollecting:)`.

### URLSession.shared vs Custom Session

| | URLSession.shared | Custom URLSession |
|--|---|---|
| Configuration | Cannot change | Full control |
| Delegate | None | Custom delegate possible |
| Background transfers | Not supported | Supported |
| Memory | Shared cache | Isolated cache |
| Best for | Simple one-off requests | Production networking layers |

## 4. Practical Usage

```swift
import Foundation

// ── Generic async network client ──────────────────────────────
actor NetworkClient {
    private let session: URLSession
    private let decoder: JSONDecoder

    init(configuration: URLSessionConfiguration = .default) {
        self.session = URLSession(configuration: configuration)
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.decoder.dateDecodingStrategy = .iso8601
    }

    func fetch<T: Decodable>(_ type: T.Type, request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    @discardableResult
    func send(request: URLRequest) async throws -> Data {
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        return data
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}

// ── Download task with progress ────────────────────────────────
class FileDownloader: NSObject, URLSessionDownloadDelegate {
    private lazy var session = URLSession(
        configuration: .default,
        delegate: self,
        delegateQueue: nil
    )
    var onProgress: ((Double) -> Void)?
    var onComplete: ((URL) -> Void)?

    func download(url: URL) {
        let task = session.downloadTask(with: url)
        task.resume()
    }

    // URLSessionDownloadDelegate
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didFinishDownloadingTo location: URL) {
        // Move temp file to permanent location before returning
        let dest = FileManager.default.temporaryDirectory.appendingPathComponent(
            location.lastPathComponent
        )
        try? FileManager.default.moveItem(at: location, to: dest)
        DispatchQueue.main.async { self.onComplete?(dest) }
    }

    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                    didWriteData bytesWritten: Int64,
                    totalBytesWritten: Int64,
                    totalBytesExpectedToWrite: Int64) {
        guard totalBytesExpectedToWrite > 0 else { return }
        let progress = Double(totalBytesWritten) / Double(totalBytesExpectedToWrite)
        DispatchQueue.main.async { self.onProgress?(progress) }
    }
}

// ── WebSocket ──────────────────────────────────────────────────
class ChatWebSocket {
    private var task: URLSessionWebSocketTask?

    func connect(to url: URL) {
        task = URLSession.shared.webSocketTask(with: url)
        task?.resume()
        receiveNext()
    }

    func send(text: String) {
        task?.send(.string(text)) { error in
            if let error { print("Send error: \(error)") }
        }
    }

    private func receiveNext() {
        task?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text): print("Received: \(text)")
                case .data(let data): print("Received data: \(data.count) bytes")
                @unknown default: break
                }
                self?.receiveNext()   // queue next receive
            case .failure(let error):
                print("Receive error: \(error)")
            }
        }
    }

    func disconnect() {
        task?.cancel(with: .normalClosure, reason: nil)
    }
}

// ── Background download ────────────────────────────────────────
class BackgroundDownloadManager: NSObject, URLSessionDownloadDelegate {
    static let sessionIdentifier = "com.myapp.background-download"
    var backgroundCompletionHandler: (() -> Void)?

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.background(withIdentifier: Self.sessionIdentifier)
        config.isDiscretionary = false          // download ASAP, not at system's convenience
        config.sessionSendsLaunchEvents = true
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    func startDownload(url: URL) {
        let task = session.downloadTask(with: url)
        task.earliestBeginDate = nil            // start immediately
        task.resume()
    }

    func urlSession(_ session: URLSession,
                    downloadTask: URLSessionDownloadTask,
                    didFinishDownloadingTo location: URL) {
        // Store file permanently — temp file is deleted after this returns
        let dest = /* permanent URL */ location
        try? FileManager.default.copyItem(at: location, to: dest)
    }

    func urlSessionDidFinishEvents(forBackgroundURLSession session: URLSession) {
        DispatchQueue.main.async {
            self.backgroundCompletionHandler?()
            self.backgroundCompletionHandler = nil
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `URLSessionDataTask`, `URLSessionDownloadTask`, and `URLSessionUploadTask`?**

A: `URLSessionDataTask` fetches the response body directly into an in-memory `Data` object — appropriate for API calls where the response is small enough to fit comfortably in RAM. `URLSessionDownloadTask` writes the response to a temporary file on disk as it arrives — appropriate for large files (video, audio, large documents) because it never holds the full content in memory. Crucially, download tasks support **resumable downloads**: if interrupted, you can obtain resume data and restart from where you left off. `URLSessionUploadTask` sends a request body from a file or data stream — like a data task but designed for sending large bodies without loading them entirely into memory.

**Q: Why must you call `task.resume()` after creating a URLSessionTask?**

A: All `URLSessionTask` objects are created in a **suspended** state. This design allows you to configure the task (set priority, description, etc.) before it begins work, and to create tasks ahead of time and start them later. If `resume()` is not called, the task never starts and no network request is sent. The completion handler is never called. This is a common oversight when using the callback API — the async/await API (`session.data(for:)`) handles this automatically and does not require a `resume()` call.

### Hard

**Q: When should you use a custom `URLSession` instead of `URLSession.shared`?**

A: `URLSession.shared` is convenient but has limitations: you cannot change its configuration, it uses a shared cache and cookie store, it has no delegate (so no authentication handling, progress callbacks, or metrics), and it cannot perform background transfers. Use a custom session when: (1) you need a background configuration for downloads/uploads that survive app suspension; (2) you need a delegate for authentication challenges (certificate pinning, client certificates); (3) you need upload/download progress; (4) you need an ephemeral session (privacy — no caching, no cookies, credentials cleared on release); (5) you need custom timeout intervals, cache policies, or additional headers applied session-wide.

**Q: How does `waitsForConnectivity` change URLSession's behaviour?**

A: By default (`waitsForConnectivity = false`), if the network is unavailable when a task starts, it fails immediately with `URLError.notConnectedToInternet`. With `waitsForConnectivity = true`, URLSession queues the request and waits for connectivity before starting the task. When connectivity is restored, the task automatically begins. The delegate callback `urlSession(_:taskIsWaitingForConnectivity:)` fires so you can update UI (show "waiting for network" state). This is particularly useful for foreground tasks where you want to automatically retry when connectivity returns without writing retry logic yourself.

### Expert

**Q: Describe how background URLSession transfers work when the app is terminated and how to correctly handle the completion.**

A: When an app with a background URLSession is terminated by the OS (memory pressure, user swipe), in-flight background tasks continue running in a system-managed process. When a task completes, the OS relaunches the app in the background and calls `application(_:handleEventsForBackgroundURLSession:completionHandler:)`. The app must store the completion handler, recreate the background `URLSession` with the same identifier (matching the one delivered), and wait for all delegate callbacks to fire. `URLSessionDelegate.urlSessionDidFinishEvents(forBackgroundURLSession:)` fires when all pending events have been delivered. At that point, you call the stored completion handler — signalling to the OS that your app has finished processing and it can take a new snapshot. Calling the handler too early or forgetting it causes issues: the OS may not correctly snapshot the app state for the background task.

## 6. Common Issues & Solutions

**Issue: Completion handler is never called.**

Solution: Forgot to call `task.resume()`. Every URLSessionTask is created suspended.

**Issue: UI update from completion handler causes purple runtime warning.**

Solution: URLSession delivers completion callbacks on a background queue. Wrap UI updates in `DispatchQueue.main.async { }` or use `await MainActor.run { }` in async context.

**Issue: Task is not cancelled when the owning object is deallocated.**

Solution: Store the `URLSessionTask` as a property and call `task?.cancel()` in `deinit`. With async/await, cancel the enclosing `Task` handle. With Combine, cancel the `AnyCancellable`.

**Issue: Background session events delivered after app relaunch but delegate is nil.**

Solution: You must recreate the `URLSession` with the same identifier before `application(_:handleEventsForBackgroundURLSession:completionHandler:)` returns. Store the session as an app-level singleton. The OS will deliver buffered events to the delegate as soon as the session is recreated.

## 7. Related Topics

- [HTTP & REST Basics](http-rest-basics.md) — HTTP methods, status codes, headers
- [Codable & JSON](codable-json.md) — decoding the Data returned by URLSession
- [Advanced Networking](advanced-networking.md) — URLCache, retry, URLProtocol interceptors
- [async/await](../03-concurrency/async-await.md) — URLSession's async API uses structured concurrency
- [Combine Networking](../05-reactive-programming/combine-networking.md) — dataTaskPublisher
