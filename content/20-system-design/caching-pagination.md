# Caching & Pagination

## 1. Overview

Caching and pagination are the two performance levers most directly visible to users in data-heavy apps. **Caching** stores previously fetched data close to the consumer — in memory (fastest), on disk (persistent across launches), or as HTTP-layer caching (transparent, uses server headers). An effective cache strategy delivers fast first-render, reduces bandwidth and server load, and provides graceful offline behaviour. **Pagination** loads data in chunks rather than all at once — essential for feeds, search results, or any list that grows over time. The standard approach for mobile is cursor-based pagination (stateless server, handles insertions between pages), not offset pagination (fragile under insertions, requires server to count). The two systems interact: each page is a cacheable unit; an expired cache should trigger re-fetching the first page; pre-fetching the next page fills the cache before the user scrolls to it.

## 2. Simple Explanation

Caching is like keeping a grocery list on your fridge. Next time you need eggs, you check the fridge first — instant, free, no trip to the store. If the list is out of date (expired), you go to the store (network) and update the fridge. Pagination is like loading a book 20 pages at a time instead of downloading the whole library. When you reach the last page you've loaded, the app fetches the next 20. The cursor is a bookmark that tells the server exactly where you left off — even if new pages were added at the beginning.

## 3. Deep iOS Knowledge

### Caching Layers

```
Request
  │
  ▼
1. Memory Cache (NSCache / dictionary)
   — Hit: return immediately (microseconds)
   — Miss: check Disk Cache
     │
     ▼
2. Disk Cache (Files / SQLite / URLCache)
   — Hit: return from disk, optionally warm memory cache
   — Miss: fetch from Network
     │
     ▼
3. HTTP Response Cache (URLCache)
   — Uses Cache-Control / ETag headers
   — Can revalidate with conditional GET (If-None-Match)
     │
     ▼
4. CDN (Content Delivery Network)
   — Edge cache close to user (not controlled by app)
   — Images, static assets, API responses with long TTL
```

### NSCache (Memory Cache)

`NSCache` is thread-safe, auto-evicts under memory pressure, and is the standard in-memory cache for iOS.

```swift
import UIKit

// Typed NSCache wrapper
final class ImageCache {
    private let cache: NSCache<NSString, UIImage> = {
        let cache = NSCache<NSString, UIImage>()
        cache.totalCostLimit = 50 * 1024 * 1024   // 50 MB — measured in bytes
        cache.countLimit = 200                      // max 200 images
        return cache
    }()

    func image(for url: URL) -> UIImage? {
        cache.object(forKey: url.absoluteString as NSString)
    }

    func setImage(_ image: UIImage, for url: URL) {
        // Cost = pixel count × 4 bytes per pixel (ARGB)
        let cost = Int(image.size.width * image.size.height * image.scale * image.scale) * 4
        cache.setObject(image, forKey: url.absoluteString as NSString, cost: cost)
    }

    func removeImage(for url: URL) {
        cache.removeObject(forKey: url.absoluteString as NSString)
    }
}
```

### Disk Cache

For persistence across app launches (images, JSON responses):

```swift
import Foundation
import CryptoKit  // for hashing cache key

actor DiskCache {
    private let directory: URL

    init(name: String) {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        directory = caches.appendingPathComponent(name)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    func read(key: String) -> Data? {
        let path = filePath(for: key)
        guard let data = try? Data(contentsOf: path) else { return nil }
        // Check TTL stored in extended attributes or a sidecar file
        guard !isExpired(key: key) else {
            try? FileManager.default.removeItem(at: path)
            return nil
        }
        return data
    }

    func write(_ data: Data, key: String, ttl: TimeInterval = 3600) {
        let path = filePath(for: key)
        try? data.write(to: path)
        // Store expiry in a sidecar JSON
        let expiry = Date().addingTimeInterval(ttl)
        let expiryData = try? JSONEncoder().encode(expiry)
        try? expiryData?.write(to: path.appendingPathExtension("expiry"))
    }

    func purge() {
        try? FileManager.default.removeItem(at: directory)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    private func filePath(for key: String) -> URL {
        // Hash the key to get a safe filename
        let hash = SHA256.hash(data: Data(key.utf8)).compactMap { String(format: "%02x", $0) }.joined()
        return directory.appendingPathComponent(hash)
    }

    private func isExpired(key: String) -> Bool {
        let expiryPath = filePath(for: key).appendingPathExtension("expiry")
        guard let data = try? Data(contentsOf: expiryPath),
              let expiry = try? JSONDecoder().decode(Date.self, from: data) else {
            return false   // no expiry info — treat as not expired
        }
        return Date() > expiry
    }
}
```

