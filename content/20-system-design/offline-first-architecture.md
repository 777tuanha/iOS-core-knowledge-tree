# Offline-First Architecture

## 1. Overview

Offline-first architecture treats local persistence as the primary data source — the UI always reads from the local store, network responses update the local store, and the UI reacts to local store changes. This is the opposite of network-first, where the UI waits for network responses and falls back to cache only on failure. Offline-first results in instant UI rendering (no loading states for cached data), seamless degradation on poor connections, and the ability to read and write data with no connectivity. The challenges: **sync** (reconciling local writes made offline with the server state after reconnect), **conflict resolution** (what happens when the user edits a record on two devices simultaneously), **consistency** (stale data visible longer), and **complexity** (more code paths than a simple fetch-and-display approach). Three complementary patterns cover this section: offline-first data flow with a repository layer, **API-driven UI** (server defines screen structure — reduces app releases needed for UI changes), and **feature flags / remote config** (control feature rollout without App Store submissions).

## 2. Simple Explanation

Offline-first is like a notebook you carry everywhere. You write in it whether or not you have WiFi. When you get to a coffee shop (connectivity), the notebook syncs what you wrote to the cloud. API-driven UI is like a digital menu board in a restaurant: the restaurant (server) can change the menu (UI layout) without printing new menus (app updates). Feature flags are like light switches the product team can flip without calling an electrician (deploying an update) — a feature can be deployed in the binary but switched off until ready.

## 3. Deep iOS Knowledge

### Offline-First Data Flow

```
NetworkLayer         Repository           LocalStore         ViewModel/View
     │                    │                    │                    │
     │        ────────────────────────────────►│                    │
     │        read(predicate)                  │ query results       │
     │                    │◄────────────────────                    │
     │                    │                                         │
     │                    │──────────────────────────────────────►  │
     │                    │  Publisher<[Item], Never>               │
     │                    │                                         │
     │◄───────────────────│                                         │
     │  fetchFromNetwork() │                                         │
     │                    │                                         │
     ├── response ────────►│                                         │
     │                    │── upsert into LocalStore ──────────────►│
     │                    │                        ◄─ triggers update│
```

The repository is the single access point for domain objects. It:
1. Returns a publisher backed by the local store (immediate response).
2. Kicks off a background network fetch.
3. When the fetch completes, upserts results into the local store.
4. The local store change triggers an update to the existing publisher.

```swift
import Combine
import CoreData

// ── Repository ────────────────────────────────────────────────
protocol ArticleRepository {
    func articles(for feedID: String) -> AnyPublisher<[Article], Never>
    func saveArticle(_ article: Article) async throws
}

final class DefaultArticleRepository: ArticleRepository {
    private let localStore: ArticleLocalStore
    private let networkClient: NetworkClient
    private var cancellables = Set<AnyCancellable>()

    init(localStore: ArticleLocalStore, networkClient: NetworkClient) {
        self.localStore = localStore
        self.networkClient = networkClient
    }

    func articles(for feedID: String) -> AnyPublisher<[Article], Never> {
        // 1. Immediately trigger background fetch (fire and forget)
        Task { [weak self] in
            await self?.refreshFromNetwork(feedID: feedID)
        }

        // 2. Return a publisher backed by the local store
        // The view reacts to local changes — no waiting on network
        return localStore.articlesPublisher(feedID: feedID)
    }

    private func refreshFromNetwork(feedID: String) async {
        do {
            let articles = try await networkClient.fetchArticles(feedID: feedID)
            try await localStore.upsert(articles)   // triggers publisher update
        } catch {
            // Network failure is silent — local data remains visible
            // Log for observability, don't surface to user unless severe
        }
    }

    // Offline writes: saved locally, synced later
    func saveArticle(_ article: Article) async throws {
        try await localStore.save(article)           // write locally first
        try? await networkClient.createArticle(article)  // attempt sync
        // If network fails, a sync queue picks up the pending write later
    }
}
```

