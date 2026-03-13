# Data Persistence

## Overview

Data persistence is how an iOS app stores state beyond the lifetime of a single run. Every production app persists something — user preferences, authentication tokens, downloaded content, structured records. Choosing the right storage mechanism for each type of data is a foundational architectural decision: the wrong choice leads to data loss, security vulnerabilities, poor performance, or unmaintainable migration code.

Apple's ecosystem provides a spectrum of persistence tools ranging from lightweight key-value storage (`UserDefaults`) to full relational databases (`Core Data`). Beyond these, the Keychain protects secrets with hardware-backed encryption, the file system handles arbitrary binary data, and third-party options like SQLite (via GRDB) and Realm offer alternatives with different tradeoffs.

For production-quality apps, persistence must also handle the hard problems: offline-first architecture (local data as the source of truth), conflict resolution (merging concurrent changes), and data migration (evolving schemas without data loss).

## Topics in This Section

- [UserDefaults](userdefaults.md) — Key-value storage for user preferences and lightweight app state; property wrappers, Suites, and limitations
- [Keychain](keychain.md) — Secure credential storage with hardware-backed encryption; SecItem API, access controls, Keychain groups, iCloud Keychain
- [File System](file-system.md) — FileManager API, sandbox directories, reading and writing files, document-based apps, file coordination
- [Core Data](core-data.md) — Apple's object graph persistence framework; NSManagedObject, NSPersistentContainer, fetch requests, relationships, migrations
- [SQLite & Realm](sqlite-realm.md) — Raw SQLite via GRDB, Realm object database; comparison with Core Data, reactive queries, migrations
- [Data Synchronization](data-sync.md) — Offline-first architecture, conflict resolution strategies, data migration patterns, CloudKit sync

## Persistence Mechanism Comparison

| Mechanism | Best for | Max practical size | Encrypted | Queryable |
|-----------|----------|--------------------|-----------|-----------|
| UserDefaults | Preferences, feature flags, small scalars | < 100 KB | No (plist on disk) | No |
| Keychain | Tokens, passwords, keys | < 4 KB per item | Yes (hardware AES) | No |
| File system | Binary data, images, JSON blobs, documents | Device storage | Optional (NSFileProtection) | No |
| Core Data | Structured records with relationships | Millions of rows | Optional (store encryption) | Yes (NSPredicate) |
| SQLite / GRDB | Structured data, complex queries | Millions of rows | Optional (SQLCipher) | Yes (SQL) |
| Realm | Structured data, reactive observation | Millions of rows | Optional (Realm Encrypt) | Yes (Realm query) |

## iOS App Sandbox Directories

```
App Sandbox/
├── Documents/          ← User-generated content; backed up by iTunes/iCloud
├── Library/
│   ├── Preferences/    ← UserDefaults plist files (automatic)
│   ├── Caches/         ← URLCache, downloaded images; NOT backed up; can be purged by OS
│   └── Application Support/  ← App databases, support files; backed up
├── tmp/                ← Temporary files; NOT backed up; purged between launches
└── (Bundle Resources)  ← Read-only app bundle; .app/
```

## Choosing the Right Storage

```
Is it a secret (token, password, key)?
  └─ YES → Keychain

Is it a user preference or small scalar (< 1 KB)?
  └─ YES → UserDefaults

Is it a binary blob (image, file, document)?
  └─ YES → File system (Documents/ or Caches/)

Is it structured relational data with queries / relationships?
  └─ YES → Core Data or SQLite/GRDB

Do you need reactive live queries with cross-platform sync?
  └─ YES → Realm or Core Data + CloudKit
```

## Relationship to Other Sections

- **Networking**: Downloaded data is cached or persisted — see [Advanced Networking](../07-networking/advanced-networking.md) for stale-while-revalidate and offline queues.
- **Architecture**: The Repository pattern abstracts persistence from business logic — see [Modularization](../06-architecture/modularization.md).
- **Concurrency**: Core Data's `NSManagedObjectContext` is not thread-safe; use `actor`-based wrappers — see [Actors](../03-concurrency/actors.md).
- **Security**: Keychain and file protection underpin app security — see [Keychain](keychain.md).
