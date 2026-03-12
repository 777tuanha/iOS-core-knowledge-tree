# VIP — Clean Swift Architecture

## 1. Overview

VIP (View-Interactor-Presenter) is the iOS architecture pattern introduced by Raymond Law as **Clean Swift**. It applies Robert Martin's Clean Architecture to individual UIKit scenes, creating a **unidirectional data flow** cycle: the View sends requests to the Interactor, the Interactor processes them and sends responses to the Presenter, and the Presenter formats them into view models that are displayed by the View. Unlike VIPER, VIP has no central Presenter-owned Router — each scene has its own `Router` object responsible for navigation and data passing. VIP is UIKit-native, fully protocol-driven, and generates every layer from Xcode templates.

## 2. Simple Explanation

Think of a restaurant with a very strict workflow. The customer (View) can only talk to the waiter (Interactor) — they submit an order. The waiter goes to the kitchen, does the cooking (business logic), and passes the finished plate to the plating station (Presenter). The plating station arranges the food nicely on a plate (view model) and sends it back to the customer's table (View). The customer never goes to the kitchen, and the kitchen never comes to the table. The path is always: View → Interactor → Presenter → View. Circular, strict, one direction.

## 3. Deep iOS Knowledge

### VIP vs VIPER

Both apply Clean Architecture, but with key differences:

| Dimension | VIP (Clean Swift) | VIPER |
|-----------|-------------------|-------|
| Data flow | Unidirectional cycle (V→I→P→V) | Bidirectional (Presenter mediates V↔I) |
| Navigation | Router: owned by ViewController | Router: owned by Presenter |
| Who holds what | VC holds Interactor; Interactor holds Presenter; Presenter holds VC (weak) | Presenter holds View (weak) and Interactor |
| Scene ownership | Each VC has its own VIP cycle | Presenter coordinates all layers |
| Code generation | Xcode templates (cleanswift.com) | Custom or manual |
| Coupling | Very low — strict protocol boundaries | Low — also protocol-driven |

### The VIP Cycle

```
┌─────────────────────────────────────────────────────┐
│                      Scene                          │
│                                                     │
│  ViewController ──Request──▶ Interactor             │
│       ▲                          │                  │
│       │                       Response              │
│    ViewModel                     │                  │
│       │                          ▼                  │
│  Presenter ◀──────────── Presenter                  │
│  (formats response → ViewModel → display)           │
└─────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**ViewController (View)**:
- Implements `DisplayLogic` protocol
- Calls `interactor.doSomething(request:)` on user events
- Receives `displaySomething(viewModel:)` calls from Presenter
- No business logic, no data formatting

**Interactor**:
- Implements `BusinessLogic` protocol
- Performs use-case logic: calls workers/services, applies business rules
- Passes `Response` objects to the Presenter
- No UIKit, no formatting, no knowledge of how data will be displayed

**Presenter**:
- Implements `PresentationLogic` protocol
- Receives `Response` from Interactor, formats it into `ViewModel`
- Calls `viewController?.displaySomething(viewModel:)`
- No UIKit layout code, no business logic
- Holds a **weak** reference to the ViewController (to break the cycle)

**Router**:
- Implements `RoutingLogic` and `DataPassing` protocols
- Navigates to other scenes and passes data between them
- Holds a weak reference to the ViewController
- Is the only layer that creates the next scene's `Configurator`

**Models (Request / Response / ViewModel)**:
- Plain structs, one set per use case
- `Request`: data from ViewController to Interactor (e.g., user input)
- `Response`: data from Interactor to Presenter (e.g., raw model data)
- `ViewModel`: data from Presenter to ViewController (e.g., formatted strings)

**Configurator / Scene**:
- Wires all five layers together
- Usually a `static func createScene()` or a `configure(viewController:)` method

### Data Flow Per Use Case

Every user action follows the same path:

```
1. User taps "Load Feed"
2. VC calls interactor.fetchFeed(request: FetchFeed.Request())
3. Interactor fetches data, creates FetchFeed.Response(posts: [...])
4. Interactor calls presenter.presentFeed(response:)
5. Presenter formats: FetchFeed.ViewModel(rows: [Row(title: "...")])
6. Presenter calls viewController?.displayFeed(viewModel:)
7. VC updates table with viewModel.rows
```

All data passed between layers is via **value types** (structs). Layers never share references.

### Protocol Structure (per scene)

```swift
// VC → Interactor
protocol FeedBusinessLogic {
    func fetchFeed(request: FeedModels.FetchFeed.Request)
}