### Offline Write Queue

For mutations made offline, use a persistent queue that replays writes when connectivity is restored:

```swift
import Foundation
import Combine

// Pending operations survive app restarts — stored on disk
struct PendingOperation: Codable {
    let id: UUID
    let type: OperationType
    let payload: Data
    let createdAt: Date

    enum OperationType: String, Codable {
        case createArticle, deleteArticle, updateArticle
    }
}

actor OfflineWriteQueue {
    private let persistence: PersistenceURL
    private(set) var operations: [PendingOperation] = []

    init(persistence: PersistenceURL) {
        self.persistence = persistence
        self.operations = load()
    }

    func enqueue(_ op: PendingOperation) {
        operations.append(op)
        save()
    }

    func dequeue(_ id: UUID) {
        operations.removeAll { $0.id == id }
        save()
    }

    // Called when network becomes available
    func flush(with networkClient: NetworkClient) async {
        for op in operations {
            do {
                try await replay(op, with: networkClient)
                dequeue(op.id)
            } catch {
                // Leave in queue — retry on next flush
                break   // stop at first failure to preserve ordering
            }
        }
    }

    private func replay(_ op: PendingOperation, with client: NetworkClient) async throws {
        switch op.type {
        case .createArticle:
            let article = try JSONDecoder().decode(Article.self, from: op.payload)
            try await client.createArticle(article)
        case .deleteArticle:
            let id = try JSONDecoder().decode(String.self, from: op.payload)
            try await client.deleteArticle(id: id)
        case .updateArticle:
            let article = try JSONDecoder().decode(Article.self, from: op.payload)
            try await client.updateArticle(article)
        }
    }

    private func load() -> [PendingOperation] {
        guard let data = try? Data(contentsOf: persistence.url),
              let ops = try? JSONDecoder().decode([PendingOperation].self, from: data) else {
            return []
        }
        return ops
    }

    private func save() {
        try? JSONEncoder().encode(operations).write(to: persistence.url)
    }
}

struct PersistenceURL { let url: URL }
```

### Conflict Resolution Strategies

| Strategy | Description | Use When |
|----------|-------------|----------|
| **Last-write-wins** | Server timestamp determines winner | Simple edits (settings, profile) |
| **Server-wins** | Server always authoritative | Content the server owns (feed, catalogue) |
| **Client-wins** | Client always wins on conflict | Offline-first notes, personal data |
| **Merge** | Field-level merge (union of sets) | Tags, lists where additions from both sides are valid |
| **User prompt** | Show diff, ask user to choose | High-value conflicts (document editors) |
| **CRDTs** | Conflict-free replicated data types | Collaborative editors, complex shared state |

```swift
// Last-write-wins implementation using server timestamp
struct ConflictResolver {
    static func resolve(local: Article, server: Article) -> Article {
        // Server timestamp wins — straightforward for feed content
        return local.updatedAt > server.updatedAt ? local : server
    }
}
```

### API-Driven UI

The server returns a structured description of the UI to render, not just data. The app maps server components to native views. Reduces the need for app updates when changing screen layouts.

```swift
// Server response describes the screen structure
struct APIScreen: Decodable {
    let sections: [APISection]
}

struct APISection: Decodable {
    let type: SectionType
    let items: [APIItem]

    enum SectionType: String, Decodable {
        case hero, carousel, grid, list, banner
    }
}

struct APIItem: Decodable {
    let id: String
    let type: String         // "article" | "product" | "ad" | "header"
    let title: String
    let imageURL: URL?
    let actionURL: URL?
    let metadata: [String: String]
}

// UI mapper — new component types added without app update
// (as long as the native view code handles the type)
final class HomeScreenBuilder {
    func buildSection(_ section: APISection) -> UIView {
        switch section.type {
        case .hero:     return HeroBannerView(items: section.items)
        case .carousel: return CarouselView(items: section.items)
        case .grid:     return GridView(items: section.items)
        case .list:     return ListView(items: section.items)
        case .banner:   return BannerView(items: section.items)
        }
    }
}
```

