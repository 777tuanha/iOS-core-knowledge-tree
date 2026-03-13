# Data Synchronization

## 1. Overview

Data synchronization addresses the hard problems that arise when local device state must stay consistent with a server — or with other devices — in the face of offline usage, concurrent edits, and schema evolution. Three concerns dominate: **offline-first architecture** (local data is the source of truth; the network is a transport, not a prerequisite), **conflict resolution** (what happens when two clients edit the same record simultaneously), and **data migration** (how schemas evolve without data loss as the app ships new versions). These topics are interconnected: an offline-first architecture forces you to confront conflicts; schema evolution requires migration strategies for both local stores and the server API.

## 2. Simple Explanation

Imagine a shared Google Doc that you can also edit offline. **Offline-first** means your changes save instantly to your local copy — you don't wait for the internet. When you reconnect, the app tries to merge your changes with what others wrote while you were offline. **Conflict resolution** is the set of rules for handling overlapping edits: "last write wins", "merge character by character" (like Git), or "ask the user". **Data migration** is what happens when the document's format changes — new columns, renamed fields — and you need to convert all existing documents to the new format without losing anything.

## 3. Deep iOS Knowledge

### Offline-First Architecture

The core principle: **local persistence is the primary source of truth; network is an optimistic sync layer**.

```
User Action
    │
    ▼
Local Store (Core Data / SQLite / Realm)  ← immediate read/write
    │
    ▼
Sync Engine (background)  ← uploads local changes, downloads remote changes
    │
    ▼
Server / CloudKit / Realm Atlas
```

**Benefits**: zero-latency UI (reads/writes are local), works completely offline, network failures are transparent.

**Components required**:
1. **Change tracking**: know which local records have been created, updated, or deleted since the last sync.
2. **Sync queue**: persist pending mutations so they survive app termination.
3. **Merge strategy**: reconcile local and remote changes when connectivity is restored.
4. **Conflict detection**: identify when two versions of the same record have diverged.

### Change Tracking Strategies

| Strategy | How it works | Complexity |
|----------|-------------|------------|
| Timestamp-based | `updatedAt` column; sync records with `updatedAt > lastSyncTime` | Low |
| Version vector | Each record carries a version counter per device | Medium |
| Event log / CRDT | Append-only log of operations; merge by replaying | High |
| CloudKit `CKServerChangeToken` | CloudKit returns a change token; fetch changes since token | Platform-specific |

**Soft deletes**: instead of deleting records, set `isDeleted = true` and sync the tombstone. Hard deletes are untrackable once the row is gone.

### Conflict Resolution Strategies

A conflict occurs when the same record is modified locally and remotely since the last sync.

| Strategy | Description | Best for |
|----------|-------------|---------|
| Last-write-wins (LWW) | Server timestamp wins; local changes are discarded | Simple scalars, preferences |
| Client-wins | Local version always wins | Offline-first apps with strong local ownership |
| Server-wins | Server version always wins | Read-heavy apps with authoritative server |
| Field-level merge | Merge non-overlapping field changes; flag overlapping fields as conflicts | Documents, rich records |
| User-resolved | Present conflict to user; let them choose or merge manually | Document editors (like iCloud Drive) |
| CRDT (Conflict-free Replicated Data Type) | Data structure designed so all merge orders produce the same result | Collaborative real-time editing |

**Practical pattern**: use **last-write-wins on individual fields** (not whole records): compare timestamps per field, take the newer value. This resolves most conflicts automatically — two people editing different fields of the same record is not a true conflict.

### CloudKit Sync with NSPersistentCloudKitContainer

Apple's built-in sync layer pairs Core Data with iCloud CloudKit:

```swift
let container = NSPersistentCloudKitContainer(name: "MyApp")
// All Core Data entities automatically sync to CloudKit private database
container.loadPersistentStores { _, error in
    if let error { fatalError(error.localizedDescription) }
}
container.viewContext.automaticallyMergesChangesFromParent = true
```

**Constraints**:
- All attributes must be optional (CloudKit records can have missing fields).
- Ordered relationships not supported.
- Conflict resolution is last-write-wins per CloudKit record (not field-level).
- Sync is best-effort — no explicit conflict resolution hooks are provided.

### Data Migration

**Local store migration** (Core Data):
- **Lightweight**: automatic for additive changes (new optional attributes, entity renames with renaming identifier). Enable via `shouldMigrateStoreAutomatically = true`.
- **Heavyweight**: for type changes, required attributes, or entity restructuring. Requires `NSMappingModel` and custom `NSEntityMigrationPolicy`.
- **Progressive migration**: for multi-version upgrades, chain migrations through intermediate versions (v1→v2→v3) rather than jumping directly.

