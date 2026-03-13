# iOS-Specific Patterns

## 1. Overview

Beyond the GoF patterns, iOS development has three patterns that are idiomatic to Cocoa and Swift: **Delegate** (UIKit's primary mechanism for one-to-one typed callbacks from a child object to its owner), **Coordinator** (a pattern for extracting navigation logic from `UIViewController` into a separate object responsible for app flow), and **Dependency Injection** (providing an object's dependencies from the outside rather than having the object create them, which enables testing and flexibility). These patterns appear throughout Apple's own frameworks — `UITableViewDelegate`, `URLSessionDelegate`, and `WKNavigationDelegate` are all delegate patterns; `UINavigationController` acts as a coordinator for its stack; SwiftUI's environment is a form of dependency injection. Understanding when and how to apply each is essential for writing testable, maintainable iOS apps.

## 2. Simple Explanation

**Delegate**: a manager who delegates tasks to an assistant. The manager (the owning object) tells the assistant (the delegate), "when something happens, call this specific method on me." Only one assistant per manager. **Coordinator**: a travel agent who manages your entire itinerary — they book hotels, arrange transport, and manage the sequence of stops. You (the view controller) don't know the itinerary; you just tell the agent "I want to go to Paris next" and the agent handles all the logistics. **Dependency Injection**: instead of a chef buying their own ingredients (creating dependencies), the restaurant's supplier delivers the ingredients to the kitchen door. The chef doesn't care which supplier — they just use whatever arrives. This lets you swap ingredients (mock a database in tests) without changing the chef.

## 3. Deep iOS Knowledge

### Delegate Pattern

The Delegate pattern is a one-to-one protocol-based callback mechanism. The delegating object (e.g., `UITableView`) defines a protocol (`UITableViewDelegate`) and holds a `weak` reference to the delegate conformer. When events occur, the delegating object calls methods on its delegate.

Key rules:
- The delegate property must be `weak` to avoid a retain cycle (the tableView is usually owned by a VC which is also the delegate).
- Delegate methods are optional by convention — `@objc protocol` with `optional` keyword, or a protocol with default implementations in an extension.
- The delegate receives typed, specific callbacks — unlike `NotificationCenter`'s untyped `userInfo`.

In Swift, prefer protocol-based delegates over closures for multi-method callbacks; use closures for single-method callbacks.

### Coordinator Pattern

The Coordinator (or Flow Controller) pattern, popularised by Soroush Khanlou, extracts navigation logic from view controllers. Problems it solves:
- View controllers in Massive VC anti-pattern often contain navigation logic (`present(vc, animated:)`) — they know too much about the app's flow.
- Deep linking requires patching the nav stack from the outside — hard when VCs control their own navigation.
- Testing navigation requires instantiating and presenting real VCs.

Structure:
```
AppCoordinator
├── AuthCoordinator (login, registration, forgot password)
└── MainCoordinator
    ├── FeedCoordinator
    ├── ProfileCoordinator
    └── SettingsCoordinator
```

Each coordinator owns a `UINavigationController` (or presents on one), creates view controllers, injects dependencies, and handles the delegate callbacks that trigger navigation.

### Dependency Injection

DI is the technique of providing an object's dependencies from outside rather than having the object create them (`let service = Service()` inside a class is a creation — `init(service: Service)` is injection). Three forms:
- **Constructor injection** (preferred): dependencies are parameters of `init`. Type cannot be created without its dependencies — compile-time safety.
- **Property injection**: `var dependency: Dependency?` set after creation. Allows optional dependencies; weaker guarantee.
- **Method injection**: dependency passed as a parameter to a specific method. Use for dependencies needed only for one operation.

DI enables:
- **Testability**: inject `MockService` instead of `RealService` in tests.
- **Flexibility**: swap implementations (staging vs production API, SQLite vs Core Data) by changing the injected concrete type.
- **Explicitness**: all dependencies are visible in the type's interface (no hidden `Logger.shared` calls).

## 4. Practical Usage

