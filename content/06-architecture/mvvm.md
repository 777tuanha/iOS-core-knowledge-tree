# MVVM — Model-View-ViewModel

## 1. Overview

MVVM (Model-View-ViewModel) separates **presentation logic** from the View into a dedicated **ViewModel** object. The ViewModel transforms raw Model data into display-ready values, handles user commands, and owns async work — without importing UIKit or knowing anything about the specific View. The View observes the ViewModel and updates automatically when its state changes. This separation makes ViewModels independently unit-testable and views declaratively simple. MVVM is the dominant architecture for modern iOS apps using both UIKit (via Combine or callbacks) and SwiftUI (via `ObservableObject`).

## 2. Simple Explanation

Think of a news broadcast. The **Model** is the raw Reuters wire feed — facts with no formatting. The **ViewModel** is the news editor — they take raw facts, decide what's important, format the headlines ("3 sentences max, past tense"), and prepare graphics. The **View** is the TV anchor — they read exactly what the editor prepared. The anchor never calls Reuters directly, and Reuters never calls the anchor. The editor is the only one who talks to both. Crucially, you can test the editor's work by reading their scripts — you don't need to broadcast the show.

## 3. Deep iOS Knowledge

### ViewModel Responsibilities

| Responsibility | Example |
|---------------|---------|
| Transform model data for display | `DateFormatter.string(from: date)` |
| Expose observable state | `@Published var title: String` |
| Handle user actions | `func submitTapped() async` |
| Own async work | `Task { ... }` |
| Call domain/service layer | `userService.fetchUser(id:)` |
| Input validation | `var isSubmitEnabled: Bool { email.contains("@") }` |

### What the ViewModel Must NOT Do

