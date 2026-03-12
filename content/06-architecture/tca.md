# The Composable Architecture (TCA)

## 1. Overview

The Composable Architecture (TCA), created by Brandon Williams and Stephen Celis at Point-Free, is an opinionated Swift framework for building applications in a **unidirectional data-flow** style. All application state lives in a single `State` struct; all state mutations happen in a pure `Reducer` function in response to `Action` values; all side effects (networking, timers, notifications) are modelled as `Effect` values returned from the Reducer and executed by the `Store`. TCA provides strong guarantees around testability, state mutation, and composition — at the cost of a steeper learning curve and a required framework dependency.

## 2. Simple Explanation

Imagine TCA as a vending machine. The **State** is what's currently displayed on the screen (selected item, price, change available). An **Action** is a button press (press B3, insert coin). The **Reducer** is the machine's internal logic — given the current state and an action, it produces the next state (deterministic, no surprises). An **Effect** is something the machine does in the outside world — dispense a product, make change, call the maintenance company. The **Store** is the machine itself — it wires all of this together and drives the display. You never mutate the display directly — you send an action to the machine and trust the reducer.

## 3. Deep iOS Knowledge

### Core TCA Types

**State**: A value type (`struct`) containing all data a feature needs to display its UI and manage its logic. No mutable logic — pure data.

**Action**: An enum listing every event a feature can receive — user gestures, system callbacks, async results. Actions are the only way state can change.

**Reducer**: A function `(inout State, Action) -> Effect<Action>` that mutates state and returns side effects. It must be pure — given the same state and action, always produces the same new state and effects.

**Effect**: Represents async work to be performed outside the reducer. Effects are run by the Store and their results are fed back as new Actions. Effects in modern TCA use Swift's async/await.

**Store**: The runtime that holds `State`, runs the `Reducer`, executes `Effect`s, and allows Views to observe state and send actions.

### Unidirectional Data Flow

```
┌─────────────────────────────────────────┐
│                   Store                 │
│                                         │
│  State ──▶ View (read-only observation) │
│                  │                      │
│               Action (send)             │
│                  │                      │
│  Reducer(state, action) → new State     │
│                  │                      │
│              Effect ──▶ async work      │
│                          │              │
│                       Action (result)   │
│                          │              │
│              Reducer again...           │
└─────────────────────────────────────────┘
```

No side effects in the Reducer. No mutable state outside the Store. This makes every state transition **traceable, reproducible, and testable**.

### Composition

TCA's key promise: features compose cleanly. A parent feature can embed a child feature's `State` and `Action`, and delegate to the child `Reducer`. Navigation (sheet, alert, navigation stack) is driven by optional state — when state is non-nil, the destination appears; when nil, it disappears.

```swift
@Reducer
struct ParentFeature {
    struct State: Equatable {
        var child: ChildFeature.State?  // nil = not presented
    }
    enum Action {
        case child(ChildFeature.Action)
        case showChild
    }
    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .showChild:
                state.child = ChildFeature.State()
                return .none
            case .child: return .none
            }
        }
        .ifLet(\.child, action: \.child) {
            ChildFeature()
        }
    }
}
```

### Effects

Side effects are returned from the Reducer as `Effect<Action>` values:

```swift
case .loadButtonTapped:
    state.isLoading = true
    return .run { send in
        let users = try await userService.fetchUsers()
        await send(.usersLoaded(users))
    }
```

`.run` executes an async closure on TCA's internal task infrastructure and feeds results back as actions. Effects can be cancelled with IDs.

### Testing

TCA's `TestStore` is its most powerful feature — it provides a step-by-step assertion API:

```swift
let store = TestStore(initialState: CounterFeature.State()) {
    CounterFeature()
}

await store.send(.incrementButtonTapped) {
    $0.count = 1   // assert state mutation
}

await store.receive(.timerTicked) {
    $0.count = 2   // assert effect-driven action and state
}
```

Every sent action and every action received from an effect must be explicitly accounted for — unaccounted actions fail the test. This gives exhaustive, step-by-step test coverage of state machines.

### Dependencies in TCA

TCA provides a `@Dependency` system that replaces constructor injection:

```swift
struct UserFeature: Reducer {
    @Dependency(\.userClient) var userClient   // injected at use site
}
```

