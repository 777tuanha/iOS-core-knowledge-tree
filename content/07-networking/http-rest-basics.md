# HTTP & REST Basics

## 1. Overview

HTTP (HyperText Transfer Protocol) is the application-layer protocol underlying almost all web API communication. REST (Representational State Transfer) is an architectural style — a set of constraints — that governs how HTTP resources should be designed. Senior iOS engineers must understand both: HTTP because `URLSession` works at this level, and REST because most production APIs they consume are RESTful. Understanding status codes, headers, methods, and idempotency is essential for building correct error handling, retry logic, and caching.

## 2. Simple Explanation

Think of HTTP like sending letters. Each letter (request) has an address (URL), a type of action (method — "please send me", "please update"), and optional content (body). The post office (server) sends back a reply (response) with a status ("delivered successfully" = 200, "address not found" = 404, "post office on fire" = 500). REST is the convention for organising what those addresses mean: `/users` is the list of all users; `/users/42` is user number 42. The convention makes APIs predictable and self-documenting.

## 3. Deep iOS Knowledge

### HTTP Methods

| Method | Semantics | Idempotent? | Safe? | Has body? |
|--------|-----------|-------------|-------|-----------|
| GET | Retrieve a resource | Yes | Yes | No |
| POST | Create a resource / submit action | No | No | Yes |
| PUT | Replace a resource entirely | Yes | No | Yes |
| PATCH | Partially update a resource | No* | No | Yes |
| DELETE | Remove a resource | Yes | No | No |
| HEAD | Like GET but no body (check existence/ETag) | Yes | Yes | No |
| OPTIONS | Discover allowed methods (CORS preflight) | Yes | Yes | No |

**Idempotent**: calling the method multiple times has the same effect as calling it once.
**Safe**: the method does not modify server state.

**iOS implication**: Only retry idempotent methods automatically. Retrying a POST can create duplicate resources.

### HTTP Status Codes

| Range | Category | Common codes |
|-------|----------|-------------|
| 1xx | Informational | 100 Continue, 101 Switching Protocols |
| 2xx | Success | 200 OK, 201 Created, 204 No Content |
| 3xx | Redirection | 301 Moved Permanently, 304 Not Modified |
| 4xx | Client error | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 429 Too Many Requests |
| 5xx | Server error | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout |

**Key distinctions**:
- **401 vs 403**: 401 means unauthenticated (no valid token); 403 means authenticated but unauthorised (valid token, insufficient permissions).
- **400 vs 422**: 400 is a malformed request (bad JSON structure); 422 is well-formed but semantically invalid (email already in use).
- **429**: Too Many Requests — rate limited; response includes `Retry-After` header.
- **503**: Service Unavailable — temporary; safe to retry after a delay.

### HTTP Headers

Headers are key-value metadata attached to requests and responses.

**Common request headers**:

| Header | Purpose | Example |
|--------|---------|---------|
| `Authorization` | Authentication token | `Bearer eyJhbGci...` |
| `Content-Type` | MIME type of the request body | `application/json; charset=utf-8` |
| `Accept` | MIME types the client accepts | `application/json` |
| `Accept-Language` | Client's preferred language | `en-US, en;q=0.9` |
| `User-Agent` | Client identification | `MyApp/2.1 (iOS 17; iPhone)` |
| `If-None-Match` | Conditional GET (ETag-based) | `"abc123"` |
| `If-Modified-Since` | Conditional GET (date-based) | `Wed, 01 Jan 2025 00:00:00 GMT` |

**Common response headers**:

| Header | Purpose |
|--------|---------|
| `Content-Type` | MIME type of the response body |
| `Cache-Control` | Caching directives (`max-age=3600`, `no-cache`, `no-store`) |
| `ETag` | Entity tag for conditional requests |
| `Last-Modified` | Last modification date of the resource |
| `Retry-After` | How long to wait before retrying (429/503 responses) |
| `X-RateLimit-Remaining` | Remaining requests in the current window |
| `Location` | URL of a newly created resource (201 Created) |

### REST Constraints

REST is defined by six architectural constraints:

1. **Client-Server**: Separation of UI from data storage.
2. **Stateless**: Each request contains all information needed; no server-side session state.
3. **Cacheable**: Responses declare whether they can be cached.
4. **Uniform Interface**: Resources identified by URLs; standard HTTP methods; hypermedia (HATEOAS).
5. **Layered System**: Client doesn't know if it's talking to the server directly or a proxy/CDN.
6. **Code on Demand** (optional): Server can deliver executable code (e.g., JavaScript).

