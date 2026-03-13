# Efficient Data Structures

## 1. Overview

Choosing the right data structure is the highest-leverage algorithmic optimisation available on iOS. The standard library provides `Array`, `Set`, `Dictionary`, and their ordered/sorted variants — each with fundamentally different time complexity for lookup, insertion, deletion, and iteration. Beyond choosing the right abstraction, iOS and Swift offer several performance-specialised types: `ContiguousArray` (guaranteed contiguous storage for non-Objective-C-bridgeable types), `NSCache` (memory-pressure-aware key-value store), lazy sequences (defer computation until elements are consumed), and `ArraySlice` / `Substring` (zero-copy views into existing storage). Understanding when to use each — and what operations are O(1) vs O(n) — prevents algorithmic bottlenecks that no amount of threading can fix.

## 2. Simple Explanation

A data structure is a filing cabinet. An `Array` is a single drawer where files are ordered left-to-right — finding a file by position is instant (open drawer, count to slot 3), but finding a file by name means reading every file from the beginning. A `Dictionary` is a cabinet with alphabetic dividers — finding a file by name is near-instant (go to the right divider), but the files aren't in any meaningful order. A `Set` is a cabinet where duplicate files are simply rejected — checking "does this file exist?" is instant, and you're guaranteed uniqueness. Choosing the wrong cabinet for the job means doing unnecessary work on every operation.

## 3. Deep iOS Knowledge

### Complexity Comparison

| Operation | Array | Set | Dictionary | Sorted Array |
|-----------|-------|-----|------------|--------------|
| Lookup by index | O(1) | — | — | O(1) |
| Lookup by value/key | O(n) | O(1) avg | O(1) avg | O(log n) |
| Insert at end | O(1) amortised | O(1) avg | O(1) avg | O(log n) |
| Insert at index | O(n) | — | — | O(n) |
| Delete by index | O(n) | — | — | O(n) |
| Delete by value/key | O(n) | O(1) avg | O(1) avg | O(log n) |
| Iteration | O(n) | O(n) | O(n) | O(n) |
| Contains | O(n) | O(1) avg | O(1) avg | O(log n) |

### Array

`Array<T>` stores elements contiguously in heap memory (one allocation). This makes sequential access cache-friendly — the CPU prefetcher loads the next elements automatically. Strengths: O(1) indexed access, O(1) amortised append, excellent cache locality for iteration.

Weaknesses: O(n) `contains`, O(n) insert/delete in the middle.

`ContiguousArray<T>`: identical to `Array` but guarantees contiguous storage even for `AnyObject` (regular `Array<AnyObject>` can fall back to `NSArray` internally). Use `ContiguousArray` for arrays of protocol types or class instances in hot paths where you need the contiguity guarantee:

```swift
var items: ContiguousArray<Renderable> = []   // guaranteed contiguous, no NSArray bridge
```

`ArraySlice<T>`: a zero-copy window into an `Array`'s storage. Create with `array[2..<10]`. Avoids copying a sub-array for algorithms that only read a range. Note: `ArraySlice` retains the backing `Array` — release it when done to avoid keeping the full array alive.

### Set

`Set<T: Hashable>` uses a hash table internally. Average O(1) for `insert`, `remove`, and `contains`. Use `Set` whenever you need: (1) fast membership testing, (2) deduplication, (3) set operations (`union`, `intersection`, `subtracting`).

Hash collisions degrade `Set` to O(n) in the worst case — use well-distributed hash functions. The Swift standard library types (`String`, `Int`, `UUID`) have good hash distributions.

### Dictionary

`Dictionary<Key: Hashable, Value>` maps keys to values with O(1) average for all keyed operations. Use it for: lookup tables, memoisation/caching, grouping, and any "find by identifier" pattern.

Performance tip: pre-size a `Dictionary` when the capacity is known: `Dictionary(minimumCapacity: 1000)`. This avoids multiple rehash/reallocation cycles during bulk insertion.

### NSCache

