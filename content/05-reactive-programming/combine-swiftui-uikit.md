# Combine + UIKit & SwiftUI

## 1. Overview

Combine integrates with both UIKit and SwiftUI to enable reactive data binding — connecting model state changes directly to UI updates without manual observation code. In **SwiftUI**, `@Published` and `ObservableObject` are built on Combine; the framework handles subscription and UI invalidation automatically. In **UIKit**, you manually subscribe to publishers and update UI elements in `sink` closures. Combine also provides publishers for many Foundation and UIKit APIs: `NotificationCenter`, `Timer`, `KVO`, `URLSession`, and `URLSession.WebSocketTask`.

## 2. Simple Explanation

Think of data binding as a smart thermostat. In the old world (UIKit without Combine), you'd manually check the temperature and adjust the heating yourself — repetitive, error-prone. With Combine binding in UIKit, you set up a wire between the temperature sensor (model) and the heating control (UI) once, and the system updates automatically. In SwiftUI, the wiring is even simpler — you just declare what depends on what, and the framework manages everything.

## 3. Deep iOS Knowledge

### @Published and ObservableObject (SwiftUI)

SwiftUI's `ObservableObject` protocol requires that conforming types emit an `objectWillChange` publisher before any property changes. `@Published` handles this automatically — each `@Published` property synthesises a Combine `Publisher` (accessible via `$property`) and calls `objectWillChange.send()` before the value changes.

SwiftUI subscribes to `objectWillChange` and schedules a view re-render when it fires. The `$property` publisher can be used directly in Combine pipelines:

```swift
class ViewModel: ObservableObject {
    @Published var query = ""

    init() {
        $query                           // Publisher<String, Never>
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { [weak self] q in self?.search(query: q) }
            .store(in: &cancellables)
    }
}
```

### Combine in UIKit — Binding Patterns

UIKit has no built-in reactive binding. Patterns for connecting Combine to UIKit:

**Pattern 1: sink to update UI**
```swift
viewModel.$title
    .receive(on: DispatchQueue.main)
    .sink { [weak self] text in
        self?.titleLabel.text = text    // manually update UIKit control
    }
    .store(in: &cancellables)
```

**Pattern 2: assign(to:on:)** — simpler but creates retain cycles if target is `self`:
```swift
viewModel.$title
    .receive(on: DispatchQueue.main)
    .assign(to: \.text, on: titleLabel)   // safe if titleLabel != self
    .store(in: &cancellables)
```

**Pattern 3: UIControl publishers via Combine** — Combine doesn't provide UIControl publishers natively, but you can create them:
```swift
extension UIControl {
    func publisher(for event: UIControl.Event) -> AnyPublisher<Void, Never> {
        UIControlPublisher(control: self, event: event).eraseToAnyPublisher()
    }
}
```

### NotificationCenter Publisher

```swift
NotificationCenter.default
    .publisher(for: UIApplication.willResignActiveNotification)
    .sink { _ in saveState() }
    .store(in: &cancellables)
```

The publisher emits `Notification` values, which you can `map` to extract `userInfo` or the `object`.

### KVO Publisher

For `NSObject` properties marked `@objc dynamic`, Combine provides a KVO publisher:

```swift
let scrollView = UIScrollView()
scrollView
    .publisher(for: \.contentOffset)     // KVO publisher on contentOffset
    .map { offset in offset.y > 100 }    // is header hidden?
    .removeDuplicates()
    .sink { [weak self] shouldHide in
        self?.navigationBar.isHidden = shouldHide
    }
    .store(in: &cancellables)
```

Requirements: the property must be `@objc dynamic` and the owning type must be an `NSObject` subclass.

### UITextField and UISearchBar Integration

Combine doesn't provide built-in UIKit control publishers. A minimal extension:

```swift
extension UITextField {
    var textPublisher: AnyPublisher<String, Never> {
        NotificationCenter.default
            .publisher(for: UITextField.textDidChangeNotification, object: self)
            .compactMap { ($0.object as? UITextField)?.text }
            .eraseToAnyPublisher()
    }
}
```

