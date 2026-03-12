# UITableView & UICollectionView

## 1. Overview

`UITableView` and `UICollectionView` are UIKit's high-performance, data-driven list views. Both use a **cell reuse queue** to recycle off-screen cells, keeping memory usage proportional to visible items rather than total data set size. `UITableView` handles one-dimensional (vertical) lists. `UICollectionView` handles arbitrary two-dimensional layouts via a pluggable `UICollectionViewLayout` — including the modern **compositional layout** API. The modern data source API, **diffable data source**, replaces manual `insertRows`/`deleteRows` with snapshot-based diffing that is safe from crash-causing inconsistencies.

## 2. Simple Explanation

Imagine a restaurant with 10 tables but a menu of 1000 items. The waiter doesn't carry all 1000 items at once — they carry only what's needed for the visible tables. When a diner finishes and leaves, their table is quickly cleared and re-used for the next guest. UITableView/CollectionView works the same way: it only creates cells for the rows currently visible, reuses them as you scroll, and only asks for data for the visible index paths.

## 3. Deep iOS Knowledge

### Cell Reuse Queue

The reuse queue is a dictionary-of-stacks keyed by `reuseIdentifier`. When a cell scrolls off-screen:
1. The cell is removed from the view hierarchy.
2. It is placed in the reuse queue under its identifier.

When a new cell is needed:
1. `dequeueReusableCell(withIdentifier:for:)` checks the queue.
2. If a recycled cell exists, it is returned (content must be reconfigured).
3. If not, a new cell is created from the registered class or nib.

**Critical**: Always configure all cell properties in `cellForRowAt` — never assume a dequeued cell has clean state. Use `prepareForReuse()` to reset expensive state (cancel image downloads, clear text).

### Cell Registration (Modern API)

```swift
// Register
tableView.register(MyCell.self, forCellReuseIdentifier: "MyCell")

// Modern: register with CellRegistration (type-safe, iOS 14+)
let registration = UICollectionView.CellRegistration<MyCell, Item> { cell, indexPath, item in
    cell.configure(with: item)
}
```

`CellRegistration` combines registration and configuration — no separate `dequeueReusableCell` call needed when used with diffable data source.

### Diffable Data Source

Introduced in iOS 13, `UITableViewDiffableDataSource` and `UICollectionViewDiffableDataSource` replace the delegate-based `numberOfRows` / `cellForRowAt` pattern:

- Data is described as a **snapshot** (`NSDiffableDataSourceSnapshot`) of sections and items.
- Applying a new snapshot **diffs** it against the current snapshot and animates the minimal set of inserts, deletes, and moves.
- Items must be `Hashable` (their `hashValue` is used for identity).
- **No more `performBatchUpdates` crashes** — diffable data source computes safe animations automatically.

### Compositional Layout

`UICollectionViewCompositionalLayout` (iOS 13+) replaces `UICollectionViewFlowLayout` with a composable API:

```
Layout
  └── Section(s)
        └── Group(s)
              └── Item(s)
```

Each level has an `NSCollectionLayoutSize` (with fractional, absolute, or estimated dimensions) and an optional `NSCollectionLayoutEdgeSpacing` or `NSCollectionLayoutInsets`. Sections can have independent scrolling behaviour (`orthogonalScrollingBehavior`), headers/footers, and decoration views.

### Self-Sizing Cells

Enable with:
```swift
tableView.estimatedRowHeight = 44                  // provide a reasonable estimate
tableView.rowHeight = UITableView.automaticDimension
```

The cell's Auto Layout constraints must create a complete vertical constraint chain from top to bottom edge — the system can then compute the height from the intrinsic sizes of labels and images.

### Prefetching

`UITableViewDataSourcePrefetching` / `UICollectionViewDataSourcePrefetching` allow you to start loading data before a cell is needed:

