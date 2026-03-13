# Lazy Loading

## 1. Overview

Lazy loading defers the creation, computation, or fetching of a resource until the moment it is first needed. On iOS, this pattern appears at multiple layers: `lazy var` properties (computed once on first access), lazy `Sequence`/`Collection` operations (transformed elements produced on demand), on-demand image loading (thumbnails downloaded as cells scroll into view), and deferred view controller instantiation (pushing a VC only when navigating). The core benefit is lower startup cost and reduced peak memory — resources that are never needed are never allocated. The tradeoff is that first-access can be slow if the deferred work is expensive; for user-visible latency this requires pairing lazy loading with **prefetching** (starting the load slightly before it's needed) and **placeholders** (showing a skeleton view while loading). The primary iOS APIs for lazy loading and prefetching are `UITableViewDataSourcePrefetching`, `UICollectionViewDataSourcePrefetching`, and Swift's `lazy` keyword.

## 2. Simple Explanation

Lazy loading is like a just-in-time warehouse. A traditional warehouse pre-stocks every shelf before opening — slow to set up, expensive, and half the stock may never be used. A just-in-time warehouse keeps shelves empty and fetches goods from the supplier only when a customer orders them. The first customer for any item waits slightly longer (the fetch), but startup is instant and nothing is wasted. Prefetching is the warehouse manager watching which shelves customers are walking toward and pre-ordering those goods 30 seconds before they arrive — eliminating the customer wait entirely.

## 3. Deep iOS Knowledge

### `lazy var` Properties

A `lazy var` is initialised on first access and the result is stored. Subsequent accesses return the stored value — the initialiser runs exactly once. The initialiser closure can reference `self` safely because `lazy` requires the enclosing type to be a `struct` or `class` (not a `let`), and `self` is fully initialised by the time the lazy property is first accessed.

```swift
lazy var expensiveObject = HeavyObject()   // created only if accessed
lazy var formattedDate: String = {          // closure form
    let f = DateFormatter(); f.dateStyle = .long
    return f.string(from: self.date)
}()
```

Limitation: `lazy var` is **not thread-safe** — two threads can both observe nil and both initialise the property. For thread-safe lazy initialisation, use `DispatchQueue.once`, a `static let` (always safe), or an actor-isolated property.

### Static `let` — Safe Lazy Singleton

`static let` in Swift is lazily initialised by the runtime on first access, and the initialisation is guaranteed to happen exactly once (thread-safe, uses `dispatch_once` under the hood). Use it for heavy shared resources:

```swift
final class ExpensiveService {
    static let shared = ExpensiveService()   // initialised on first access, thread-safe
    private init() { /* heavy setup */ }
}
```

### `lazy` Sequence Operations

Applying `.lazy` to a sequence returns a `LazySequence` wrapper that defers `map`, `filter`, `compactMap`, and other transformations until elements are consumed. See [Efficient Data Structures](efficient-data-structures.md) for complexity details. Key use case: when only a prefix of a large, transformed sequence is needed.

### On-Demand Image Loading

The canonical pattern: cells display a placeholder immediately, then load the real image asynchronously.

```swift
// Cell configuration — immediate
func configure(with post: Post) {
    thumbnailImageView.image = UIImage(named: "placeholder")
    loadThumbnail(from: post.thumbnailURL)
}

// Load on demand — cancel on reuse
var imageTask: Task<Void, Never>?

func loadThumbnail(from url: URL) {
    imageTask?.cancel()
    imageTask = Task {
        let image = await ImageLoader.shared.load(url)
        guard !Task.isCancelled else { return }
        await MainActor.run { thumbnailImageView.image = image }
    }
}

override func prepareForReuse() {
    super.prepareForReuse()
    imageTask?.cancel()
    imageTask = nil
    thumbnailImageView.image = UIImage(named: "placeholder")
}
```

### Prefetching with `UICollectionViewDataSourcePrefetching`

The prefetching delegate receives index paths for cells that are about to enter the visible area — before `cellForItemAt` is called. Use this to start loading images or data so they're ready when the cell is dequeued.

```swift
extension FeedViewController: UICollectionViewDataSourcePrefetching {

    func collectionView(_ collectionView: UICollectionView,
                        prefetchItemsAt indexPaths: [IndexPath]) {
        for indexPath in indexPaths {
            let post = posts[indexPath.item]
            ImageLoader.shared.startPrefetch(url: post.thumbnailURL)
        }
    }

    func collectionView(_ collectionView: UICollectionView,
                        cancelPrefetchingForItemsAt indexPaths: [IndexPath]) {
        for indexPath in indexPaths {
            let post = posts[indexPath.item]
            ImageLoader.shared.cancelPrefetch(url: post.thumbnailURL)
        }
    }
}
```

**Important**: prefetching is cancelled automatically when the user changes scroll direction — the cancel delegate ensures you don't waste bandwidth on images that scrolled out of the upcoming visible area.

### Lazy View Controller Loading

`UIViewController`'s `view` property is lazy — `viewDidLoad` is not called until someone accesses `vc.view`. Avoid accessing `.view` unnecessarily (it forces an eager load). In a tab bar or navigation controller with many tabs/stacks, child VCs that haven't been tapped never load their views.

In SwiftUI, `NavigationLink(destination:)` lazily creates the destination view only when the link is tapped (`NavigationStack` with `navigationDestination(for:)` is even more efficient — the destination closure is evaluated only when navigating).

### Pagination as Lazy Loading

Infinite scroll is lazy loading applied to data: fetch the first 20 items, and load the next page only when the user scrolls near the bottom.

```swift
func collectionView(_ collectionView: UICollectionView,
                    willDisplay cell: UICollectionViewCell,
                    forItemAt indexPath: IndexPath) {
    let threshold = posts.count - 5   // 5 items from the end
    if indexPath.item >= threshold && !isFetchingNextPage {
        loadNextPage()
    }
}
```

### Skeleton Screens

Skeleton screens (shimmering grey placeholders that match the expected layout) provide immediate visual feedback while lazy loading completes. They are preferable to activity spinners for content-heavy feeds because they communicate the shape of the incoming content and reduce perceived wait time.

Implementation: create a separate "skeleton" cell class with animated gradient layers using `CAGradientLayer` + `CABasicAnimation` for the shimmer.

## 4. Practical Usage

```swift
import UIKit

// ── lazy var — computed once on first access ───────────────────
final class ProfileViewController: UIViewController {

    // Heavy object — don't create it if the profile VC is never shown
    private lazy var analyticsLogger: AnalyticsLogger = {
        AnalyticsLogger(screen: .profile, userID: currentUserID)
    }()

    private var currentUserID: String = ""

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        analyticsLogger.logScreenView()   // created here, on first call
    }
}

// ── Thread-safe lazy via actor ─────────────────────────────────
actor ServiceLocator {
    private var _heavyService: HeavyService?

    var heavyService: HeavyService {
        if let s = _heavyService { return s }
        let s = HeavyService()   // initialised on first access, actor-serialised
        _heavyService = s
        return s
    }
}

// ── Lazy image loader with NSCache ────────────────────────────
actor ImageLoader {
    static let shared = ImageLoader()

    private let cache = NSCache<NSString, UIImage>()
    private var inFlightTasks: [URL: Task<UIImage?, Never>] = [:]

    func load(_ url: URL) async -> UIImage? {
        // Cache hit
        if let cached = cache.object(forKey: url.absoluteString as NSString) {
            return cached
        }
        // Coalesce concurrent requests for the same URL
        if let existing = inFlightTasks[url] {
            return await existing.value
        }
        let task = Task<UIImage?, Never> {
            guard let (data, _) = try? await URLSession.shared.data(from: url),
                  let image = UIImage(data: data)
            else { return nil }
            self.cache.setObject(image, forKey: url.absoluteString as NSString)
            return image
        }
        inFlightTasks[url] = task
        let result = await task.value
        inFlightTasks[url] = nil
        return result
    }

    func startPrefetch(url: URL) {
        guard inFlightTasks[url] == nil,
              cache.object(forKey: url.absoluteString as NSString) == nil
        else { return }
        inFlightTasks[url] = Task { await self.load(url) }
    }

    func cancelPrefetch(url: URL) {
        inFlightTasks[url]?.cancel()
        inFlightTasks[url] = nil
    }
}

// ── Skeleton cell with shimmer animation ──────────────────────
final class SkeletonCell: UICollectionViewCell {
    private let shimmerLayer = CAGradientLayer()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .systemGray6

        shimmerLayer.colors = [
            UIColor.systemGray5.cgColor,
            UIColor.systemGray4.cgColor,
            UIColor.systemGray5.cgColor
        ]
        shimmerLayer.startPoint = CGPoint(x: 0, y: 0.5)
        shimmerLayer.endPoint = CGPoint(x: 1, y: 0.5)
        shimmerLayer.locations = [0, 0.5, 1]
        layer.addSublayer(shimmerLayer)

        startShimmer()
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        shimmerLayer.frame = bounds
    }

    private func startShimmer() {
        let animation = CABasicAnimation(keyPath: "locations")
        animation.fromValue = [-1.0, -0.5, 0.0]
        animation.toValue = [1.0, 1.5, 2.0]
        animation.duration = 1.2
        animation.repeatCount = .infinity
        shimmerLayer.add(animation, forKey: "shimmer")
    }
}

// ── Lazy sequence — only compute first N matching elements ─────
func firstFeaturedPosts(_ posts: [Post], count: Int) -> [Post] {
    Array(
        posts.lazy
            .filter { $0.isFeatured && !$0.isExpired }
            .map { PostViewModel(post: $0) }   // expensive transform
            .prefix(count)
    )   // stops at `count` — does not scan the whole array
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What does the `lazy` keyword do on a stored property and what are its limitations?**

A: `lazy var` defers the property's initialisation until the first time it is read. The initialisation closure runs once; the result is stored and returned on all subsequent accesses. Practical use: avoiding the construction cost of a heavy object until (if ever) it's needed. Limitations: (1) Must be `var`, not `let` — the property mutates from nil to a value on first access. (2) Not thread-safe — if two threads simultaneously read a not-yet-initialised `lazy var`, both may run the initialiser and one result is discarded (or, in a struct, undefined behaviour). Use `static let` (which is thread-safe) for shared lazy singletons, or protect `lazy var` with a lock or actor. (3) Cannot be used in a `struct` that is itself a `let` — the mutation on first access requires a `var` binding of the enclosing struct.

**Q: What is the difference between `UICollectionViewDataSourcePrefetching.prefetchItemsAt` and `cellForItemAt`?**

A: `cellForItemAt` is called when a cell must be displayed — it is on the critical path of rendering. Anything slow here causes a dropped frame. `prefetchItemsAt` is called for index paths that are about to become visible (typically 1–2 screens ahead in the scroll direction) but haven't reached the display threshold yet. It runs off the critical path, giving you time to start asynchronous network or disk loads so that by the time `cellForItemAt` is called, the data is ready in a cache. The pair `cancelPrefetchingForItemsAt` is called if the user reverses scroll direction, telling you to cancel work for cells that no longer need to be prefetched. Together, they enable a "pre-load ahead, cancel on reversal" strategy that eliminates visible loading states during forward scrolling.

### Hard

**Q: How do you prevent a cell's image load task from displaying on the wrong cell after the cell is reused?**

A: Cell reuse is the classic stale-image bug: cell A starts loading image for row 3, is reused for row 7 while still loading, and when the image for row 3 arrives it's displayed in the cell now showing row 7. Fix in three parts: (1) **Cancel in `prepareForReuse`**: store the `Task` (or `AnyCancellable`) as a property on the cell and call `.cancel()` in `prepareForReuse`. (2) **Guard after await**: after the `await` for the image, check `Task.isCancelled` — if the task was cancelled (cell was reused), return without setting the image. (3) **Tag the request**: some implementations store the URL as a property on the cell and check at completion that `cell.currentURL == requestURL` before assigning. This is a belt-and-suspenders check for cases where cancellation is not perfectly synchronous. All three together guarantee the correct image is displayed in the correct cell with no flicker.

**Q: How does `lazy` evaluation interact with Combine and `AsyncSequence`?**

A: Combine publishers and `AsyncSequence` are inherently lazy — no work is performed until there is a subscriber or an active `for await` loop. A publisher chain `publisher.filter { }.map { }` creates no values until a subscription is established with `.sink` or `.assign`. An `AsyncSequence` with `.filter { }.map { }` evaluates no elements until the `for await in` loop iterates. This means you can construct complex transformation pipelines cheaply and conditionally start them. The practical implication: prefer lazy Combine chains or `AsyncSequence` pipelines over eagerly transforming arrays when the consumer might not need all values, or when values arrive over time. For one-shot transformations of an existing in-memory array, Swift's standard library `.lazy` is sufficient.

### Expert

**Q: Design a lazy-loading image system for a photo grid that must handle 100,000 photos, remain responsive at 60 fps, and not crash from memory pressure.**

A: Five-layer architecture: (1) **Demand-based loading**: only load images for cells within 2 screens of the current scroll position. Track visible + prefetch index ranges using `UICollectionView.indexPathsForVisibleItems` plus the prefetch delegate. Start loads for the next range; cancel loads outside the range. (2) **Two-level cache**: `NSCache<NSString, UIImage>` (in-memory, auto-evicted) as L1; filesystem cache directory as L2 (persist across launches). On a cache miss, check L2 before making a network request. (3) **Request coalescing**: the actor-based `ImageLoader` shown above deduplicates concurrent requests for the same URL — if 3 cells request the same avatar, only 1 network call is made. (4) **Thumbnail generation**: store a 200×200 thumbnail on the server per photo. Download thumbnails (small) for the grid; download full resolution only when a photo is tapped. Downscale even the thumbnail to the cell's display size using `CGImageSourceCreateThumbnailAtIndex` before storing in L1. (5) **Memory pressure response**: subscribe to `UIApplication.didReceiveMemoryWarningNotification` and call `cache.removeAllObjects()` on L1. The grid will refetch from L2 or network — slower, but no crash. `NSCache` handles Level 1 evictions automatically; Level 2 evictions are managed by the cache directory size limit (remove oldest-accessed files when > 200 MB).

## 6. Common Issues & Solutions

**Issue: Images flicker or show the wrong thumbnail when scrolling fast.**

Solution: The cell is being reused before the previous image load task is cancelled. In `prepareForReuse`, cancel the active `Task` and reset `imageView.image` to the placeholder. After `await`ing the image, check `Task.isCancelled` before assigning. Also ensure the cell's `currentURL` matches the requested URL at the assignment site.

**Issue: `lazy var` is being initialised multiple times (duplicate side effects).**

Solution: `lazy var` is not thread-safe. If the property is accessed from multiple threads simultaneously, both can observe it as unset and both run the initialiser. Fix: if the property must be computed once, use a `static let` (guaranteed once), an `actor`, or a `DispatchQueue` serialiser. If it's a UIKit property accessed only from the main thread, `lazy var` is safe because UIKit enforces single-thread access.

**Issue: Prefetch requests are being made for index paths the user never scrolls to, wasting bandwidth.**

Solution: Implement `cancelPrefetchingForItemsAt` and cancel the corresponding tasks. Also limit the look-ahead window — request at most 10 upcoming items in `prefetchItemsAt`, ignoring any more distant index paths. Sort by distance from the current scroll position if the prefetch delegate delivers a large batch at once.

## 7. Related Topics

- [Efficient Data Structures](efficient-data-structures.md) — lazy sequences, NSCache
- [Memory Optimization](memory-optimization.md) — NSCache eviction, image downsampling
- [Main Thread Optimization](main-thread-optimization.md) — async image loading offloading
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — `UICollectionViewDataSourcePrefetching`, cell reuse
- [Concurrency — async/await](../03-concurrency/async-await.md) — Task cancellation, actor-based loaders