```swift
import UIKit

// ── Delegate: Custom view delegate ────────────────────────────
// The view defines the protocol; the owner (VC) conforms to it

protocol RatingViewDelegate: AnyObject {
    func ratingView(_ ratingView: RatingView, didSelectRating rating: Int)
    func ratingViewDidRequestHelp(_ ratingView: RatingView)
}

final class RatingView: UIView {
    weak var delegate: RatingViewDelegate?   // weak — avoids retain cycle

    private func starTapped(at index: Int) {
        delegate?.ratingView(self, didSelectRating: index + 1)
    }

    private func helpButtonTapped() {
        delegate?.ratingViewDidRequestHelp(self)
    }
}

// VC conforms to the delegate
final class ReviewViewController: UIViewController, RatingViewDelegate {
    private let ratingView = RatingView()

    override func viewDidLoad() {
        super.viewDidLoad()
        ratingView.delegate = self   // self owns ratingView → ratingView.delegate is weak
    }

    func ratingView(_ ratingView: RatingView, didSelectRating rating: Int) {
        print("User selected \(rating) stars")
    }

    func ratingViewDidRequestHelp(_ ratingView: RatingView) {
        showHelp()
    }

    private func showHelp() {}
}

// ── Coordinator: App navigation ───────────────────────────────
protocol Coordinator: AnyObject {
    var childCoordinators: [Coordinator] { get set }
    func start()
}

// MARK: - App Coordinator
final class AppCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    private let window: UIWindow
    private let dependencies: AppDependencies

    init(window: UIWindow, dependencies: AppDependencies) {
        self.window = window
        self.dependencies = dependencies
    }

    func start() {
        if dependencies.authService.isLoggedIn {
            showMain()
        } else {
            showAuth()
        }
    }

    private func showAuth() {
        let nav = UINavigationController()
        let coordinator = AuthCoordinator(
            navigationController: nav,
            dependencies: dependencies
        )
        coordinator.onAuthComplete = { [weak self] in
            self?.childCoordinators.removeAll { $0 === coordinator }
            self?.showMain()
        }
        childCoordinators.append(coordinator)
        coordinator.start()
        window.rootViewController = nav
    }

    private func showMain() {
        let tabBarController = UITabBarController()
        let feedNav = UINavigationController()
        let profileNav = UINavigationController()

        let feedCoord = FeedCoordinator(navigationController: feedNav, dependencies: dependencies)
        let profileCoord = ProfileCoordinator(navigationController: profileNav, dependencies: dependencies)
        childCoordinators = [feedCoord, profileCoord]

        feedCoord.start()
        profileCoord.start()

        tabBarController.viewControllers = [feedNav, profileNav]
        window.rootViewController = tabBarController
    }
}

// MARK: - Auth Coordinator
final class AuthCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    var onAuthComplete: (() -> Void)?

    private let navigationController: UINavigationController
    private let dependencies: AppDependencies

    init(navigationController: UINavigationController, dependencies: AppDependencies) {
        self.navigationController = navigationController
        self.dependencies = dependencies
    }

    func start() {
        let vm = LoginViewModel(authService: dependencies.authService)
        vm.onLoginSuccess = { [weak self] in self?.onAuthComplete?() }
        vm.onForgotPassword = { [weak self] in self?.showForgotPassword() }
        let vc = LoginViewController(viewModel: vm)
        navigationController.setViewControllers([vc], animated: false)
    }

    private func showForgotPassword() {
        let vc = ForgotPasswordViewController()
        navigationController.pushViewController(vc, animated: true)
    }
}

// ── Dependency Injection: Constructor injection ───────────────
protocol AuthService {
    var isLoggedIn: Bool { get }
    func login(email: String, password: String) async throws -> User
    func logout()
}

protocol PostRepository {
    func fetchPosts() async throws -> [Post]
}

// AppDependencies — the dependency container
struct AppDependencies {
    let authService: AuthService
    let postRepository: PostRepository
    let analytics: AnalyticsProtocol
}

// ViewModel with constructor injection — all dependencies explicit
final class FeedViewModel: ObservableObject {
    @Published private(set) var posts: [Post] = []
    @Published private(set) var isLoading = false

    private let repository: PostRepository   // injected — not created here
    private let analytics: AnalyticsProtocol

    init(repository: PostRepository, analytics: AnalyticsProtocol) {
        self.repository = repository
        self.analytics = analytics
    }

    @MainActor
    func loadPosts() async {
        isLoading = true
        defer { isLoading = false }
        do {
            posts = try await repository.fetchPosts()
            analytics.log(event: "feed_loaded", parameters: ["count": posts.count])
        } catch {
            // handle error
        }
    }
}

// In production:
// let vm = FeedViewModel(repository: RemotePostRepository(), analytics: FirebaseAnalytics())

// In tests:
// let vm = FeedViewModel(repository: MockPostRepository(), analytics: MockAnalytics())

// Placeholder types for compilation
struct User {}
struct Post {}
protocol AnalyticsProtocol { func log(event: String, parameters: [String: Any]) }
final class FeedCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    private let navigationController: UINavigationController
    private let dependencies: AppDependencies
    init(navigationController: UINavigationController, dependencies: AppDependencies) {
        self.navigationController = navigationController; self.dependencies = dependencies
    }
    func start() {}
}
final class ProfileCoordinator: Coordinator {
    var childCoordinators: [Coordinator] = []
    private let navigationController: UINavigationController
    private let dependencies: AppDependencies
    init(navigationController: UINavigationController, dependencies: AppDependencies) {
        self.navigationController = navigationController; self.dependencies = dependencies
    }
    func start() {}
}
final class LoginViewModel {
    var onLoginSuccess: (() -> Void)?
    var onForgotPassword: (() -> Void)?
    init(authService: AuthService) {}
}
final class LoginViewController: UIViewController { init(viewModel: LoginViewModel) { super.init(nibName: nil, bundle: nil) } required init?(coder: NSCoder) { fatalError() } }
final class ForgotPasswordViewController: UIViewController {}
final class ProfileViewController: UIViewController { init(userID: String) { super.init(nibName: nil, bundle: nil) } required init?(coder: NSCoder) { fatalError() } }
```

