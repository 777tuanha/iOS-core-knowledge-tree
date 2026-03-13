# Mobile System Design

## 1. Overview

Mobile system design interviews ask candidates to design the architecture of a complete iOS feature or app — a Twitter feed, an offline-capable notes app, a real-time messaging system, an image-heavy social app. Unlike whiteboard algorithm interviews, system design interviews evaluate how you decompose a problem, choose appropriate technologies, handle failure modes, and balance competing concerns (offline support vs freshness, memory vs disk caching, modular boundaries vs build time). For iOS, system design spans three layers: **architecture** (how the app is structured — networking, persistence, UI, and feature flag layers), **data strategies** (how data moves between server, disk cache, and UI — pagination, sync, conflict resolution), and **large-scale app engineering** (how a team of 50+ engineers organises code across modules, frameworks, and shared SDKs). Strong answers show trade-off thinking, not just technology name-dropping.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Offline-First Architecture](offline-first-architecture.md) | Offline-first design, sync strategies, conflict resolution, API-driven UI, feature flags, remote config |
| 2 | [Caching & Pagination](caching-pagination.md) | Caching layers (memory/disk/CDN), cache invalidation strategies, cursor-based pagination, prefetching, sync |
| 3 | [Modular Architecture](modular-architecture.md) | Module boundaries, SPM packages, shared components, SDK design, dependency inversion across modules |

## 3. System Design Framework

Use this framework to structure any iOS system design answer:

```
1. Clarify requirements
   - Functional: what does the feature do?
   - Non-functional: offline support? real-time? scale? (user count, data size)
   - Constraints: time to implement, team size, existing infrastructure

2. High-level architecture
   - Layers: Network → Repository → Domain → Presentation
   - Data flow direction (unidirectional preferred)

3. Data model
   - Server schema vs local schema
   - What needs to be persisted? For how long?

4. Networking
   - REST vs GraphQL vs WebSocket
   - Retry, timeout, reachability handling

5. Persistence
   - CoreData vs SQLite vs UserDefaults vs Keychain
   - Cache size and eviction strategy

6. Offline / Sync
   - Can users write offline? How are conflicts resolved?
   - Queue of pending mutations?

7. Performance
   - What gets lazy-loaded? Prefetched? Paginated?
   - Image pipeline, memory budget

8. Error handling and observability
   - What errors are surfaced to users?
   - What's logged? What's crash-reported?

9. Testing
   - What's unit tested? Integration tested?
   - How is the network layer mocked?

10. Trade-offs
    - What did you intentionally simplify?
    - What would you do differently at 10× scale?
```

## 4. Quick Reference — Common Design Decisions

| Decision | Options | When to choose |
|----------|---------|---------------|
| Persistence | Core Data | Complex relationships, NSFetchedResultsController |
| | SQLite/GRDB | Complex queries, full control |
| | UserDefaults | Simple key-value, settings |
| | Files (JSON/Codable) | Simple, infrequently updated collections |
| Networking | URLSession | All networking — wrap in a custom `NetworkClient` |
| | WebSocket (URLSessionWebSocketTask) | Real-time messaging, live updates |
| | GraphQL | When multiple REST endpoints would be needed |
| Caching | NSCache | In-memory, automatic eviction |
| | URLCache | HTTP response caching (ETags, Cache-Control) |
| | Disk (Files) | Persistent across launches |
| Sync | Polling | Simple; acceptable latency |
| | Long polling | Medium latency; no persistent connection |
| | WebSocket | Real-time; persistent connection overhead |
| | Push + fetch | Best battery; push wakes app, app fetches |
| Offline writes | Operation queue to disk | Resume after reconnect; simple conflict model |
| | CRDTs | Conflict-free but complex; for collaborative editors |

## 5. Related Topics

- [Architecture](../06-architecture/index.md) — MVVM, Clean Architecture, dependency injection
- [Networking](../07-networking/index.md) — URLSession, Combine publishers, async/await
- [Data Persistence](../08-data-persistence/index.md) — Core Data, SQLite, Keychain
- [Performance](../12-performance/index.md) — memory, main thread, lazy loading
- [Concurrency](../03-concurrency/index.md) — async/await, actors for data access