### URLCache (HTTP Response Caching)

`URLCache` respects `Cache-Control` and `ETag` headers automatically:

```swift
// Configure URLSession with a persistent URLCache
let configuration = URLSessionConfiguration.default
configuration.urlCache = URLCache(
    memoryCapacity: 10 * 1024 * 1024,   // 10 MB memory
    diskCapacity: 100 * 1024 * 1024,    // 100 MB disk
    diskPath: "api_cache"
)
configuration.requestCachePolicy = .returnCacheDataElseLoad  // offline-first
// or: .useProtocolCachePolicy (respects Cache-Control headers)

let session = URLSession(configuration: configuration)
```

**Cache-Control header strategies:**

| Header | Behaviour |
|--------|-----------|
| `Cache-Control: max-age=300` | Cache for 5 minutes |
| `Cache-Control: no-store` | Never cache |
| `Cache-Control: no-cache` | Cache but always revalidate |
| `ETag: "abc123"` + `If-None-Match` | Conditional GET — 304 Not Modified if unchanged |
| `Last-Modified` + `If-Modified-Since` | Alternative conditional GET |

### Cache Invalidation Strategies

| Strategy | Description | Use When |
|----------|-------------|----------|
| TTL (Time-to-Live) | Cache expires after N seconds | API data that changes infrequently |
| Event-based | Invalidate on write (`POST`/`PUT`/`DELETE`) | Data the user can modify |
| ETag revalidation | Conditional GET; 304 if unchanged | Large responses where bandwidth matters |
| Cache version | Append version to cache key; bump version to invalidate all | Design system assets, app configuration |
| Manual purge | `URLCache.shared.removeAllCachedResponses()` | User logout, account switch |

### Cursor-Based Pagination

Preferred over offset pagination for mobile feeds. The server returns a `nextCursor` (an opaque token representing the position in the result set).

```swift
// Server response for a paginated feed
struct FeedPage: Decodable {
    let articles: [Article]
    let nextCursor: String?     // nil = no more pages
    let totalCount: Int?        // optional — for display ("1,234 results")
}

// Pagination state machine
actor PaginationController<Item: Decodable> {
    private let pageSize = 20
    private var cursor: String? = nil    // nil = fetch first page
    private var isFetching = false
    private(set) var hasMore = true
    private(set) var items: [Item] = []

    private let fetch: (String?) async throws -> (items: [Item], nextCursor: String?)

    init(fetch: @escaping (String?) async throws -> (items: [Item], nextCursor: String?)) {
        self.fetch = fetch
    }

    func loadNextPage() async throws {
        guard !isFetching, hasMore else { return }
        isFetching = true
        defer { isFetching = false }

        let result = try await fetch(cursor)
        items.append(contentsOf: result.items)
        cursor = result.nextCursor
        hasMore = result.nextCursor != nil
    }

    func reset() {
        cursor = nil
        hasMore = true
        items = []
    }
}
```

### Prefetching

Load the next page before the user reaches the bottom:

