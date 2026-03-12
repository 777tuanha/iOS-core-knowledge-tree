# MVVM & Coordinator

## 1. Overview

**MVVM** (Model-View-ViewModel) separates UI rendering logic (View) from presentation logic and state (ViewModel), keeping both testable and independently changeable. The ViewModel exposes data and commands; the View binds to them. The **Coordinator** pattern (also called Flow Coordinator) extracts navigation decisions from view controllers, solving the "Massive View Controller" problem and making navigation flows testable and reusable. Together, MVVM + Coordinator is the most common architecture for production UIKit apps; SwiftUI encourages MVVM with `ObservableObject` natively.

## 2. Simple Explanation

MVVM is like a restaurant: the **Model** is the kitchen (raw ingredients and recipes — pure data and business logic). The **ViewModel** is the chef — they take raw ingredients, prepare them, and package the dish. The **View** is the waiter — they display the finished dish to the customer and relay orders back to the chef. The chef never interacts directly with the customer; the waiter never knows how to cook.

The **Coordinator** is the maître d' — they decide where customers sit, which room they move to for dessert, and how to handle special requests for seating. Neither the chef nor the waiter needs to know the floor plan.

## 3. Deep iOS Knowledge

### MVVM Structure

| Layer | Responsibility | iOS type |
|-------|---------------|----------|
| Model | Business entities, data access, domain logic | `struct` / `class`, data services |
| ViewModel | Prepares model data for display, handles user actions, owns async work | `class` conforming to `ObservableObject` or plain class |
| View | Renders the ViewModel's output, forwards user actions | `UIViewController` (UIKit) / `View` struct (SwiftUI) |

### MVVM with UIKit — Binding Strategies

UIKit has no built-in binding mechanism. Common approaches:

**Closures (Callback-based)**:
```swift
class ProfileViewModel {
    var onProfileLoaded: ((Profile) -> Void)?
    var onError: ((Error) -> Void)?
    func loadProfile() { /* ... await ... onProfileLoaded?(profile) */ }
}
// VC calls viewModel.onProfileLoaded = { [weak self] profile in ... }
```

**Combine**:
```swift
class ProfileViewModel: ObservableObject {
    @Published var profile: Profile?
    @Published var error: Error?
}
// VC subscribes with Combine publishers
```

**async/await with @MainActor**:
```swift
@MainActor class ProfileViewModel {
    private(set) var profile: Profile?
    func loadProfile() async { /* ... */ }
}
// VC calls Task { await viewModel.loadProfile(); updateUI() }
```

### MVVM with SwiftUI

SwiftUI provides the binding layer natively. The ViewModel is an `ObservableObject`; the View uses `@StateObject` or `@ObservedObject`:

```swift
@MainActor
class LoginViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoading = false
    @Published var errorMessage: String?

    func login() async { /* ... */ }
}

struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()
    var body: some View {
        TextField("Email", text: $viewModel.email)
        // ...
    }
}
```

### @MainActor on ViewModels

All `@Published` property changes and UI-bound state updates must happen on the main thread. Marking the ViewModel class `@MainActor` ensures this at compile time — all methods run on the main thread by default, and async method calls that hop to a background executor automatically resume on the main thread when they return.

### Coordinator Pattern

A **Coordinator** object:
- Owns a `UINavigationController` (or equivalent).
- Creates and presents view controllers / views.
- Owns child coordinators for sub-flows.
- Does **not** know about business logic — only navigation logic.

```
AppCoordinator
  ├── AuthCoordinator    (login / register flow)
  │    └── LoginVC, RegisterVC
  └── MainCoordinator    (authenticated content)
       ├── FeedCoordinator
       │    └── FeedVC, PostDetailVC
       └── ProfileCoordinator
            └── ProfileVC, EditProfileVC
```

### Coordinator Implementation Steps

