# Main Thread Optimization

## 1. Overview

The main thread in iOS is the only thread that drives UIKit rendering and event handling. The display system calls the app at 60 fps (16.67 ms per frame) or 120 fps on ProMotion displays (8.33 ms per frame). Any work that keeps the main thread busy longer than one frame budget produces a **hitch** — a dropped frame that users see as jank. Work on the main thread must be limited to: updating data sources, triggering layout/rendering, and processing user input. All other work — networking, JSON decoding, database queries, image decoding, cryptography, file I/O — belongs on background threads or async Swift concurrency tasks. The tools for diagnosis are Instruments' Time Profiler (main thread flame graph), Xcode's `Main Thread Checker` (catches UIKit-on-background-thread violations), and `MetricKit`'s hitch rate metric in production. The Swift concurrency tools for offloading work are `async/await`, `Task { }`, `actor`, and `Task.detached { }`.

## 2. Simple Explanation

The main thread is a single cashier at a supermarket checkout. Every 16.67 ms a new customer (a display frame) arrives. If the cashier is in the back room doing stocktaking (decoding JSON, querying a database), every customer arriving during that time waits. The longer the backroom job, the longer the queue — customers (frames) pile up and the whole checkout looks frozen. The fix is to hire backroom staff (background threads/actors) and have the cashier only do cashier work: scanning items (updating UI), accepting payment (handling taps), and printing receipts (committing layout). The backroom staff hand the cashier only the finished result.

## 3. Deep iOS Knowledge

### What Causes Main Thread Jank

| Category | Examples |
|----------|---------|
| Network I/O | `URLSession` synchronous calls (never do this) |
| Disk I/O | `Data(contentsOf:)`, `FileManager`, SQLite queries |
| JSON decoding | `JSONDecoder().decode()` on a large payload |
| Image decoding | `UIImage(data:)` — the PNG/JPEG decode happens on first draw |
| Cryptography | Hashing, encryption of large data |
| Core Data | `NSFetchRequest` on `viewContext` for large result sets |
| Layout calculation | Complex Auto Layout with O(n²) ambiguous constraints |
| Synchronous closures | `DispatchQueue.main.sync` from background thread (deadlock risk too) |

### Time Profiler: Reading the Main Thread

In Time Profiler, select the main thread lane. The flame graph shows the call stack. A wide block = long duration. The hottest frame functions are listed in the Call Tree sorted by self-time. Key signs of main-thread trouble:
- `UIApplication.sendEvent` taking > 5 ms → input handling jank.
- `CALayer.display` or `CA::Layer::display_` → expensive draw pass.
- Your own symbol with high self-time → CPU work you can offload.

### The Main Thread Checker

Enable in scheme: Edit Scheme → Run → Diagnostics → **Main Thread Checker**. It crashes the app (in Debug builds) when UIKit or AppKit APIs are called off the main thread — catching threading mistakes at development time rather than in production.

### Offloading with async/await

The canonical pattern: mark the async function with `nonisolated` or place it in an actor, do the work there, then update `@MainActor`-bound state.

```swift
@MainActor
final class FeedViewModel: ObservableObject {
    @Published var posts: [Post] = []
    @Published var isLoading = false

    func loadFeed() async {
        isLoading = true
        // Jump off main thread to decode + transform
        let decoded = await Task.detached(priority: .userInitiated) {
            let data = try? Data(contentsOf: Bundle.main.url(forResource: "feed", withExtension: "json")!)
            return (try? JSONDecoder().decode([Post].self, from: data ?? Data())) ?? []
        }.value
        // Back on @MainActor — safe to write @Published
        posts = decoded
        isLoading = false
    }
}
```

### Actor Isolation

A `nonisolated` free function or a non-`@MainActor` `actor` runs on the cooperative thread pool, not the main thread. Use actors to encapsulate background work with safe state:

```swift
actor ImageProcessor {
    func decode(_ data: Data) -> UIImage? {
        UIImage(data: data)   // runs on cooperative pool, not main thread
    }
}
```

Calling `await imageProcessor.decode(data)` from a `@MainActor` function:
1. Suspends the main thread (not blocks — no frame is dropped).
2. Schedules `decode` on the cooperative pool.
3. Resumes on the main thread with the result.

### Grand Central Dispatch (pre-Swift-Concurrency)

For legacy code or when integrating with callback-based APIs:

```swift
DispatchQueue.global(qos: .userInitiated).async {
    let result = expensiveComputation()
    DispatchQueue.main.async {
        self.label.text = result   // must update UI on main thread
    }
}
```

Avoid `DispatchQueue.global().sync` on the main thread — it blocks the main thread for the duration, causing jank.

### Identifying Layout Bottlenecks

Auto Layout's constraint solver is O(n) for most layouts but can degrade to O(n²) for ambiguous or conflicting constraints. Profile with the **Time Profiler** + filter for `UIView.layoutSubviews` and `NSISEngine`. If layout takes > 2 ms per frame, consider:
- Replacing `UIStackView` with manual frame-based layout for cells (especially in UITableView with 1000+ rows).
- Reducing constraint count per cell (10–20 constraints is fine; 50+ may cause layout pass spikes).
- Using `UIView.invalidateIntrinsicContentSize()` instead of adding/removing constraints dynamically.