```swift
func collectionView(_ cv: UICollectionView, prefetchItemsAt indexPaths: [IndexPath]) {
    indexPaths.forEach { imageLoader.loadImage(at: $0) }
}
func collectionView(_ cv: UICollectionView, cancelPrefetchingForItemsAt indexPaths: [IndexPath]) {
    indexPaths.forEach { imageLoader.cancelLoad(at: $0) }
}
```

### Performance Best Practices

| Technique | Impact |
|-----------|--------|
| Opaque cells (`isOpaque = true`) | Skips alpha blending — significant GPU saving |
| `estimatedRowHeight` accuracy | Reduces layout pass thrashing on scroll |
| Avoid `layoutIfNeeded()` in `cellForRowAt` | Forces early layout — defeats batching |
| `prepareForReuse()` cancel downloads | Prevents stale images on recycled cells |
| Pre-render images to exact cell size | Avoids scaling during scroll |
| Background thread data preparation | Keeps `cellForRowAt` fast |

### List Configuration (iOS 14+)

`UICollectionLayoutListConfiguration` creates table-like layouts in `UICollectionView` with system accessories (disclosure indicators, swipe actions, separators) without needing `UITableView`:

```swift
var config = UICollectionLayoutListConfiguration(appearance: .insetGrouped)
config.trailingSwipeActionsConfigurationProvider = { indexPath in
    let deleteAction = UIContextualAction(style: .destructive, title: "Delete") { _, _, completion in
        // handle delete
        completion(true)
    }
    return UISwipeActionsConfiguration(actions: [deleteAction])
}
let layout = UICollectionViewCompositionalLayout.list(using: config)
```

## 4. Practical Usage

```swift
import UIKit

// ── Data model (must be Hashable for diffable data source) ─────
struct Contact: Hashable {
    let id: UUID
    let name: String
    let email: String
}

enum Section: Hashable { case main }

// ── Custom cell ────────────────────────────────────────────────
class ContactCell: UITableViewCell {
    override func prepareForReuse() {
        super.prepareForReuse()
        textLabel?.text = nil           // reset — never assume dequeued cell is clean
        detailTextLabel?.text = nil
    }

    func configure(with contact: Contact) {
        textLabel?.text = contact.name
        detailTextLabel?.text = contact.email
    }
}

// ── UITableView with diffable data source ──────────────────────
class ContactListViewController: UIViewController {
    private var tableView: UITableView!
    private var dataSource: UITableViewDiffableDataSource<Section, Contact>!

    override func viewDidLoad() {
        super.viewDidLoad()

        tableView = UITableView(frame: view.bounds, style: .insetGrouped)
        tableView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        tableView.register(ContactCell.self, forCellReuseIdentifier: "ContactCell")
        tableView.estimatedRowHeight = 56       // helps avoid layout thrashing
        tableView.rowHeight = UITableView.automaticDimension
        view.addSubview(tableView)

        // Diffable data source — configure cell here
        dataSource = UITableViewDiffableDataSource(tableView: tableView) {
            tableView, indexPath, contact in
            let cell = tableView.dequeueReusableCell(
                withIdentifier: "ContactCell", for: indexPath
            ) as! ContactCell
            cell.configure(with: contact)
            return cell
        }
    }

    // Apply snapshot — safe, no crash-prone batch updates
    func display(contacts: [Contact]) {
        var snapshot = NSDiffableDataSourceSnapshot<Section, Contact>()
        snapshot.appendSections([.main])
        snapshot.appendItems(contacts)
        dataSource.apply(snapshot, animatingDifferences: true)
    }
}

// ── UICollectionView with compositional layout ─────────────────
class PhotoGridViewController: UIViewController {

    typealias DataSource = UICollectionViewDiffableDataSource<Section, URL>
    typealias Snapshot = NSDiffableDataSourceSnapshot<Section, URL>

    private var collectionView: UICollectionView!
    private var dataSource: DataSource!

    override func viewDidLoad() {
        super.viewDidLoad()
        collectionView = UICollectionView(frame: view.bounds, collectionViewLayout: makeLayout())
        collectionView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(collectionView)

        let registration = UICollectionView.CellRegistration<PhotoCell, URL> { cell, _, url in
            cell.load(imageURL: url)            // configure via CellRegistration closure
        }

        dataSource = DataSource(collectionView: collectionView) {
            collectionView, indexPath, url in
            collectionView.dequeueConfiguredReusableCell(
                using: registration, for: indexPath, item: url
            )
        }
    }

    private func makeLayout() -> UICollectionViewLayout {
        // Three-column grid with proportional item sizing
        let itemSize = NSCollectionLayoutSize(
            widthDimension: .fractionalWidth(1/3),      // 1/3 of group width
            heightDimension: .fractionalHeight(1.0)
        )
        let item = NSCollectionLayoutItem(layoutSize: itemSize)
        item.contentInsets = NSDirectionalEdgeInsets(top: 2, leading: 2, bottom: 2, trailing: 2)

        let groupSize = NSCollectionLayoutSize(
            widthDimension: .fractionalWidth(1.0),      // full width
            heightDimension: .fractionalWidth(1/3)      // square cells
        )
        let group = NSCollectionLayoutGroup.horizontal(layoutSize: groupSize, subitems: [item])

        let section = NSCollectionLayoutSection(group: group)
        return UICollectionViewCompositionalLayout(section: section)
    }
}

// ── Prefetching images ─────────────────────────────────────────
class PrefetchingViewController: UIViewController,
    UICollectionViewDataSourcePrefetching {

    var collectionView: UICollectionView!

    func collectionView(
        _ collectionView: UICollectionView,
        prefetchItemsAt indexPaths: [IndexPath]
    ) {
        // Start loading images before cells are needed
        indexPaths.forEach { _ in
            // ImageLoader.shared.startPrefetch(for: items[$0.item].imageURL)
        }
    }

    func collectionView(
        _ collectionView: UICollectionView,
        cancelPrefetchingForItemsAt indexPaths: [IndexPath]
    ) {
        // Cancel loads for cells that scrolled off without becoming visible
        indexPaths.forEach { _ in
            // ImageLoader.shared.cancelPrefetch(for: items[$0.item].imageURL)
        }
    }
}

// Stubs
class PhotoCell: UICollectionViewCell {
    func load(imageURL: URL) {}
}
```