**Local store migration** (GRDB/SQLite):
- `DatabaseMigrator` applies numbered migrations in sequence, tracking applied migrations in a system table.
- Each migration is a SQL transaction — atomic; failure rolls back cleanly.
- Support for destructive migration on Simulator (for development reset): `migrator.eraseDatabaseOnSchemaChange = true` (development only).

**API versioning and model evolution**:
- Additive API changes (new optional fields): handled by `decodeIfPresent` in `Codable` — missing keys become `nil`.
- Renamed fields: decode with a custom `init(from:)` trying new key first, old key as fallback.
- Removed fields: ignore gracefully — the `Codable` synthesised decoder ignores unknown JSON keys.
- Breaking changes: version the API (`/v2/endpoint`) and maintain parallel support during a transition window.

### iCloud Key-Value Store

For lightweight sync of small preferences across the user's devices (like UserDefaults, but synced):

```swift
let store = NSUbiquitousKeyValueStore.default
store.set("dark", forKey: "theme")
store.synchronize()

// Observe changes from other devices
NotificationCenter.default.addObserver(
    self,
    selector: #selector(kvStoreChanged),
    name: NSUbiquitousKeyValueStore.didChangeExternallyNotification,
    object: store
)
```

Limits: 1 MB total storage, 1024 keys. Best for settings, user preferences. Not a database.

## 4. Practical Usage

```swift
import Foundation
import Combine

// ── Change tracking with timestamps ──────────────────────────
// Assumes Post has: id, title, body, updatedAt, serverUpdatedAt, isSyncPending
// isSyncPending = true means local change not yet uploaded

// ── Sync engine (actor for thread safety) ─────────────────────
actor SyncEngine {
    private let apiClient: APIClient
    private let repository: PostRepository
    private var isSyncing = false

    init(apiClient: APIClient, repository: PostRepository) {
        self.apiClient = apiClient
        self.repository = repository
    }

    func sync() async throws {
        guard !isSyncing else { return }
        isSyncing = true
        defer { isSyncing = false }

        try await uploadPendingChanges()
        try await downloadRemoteChanges()
    }

    // ── Upload local changes to server ────────────────────────
    private func uploadPendingChanges() async throws {
        let pending = try await repository.fetchPending()       // WHERE isSyncPending = true
        for post in pending {
            do {
                let serverPost = try await apiClient.upsert(post)
                try await repository.markSynced(post.id, serverUpdatedAt: serverPost.updatedAt)
            } catch let error as NetworkError where error.isConflict {
                try await resolveConflict(localPost: post)
            }
        }
    }

    // ── Download remote changes ───────────────────────────────
    private func downloadRemoteChanges() async throws {
        let lastSync = try await repository.lastSuccessfulSyncDate()
        let remotePosts = try await apiClient.fetchChanges(since: lastSync)  // server-side filtering
        for remote in remotePosts {
            let local = try await repository.find(id: remote.id)
            if let local {
                try await merge(local: local, remote: remote)
            } else {
                try await repository.insert(remote)
            }
        }
        try await repository.recordSyncDate(Date())
    }

    // ── Field-level merge ─────────────────────────────────────
    private func merge(local: Post, remote: Post) async throws {
        // If no local pending changes, remote wins unconditionally
        guard local.isSyncPending else {
            try await repository.update(remote)
            return
        }

        // Field-level: take the newer value per field
        var merged = local
        if remote.titleUpdatedAt > local.titleUpdatedAt { merged.title = remote.title }
        if remote.bodyUpdatedAt  > local.bodyUpdatedAt  { merged.body  = remote.body  }
        merged.isSyncPending = true    // merged result still needs upload
        try await repository.update(merged)
    }

    // ── Conflict resolution ───────────────────────────────────
    private func resolveConflict(localPost: Post) async throws {
        let serverPost = try await apiClient.fetch(id: localPost.id)

        // Strategy: last-write-wins by updatedAt
        if localPost.updatedAt > serverPost.updatedAt {
            // Local is newer — retry upload with force flag
            let updated = try await apiClient.upsert(localPost, force: true)
            try await repository.markSynced(localPost.id, serverUpdatedAt: updated.updatedAt)
        } else {
            // Server is newer — discard local changes
            try await repository.update(serverPost)
        }
    }
}

// ── Connectivity-driven sync trigger ─────────────────────────
import Network

class SyncCoordinator {
    private let syncEngine: SyncEngine
    private let monitor = NWPathMonitor()
    private var cancellables = Set<AnyCancellable>()

    init(syncEngine: SyncEngine) {
        self.syncEngine = syncEngine
        monitor.pathUpdateHandler = { [weak self] path in
            if path.status == .satisfied {
                Task { try? await self?.syncEngine.sync() }
            }
        }
        monitor.start(queue: DispatchQueue(label: "SyncCoordinator.monitor"))
    }
}

// ── GRDB progressive migration ────────────────────────────────
import GRDB

var migrator = DatabaseMigrator()

migrator.registerMigration("v1_initial") { db in
    try db.create(table: "post") { t in
        t.column("id", .text).primaryKey()
        t.column("title", .text).notNull()
        t.column("updatedAt", .datetime).notNull()
        t.column("isSyncPending", .boolean).notNull().defaults(to: false)
    }
}

migrator.registerMigration("v2_add_body") { db in
    try db.alter(table: "post") { t in
        t.add(column: "body", .text).defaults(to: "")
    }
}

migrator.registerMigration("v3_add_field_timestamps") { db in
    // Non-nullable column with default backfill
    try db.alter(table: "post") { t in
        t.add(column: "titleUpdatedAt", .datetime)
        t.add(column: "bodyUpdatedAt", .datetime)
    }
    // Backfill existing rows
    try db.execute(sql: "UPDATE post SET titleUpdatedAt = updatedAt, bodyUpdatedAt = updatedAt")
}

// ── NSPersistentCloudKitContainer sync ───────────────────────
import CoreData

class CloudSyncController {
    let container: NSPersistentCloudKitContainer

    init() {
        container = NSPersistentCloudKitContainer(name: "MyApp")

        // Configure for CloudKit sync
        guard let description = container.persistentStoreDescriptions.first else { return }
        description.cloudKitContainerOptions = NSPersistentCloudKitContainerOptions(
            containerIdentifier: "iCloud.com.myapp"
        )

        container.loadPersistentStores { _, error in
            if let error { print("CloudKit load error: \(error)") }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyStoreTrumpMergePolicy

        // Observe sync events
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(syncEventChanged),
            name: NSPersistentCloudKitContainer.eventChangedNotification,
            object: container
        )
    }

    @objc private func syncEventChanged(_ notification: Notification) {
        guard let event = notification.userInfo?[NSPersistentCloudKitContainer.eventNotificationUserInfoKey]
                as? NSPersistentCloudKitContainer.Event else { return }
        if let error = event.error {
            print("CloudKit sync error: \(error)")
        }
    }
}

// ── Soft delete pattern ───────────────────────────────────────
// Instead of DELETE FROM post WHERE id = ?, mark as deleted:
// UPDATE post SET isDeleted = 1, updatedAt = CURRENT_TIMESTAMP WHERE id = ?
// Sync engine propagates the tombstone to the server
// Server-side cleanup job permanently deletes records older than 30 days
```