- Import `UIKit` or `SwiftUI` (except `@MainActor`, which is in Foundation's concurrency module)
- Reference a specific View type
- Perform navigation (delegate that to Coordinator)
- Know how data is persisted (delegate to Repository/Service)

### ViewModel in UIKit (Combine binding)

```swift
@MainActor
class ProfileViewModel: ObservableObject {
    @Published private(set) var displayName = ""
    @Published private(set) var isLoading = false

    private let userService: UserServiceProtocol

    init(userService: UserServiceProtocol) { self.userService = userService }

    func loadProfile(id: String) async {
        isLoading = true
        defer { isLoading = false }
        let user = try? await userService.fetchUser(id: id)
        displayName = user?.name ?? ""
    }
}
```

UIViewController binds to `@Published` properties via `sink`. See [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) for full UIKit binding code.

### ViewModel in SwiftUI

SwiftUI is MVVM by design — `ObservableObject` is the ViewModel protocol. The View uses `@StateObject` (owned) or `@ObservedObject` (injected):

```swift
struct ProfileView: View {
    @StateObject private var vm = ProfileViewModel(userService: UserService())

    var body: some View {
        Group {
            if vm.isLoading { ProgressView() }
            else { Text(vm.displayName) }
        }
        .task { await vm.loadProfile(id: "42") }
    }
}
```

See [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) for `@StateObject` vs `@ObservedObject` ownership rules.

### MVVM vs MVC — Testability

| | MVC | MVVM |
|--|-----|------|
| Unit-test business logic | Hard — VC requires UIKit | Easy — ViewModel is a plain Swift class |
| Test networking | Hard — inside VC | Easy — inject mock service |
| Test form validation | Hard | Easy — `XCTAssertTrue(vm.isSubmitEnabled)` |
| Test async state | Hard | Easy — `await vm.load(); XCTAssertEqual(vm.items, expected)` |

### Binding Strategies (UIKit)

| Strategy | Pros | Cons |
|----------|------|------|
| Combine `@Published` + `sink` | Type-safe, cancellable | Requires Combine knowledge |
| Closures (callback) | Simple, no framework | Not reactive; manual call |
| NotificationCenter | Decoupled | Type-unsafe, hard to test |
| KVO | Works with Obj-C types | Verbose, crash-prone |
| RxSwift | Mature, powerful | Third-party dependency |

### Input/Output ViewModel Pattern

A clean pattern for documenting the ViewModel interface:

```swift
protocol ProfileViewModelInput {
    func loadProfile(id: String)
    func editTapped()
}

protocol ProfileViewModelOutput: AnyObject {
    var displayName: AnyPublisher<String, Never> { get }
    var isLoading: AnyPublisher<Bool, Never> { get }
}

typealias ProfileViewModelProtocol = ProfileViewModelInput & ProfileViewModelOutput
```

This makes the ViewModel interface explicit and swap-able in tests.

### Reactive vs Non-Reactive MVVM

Non-reactive MVVM (closures):
```swift
class ViewModel {
    var onDataLoaded: (([Item]) -> Void)?
    func load() {
        service.fetch { [weak self] items in
            self?.onDataLoaded?(items)
        }
    }
}
```

Reactive MVVM (Combine):
```swift
class ViewModel: ObservableObject {
    @Published var items: [Item] = []
    func load() {
        service.fetchPublisher()
            .receive(on: .main)
            .assign(to: &$items)
    }
}
```

Reactive is more composable; closure-based is simpler and has no framework dependency.

## 4. Practical Usage

```swift
import Foundation
import Combine

// ── Protocols for testability ─────────────────────────────────
protocol UserServiceProtocol {
    func fetchUser(id: String) async throws -> User
}

struct User { let id: String; let name: String; let email: String }

// ── ViewModel ─────────────────────────────────────────────────
@MainActor
final class UserDetailViewModel: ObservableObject {
    // Outputs — observed by the View
    @Published private(set) var displayName = ""
    @Published private(set) var emailText = ""
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    // Computed output — derived from state; no need to store separately
    var hasError: Bool { errorMessage != nil }

    private let userID: String
    private let service: UserServiceProtocol

    // Constructor injection — testable
    init(userID: String, service: UserServiceProtocol) {
        self.userID = userID
        self.service = service
    }

    // MARK: – Inputs (user actions)
    func onViewAppear() async {
        await loadUser()
    }

    func retryTapped() async {
        errorMessage = nil
        await loadUser()
    }

    // MARK: – Private
    private func loadUser() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let user = try await service.fetchUser(id: userID)
            displayName = user.name
            emailText = user.email
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// ── SwiftUI View (thin — reads ViewModel state only) ──────────
import SwiftUI

struct UserDetailView: View {
    @StateObject private var vm: UserDetailViewModel

    init(userID: String, service: UserServiceProtocol) {
        _vm = StateObject(wrappedValue: UserDetailViewModel(
            userID: userID, service: service
        ))
    }

    var body: some View {
        Group {
            if vm.isLoading {
                ProgressView("Loading...")
            } else if vm.hasError {
                VStack {
                    Text(vm.errorMessage ?? "Unknown error").foregroundStyle(.red)
                    Button("Retry") { Task { await vm.retryTapped() } }
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    Text(vm.displayName).font(.title)
                    Text(vm.emailText).foregroundStyle(.secondary)
                }
                .padding()
            }
        }
        .task { await vm.onViewAppear() }
        .navigationTitle("Profile")
    }
}

// ── Mock for unit tests ────────────────────────────────────────
class MockUserService: UserServiceProtocol {
    var stubbedUser: User?
    var stubbedError: Error?

    func fetchUser(id: String) async throws -> User {
        if let error = stubbedError { throw error }
        return stubbedUser ?? User(id: id, name: "Test User", email: "test@test.com")
    }
}

// ── Unit test (no UIKit needed) ────────────────────────────────
// class UserDetailViewModelTests: XCTestCase {
//     func testLoadSetsDisplayName() async throws {
//         let mock = MockUserService()
//         mock.stubbedUser = User(id: "1", name: "Alice", email: "a@b.com")
//         let vm = await UserDetailViewModel(userID: "1", service: mock)
//         await vm.onViewAppear()
//         let name = await vm.displayName
//         XCTAssertEqual(name, "Alice")
//     }
// }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the ViewModel's role in MVVM, and what should it NOT do?**

A: The ViewModel transforms Model data into display-ready values (formatted strings, booleans for UI state), handles user-initiated commands (button taps → service calls), and exposes observable state for the View. It should **not**: import UIKit or SwiftUI (it must remain UI-framework-agnostic and testable in isolation); reference the View directly; perform navigation (that is the Coordinator's job); or access networking or persistence directly (delegate to service/repository layers). This separation ensures the ViewModel can be instantiated and tested with `XCTestCase` without launching a view.

**Q: How does MVVM improve testability compared to MVC?**

A: In MVC, business and presentation logic lives in `UIViewController`, which requires UIKit to instantiate and test. In MVVM, that logic moves to the ViewModel — a plain Swift class with no UIKit imports. You can write: `let vm = ViewModel(service: MockService()); await vm.load(); XCTAssertEqual(vm.items.count, 3)`. No `UIViewController`, no `XCUITest`, no app launch. This drastically shortens test run time and makes edge cases (error states, loading states) easy to test by controlling the mock service's responses.

### Hard

**Q: Describe the retain cycle risk with Combine bindings in a MVVM UIKit setup and how to prevent it.**

A: The cycle: `UIViewController` holds a `Set<AnyCancellable>`. Each `AnyCancellable` holds the `sink` closure. The `sink` closure captures `self` (the ViewController) strongly. The ViewController holds the Set → holds the closures → holds the ViewController. Fix: use `[weak self]` in every `sink` closure. Additionally, `assign(to:on: self)` creates a cycle via a different path — the `assign` subscriber holds a strong reference to its target. Use `assign(to: &$publishedProperty)` (iOS 14+) or `sink { [weak self] in self?.prop = $0 }` instead. Verify with the Memory Graph Debugger after every significant binding change.

**Q: What is the difference between a "reactive" ViewModel (Combine) and a "callback" ViewModel, and when do you choose each?**

A: A reactive ViewModel exposes `@Published` / `AnyPublisher` outputs and uses Combine operators for pipelines — debounce, flatMap, combineLatest. It integrates naturally with SwiftUI and enables powerful operator-based transformations. A callback ViewModel uses closures (`var onDataLoaded: (([Item]) -> Void)?`) — simpler, no framework dependency, and requires no knowledge of Combine. Use the callback pattern for small teams, older codebases, or when the reactive transformations are not needed. Use Combine when you need operators (debounce, merge), when you're integrating with SwiftUI's `@Published`, or when the data flow benefits from composable pipelines.

### Expert

**Q: How would you architect a ViewModel that must coordinate two parallel async operations and expose a combined result, including a loading and error state?**

A: With async/await: use `async let` for parallel execution. The ViewModel exposes `@Published var state: ViewState` where `ViewState` is an enum (`loading`, `loaded(combined)`, `error(message)`). The load function sets state to `.loading`, fires both tasks with `async let`, awaits the combined tuple, then sets state to `.loaded`. With Combine: use `Publishers.Zip(publisherA, publisherB)` to combine results. Wire `isLoading` to a shared `PassthroughSubject<Bool, Never>` that fires `true` on subscription start and `false` on completion via `handleEvents`. Error state is derived from the `.catch` branch. The async/await version is simpler to read and test; the Combine version is preferred when the result feeds directly into a Combine pipeline (e.g., bound to `@Published` via `assign`).

## 6. Common Issues & Solutions

**Issue: ViewModel is difficult to instantiate in tests because it requires UIKit types.**

Solution: The ViewModel should never import UIKit. If it does, extract the UIKit dependency into a protocol and inject it. For example, instead of passing a `UIColor`, pass a struct `DisplayColor { let hex: String }`.

**Issue: `@Published` property changes on a background thread — purple warning in Xcode.**

Solution: Mark the ViewModel class `@MainActor`. All `@Published` mutations will then guarantee main-thread execution, and the compiler will enforce this at call sites.

**Issue: SwiftUI view not updating when ViewModel's `@Published` changes.**

Solution: The ViewModel is stored as `@ObservedObject` in a View that creates it — every parent re-render recreates the ViewModel, resetting state. Switch to `@StateObject` to give the View ownership and stable lifetime.

## 7. Related Topics

- [MVC](mvc.md) — what MVVM improves upon
- [MVP & VIPER](mvp-viper.md) — stricter architectural alternatives
- [Dependency Injection](dependency-injection.md) — injecting services into the ViewModel
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — UIKit/SwiftUI implementation details
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — ObservableObject in SwiftUI
- [Combine + UIKit & SwiftUI](../05-reactive-programming/combine-swiftui-uikit.md) — binding layer