## 5. Interview Questions & Answers

### Basic

**Q: Why must the delegate property in UIKit be `weak`?**

A: The delegating object (e.g., `UITableView`) is owned by the view controller that is also the delegate. If `tableView.delegate` were `strong`, the retain cycle would be: `ViewController → tableView (strong) → delegate → ViewController (strong)`. Neither object would ever be deallocated. Making the delegate `weak` breaks the cycle — the tableView holds a non-owning reference to the view controller. When the view controller is released, the tableView's delegate automatically becomes `nil`. The same applies to custom delegates: the child object should never strongly retain its parent, or objects that strongly retain it. The rule: if A owns B and B has a delegate back to A, the delegate must be `weak`.

**Q: What problem does the Coordinator pattern solve?**

A: The Coordinator pattern solves two problems in UIKit: (1) **Massive View Controller**: view controllers in unstructured apps often contain navigation logic (`present`, `push`, deep link handling). This knowledge of the app's flow doesn't belong in the VC — it should be concerned only with displaying data and handling input for its screen. Coordinators extract this responsibility. (2) **Testability of navigation**: with coordinators, navigating from screen A to screen B is handled by a coordinator method (`coordinator.showDetail(for: post)`) — this can be tested by verifying the coordinator created and pushed the right VC. Without coordinators, testing navigation requires full UIKit integration tests. A secondary benefit: deep linking becomes straightforward — the `AppCoordinator` interprets the deep link and tells the appropriate child coordinator to navigate to the right state.

### Hard

**Q: How do you handle a coordinator that needs to pass data back from a child coordinator to a parent?**

A: Three patterns: (1) **Completion callbacks**: the parent coordinator sets a closure on the child coordinator before starting it: `childCoordinator.onComplete = { [weak self] result in self?.handleResult(result) }`. The child calls the closure when its flow finishes. This is the simplest and most explicit. (2) **Delegate protocol**: define a `AuthCoordinatorDelegate` protocol with methods like `authCoordinatorDidLogin(_ coordinator: AuthCoordinator, user: User)`. The parent coordinator conforms and is set as the delegate. More formal and supports multiple callback methods. (3) **Combine / async**: child coordinator exposes a `Deferred<Future<Result, Error>>` or an `AsyncStream` — the parent `await`s the child's result. This integrates naturally with Swift concurrency. The completion callback approach is the most common — it's lightweight and the callback is visible at the point where `childCoordinator.start()` is called, making the flow easy to read. Store child coordinators in `childCoordinators: [Coordinator]` and remove them when their flow completes to avoid memory leaks.