// Interactor → Presenter
protocol FeedPresentationLogic {
    func presentFeed(response: FeedModels.FetchFeed.Response)
    func presentError(response: FeedModels.ShowError.Response)
}

// Presenter → VC
protocol FeedDisplayLogic: AnyObject {
    func displayFeed(viewModel: FeedModels.FetchFeed.ViewModel)
    func displayError(viewModel: FeedModels.ShowError.ViewModel)
}

// Router
protocol FeedRoutingLogic {
    func routeToDetail()
}

protocol FeedDataPassing {
    var dataStore: FeedDataStore? { get }
}
```

### Data Passing Between Scenes

VIP uses a **DataStore** protocol on the Interactor to hold data that needs to be passed to the next scene. The Router reads from the current scene's `DataStore` and writes to the destination scene's `DataStore`:

```swift
protocol FeedDataStore {
    var selectedPost: Post? { get set }
}

class FeedRouter: FeedRoutingLogic, FeedDataPassing {
    weak var viewController: FeedViewController?
    var dataStore: FeedDataStore?

    func routeToDetail() {
        let dest = PostDetailViewController()
        var destDS = dest.router?.dataStore
        passDataToDetail(source: dataStore!, destination: &destDS)
        viewController?.navigationController?.pushViewController(dest, animated: true)
    }

    private func passDataToDetail(
        source: FeedDataStore,
        destination: inout PostDetailDataStore?
    ) {
        destination?.post = source.selectedPost
    }
}
```

This eliminates the need to pass data through segues or init parameters across scenes.

### Testability

VIP's strict protocol boundaries make each layer independently testable:
- Test the **Interactor** by calling business logic methods and asserting `presenter.presentX(response:)` was called with expected values.
- Test the **Presenter** by passing a `Response` and asserting the `viewController.displayX(viewModel:)` was called with correctly formatted values.
- Test the **ViewController** by calling `displayX(viewModel:)` and asserting UI state.

Each test mocks only the adjacent layer's protocol.

## 4. Practical Usage

```swift
import UIKit

// ─────────────────────────────────────────────────────────────
// MARK: – Models (value types, grouped by use case)
// ─────────────────────────────────────────────────────────────

struct Post { let id: Int; let title: String; let body: String }

enum FeedModels {
    enum FetchFeed {
        struct Request {}                                     // VC → Interactor (no params needed)
        struct Response { let posts: [Post]; let error: Error? }  // Interactor → Presenter
        struct ViewModel {
            struct Row { let title: String; let summary: String }
            let rows: [Row]
            let errorMessage: String?
        }
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Protocols
// ─────────────────────────────────────────────────────────────

protocol FeedBusinessLogic {
    func fetchFeed(request: FeedModels.FetchFeed.Request)
}

protocol FeedDataStore {
    var selectedPost: Post? { get set }
}

protocol FeedPresentationLogic {
    func presentFeed(response: FeedModels.FetchFeed.Response)
}

protocol FeedDisplayLogic: AnyObject {
    func displayFeed(viewModel: FeedModels.FetchFeed.ViewModel)
}

protocol FeedRoutingLogic {
    func routeToPostDetail()
}

// ─────────────────────────────────────────────────────────────
// MARK: – Interactor (business logic + data store)
// ─────────────────────────────────────────────────────────────

class FeedInteractor: FeedBusinessLogic, FeedDataStore {
    var presenter: FeedPresentationLogic?
    var worker: FeedWorker = FeedWorker()

    // DataStore — holds data for inter-scene passing
    var selectedPost: Post?