## 5. Interview Questions & Answers

### Basic

**Q: What is an offline-first architecture and how does it differ from a network-first approach?**

A: In a **network-first** architecture, the app fetches data from the server before displaying it — the UI waits for the network. Offline means no content. In an **offline-first** architecture, the local database is the primary source of truth. The UI reads from and writes to local storage immediately — the network is used to sync changes in the background. The result: zero-latency UI, full functionality offline, and transparent error recovery when the network is unreliable. The tradeoff is implementation complexity: you must handle change tracking, conflict resolution, and merge logic. Offline-first is appropriate for apps where users regularly operate in poor connectivity (travel, field work) or where responsiveness is critical. It is not necessary for simple read-only API consumers where stale data is unacceptable.

**Q: What is a soft delete and why is it necessary for sync?**

A: A soft delete marks a record as deleted (`isDeleted = true`, `deletedAt = timestamp`) rather than removing its row. This is necessary for sync because a hard-deleted row leaves no trace — when the sync engine asks "what changed since last sync?", it has no way to discover that a record was deleted. With soft deletes, the tombstone row is included in the change set and synced to other clients/the server, which then cascade-delete from their own stores. Tombstones must be retained for long enough that all clients have had an opportunity to sync (typically 30–90 days), after which a server-side cleanup job permanently removes them. Soft deletes also enable undo and audit logs as a side benefit.

### Hard

**Q: Compare last-write-wins, field-level merge, and CRDTs for conflict resolution. When is each appropriate?**

A: **Last-write-wins (LWW)**: the record with the most recent `updatedAt` timestamp replaces the other. Simple to implement but loses data — if Alice updates the `title` and Bob updates the `body` simultaneously, one edit is discarded. Appropriate for settings, preferences, and records where one canonical value is always correct. **Field-level merge**: compare timestamps per field; take the newer value for each field independently. Alice's `title` and Bob's `body` both survive. Appropriate for structured records with independent fields edited by multiple users — covers the majority of real-world conflicts. Requires per-field `updatedAt` timestamps. **CRDTs (Conflict-free Replicated Data Types)**: mathematical data structures (G-Counter, OR-Set, Logoot for text) designed so concurrent updates from any order of merge always produce the same result — no conflicts by construction. Appropriate for collaborative real-time editing (shared text documents, whiteboards). High implementation complexity; typically use a library (Automerge, Yjs). For most iOS apps, field-level merge is the right balance of correctness and complexity.

