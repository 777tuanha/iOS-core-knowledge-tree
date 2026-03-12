# Combine Networking

## 1. Overview

`URLSession` provides a first-party Combine integration via `dataTaskPublisher(for:)`, returning a publisher that emits a `(Data, URLResponse)` tuple or a `URLError`. Combined with Combine's operators (`map`, `decode`, `retry`, `catch`, `tryMap`), this enables composable, declarative networking pipelines. Combine networking is most valuable when you need to coordinate multiple requests, apply retry/recovery logic, or integrate network responses directly into a reactive data binding pipeline.

## 2. Simple Explanation

A Combine networking pipeline is like a assembly line. At one end, a `dataTaskPublisher` is the factory worker who fetches raw materials (Data). Operators are the quality control stations: one checks the HTTP status code, one extracts the materials, one converts raw materials into a finished product (decodes JSON into a Swift type). The final subscriber receives the finished product. If any station fails, the error handling path kicks in — like a defect response process.

## 3. Deep iOS Knowledge

### dataTaskPublisher

`URLSession.dataTaskPublisher(for: url)` returns `URLSession.DataTaskPublisher`:
- **Output**: `(data: Data, response: URLResponse)`
- **Failure**: `URLError`

The publisher creates a `URLSessionDataTask` when subscribed and cancels it when the subscription is cancelled.

### Standard Networking Pipeline

```swift
URLSession.shared
    .dataTaskPublisher(for: url)             // fetch
    .tryMap { data, response in              // validate HTTP status
        guard let http = response as? HTTPURLResponse,
              (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }
    .decode(type: T.self, decoder: JSONDecoder())  // decode JSON
    .receive(on: DispatchQueue.main)         // deliver on main thread
    .eraseToAnyPublisher()
```

### tryMap vs map

- `map` — synchronous, non-throwing transform. Cannot introduce errors into the pipeline.
- `tryMap` — synchronous transform that can `throw`. On throw, the publisher fails with the thrown error. This is how you validate HTTP status codes and convert them to pipeline errors.

After `tryMap`, the `Failure` type widens from `URLError` to `Error`.

### decode

`decode(type:decoder:)` decodes `Data` into any `Decodable` type using the specified `Decoder`. On decoding failure it emits a `DecodingError`. The `Failure` type must be `Error` (or `DecodingError`) — incompatible with `Never` failure pipelines.

### Error Handling Patterns

**Retry**: Re-subscribe to the upstream publisher on failure. Creates a new request:
```swift
.retry(3)
```

**catch with fallback**: On failure, switch to a fallback publisher:
```swift
.catch { error in
    Just(cachedData)   // return cached data on failure
}
```

**replaceError**: Absorb the error and emit a default value:
```swift
.replaceError(with: [])
```

**mapError**: Transform the error type without recovering:
```swift
.mapError { AppError.network($0) }
```

### Scheduling

Network responses arrive on a background thread. Add `receive(on: DispatchQueue.main)` before any UI-bound operator or subscriber. Do not place `receive(on:)` before `decode` — decoding on a background thread is fine and avoids main-thread contention.

### Request Configuration

For POST/PUT/DELETE requests, use `URLRequest`:
```swift
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.httpBody = try? JSONEncoder().encode(body)

URLSession.shared.dataTaskPublisher(for: request)
```

### Chaining Requests (flatMap)

```swift
// Step 1: fetch token, Step 2: fetch user with token
tokenPublisher
    .flatMap { token in
        userPublisher(token: token)
    }
```

### Parallel Requests (zip / merge)

```swift
// Wait for both
Publishers.Zip(userPublisher, postsPublisher)
    .sink { user, posts in configure(user: user, posts: posts) }
```

### Comparison: Combine vs async/await for networking

| Aspect | Combine | async/await |
|--------|---------|------------|
| Single request | Verbose | Concise |
| Chained requests | `.flatMap` | Sequential `await` |
| Parallel requests | `.zip` / `Publishers.Zip` | `async let` |
| UI binding | Native (`.assign`, `@Published`) | Requires explicit assignment |
| Error handling | `.catch`, `.retry` | `do/catch`, `try` |
| Cancellation | `AnyCancellable` | `Task.cancel()` |
| iOS requirement | iOS 13 | iOS 15 |

For new code targeting iOS 15+, prefer async/await for networking. Use Combine when the result feeds directly into a reactive binding pipeline.

## 4. Practical Usage

