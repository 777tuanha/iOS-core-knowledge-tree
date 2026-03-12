# MVP & VIPER

## 1. Overview

**MVP** (Model-View-Presenter) and **VIPER** (View-Interactor-Presenter-Entity-Router) are architectural patterns that enforce stricter separation of concerns than MVC or MVVM, at the cost of more boilerplate. MVP is a thin step beyond MVC: it extracts presentation logic into a `Presenter` that talks to a passive, protocol-based `View`, making it testable without UIKit. **VIPER** goes further, applying **Clean Architecture** principles to separate every distinct responsibility — navigation, business logic, data fetching, entities — into its own layer with explicit protocols between them. VIPER is most valuable in large teams where different engineers own different layers.

## 2. Simple Explanation

In MVC, a VC is a do-everything waiter. MVP says: make the VC a dumb screen (just display what you're told) and hire a Presenter who does the thinking and tells the screen what to show. The View holds a reference to the Presenter; the Presenter holds a weak reference back to the View (via a protocol).

VIPER takes this further by hiring an entire team for one feature: the **View** displays, the **Presenter** formats, the **Interactor** does business logic, the **Entity** holds the data model, and the **Router** handles navigation. Each team member talks to the next through a strict contract.

## 3. Deep iOS Knowledge

### MVP Architecture

```
View  ←──────── Presenter ────────▶ Model/Service
(UIViewController)  ▲         (protocol-based dependency)
                     │
                  protocol
                  (ViewProtocol)
```

**View** (UIViewController):
- Implements a `ViewProtocol` (e.g., `ArticleListView`)
- Calls `presenter.viewDidLoad()`, `presenter.didSelectItem(at:)` for user events
- Has no logic — just updates UI from presenter calls

**Presenter**:
- Holds a `weak var view: ArticleListView?`
- Calls `view?.showArticles(...)`, `view?.showError(...)`
- Has no UIKit imports — testable with a mock View
- Calls service/interactor for data

**Model**:
- Service objects, entities, and data access

### MVP vs MVVM

| | MVP | MVVM |
|--|-----|------|
| View updates | Presenter calls View methods explicitly | View observes ViewModel state |
| View protocol | Required | Not required |
| Passive view | Yes — explicit push | No — View pulls via binding |
| Framework dependency | None (pure Swift) | Combine / SwiftUI |
| Verbosity | Higher (explicit calls) | Lower (reactive) |

MVP is preferable in UIKit codebases without Combine where you still want full testability — the View protocol can be mocked trivially.

### VIPER Architecture

Each letter is a distinct layer:

| Layer | Responsibility |
|-------|---------------|
| **V**iew | UIViewController subclass; displays data; forwards events to Presenter |
| **I**nteractor | Business logic; data fetching; pure computation; knows nothing about UI |
| **P**resenter | Mediates between View and Interactor; formats data for display |
| **E**ntity | Plain data models (structs); owned by the Interactor |
| **R**outer | Navigation: creates scenes, pushes/presents VCs |

### VIPER Communication Flow

```
User Action
    │
    ▼
View ──────▶ Presenter ──────▶ Interactor
 ▲                │                │
 │           (formats)        (fetches data,
 │                │             applies rules)
 │                ▼                │
 └──────── Presenter          Entities
           (updates view ◀────────┘
            via protocol)

Navigation:
Presenter ──────▶ Router ──────▶ UINavigationController
```

### VIPER Protocols

VIPER typically defines five protocols per module:

```swift
protocol ArticleListViewProtocol: AnyObject {
    func showArticles(_ articles: [ArticleViewModel])
    func showError(_ message: String)
}

protocol ArticleListPresenterProtocol: AnyObject {
    func viewDidLoad()
    func didSelectArticle(at index: Int)
}

protocol ArticleListInteractorProtocol: AnyObject {
    func fetchArticles()
}

protocol ArticleListInteractorOutputProtocol: AnyObject {
    func didFetchArticles(_ articles: [Article])
    func didFailWithError(_ error: Error)
}

protocol ArticleListRouterProtocol: AnyObject {
    func navigateToDetail(article: Article)
    static func createModule() -> UIViewController
}
```

### Clean Architecture Mapping

VIPER is an iOS implementation of Robert Martin's Clean Architecture:

| Clean Architecture | VIPER |
|-------------------|-------|
| Presentation layer | View + Presenter |
| Use Case layer | Interactor |
| Domain / Entity layer | Entity |
| Infrastructure layer | Router + external services |

The **Dependency Rule**: inner layers (Entity, Interactor) must not depend on outer layers (View, Router). Dependencies point inward.

### VIPER Module Assembler

The Router or a dedicated Assembler creates all five objects and wires them together:

```swift
static func createModule() -> UIViewController {
    let view = ArticleListViewController()
    let interactor = ArticleListInteractor()
    let presenter = ArticleListPresenter()
    let router = ArticleListRouter()

    view.presenter = presenter
    presenter.view = view
    presenter.interactor = interactor
    presenter.router = router
    interactor.output = presenter
    router.viewController = view

    return view
}
```

### When to Use Each

| Pattern | When |
|---------|------|
| MVC | Simple screens, prototypes |
| MVVM | Standard production apps, SwiftUI |
| MVP | UIKit-heavy teams that want testability without Combine |
| VIPER | Large teams (4+ devs per feature), complex business logic, Clean Architecture mandate |

## 4. Practical Usage

```swift
import UIKit

// ─────────────────────────────────────────────────────────────
// MARK: – MVP Example
// ─────────────────────────────────────────────────────────────

struct Article { let id: Int; let title: String }

// View protocol — what the Presenter calls
protocol ArticleListViewProtocol: AnyObject {
    func displayArticles(_ articles: [Article])
    func displayError(_ message: String)
    func setLoadingVisible(_ visible: Bool)
}

// Presenter — no UIKit, fully testable
class ArticleListPresenter {
    weak var view: ArticleListViewProtocol?
    private let service: ArticleServiceProtocol

    init(service: ArticleServiceProtocol) {
        self.service = service
    }

    // Called by View in viewDidLoad
    func viewDidLoad() {
        view?.setLoadingVisible(true)
        service.fetchArticles { [weak self] result in
            DispatchQueue.main.async {
                self?.view?.setLoadingVisible(false)
                switch result {
                case .success(let articles):
                    self?.view?.displayArticles(articles)
                case .failure(let error):
                    self?.view?.displayError(error.localizedDescription)
                }
            }
        }
    }

    func didSelectArticle(at index: Int, articles: [Article]) {
        // Navigation — would call router in VIPER
        print("Selected: \(articles[index].title)")
    }
}

// View — UIViewController is a passive display layer
class ArticleListViewController: UIViewController, ArticleListViewProtocol {
    var presenter: ArticleListPresenter!
    private var articles: [Article] = []
    private let tableView = UITableView()
    private let activityIndicator = UIActivityIndicatorView(style: .medium)

    override func viewDidLoad() {
        super.viewDidLoad()
        presenter.viewDidLoad()   // delegate to presenter; no logic here
    }

    // ArticleListViewProtocol
    func displayArticles(_ articles: [Article]) {
        self.articles = articles
        tableView.reloadData()
    }

    func displayError(_ message: String) {
        let alert = UIAlertController(title: "Error", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    func setLoadingVisible(_ visible: Bool) {
        visible ? activityIndicator.startAnimating() : activityIndicator.stopAnimating()
    }
}

protocol ArticleServiceProtocol {
    func fetchArticles(completion: @escaping (Result<[Article], Error>) -> Void)
}

// ─────────────────────────────────────────────────────────────
// MARK: – VIPER Example (simplified)
// ─────────────────────────────────────────────────────────────

// Entity
struct ArticleEntity { let id: Int; let title: String; let body: String }

// View protocol
protocol ArticleViewProtocol: AnyObject {
    func showArticles(_ viewModels: [ArticleDisplayModel])
    func showError(_ message: String)
}

// Display model (entity formatted for display by Presenter)
struct ArticleDisplayModel { let title: String; let shortSummary: String }

// Interactor output protocol
protocol ArticleInteractorOutputProtocol: AnyObject {
    func didFetch(_ articles: [ArticleEntity])
    func didFail(error: Error)
}

// Interactor — pure business logic, no UIKit
class ArticleInteractor {
    weak var output: ArticleInteractorOutputProtocol?
    private let service: ArticleServiceProtocol

    init(service: ArticleServiceProtocol) { self.service = service }

    func fetchArticles() {
        service.fetchArticles { [weak self] result in
            switch result {
            case .success(let articles):
                // Map to Entity
                let entities = articles.map { ArticleEntity(id: $0.id, title: $0.title, body: "") }
                self?.output?.didFetch(entities)
            case .failure(let error):
                self?.output?.didFail(error: error)
            }
        }
    }
}

// Presenter — formats Entity for display; mediates View ↔ Interactor
class ArticlePresenter: ArticleInteractorOutputProtocol {
    weak var view: ArticleViewProtocol?
    var interactor: ArticleInteractor?
    var router: ArticleRouter?

    func viewDidLoad() {
        interactor?.fetchArticles()
    }

    // Interactor output
    func didFetch(_ articles: [ArticleEntity]) {
        // Format for display
        let displayModels = articles.map {
            ArticleDisplayModel(
                title: $0.title,
                shortSummary: String($0.body.prefix(80))
            )
        }
        DispatchQueue.main.async { [weak self] in
            self?.view?.showArticles(displayModels)
        }
    }

    func didFail(error: Error) {
        DispatchQueue.main.async { [weak self] in
            self?.view?.showError(error.localizedDescription)
        }
    }
}

// Router — navigation; creates the module
class ArticleRouter {
    weak var viewController: UIViewController?

    static func createModule(service: ArticleServiceProtocol) -> UIViewController {
        let view = ArticleViewController()
        let presenter = ArticlePresenter()
        let interactor = ArticleInteractor(service: service)
        let router = ArticleRouter()

        view.presenter = presenter   // wire all together
        presenter.view = view
        presenter.interactor = interactor
        presenter.router = router
        interactor.output = presenter
        router.viewController = view

        return view
    }

    func navigateToDetail(article: ArticleEntity, from vc: UIViewController) {
        // push detail VC
    }
}

// View — UIViewController, passive display
class ArticleViewController: UIViewController, ArticleViewProtocol {
    var presenter: ArticlePresenter?

    override func viewDidLoad() {
        super.viewDidLoad()
        presenter?.viewDidLoad()
    }

    func showArticles(_ viewModels: [ArticleDisplayModel]) { /* update table */ }
    func showError(_ message: String) { /* show alert */ }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between MVP and MVC?**

A: The key difference is where UI logic lives and how it is tested. In MVC, the Controller (`UIViewController`) contains both routing and presentation logic and is tightly coupled to the View — making it hard to test. In MVP, the `UIViewController` is a **passive View** that implements a lightweight protocol — it has no logic. All presentation logic moves to a `Presenter` that holds a `weak` reference to the View via the protocol. The Presenter has no UIKit imports and can be unit-tested by injecting a mock View. MVP makes the View almost completely passive, whereas in MVC the ViewController is an active participant in logic decisions.

**Q: What does each letter in VIPER stand for and what is each layer's responsibility?**

A: **V**iew: UIViewController — displays data, forwards user events to Presenter; no business logic. **I**nteactor: business logic and data fetching — calls services, applies rules, returns entities. **P**resenter: mediates View and Interactor — formats entities into display models for the View; instructs the Router for navigation. **E**ntity: plain data model structs — owned by the Interactor; no business logic. **R**outer: navigation — creates the module, pushes/presents other VCs, receives navigation commands from the Presenter.

### Hard

**Q: What is the Dependency Rule in Clean Architecture and how does VIPER enforce it?**

A: The Dependency Rule states that source-code dependencies can only point **inward** — toward higher-level, more abstract layers. Outer layers (View, Router) depend on inner layer protocols but inner layers (Interactor, Entity) never import or reference outer layers. In VIPER: the Interactor defines its output via a protocol (`InteractorOutputProtocol`). The Presenter implements that protocol. The Interactor never imports UIKit or knows about the Presenter's concrete type — it only knows about the output protocol. This allows the business logic (Interactor) to be tested, swapped, or reused independently of any UI technology.

**Q: How does the VIPER module assembler work and why is it important?**

A: The assembler (typically a `static func createModule()` on the Router) is responsible for creating all five VIPER objects and wiring their inter-references. Without the assembler, each object would need to know how to find the others, creating coupling. The assembler is the only place that knows about all five concrete types simultaneously. It constructs the dependency graph and hands the caller only a `UIViewController`, hiding all internal VIPER plumbing. This pattern also serves as the single place to swap implementations (e.g., inject a mock Interactor for testing).

### Expert

**Q: Compare VIPER and TCA for a feature with complex async state. What are the concrete tradeoffs?**

A: **VIPER**: Five separate objects communicate via protocols. Async work lives in the Interactor and results flow back via the output protocol. State is mutable — the Presenter updates View state imperatively. Testing requires mock protocols for each boundary. Scaling to a team of engineers is natural because each layer can be owned independently. Weakness: no guaranteed unidirectional flow; state mutation is spread across layers; hard to reason about combined state. **TCA**: All state is in a single `State` struct; all mutations happen in a pure `Reducer` function. Side effects (network, persistence) are expressed as `Effect` values and executed by the `Store`. This makes every state transition an explicit, testable, logged event — ideal for debugging and reproducibility. Weakness: significant learning curve, all action/state types are centralised (risk of large reducers in complex features), and requires the Point-Free TCA dependency. Choose VIPER for large UIKit teams with separate ownership per layer; choose TCA for teams that need strong state debuggability and are comfortable with functional patterns.

## 6. Common Issues & Solutions

**Issue: VIPER module is hard to set up — too much boilerplate for a simple screen.**

Solution: VIPER is inappropriate for simple screens. Use MVC or MVVM there. Reserve VIPER for complex screens with significant business logic, multiple async operations, and multiple developers. Consider a code generator (templates, Sourcery) to reduce boilerplate.

**Issue: Presenter holds a strong reference to the ViewController, causing a retain cycle.**

Solution: The Presenter must always hold the View via `weak var view: ArticleListViewProtocol?`. The View holds the Presenter strongly. The direction is: View → Presenter (strong), Presenter → View (weak).

**Issue: Unit test for Presenter fails because Interactor fetches real data.**

Solution: The Interactor should conform to a protocol. In tests, inject a `MockInteractor` that immediately calls the output with stub data. The Presenter should never create its dependencies — use constructor injection.

## 7. Related Topics

- [MVC](mvc.md) — the simpler starting point
- [MVVM](mvvm.md) — the standard modern alternative to MVP
- [The Composable Architecture](tca.md) — a modern alternative to VIPER for complex state
- [Dependency Injection](dependency-injection.md) — protocol injection is the backbone of MVP/VIPER testability
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — Coordinator pattern as a lightweight Router