In tests, override dependencies inline:

```swift
let store = TestStore(...) {
    UserFeature()
} withDependencies: {
    $0.userClient.fetchUsers = { .mock }
}
```

### TCA vs MVVM Tradeoffs

| | MVVM | TCA |
|--|------|-----|
| State mutability | Mutable ViewModel properties | Only via Reducer (pure) |
| Side effects | Async methods on ViewModel | `Effect` values |
| Testing | Mock service injection | `TestStore` exhaustive assertions |
| Learning curve | Low | High |
| Framework dependency | Optional (Combine) | Required (TCA library) |
| State traceability | Manual logging | Built-in (reducers log actions) |
| Composition | Coordinator for navigation | State-driven `.ifLet`, `.forEach` |

## 4. Practical Usage

```swift
import ComposableArchitecture
import SwiftUI

// ── Simple counter feature ────────────────────────────────────
@Reducer
struct CounterFeature {
    // All feature state in one struct
    struct State: Equatable {
        var count = 0
        var isTimerRunning = false
    }

    // All events as an enum
    enum Action {
        case incrementTapped
        case decrementTapped
        case toggleTimerTapped
        case timerTicked
    }

    // Cancellation ID for the timer effect
    enum CancelID { case timer }

    // Reducer — pure function: (state, action) → next state + effects
    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .incrementTapped:
                state.count += 1
                return .none                      // no side effects

            case .decrementTapped:
                state.count -= 1
                return .none

            case .toggleTimerTapped:
                state.isTimerRunning.toggle()
                if state.isTimerRunning {
                    return .run { send in          // start async effect
                        while true {
                            try await Task.sleep(for: .seconds(1))
                            await send(.timerTicked)   // feed action back
                        }
                    }
                    .cancellable(id: CancelID.timer)  // register cancellation ID
                } else {
                    return .cancel(id: CancelID.timer) // cancel on stop
                }

            case .timerTicked:
                state.count += 1
                return .none
            }
        }
    }
}

// ── SwiftUI View — observes Store ─────────────────────────────
struct CounterView: View {
    // ViewStore holds a reference to the Store and provides state + action send
    let store: StoreOf<CounterFeature>

    var body: some View {
        WithViewStore(self.store, observe: { $0 }) { viewStore in
            VStack(spacing: 16) {
                Text("\(viewStore.count)")
                    .font(.largeTitle)

                HStack {
                    Button("−") { viewStore.send(.decrementTapped) }
                    Button("+") { viewStore.send(.incrementTapped) }
                }

                Button(viewStore.isTimerRunning ? "Stop Timer" : "Start Timer") {
                    viewStore.send(.toggleTimerTapped)
                }
                .foregroundStyle(viewStore.isTimerRunning ? .red : .green)
            }
        }
    }
}

// ── Network effect with dependency injection ──────────────────
struct User: Equatable { let id: Int; let name: String }

struct UserClient {
    var fetchUsers: () async throws -> [User]
}

extension UserClient: DependencyKey {
    static let liveValue = UserClient(
        fetchUsers: { [] }   // replace with real URLSession call
    )
    static let testValue = UserClient(
        fetchUsers: { [User(id: 1, name: "Test")] }
    )
}

extension DependencyValues {
    var userClient: UserClient {
        get { self[UserClient.self] }
        set { self[UserClient.self] = newValue }
    }
}

@Reducer
struct UsersFeature {
    struct State: Equatable {
        var users: [User] = []
        var isLoading = false
        var errorMessage: String?
    }

    enum Action {
        case onAppear
        case usersResponse(Result<[User], Error>)
    }

    @Dependency(\.userClient) var userClient    // injected — no constructor arg needed

    var body: some ReducerOf<Self> {
        Reduce { state, action in
            switch action {
            case .onAppear:
                state.isLoading = true
                return .run { send in
                    await send(.usersResponse(
                        Result { try await userClient.fetchUsers() }
                    ))
                }

            case .usersResponse(.success(let users)):
                state.isLoading = false
                state.users = users
                return .none

            case .usersResponse(.failure(let error)):
                state.isLoading = false
                state.errorMessage = error.localizedDescription
                return .none
            }
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is unidirectional data flow and how does TCA implement it?**

A: Unidirectional data flow means state can only flow in one direction: state → view (read), view → action (send), action → reducer (mutation), reducer → effect (side effect), effect result → action. There is no bidirectional binding and no direct state mutation from the view. TCA enforces this by making `State` a value type, mutations only possible inside the `Reducer`, and all async work returned as `Effect` values. This makes every state transition explicit, traceable, and reproducible — you can replay any sequence of actions and always arrive at the same state.

**Q: What is the role of `Effect` in TCA?**

A: `Effect` represents async work that the Reducer cannot do directly (networking, timers, persistence). Reducers are pure functions — they cannot call `await` or perform side effects. Instead, they return an `Effect<Action>` value describing what work to do. The `Store` executes these effects, and when they produce results, feeds them back as new `Action` values into the Reducer. This keeps the Reducer pure and all side effects explicit, observable, and cancellable.

### Hard

**Q: How does TCA's `TestStore` provide stronger test guarantees than injecting a mock into a ViewModel?**

A: A `TestStore` requires you to account for every action sent and every action received from effects. If a test sends `.loadButtonTapped` and the Reducer returns an effect that fires `.usersLoaded([...])`, you must explicitly handle that with `store.receive(.usersLoaded([...]))` and assert the resulting state mutation. Any unhandled action fails the test. This means you cannot accidentally ignore state changes — the test will catch them. With a ViewModel + mock, tests only check the properties you assert — if the ViewModel changes an additional property you didn't check, the test passes silently. TCA's `TestStore` is **exhaustive** by default; MVVM tests are asserting specific outcomes only.

**Q: How does TCA handle navigation between screens?**

A: Navigation in TCA is **state-driven**: a parent feature's `State` contains an optional child feature `State` (for sheet/popover) or an enum of possible destinations. When the optional is non-nil, the destination is presented; when set to nil, it is dismissed. Navigation actions (`.destinationPresented`, `.destinationDismissed`) trigger state mutations. The `Store` is scoped to the child feature via `.scope(state:action:)`. This approach means navigation is fully testable — asserting that a button tap sets `state.destination = .some(ChildFeature.State())` is a plain equality assertion.

### Expert

**Q: How would you incrementally adopt TCA in an existing MVC/MVVM codebase?**

A: Incrementally, feature by feature: (1) Identify a new feature or a high-churn existing feature. (2) Build it as a TCA `Reducer` with `State`, `Action`, and `Effect`. (3) Present it from the existing UIKit coordinator using `UIHostingController(rootView: TCAFeatureView(store: store))`. The existing code outside this feature remains unchanged. (4) When navigating from the TCA feature to a legacy UIKit screen, use the Router/Coordinator pattern — the TCA feature's Reducer sets a navigation flag, an `Effect` calls a callback on the Coordinator, and the Coordinator performs the UIKit push. (5) Gradually expand the TCA surface while retiring MVC/MVVM screens. The key integration points: `UIHostingController` to embed SwiftUI TCA views in UIKit, and callback effects to cross the TCA/UIKit boundary for navigation.

## 6. Common Issues & Solutions

**Issue: Reducer becomes very large for a complex feature.**

Solution: Decompose using `Scope` and child reducers. Extract sub-domains (e.g., a form, a list, a filter panel) into their own `Reducer` types and combine with `Scope(state:action:) { ChildReducer() }`. TCA's composition model is designed for this.

**Issue: `TestStore` fails because an effect fires an unexpected action.**

Solution: Use `store.exhaustivity = .off` for a specific test to make it non-exhaustive, or account for all actions explicitly. The exhaustive mode is intentional — it makes your tests catch unintended state changes. Fix the test to handle all actions, or scope the store to just the sub-feature being tested.

**Issue: State struct is too large — every view re-renders on any state change.**

Solution: Use `observe:` in `WithViewStore` to extract only the slice of state the View reads: `WithViewStore(store, observe: { $0.items })`. The view re-renders only when `items` changes, not when unrelated state mutates.

## 7. Related Topics

- [MVP & VIPER](mvp-viper.md) — VIPER's Clean Architecture foundation, which TCA also applies
- [MVVM](mvvm.md) — the simpler alternative for most apps
- [Dependency Injection](dependency-injection.md) — TCA's @Dependency system
- [async/await](../03-concurrency/async-await.md) — TCA Effects use structured concurrency internally