### Feature Flags

Feature flags gate code paths — deploy a feature disabled, enable it for specific users or a percentage, roll back by flipping the flag without a new build.

```swift
import Foundation

// ── Feature flag service ──────────────────────────────────────
protocol FeatureFlagService {
    func isEnabled(_ flag: FeatureFlag) -> Bool
    func stringValue(for flag: FeatureFlag) -> String?
}

enum FeatureFlag: String {
    case newFeedLayout = "feed.new_layout"
    case paymentsV2 = "payments.v2"
    case chatFeature = "chat.enabled"
    case maxUploadSizeMB = "uploads.max_size_mb"
}

// ── Remote config backed implementation ──────────────────────
final class RemoteFeatureFlagService: FeatureFlagService {
    // UserDefaults used as local cache — survives offline
    private let cache = UserDefaults(suiteName: "group.com.acme.flags")!
    private let networkClient: NetworkClient

    func isEnabled(_ flag: FeatureFlag) -> Bool {
        // Read from local cache — fetch happens in background
        cache.bool(forKey: flag.rawValue)
    }

    func stringValue(for flag: FeatureFlag) -> String? {
        cache.string(forKey: flag.rawValue)
    }

    // Called at app launch — updates cache from server
    func refresh() async {
        do {
            let flags = try await networkClient.fetchFeatureFlags()
            for (key, value) in flags {
                cache.set(value, forKey: key)
            }
        } catch {
            // Use cached values — acceptable; flags rarely change
        }
    }
}

// ── Usage in a view model ─────────────────────────────────────
final class FeedViewModel: ObservableObject {
    private let flags: FeatureFlagService

    var useNewLayout: Bool { flags.isEnabled(.newFeedLayout) }

    init(flags: FeatureFlagService) {
        self.flags = flags
    }
}
```

## 4. Practical Usage

