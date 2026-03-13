# Memory Optimization

## 1. Overview

Memory optimization on iOS operates on two levels: reducing **allocation volume** (fewer objects, smaller objects, shorter lifetimes) and reducing **peak resident memory** (the amount of memory the OS considers "in use" at any moment). iOS uses a paged virtual memory system with no swap file on real devices — when physical memory is exhausted the OS sends memory pressure notifications, then terminates background apps (Jailbreak Level 1), and finally terminates the foreground app (Level 5, the most severe). The primary tools are choosing value types over reference types where appropriate, understanding ARC's retain/release traffic, using `weak`/`unowned` references correctly, responding to `UIApplicationDidReceiveMemoryWarningNotification`, and profiling with Instruments' Allocations and VM Tracker templates to find the actual source of growth.

## 2. Simple Explanation

Memory in iOS works like a hotel where each floor (memory page, 16 KB) is either occupied, reserved, or empty. When the hotel fills up, the manager (the OS) asks guests in their rooms (background apps) to leave first. If that's not enough, the manager asks the guest currently in the lobby (foreground app) to leave too — that's a crash from OOM (out of memory). Optimization means: (1) checking out guests who've already left (releasing objects promptly), (2) booking smaller rooms (using value types and compact data layouts), and (3) not booking rooms on spec (lazy loading, not pre-allocating large buffers). The hotel manager sends warnings — listen to them and clean up the minibar (purge image caches) before being evicted.

## 3. Deep iOS Knowledge

### Value Types vs Reference Types

Value types (`struct`, `enum`, `tuple`) are allocated on the **stack** (or inline in a containing struct) when they fit within 3 words. Stack allocation and deallocation is a single pointer decrement — no heap call, no ARC traffic, no lock.

Reference types (`class`) are always allocated on the **heap**: `malloc` + ARC `retain`/`release`. Every assignment of a class reference triggers an atomic retain/release, which involves an atomic operation and is a significant cost in tight loops.

**Guideline**: prefer `struct` for data models, results, and intermediate computations. Use `class` only when you need reference semantics (shared identity, inheritance, or storage in `@Observable`/`ObservableObject`).

```
Value type:   [value inline in stack frame]  ← no heap, no ARC
Reference type: [stack: pointer] → [heap: object + refcount]  ← malloc + atomic ops
```

### Copy-on-Write (CoW)

Swift standard library value types (`Array`, `Dictionary`, `String`, `Data`) use copy-on-write: they share the underlying storage buffer until one copy is mutated. Only the mutating copy triggers a heap allocation and buffer copy. This means passing large arrays into functions is cheap (shared buffer), and allocation only happens at mutation.

```swift
var a = [1, 2, 3, 4, 5]    // one heap buffer
var b = a                   // still one buffer (shared)
b.append(6)                 // CoW: b now has its own copy
```

### ARC Traffic Reduction

Every `strong` assignment triggers an `objc_retain` + eventual `objc_release` — both are atomic operations. In tight inner loops this becomes measurable. Patterns that generate high ARC traffic:

- Passing `[AnyObject]` through many function calls.
- Using `as AnyObject` bridging.
- Storing class instances in an `Array` with high churn.

Mitigation:
- Use `withUnsafeBufferPointer` for read-only array iteration in tight loops — avoids per-element retain.
- Use `nonisolated(unsafe)` or value types for hot-path data.
- Prefer `UnsafeRawBufferPointer` for binary data processing.

### Memory Pressure Notifications

iOS sends memory warnings at three escalating levels. Register and respond:

```swift
NotificationCenter.default.addObserver(
    self,
    selector: #selector(handleMemoryWarning),
    name: UIApplication.didReceiveMemoryWarningNotification,
    object: nil
)

@objc func handleMemoryWarning() {
    imageCache.removeAllObjects()     // purge NSCache
    thumbnailCache.removeAll()        // purge custom caches
    prefetchedData = nil              // release prefetched buffers
}
```

`NSCache` purges its contents automatically under memory pressure — prefer `NSCache` over `Dictionary` for caches.

### Image Memory

