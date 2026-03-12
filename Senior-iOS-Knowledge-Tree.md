# Senior iOS Knowledge Tree

## 1. Swift Language

### Core Concepts
- Value vs Reference types
- Struct vs Class
- Copy-on-write
- ARC
- weak vs unowned
- Retain cycles

### Generics & Protocols
- Generics
- Associated types
- Protocol oriented programming
- Existential types
- Type erasure

### Advanced Swift
- Result type
- Property wrappers
- KeyPath
- Dynamic member lookup
- Reflection (Mirror)

---

## 2. Memory Management

### ARC
- Strong reference
- Weak reference
- Unowned reference
- Retain cycles

### Closures
- Capture lists
- Escaping vs non-escaping
- Autoclosure

### Performance
- Stack vs Heap
- Copy-on-write
- Memory allocation

---

## 3. Concurrency

### Legacy Concurrency
- Grand Central Dispatch (GCD)
- DispatchQueue
- DispatchGroup
- DispatchSemaphore
- OperationQueue

### Modern Swift Concurrency
- async / await
- Task
- TaskGroup
- Structured concurrency
- Actor
- MainActor

### Concurrency Problems
- Race conditions
- Deadlocks
- Priority inversion
- Thread safety

---

## 4. UI Frameworks

### UIKit
- UIView lifecycle
- UIViewController lifecycle
- Event handling
- RunLoop
- Rendering pipeline
- AutoLayout
- UICollectionView / UITableView

### SwiftUI
- State
- Binding
- ObservedObject
- StateObject
- EnvironmentObject
- View identity
- Diffing system
- View lifecycle

### UI Architecture
- MVVM with UIKit
- MVVM with SwiftUI
- Coordinator pattern
- Navigation management

---

## 5. Reactive Programming

### Combine
- Publisher
- Subscriber
- Operators
- Subjects
- Backpressure
- Cancellation

### Concepts
- Reactive streams
- Data binding
- Async pipelines

---

## 6. Architecture

### Common Architectures
- MVC
- MVVM
- MVP
- VIPER / Clean Architecture
- The Composable Architecture (TCA)

### Design Principles
- SOLID
- Separation of concerns
- Dependency inversion
- Composition over inheritance

### Dependency Injection
- Constructor injection
- Service locator
- DI containers

### Modularization
- Feature modules
- Core modules
- Layered architecture
- Monolith vs modular

---

## 7. Networking

### HTTP Basics
- REST
- HTTP methods
- Status codes
- Headers

### iOS Networking
- URLSession
- Codable
- JSON parsing

### Advanced Networking
- Retry strategies
- Request interceptors
- Caching
- Pagination
- Offline handling

---

## 8. Data Persistence

### Local Storage
- UserDefaults
- Keychain
- File system

### Databases
- CoreData
- SQLite
- Realm

### Data Sync
- Offline-first design
- Conflict resolution
- Data migration

---

## 9. iOS Platform

### App Lifecycle
- AppDelegate
- SceneDelegate
- App states

### System Features
- Background tasks
- Push notifications
- Deep links
- Universal links

### Frameworks
- CoreLocation
- AVFoundation
- MapKit
- CoreAnimation

---

## 10. Dependency Management

### Package Managers
- Swift Package Manager
- CocoaPods
- Carthage

### Binary Frameworks
- XCFramework
- Static vs dynamic libraries

---

## 11. Testing & Quality

### Testing Types
- Unit tests
- Integration tests
- UI tests
- Snapshot tests

### Test Design
- Dependency injection
- Mocking
- Testable architecture

### Tools
- XCTest
- Quick / Nimble
- XCUITest

---

## 12. Performance

### Profiling Tools
- Instruments
- Time Profiler
- Allocations
- Leaks
- Energy Log

### Optimization
- App launch time
- Lazy loading
- Memory optimization
- Reducing main thread work

---

## 13. Security

### Data Security
- Keychain
- Encryption
- Secure storage

### Network Security
- HTTPS
- Certificate pinning

### App Security
- Jailbreak detection
- Code obfuscation

---

## 14. Design Patterns

### Creational
- Factory
- Builder
- Singleton

### Structural
- Adapter
- Decorator
- Facade
- Composite

### Behavioral
- Observer
- Strategy
- Command
- State

### iOS Common Patterns
- Delegate
- Coordinator
- Dependency injection

---

## 15. Refactoring

### Code Smells
- Long methods
- Large classes
- Duplicate code

### Refactoring Techniques
- Extract method
- Extract class
- Move method
- Replace conditional with polymorphism

Reference: https://refactoring.guru

---

## 16. Observability

### Crash Reporting
- Crashlytics
- Crash logs
- Symbolication

### Logging
- Structured logging
- OSLog

### Monitoring
- Analytics
- Metrics
- Feature flags

---

## 17. Mobile System Design

### Architecture
- Offline-first architecture
- API driven UI
- Feature flags
- Remote config

### Data Strategies
- Caching layers
- Pagination
- Sync strategies

### Large Apps
- Modular architecture
- Shared components
- SDK design