**Q: How does Core Data's lightweight migration know which version to migrate from?**

A: Core Data inspects the metadata stored in the SQLite file's `Z_METADATA` table, which contains a hash of the `NSManagedObjectModel` that was used to create the store. At load time, Core Data compares this hash against the current model. If they differ, it searches for a migration path by enumerating the `.xcdatamodeld` version bundle — each `.xcdatamodel` file inside corresponds to one schema version. The system constructs an `NSMappingModel` by comparing consecutive versions and applies lightweight migration rules (new optional attributes, renamed entities with renaming identifiers). If no lightweight migration path can be inferred, loading fails with "The model used to open the store is incompatible." This is why `shouldInferMappingModelAutomatically = true` must be paired with `shouldMigrateStoreAutomatically = true`, and why skipping versions requires progressive migration through intermediate models.

### Expert

**Q: Design a sync architecture for an iOS app that supports multi-device offline editing with conflict resolution and periodic CloudKit sync.**

A: The architecture has five layers: (1) **Local store** (Core Data with `NSPersistentCloudKitContainer` or GRDB) as the source of truth. Every write goes here first and is immediately reflected in the UI. (2) **Change log**: a separate `PendingChange` table records every mutation (insert/update/delete) with a UUID, entity type, record ID, field deltas, and device timestamp. This is the upload queue. (3) **Sync engine** (an `actor`): on connectivity or foreground, uploads the `PendingChange` queue to the server in order; downloads remote changes since a stored change token (`CKServerChangeToken` for CloudKit or a cursor for a custom backend); applies downloads to the local store. (4) **Conflict resolver**: detects conflicts (local record has `isSyncPending = true` AND remote has a newer `serverUpdatedAt`) and applies field-level merge. Unresolvable conflicts (same field, both modified) surface to the user as a "choose version" sheet. (5) **Migration layer**: both the local schema (Core Data lightweight migrations or GRDB migrator) and the API schema (versioned endpoints + `Codable` with `decodeIfPresent` fallbacks) handle evolution independently. Key invariants: mutations are idempotent (server accepts re-sent changes gracefully via idempotency keys); tombstones are retained for 90 days; sync is triggered on foreground, on connectivity restoration, and via a background task (BGAppRefreshTask).

## 6. Common Issues & Solutions

**Issue: After a sync, duplicate records appear in the UI.**

Solution: The insert path doesn't check for existing records with the same server ID. Use an **upsert** (INSERT OR REPLACE in SQLite, or `NSBatchInsertRequest` with a unique constraint in Core Data) keyed on the server-assigned ID. Define a unique constraint on the `serverId` column and set `mergePolicy = NSMergeByPropertyStoreTrumpMergePolicy` on the import context.

**Issue: CloudKit sync stops working silently — no error, no updates.**

Solution: Observe `NSPersistentCloudKitContainer.eventChangedNotification` and log sync event errors. Common causes: iCloud account signed out, CKErrorAccountTemporarilyUnavailable, schema mismatch (required attributes block CloudKit which requires all optional). Also check that the CloudKit container identifier matches the app's entitlement and that the CloudKit schema has been "deployed to production" in the CloudKit dashboard.

**Issue: GRDB migration fails on app update — users' databases are corrupted.**

Solution: Each migration must be a self-contained SQL transaction. Verify every migration runs cleanly on a fresh build before shipping. Test migrations against production-representative data sizes. If a migration is irreversible or has run partially, implement a **recovery path**: detect the corrupted schema version (GRDB stores this in `grdb_migrations`), show a "database repair" UI, and offer to re-download data from the server after clearing the store.

**Issue: Sync conflicts cause data loss — remote edits overwrite local changes silently.**

Solution: Implement soft deletes and per-field timestamps. Before applying a remote record, check `isSyncPending` — if `true`, apply field-level merge rather than a blanket overwrite. Log all conflict resolutions for debugging. Consider surfacing a "changes from another device" indicator in the UI so users are aware of merges.

## 7. Related Topics

- [Core Data](core-data.md) — NSPersistentCloudKitContainer for CloudKit sync; lightweight migration
- [SQLite & Realm](sqlite-realm.md) — GRDB DatabaseMigrator; Realm Atlas Device Sync
- [UserDefaults](userdefaults.md) — NSUbiquitousKeyValueStore for lightweight multi-device preference sync
- [Advanced Networking](../07-networking/advanced-networking.md) — offline request queue, NWPathMonitor, sync triggers
- [Actors](../03-concurrency/actors.md) — actor-based sync engine for safe concurrent access
