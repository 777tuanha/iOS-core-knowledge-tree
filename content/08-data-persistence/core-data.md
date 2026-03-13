# Core Data

## 1. Overview

Core Data is Apple's object graph persistence framework. It maps Swift objects (`NSManagedObject` subclasses) to a persistent store — typically SQLite — and manages the full lifecycle: insertion, fetching, updating, deleting, undo/redo, and change tracking. Core Data is not a SQL wrapper; it operates at the object graph level with an `NSManagedObjectContext` acting as a scratch pad. It provides powerful features: `NSFetchedResultsController` for live table/collection view updates, lightweight migrations for schema evolution, faulting for lazy-loading, and CloudKit integration via `NSPersistentCloudKitContainer`. Understanding Core Data's threading model is critical — an `NSManagedObjectContext` and its objects are not thread-safe and must be used on the queue they were created on.

## 2. Simple Explanation

Think of Core Data as a smart filing system for objects. The `NSManagedObjectContext` is your desk — a working area where you create, modify, and organise papers (objects). The `NSPersistentStore` (SQLite file) is the filing cabinet in the back room. When you're done editing, you call `save()` and the system moves your desk work into the filing cabinet. Fetching is like asking a filing clerk to bring you matching folders (objects) matching a description. The `NSPersistentContainer` is the building manager that sets up the whole system for you. The key rule: each desk (context) belongs to one person (one thread) — never hand a paper (managed object) to someone at a different desk.

## 3. Deep iOS Knowledge

### Stack Architecture

```
NSPersistentContainer
  ├── NSManagedObjectModel        (.xcdatamodeld — entity definitions)
  ├── NSPersistentStoreCoordinator (manages one or more stores)
  │     └── NSPersistentStore     (SQLite file in Library/Application Support/)
  └── NSManagedObjectContext      (viewContext — main queue)
        └── child contexts        (background contexts for writes)
```

### NSPersistentContainer Setup

`NSPersistentContainer` initialises the full Core Data stack from a `.xcdatamodeld` model file:

```swift
class PersistenceController {
    static let shared = PersistenceController()

    let container: NSPersistentContainer

    init(inMemory: Bool = false) {
        container = NSPersistentContainer(name: "MyApp")   // matches .xcdatamodeld filename
        if inMemory {
            container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
        }
        container.loadPersistentStores { _, error in
            if let error { fatalError("Core Data load failed: \(error)") }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
    }
}
```

### NSManagedObjectContext Threading Rules

- `viewContext` runs on the **main queue** — use it for reading data to display in the UI.
- Background contexts (`container.newBackgroundContext()` or `performBackgroundTask`) run on a private queue — use for writes, imports, and heavy processing.
- **Never pass `NSManagedObject` instances between contexts.** Pass `NSManagedObjectID` instead and call `context.object(with: objectID)` in the target context.
- Always call `context.perform { }` or `context.performAndWait { }` to execute operations on the correct queue.

### Fetch Requests

```swift
let request = NSFetchRequest<Article>(entityName: "Article")
request.predicate = NSPredicate(format: "isPublished == YES AND authorID == %@", userID)
request.sortDescriptors = [NSSortDescriptor(key: "publishedAt", ascending: false)]
request.fetchLimit = 20
request.fetchBatchSize = 20    // faults remaining objects — memory-efficient

let articles = try context.fetch(request)
```

**`fetchBatchSize`** is critical for large datasets: Core Data loads objects in batches as you access them, rather than pulling all rows into memory at once. The returned array is a fault array — individual objects are loaded on demand.

### NSFetchedResultsController

`NSFetchedResultsController` (NSFRC) monitors a fetch request and notifies a delegate when the result set changes. Essential for `UITableView`/`UICollectionView` driven by Core Data:

```swift
lazy var frc: NSFetchedResultsController<Article> = {
    let request = Article.fetchRequest()
    request.sortDescriptors = [NSSortDescriptor(key: "publishedAt", ascending: false)]
    return NSFetchedResultsController(
        fetchRequest: request,
        managedObjectContext: PersistenceController.shared.container.viewContext,
        sectionNameKeyPath: nil,
        cacheName: nil
    )
}()
```

### Faulting

