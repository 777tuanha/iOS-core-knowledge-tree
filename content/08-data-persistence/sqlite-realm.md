# SQLite & Realm

## 1. Overview

While Core Data is Apple's official persistence framework, two alternatives see wide use in production iOS apps: **SQLite** (via the GRDB.swift library) and **Realm**. Raw SQLite is a C library embedded in iOS that provides an ACID-compliant relational database — the most widely deployed database engine in the world. GRDB.swift wraps it with a Swift-friendly API while preserving full SQL expressiveness. Realm is a mobile-first object database with a distinct architecture: objects are live, accessed in-place from memory-mapped files, and queries return live-updating result sets. Both are valid alternatives to Core Data with distinct tradeoffs in API ergonomics, query power, migration story, and reactive capabilities.

## 2. Simple Explanation

**SQLite** is a perfect filing cabinet built into your house — it stores everything in organised drawers (tables), lets you search with precise queries, and never loses data. GRDB is the expert assistant who translates your Swift requests into the cabinet's language (SQL). **Realm** is a different kind of storage: instead of drawers, objects are live objects in memory that automatically reflect the database state — change one copy and all observers see it instantly, like a shared whiteboard rather than individual paper copies.

## 3. Deep iOS Knowledge

### SQLite — Core Characteristics

- **Embedded**: the SQLite engine is compiled into iOS and your app — no server process.
- **ACID**: Atomicity, Consistency, Isolation, Durability — transactions are reliable.
- **WAL mode**: Write-Ahead Logging allows concurrent reads during a write, improving throughput.
- **Single file**: the database is a single `.sqlite` file, trivially copyable and inspectable.
- **Full SQL**: supports complex joins, subqueries, window functions, CTEs, and triggers.

### GRDB.swift — Swift Wrapper for SQLite

GRDB is the community-standard Swift interface to SQLite. Key concepts:

| Concept | Description |
|---------|-------------|
| `DatabaseQueue` | Serial access (read + write on one queue) — simplest |
| `DatabasePool` | Concurrent reads + serialised writes (WAL mode) — recommended for production |
| `Record` | Protocol for `Codable`-based row mapping; generates SQL automatically |
| `DatabaseRegionObservation` | Reactive observation of query results |
| `ValueObservation` | Observes a value query, notifies on change (Combine / async-await) |

**DatabaseMigrator**: GRDB's built-in migration system applies numbered schema migrations in sequence, tracking which have been applied.

### GRDB — Read/Write Patterns

```
DatabasePool
  ├── write { db in ... }         ← serialised writer queue
  └── read { db in ... }          ← concurrent reader queues (WAL snapshot)
```

### Realm — Core Characteristics

- **Object database**: you work with Swift objects directly; no SQL, no mapping layer.
- **Live objects**: `Results<T>` is a live view — it updates automatically when data changes.
- **Memory-mapped**: Realm reads/writes directly from a memory-mapped file — zero-copy for reads.
- **Reactive**: `Results` can be observed via Combine publishers or async-await `AsyncStream`.
- **Realm Schema**: defined by your Swift classes (`Object` subclasses with `@Persisted` properties).
- **Realm Studio**: a GUI tool for inspecting `.realm` files.

### Realm Threading Model

Like Core Data, Realm objects cannot be passed between threads. Use `ThreadSafeReference` to pass objects between queues:

```swift
let ref = ThreadSafeReference(to: object)
DispatchQueue.global().async {
    let realm = try! Realm()
    let resolved = realm.resolve(ref)!
    // use resolved safely on this thread
}
```

In modern Realm (v10+), `@MainActor` actors and async/await are the preferred approach — obtain a `Realm()` on the actor's executor.

### Core Data vs GRDB vs Realm