### RESTful Resource Design

```
GET    /posts           → list all posts
POST   /posts           → create a new post
GET    /posts/42        → get post 42
PUT    /posts/42        → replace post 42
PATCH  /posts/42        → partially update post 42
DELETE /posts/42        → delete post 42
GET    /posts/42/comments → list comments on post 42
```

### Content Negotiation

Client and server negotiate format via headers:
- Client sends `Accept: application/json` — prefers JSON.
- Server responds `Content-Type: application/json` — confirming JSON.
- If server can't satisfy `Accept`, it returns `406 Not Acceptable`.

### Caching with ETags

```
1. Client: GET /posts/42
2. Server: 200 OK, ETag: "abc123", body: {...}
3. (time passes)
4. Client: GET /posts/42, If-None-Match: "abc123"
5. Server: 304 Not Modified (no body) — client uses cached copy
     OR
   Server: 200 OK, ETag: "xyz789", body: {...} — new content
```

`URLCache` handles this automatically when `Cache-Control` headers are correct.

## 4. Practical Usage

```swift
import Foundation

// ── Building URLRequests with correct HTTP method + headers ───
func makeGetRequest(url: URL, token: String) -> URLRequest {
    var request = URLRequest(url: url)
    request.httpMethod = "GET"                                  // explicit — GET is default
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.setValue("application/json", forHTTPHeaderField: "Accept")
    return request
}

func makePostRequest<T: Encodable>(url: URL, body: T, token: String) throws -> URLRequest {
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.httpBody = try JSONEncoder().encode(body)           // encode body to JSON
    return request
}

func makePatchRequest<T: Encodable>(url: URL, body: T, token: String) throws -> URLRequest {
    var request = URLRequest(url: url)
    request.httpMethod = "PATCH"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    request.httpBody = try JSONEncoder().encode(body)
    return request
}

// ── Validating HTTP status codes ──────────────────────────────
enum NetworkError: Error {
    case unauthorized                // 401
    case forbidden                   // 403
    case notFound                    // 404
    case rateLimited(retryAfter: TimeInterval?)  // 429
    case serverError(statusCode: Int)            // 5xx
    case unexpected(statusCode: Int)
}

func validate(response: URLResponse, data: Data) throws -> Data {
    guard let http = response as? HTTPURLResponse else {
        throw NetworkError.unexpected(statusCode: -1)
    }
    switch http.statusCode {
    case 200...299:
        return data                   // success — return data for decoding
    case 401:
        throw NetworkError.unauthorized
    case 403:
        throw NetworkError.forbidden
    case 404:
        throw NetworkError.notFound
    case 429:
        let retryAfter = (http.value(forHTTPHeaderField: "Retry-After"))
            .flatMap { TimeInterval($0) }
        throw NetworkError.rateLimited(retryAfter: retryAfter)
    case 500...599:
        throw NetworkError.serverError(statusCode: http.statusCode)
    default:
        throw NetworkError.unexpected(statusCode: http.statusCode)
    }
}

// ── Full request + validation ─────────────────────────────────
struct Post: Decodable { let id: Int; let title: String }

func fetchPost(id: Int, token: String) async throws -> Post {
    let url = URL(string: "https://api.example.com/posts/\(id)")!
    let request = makeGetRequest(url: url, token: token)

    let (data, response) = try await URLSession.shared.data(for: request)
    let validData = try validate(response: response, data: data)
    return try JSONDecoder().decode(Post.self, from: validData)
}

// ── Reading response headers ──────────────────────────────────
func fetchWithETag(url: URL) async throws -> (Data, String?) {
    let (data, response) = try await URLSession.shared.data(from: url)
    let etag = (response as? HTTPURLResponse)?.value(forHTTPHeaderField: "ETag")
    return (data, etag)
}

// ── Conditional GET with If-None-Match ───────────────────────
func fetchIfChanged(url: URL, etag: String?) async throws -> Data? {
    var request = URLRequest(url: url)
    if let etag { request.setValue(etag, forHTTPHeaderField: "If-None-Match") }

    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse else { return data }

    if http.statusCode == 304 { return nil }    // not modified — use cached copy
    return data
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between PUT and PATCH?**

A: `PUT` replaces the entire resource at the target URL with the request body. If you `PUT` a user object, all fields are replaced — omitting a field removes it. `PATCH` applies a partial update — only the fields included in the request body are changed. In iOS, use `PUT` when the client owns the complete resource representation and can always send the full object. Use `PATCH` for incremental edits (e.g., updating a user's display name without sending their entire profile). `PUT` is idempotent; `PATCH` technically is not, though many APIs treat it as idempotent in practice.

**Q: What is the difference between a 401 and a 403 status code?**

A: `401 Unauthorized` means the request is **unauthenticated** — no valid credentials were provided, or the token is expired. The correct action is to re-authenticate (refresh the token or prompt for login). `403 Forbidden` means the request is **authenticated** (the server knows who you are) but **unauthorised** — your account lacks permission to access the resource. Re-authenticating won't help; the user simply doesn't have access. In iOS networking layers, these require different handling: 401 triggers a token refresh; 403 shows an "insufficient permissions" error to the user.

### Hard

**Q: Explain ETags and conditional requests. Why are they important for mobile networking?**

A: An ETag is an opaque identifier (hash or version string) the server assigns to a resource. On a GET response, the server includes `ETag: "abc123"`. On subsequent requests, the client sends `If-None-Match: "abc123"`. If the resource hasn't changed, the server returns `304 Not Modified` with no body — saving bandwidth. If changed, it returns `200 OK` with the new body and new ETag. For mobile networks, this is significant: a 304 response costs only the round-trip (headers only), while a full JSON payload might be 100KB+. `URLCache` handles ETags automatically when `Cache-Control` headers permit caching and when using the `.useProtocolCachePolicy` cache policy.

**Q: When should you retry a failed request and when should you not?**

A: Retry only **idempotent** requests where it is safe to call multiple times: GET, PUT, DELETE, HEAD. Never auto-retry POST (could create duplicate records) or PATCH without idempotency keys. Retry for: `5xx` server errors (transient failures), `429 Too Many Requests` (after the `Retry-After` delay), network timeouts (`URLError.timedOut`), and DNS failures. Do not retry for: `4xx` client errors (the request is wrong — retrying won't help), `401` without first refreshing the token, or `403` (permission denied). Always implement exponential backoff with jitter to avoid thundering-herd when a server recovers — see [Advanced Networking](advanced-networking.md).

### Expert

**Q: Describe HTTP/2 multiplexing and how it affects iOS networking compared to HTTP/1.1.**

A: HTTP/1.1 sends one request per TCP connection (with pipelining rarely used in practice). HTTP/2 multiplexes multiple concurrent requests over a single TCP connection using binary-framed streams. For iOS apps that make 10–20 concurrent API calls on a screen load, HTTP/1.1 required multiple TCP+TLS handshakes, with each new connection costing 100–300ms. HTTP/2 amortises this cost — all requests share one connection, headers are compressed (HPACK), and the server can push responses proactively. `URLSession` transparently uses HTTP/2 when the server supports ALPN negotiation. Developers generally don't need to configure anything, but understanding this is important for: diagnosing why batching 20 requests into one is less valuable on HTTP/2 than on HTTP/1.1; understanding server-push use cases; and troubleshooting why `URLSession` maintains only one connection to the same host under HTTP/2.

## 6. Common Issues & Solutions

**Issue: Server returns 200 even for errors — body contains `{ "error": "not found" }`.**

Solution: Some APIs (especially older ones) use HTTP 200 for all responses and encode errors in the body. Your `validate` function must check both the HTTP status and the response body structure. Add a `tryMap` step in your pipeline to parse the body and throw an error if it contains an error field.

**Issue: `Authorization` header is stripped on redirect.**

Solution: `URLSession` drops the `Authorization` header by default on cross-origin redirects (security measure). Use `URLSessionTaskDelegate.urlSession(_:task:willPerformHTTPRedirection:newRequest:completionHandler:)` to re-add the header to the new request when the redirect is to a trusted domain.

**Issue: POST request creates duplicate records on retry.**

Solution: Implement **idempotency keys** — a client-generated UUID sent as a header (e.g., `Idempotency-Key: <UUID>`). The server deduplicates requests with the same key. Alternatively, move the retry logic to only apply to GET requests and implement a separate "check then create" flow for POST.

## 7. Related Topics

- [URLSession](urlsession.md) — the iOS API that sends HTTP requests
- [Codable & JSON](codable-json.md) — decoding HTTP response bodies
- [Advanced Networking](advanced-networking.md) — retry, caching, pagination, offline
- [Combine Networking](../05-reactive-programming/combine-networking.md) — Combine pipeline for HTTP requests