Core Data uses **faults** — placeholder objects that haven't loaded their data from the store yet. When you access a fault's property, Core Data fires the fault and loads the data. This is transparent but has performance implications: accessing many faults one-by-one in a loop causes N+1 queries ("fault storm"). Mitigate with `NSFetchRequest.returnsObjectsAsFaults = false` for small result sets, or `NSFetchRequest.relationshipKeyPathsForPrefetching` for related objects.

### Relationships

Core Data models relationships (`to-one`, `to-many`) in the data model editor:

- Always define **inverse relationships** — Core Data uses them to maintain graph consistency.
- For large to-many relationships, use `NSOrderedSet` if order matters; otherwise `NSSet`.
- Cascade delete rules propagate deletions through the graph automatically.

### Lightweight Migration

When the schema changes, Core Data can automatically migrate the store if the change is "lightweight" (additive: new entity, new optional attribute, renamed entity/attribute with a renaming identifier):

```swift
let description = container.persistentStoreDescriptions.first!
description.shouldMigrateStoreAutomatically = true
description.shouldInferMappingModelAutomatically = true
```

For non-lightweight changes (new required attribute without default, changed relationship type), provide a `NSMappingModel` and use `NSMigrationManager`.

### CloudKit Integration

`NSPersistentCloudKitContainer` replaces `NSPersistentContainer` to sync the Core Data store with CloudKit automatically. Constraints: all attributes must be optional, and ordered relationships are not supported. Sync conflicts are resolved with a last-write-wins strategy by default.

## 4. Practical Usage