```swift
// ── Full offline-first feed system ───────────────────────────
import SwiftUI
import Combine

// Domain model
struct Article: Identifiable, Codable {
    let id: String
    let title: String
    let body: String
    let updatedAt: Date
}

// ViewModel subscribes to the repository publisher
// — renders from local data immediately, updates when network returns
@MainActor
final class FeedViewModel: ObservableObject {
    @Published private(set) var articles: [Article] = []
    @Published private(set) var isOnline: Bool = true

    private let repository: ArticleRepository
    private let reachability: ReachabilityMonitor
    private let offlineQueue: OfflineWriteQueue
    private var cancellables = Set<AnyCancellable>()

    init(
        repository: ArticleRepository,
        reachability: ReachabilityMonitor,
        offlineQueue: OfflineWriteQueue
    ) {
        self.repository = repository
        self.reachability = reachability
        self.offlineQueue = offlineQueue

        repository.articles(for: "main")
            .receive(on: DispatchQueue.main)
            .assign(to: &$articles)

        // Flush offline queue when connectivity restored
        reachability.isConnectedPublisher
            .removeDuplicates()
            .sink { [weak self] connected in
                self?.isOnline = connected
                if connected {
                    Task { [weak self] in
                        guard let self else { return }
                        await self.offlineQueue.flush(with: NetworkClient())
                    }
                }
            }
            .store(in: &cancellables)
    }

    func likeArticle(_ article: Article) async {
        let op = PendingOperation(
            id: UUID(),
            type: .updateArticle,
            payload: (try? JSONEncoder().encode(article)) ?? Data(),
            createdAt: Date()
        )
        if isOnline {
            // Try immediate sync
            try? await repository.saveArticle(article)
        } else {
            // Queue for later
            await offlineQueue.enqueue(op)
        }
    }
}

// Reachability Monitor using Network framework
import Network

final class ReachabilityMonitor {
    private let monitor = NWPathMonitor()
    private let subject = CurrentValueSubject<Bool, Never>(true)

    var isConnectedPublisher: AnyPublisher<Bool, Never> {
        subject.eraseToAnyPublisher()
    }

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            self?.subject.send(path.status == .satisfied)
        }
        monitor.start(queue: DispatchQueue(label: "reachability"))
    }
}

// Placeholder types
protocol NetworkClient {
    func fetchArticles(feedID: String) async throws -> [Article]
    func createArticle(_ article: Article) async throws
    func updateArticle(_ article: Article) async throws
    func deleteArticle(id: String) async throws
    func fetchFeatureFlags() async throws -> [String: Bool]
}
protocol ArticleLocalStore {
    func articlesPublisher(feedID: String) -> AnyPublisher<[Article], Never>
    func upsert(_ articles: [Article]) async throws
    func save(_ article: Article) async throws
}
final class NetworkClient: NetworkClient { /* URLSession implementation */ }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is offline-first architecture and how does it differ from network-first?**

A: In **network-first** architecture, the app issues a network request and waits for a response before rendering the UI. On failure, it falls back to cached data. The UX suffers on slow connections: users see loading spinners even for data they've already seen. In **offline-first** architecture, the app always reads from the local store first and renders immediately. A background network request refreshes the local store; when the store updates, the UI updates reactively. The key difference is that the local store is the source of truth for the UI — network responses update the store, not the UI directly. Offline-first also means supporting writes while offline: user actions are saved locally and queued for sync when connectivity returns. The trade-off: more code complexity (sync logic, conflict resolution), and the UI can show stale data until the background fetch completes (mitigated with timestamps or "last updated" indicators).

**Q: What are feature flags and why do mobile apps need them when the App Store requires review?**

A: Feature flags are boolean (or string) values fetched from a remote service that control which code paths execute. They allow: (1) **Gradual rollout** — deploy a feature to 1% of users, monitor crash rate and engagement, expand to 100% if healthy; (2) **Kill switch** — disable a broken feature without submitting a new build (critical on iOS where updates take 1–3 days to review); (3) **A/B testing** — show different UI variants to different user segments; (4) **Environment-specific features** — enable features only for internal users during development. On iOS, shipping a hotfix takes at minimum 24 hours (review time). A feature flag that disables a broken feature is instant. The flag is fetched from a service (Firebase Remote Config, LaunchDarkly, or a custom endpoint) at app launch, cached locally (for offline use), and read by feature code before executing.

### Hard

**Q: How do you handle conflicts when a user edits a note on two devices simultaneously while offline?**

A: The correct strategy depends on the data type: (1) **Last-write-wins with vector clocks**: each device tracks a logical clock (a counter incremented on each write). On sync, the server compares vector clocks — if Device A's clock is strictly greater than Device B's, Device A wins without conflict. If clocks are concurrent (both incremented since the last sync), a conflict exists. (2) **Operational transform (OT) or CRDTs**: for collaborative text editing, use a CRDT like a sequence CRDT (Automerge, Y.js). Operations (insert/delete at position) from both devices are replayed in a deterministic order — no conflict, no data loss. (3) **Field-level merge**: if the note has independent fields (title, body, tags), merge field-by-field using last-write-wins per field. If only the title changed on Device A and only the body changed on Device B, the merge is trivial. (4) **User prompt**: for high-value, short-form content (expense amounts, medical records), show the user both versions and ask them to choose. For an iOS notes app, the pragmatic choice is OT/CRDT for the body (collaborative editing UX) and last-write-wins for metadata fields (title, tags).

**Q: How do you implement API-driven UI safely — handling unknown component types without crashing?**

A: Use an unknown-safe default in the type mapping and a graceful fallback view: (1) **Decodable safety**: add an `unknown` case to the `SectionType` enum with a `@unknown default` or make the raw value init return `nil` for unrecognised values — then use `nil` to render an empty view. Swift `Decodable` with custom `init(from:)` can decode unexpected strings to `.unknown` instead of throwing. (2) **Nil/empty view**: the UI mapper returns an empty view or `nil` for `.unknown` types — it logs the unknown type to analytics so you know when a new component type is being sent before the client has support. (3) **Versioned API**: include a `minimumClientVersion` field in the screen response. If the client version is below the minimum, show a forced-upgrade prompt instead of an incompatible layout. (4) **Shadow rendering**: for new component types, the server can include both a known fallback layout and the new type — older clients render the fallback; newer clients render the new component. This is the safest rollout strategy for structural UI changes.

### Expert

**Q: Design the architecture for an offline-capable iOS messaging app where users can send messages offline and receive them on reconnect.**

A: Seven-component design: (1) **Local message store** (Core Data with WAL mode for concurrent reads/writes): messages are stored with states: `.sending` (local only, not yet acked), `.sent` (server-confirmed), `.delivered` (server confirmed delivery), `.failed`. The UI reads from Core Data and renders all states. (2) **Send pipeline**: user sends → message saved locally as `.sending` → added to `OutboxQueue` (a persistent ordered list of pending sends). The queue runs a serial task that attempts to send each message in order — ordering is preserved even after app restart. (3) **WebSocket for real-time**: `URLSessionWebSocketTask` maintains a persistent connection when the app is in the foreground. Incoming messages are upserted into Core Data. On disconnect, the task reconnects automatically with exponential backoff. (4) **APNs for background delivery**: when offline, the server sends a silent push notification — `UIBackgroundFetchResult` triggers a background URLSession task that downloads missed messages and updates Core Data. (5) **Reachability integration**: `NWPathMonitor` observes connectivity changes. On reconnect: (a) flush the `OutboxQueue`, (b) fetch missed messages via HTTP (for reliability over WebSocket gaps), (c) reconnect WebSocket. (6) **Conflict resolution**: messages are append-only (immutable after send) — no conflicts. Message IDs are client-generated UUIDs to avoid duplicate sends. The server deduplicates by UUID. (7) **Observability**: log outbox queue depth, send latency, WebSocket reconnect events. Alert if queue depth > 50 messages (user is stuck).

## 6. Common Issues & Solutions

**Issue: The app shows stale data long after the network fetch completes.**

Solution: The repository is not updating the local store publisher after the network response. Check that: (1) the local store is the source of truth (UI reads from it, not from the network response directly), (2) the `upsert` operation writes to the same context/table the publisher observes, (3) the publisher is configured to emit on data change (e.g., `NSFetchedResultsController` with a delegate, or a Combine publisher backed by an `NSManagedObjectContextDidSave` notification). Also check that `upsert` performs on the correct Core Data context — writing on a background context and reading on the view context requires a context merge (`viewContext.automaticallyMergesChangesFromParent = true`).

**Issue: Feature flags show the wrong value for returning users — they see the old value after a flag is changed.**

Solution: The local cache is being read before the refresh completes. Use a strategy of: cache-first with background refresh (acceptable) — the stale value is shown on the first launch after a flag change, but is correct on subsequent launches. Or use async/await to await the refresh before proceeding for critical flags: `await flagService.refresh()` in the launch sequence before the first screen is shown (add a splash screen timeout of 1–2 seconds). For kill-switch flags (used to disable broken features), prefer the remote value over the cache — add a flag property `isCritical: Bool` that forces a network fetch before returning.

## 7. Related Topics

- [Caching & Pagination](caching-pagination.md) — cache layers below the repository
- [Modular Architecture](modular-architecture.md) — feature isolation that enables safe flag rollouts
- [Data Persistence](../08-data-persistence/index.md) — Core Data as the local store
- [Networking](../07-networking/index.md) — URLSession, async/await for fetch calls
- [Concurrency](../03-concurrency/actors.md) — actors protecting the offline queue