| Dimension | Core Data | GRDB (SQLite) | Realm |
|-----------|-----------|--------------|-------|
| Query language | NSPredicate | Full SQL | Realm Query Language |
| Schema definition | Xcode data model editor | Code (migrations) | Swift class definition |
| Reactive observation | NSFetchedResultsController | ValueObservation | Live Results + Combine |
| Threading model | Context-per-thread | Connection pool | Thread-confined / actors |
| CloudKit sync | Built-in (NSPersistentCloudKitContainer) | Manual | Realm Atlas Device Sync |
| Migration | Lightweight / heavyweight | DatabaseMigrator | Incremental schema versioning |
| Learning curve | High (NSManagedObject, faulting) | Medium (SQL knowledge) | Low (plain Swift objects) |
| Performance (reads) | Good (faulting) | Excellent (WAL pool) | Excellent (memory-mapped) |
| Dependency | System framework | SPM dependency | SPM dependency |

### When to Choose Each

**Core Data**: team already familiar; need CloudKit sync; building a document-based app; Apple-only supply chain preferred.

**GRDB**: need complex SQL queries; full control over schema; existing SQL expertise; want a lightweight but powerful solution without the Core Data complexity.

**Realm**: need reactive live queries; cross-platform (iOS + Android); rapid prototyping with a low-boilerplate API; willing to add a large dependency.

## 4. Practical Usage

