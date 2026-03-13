# Behavioral Patterns

## 1. Overview

Behavioral patterns deal with **algorithms and the assignment of responsibilities between objects** — how objects communicate, how they share data, and how they distribute work. The four GoF behavioral patterns most important to iOS are: **Observer** (one-to-many notification when state changes — the foundation of `NotificationCenter`, `KVO`, `Combine`, and `@Published`), **Strategy** (interchangeable algorithms behind a common interface — enabling runtime algorithm selection without conditionals), **Command** (encapsulate a request as an object — enabling undo/redo, queuing, and logging of operations), and **State** (alter an object's behaviour when its internal state changes — formalising a finite state machine instead of a tangle of boolean flags). Understanding these patterns allows you to recognise them when they appear in Apple frameworks and apply them deliberately when designing app architecture.

## 2. Simple Explanation

**Observer**: a newspaper subscription — readers (observers) register once, and every time a new edition is published (state changes), they receive a copy automatically. **Strategy**: GPS navigation with selectable routes — "fastest", "avoid tolls", "scenic" are interchangeable algorithms; you swap them without rebuilding the GPS. **Command**: a restaurant order ticket — the waiter writes your order on a ticket (a command object), which the kitchen can execute immediately, execute later, or cancel entirely. The waiter doesn't cook; the kitchen doesn't deal with customers. **State**: a traffic light — the same object (the light controller) behaves completely differently depending on its current state (red: stop, green: go, yellow: prepare to stop). Changing the state changes all future behaviour.

## 3. Deep iOS Knowledge

### Observer

The Observer pattern defines a one-to-many dependency: when one object changes, all its dependants are notified. iOS implements this at multiple layers:

| Mechanism | Scope | Thread-safe | Typed |
|-----------|-------|-------------|-------|
| `NotificationCenter` | Process-wide | Yes (posting) | No (userInfo dict) |
| `KVO` (`addObserver(forKeyPath:)`) | Any object | Yes | No |
| `Combine` / `@Published` | Any publisher | Publisher-dependent | Yes |
| `NotificationCenter.publisher(for:)` | Process-wide | Yes | No (AnyPublisher) |
| SwiftUI `@Observable` | View body | Main actor | Yes |

The GoF Observer maps directly to Combine: `Publisher` = Subject, `Subscriber`/`sink` = Observer, `AnyCancellable` = the subscription (disposable).

### Strategy

The Strategy pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. The context delegates to the strategy:

```swift
protocol SortStrategy { func sort(_ items: inout [Item]) }

final class QuickSort: SortStrategy { ... }
final class MergeSort: SortStrategy { ... }

final class ItemList {
    var strategy: SortStrategy = QuickSort()
    var items: [Item] = []

    func sort() { strategy.sort(&items) }
}
```

iOS examples: `UICollectionViewLayout` (interchangeable layouts — flow, compositional), `URLSessionConfiguration` (ephemeral/default/background — different caching strategies).

### Command

The Command pattern encapsulates a request (method + parameters + receiver) as an object. Enables:
- **Undo/redo**: store executed commands; undo = reverse the last command.
- **Queuing**: commands can be serialised and executed later.
- **Logging**: log commands as they execute.
- **Macro recording**: record a sequence of commands for replay.

iOS example: `UICommand` (menu actions as command objects), `NSUndoManager` (CocoaTouch's built-in command-based undo).

### State

The State pattern allows an object to change its behaviour when its internal state changes. Instead of a large `switch` or chains of `if/else` on an enum, the State pattern externalises each state as a separate object (or value) that handles events.

iOS example: `AVPlayer`'s `status` (`unknown`, `readyToPlay`, `failed`) — the player's behaviour in each state is encapsulated. `URLSessionTask`'s `state` (`running`, `suspended`, `canceling`, `completed`).

## 4. Practical Usage

```swift
import Foundation
import Combine

// ── Observer: Combine publisher ───────────────────────────────
final class CartViewModel: ObservableObject {
    @Published private(set) var items: [CartItem] = []
    @Published private(set) var totalPrice: Decimal = 0

    private var cancellables = Set<AnyCancellable>()

    init() {
        // Observer: totalPrice reacts to any change in items
        $items
            .map { $0.reduce(Decimal(0)) { $0 + $1.price } }
            .assign(to: &$totalPrice)
    }

    func add(_ item: CartItem) { items.append(item) }
    func remove(at index: Int) { items.remove(at: index) }
}

struct CartItem { let name: String; let price: Decimal }

// ── Strategy: Validation strategy ────────────────────────────
protocol ValidationStrategy {
    func validate(_ input: String) -> String?   // returns error message, or nil if valid
}

struct EmailValidation: ValidationStrategy {
    func validate(_ input: String) -> String? {
        let pattern = #"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$"#
        let valid = input.range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
        return valid ? nil : "Please enter a valid email address"
    }
}

struct PasswordValidation: ValidationStrategy {
    func validate(_ input: String) -> String? {
        guard input.count >= 8 else { return "Password must be at least 8 characters" }
        guard input.contains(where: \.isNumber) else { return "Password must contain a number" }
        return nil
    }
}

struct NonEmptyValidation: ValidationStrategy {
    func validate(_ input: String) -> String? {
        input.trimmingCharacters(in: .whitespaces).isEmpty ? "This field is required" : nil
    }
}

// TextField that accepts any validation strategy at construction
final class ValidatingTextField: UITextField {
    var strategy: ValidationStrategy = NonEmptyValidation()
    private(set) var errorMessage: String?

    @discardableResult
    func validate() -> Bool {
        errorMessage = strategy.validate(text ?? "")
        // Update UI to show/hide error
        return errorMessage == nil
    }
}

// ── Command: Text editor with undo/redo ───────────────────────
protocol TextCommand {
    func execute(on text: inout String)
    func undo(on text: inout String)
}

struct InsertTextCommand: TextCommand {
    let index: String.Index
    let insertion: String

    func execute(on text: inout String) {
        text.insert(contentsOf: insertion, at: index)
    }
    func undo(on text: inout String) {
        let end = text.index(index, offsetBy: insertion.count)
        text.removeSubrange(index..<end)
    }
}

struct DeleteTextCommand: TextCommand {
    let range: Range<String.Index>
    private let deletedText: String

    init(range: Range<String.Index>, in text: String) {
        self.range = range
        self.deletedText = String(text[range])
    }

    func execute(on text: inout String) { text.removeSubrange(range) }
    func undo(on text: inout String) { text.insert(contentsOf: deletedText, at: range.lowerBound) }
}

final class TextEditor {
    private(set) var text: String = ""
    private var undoStack: [TextCommand] = []
    private var redoStack: [TextCommand] = []

    func execute(_ command: TextCommand) {
        command.execute(on: &text)
        undoStack.append(command)
        redoStack.removeAll()   // new command invalidates redo history
    }

    func undo() {
        guard let command = undoStack.popLast() else { return }
        command.undo(on: &text)
        redoStack.append(command)
    }

    func redo() {
        guard let command = redoStack.popLast() else { return }
        command.execute(on: &text)
        undoStack.append(command)
    }
}

// ── State: Media player state machine ─────────────────────────
enum PlayerState {
    case idle
    case loading(url: URL)
    case playing(duration: TimeInterval)
    case paused(at: TimeInterval)
    case error(Error)
}

@MainActor
final class MediaPlayerViewModel: ObservableObject {
    @Published private(set) var state: PlayerState = .idle
    @Published private(set) var currentTime: TimeInterval = 0

    func load(url: URL) {
        guard case .idle = state else { return }
        state = .loading(url: url)
        // Start loading...
    }

    func playbackReady(duration: TimeInterval) {
        guard case .loading = state else { return }
        state = .playing(duration: duration)
    }

    func pause() {
        guard case .playing(let duration) = state else { return }
        state = .paused(at: currentTime)
    }

    func resume() {
        guard case .paused(let position) = state else { return }
        currentTime = position
        if case .playing(let d) = state { _ = d }
        // Approximate — in real code, carry duration through state transitions
        state = .playing(duration: 0)
    }

    func error(_ error: Error) {
        state = .error(error)
    }

    func reset() {
        state = .idle
        currentTime = 0
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between NotificationCenter (Observer) and delegation in iOS?**

A: `NotificationCenter` implements **one-to-many** observation — any number of observers can subscribe to any notification, and the poster does not know who is listening. It is appropriate for app-wide events where the sender and receivers have no direct relationship (e.g., `UIApplication.didBecomeActiveNotification`, user settings changes). **Delegation** implements **one-to-one** communication — a single delegate object is assigned and the delegating object calls specific methods on it. It is appropriate for a child object to communicate back to its parent (e.g., `UITableViewDelegate`, `URLSessionDelegate`). The key differences: delegation is typed (protocol methods with parameters), notification userInfo is untyped; delegation is synchronous and direct, NotificationCenter is decoupled; with delegation, only one delegate handles an event, with NotificationCenter multiple observers can respond.

**Q: What is the Strategy pattern and how does it differ from using a simple closure?**

A: The Strategy pattern encapsulates an algorithm as an object conforming to a protocol, making the algorithm independently testable, reusable, and composable with other patterns. A closure also encapsulates behaviour, but: (1) A strategy object can have state (e.g., a caching strategy might hold a cache dictionary); closures must capture state explicitly. (2) A strategy can be identified by type (`type(of: strategy)`) for serialisation or debugging; closures are anonymous. (3) A strategy conforms to a protocol, making it mockable in tests (`MockValidationStrategy`); a closure-based approach requires a `(String) -> String?` type alias and is harder to mock with call-count verification. (4) Multiple strategies can implement the same protocol with different logic — a `RegexValidation` and a `EmailValidation` can both be `ValidationStrategy`. Use closures for simple, stateless one-off behaviours; use Strategy when the algorithm is complex, stateful, or needs to be interchangeable at runtime.

### Hard

**Q: How would you implement an undo/redo system for a drawing app using the Command pattern?**

A: Four components: (1) **Command protocol**: `protocol DrawCommand { func execute(on canvas: inout Canvas); func undo(on canvas: inout Canvas) }`. The `undo` method reverses `execute` exactly. For drawing: `AddStrokeCommand` stores the added stroke; its `undo` removes the last stroke. `EraseCommand` stores both the erased region and the pixels that were there (snapshot); `undo` restores the snapshot. (2) **Command history**: `CommandHistory` holds an `undoStack: [DrawCommand]` and `redoStack: [DrawCommand]`. `execute` appends to undo stack and clears redo stack. `undo` pops from undo, calls `command.undo`, pushes to redo stack. (3) **Composite commands**: for batch operations (e.g., "select all + delete"), use a `CompositeDrawCommand([DrawCommand])` that executes/undoes each child in sequence (reverse order for undo). (4) **Serialisation**: commands are `Codable` — the undo history can be persisted across app launches. This is how professional drawing apps (Procreate, Pixelmator) implement multi-session undo.

**Q: How does the State pattern prevent a tangle of boolean flags in a complex view controller?**

A: Complex VCs often accumulate flags: `isLoading`, `hasError`, `isRefreshing`, `isEmpty`, `isShowingDetail`. These flags can be in mutually exclusive combinations (can't be `isLoading` AND `hasError` at the same time) but the code doesn't enforce this — illegal combinations cause bugs. The State pattern replaces N booleans with a single enum: `enum FeedState { case idle; case loading; case loaded([Post]); case empty; case failed(Error) }`. This enforces mutual exclusivity at the type level — you cannot be in both `.loading` and `.failed` simultaneously. Logic that was `if isLoading { ... } else if hasError { ... } else if isEmpty { ... }` becomes a `switch` over the state enum — exhaustive, unambiguous, and easy to extend with new states. Each state carries exactly the data it needs (`.failed(Error)` carries the error; `.loaded([Post])` carries the posts), avoiding optional properties that are only valid in certain states.

### Expert

**Q: Design a request queuing system using the Command pattern that supports offline operation, retry, and ordering guarantees.**

A: Four components: (1) **Serialisable command**: `protocol QueuedRequest: Codable { var id: UUID { get }; var priority: Int { get }; func execute() async throws }`. Each command is `Codable` so it can be persisted to disk. Concrete commands: `SyncPostCommand(postID:)`, `UpdateProfileCommand(fields:)`. (2) **Persistent queue**: an `actor RequestQueue` backed by a GRDB (SQLite) table with columns `(id, type, payload, priority, status, createdAt, attempts)`. Commands are inserted as rows; on execution, their status is updated. The actor serialises all queue mutations. (3) **Queue processor**: triggered on app foreground and on network reachability changes (using `NWPathMonitor`). Fetches all `pending` commands ordered by priority and `createdAt`. Executes each command; on success, marks it `completed`; on retryable failure (network error), increments `attempts` and schedules a back-off delay; on fatal failure (4xx, max attempts reached), marks it `failed`. (4) **Deduplication**: commands with the same logical identity (e.g., "update profile") upsert — a new `UpdateProfileCommand` replaces the pending one rather than appending, avoiding redundant operations. This architecture supports: offline queuing (rows persist across launches), retry with exponential back-off, priority ordering (analytics are lower priority than sync), and idempotency (commands can be re-executed safely).

## 6. Common Issues & Solutions

**Issue: State enum grows large with many cases and the switch statements become unmanageable.**

Solution: If the state has more than 7–8 cases, consider hierarchical states: a top-level `enum UIState { case loading; case content(ContentState); case error(ErrorState) }` with nested enums. Or, if transitions between states are complex, use the full State Object pattern — each state is a class conforming to a `State` protocol with `enter()`, `exit()`, and event-handling methods. A `StateMachine<State>` manages the current state and valid transitions. Third-party libraries like `swift-state-machine` provide this infrastructure.

**Issue: Observer retains itself because a `NotificationCenter` observer closure captures `self` strongly.**

Solution: Use `[weak self]` in the closure: `NotificationCenter.default.addObserver(forName:object:queue:using: { [weak self] notification in self?.handleNotification(notification) })`. Also store the returned token and call `NotificationCenter.default.removeObserver(token)` in `deinit`. The `addObserver(forName:object:queue:using:)` method returns a token object — failing to remove it keeps the observer alive indefinitely (a classic memory leak).

## 7. Related Topics

- [Creational Patterns](creational-patterns.md) — factories for command and strategy objects
- [Structural Patterns](structural-patterns.md) — composite for combining commands
- [iOS-Specific Patterns](ios-patterns.md) — Delegate as a typed, one-to-one observer
- [Concurrency — Combine](../03-concurrency/combine-publishers.md) — Observer pattern implementation
- [Data Synchronization](../08-data-persistence/data-sync.md) — command queue for offline sync