## 5. Interview Questions & Answers

### Basic

**Q: How does the cell reuse queue work and why is `prepareForReuse` important?**

A: The reuse queue is a pool of off-screen cells keyed by `reuseIdentifier`. When a cell scrolls off-screen, it is removed from the view hierarchy and placed in the queue. When a new cell is needed, `dequeueReusableCell` pulls one from the queue (or creates a new one if empty) and returns it. Because the cell carries content from a previous row, `prepareForReuse` is called before the cell is returned to you — it is the correct place to reset expensive or state-carrying properties: cancel image downloads, clear text, reset selection states. You must then fully re-configure the cell in `cellForRowAt` — never assume a dequeued cell has clean state.

**Q: What is diffable data source and what problem does it solve?**

A: Diffable data source (`UITableViewDiffableDataSource` / `UICollectionViewDiffableDataSource`) is a type-safe, snapshot-based replacement for the traditional delegate data source. You create a snapshot of sections and items, then apply it. The data source diffs the new snapshot against the current one and performs the minimum set of animated inserts, deletes, and moves. It solves the crash-prone problem of "performBatchUpdates" where manual inconsistencies between the data model and the table's internal state caused "NSInternalInconsistencyException" crashes. Items must be `Hashable` — the hash value determines identity for diffing.

### Hard

**Q: How does `UICollectionViewCompositionalLayout` differ from `UICollectionViewFlowLayout`?**