### Hitch Rate (MetricKit)

A **hitch** is any frame that takes longer than its display deadline. MetricKit's `MXAnimationMetric` reports the **hitch time ratio** — total hitch time divided by total animation time. Industry benchmark:
- < 1 ms/s: excellent (imperceptible)
- 1–5 ms/s: good
- 5–10 ms/s: noticeable
- > 10 ms/s: poor (users will complain)

## 4. Practical Usage

```swift
import UIKit
import SwiftUI

// ── Pattern 1: Decode JSON off main thread ─────────────────────
@MainActor
final class ArticleListViewModel: ObservableObject {
    @Published var articles: [Article] = []

    private let decoder = JSONDecoder()

    func loadArticles(data: Data) async {
        // Task.detached escapes the current actor (main) to the pool
        let result = await Task.detached(priority: .userInitiated) { [decoder] in
            try? decoder.decode([Article].self, from: data)
        }.value
        articles = result ?? []   // @MainActor — safe
    }
}

// ── Pattern 2: Async image decoding actor ─────────────────────
actor ImageDecoder {
    private var cache: [URL: UIImage] = [:]

    func decode(from url: URL) async -> UIImage? {
        if let cached = cache[url] { return cached }

        guard let data = try? Data(contentsOf: url) else { return nil }
        let image = UIImage(data: data)   // decode runs on cooperative thread pool
        cache[url] = image
        return image
    }
}

// Usage in a @MainActor view model:
// let image = await imageDecoder.decode(from: url)
// self.thumbnail = image    // safe — back on main actor

// ── Pattern 3: Background Core Data fetch ─────────────────────
// Use a background NSManagedObjectContext — never fetch on viewContext
// with a large result set from the main thread
final class PostRepository {
    private let container: NSPersistentContainer

    init(container: NSPersistentContainer) {
        self.container = container
    }

    func fetchAll() async throws -> [Post] {
        try await withCheckedThrowingContinuation { continuation in
            // newBackgroundContext() is off main thread
            let context = container.newBackgroundContext()
            context.perform {
                do {
                    let request = PostMO.fetchRequest()
                    request.fetchBatchSize = 50
                    let results = try context.fetch(request)
                    let posts = results.map { Post(from: $0) }   // map to value types
                    continuation.resume(returning: posts)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}

// ── Pattern 4: Serialised background work with an actor ───────
actor DataProcessor {
    private var buffer: [String] = []

    // All calls to append/flush are serialised by actor isolation
    func append(_ item: String) {
        buffer.append(item)
    }

    func flush() -> [String] {
        defer { buffer.removeAll(keepingCapacity: true) }
        return buffer
    }
}

// ── Pattern 5: Avoid blocking main thread with large string ops
extension String {
    /// Expensive regex matching — never call on main thread for large strings
    func matches(pattern: String) async -> Bool {
        await Task.detached(priority: .utility) {
            (try? NSRegularExpression(pattern: pattern))
                .map { $0.firstMatch(in: self, range: NSRange(self.startIndex..., in: self)) != nil }
                ?? false
        }.value
    }
}

// ── Pattern 6: Throttle expensive main-thread callbacks ───────
final class SearchViewController: UIViewController {
    private var searchTask: Task<Void, Never>?

    func searchTextChanged(_ query: String) {
        searchTask?.cancel()   // cancel previous search
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 300_000_000)   // 300ms debounce
            guard !Task.isCancelled else { return }
            let results = await performSearch(query: query)
            await MainActor.run { self.displayResults(results) }
        }
    }

    private func performSearch(query: String) async -> [SearchResult] {
        await Task.detached(priority: .userInitiated) {
            // heavy search logic off main thread
            return []
        }.value
    }

    private func displayResults(_ results: [SearchResult]) {
        // Update UI — on main thread
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the 16 ms rule and why does violating it cause visible jank?**

A: At 60 fps, the display hardware expects a new rendered frame every 16.67 ms. The display system's CA (Core Animation) commit phase runs at the end of the run loop iteration on the main thread. If the main thread is busy with non-UI work and can't commit the frame within 16.67 ms, the previous frame is displayed again — a duplicated frame, visible as a momentary freeze (jank or stutter). On ProMotion (120 Hz) displays, the budget is halved to 8.33 ms. Violating it even by 1 ms causes a hitch. The Instruments Time Profiler shows this as the main thread flame graph exceeding the 16 ms horizontal marker in the timeline.

**Q: What is the difference between `Task.detached` and `Task { }` regarding thread affinity?**

A: `Task { }` inherits the actor context of its enclosing scope. If called from a `@MainActor` function, the task runs on the main actor (main thread). This is usually what you want for updating UI — but it means CPU-heavy work inside a `Task { }` called from `@MainActor` still runs on the main thread. `Task.detached { }` explicitly breaks actor inheritance — it runs on the Swift cooperative thread pool with no actor context. Use `Task.detached` when you want to guarantee that heavy computation runs off the main thread, regardless of where it was started. The tradeoff: `Task.detached` captures nothing implicitly, so you must explicitly capture `[weak self]` or copy value parameters.

### Hard

**Q: How do you offload image decoding from the main thread in a UICollectionView that displays hundreds of photos?**

A: UIImage decoding (decompressing JPEG/PNG bytes to a bitmap) is deferred by default — it happens on the main thread during the first draw pass of the `UIImageView`. This causes jank when cells appear on screen. The solution: decode images on a background thread before they reach the cell. Pattern: (1) In `prefetchItemsAt indexPaths`, start a `Task.detached` for each upcoming cell's image URL that decodes the `UIImage` off-thread using `UIGraphicsImageRenderer` or `CGImageSourceCreateThumbnailAtIndex`. (2) Cache the decoded `UIImage` in `NSCache`. (3) In `cellForItemAt`, check the cache — if available, set directly; if not, set a placeholder and start a decode task. (4) In `prepareForReuse`, cancel the in-flight decode task using `task.cancel()`. With this pattern, visible cells get pre-decoded images from cache and the main thread never blocks for decode. Apple's recommendation: use `UIImage.prepareThumbnail(of:completionHandler:)` (iOS 15+) which does this automatically.

**Q: How do you detect that a specific async function is accidentally running on the main thread?**

A: Three techniques: (1) **`MainActor.assertIsolated()`** (Swift 5.9+): call this inside any function that must NOT run on the main actor — it traps if it's unexpectedly isolated to the main actor. (2) **`Thread.isMainThread` assertion**: `assert(!Thread.isMainThread, "Must not run on main thread")` — fires in Debug builds. (3) **Time Profiler**: capture a trace, filter the main thread's call tree, and look for your function symbol. If it appears there, it's running on the main thread. For structured concurrency, use `nonisolated` on functions that should not inherit actor isolation, and place heavy-computation functions in a `nonisolated actor` or `Task.detached`.

### Expert

**Q: Design a strategy for ensuring a feature that aggregates data from three APIs and one database query renders without dropping frames on a 120Hz ProMotion display.**

A: An 8.33 ms budget requires everything except the final UI update to be off the main thread. Strategy: (1) **Concurrent fetching**: launch the three API calls and the database query as concurrent `async let` expressions inside a `Task.detached`, so all four run in parallel on the cooperative pool. (2) **Result aggregation off-thread**: still inside the detached task, merge and transform the four results into the final view model struct (a value type). JSON decoding and data transformation stay off-thread. (3) **Single main-thread commit**: after the detached task resolves, `await MainActor.run { viewModel = result }` — a single, cheap assignment. This triggers at most one `objectWillChange` and one body re-evaluation in SwiftUI. (4) **Pre-computed layout**: if the view requires complex layout measurement (e.g., variable-height cells), compute heights as part of the background transformation step and include them in the view model struct. Layout pass on the main thread then becomes a direct frame assignment — O(1). (5) **`CATransaction.disableActions`** for batch updates: wrap the final UI update in `CATransaction.begin()` / `disableActions = true` / `CATransaction.commit()` to suppress implicit animations on the batch, preventing multiple animation frames from being scheduled at once.

## 6. Common Issues & Solutions

**Issue: `UIImage` loading causes visible stutter when cells appear.**

Solution: UIImage decoding is lazy — it happens on the first draw call on the main thread. Pre-decode images on a background thread: `UIImage.prepareThumbnail(of: targetSize) { image in DispatchQueue.main.async { cell.imageView.image = image } }` (iOS 15+). For older iOS: use `UIGraphicsImageRenderer` in a `Task.detached` to draw the image to a new context (forcing decode), then pass the resulting pre-decoded image to the cell.

**Issue: App is responsive between scrolls but freezes when the user stops scrolling.**

Solution: This is often a batch database write or JSON serialisation that fires when the user stops — triggered by an `NSFetchedResultsController` delegate callback or a `UserDefaults.synchronize()` call. Profile with Time Profiler while reproducing the freeze: filter for the main thread and look for disk I/O or SQLite symbols. Move all persistence writes to a background context or `actor`.

**Issue: `@MainActor` annotation isn't preventing background-thread UIKit calls.**

Solution: `@MainActor` enforces isolation at the Swift type-system level — calling non-`@MainActor` legacy code (Objective-C delegates, completion handlers that arrive on arbitrary threads) bypasses it. Audit every completion handler and delegate method: wrap the UI-updating code in `Task { @MainActor in ... }` or `DispatchQueue.main.async`. Enable the **Main Thread Checker** in scheme diagnostics to catch violations at runtime during development.

## 7. Related Topics

- [Instruments & Profiling](instruments-profiling.md) — Time Profiler to identify main-thread bottlenecks
- [async/await](../03-concurrency/async-await.md) — Task, Task.detached, MainActor
- [Actors](../03-concurrency/actors.md) — actor isolation and the cooperative thread pool
- [App Startup & Runtime — RunLoop](../13-app-startup/index.md) — RunLoop mechanics and main thread scheduling
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — prefetching and cell configuration
