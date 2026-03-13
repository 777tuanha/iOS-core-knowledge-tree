# File System

## 1. Overview

The iOS file system provides an API for reading and writing arbitrary data — images, audio, JSON blobs, documents, databases, and binary files. Every iOS app runs inside a sandbox: a private directory tree that prevents access to other apps' files. `FileManager` is the primary interface for navigating and manipulating the file system. `Data` provides reading and writing of raw bytes; `Codable` types can be persisted as JSON or plist files. Understanding the sandbox directory structure, backup behaviour, file protection classes, and file coordination (for document-based apps and extensions) is essential for correct, performant file system usage.

## 2. Simple Explanation

The iOS file system sandbox is like a set of labelled drawers in your private office. **Documents/** is your filing cabinet — important papers you want backed up. **Caches/** is your desk inbox — working copies you can recreate if lost. **tmp/** is your whiteboard — temporary notes that get erased when you leave. The `FileManager` is your personal assistant who creates, moves, and deletes files in these drawers. The building security (iOS sandbox) ensures no other tenant can enter your office, and a vault lock (NSFileProtection) can further encrypt individual drawers.

## 3. Deep iOS Knowledge

### Sandbox Directory Structure

```
<App Sandbox>/
├── <AppName>.app/          ← Read-only bundle (compiled code, assets, plists)
├── Documents/              ← User data; iTunes + iCloud backup; user-visible in Files app
│   └── Inbox/              ← Files delivered via AirDrop or document sharing
├── Library/
│   ├── Application Support/ ← App databases, support files; backed up; not user-visible
│   ├── Caches/             ← Downloaded/derived data; NOT backed up; can be purged by OS
│   └── Preferences/        ← UserDefaults plist files (managed by system)
└── tmp/                    ← Temporary files; NOT backed up; purged between launches
```

**Key rule**: If the OS needs storage space, it may purge `Caches/`. Never store data in `Caches/` that cannot be recreated from a canonical source.

### Getting Standard Directory URLs

```swift
let fm = FileManager.default

// Documents
let docs = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]

// Library/Application Support
let appSupport = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]

// Library/Caches
let caches = fm.urls(for: .cachesDirectory, in: .userDomainMask)[0]

// tmp
let tmp = URL(fileURLWithPath: NSTemporaryDirectory())
```

### Reading and Writing Files

`Data` reads and writes are the primitive operations:

```swift
let url = docs.appendingPathComponent("config.json")

// Write
try data.write(to: url, options: .atomic)   // .atomic writes to temp then renames — safe

// Read
let loaded = try Data(contentsOf: url)
```

**Write options**:
- `.atomic` — writes to a temp file, then atomically renames to the destination; prevents partial-write corruption.
- `.withoutOverwriting` — fails if the file already exists.
- `.completeFileProtection` — enables file protection (equivalent to NSFileProtectionComplete).

### File Protection Classes

iOS encrypts files when the device is locked. The protection class determines when the file is accessible:

| Class | Accessible when |
|-------|----------------|
| `NSFileProtectionComplete` | Only while device is unlocked |
| `NSFileProtectionCompleteUnlessOpen` | After file is opened while unlocked, remains accessible |
| `NSFileProtectionCompleteUntilFirstUserAuthentication` | After first unlock (default for most files) |
| `NSFileProtectionNone` | Always accessible (no extra encryption) |

Set the protection class via file attributes or write options:

```swift
try data.write(to: url, options: .completeFileProtection)
// or
try fm.setAttributes([.protectionKey: FileProtectionType.complete], ofItemAtPath: url.path)
```

### FileManager Operations

```swift
let fm = FileManager.default

// Check existence
fm.fileExists(atPath: url.path)

// Create directory
try fm.createDirectory(at: url, withIntermediateDirectories: true)

// Copy / Move
try fm.copyItem(at: source, to: destination)
try fm.moveItem(at: source, to: destination)

// Delete
try fm.removeItem(at: url)

// List contents
let contents = try fm.contentsOfDirectory(at: docs, includingPropertiesForKeys: [.fileSizeKey, .creationDateKey])

// File attributes
let attrs = try fm.attributesOfItem(atPath: url.path)
let size  = attrs[.size] as? Int
```

### File Coordination (Extensions and Document-Based Apps)

When multiple processes (app + extension) may read/write the same file simultaneously, use `NSFileCoordinator` to serialise access and prevent corruption:

```swift
let coordinator = NSFileCoordinator()
var error: NSError?
coordinator.coordinate(writingItemAt: url, options: .forReplacing, error: &error) { resolvedURL in
    try? data.write(to: resolvedURL, options: .atomic)
}
```

### Excluding Files from iCloud Backup

Mark cache and derived data files so iCloud doesn't waste bandwidth syncing them:

```swift
var url = caches.appendingPathComponent("large-cache.dat")
var resourceValues = URLResourceValues()
resourceValues.isExcludedFromBackup = true
try url.setResourceValues(resourceValues)
```

Apple's App Review guidelines require that data that can be regenerated must not be stored in `Documents/` (which is backed up). Store regenerable data in `Caches/` or exclude it explicitly.

### Streaming Large Files

For large files, avoid loading the entire content into memory:

```swift
// Read line-by-line with InputStream
let stream = InputStream(url: url)!
stream.open()
var buffer = [UInt8](repeating: 0, count: 4096)
while stream.hasBytesAvailable {
    let count = stream.read(&buffer, maxLength: buffer.count)
    // process buffer[0..<count]
}
stream.close()
```

## 4. Practical Usage

```swift
import Foundation

// ── Codable persistence to file ───────────────────────────────
struct DiskStorage<T: Codable> {
    private let url: URL
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(filename: String, in directory: FileManager.SearchPathDirectory = .applicationSupportDirectory) {
        let base = FileManager.default.urls(for: directory, in: .userDomainMask)[0]
        url = base.appendingPathComponent(filename)
        // Ensure directory exists
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
    }

    func save(_ value: T) throws {
        let data = try encoder.encode(value)
        try data.write(to: url, options: .atomic)        // atomic prevents partial writes
    }

    func load() throws -> T {
        let data = try Data(contentsOf: url)
        return try decoder.decode(T.self, from: data)
    }

    func delete() throws {
        try FileManager.default.removeItem(at: url)
    }

    var exists: Bool { FileManager.default.fileExists(atPath: url.path) }
}

// Usage:
// let store = DiskStorage<[Post]>(filename: "cached_posts.json")
// try store.save(posts)
// let posts = try store.load()

// ── Image cache on disk ───────────────────────────────────────
actor ImageDiskCache {
    private let cacheDirectory: URL

    init() {
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        cacheDirectory = caches.appendingPathComponent("ImageCache")
        try? FileManager.default.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
    }

    func store(_ data: Data, key: String) throws {
        let url = cacheDirectory.appendingPathComponent(sanitise(key))
        try data.write(to: url, options: .atomic)
    }

    func load(key: String) -> Data? {
        let url = cacheDirectory.appendingPathComponent(sanitise(key))
        return try? Data(contentsOf: url)
    }

    func clear() throws {
        let files = try FileManager.default.contentsOfDirectory(at: cacheDirectory,
                                                                 includingPropertiesForKeys: nil)
        try files.forEach { try FileManager.default.removeItem(at: $0) }
    }

    func cacheSize() throws -> Int {
        let files = try FileManager.default.contentsOfDirectory(
            at: cacheDirectory, includingPropertiesForKeys: [.fileSizeKey]
        )
        return try files.reduce(0) {
            let size = try $1.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
            return $0 + size
        }
    }

    private func sanitise(_ key: String) -> String {
        key.components(separatedBy: CharacterSet.alphanumerics.inverted).joined(separator: "_")
    }
}

// ── File with protection class ────────────────────────────────
func writeProtectedFile(data: Data, filename: String) throws {
    let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let url = docs.appendingPathComponent(filename)
    // .completeFileProtection = accessible only when device is unlocked
    try data.write(to: url, options: [.atomic, .completeFileProtection])
}

// ── Excluding from iCloud backup ─────────────────────────────
func excludeFromBackup(url: inout URL) throws {
    var resourceValues = URLResourceValues()
    resourceValues.isExcludedFromBackup = true
    try url.setResourceValues(resourceValues)
}

// ── Move downloaded file to permanent location ────────────────
// Called in URLSessionDownloadDelegate.urlSession(_:downloadTask:didFinishDownloadingTo:)
func moveDownloadedFile(from tempURL: URL, filename: String) throws -> URL {
    let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
    let dest = appSupport.appendingPathComponent(filename)
    if FileManager.default.fileExists(atPath: dest.path) {
        try FileManager.default.removeItem(at: dest)    // remove existing version
    }
    try FileManager.default.moveItem(at: tempURL, to: dest)  // move from temp
    return dest
}

// ── Listing files with attributes ────────────────────────────
func listDocuments() throws -> [(name: String, size: Int, modified: Date)] {
    let fm = FileManager.default
    let docs = fm.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let keys: [URLResourceKey] = [.fileSizeKey, .contentModificationDateKey]

    return try fm.contentsOfDirectory(at: docs, includingPropertiesForKeys: keys)
        .compactMap { url in
            let values = try url.resourceValues(forKeys: Set(keys))
            return (
                name:     url.lastPathComponent,
                size:     values.fileSize ?? 0,
                modified: values.contentModificationDate ?? .distantPast
            )
        }
        .sorted { $0.modified > $1.modified }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What are the main sandbox directories in an iOS app and when should you use each?**

A: **`Documents/`** is for user-generated content that should be backed up to iCloud/iTunes and visible to the user in the Files app (for document-based apps). **`Library/Application Support/`** is for app-managed data files (Core Data stores, databases, support files) that should be backed up but are not user-visible. **`Library/Caches/`** is for data that can be regenerated — downloaded images, network response caches, precomputed results. The OS may purge it under storage pressure; do not store anything irreplaceable here. **`tmp/`** is for truly temporary files needed only during the current session; the OS clears it between launches. The wrong choice leads to either wasted iCloud backup space (large derived data in `Documents/`) or data loss on low-storage devices (critical files in `Caches/`).

**Q: What is atomic file writing and why does it matter?**

A: An atomic write uses a write-then-rename pattern: data is written to a temporary file in the same directory, then the temp file is atomically renamed to the target path. Because rename is an atomic OS operation (it either completes or doesn't, no partial state), the target file always contains either the old complete content or the new complete content — never a partially-written mix. This is critical for app restarts, crashes, and power loss during a write. In Swift, `data.write(to: url, options: .atomic)` enables this. For non-atomic writes, a crash mid-write can leave the file in a corrupt state that the app cannot parse on the next launch.

### Hard

**Q: How do you prevent a file from being backed up to iCloud and why is this important?**

A: Set the `isExcludedFromBackup` resource value to `true` on the file URL using `url.setResourceValues(...)`. This is important for two reasons: (1) **Apple's App Store guidelines** require that content that can be recreated (cached images, downloaded content, derived data) must not be stored in backed-up directories. Violating this risks App Review rejection and wastes users' iCloud storage. (2) **Performance**: large caches in `Documents/` slow down iCloud backup and restore. The correct approach is to store regenerable data in `Library/Caches/` (automatically excluded) or, if it must live in `Documents/`, explicitly exclude it. Note that files in `tmp/` and `Library/Caches/` are automatically excluded — only files in `Documents/` and `Library/Application Support/` need manual exclusion.

**Q: When should you use `NSFileCoordinator` and why?**

A: `NSFileCoordinator` serialises concurrent file access across process boundaries — particularly between an app and its extensions (share extension, widget, keyboard). Without coordination, an app writing a file while an extension reads it can result in a torn read (the extension sees partial data). `NSFileCoordinator` uses a file presenter protocol (`NSFilePresenter`) to notify interested parties of changes and to arbitrate access. Use it whenever: (1) a file is shared between the app and an extension via an App Group container; (2) implementing a document-based app with `UIDocument` (which uses `NSFileCoordinator` internally); (3) reading/writing a file that another process might modify. For app-private files never accessed by extensions, `NSFileCoordinator` is unnecessary overhead.

### Expert

**Q: How would you design a disk cache that respects iOS storage pressure and Apple's file system guidelines?**

A: A well-designed disk cache has four properties: (1) **Correct directory**: store in `Library/Caches/` so the OS can purge it automatically under storage pressure, or use `NSPurgeableData` / `NSCache` in memory. (2) **Backup exclusion**: if cache files must live in `Documents/` for any reason, mark them with `isExcludedFromBackup = true`. (3) **Size management**: track total cache size using `URLResourceKey.fileSizeKey`; implement LRU eviction when a threshold is exceeded (e.g., 100 MB). Store file metadata (access time, size) in a separate index file or SQLite to avoid enumerating the directory on every operation. (4) **Respond to storage pressure**: observe `UIApplication.didReceiveMemoryWarningNotification` (for in-memory caches) and `NSProcessInfo.thermalState` or `NSFileManager`'s `volumeAvailableCapacityForImportantUsage` to proactively evict when the device is constrained. Also handle `NSNotification.Name.NSBundleResourceRequestLowDiskSpace` for on-demand resource scenarios.

## 6. Common Issues & Solutions

**Issue: File disappears between app launches on device (but works on Simulator).**

Solution: The file is being stored in `tmp/` or `Library/Caches/`, which the OS purges. Move it to `Library/Application Support/` (for app data) or `Documents/` (for user data).

**Issue: `Data(contentsOf:)` crashes with out-of-memory for a large file.**

Solution: `Data(contentsOf:)` loads the entire file into memory. For large files (video, audio, large databases), use `InputStream` for streaming reads, or `FileHandle` for random access. For media files, hand the URL directly to `AVPlayer` or `UIImage(contentsOfFile:)` which manage memory internally.

**Issue: Writing a file fails with "No such file or directory" even though the path looks correct.**

Solution: The parent directory doesn't exist. Use `FileManager.default.createDirectory(at: parentURL, withIntermediateDirectories: true)` before writing. The `Library/Application Support/` directory itself may not exist on a fresh install — always create it before writing.

**Issue: File written in the app is not visible in the widget extension.**

Solution: App and extension sandboxes are separate. Use an App Group shared container: `FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: "group.com.myapp")` returns the shared container URL, accessible by both app and extension.

## 7. Related Topics

- [UserDefaults](userdefaults.md) — for small key-value data; not for binary files
- [Keychain](keychain.md) — for encrypted small secrets
- [Core Data](core-data.md) — Core Data store files live in `Library/Application Support/`
- [URLSession](../07-networking/urlsession.md) — download tasks write to tmp; move to permanent location in delegate
- [Advanced Networking](../07-networking/advanced-networking.md) — disk-based response caching patterns