### Combine vs SwiftUI Binding

| Binding target | Combine approach | SwiftUI approach |
|---------------|-----------------|-----------------|
| UILabel.text | `.sink { label.text = $0 }` | `Text(viewModel.name)` directly |
| UISwitch | KVO or NotificationCenter publisher | `Toggle(isOn: $viewModel.flag)` |
| UITableView | `.sink { tableView.reloadData() }` | `List(viewModel.items)` |
| UITextField | NotificationCenter publisher | `TextField("", text: $viewModel.query)` |

### Bridging Combine to async/await

iOS 15+ allows consuming any Combine publisher as an `AsyncSequence` via the `.values` property:

```swift
for await value in viewModel.$someProperty.values {
    // each new value of someProperty arrives here
}
```

And converting async work to a Combine publisher:
```swift
func asyncToCombine<T>(_ work: @escaping () async throws -> T) -> AnyPublisher<T, Error> {
    Future { promise in
        Task {
            do { promise(.success(try await work())) }
            catch { promise(.failure(error)) }
        }
    }
    .eraseToAnyPublisher()
}
```

### Thread Safety in UIKit Binding

Combine delivers values on the scheduler of the upstream publisher (usually a background thread for network publishers). Always add `receive(on: DispatchQueue.main)` before any operator or `sink` that updates UIKit controls. Omitting this causes purple runtime warnings ("UIView was accessed from a non-main thread").

## 4. Practical Usage

