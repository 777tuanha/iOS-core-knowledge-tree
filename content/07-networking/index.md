# Networking

## Overview

Networking is how an iOS app communicates with the outside world — fetching data from APIs, uploading files, receiving push payloads, and synchronising state with a server. Every production iOS app does networking. Senior engineers must understand the full stack: the HTTP/REST protocol layer, Apple's `URLSession` API, Swift's `Codable` system for serialisation, and the advanced patterns that make networking robust in the real world — retry, interceptors, caching, pagination, and offline handling.

Apple's networking stack is built around `URLSession`, a mature, powerful API that supports data tasks, download/upload tasks, WebSocket, background transfers, and authentication. In modern Swift it integrates directly with async/await. For reactive pipelines, `URLSession.dataTaskPublisher` brings it into Combine.

## Topics in This Section

- [HTTP & REST Basics](http-rest-basics.md) — REST constraints, HTTP methods, status codes, headers, content negotiation
- [URLSession](urlsession.md) — URLSession architecture, task types, URLRequest, delegates, background sessions, async/await integration
- [Codable & JSON](codable-json.md) — Codable protocol, JSONDecoder/Encoder, CodingKeys, custom decoding, nested structures, error handling
- [Advanced Networking](advanced-networking.md) — Retry with backoff, URLProtocol interceptors, URLCache, pagination patterns, offline handling and Reachability

## iOS Networking Stack

```
Your App Code  (ViewModel / Repository)
      │
      ▼
URLSession  (task management, authentication, cookies)
      │
      ▼
URLSessionConfiguration  (timeouts, cache policy, headers, TLS)
      │
      ▼
CFNetwork / Network.framework  (TCP/TLS/HTTP2 implementation)
      │
      ▼
Kernel / Network Driver
      │
      ▼
Physical Network  (Wi-Fi / Cellular)
```

## Key Concepts at a Glance

| Concept | One-line summary |
|---------|-----------------|
| URLSession | The central networking object; manages tasks and connections |
| URLRequest | Configures a single HTTP request (URL, method, headers, body) |
| URLSessionDataTask | Fetches data into memory |
| URLSessionDownloadTask | Downloads to a temp file; supports background and resume |
| URLSessionUploadTask | Uploads data/file; supports background |
| URLSessionWebSocketTask | Persistent bidirectional WebSocket connection |
| URLSessionConfiguration | Session-level settings (timeout, cache policy, headers) |
| Codable | Swift protocol for encoding/decoding to/from external representations |
| JSONDecoder | Decodes JSON Data → Swift Decodable types |
| URLCache | System HTTP response cache, configurable in URLSessionConfiguration |
| URLProtocol | Intercepts and handles URL loading at the protocol level |

## Request Lifecycle

```
1. Create URLRequest (URL, method, headers, body)
2. URLSession creates a URLSessionTask
3. Task executes: DNS → TCP → TLS handshake → HTTP request sent
4. Server sends HTTP response (status + headers + body)
5. URLSession delivers (Data, URLResponse, Error) to completion / delegate
6. App validates status code, decodes body with JSONDecoder
7. Decoded model flows to ViewModel / Repository
```

## Relationship to Other Sections

- **Reactive Programming**: `URLSession.dataTaskPublisher` integrates networking into Combine pipelines — see [Combine Networking](../05-reactive-programming/combine-networking.md).
- **Concurrency**: `URLSession.data(for:)` is an async function; use with `async/await` — see [async/await](../03-concurrency/async-await.md).
- **Architecture**: Networking belongs in the Data layer of a layered architecture — see [Modularization](../06-architecture/modularization.md).
- **Data Persistence**: Caching and offline support bridge networking and persistence — see [Data Persistence](../08-data-persistence/index.md).