```swift
// UICollectionView prefetching
extension FeedViewController: UICollectionViewDataSourcePrefetching {
    func collectionView(_ collectionView: UICollectionView,
                        prefetchItemsAt indexPaths: [IndexPath]) {
        let lastVisible = collectionView.indexPathsForVisibleItems
            .map { $0.item }
            .max() ?? 0
        let totalItems = viewModel.items.count

        // Load next page when within 5 items of the end
        if lastVisible > totalItems - 5 {
            Task { try? await viewModel.loadNextPage() }
        }
    }
}

// SwiftUI: use .task(id:) or .onAppear on the last item
struct ArticleListView: View {
    @StateObject private var viewModel: FeedViewModel

    var body: some View {
        LazyVStack {
            ForEach(viewModel.articles) { article in
                ArticleRow(article: article)
                    .onAppear {
                        if article.id == viewModel.articles.last?.id {
                            Task { try? await viewModel.loadNextPage() }
                        }
                    }
            }
            if viewModel.isLoading {
                ProgressView()
            }
        }
    }
}
```

### Image Pipeline Architecture

A production image pipeline: URL → memory cache → disk cache → network download → decode → memory cache update.

```swift
import UIKit

// Thread-safe image loader with request coalescing
// (multiple requests for the same URL share one network call)
actor ImageLoader {
    private let memoryCache = ImageCache()
    private let diskCache = DiskCache(name: "images")
    private var inFlightTasks: [URL: Task<UIImage, Error>] = [:]

    func image(for url: URL) async throws -> UIImage {
        // 1. Memory cache
        if let cached = memoryCache.image(for: url) { return cached }

        // 2. Coalesce: reuse in-flight task
        if let task = inFlightTasks[url] { return try await task.value }

        // 3. Create new load task
        let task = Task<UIImage, Error> {
            // Check disk cache first
            if let data = await diskCache.read(key: url.absoluteString),
               let image = UIImage(data: data) {
                memoryCache.setImage(image, for: url)
                return image
            }

            // Network download
            let (data, _) = try await URLSession.shared.data(from: url)

            // Downsample to display size (avoid decoding a 4K image for a 44pt thumbnail)
            let image = try downsample(data: data, to: CGSize(width: 200, height: 200))

            // Cache
            await diskCache.write(data, key: url.absoluteString, ttl: 86400)
            memoryCache.setImage(image, for: url)
            return image
        }

        inFlightTasks[url] = task
        defer { inFlightTasks[url] = nil }

        return try await task.value
    }

    private func downsample(data: Data, to size: CGSize) throws -> UIImage {
        let options: [CFString: Any] = [
            kCGImageSourceShouldCache: false,
            kCGImageSourceShouldAllowFloat: false
        ]
        guard let source = CGImageSourceCreateWithData(data as CFData, options as CFDictionary) else {
            throw ImageError.invalidData
        }
        let maxPixel = max(size.width, size.height) * UIScreen.main.scale
        let thumbOptions: [CFString: Any] = [
            kCGImageSourceThumbnailMaxPixelSize: maxPixel,
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true
        ]
        guard let cgImage = CGImageSourceCreateThumbnailAtIndex(source, 0, thumbOptions as CFDictionary) else {
            throw ImageError.thumbnailFailed
        }
        return UIImage(cgImage: cgImage)
    }

    enum ImageError: Error { case invalidData, thumbnailFailed }
}
```

## 4. Practical Usage

