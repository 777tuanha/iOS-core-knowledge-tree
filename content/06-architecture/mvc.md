# MVC — Model-View-Controller

## 1. Overview

MVC is Apple's built-in architectural pattern for iOS, baked into UIKit since the beginning. It divides app code into three layers: the **Model** holds data and business logic, the **View** displays data and receives input, and the **Controller** mediates between them. In theory, MVC cleanly separates concerns. In practice, UIKit's tight coupling between `UIViewController` and its view causes the Controller to absorb responsibilities that belong elsewhere, leading to **Massive View Controller** — one of the most common iOS anti-patterns.

## 2. Simple Explanation

Imagine a restaurant. The **Model** is the kitchen: it prepares food, stores recipes, and manages inventory — pure logic, no customer contact. The **View** is the dining room: it displays the food and receives orders. The **Controller** is the waiter: they take the customer's order to the kitchen, and bring the food back to the table. The problem with UIKit's MVC is that the waiter (ViewController) ends up cooking half the food, washing dishes, managing inventory, and taking reservations — they become overwhelmed because UIKit physically couples the Controller to the View.

## 3. Deep iOS Knowledge

### Apple's UIKit MVC

UIKit's MVC is often called **"Massive View Controller" MVC** because:
- `UIViewController` is both the controller and the view's owner (`self.view`)
- The VC manages the view hierarchy, responds to lifecycle events, handles user actions, performs networking, parses data, and navigates
- There is no natural boundary preventing logic from accumulating in the VC

Strict Apple MVC theory says the Controller should be a thin mediator — but UIKit provides no mechanism to enforce this.

### MVC Layers in UIKit

| Layer | Role | iOS type |
|-------|------|----------|
| Model | Business entities, data access, domain rules | `struct`/`class`, service objects, `CoreData` NSManagedObject |
| View | Display only, no business logic | `UIView` subclasses, XIBs, Storyboards |
| Controller | Glue: owns the view, responds to events, calls model | `UIViewController` |

### Communication Patterns

```
Model ──────────────────▶ Controller ──────────────────▶ View
       (notification/KVO)              (direct update)
       (data source callbacks)

View ───────────────────▶ Controller ──────────────────▶ Model
      (delegate/target-action)         (method call)
```

- **Model → Controller**: `NotificationCenter`, KVO, delegate callbacks, completion handlers
- **Controller → View**: Direct property access (`label.text = ...`)
- **View → Controller**: Target-action, `UITableViewDelegate`, `UITextFieldDelegate`
- **Controller → Model**: Method calls on service/model objects

### The Massive View Controller Problem

A VC accumulates responsibilities because UIKit APIs make it the natural destination:
- `UITableViewDataSource` and `UITableViewDelegate` are almost always on the VC
- Networking is called from `viewDidLoad`
- JSON is parsed and assigned in the completion handler
- Navigation is triggered directly (`navigationController?.pushViewController(...)`)

The result is a 500–2000 line VC that is untestable (because it extends `UIViewController` and requires a view to instantiate) and impossible to reuse.

### When MVC is Appropriate

MVC is not always wrong. It is appropriate when:
- The screen is simple and unlikely to grow (settings, about, onboarding)
- Speed of development matters more than long-term maintainability (prototype, MVP product)
- The team is small and communication overhead of VIPER is not worth it

### Improving MVC Without Switching Patterns

Extract responsibilities into smaller objects:
- **Model layer**: Create service objects and repository classes. The VC calls services, not URLSession directly.
- **DataSource object**: Create a separate `UITableViewDataSource`/`UITableViewDelegate` class.
- **Coordinator**: Extract navigation into a Coordinator.
- **Child VCs**: Decompose complex screens into container + child VCs.

These improvements move toward MVVM or MVP incrementally without a full rewrite.

## 4. Practical Usage