```swift
import CoreData
import SwiftUI

// ── PersistenceController singleton ───────────────────────────
class PersistenceController {
    static let shared = PersistenceController()

    // Preview / test instance with in-memory store
    static let preview: PersistenceController = {
        let ctrl = PersistenceController(inMemory: true)
        let ctx = ctrl.container.viewContext
        // Seed preview data
        for i in 0..<5 {
            let note = Note(context: ctx)
            note.id = UUID()
            note.title = "Note \(i)"
            note.body = "Body of note \(i)"
            note.createdAt = Date()
        }
        try? ctx.save()
        return ctrl
    }()

    let container: NSPersistentContainer

    init(inMemory: Bool = false) {
        container = NSPersistentContainer(name: "MyApp")
        if inMemory {
            container.persistentStoreDescriptions.first?.url = URL(fileURLWithPath: "/dev/null")
        }
        container.loadPersistentStores { _, error in
            if let error { fatalError("Core Data: \(error)") }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
    }
}

// ── NSManagedObject subclass (generated or manual) ────────────
// Assumes Note entity with: id: UUID, title: String, body: String, createdAt: Date
// (In Xcode: Entity → Codegen = "Class Definition")

// ── Repository wrapping Core Data operations ──────────────────
actor NoteRepository {
    private let container: NSPersistentContainer

    init(container: NSPersistentContainer = PersistenceController.shared.container) {
        self.container = container
    }

    // ── Read on main context (for UI) ────────────────────────
    func fetchAll() throws -> [Note] {
        let ctx = container.viewContext
        let request = Note.fetchRequest() as NSFetchRequest<Note>
        request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: false)]
        request.fetchBatchSize = 20
        return try ctx.fetch(request)
    }

    // ── Write on background context ──────────────────────────
    func create(title: String, body: String) async throws {
        try await container.performBackgroundTask { ctx in
            let note = Note(context: ctx)
            note.id = UUID()
            note.title = title
            note.body = body
            note.createdAt = Date()
            try ctx.save()                              // persist to SQLite
        }
    }

    func update(objectID: NSManagedObjectID, title: String, body: String) async throws {
        try await container.performBackgroundTask { ctx in
            let note = ctx.object(with: objectID) as! Note   // re-fetch in background context
            note.title = title
            note.body = body
            if ctx.hasChanges { try ctx.save() }
        }
    }

    func delete(objectID: NSManagedObjectID) async throws {
        try await container.performBackgroundTask { ctx in
            let note = ctx.object(with: objectID)
            ctx.delete(note)
            try ctx.save()
        }
    }

    // ── Batch delete (avoids loading objects into memory) ────
    func deleteAll() async throws {
        try await container.performBackgroundTask { ctx in
            let request = NSFetchRequest<NSFetchRequestResult>(entityName: "Note")
            let batchDelete = NSBatchDeleteRequest(fetchRequest: request)
            batchDelete.resultType = .resultTypeObjectIDs
            let result = try ctx.execute(batchDelete) as? NSBatchDeleteResult
            let ids = result?.result as? [NSManagedObjectID] ?? []

            // Merge deletions into view context
            let changes = [NSDeletedObjectsKey: ids]
            NSManagedObjectContext.mergeChanges(fromRemoteContextSave: changes,
                                               into: [self.container.viewContext])
        }
    }
}

// ── NSFetchedResultsController in UIKit ──────────────────────
class NotesViewController: UITableViewController, NSFetchedResultsControllerDelegate {
    private lazy var frc: NSFetchedResultsController<Note> = {
        let request = Note.fetchRequest() as NSFetchRequest<Note>
        request.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: false)]
        request.fetchBatchSize = 20
        return NSFetchedResultsController(
            fetchRequest: request,
            managedObjectContext: PersistenceController.shared.container.viewContext,
            sectionNameKeyPath: nil,
            cacheName: "NotesList"
        )
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        frc.delegate = self
        try? frc.performFetch()
    }

    // UITableViewDataSource
    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        frc.sections?[section].numberOfObjects ?? 0
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let note = frc.object(at: indexPath)
        let cell = tableView.dequeueReusableCell(withIdentifier: "NoteCell", for: indexPath)
        cell.textLabel?.text = note.title
        return cell
    }

    // NSFetchedResultsControllerDelegate — automatic table updates
    func controllerWillChangeContent(_ controller: NSFetchedResultsController<NSFetchRequestResult>) {
        tableView.beginUpdates()
    }

    func controller(_ controller: NSFetchedResultsController<NSFetchRequestResult>,
                    didChange anObject: Any, at indexPath: IndexPath?,
                    for type: NSFetchedResultsChangeType, newIndexPath: IndexPath?) {
        switch type {
        case .insert: tableView.insertRows(at: [newIndexPath!], with: .automatic)
        case .delete: tableView.deleteRows(at: [indexPath!], with: .automatic)
        case .update: tableView.reloadRows(at: [indexPath!], with: .automatic)
        case .move:   tableView.moveRow(at: indexPath!, to: newIndexPath!)
        @unknown default: break
        }
    }

    func controllerDidChangeContent(_ controller: NSFetchedResultsController<NSFetchRequestResult>) {
        tableView.endUpdates()
    }
}

// ── @FetchRequest in SwiftUI ──────────────────────────────────
struct NoteListView: View {
    @FetchRequest(
        sortDescriptors: [SortDescriptor(\.createdAt, order: .reverse)],
        predicate: nil,
        animation: .default
    )
    private var notes: FetchedResults<Note>

    @Environment(\.managedObjectContext) private var context

    var body: some View {
        List(notes) { note in
            Text(note.title ?? "")
        }
        .toolbar {
            Button("Add") {
                let n = Note(context: context)
                n.id = UUID(); n.title = "New"; n.createdAt = Date()
                try? context.save()
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the role of NSManagedObjectContext and why can't you use it on multiple threads?**

A: `NSManagedObjectContext` is the in-memory workspace where Core Data objects live. It tracks inserts, updates, and deletes since the last save. It is not thread-safe because it uses mutable, unsynchronised internal state. Each context is tied to a serial queue (main or private), and `NSManagedObject` instances are bound to the context that created them. Accessing a managed object from a different queue than its context's queue causes data corruption and crashes. The correct pattern is: use `viewContext` (main queue) for reads that feed the UI, create background contexts via `container.newBackgroundContext()` or `performBackgroundTask` for writes and imports, and pass `NSManagedObjectID` values (not the objects themselves) between contexts.

**Q: What is `automaticallyMergesChangesFromParent` and when should you set it to `true`?**

A: When a background context saves changes, those changes are pushed to the persistent store coordinator. The `viewContext` does not automatically receive them unless `automaticallyMergesChangesFromParent = true` is set. With this flag enabled, the `viewContext` merges the background saves automatically (on the main thread), ensuring the UI reflects the latest data. Set it to `true` on the `viewContext` in almost all cases. If disabled, you must manually call `mergeChanges(fromContextDidSave:)` in response to `NSManagedObjectContextDidSave` notifications — more error-prone.

### Hard

**Q: What is faulting in Core Data, and how do you avoid fault storms?**

A: A fault is a lightweight placeholder for a managed object that hasn't loaded its property data from the store yet. When you access a faulted object's property, Core Data fires the fault — executing a SQL query to load that object's row. In a loop over a large array, this causes N individual SQL queries ("fault storm"), severely degrading performance. Mitigations: (1) Set `NSFetchRequest.returnsObjectsAsFaults = false` for small result sets where you'll access most properties. (2) Specify `propertiesToFetch` to load only needed columns. (3) Use `relationshipKeyPathsForPrefetching` to pre-fetch related objects in the same query. (4) Set `fetchBatchSize` on the fetch request — Core Data fetches rows in batches, reducing memory usage while amortising round-trips.

**Q: When does lightweight migration work and when do you need a heavyweight migration?**

A: Lightweight migration works for schema changes that Core Data can infer automatically: adding a new optional attribute or entity, deleting an attribute or entity, renaming an entity or attribute (with a renaming identifier set in the model editor), and changing an attribute to optional. It does NOT work for: adding a required (non-optional) attribute without a default value, changing an attribute's type (e.g., `String` → `Int`), splitting an entity into two, or merging two entities. For these cases, you need a heavyweight migration: create a `NSMappingModel` that maps old entities to new entities, write `NSEntityMigrationPolicy` subclasses to handle custom value transformations, and use `NSMigrationManager` to execute the migration manually before loading the store.

### Expert

**Q: How would you architect a performant Core Data import of 50,000 records from a JSON API response?**

A: Large imports must not run on the `viewContext` (would block the UI) and must be designed to avoid excessive memory use. The architecture: (1) **Background context**: use `container.performBackgroundTask` to get a private-queue context. (2) **Batch processing**: process records in chunks of 500–1000, calling `context.save()` and `context.reset()` after each chunk. `reset()` clears the context's object graph, releasing memory — without it, all 50k objects accumulate in memory. (3) **Batch insert** (iOS 13+): `NSBatchInsertRequest` with a `managedObjectHandler` block inserts records directly into SQLite without going through the object graph — orders of magnitude faster than individual `NSManagedObject` inserts. (4) **Merge**: after the batch insert, call `NSManagedObjectContext.mergeChanges(fromRemoteContextSave:into: [viewContext])` to notify the view context. (5) **Conflict policy**: set `mergePolicy = NSMergeByPropertyStoreTrumpMergePolicy` on the import context to handle re-imports correctly (existing records are updated, not duplicated, based on a unique constraint defined in the model).

## 6. Common Issues & Solutions

**Issue: `EXC_BAD_ACCESS` or crashes when accessing managed objects.**

Solution: A managed object is being accessed from a different thread than its context's queue. Use `context.perform { }` to access objects on the correct queue, or pass `NSManagedObjectID` between threads.

**Issue: Changes saved in a background context do not appear in the UI.**

Solution: Set `container.viewContext.automaticallyMergesChangesFromParent = true`. Without this, the `viewContext` does not receive background saves automatically.

**Issue: `NSFetchedResultsController` triggers too many UI updates.**

Solution: Ensure `sectionNameKeyPath` is nil if you're not using sections. Use the batched delegate methods (`controllerWillChangeContent`/`controllerDidChangeContent` with `beginUpdates`/`endUpdates`) rather than `reloadData()` in `controllerDidChangeContent`. For diffable data source integration, update the snapshot inside `controllerDidChangeContent`.

**Issue: App crashes on launch after a schema change with "The model used to open the store is incompatible with the one used to create the store."**

Solution: You changed the Core Data model without creating a new model version. Always use **Editor → Add Model Version** in Xcode to create a versioned model, set the current version to the new one, and enable lightweight migration on the persistent store description. Never edit the active model version directly.

## 7. Related Topics

- [File System](file-system.md) — Core Data SQLite files live in `Library/Application Support/`
- [Data Synchronization](data-sync.md) — NSPersistentCloudKitContainer and migration strategies
- [Actors](../03-concurrency/actors.md) — actor-based wrappers enforce Core Data threading rules
- [MVVM](../06-architecture/mvvm.md) — ViewModel fetches from the repository; Core Data stays out of the View
- [SQLite & Realm](sqlite-realm.md) — alternative database options with tradeoff comparison