**Q: What is the difference between constructor injection, property injection, and method injection, and when should you use each?**

A: **Constructor injection** (`init(service:)`) is the strongest form: the type cannot be created without its dependencies — compile-time enforcement. Dependencies are clearly visible in the initializer signature. Use it for essential, long-lived dependencies that the type needs for its entire lifetime (repository, analytics, auth service). **Property injection** (`var service: Service?`) is weaker: the dependency is set after creation and is optional — callers could forget to set it, leaving the type with a `nil` dependency that crashes at runtime. Use only when the dependency is optional or when the type is created by a framework (e.g., a `UIViewController` from a Storyboard, where you cannot customise `init`). **Method injection** (`func load(using service: Service)`) provides the dependency only to a single method — appropriate for dependencies needed for one operation, not the entire type lifecycle. Use it for utility functions that accept a strategy or helper as a parameter.

### Expert

**Q: Design a Coordinator architecture for a large app with deep linking, tab bar navigation, and modal flows.**

A: Five-component architecture: (1) **Route enum as the canonical navigation target**: `indirect enum Route { case feed; case postDetail(id: String); case profile(userID: String); case compose; case settings }`. Deep links and push notifications parse into `Route` cases. (2) **Hierarchical coordinators**: `AppCoordinator` owns a `TabBarCoordinator` (after login) which owns one coordinator per tab (`FeedCoordinator`, `ProfileCoordinator`, `SearchCoordinator`). Modal flows (compose, settings) are presented by the `TabBarCoordinator`. Each coordinator manages its own `UINavigationController`. (3) **Deep link handling**: `AppCoordinator.handle(route: Route)` dispatches to the appropriate child coordinator. `FeedCoordinator.showPostDetail(id:)` pushes the detail VC onto the feed nav stack and also pops to root first if needed. `TabBarCoordinator` selects the correct tab before dispatching. (4) **Modal coordinator lifecycle**: when `TabBarCoordinator` starts a modal `ComposeCoordinator`, it stores it in `childCoordinators`. The compose coordinator calls `onComplete` (or `onDismiss`) when the user finishes — the tab coordinator calls `coordinator.dismiss(from: nav)` and removes the coordinator from `childCoordinators`. (5) **SwiftUI integration**: for SwiftUI screens, use a `NavigationPath`-based coordinator where the coordinator drives the `path` binding. UIKit screens use the push/pop/present API. The two worlds connect at the boundary VC that wraps the SwiftUI flow in `UIHostingController`.

## 6. Common Issues & Solutions

**Issue: Coordinator's child coordinators are deallocated immediately after `start()` because nothing holds a strong reference.**

Solution: Store child coordinators in `var childCoordinators: [Coordinator]` on the parent coordinator. Remove a child coordinator from this array in its completion callback: `childCoordinator.onComplete = { [weak self, weak childCoordinator] in self?.childCoordinators.removeAll { $0 === childCoordinator } }`. If the child coordinator is deallocated while a flow is in progress, all its state and callbacks are lost — this is the most common coordinator bug.

**Issue: View controllers created by coordinators have no way to communicate back without knowing about the coordinator.**

Solution: View controllers should not know about coordinators at all. Instead: (1) View controllers expose closures (`var onSelectPost: ((Post) -> Void)?`) or delegate protocols. (2) The coordinator sets these closures when creating the VC and handles them by triggering navigation. This keeps the VC focused on its screen and the coordinator focused on flow.

## 7. Related Topics

- [Creational Patterns](creational-patterns.md) — Factory Method for creating view controllers in coordinators
- [Behavioral Patterns](behavioral-patterns.md) — Observer as the basis for delegate-like callbacks
- [Dependency Injection](../06-architecture/dependency-injection.md) — in-depth DI container patterns
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — coordinator applied with MVVM
- [Testing — Testable Architecture](../11-testing/testable-architecture.md) — mocking injected dependencies