`NSCache<KeyType, ObjectType>` is a thread-safe, memory-pressure-aware dictionary for caches. It automatically evicts objects when the system is under memory pressure (unlike `Dictionary`, which never evicts). Use `NSCache` for any in-memory cache of recomputable or re-fetchable data.

```swift
let cache = NSCache<NSString, UIImage>()
cache.countLimit = 100          // max 100 objects
cache.totalCostLimit = 50 * 1024 * 1024   // 50 MB
```

Note: `NSCache` does not call `copy` on keys (unlike `NSDictionary`) and its entries can be removed at any time — do not store authoritative state in it.

### Lazy Sequences

Swift's `LazySequence` (via `.lazy`) defers element computation until iteration. Each element is computed on demand rather than materialising the full transformed collection upfront.

```swift
let heavy = largeArray
    .lazy
    .filter { $0.isEligible }   // no allocation yet
    .map { $0.expensiveTransform() }   // no computation yet

for item in heavy.prefix(10) {
    process(item)   // only 10 elements computed and allocated
}
```

Use lazy when: the downstream consumer doesn't need all elements (e.g., `.first(where:)`, `.prefix(n)`), when the transformation is expensive, or when the source is infinite.

### Ordered Collections (Swift Collections package)

Apple's `swift-collections` package provides:

- `OrderedSet<T>`: maintains insertion order + O(1) `contains`. Use for a deduplicated, ordered list (e.g., recently-viewed items).
- `OrderedDictionary<Key, Value>`: insertion-order dictionary.
- `Deque<T>`: double-ended queue — O(1) prepend and append. Use instead of `Array` when you frequently insert at the front.

### Choosing for Common iOS Patterns

| Pattern | Recommended structure |
|---------|-----------------------|
| Feed posts list | `Array<PostViewModel>` — ordered, indexed by position |
| Selected items tracking | `Set<PostID>` — O(1) toggle + contains |
| User profile lookup by ID | `[UserID: User]` Dictionary |
| Recent searches (dedup + order) | `OrderedSet<String>` |
| In-memory image cache | `NSCache<NSString, UIImage>` |
| Front-of-queue notification | `Deque<Notification>` |
| Read-only sub-range processing | `ArraySlice<Post>` |

## 4. Practical Usage