Images are the largest single consumer of memory in most apps. A 3× retina photo decoded from JPEG takes: width × height × 4 bytes. A 4032×3024 (12 MP) photo at 3× = 4032×3024×4 = ~46 MB per image in memory, not the 3–5 MB JPEG file size.

Strategies:
- **Downscale to display size** before rendering: `UIGraphicsImageRenderer` at the image view's frame size.
- **Use `UIImage(named:)` for assets** — it caches using the asset catalog's asset key, deduplicating.
- **Use `UIImage(contentsOfFile:)` for large photos** — not cached by the system.
- **`SDWebImage` / `Kingfisher`** implement memory + disk two-level caches with eviction.

### Avoiding Memory Fragmentation

Small frequent allocations fragment the heap, increasing peak memory and allocation latency. Patterns:
- **Object pools**: reuse objects (cells use the dequeue/enqueue pool automatically; for other objects, implement a pool with a `[T]` free list).
- **Contiguous storage**: `ContiguousArray<T>` (for non-Objective-C types) and flat arrays instead of arrays of arrays.
- **Batched allocations**: allocate in bulk rather than one-at-a-time in a loop.

### Instruments: Allocations Workflow

1. Profile → Allocations template.
2. Use the app to reach the suspect scenario.
3. Switch to **"All Heap Allocations"** → sort by **Persistent Bytes** descending.
4. The top class in persistent bytes is what's consuming the most live memory.
5. Click the class → **Object Details** pane → see the allocation call stack of every live instance.
6. Use **Heap Shots** to find objects that survive a scenario that should release them (see [Instruments & Profiling](instruments-profiling.md)).

### VM Tracker

The **VM Tracker** Instruments template shows virtual memory regions — `__TEXT`, `__DATA`, `mapped files`, `malloc heaps`, `dirty pages`. The critical metric is **Dirty + Swapped** size, which is the memory the OS considers "in use". `__TEXT` (compiled code) is clean and can be evicted. Large `dirty pages` in the malloc region indicate heavy heap use. Large `mapped files` indicate `mmap`'d resources (e.g., memory-mapped Core Data SQLite file).

## 4. Practical Usage