A: `FlowLayout` is a single fixed grid/flow model — all sections share the same layout rules, and customisation is limited to delegate methods for item size and spacing. `CompositionalLayout` is a composable hierarchy of `Item → Group → Section → Layout`, where each level has independent sizing (fractional, absolute, or estimated) and spacing. Sections can have their own scrolling direction (`orthogonalScrollingBehavior`), decoration views, headers/footers with pinning behaviour, and boundary supplementary items. CompositionalLayout also supports `UICollectionViewCompositionalLayout.list` for table-like list layouts with swipe actions, accessories, and separators — replacing most `UITableView` use cases.

**Q: What causes `UITableView`/`UICollectionView` jank during fast scrolling, and how do you fix it?**

A: Common causes: (1) **Heavy `cellForRowAt`** — creating sublayers, downloading images synchronously, or running layout calculations. Fix: precompute data on a background thread, use async image loading with cancellation. (2) **Non-opaque cells** — GPU must composite alpha channels. Fix: set `cell.isOpaque = true` and matching `backgroundColor`. (3) **Inaccurate `estimatedRowHeight`** — causes layout thrashing as the table readjusts content offset. Fix: provide accurate estimates, ideally cached from a previous layout pass. (4) **Mismatched batch updates** — use diffable data source to eliminate. (5) **Deferred image resizing** — images loaded at a larger size than displayed waste memory and cause scaling on the main thread. Fix: downscale images to the target size on a background thread before setting them on the cell.

### Expert

**Q: Design a highly performant infinite-scrolling feed using modern UICollectionView APIs.**

A: Use `UICollectionViewDiffableDataSource` with a `NSDiffableDataSourceSnapshot` so updates never crash. Use `UICollectionViewCompositionalLayout` for the layout with `estimatedDimension` for self-sizing cells. For prefetching, implement `UICollectionViewDataSourcePrefetching` — start image/data downloads in `prefetchItemsAt` and cancel them in `cancelPrefetchingForItemsAt` using a `URLSessionDataTask` keyed by index path. Use `NSCache` or a disk cache for loaded images. For infinite scroll, detect when the user approaches the last N items (compare `contentOffset` + `bounds.height` against `contentSize.height`), trigger the next page load, and append items to the snapshot with `.apply(animatingDifferences: false)` to avoid scroll interruption. On the cell level: precompute attributed strings and image thumbnails off the main thread, cache attributed string heights so `estimatedRowHeight` matches actual height closely.

## 6. Common Issues & Solutions

**Issue: "NSInternalInconsistencyException: Invalid update" crash during `insertRows`.**

Solution: Migrate to diffable data source — it eliminates this crash class entirely. If stuck with traditional data source, ensure the number of rows returned by `numberOfRowsInSection` before and after the update is exactly consistent with the number of rows inserted/deleted in `performBatchUpdates`.

**Issue: Cells show stale content (wrong image, wrong text) after scrolling.**

Solution: You're not resetting state in `prepareForReuse`. Cancel any in-flight image downloads and clear the `UIImageView.image` there. Then set the image from the current index path's data in `cellForRowAt`.

**Issue: Self-sizing cells have incorrect height on first load.**

Solution: Ensure the cell's Auto Layout constraints form a complete vertical chain (top to bottom). Set `tableView.estimatedRowHeight = UITableView.automaticDimension` — actually this is wrong, set `rowHeight = UITableView.automaticDimension` and provide a reasonable `estimatedRowHeight` number. For collection view cells, override `preferredLayoutAttributesFitting(_:)` to return the self-sized attributes.

**Issue: Diffable data source crash: "Fatal error: Duplicate item identifiers".**

Solution: Two items in your snapshot have the same `hashValue`. Ensure your model's `Hashable` implementation uses a unique identifier (like a UUID) rather than mutable properties like a name that can repeat.

## 7. Related Topics

- [UIView Lifecycle](uiview-lifecycle.md) — cell rendering and layout passes
- [Auto Layout](autolayout.md) — self-sizing cells depend on intrinsic content size
- [SwiftUI View Lifecycle](swiftui-view-lifecycle.md) — SwiftUI `List` as the declarative equivalent
- [MVVM & Coordinator](mvvm-coordinator.md) — data source as part of the MVVM binding layer