```swift
import Collections   // swift-collections package

// ── Wrong: O(n) lookup in a hot path ──────────────────────────
let selectedIDs: [String] = ["1", "3", "7"]

func isSelected(_ id: String) -> Bool {
    selectedIDs.contains(id)   // O(n) — scans entire array each call
}

// ── Right: O(1) lookup with Set ───────────────────────────────
var selectedIDSet: Set<String> = ["1", "3", "7"]

func isSelected(_ id: String) -> Bool {
    selectedIDSet.contains(id)   // O(1) hash lookup
}

// ── Grouping posts by category (Dictionary) ───────────────────
struct Post { let id: String; let category: String; let title: String }

func groupByCategory(_ posts: [Post]) -> [String: [Post]] {
    // Dictionary(grouping:by:) — single pass, O(n)
    Dictionary(grouping: posts, by: \.category)
}

// ── Lazy filtering of a large dataset ─────────────────────────
func firstMatchingPost(in posts: [Post], predicate: (Post) -> Bool) -> Post? {
    // .lazy stops after first match — no full array transformation
    posts.lazy.first(where: predicate)
}

// ── ContiguousArray for protocol-type collections ─────────────
protocol Renderable { func render() }

// Guaranteed contiguous; avoids Array<AnyObject> NSArray bridging overhead
var renderables: ContiguousArray<any Renderable> = []

func renderAll() {
    renderables.withUnsafeBufferPointer { buffer in
        for item in buffer { item.render() }   // hot loop — contiguous memory
    }
}

// ── NSCache with cost-based eviction ──────────────────────────
final class ThumbnailCache {
    private let cache = NSCache<NSString, UIImage>()

    init() {
        cache.totalCostLimit = 30 * 1024 * 1024   // 30 MB
    }

    func store(_ image: UIImage, for key: String) {
        let pixelCount = Int(image.size.width * image.size.height * image.scale * image.scale)
        let byteCost = pixelCount * 4   // 4 bytes per RGBA pixel
        cache.setObject(image, forKey: key as NSString, cost: byteCost)
    }

    func image(for key: String) -> UIImage? {
        cache.object(forKey: key as NSString)
    }
}

// ── Deque for a bounded recent-actions buffer ─────────────────
var recentActions: Deque<UserAction> = []
let maxHistory = 50

func record(_ action: UserAction) {
    recentActions.prepend(action)   // O(1) — Deque, not Array
    if recentActions.count > maxHistory {
        recentActions.removeLast()  // O(1)
    }
}

// vs. Array: prepend is O(n) because all elements shift right

// ── Pre-sized Dictionary for bulk operations ───────────────────
func buildLookup(from posts: [Post]) -> [String: Post] {
    var lookup = Dictionary<String, Post>(minimumCapacity: posts.count)
    for post in posts { lookup[post.id] = post }
    return lookup   // no rehashing during build
}

// ── ArraySlice for divide-and-conquer without copying ─────────
func mergeSort(_ array: inout [Int]) {
    guard array.count > 1 else { return }
    let mid = array.count / 2
    var left = Array(array[..<mid])    // copy only at recursion base
    var right = Array(array[mid...])
    mergeSort(&left); mergeSort(&right)
    array = merge(left, right)
}

func processInBatches(_ items: [Post], batchSize: Int) {
    var index = items.startIndex
    while index < items.endIndex {
        let end = items.index(index, offsetBy: batchSize, limitedBy: items.endIndex) ?? items.endIndex
        let batch: ArraySlice<Post> = items[index..<end]   // zero-copy view
        processBatch(batch)
        index = end
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: When should you use a `Set` instead of an `Array` in Swift?**

A: Use `Set<T>` when (1) you need O(1) `contains` checks — testing membership in a `Set` is a hash lookup whereas `Array.contains` is a linear scan; (2) you want uniqueness guaranteed — `Set` silently ignores duplicate insertions; (3) you need set algebra — `union`, `intersection`, `subtracting`, `symmetricDifference` are built in and efficient. Use `Array` when order matters, when elements are accessed by index, or when you need duplicate elements. A common performance mistake: using an `Array` as a "list of selected IDs" and calling `contains` inside a `cellForRow` — O(n) per cell. Replace with `Set<ID>` for O(1) per cell.

**Q: What is `NSCache` and how does it differ from a `Dictionary` used as a cache?**

A: `NSCache` is a thread-safe, memory-pressure-aware collection. It differs from `Dictionary` in three ways: (1) **Auto-eviction**: `NSCache` automatically removes objects when the system is under memory pressure — `Dictionary` never evicts. (2) **Thread safety**: `NSCache` can be read and written concurrently without a lock — `Dictionary` is not thread-safe. (3) **Cost-based eviction**: you can assign a cost to each object (e.g., byte size) and set a `totalCostLimit`; eviction removes high-cost objects first. The downside: `NSCache` may evict any object at any time — treat its contents as ephemeral and always be prepared to recompute or re-fetch.

### Hard

**Q: What is the performance difference between `Array<AnyObject>` and `ContiguousArray<AnyObject>`, and when does it matter?**

A: `Array<T>` in Swift can bridge to `NSArray` when `T` is a class type or `AnyObject`, which may store elements in a non-contiguous, Objective-C-managed buffer. `ContiguousArray<T>` always stores elements in a Swift-managed contiguous buffer — no Objective-C bridging, no `NSArray` overhead. In practice, for pure Swift code accessing elements in a tight loop, `ContiguousArray` can be measurably faster (avoiding bridge overhead on each element access) when `T` is a class or protocol type. For `Array<Int>` or `Array<String>`, there's no difference because these are not `AnyObject`. The difference matters in rendering pipelines or physics engines where you're iterating over thousands of protocol-typed objects per frame.

**Q: How does lazy evaluation in Swift sequences improve performance, and what are its limitations?**

A: Lazy sequences (`array.lazy.filter { }.map { }`) defer computation — elements are produced and transformed only when consumed by the terminal operation (`forEach`, `first(where:)`, `prefix(n)`, `reduce`). Benefits: (1) **No intermediate allocations**: a non-lazy `filter` + `map` chain allocates two intermediate arrays; lazy allocates none. (2) **Early termination**: `array.lazy.filter { }.first` stops at the first match; non-lazy `filter` processes the entire array first. (3) **Infinite sequences**: lazy enables working with `sequence(first:next:)` infinite generators. Limitations: (1) Lazy sequences are re-evaluated on each iteration — if you iterate twice, the transformations run twice. Store the result if you need it multiple times. (2) Lazy is not always faster for full iterations — the per-element function call overhead can exceed the allocation savings for small arrays. (3) Debugging is harder — breakpoints inside lazy closures behave unexpectedly.

### Expert

**Q: Design the data model and lookup strategy for a real-time messaging app that displays 10,000 messages in a thread, supports instant "has user X reacted to message Y?" lookups, and supports O(1) append of new messages.**

A: Three-layer data model: (1) **Primary storage**: `[Message]` array (ordered by timestamp, O(1) append, O(1) indexed access for `cellForRow`). This is the source of truth for the table view's data source. (2) **Reaction index**: `[MessageID: [ReactionType: Set<UserID>]]` dictionary. "Has user X reacted with emoji E to message Y?" is a three-level lookup: O(1) message lookup, O(1) reaction type lookup, O(1) `Set.contains`. Without this index, checking reactions during `cellForRow` for 10,000 messages would be O(n × r) per render. (3) **Reverse index for user reactions**: `[UserID: Set<MessageID>]` dictionary — "which messages has user X reacted to?" is O(1). Insertion of a new message: O(1) append to the array. Insertion of a new reaction: O(1) `Set.insert` in both reaction index and reverse index. For diffable data source snapshots, hash the `Message` struct efficiently by including only the `id` and `updatedAt` timestamp in `hashValue`, not the full content. This makes snapshot diffing O(n) instead of O(n × message_length).

## 6. Common Issues & Solutions

**Issue: `cellForRow` is slow — Time Profiler shows `Array.contains` with high self-time.**

Solution: The cell configuration is calling `selectedItems.contains(item.id)` where `selectedItems` is an `Array`. Replace with `Set<ItemID>`. With 500 selected items, this changes from 500 comparisons per cell to 1 hash lookup, eliminating the bottleneck entirely.

**Issue: Building a lookup Dictionary from an API response takes 200ms on the main thread.**

Solution: Move the `Dictionary` construction to a `Task.detached`. Also pre-size: `Dictionary(minimumCapacity: response.count)` and use `Dictionary(uniqueKeysWithValues: response.map { ($0.id, $0) })` — this builds the dictionary in a single pass without repeated resizing.

**Issue: `NSCache` evicts objects too aggressively — frequent cache misses cause visible image reloads.**

Solution: Set `totalCostLimit` to a larger value proportional to available device memory: `ProcessInfo.processInfo.physicalMemory / 10` (10% of device RAM). Also set `countLimit` to a reasonable cap (e.g., 300 for thumbnails). Provide accurate `cost` values per object (pixel area × 4 bytes); NSCache evicts based on cost, not count, when both limits are set.

## 7. Related Topics

- [Memory Optimization](memory-optimization.md) — ARC traffic, NSCache tuning, allocation reduction
- [Lazy Loading](lazy-loading.md) — lazy var and lazy sequence patterns
- [Main Thread Optimization](main-thread-optimization.md) — offloading Dictionary/Set construction
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — diffable data source and efficient cell configuration
- [Concurrency — async/await](../03-concurrency/async-await.md) — offloading data structure construction