```swift
// ── Complete feed ViewModel with pagination + caching ─────────
import SwiftUI
import Combine

@MainActor
final class FeedViewModel: ObservableObject {
    @Published private(set) var articles: [Article] = []
    @Published private(set) var isLoading = false
    @Published private(set) var error: Error?

    private let repository: ArticleRepository
    private let cache: ResponseCache
    private var pagination: PaginationController<Article>!

    init(repository: ArticleRepository, cache: ResponseCache) {
        self.repository = repository
        self.cache = cache
        self.pagination = PaginationController { [weak self] cursor in
            guard let self else { return ([], nil) }
            return try await self.repository.fetchPage(cursor: cursor)
        }
    }

    func loadInitialPage() async {
        // Show cached data immediately
        if let cached = await cache.cachedArticles() {
            articles = cached
        }

        isLoading = true
        defer { isLoading = false }

        do {
            await pagination.reset()
            try await pagination.loadNextPage()
            articles = await pagination.items
            await cache.cacheArticles(articles)
        } catch {
            self.error = error
        }
    }

    func loadNextPage() async {
        guard !isLoading else { return }
        do {
            try await pagination.loadNextPage()
            articles = await pagination.items
        } catch {
            self.error = error
        }
    }

    func refresh() async {
        await cache.invalidate()
        await loadInitialPage()
    }
}

// Placeholder types
protocol ArticleRepository {
    func fetchPage(cursor: String?) async throws -> (items: [Article], nextCursor: String?)
}
actor ResponseCache {
    func cachedArticles() -> [Article]? { nil }
    func cacheArticles(_ articles: [Article]) {}
    func invalidate() {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between offset pagination and cursor pagination?**

A: **Offset pagination** uses `page=2&limit=20` or `offset=20&limit=20`. The server skips the first N rows and returns the next batch. Problems: (1) if new items are inserted at the top between page fetches, items shift and the user sees duplicates or skips items; (2) large offsets are expensive — the database must count and skip rows. **Cursor pagination** uses an opaque token (the cursor) representing the last seen item — e.g., the item's ID or a timestamp. The server returns all items after that cursor: `cursor=xyz&limit=20`. Advantages: (1) stable — insertions at the top don't affect subsequent pages because the server returns items relative to the cursor, not an offset; (2) efficient — the cursor can be an indexed primary key, making the query fast regardless of position. Disadvantage: you cannot jump to an arbitrary page (no "go to page 5"). For mobile feeds, cursor pagination is always preferred: the user scrolls linearly, page-jumping isn't needed, and stability under live updates is critical.

**Q: When should you use `NSCache` vs a disk cache?**

A: Use **`NSCache`** for: data that's expensive to compute but cheap to re-fetch (decoded images, parsed JSON), data that doesn't need to survive app restart (session-lived), and when automatic eviction under memory pressure is acceptable. `NSCache` lives in memory — fastest access but lost on launch or memory warning. Use a **disk cache** for: data that must survive app restart (feed content for offline-first, user preferences, downloaded assets), data that's expensive or slow to fetch from the network, and content that should be available immediately on next launch (avoiding a loading state). The cost of a disk cache is I/O latency for reads/writes. A production app uses both: memory cache for the session, disk cache for persistence. The typical read path is: memory → disk → network.

### Hard

**Q: How do you invalidate disk cache correctly when the server data changes?**

A: Three strategies depending on the data type: (1) **TTL (Time-to-Live)**: associate an expiry timestamp with each cache entry. Common TTLs: user profile 5 minutes, feed articles 2 minutes, images 24 hours, config 1 hour. On read, check if the entry is expired before returning it. On expiry, return the stale entry (for immediate render) and trigger a background refresh. (2) **ETag / conditional GET**: store the `ETag` header value from the response alongside the cached data. On next request, send `If-None-Match: <etag>` — if the server returns `304 Not Modified`, use the cached data; if `200 OK`, update the cache. This is bandwidth-efficient for large, infrequently changing responses. `URLCache` handles this automatically for HTTP responses. (3) **Event-driven invalidation**: when the user performs a write (creates, updates, or deletes), invalidate the relevant cache keys immediately before the network request returns — the cache key is known (e.g., `feed/<userId>`). The next read triggers a fresh fetch. For multi-device sync, use a server-sent invalidation event (WebSocket message or silent push) to signal that the cache is stale.

**Q: How would you build an image pre-fetching system for a scrolling feed of 1,000 items?**

A: Four-component system: (1) **Prefetch trigger**: adopt `UICollectionViewDataSourcePrefetching` — `prefetchItemsAt` is called with upcoming index paths as the user scrolls. Extract the image URLs for those items and enqueue download tasks. In `cancelPrefetchingForItemsAt`, cancel tasks for items scrolled past. (2) **Prioritised task queue**: use an `actor`-based `ImageLoader` with a priority queue — items close to the visible area get `.userInitiated` QoS; prefetch items get `.utility`. Limit concurrent downloads to 3–5 (configurable) to avoid network saturation. (3) **Request coalescing**: if the same URL is requested multiple times (same image appears in multiple cells), the `ImageLoader` deduplicates by URL — one network request, multiple waiters via `Task.value`. (4) **Cancellation**: each cell's prefetch request is wrapped in a `Task` stored keyed by index path. When the cell is reused, cancel the old task before starting a new one. Memory budget: `NSCache` with `totalCostLimit = 50MB` (cost = pixel count × 4 bytes). Images outside the visible window + 50 items above/below are eligible for eviction.

### Expert

**Q: Design a caching strategy for a social media app where feed content is real-time (new posts every few seconds) but the cache must provide instant rendering on cold launch.**

A: Five-layer strategy: (1) **Layered cache with explicit TTLs**: memory cache TTL = 30 seconds (fastest path, acceptable for real-time feed — 30s stale is imperceptible); disk cache TTL = 5 minutes (for cold launch); both layers store the full feed page including images URLs. (2) **Cold launch render from disk**: on app cold launch, before any network request, read the last cached feed page from disk and render it immediately. Users see content within 100ms, no loading spinner. Stale indicator ("Updated 3 minutes ago") shown. (3) **Concurrent refresh**: immediately after rendering cached content, fetch the latest feed page. On response, merge new posts at the top using `DiffableDataSource` — existing cells stay in place, new cells are inserted with animation. (4) **Real-time updates via WebSocket**: once the feed is visible, subscribe to a WebSocket channel for the user's feed. New posts arrive as events — prepend to the local store and update the UI. No polling needed while the app is in the foreground. (5) **Cache invalidation on background**: use a background URLSession task (triggered by silent push) to refresh the disk cache while the app is suspended. The next cold launch shows content that's at most the push delivery delay (seconds) stale, rather than 5 minutes stale. Image prefetching: prefetch images for the first 10 feed items immediately after the disk cache render, using the `ImageLoader` actor at `.userInitiated` priority.

## 6. Common Issues & Solutions

**Issue: Paginated feed shows duplicate items when the user pulls-to-refresh mid-scroll.**

Solution: Pull-to-refresh must reset the `PaginationController` (clear items, reset cursor to `nil`) before fetching the first page. If the user has already loaded 3 pages (60 items) and pulls-to-refresh, the controller is reset, a fresh first page (20 items) is fetched, and `items` is set to those 20 items — replacing the previous 60. Use `DiffableDataSource` to apply the new snapshot; it handles the deletion and insertion animation automatically without UICollectionView crashes.

**Issue: NSCache grows unbounded when caching decoded images.**

Solution: `NSCache` evicts automatically under memory pressure, but only if `cost` is set correctly when inserting items. If `setObject(_:forKey:cost:)` is called with `cost = 0` (or `setObject(_:forKey:)` without cost), `totalCostLimit` has no effect — `NSCache` only evicts by count (`countLimit`). Calculate the actual cost: for `UIImage`, cost = `Int(image.size.width * image.size.height * image.scale * image.scale) * 4` (bytes). Set `totalCostLimit` to your target memory budget (e.g., 50MB). Also register for `UIApplication.didReceiveMemoryWarningNotification` and call `cache.removeAllObjects()` as a safety net.

## 7. Related Topics

- [Offline-First Architecture](offline-first-architecture.md) — repository layer above the cache
- [Performance — Memory Optimization](../12-performance/memory-optimization.md) — NSCache cost-based eviction
- [Performance — Lazy Loading](../12-performance/lazy-loading.md) — image loader actor and prefetching
- [Networking](../07-networking/index.md) — URLSession, URLCache, ETag handling
- [Data Persistence](../08-data-persistence/index.md) — disk persistence for cache entries