```swift
import UIKit

// ── Model ───────────────────────────────────────────────────────
struct Article: Decodable {
    let id: Int
    let title: String
    let summary: String
}

// Service object — not in the VC
class ArticleService {
    func fetchArticles(completion: @escaping (Result<[Article], Error>) -> Void) {
        // URLSession networking here
        completion(.success([]))
    }
}

// ── Poor MVC — Massive VC (don't do this) ──────────────────────
class BadArticleViewController: UIViewController, UITableViewDataSource {
    private var articles: [Article] = []
    private let tableView = UITableView()

    override func viewDidLoad() {
        super.viewDidLoad()
        // VC does networking, parsing, layout, and data source — too much
        URLSession.shared.dataTask(with: URL(string: "https://api.example.com/articles")!) {
            data, _, _ in
            if let data = data,
               let articles = try? JSONDecoder().decode([Article].self, from: data) {
                DispatchQueue.main.async {
                    self.articles = articles          // direct self capture — retain cycle risk
                    self.tableView.reloadData()
                }
            }
        }.resume()
    }

    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        articles.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "Cell", for: indexPath)
        cell.textLabel?.text = articles[indexPath.row].title
        return cell
    }
}

// ── Better MVC — VC as a thin coordinator ────────────────────
class ArticleDataSource: NSObject, UITableViewDataSource {
    var articles: [Article] = []

    func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        articles.count
    }

    func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "Cell", for: indexPath)
        configure(cell: cell, with: articles[indexPath.row])
        return cell
    }

    private func configure(cell: UITableViewCell, with article: Article) {
        var config = UIListContentConfiguration.subtitleCell()
        config.text = article.title
        config.secondaryText = article.summary
        cell.contentConfiguration = config
    }
}

class ArticleViewController: UIViewController {
    private let tableView = UITableView()
    private let dataSource = ArticleDataSource()   // separate object — not on VC
    private let service = ArticleService()          // injected or created here

    override func viewDidLoad() {
        super.viewDidLoad()
        tableView.dataSource = dataSource
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "Cell")
        setupLayout()
        loadArticles()
    }

    private func loadArticles() {
        service.fetchArticles { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let articles):
                    self?.dataSource.articles = articles
                    self?.tableView.reloadData()
                case .failure(let error):
                    self?.showError(error)
                }
            }
        }
    }

    private func setupLayout() {
        tableView.frame = view.bounds
        tableView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(tableView)
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Error", message: error.localizedDescription, preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What are the three layers of MVC and what is each responsible for?**

A: The **Model** layer owns business entities, data access logic, and domain rules — it is completely independent of UI. The **View** layer renders the UI and forwards user input; it knows nothing about business logic. The **Controller** layer mediates: it receives user events from the View, instructs the Model, and updates the View with Model changes. In UIKit, `UIViewController` is the Controller, `UIView` subclasses are the View, and plain Swift/Objective-C types (structs, classes, services) are the Model.

**Q: What is the "Massive View Controller" problem?**

A: Because UIKit physically couples the ViewController to the view (VC owns `self.view`, receives all lifecycle events, and is the natural delegate for most UIKit controls), it becomes the path of least resistance for adding code. Over time, VCs accumulate: networking code, JSON parsing, navigation logic, form validation, data source implementation, and presentation logic. The resulting 1000+ line VC is impossible to unit-test (it requires UIKit to instantiate), cannot be reused, and is difficult for teams to work on in parallel. The solution is to extract each responsibility into its own object.

### Hard

**Q: How does Apple's MVC differ from the classical MVC described in design-pattern literature?**

A: Classical MVC (Smalltalk-80) makes the View a direct observer of the Model — the View subscribes to model change notifications and updates itself without going through the Controller. Apple's Cocoa MVC breaks this: the View and Model must never communicate directly. The Controller is the exclusive mediator. This "Mediating Controller" pattern was chosen because the View (built in Interface Builder, sometimes generic and reusable) should not know about a specific Model type. The practical consequence is that the Controller's responsibility is larger, making accumulation of logic easier. In classical MVC, the View has more responsibility and can be simpler; in Cocoa MVC, the Controller is the chokepoint.

**Q: Describe three concrete techniques to slim down a Massive View Controller.**

A: (1) **Extract a separate `UITableViewDataSource` class** — move all `numberOfRowsInSection`, `cellForRowAt`, and `cellForHeader` methods into a dedicated class. The VC holds it as a property and sets `tableView.dataSource = myDataSource`. (2) **Move networking and parsing into a service layer** — create `UserService`, `ArticleService`, etc. The VC calls service methods and receives results. The VC itself never uses `URLSession`. (3) **Extract navigation into a Coordinator** — the VC exposes delegate callbacks or closures when the user takes an action, and the Coordinator responds by pushing/presenting the appropriate VC. The VC no longer imports or knows about any other VCs.

### Expert

**Q: Is MVC inherently bad for iOS, or are there situations where it remains the right choice?**

A: MVC is not inherently bad. The problems are: (1) UIKit's tight VC-View coupling makes the Controller an attractive accumulation point; (2) there's no language- or framework-level enforcement of boundaries. In situations where screens are genuinely simple — a pure display screen with one model type and no user input — a thin VC with a service call is perfectly maintainable. The cost of MVVM (a ViewModel class, binding code) or VIPER (five layer objects) is only justified when the screen has complex state, multiple data sources, or needs to be independently testable. Senior engineers choose the minimum architecture that handles the actual complexity — over-engineering a settings screen into VIPER is just as problematic as under-engineering a 10-feature dashboard as a single VC.

## 6. Common Issues & Solutions

**Issue: ViewController is over 500 lines and untestable.**

Solution: Incrementally extract: (1) a dedicated data source class, (2) a service layer for networking, (3) a Coordinator for navigation. Each extraction reduces the VC and creates a unit-testable pure Swift object.

**Issue: Notification/KVO observer added in `viewDidLoad` but never removed.**

Solution: Remove observers in `deinit` or use the block-based `NotificationCenter.addObserver(forName:using:)` form and store the token, removing it in `deinit`.

**Issue: Model objects imported into Views.**

Solution: Views should only receive display-ready values (strings, booleans, colors) — not model types. Transform model data in the Controller (or better, in a ViewModel/Presenter) before passing it to the View.

## 7. Related Topics

- [MVVM](mvvm.md) — the natural evolution from MVC for testable presentation logic
- [MVP & VIPER](mvp-viper.md) — stricter boundaries for larger teams
- [Dependency Injection](dependency-injection.md) — inject services rather than creating them in the VC
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — practical UIKit MVVM implementation