```swift
import UIKit

// ── Prefer struct for data models ─────────────────────────────
struct PostViewModel {       // ✓ value type — stack allocated, no ARC
    let id: String
    let title: String
    let authorName: String
    var isBookmarked: Bool
}

// vs.
// final class PostViewModel { ... }  // ✗ heap + ARC for every assignment

// ── NSCache for images — auto-evicts under memory pressure ────
final class ImageCache {
    static let shared = ImageCache()

    private let cache: NSCache<NSString, UIImage> = {
        let c = NSCache<NSString, UIImage>()
        c.countLimit = 200           // max 200 images retained
        c.totalCostLimit = 50 * 1024 * 1024   // 50 MB cost limit
        return c
    }()

    func image(for url: URL) -> UIImage? {
        cache.object(forKey: url.absoluteString as NSString)
    }

    func store(_ image: UIImage, for url: URL) {
        // Estimate cost = width × height × 4 bytes
        let cost = Int(image.size.width * image.size.height * 4 * image.scale * image.scale)
        cache.setObject(image, forKey: url.absoluteString as NSString, cost: cost)
    }
}

// ── Downscaling large images to display size ──────────────────
extension UIImage {
    /// Returns a version of the image scaled to `targetSize`, reducing memory usage.
    func downsampled(to targetSize: CGSize, scale: CGFloat = UIScreen.main.scale) -> UIImage {
        let imageSourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
        guard let data = jpegData(compressionQuality: 1.0),
              let source = CGImageSourceCreateWithData(data as CFData, imageSourceOptions)
        else { return self }

        let maxDimension = max(targetSize.width, targetSize.height) * scale
        let downsampleOptions: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: maxDimension
        ]
        guard let thumbnail = CGImageSourceCreateThumbnailAtIndex(source, 0, downsampleOptions as CFDictionary)
        else { return self }
        return UIImage(cgImage: thumbnail)
    }
}

// ── Responding to memory warnings ─────────────────────────────
final class FeedViewController: UIViewController {

    private var imageCache = ImageCache.shared
    private var prefetchedPostBodies: [String: String] = [:]

    override func viewDidLoad() {
        super.viewDidLoad()
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(didReceiveMemoryWarning),
            name: UIApplication.didReceiveMemoryWarningNotification,
            object: nil
        )
    }

    @objc private func didReceiveMemoryWarning() {
        // Release what can be re-fetched on demand
        prefetchedPostBodies.removeAll(keepingCapacity: false)
        // NSCache (ImageCache) purges itself automatically
    }
}

// ── Avoiding retain cycles with closures ──────────────────────
final class ProfileViewModel {
    var onUpdate: (() -> Void)?

    func loadProfile() {
        fetchProfile { [weak self] profile in     // weak — avoids retain cycle
            guard let self else { return }
            self.onUpdate?()
        }
    }

    private func fetchProfile(completion: @escaping (String) -> Void) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { completion("Alice") }
    }
}

// ── Object pool for expensive-to-create objects ───────────────
final class DateFormatterPool {
    private var pool: [DateFormatter] = []
    private let queue = DispatchQueue(label: "DateFormatterPool")

    func acquire() -> DateFormatter {
        queue.sync {
            if pool.isEmpty {
                let formatter = DateFormatter()
                formatter.dateStyle = .medium
                formatter.timeStyle = .short
                return formatter
            }
            return pool.removeLast()
        }
    }

    func release(_ formatter: DateFormatter) {
        queue.async { self.pool.append(formatter) }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between stack allocation and heap allocation on iOS, and why does it matter for performance?**

A: Stack allocation places a value at the current stack frame pointer and reclaims it by adjusting the pointer — two instructions, no locks. Heap allocation calls `malloc`, which searches a free-list, possibly invokes `mmap`, and updates allocator bookkeeping — hundreds of instructions, potentially blocking. For reference types, every assignment also triggers an atomic `retain`/`release`, involving a CPU memory barrier. Struct values stored in local variables or function arguments live on the stack (if ≤ 3 words); class instances always live on the heap. For hot code paths processing thousands of items (e.g., populating 1000 cells during a scroll), the difference between struct and class can be a 2–5× speedup in a tight loop, visible in Instruments as a reduction in `malloc` and `objc_retain` self-time.

**Q: What is copy-on-write in Swift and what is its performance implication?**

A: Copy-on-write (CoW) is an optimisation in Swift's standard library collection types (`Array`, `Dictionary`, `String`, `Data`) where multiple values share one underlying heap buffer until one of them is mutated. When a mutation occurs on a non-uniquely-owned buffer, the buffer is copied first. The implication: passing an `Array` into a function is O(1) (shared buffer, no copy), and reading it is O(1). Only writing to a non-unique copy triggers an O(n) buffer copy. For performance, this means you can safely pass large arrays as function arguments without copying them, but mutating an array inside a function when multiple variables reference it will trigger a copy — profile with Instruments Allocations to detect unexpected copies in hot paths.

### Hard

**Q: How do you diagnose a progressive memory growth that doesn't appear as a Leaks instrument leak?**

A: This is a "logical leak" — the object is reachable through a valid reference path but should have been released. Diagnosis: (1) Take Heap Shots: perform the suspect action (e.g., open and dismiss a modal) five times, marking the heap before and after each cycle. (2) Examine the delta: any class whose instance count grows monotonically with each cycle is accumulating. (3) Use "Object Details" for that class to see each instance's allocation call stack. (4) Common causes: a `[MyViewController]` array collecting dismissed VCs; `NotificationCenter` observers added but never removed (the observer closure captures `self` strongly, keeping the VC alive); `URLSession` completion handlers stored in a dictionary without cleanup; `Timer` with a strong `target` reference. Fix: audit `removeObserver` calls, use `weak self` in closures, and ensure caches have eviction policies (`NSCache` instead of `Dictionary`).

**Q: What techniques reduce memory usage when displaying a grid of high-resolution images?**

A: Four techniques: (1) **Downsampling at decode time**: use `CGImageSourceCreateThumbnailAtIndex` with `kCGImageSourceThumbnailMaxPixelSize` set to the display pixel size. A 12 MP photo decoded at 375×375 pt at 3× = 1125×1125 px = 5 MB instead of 46 MB. (2) **Two-level cache**: `NSCache` for in-memory (auto-evicted under pressure), filesystem for disk cache (survives app relaunch). Limit `NSCache.totalCostLimit` proportionally to device RAM, queried from `ProcessInfo.processInfo.physicalMemory`. (3) **Cell-based lifecycle**: assign images only in `cellForRow`; cancel in-flight image loads in `prepareForReuse` to avoid setting a stale image. (4) **Prefetching cap**: use `UICollectionViewDataSourcePrefetching` to start loading the next 3–5 rows, but cancel the rest — prefetching too aggressively causes memory pressure. All four together can reduce peak memory from several hundred MB to under 50 MB on a photo-heavy feed screen.

### Expert

**Q: How would you design a memory management strategy for a social media app that displays an infinite scroll feed with images, video previews, and text?**

A: Four-layer strategy: (1) **Rendering budget per cell type**: compute the maximum memory per cell (image: downsampled to cell size; video: thumbnail only, not decoded video buffer; text: negligible). For 100 visible+buffered cells, cap total at ~100 MB. Set `NSCache.totalCostLimit` accordingly. (2) **Lifecycle-aware resource management**: track which cells are visible (`UICollectionView.indexPathsForVisibleItems`). When a cell scrolls off-screen beyond 2 screens of distance, cancel its image/video task and set thumbnail to `nil`. Resume on scroll-back. This is the "cell eviction" complement to cell reuse. (3) **Video streaming, not decoding**: use `AVPlayerItem` with an `AVAssetResourceLoaderDelegate` that streams the video lazily from the network — never decode the full video into memory. Pause and nil out `AVPlayer` in cells more than 1 screen away. (4) **Memory pressure tiers**: implement a `MemoryPressureResponder` that listens to `UIApplication.didReceiveMemoryWarningNotification` and progressively purges: Level 1 → clear off-screen thumbnail cache; Level 2 → clear all thumbnail cache; Level 3 → cancel all pending network requests and release all non-visible cell data. This ensures the app survives memory warnings without a crash.

## 6. Common Issues & Solutions

**Issue: App is terminated by the OS without a crash log — just disappears.**

Solution: This is an OOM (out-of-memory) kill. Check `UIApplicationDidReceiveMemoryWarningNotification` — if the app never receives it, the growth was sudden (e.g., loading a large image into memory at once). Use Instruments VM Tracker to find the dirty-memory peak. Profile with Allocations and look for the largest persistent allocation class. Common cause: an uncompressed image loaded into a `UIImageView` at its original resolution rather than the display size.

**Issue: `NSCache` is purging too aggressively — images reload frequently.**

Solution: Set `countLimit` and `totalCostLimit` to match device capability. Query `ProcessInfo.processInfo.physicalMemory` and set `totalCostLimit` to 10–20% of device RAM. On a 6 GB device that's 600 MB–1.2 GB — far more than the default (unlimited). Also set `cost` per object correctly (pixel area × bytes per pixel) rather than using cost = 1.

**Issue: Allocations instrument shows `String` objects growing unboundedly.**

Solution: Strings in Swift are value types but their storage buffer is heap-allocated. Unbounded string growth often means: log accumulation (a `[String]` log buffer appending indefinitely), attributed string creation per-cell without reuse, or `String(describing:)` called in a hot path creating many short-lived strings. Identify the allocation call stack in Instruments, add `keepingCapacity: true` to `removeAll` calls where appropriate, and reuse `AttributedString` formatters.

## 7. Related Topics

- [Instruments & Profiling](instruments-profiling.md) — Allocations and Leaks workflows
- [ARC & Memory Management](../02-memory-management/arc-memory-management.md) — retain count mechanics
- [Retain Cycles & Weak References](../02-memory-management/retain-cycles.md) — fixing cycles found in Leaks
- [Lazy Loading](lazy-loading.md) — deferred allocation strategies
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — cell reuse and prefetching