1. **Protocol**: Define a `Coordinator` protocol with `start()` and a child coordinator array.
2. **AppCoordinator**: Owns the UIWindow; decides whether to start Auth or Main flow.
3. **Child coordinators**: Own their navigation controller; present VCs.
4. **VC → Coordinator communication**: Via `delegate` (classic) or closures (modern).
5. **Finishing**: Child coordinator calls `parentCoordinator.childDidFinish(self)`.

### Retain Cycle Risks

| Pattern | Cycle | Fix |
|---------|-------|-----|
| VC holds Coordinator as strong delegate | VC → Coordinator → VC (if coordinator holds VC) | Use `weak var delegate` |
| ViewModel closure captures self | ViewModel → closure → ViewModel | Use `[weak self]` in closure |
| Coordinator keeps strong reference to VC | Coordinator → VC → Coordinator (via delegate) | `weak var delegate` on VC |

### Navigation in SwiftUI

SwiftUI 16+ (iOS 16+) introduced `NavigationStack` with a data-driven navigation path:

```swift
@State private var path = NavigationPath()

NavigationStack(path: $path) {
    ContentView()
        .navigationDestination(for: Destination.self) { dest in
            DestinationView(destination: dest)
        }
}

// Navigate:
path.append(Destination.profile(userID: "123"))
// Pop:
path.removeLast()
```

For complex SwiftUI navigation with deep links and coordinator-like separation, wrap the `NavigationPath` in an `@Observable` or `ObservableObject` router class.

## 4. Practical Usage