```swift
import Combine
import UIKit
import SwiftUI

// ── ViewModel shared between UIKit and SwiftUI ─────────────────
@MainActor
class UserViewModel: ObservableObject {
    @Published var displayName: String = ""
    @Published var isLoading: Bool = false
    @Published var avatarURL: URL?

    private var cancellables = Set<AnyCancellable>()

    func loadUser(id: String) {
        isLoading = true
        // Network call via Combine or async/await
        URLSession.shared.dataTaskPublisher(
            for: URL(string: "https://api.example.com/users/\(id)")!
        )
        .map(\.data)
        .decode(type: APIUser.self, decoder: JSONDecoder())
        .receive(on: DispatchQueue.main)
        .sink(
            receiveCompletion: { [weak self] _ in self?.isLoading = false },
            receiveValue: { [weak self] user in
                self?.displayName = user.name
                self?.avatarURL = user.avatarURL
            }
        )
        .store(in: &cancellables)
    }
}

struct APIUser: Decodable { let name: String; let avatarURL: URL? }

// ── SwiftUI View — @Published drives UI automatically ─────────
struct UserProfileView: View {
    @StateObject private var viewModel = UserViewModel()

    var body: some View {
        VStack {
            if viewModel.isLoading {
                ProgressView()
            } else {
                Text(viewModel.displayName)
                    .font(.title)
            }
        }
        .onAppear { viewModel.loadUser(id: "42") }
    }
}

// ── UIKit ViewController bound to the same ViewModel ──────────
class UserProfileViewController: UIViewController {
    private let viewModel: UserViewModel
    private var cancellables = Set<AnyCancellable>()

    private let nameLabel = UILabel()
    private let loadingIndicator = UIActivityIndicatorView(style: .medium)

    init(viewModel: UserViewModel) {
        self.viewModel = viewModel
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        setupViews()
        bindViewModel()
        viewModel.loadUser(id: "42")
    }

    private func bindViewModel() {
        // Bind displayName → label text
        viewModel.$displayName
            .receive(on: DispatchQueue.main)            // UIKit update on main thread
            .sink { [weak self] name in                 // [weak self] prevents retain cycle
                self?.nameLabel.text = name
            }
            .store(in: &cancellables)

        // Bind isLoading → activity indicator
        viewModel.$isLoading
            .receive(on: DispatchQueue.main)
            .sink { [weak self] loading in
                loading
                    ? self?.loadingIndicator.startAnimating()
                    : self?.loadingIndicator.stopAnimating()
            }
            .store(in: &cancellables)
    }

    private func setupViews() {
        view.backgroundColor = .systemBackground
        [nameLabel, loadingIndicator].forEach {
            $0.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview($0)
        }
        NSLayoutConstraint.activate([
            nameLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            nameLabel.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            loadingIndicator.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            loadingIndicator.topAnchor.constraint(equalTo: nameLabel.bottomAnchor, constant: 8)
        ])
    }
}

// ── NotificationCenter publisher ──────────────────────────────
class KeyboardObserver {
    private var cancellables = Set<AnyCancellable>()

    func observe(adjustingView view: UIView) {
        NotificationCenter.default
            .publisher(for: UIResponder.keyboardWillShowNotification)
            .compactMap { $0.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect }
            .map { keyboardFrame in keyboardFrame.height }
            .sink { [weak view] keyboardHeight in
                view?.transform = CGAffineTransform(translationX: 0, y: -keyboardHeight)
            }
            .store(in: &cancellables)

        NotificationCenter.default
            .publisher(for: UIResponder.keyboardWillHideNotification)
            .sink { [weak view] _ in
                view?.transform = .identity
            }
            .store(in: &cancellables)
    }
}

// ── KVO publisher — track scroll position ─────────────────────
class HeaderViewController: UIViewController {
    private let scrollView = UIScrollView()
    private var cancellables = Set<AnyCancellable>()

    override func viewDidLoad() {
        super.viewDidLoad()

        scrollView
            .publisher(for: \.contentOffset)            // KVO on contentOffset
            .map { $0.y }
            .removeDuplicates()
            .sink { [weak self] offsetY in
                let alpha = min(1.0, max(0.0, offsetY / 100))
                self?.navigationController?.navigationBar.alpha = alpha
            }
            .store(in: &cancellables)
    }
}

// ── @Published pipeline — search debounce ─────────────────────
class SearchViewModel: ObservableObject {
    @Published var searchText = ""
    @Published var results: [String] = []

    private var cancellables = Set<AnyCancellable>()

    init() {
        $searchText                                      // Publisher<String, Never>
            .debounce(for: .milliseconds(300), scheduler: DispatchQueue.main)
            .removeDuplicates()
            .filter { !$0.isEmpty }
            .map { query in ["Result: \(query)"] }       // replace with real search
            .assign(to: &$results)                       // assign to @Published — no cycle
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: How does `@Published` integrate with Combine and SwiftUI?**

A: `@Published` is a property wrapper that wraps a stored value and synthesises a Combine `Publisher` accessible via the `$` prefix (e.g., `$name` is a `Published<String>.Publisher`). When the wrapped value changes, it calls `objectWillChange.send()` on the enclosing `ObservableObject` before the change, triggering SwiftUI to schedule a view re-render. The `$name` publisher also emits the new value downstream, so it can be used in Combine pipelines with operators like `debounce`, `map`, and `sink`. This dual role — triggering SwiftUI and serving as a Combine source — makes `@Published` the primary bridge between reactive models and the SwiftUI view layer.

**Q: Why do you need `receive(on: DispatchQueue.main)` when binding Combine to UIKit?**

A: Combine delivers values on the same thread/scheduler as the upstream publisher. For `URLSession.dataTaskPublisher`, values arrive on a background queue managed by `URLSession`. UIKit requires that all view updates happen on the main thread — accessing any `UIView` property from a background thread is a data race and causes runtime warnings or crashes. `receive(on: DispatchQueue.main)` inserts a scheduler hop, ensuring the downstream `sink` closure runs on the main thread. In SwiftUI, `@MainActor` on the `ObservableObject` class ensures all `@Published` mutations happen on the main thread, eliminating the need for manual `receive(on:)`.

### Hard

**Q: What is the difference between using `assign(to:on:)` and `sink` for UIKit binding and which is safer?**

A: `assign(to:on:)` assigns emitted values to a property via key path and holds a **strong** reference to the target object. If the target is `self` and you store the `AnyCancellable` in `self`, you have a retain cycle: `self → AnyCancellable → assign → self`. This prevents deallocation. `sink { [weak self] in self?.property = value }` uses `[weak self]` to avoid the cycle — the closure holds a weak reference. `assign(to:on:)` is safe when the target is **not** the same object holding the `AnyCancellable` (e.g., assigning to a `UILabel` reference that is a separate object). For assigning to `@Published` properties on `self`, use `assign(to: &$property)` (iOS 14+) — this form is retain-cycle safe.

**Q: How would you implement a UITextField text change publisher without third-party libraries?**

A: Two approaches: (1) `NotificationCenter.publisher(for: UITextField.textDidChangeNotification, object: textField)` — emits a `Notification`; use `compactMap { ($0.object as? UITextField)?.text }` to extract the text. (2) A custom `Publisher` + `Subscription` that adds a target-action pair to the `UITextField` for `.editingChanged` events. When the control fires, the subscription calls `receive(_ input:)` on the subscriber. Wrap in a `UITextField` extension for ergonomics. The NotificationCenter approach is simpler but doesn't deliver an initial value; the custom publisher approach can optionally emit the current text on subscription.

### Expert

**Q: Describe a complete reactive data binding architecture using Combine in a UIKit app without SwiftUI.**

A: (1) **ViewModel**: `ObservableObject` class with `@Published` properties for each piece of UI state — `@Published var items: [Item]`, `@Published var isLoading: Bool`, `@Published var error: String?`. Mark the class `@MainActor`. (2) **ViewController binding**: In `viewDidLoad`, subscribe to each `@Published` publisher with `sink { [weak self] value in ... }.store(in: &cancellables)`. Use `receive(on: DispatchQueue.main)` if the ViewModel isn't `@MainActor`. (3) **User actions**: The VC calls ViewModel methods directly (e.g., `viewModel.loadItems()`). The ViewModel performs async work and publishes results via `@Published`. (4) **Lifecycle**: Cancel subscriptions in `deinit` or `viewWillDisappear` via `cancellables.removeAll()`. (5) **Testing**: Inject a mock service into the ViewModel constructor; observe `@Published` values in tests using `sink` with an `XCTestExpectation`. This architecture is identical to SwiftUI's MVVM — the only difference is the manual binding step in the VC.

## 6. Common Issues & Solutions

**Issue: UIKit control not updating despite publisher emitting values.**

Solution: Missing `receive(on: DispatchQueue.main)`. Add it before the `sink` that updates the UI control. Also check that `AnyCancellable` is stored.

**Issue: `assign(to:on: self)` causes a memory leak.**

Solution: Replace with `assign(to: &$publishedProperty)` or `sink { [weak self] in self?.property = $0 }`.

**Issue: KVO publisher crashes with "An -observeValueForKeyPath:ofObject:change:context: message was received but not handled."**

Solution: The property is not `@objc dynamic`. Both `@objc` and `dynamic` are required for KVO — `@objc` makes it visible to Objective-C, `dynamic` forces runtime dispatch through the KVO machinery.

**Issue: Combine pipeline in UIViewController fires after the VC is deallocated.**

Solution: The `AnyCancellable` is still alive (held by the publisher or another object). Ensure `cancellables` is a property on `self` and is cleared on deallocation. Also use `[weak self]` in all closures.

## 7. Related Topics

- [Publishers & Subscribers](publishers-subscribers.md) — the protocol foundation
- [Operators](operators.md) — debounce, removeDuplicates used in binding pipelines
- [Subjects](subjects.md) — PassthroughSubject as an action relay from UIKit controls
- [Backpressure & Cancellation](backpressure-cancellation.md) — [weak self] and AnyCancellable lifetime
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — @Published and ObservableObject in SwiftUI
- [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — architecture that hosts Combine bindings