```swift
import GRDB

// ── GRDB setup ────────────────────────────────────────────────
struct AppDatabase {
    static let shared = try! makeDatabase()

    static func makeDatabase(path: String = /* Application Support URL */.path) throws -> DatabasePool {
        let pool = try DatabasePool(path: path)
        try migrator.migrate(pool)
        return pool
    }

    // ── Migrations ───────────────────────────────────────────
    static var migrator: DatabaseMigrator = {
        var migrator = DatabaseMigrator()

        migrator.registerMigration("v1_create_posts") { db in
            try db.create(table: "post") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("title", .text).notNull()
                t.column("body", .text).notNull()
                t.column("authorId", .integer).notNull()
                t.column("publishedAt", .datetime)
                t.column("isFeatured", .boolean).notNull().defaults(to: false)
            }
        }

        migrator.registerMigration("v2_add_tags") { db in
            try db.alter(table: "post") { t in
                t.add(column: "tags", .text).defaults(to: "[]")   // JSON array as text
            }
        }

        return migrator
    }()
}

// ── GRDB Record (Codable + FetchableRecord + PersistableRecord) ─
struct Post: Codable, FetchableRecord, MutablePersistableRecord {
    var id: Int64?
    var title: String
    var body: String
    var authorId: Int64
    var publishedAt: Date?
    var isFeatured: Bool

    static let databaseTableName = "post"

    // Called after insert to capture auto-incremented id
    mutating func didInsert(_ inserted: InsertionSuccess) {
        id = inserted.rowID
    }
}

// ── GRDB Repository ───────────────────────────────────────────
actor PostRepository {
    private let db: DatabasePool

    init(db: DatabasePool = AppDatabase.shared) { self.db = db }

    func fetchAll() throws -> [Post] {
        try db.read { db in
            try Post.fetchAll(db)                        // SELECT * FROM post
        }
    }

    func fetchFeatured() throws -> [Post] {
        try db.read { db in
            try Post
                .filter(Column("isFeatured") == true)   // WHERE isFeatured = 1
                .order(Column("publishedAt").desc)       // ORDER BY publishedAt DESC
                .fetchAll(db)
        }
    }

    func fetchByAuthor(_ authorId: Int64, limit: Int = 20) throws -> [Post] {
        try db.read { db in
            try Post
                .filter(Column("authorId") == authorId)
                .order(Column("publishedAt").desc)
                .limit(limit)
                .fetchAll(db)
        }
    }

    func insert(_ post: inout Post) throws {
        try db.write { db in try post.insert(db) }      // INSERT; sets post.id
    }

    func update(_ post: Post) throws {
        try db.write { db in try post.update(db) }      // UPDATE SET ...
    }

    func delete(id: Int64) throws {
        try db.write { db in
            try Post.deleteOne(db, key: id)             // DELETE WHERE id = ?
        }
    }

    // ── Complex SQL query ────────────────────────────────────
    func fetchPostsWithAuthorName() throws -> [(Post, String)] {
        try db.read { db in
            let sql = """
                SELECT post.*, user.name AS authorName
                FROM post
                JOIN user ON post.authorId = user.id
                WHERE post.publishedAt IS NOT NULL
                ORDER BY post.publishedAt DESC
                LIMIT 50
            """
            return try Row.fetchAll(db, sql: sql).map { row in
                let post = Post(row: row)
                let name = row["authorName"] as String
                return (post, name)
            }
        }
    }
}

// ── GRDB ValueObservation (reactive) ─────────────────────────
import Combine

func observeFeaturedPosts(db: DatabasePool) -> AnyPublisher<[Post], Error> {
    ValueObservation
        .tracking { db in try Post.filter(Column("isFeatured") == true).fetchAll(db) }
        .publisher(in: db, scheduling: .immediate)     // emit current value immediately
        .eraseToAnyPublisher()
}

// ── Realm setup and usage ─────────────────────────────────────
import RealmSwift

// Schema — plain Swift class
class RealmPost: Object {
    @Persisted(primaryKey: true) var id: ObjectId
    @Persisted var title: String
    @Persisted var body: String
    @Persisted var authorId: String
    @Persisted var publishedAt: Date?
    @Persisted var isFeatured: Bool
}

// ── Realm write ───────────────────────────────────────────────
func createPost(title: String, body: String) throws {
    let realm = try Realm()
    let post = RealmPost()
    post.id = ObjectId.generate()
    post.title = title
    post.body = body
    post.publishedAt = Date()
    try realm.write { realm.add(post) }
}

// ── Realm live query ──────────────────────────────────────────
func observeFeaturedRealmPosts() -> RealmPublishers.Value<Results<RealmPost>> {
    let realm = try! Realm()
    return realm.objects(RealmPost.self)
        .filter("isFeatured == true")
        .collectionPublisher                           // live Results publisher
        .freeze()                                      // make thread-safe for publisher chain
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is WAL mode in SQLite and why does GRDB use DatabasePool instead of DatabaseQueue?**

A: WAL (Write-Ahead Logging) is a SQLite journalling mode that allows concurrent reads while a write transaction is in progress. In WAL mode, readers access a consistent snapshot of the database at the point their transaction started, while the writer appends changes to a separate log file that is later checkpointed back to the main database. `DatabaseQueue` uses a single serial queue for both reads and writes — simple but readers block writers and vice versa. `DatabasePool` exploits WAL by maintaining a pool of read connections (which can run concurrently on multiple threads) plus one serial writer connection. For production apps with a UI performing reads while background imports run, `DatabasePool` delivers significantly better throughput and prevents UI hitches caused by write locks.

**Q: What is the key architectural difference between Realm and Core Data / SQLite?**

A: Core Data and SQLite are row-based stores: data lives in tables, and Swift objects are copies of rows fetched into memory. Changing an object in memory doesn't affect the store until you explicitly save. Realm uses a **memory-mapped object store**: Realm objects are live views into the memory-mapped file. There are no copies — the `RealmPost` object IS the database row, accessed via memory mapping. This means: reads are zero-copy; changes are made inside write transactions and are immediately visible to all live `Results` in the same Realm; no `save()` or `fetch()` cycle is needed. The tradeoff is that objects are thread-confined (you need `ThreadSafeReference` or freeze/thaw for cross-thread use) and the in-place mutation model differs from typical value-type Swift idioms.

### Hard

**Q: How does GRDB's `ValueObservation` work and how do you integrate it with SwiftUI?**

A: `ValueObservation` tracks a database region — the set of tables and rows that a fetch request reads — and automatically re-executes the fetch when that region changes. It uses SQLite's update hook internally to detect changes. The observation starts with `observation.start(in: db, scheduling: .mainQueue, onChange: ...)` or via the Combine publisher `.publisher(in: db, scheduling: .immediate)`. In SwiftUI, wrap it in an `@Observable` class or `ObservableObject` with a `@Published` property updated in the `onChange` handler, or use `AsyncValueObservation` via `.values(in: db)` and consume it in a `.task { }` modifier. The scheduling `.immediate` emits the current value synchronously on first subscription (no blank state), then subsequent updates asynchronously.

**Q: Compare GRDB migrations with Core Data lightweight migrations. Which gives more control?**

A: GRDB's `DatabaseMigrator` is explicit and code-driven: each migration is a named closure that runs raw SQL (`CREATE TABLE`, `ALTER TABLE`, etc.). Migrations are applied in registration order; the migrator tracks applied migrations in a `grdb_migrations` table. This gives complete control — any SQL is valid, including backfilling data, creating indexes, or restructuring tables via a temp-table-copy pattern. Core Data's lightweight migration is automatic and model-driven: the system infers the mapping model from the old and new `.xcdatamodeld` versions, which works for simple additive changes but fails for complex transformations. Core Data's heavyweight migration requires `NSMappingModel` and `NSEntityMigrationPolicy` — more powerful but significantly more complex. GRDB gives more predictable, auditable migrations; Core Data's lightweight migration is more convenient for simple cases.

### Expert

**Q: How would you migrate from Core Data to GRDB in a shipping app without data loss?**

A: A live migration requires: (1) **Read** all existing Core Data records using the old stack on first launch after update. (2) **Write** them into the new GRDB database in a migration transaction. (3) **Verify** record counts match between old and new stores. (4) **Mark migration complete** (a flag in UserDefaults). (5) **Delete** the Core Data store after a grace period (one or two releases, giving users time to update). Critical details: run the migration on a background thread; show a migration progress UI if the dataset is large; make it idempotent (if the app is killed mid-migration, restart from the beginning using a `grdb_migrations` entry that only marks completion when the full migration succeeds); test on the oldest supported iOS version; and keep the Core Data stack in the binary for at least two releases so users who skip versions still get their data migrated.

## 6. Common Issues & Solutions

**Issue: GRDB `DatabasePool` throws "database is locked" during writes.**

Solution: All writes must go through `db.write { }` — the pool serialises write access. If you're calling multiple `db.write` blocks from different concurrent tasks and seeing locks, check for nested writes. `DatabasePool.write` is non-reentrant — a write closure that calls `db.write` again will deadlock. Refactor to a single write transaction.

**Issue: Realm crashes with "Realm accessed from incorrect thread".**

Solution: Each `Realm()` instance is thread-confined. Create a fresh `Realm()` instance on each thread/actor, or use `realm.freeze()` to create a thread-safe immutable copy of objects/results for cross-thread passing. In async contexts, use `@MainActor` to confine Realm access to the main actor, or use the async-aware Realm API: `await realm.asyncWrite { ... }`.

**Issue: GRDB record insert does not set the auto-incremented `id` back on the struct.**

Solution: Implement `mutating func didInsert(_ inserted: InsertionSuccess)` on your `MutablePersistableRecord` type and assign `id = inserted.rowID`. Without this, the `id` remains `nil` after insert. Note the method requires the record to be `mutating` — declare it as `var`, not `let`, at the call site.

**Issue: Realm live `Results` causes excessive UI updates when many objects change.**

Solution: Use `.freeze()` on the `Results` before passing to a Combine pipeline, then apply `removeDuplicates()` or debounce. Alternatively, observe only the specific keyPaths you care about using `observe(keyPaths:)` to limit notification scope. For table views, use `RealmSwift.AnyRealmCollection`'s change notifications which provide fine-grained insertions/deletions/modifications rather than full reloads.

## 7. Related Topics

- [Core Data](core-data.md) — Apple's official persistence framework; comparison baseline
- [File System](file-system.md) — SQLite and Realm files live in `Library/Application Support/`
- [Data Synchronization](data-sync.md) — migration strategies and offline-first patterns
- [Actors](../03-concurrency/actors.md) — actor wrappers enforce database threading rules
- [Combine Networking](../05-reactive-programming/combine-networking.md) — GRDB ValueObservation integrates with Combine pipelines