```swift
import UIKit
import Combine

// ─────────────────────────────────────────────────────────────
// MARK: – Model
// ─────────────────────────────────────────────────────────────

struct User {
    let id: String
    let name: String
    let email: String
}

// ─────────────────────────────────────────────────────────────
// MARK: – ViewModel (UIKit, Combine binding)
// ─────────────────────────────────────────────────────────────

@MainActor                              // all mutations on main thread
final class UserListViewModel: ObservableObject {
    @Published private(set) var users: [User] = []
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    private let userService: UserServiceProtocol

    init(userService: UserServiceProtocol) {
        self.userService = userService  // inject dependency — enables testing
    }

    func loadUsers() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            users = try await userService.fetchUsers()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func userSelected(at index: Int) -> User {
        users[index]
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – View (UIKit)
// ─────────────────────────────────────────────────────────────

protocol UserListViewControllerDelegate: AnyObject {
    func userListViewController(_ vc: UserListViewController, didSelect user: User)
}

class UserListViewController: UIViewController {
    weak var delegate: UserListViewControllerDelegate?  // weak to avoid retain cycle

    private let viewModel: UserListViewModel
    private var cancellables = Set<AnyCancellable>()
    private let tableView = UITableView()

    init(viewModel: UserListViewModel) {
        self.viewModel = viewModel
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        setupTableView()
        bindViewModel()
        Task { await viewModel.loadUsers() }
    }

    private func bindViewModel() {
        // Combine subscription — update table when users change
        viewModel.$users
            .receive(on: DispatchQueue.main)        // already @MainActor, but explicit here
            .sink { [weak self] _ in                // [weak self] prevents retain cycle
                self?.tableView.reloadData()
            }
            .store(in: &cancellables)

        viewModel.$isLoading
            .sink { [weak self] loading in
                // show/hide spinner
                _ = loading
                _ = self
            }
            .store(in: &cancellables)
    }

    private func setupTableView() {
        tableView.frame = view.bounds
        tableView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        tableView.dataSource = self
        tableView.delegate = self
        view.addSubview(tableView)
    }
}

extension UserListViewController: UITableViewDataSource, UITableViewDelegate {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        viewModel.users.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "Cell")
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: "Cell")
        let user = viewModel.users[indexPath.row]
        cell.textLabel?.text = user.name
        cell.detailTextLabel?.text = user.email
        return cell
    }

    func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        let user = viewModel.userSelected(at: indexPath.row)
        delegate?.userListViewController(self, didSelect: user)  // coordinator handles navigation
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Coordinator
// ─────────────────────────────────────────────────────────────

protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    func start()
}

extension Coordinator {
    func childDidFinish(_ child: Coordinator) {
        childCoordinators.removeAll { $0 === child }
    }
}

class UsersCoordinator: Coordinator, UserListViewControllerDelegate {
    var childCoordinators: [Coordinator] = []
    private let navigationController: UINavigationController

    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    func start() {
        let vm = UserListViewModel(userService: UserService())  // create dependencies
        let vc = UserListViewController(viewModel: vm)
        vc.delegate = self                                       // coordinator handles navigation
        navigationController.pushViewController(vc, animated: false)
    }

    // MARK: – UserListViewControllerDelegate
    func userListViewController(_ vc: UserListViewController, didSelect user: User) {
        // VC tells us "user selected"; we decide what to do (navigate)
        let detailCoordinator = UserDetailCoordinator(
            user: user,
            navigationController: navigationController
        )
        childCoordinators.append(detailCoordinator)
        detailCoordinator.start()
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – SwiftUI MVVM
// ─────────────────────────────────────────────────────────────

import SwiftUI

@MainActor
class LoginViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var isLoggedIn = false

    private let authService: AuthServiceProtocol

    init(authService: AuthServiceProtocol) {
        self.authService = authService
    }

    func login() async {
        guard !email.isEmpty, !password.isEmpty else {
            errorMessage = "Please fill all fields"
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            try await authService.login(email: email, password: password)
            isLoggedIn = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct LoginView: View {
    @StateObject private var viewModel: LoginViewModel

    init(authService: AuthServiceProtocol) {
        _viewModel = StateObject(wrappedValue: LoginViewModel(authService: authService))
    }

    var body: some View {
        VStack(spacing: 16) {
            TextField("Email", text: $viewModel.email)
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()

            SecureField("Password", text: $viewModel.password)
                .textFieldStyle(.roundedBorder)

            if let error = viewModel.errorMessage {
                Text(error).foregroundStyle(.red).font(.caption)
            }

            Button("Login") {
                Task { await viewModel.login() }
            }
            .disabled(viewModel.isLoading)
            .overlay { if viewModel.isLoading { ProgressView() } }
        }
        .padding()
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Protocols & Stubs
// ─────────────────────────────────────────────────────────────

protocol UserServiceProtocol {
    func fetchUsers() async throws -> [User]
}

protocol AuthServiceProtocol {
    func login(email: String, password: String) async throws
}

class UserService: UserServiceProtocol {
    func fetchUsers() async throws -> [User] { [] }
}

class UserDetailCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    let user: User
    let navigationController: UINavigationController
    init(user: User, navigationController: UINavigationController) {
        self.user = user; self.navigationController = navigationController
    }
    func start() { /* push detail VC */ }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the role of the ViewModel in MVVM?**

A: The ViewModel sits between the Model and the View. It transforms raw model data into a form the View can display directly (formatted strings, booleans for visibility, etc.), handles user-initiated actions by calling model/service layer methods, and manages view-specific state like loading indicators and error messages. The View observes the ViewModel and updates itself when it changes — the ViewModel never imports UIKit or knows about any specific view type. This separation makes ViewModels independently unit-testable: you can test the ViewModel's logic by injecting mock services without instantiating any view.

**Q: What is the Coordinator pattern and what problem does it solve?**

A: A Coordinator is an object that owns navigation logic — creating view controllers, pushing/presenting them, and managing the flow between screens. It solves the "Massive View Controller" problem where VCs accumulate both UI logic and navigation decisions. By extracting navigation into coordinators: (1) VCs become simpler and reusable across different flows. (2) Navigation logic is testable. (3) Deep links and flow variations (e.g., different onboarding for A/B tests) can be handled by swapping or modifying coordinators without touching individual VCs.

### Hard

**Q: How do you avoid retain cycles between a ViewController, its ViewModel, and a Coordinator?**

A: The common cycle: VC holds ViewModel strongly, ViewModel has a closure or delegate back to VC (or Coordinator). Fix: (1) The VC's delegate property pointing to the Coordinator must be `weak var`. (2) Any closure stored in the ViewModel that captures the VC must use `[weak self]`. (3) The Coordinator holds child coordinators in an array and removes them (`childDidFinish`) when a flow ends — preventing accumulation. Use Xcode's Memory Graph Debugger to visualise the object graph and spot unexpected strong paths. The rule: ownership flows downward (Coordinator → VC → ViewModel); any upward reference must be weak.

**Q: How does `@MainActor` on a ViewModel class interact with async service calls?**

A: A `@MainActor` class has all its methods implicitly running on the main thread. When a method calls `await someService.fetchData()` and the service performs work on a background thread, the function suspends and may resume on a different thread — but because the method is `@MainActor`, the Swift runtime hops back to the main thread before continuing execution. This means you can safely mutate `@Published` properties after every `await` without an explicit `DispatchQueue.main.async`. The compiler also enforces that callers from non-`MainActor` contexts must `await` the call, preventing accidental off-thread access.

### Expert

**Q: Compare MVVM+Coordinator for UIKit vs the SwiftUI navigation approach for a large multi-flow app.**

A: **UIKit MVVM+Coordinator**: Explicit coordinator objects give full programmatic control over navigation. Deep links are handled by the root coordinator traversing and rebuilding the coordinator tree. Testing navigation is straightforward — inject mock coordinators. The overhead: boilerplate for every coordinator (protocol, start, childDidFinish), manual memory management, and ensuring lifecycle calls propagate through container VCs. **SwiftUI NavigationStack + Router**: A `NavigationPath` or a custom router `ObservableObject` drives navigation declaratively. Deep links map to path state changes. Less boilerplate, but complex multi-level flows (e.g., popping to a specific screen mid-stack) require careful path state management. For iOS 16+ only apps, a `@Observable` `Router` class that owns `NavigationPath` closely mirrors the Coordinator pattern without the UIKit ceremony. For apps supporting iOS 15 and below, UIKit MVVM+Coordinator remains more mature.

## 6. Common Issues & Solutions

**Issue: ViewModel is deallocated immediately after init.**

Solution: The ViewController is not retaining the ViewModel. The ViewModel must be stored as a `let` or `var` property on the VC — not created inline in `viewDidLoad`. In SwiftUI, use `@StateObject` not `@ObservedObject` when the view owns the ViewModel.

**Issue: Navigation from ViewModel — ViewModel calls `navigationController?.pushViewController`.**

Solution: The ViewModel should not know about navigation. Extract navigation into a delegate method or closure, and let the Coordinator react to it. If the ViewModel needs to trigger navigation, expose an output (`var onUserSelected: ((User) -> Void)?`) and let the Coordinator or VC subscribe to it.

**Issue: Memory accumulation — coordinator array grows unboundedly.**

Solution: Implement `childDidFinish` correctly. Each child coordinator must notify its parent when its flow completes (e.g., user logs out, modal is dismissed) so the parent removes it from `childCoordinators`. Use the Memory Graph Debugger to check that dismissed flows release all their objects.

**Issue: `@Published` changes from background thread cause runtime warnings.**

Solution: Mark the ViewModel class `@MainActor`. If you can't change the class, wrap each `@Published` mutation in `DispatchQueue.main.async` or use `await MainActor.run { }` inside async functions.

## 7. Related Topics

- [UIViewController Lifecycle](uiviewcontroller-lifecycle.md) — VCs that Coordinators create and manage
- [SwiftUI State Management](swiftui-state-management.md) — ObservableObject as SwiftUI ViewModel
- [SwiftUI View Lifecycle](swiftui-view-lifecycle.md) — SwiftUI navigation patterns
- [Actors](../03-concurrency/actors.md) — @MainActor for safe ViewModel updates
- [Retain Cycles](../02-memory-management/retain-cycles.md) — delegate/closure cycles in MVVM
- [Closures & Capture Lists](../02-memory-management/closures-capture-lists.md) — [weak self] in ViewModel bindings
- [Architecture](../06-architecture/index.md) — broader architecture patterns (forward link)