```swift
import Combine
import Foundation

// ── Generic Decodable fetch ────────────────────────────────────
struct APIClient {
    private let session: URLSession
    private let decoder: JSONDecoder

    init(session: URLSession = .shared, decoder: JSONDecoder = .init()) {
        self.session = session
        self.decoder = decoder
    }

    func fetch<T: Decodable>(_ type: T.Type, from url: URL) -> AnyPublisher<T, Error> {
        session.dataTaskPublisher(for: url)        // (Data, URLResponse) | URLError
            .tryMap { data, response in
                guard let http = response as? HTTPURLResponse else {
                    throw URLError(.badServerResponse)
                }
                guard (200...299).contains(http.statusCode) else {
                    throw HTTPError.statusCode(http.statusCode)
                }
                return data
            }
            .decode(type: T.self, decoder: decoder) // Data → T
            .receive(on: DispatchQueue.main)
            .eraseToAnyPublisher()
    }

    func fetchWithRetry<T: Decodable>(
        _ type: T.Type,
        from url: URL,
        retries: Int = 3
    ) -> AnyPublisher<T, Error> {
        fetch(type, from: url)
            .retry(retries)                        // retry up to N times on failure
            .eraseToAnyPublisher()
    }
}

enum HTTPError: Error {
    case statusCode(Int)
}

// ── POST request ──────────────────────────────────────────────
struct LoginRequest: Encodable { let email: String; let password: String }
struct LoginResponse: Decodable { let token: String }

func login(email: String, password: String) -> AnyPublisher<LoginResponse, Error> {
    let url = URL(string: "https://api.example.com/login")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try? JSONEncoder().encode(LoginRequest(email: email, password: password))

    return URLSession.shared.dataTaskPublisher(for: request)
        .tryMap { data, response in
            guard let http = response as? HTTPURLResponse,
                  (200...299).contains(http.statusCode) else {
                throw URLError(.badServerResponse)
            }
            return data
        }
        .decode(type: LoginResponse.self, decoder: JSONDecoder())
        .receive(on: DispatchQueue.main)
        .eraseToAnyPublisher()
}

// ── Chained requests: login then fetch profile ─────────────────
struct UserProfile: Decodable { let name: String }

func loadDashboard(email: String, password: String) -> AnyPublisher<UserProfile, Error> {
    login(email: email, password: password)
        .flatMap { response in                     // use token to fetch profile
            let url = URL(string: "https://api.example.com/profile")!
            var request = URLRequest(url: url)
            request.setValue("Bearer \(response.token)", forHTTPHeaderField: "Authorization")
            return URLSession.shared.dataTaskPublisher(for: request)
                .tryMap { data, _ in data }
                .decode(type: UserProfile.self, decoder: JSONDecoder())
                .mapError { $0 as Error }
        }
        .receive(on: DispatchQueue.main)
        .eraseToAnyPublisher()
}

// ── Parallel requests with Zip ────────────────────────────────
struct Post: Decodable { let title: String }

func loadFeed() -> AnyPublisher<(UserProfile, [Post]), Error> {
    let client = APIClient()
    let profileURL = URL(string: "https://api.example.com/profile")!
    let postsURL = URL(string: "https://api.example.com/posts")!

    return Publishers.Zip(
        client.fetch(UserProfile.self, from: profileURL),
        client.fetch([Post].self, from: postsURL)
    )
    .eraseToAnyPublisher()
}

// ── ViewModel using Combine networking ────────────────────────
class FeedViewModel: ObservableObject {
    @Published var posts: [Post] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var cancellables = Set<AnyCancellable>()
    private let client = APIClient()

    func loadPosts() {
        isLoading = true
        errorMessage = nil

        client.fetch([Post].self, from: URL(string: "https://api.example.com/posts")!)
            .handleEvents(receiveCompletion: { [weak self] _ in
                self?.isLoading = false            // always stop loading on completion
            })
            .sink(
                receiveCompletion: { [weak self] completion in
                    if case .failure(let error) = completion {
                        self?.errorMessage = error.localizedDescription
                    }
                },
                receiveValue: { [weak self] posts in
                    self?.posts = posts
                }
            )
            .store(in: &cancellables)
    }
}

// ── Error recovery — fallback to cache ────────────────────────
func fetchWithFallback(url: URL, cached: [Post]) -> AnyPublisher<[Post], Never> {
    URLSession.shared.dataTaskPublisher(for: url)
        .map(\.data)
        .decode(type: [Post].self, decoder: JSONDecoder())
        .catch { _ in Just(cached) }               // on any error, use cached posts
        .receive(on: DispatchQueue.main)
        .eraseToAnyPublisher()
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What does `dataTaskPublisher` emit and when does it fail?**

A: `URLSession.DataTaskPublisher` emits a `(data: Data, response: URLResponse)` tuple when the HTTP response is received — regardless of the HTTP status code. It fails with a `URLError` only for network-level failures (no internet, timeout, SSL error). A 404 or 500 HTTP response is **not** a failure at the publisher level — you must add a `tryMap` operator to inspect the HTTP status code and throw an error for non-2xx responses.

**Q: What is the difference between `map` and `tryMap` in a networking pipeline?**

A: `map` applies a non-throwing transformation and cannot change the `Failure` type of the pipeline. `tryMap` applies a throwing transformation — if the closure throws, the publisher fails with the thrown error (widening `Failure` to `Error`). In a networking pipeline, `tryMap` is used to inspect the `URLResponse`, check the HTTP status code, and throw an error for non-success responses — converting a successful-at-network-layer but failed-at-HTTP-layer response into a pipeline failure.

### Hard

**Q: How do you chain two dependent network requests in Combine and what is the threading model?**

A: Use `flatMap`: the first publisher emits a value (e.g., an auth token), and `flatMap`'s closure uses that value to create and return a second publisher (e.g., fetch a profile using the token). The result is a pipeline that emits the second publisher's output. Threading: both `dataTaskPublisher` instances run their network tasks on `URLSession`'s internal queue. Each publisher delivers its response on a background thread. A single `receive(on: DispatchQueue.main)` at the end of the chain (after the last `flatMap`) is sufficient to deliver the final result to the main thread. Adding `receive(on:)` between the chained publishers is unnecessary and adds scheduling overhead.

**Q: When would you choose Combine networking over async/await?**

A: Combine networking is preferable when: (1) The result feeds directly into an existing reactive binding pipeline — e.g., assigning the result to a `@Published` property using `assign(to:)`. (2) You need complex operator-based transformations — multiple `retry`, `catch`, `combineLatest` with other publishers. (3) The codebase is already heavily Combine-based (iOS 13 apps). Async/await is preferable for: single or sequentially chained requests (simpler `try await` syntax), new code targeting iOS 15+, and when you want structured concurrency's cancellation and task tree semantics. For bridging: `publisher.values` (iOS 15+) converts any publisher to an `AsyncSequence`, enabling use in `for await` loops.

### Expert

**Q: Design a Combine-based API client with request deduplication — identical concurrent requests share one response.**

A: Use `share()` paired with a dictionary of in-flight publishers. When a request arrives: check if an `AnyPublisher` for this URL is already in the dictionary. If yes, return the shared publisher. If no, create a new `dataTaskPublisher`, apply `.share()`, store it in the dictionary, and return it. Add a `handleEvents(receiveCompletion:)` to remove the entry from the dictionary when the request completes. The `share()` operator multicasts one network response to all subscribers that subscribed before completion. If a subscriber arrives after completion, `share()` does not replay — use `makeConnectable()` + `autoconnect()` with a `ReplaySubject` (3rd party or custom) for replay semantics. This pattern prevents N identical requests being fired when N views bind to the same data simultaneously.

## 6. Common Issues & Solutions

**Issue: Sink receives no values from a network publisher.**

Solution: `AnyCancellable` not stored. Also check that the URL is valid and the network is reachable. Add `.print()` operator before `sink` to trace events.

**Issue: "Cannot convert return expression" error when chaining requests with flatMap.**

Solution: The inner publisher's `Failure` type must match the outer pipeline's `Failure` type. Use `.mapError { $0 as Error }` on the inner publisher to convert `URLError` to `Error`, or ensure the outer pipeline's failure is also typed as `URLError`.

**Issue: UI flickers — publisher fires multiple times for one network response.**

Solution: Add `removeDuplicates()` before the UI-bound operator if the model is `Equatable`. Also check that you're not accidentally creating multiple subscriptions (e.g., calling `bind()` on every `viewWillAppear`). Use `share()` if multiple UI components observe the same request.

**Issue: Decoding fails silently — completion fires with no values.**

Solution: Add a `sink(receiveCompletion:)` that logs the error. `DecodingError` descriptions are verbose but informative. Also add `.print("network")` operator to trace all events through the pipeline.

## 7. Related Topics

- [Publishers & Subscribers](publishers-subscribers.md) — dataTaskPublisher conforms to Publisher
- [Operators](operators.md) — tryMap, decode, retry, catch used in this section
- [Backpressure & Cancellation](backpressure-cancellation.md) — AnyCancellable cancels the URLSessionDataTask
- [async/await](../03-concurrency/async-await.md) — modern alternative for networking