    func fetchFeed(request: FeedModels.FetchFeed.Request) {
        worker.fetchPosts { [weak self] result in
            switch result {
            case .success(let posts):
                self?.presenter?.presentFeed(
                    response: .init(posts: posts, error: nil)
                )
            case .failure(let error):
                self?.presenter?.presentFeed(
                    response: .init(posts: [], error: error)
                )
            }
        }
    }
}

// Worker — handles external service calls (keeps Interactor focused on logic)
class FeedWorker {
    func fetchPosts(completion: @escaping (Result<[Post], Error>) -> Void) {
        // URLSession or service call here
        completion(.success([
            Post(id: 1, title: "Hello VIP", body: "Clean architecture is satisfying.")
        ]))
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Presenter (formats Response → ViewModel)
// ─────────────────────────────────────────────────────────────

class FeedPresenter: FeedPresentationLogic {
    weak var viewController: FeedDisplayLogic?   // weak — breaks the cycle

    func presentFeed(response: FeedModels.FetchFeed.Response) {
        if let error = response.error {
            let vm = FeedModels.FetchFeed.ViewModel(rows: [], errorMessage: error.localizedDescription)
            viewController?.displayFeed(viewModel: vm)
            return
        }
        // Format raw Post into display rows
        let rows = response.posts.map { post in
            FeedModels.FetchFeed.ViewModel.Row(
                title: post.title.capitalized,              // formatting lives here — not in VC
                summary: String(post.body.prefix(80))
            )
        }
        let vm = FeedModels.FetchFeed.ViewModel(rows: rows, errorMessage: nil)
        viewController?.displayFeed(viewModel: vm)
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – ViewController (display logic only)
// ─────────────────────────────────────────────────────────────

class FeedViewController: UIViewController, FeedDisplayLogic {
    var interactor: FeedBusinessLogic?
    var router: (FeedRoutingLogic & FeedDataPassing)?  // optional: only navigation logic

    private var displayedRows: [FeedModels.FetchFeed.ViewModel.Row] = []
    private let tableView = UITableView()

    // MARK: – Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        setupTableView()
        fetchFeed()
    }

    // MARK: – VIP Input (user actions → Interactor)
    private func fetchFeed() {
        interactor?.fetchFeed(request: .init())  // send Request — no data needed here
    }

    // MARK: – VIP Output (Presenter calls → update UI)
    func displayFeed(viewModel: FeedModels.FetchFeed.ViewModel) {
        DispatchQueue.main.async { [weak self] in
            if let error = viewModel.errorMessage {
                self?.showError(message: error)
                return
            }
            self?.displayedRows = viewModel.rows
            self?.tableView.reloadData()
        }
    }

    private func showError(message: String) {
        let alert = UIAlertController(title: "Error", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func setupTableView() {
        tableView.frame = view.bounds
        tableView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "Cell")
        tableView.dataSource = self
        view.addSubview(tableView)
    }
}

extension FeedViewController: UITableViewDataSource {
    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        displayedRows.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "Cell", for: indexPath)
        let row = displayedRows[indexPath.row]
        var config = UIListContentConfiguration.subtitleCell()
        config.text = row.title
        config.secondaryText = row.summary
        cell.contentConfiguration = config
        return cell
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Router
// ─────────────────────────────────────────────────────────────

class FeedRouter: FeedRoutingLogic, FeedDataPassing {
    weak var viewController: FeedViewController?
    var dataStore: FeedDataStore?

    func routeToPostDetail() {
        // Create destination, pass data via DataStore
        // viewController?.navigationController?.push(...)
    }
}

// ─────────────────────────────────────────────────────────────
// MARK: – Scene Configurator (wires all layers together)
// ─────────────────────────────────────────────────────────────

extension FeedViewController {
    func configure() {
        let interactor = FeedInteractor()
        let presenter = FeedPresenter()
        let router = FeedRouter()

        // Wire the cycle
        self.interactor = interactor       // VC → Interactor (strong)
        interactor.presenter = presenter   // Interactor → Presenter (strong)
        presenter.viewController = self    // Presenter → VC (WEAK — breaks cycle)
        self.router = router
        router.viewController = self
        router.dataStore = interactor
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the VIP cycle and how does data flow through it?**

A: VIP stands for View-Interactor-Presenter, representing a strict unidirectional cycle. (1) The **View** (UIViewController) receives a user event and packages it into a `Request` struct, calling a method on the **Interactor**. (2) The **Interactor** contains the business logic — it fetches data, applies rules, and packages the result into a `Response` struct, calling a method on the **Presenter**. (3) The **Presenter** formats the `Response` into a `ViewModel` (display-ready strings, booleans) and calls a `display...` method on the **View**. The cycle is always V→I→P→V. No layer skips a step or communicates backward.

**Q: How does VIP differ from VIPER?**

A: Both use the same Clean Architecture layers, but their data flow and ownership differ. VIPER has the **Presenter** as the central mediator — it receives data from the Interactor and tells the View what to show. VIP enforces a **unidirectional cycle** — the Presenter does not call the Interactor; it only calls the View. Navigation in VIPER is the Presenter's responsibility; in VIP the **Router** is owned by the ViewController and handles navigation and inter-scene data passing via the `DataStore` protocol. VIP also introduces a **Worker** class to keep the Interactor focused on business logic rather than external API calls.

### Hard

**Q: How does VIP handle data passing between two scenes, and why is the DataStore approach safer than passing data via init parameters?**

A: In VIP, each Interactor implements a `DataStore` protocol exposing the data it holds. When navigating, the Router reads from the current scene's `DataStore` and writes into the destination scene's `DataStore` via a dedicated `passData(to:)` method. This is safer than passing data through `init` parameters or segues because: (1) the destination ViewController can be created independently of the data — the `configure()` step and the data-passing step are separate, keeping the composition cleaner; (2) it works naturally with storyboard segues (`prepare(for:)` calls the Router which moves data between stores); (3) the data contract is explicit in the `DataStore` protocol — what is passed is documented and type-checked at the boundary.

**Q: Why does the Presenter hold a `weak` reference to the ViewController, and what cycle does this break?**

A: The reference ownership in VIP is: ViewController → Interactor (strong), Interactor → Presenter (strong), Presenter → ViewController. Without `weak`, this creates a retain cycle: VC → Interactor → Presenter → VC. None of the three objects would deallocate when the VC is popped from the navigation stack. Making `Presenter.viewController` a `weak var` breaks the cycle — the reference from Presenter to VC does not contribute to the retain count, so when the navigation stack releases the VC, it deallocates, which releases the Interactor and Presenter in turn.

### Expert

**Q: Compare VIP and MVVM for a feature with complex user input validation and multi-step async workflows. What are the concrete tradeoffs?**

A: **VIP**: Each use case (validate form, submit step 1, submit step 2) has its own `Request`/`Response`/`ViewModel` triplet. The Interactor owns the workflow state and calls workers for each step. The Presenter formats intermediate states (loading, partial success, error) into ViewModels. The VC is completely passive — it never decides what to show. Advantage: scaling to 10 use cases is mechanical — add another triplet and another pair of methods. Disadvantage: high boilerplate (5 objects per scene, 3 structs per use case), and the strict cycle can feel over-engineered for simple screens. **MVVM**: The ViewModel holds all state as `@Published` properties, async logic as `async` functions, and validation as computed properties. Less boilerplate, reactive binding via Combine or SwiftUI. Disadvantage: as use cases grow, the ViewModel risks becoming a Massive ViewModel — the same concentration problem as Massive ViewController but one layer removed. For complex, multi-step flows with many use cases, VIP's mechanical structure scales better; for standard CRUD screens, MVVM is more concise.

## 6. Common Issues & Solutions

**Issue: Retain cycle — ViewController not deallocating after pop.**

Solution: Verify `presenter.viewController` is declared `weak var`. In Swift, a plain `var viewController: FeedDisplayLogic?` without `weak` will retain the VC. Use `weak var viewController: FeedDisplayLogic?` — note that `weak` requires the protocol to be class-constrained (`protocol FeedDisplayLogic: AnyObject`).

**Issue: UI not updating — `displayFeed` is not being called.**

Solution: Check that `configure()` was called (all layers are wired). Verify that `presenter.viewController` was set and is not nil. Add a breakpoint in `presentFeed` to confirm the Presenter's method is being reached.

**Issue: Massive Interactor — Interactor grows to hundreds of lines.**

Solution: Introduce **Workers** — separate objects that the Interactor delegates external calls to. `FeedWorker` handles network fetching; `FeedCacheWorker` handles persistence. The Interactor calls workers and processes their results — keeping it focused on business rules rather than I/O details.

**Issue: Boilerplate feels excessive for simple screens.**

Solution: VIP is not appropriate for every screen. Use MVC or MVVM for simple display-only screens. Reserve VIP for screens with significant business logic, multiple use cases, or frequent change by a team. Use Clean Swift Xcode templates to generate the boilerplate automatically.

## 7. Related Topics

- [MVP & VIPER](mvp-viper.md) — VIPER shares the same Clean Architecture roots; compare both
- [MVVM](mvvm.md) — the simpler reactive alternative
- [MVC](mvc.md) — the problem VIP solves (Massive ViewController)
- [Dependency Injection](dependency-injection.md) — each VIP layer is injected via protocol
- [SOLID Principles](solid-principles.md) — VIP is a direct application of SRP, OCP, and DIP
