# Senior iOS Knowledge Tree

---

## 1. Swift Language

### Core Concepts
- Value vs Reference types
- Struct vs Class
- Copy-on-write
- ARC basics
- weak vs unowned

### Generics & Protocols
- Generics
- Associated types
- Protocol-oriented programming
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
- Strong references
- Weak references
- Unowned references
- Retain cycles

### Closures
- Capture lists
- Escaping vs non-escaping
- Autoclosure

### Memory Performance
- Stack vs Heap
- Copy-on-write optimization
- Memory allocation patterns

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
- Thread safety
- Priority inversion

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
- Data pipelines
- Data binding

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

### Data Synchronization
- Offline-first architecture
- Conflict resolution
- Data migration

---

## 9. iOS Platform

### App Lifecycle
- AppDelegate
- SceneDelegate
- App states

### System Capabilities
- Background tasks
- Push notifications
- Deep links
- Universal links

### Platform Frameworks
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

### Framework Types
- Static libraries
- Dynamic frameworks
- XCFrameworks

---

## 11. Testing & Quality

### Testing Types
- Unit testing
- Integration testing
- UI testing
- Snapshot testing

### Testable Architecture
- Dependency injection
- Mocking
- Test doubles

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

### Optimization Techniques
- Memory optimization
- Reducing main-thread work
- Efficient data structures
- Lazy loading

---

## 13. App Startup & Runtime

### App Launch Process
- dyld
- Dynamic library loading
- App launch stages
- Initial view controller setup

### Startup Optimization
- Reducing startup work
- Lazy initialization
- Deferred loading
- Minimizing dynamic frameworks

### Runtime Behavior
- RunLoop
- Main thread scheduling
- Event processing

---

## 14. Security

### Data Security
- Keychain
- Encryption
- Secure storage

### Network Security
- HTTPS
- Certificate pinning
- Secure transport

### App Security
- Jailbreak detection
- Code obfuscation
- Secure coding practices

---

## 15. Design Patterns

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

### iOS Patterns
- Delegate
- Coordinator
- Dependency injection

---

## 16. Refactoring

### Code Smells
- Long methods
- Large classes
- Duplicate code
- Tight coupling

### Refactoring Techniques
- Extract method
- Extract class
- Move method
- Replace conditional with polymorphism

Reference: https://refactoring.guru

---

## 17. Observability

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

## 18. Accessibility (a11y)

### Core Accessibility
- VoiceOver
- Accessibility labels
- Accessibility traits
- Accessibility hints

### UI Support
- Dynamic Type
- Color contrast
- Reduce motion

### Tools
- Accessibility Inspector
- VoiceOver testing

---

## 19. App Distribution

### Code Signing
- Certificates
- Provisioning profiles
- Development vs Distribution

### Entitlements
- Push notifications
- Keychain access
- App groups

### Distribution
- TestFlight
- App Store submission
- Enterprise distribution

### Automation
- Fastlane
- CI/CD pipelines

---

## 20. Mobile System Design

### Architecture
- Offline-first architecture
- API-driven UI
- Feature flags
- Remote config

### Data Strategies
- Caching layers
- Pagination
- Sync strategies

### Large Scale Apps
- Modular architecture
- Shared components
- SDK design