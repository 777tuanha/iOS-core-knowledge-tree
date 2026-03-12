# SwiftUI State Management

## 1. Overview

SwiftUI uses a reactive, unidirectional data-flow model where the UI is a **function of state**. Five property wrappers govern how state is owned, shared, and observed: `@State`, `@Binding`, `@ObservedObject`, `@StateObject`, and `@EnvironmentObject`. Each has a specific ownership rule — getting this wrong causes bugs like lost state on re-render, memory leaks, or views not updating. Understanding when to use each and why is one of the most-tested SwiftUI topics in senior iOS interviews.

## 2. Simple Explanation

Think of a house as a SwiftUI view hierarchy. `@State` is a piece of furniture you own — you bought it, you control it, you can move it. `@Binding` is a key to someone else's furniture — you can use it and change it, but you don't own it. `@StateObject` is a pet you own — you adopted it and you're responsible for it for your whole tenancy. `@ObservedObject` is a pet you're babysitting — you can interact with it and care for it, but you didn't adopt it. `@EnvironmentObject` is the shared Wi-Fi password — you don't own it, it's just available to everyone in the house.

## 3. Deep iOS Knowledge

### @State

`@State` stores simple value-type data local to a view. SwiftUI owns the storage — not the view struct itself. When the value changes, SwiftUI invalidates the view and re-evaluates `body`.

- **Ownership**: The view that declares it.
- **Scope**: Private to that view and its children (via `@Binding`).
- **Storage**: Allocated by the SwiftUI framework outside the view struct (so re-creating the view struct doesn't reset the value).
- **Type**: Value types only (Int, String, Bool, structs).

```swift
@State private var count = 0
```

### @Binding

`@Binding` is a two-way reference to state owned elsewhere. It does not allocate storage — it reads from and writes to the source's `@State` or published property.

- **Ownership**: None — it projects from a parent's `@State` or `@StateObject`.
- **Use case**: Child views that need to mutate parent state.
- Created by prefixing the parent's `@State` property with `$`: `$count`.

### @ObservedObject

`@ObservedObject` subscribes a view to an external `ObservableObject`. When any `@Published` property on the object changes, the view re-renders.

- **Ownership**: The object is owned **outside** the view — by a parent, a coordinator, or a dependency injection container.
- **Critical caveat**: SwiftUI does **not** retain the object. If the owner is deallocated, the observed object is deallocated too — the view holds only a weak reference pattern.
- **Problem**: If a view creates an `ObservableObject` and stores it in `@ObservedObject`, it will be recreated every time the view is re-initialised, losing all state.

### @StateObject

`@StateObject` is the fix for `@ObservedObject`'s ownership problem. It creates **and owns** the `ObservableObject` for the view's lifetime. SwiftUI creates it exactly once per view identity and keeps it alive across re-renders.

- **Ownership**: The view that declares it.
- **Lifetime**: Tied to the view's identity in the view tree — survives re-renders, destroyed when the view leaves the tree.
- **Use case**: Any `ObservableObject` that should be created and owned by a view.

### Comparison: @ObservedObject vs @StateObject

| | `@ObservedObject` | `@StateObject` |
|--|---|---|
| Creates object? | No | Yes (once) |
| Owns object? | No | Yes |
| Stable across re-renders? | Depends on owner | Yes |
| Use when | Injecting from parent | Creating in view |

### @EnvironmentObject

`@EnvironmentObject` reads an `ObservableObject` from the SwiftUI environment — an implicit dependency injection system. Any ancestor view can inject an object with `.environmentObject(_:)`, and any descendant can read it with `@EnvironmentObject`.

- **Ownership**: Injected by an ancestor — typically the App struct or a coordinator.
- **Scope**: Available anywhere in the subtree below the injection point.
- **Crash risk**: If you read `@EnvironmentObject` from a view that hasn't had the object injected, the app crashes at runtime.

### @Environment

Different from `@EnvironmentObject` — `@Environment` reads system-provided values (color scheme, size class, locale, font):

```swift
@Environment(\.colorScheme) var colorScheme
@Environment(\.dismiss) var dismiss
```

### @Observable (iOS 17+ — Observation framework)

iOS 17 introduced the `@Observable` macro, replacing `ObservableObject` + `@Published`:

```swift
@Observable
class UserViewModel {
    var name: String = ""
    var isLoading: Bool = false
}
```

Views that access properties of an `@Observable` object automatically subscribe to only the properties they read — no `@Published` annotations needed, and no `@ObservedObject`/`@StateObject` distinction required (use `@State` or plain `var`).

### Data Flow Rules

```
Owner creates data        → @State / @StateObject
Child reads + mutates     → @Binding (from $state / $stateObject.property)
Object injected in        → @ObservedObject
Object created in view    → @StateObject
Wide-scope sharing        → @EnvironmentObject
System values             → @Environment
```

### Thread Safety

`ObservableObject` updates that modify `@Published` properties must happen on the **main thread** — SwiftUI observes these changes and updates the UI synchronously. Mark ViewModels with `@MainActor` to ensure this:

```swift
@MainActor
class ProfileViewModel: ObservableObject {
    @Published var profile: Profile?
    func loadProfile() async { /* ... */ }
}
```

## 4. Practical Usage

```swift
import SwiftUI
import Combine

// ── @State — local toggle ──────────────────────────────────────
struct CounterView: View {
    @State private var count = 0          // owned by this view; private

    var body: some View {
        VStack {
            Text("Count: \(count)")
            Button("Increment") { count += 1 }  // direct mutation triggers re-render
        }
    }
}

// ── @Binding — child mutates parent's state ───────────────────
struct ToggleRow: View {
    let title: String
    @Binding var isOn: Bool               // no storage — projects from parent

    var body: some View {
        Toggle(title, isOn: $isOn)        // $isOn creates a Binding<Bool>
    }
}

struct SettingsView: View {
    @State private var notificationsOn = true   // owned here

    var body: some View {
        ToggleRow(title: "Notifications", isOn: $notificationsOn)  // pass Binding
    }
}

// ── @StateObject — view owns the view model ───────────────────
@MainActor                                // all UI work on main thread
class FeedViewModel: ObservableObject {
    @Published var posts: [String] = []
    @Published var isLoading = false

    func loadPosts() async {
        isLoading = true
        defer { isLoading = false }
        // await networkService.fetchPosts()
        posts = ["Post 1", "Post 2", "Post 3"]
    }
}

struct FeedView: View {
    @StateObject private var viewModel = FeedViewModel()  // created once, owned here

    var body: some View {
        Group {
            if viewModel.isLoading {
                ProgressView()
            } else {
                List(viewModel.posts, id: \.self) { Text($0) }
            }
        }
        .task { await viewModel.loadPosts() }  // cancels when view disappears
    }
}

// ── @ObservedObject — injected from outside ───────────────────
struct PostDetailView: View {
    @ObservedObject var viewModel: FeedViewModel  // NOT created here — injected

    var body: some View {
        List(viewModel.posts, id: \.self) { Text($0) }
    }
}

// ── @EnvironmentObject — wide sharing ─────────────────────────
@MainActor
class AuthService: ObservableObject {
    @Published var isLoggedIn = false
    func login() { isLoggedIn = true }
    func logout() { isLoggedIn = false }
}

struct RootView: View {
    @StateObject private var auth = AuthService()  // owned at root

    var body: some View {
        ContentView()
            .environmentObject(auth)               // inject into environment
    }
}

struct ProfileButton: View {
    @EnvironmentObject var auth: AuthService       // read from anywhere in subtree

    var body: some View {
        Button(auth.isLoggedIn ? "Logout" : "Login") {
            if auth.isLoggedIn { auth.logout() } else { auth.login() }
        }
    }
}

// ── Custom Binding for derived state ─────────────────────────
struct SliderView: View {
    @State private var percentage: Double = 0.5

    // Derived binding: exposes percentage as 0–100 integer
    var percentageInt: Binding<Int> {
        Binding(
            get: { Int(percentage * 100) },
            set: { percentage = Double($0) / 100 }
        )
    }

    var body: some View {
        VStack {
            Slider(value: $percentage)
            Stepper("Value: \(percentageInt.wrappedValue)", value: percentageInt, in: 0...100)
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `@State` and `@Binding`?**

A: `@State` allocates and **owns** storage for a value. When the value changes, SwiftUI re-evaluates the view's `body`. It should be private and scoped to the declaring view. `@Binding` does **not** allocate storage — it is a two-way reference to state owned by another view (or `@StateObject`). Changes to a `@Binding` propagate back to the original `@State`. A child view receives a `@Binding` by accepting a `Binding<T>` parameter and the parent passes it with the `$` prefix on a `@State` variable.

**Q: What is `ObservableObject` and when should you use it?**

A: `ObservableObject` is a protocol for reference-type models that emit change notifications. Properties marked `@Published` automatically trigger `objectWillChange.send()` before they change. SwiftUI views that observe an `ObservableObject` (via `@StateObject` or `@ObservedObject`) re-render when any `@Published` property changes. Use `ObservableObject` for view models — objects that hold business logic and data that the view reads, and that outlive a single view instance.

### Hard

**Q: Why does `@ObservedObject` lose state when a parent view re-renders, and how does `@StateObject` fix it?**

A: When a parent view's `body` re-evaluates, it re-initialises any child view structs. If a child view creates an `ObservableObject` inside its `init` and stores it as `@ObservedObject`, that object is recreated on every parent re-render — losing all accumulated state. `@StateObject` solves this because SwiftUI manages the object's lifetime independently of struct re-initialisation. The object is created once when the view first appears in the view identity tree, and kept alive as long as the view remains in the tree — even if the view struct is re-created many times during re-renders.

**Q: How does `@EnvironmentObject` differ from passing an `@ObservedObject` through the view hierarchy?**

A: Passing `@ObservedObject` explicitly requires every intermediate view in the hierarchy to accept and forward the object, even if they don't use it — this is called "prop drilling". `@EnvironmentObject` injects the object into the environment at an ancestor level and makes it available to any descendant without explicit forwarding. The tradeoff: `@EnvironmentObject` is implicit — there's no compile-time guarantee the object was injected. A view that reads `@EnvironmentObject` crashes at runtime if the environment doesn't contain the required type. For this reason, inject `@EnvironmentObject` only for genuinely app-wide singletons (authentication, theme, feature flags).

### Expert

**Q: How does the Observation framework (`@Observable`, iOS 17) improve on `ObservableObject` + `@Published`?**

A: `ObservableObject` + `@Published` has coarse granularity — any change to any `@Published` property triggers a full view re-render, even if the view only reads one property. With the `@Observable` macro, SwiftUI tracks exactly which properties a view's `body` accesses during rendering, and only re-renders when those specific properties change. This fine-grained observation eliminates redundant re-renders. Additionally: no `@Published` annotations needed, no `ObservableObject` protocol conformance, and no `@StateObject`/`@ObservedObject` distinction — just use the object as a regular `var` (or `@State` if the view owns it). The main caveat: requires iOS 17+, so production apps supporting older OS versions still need the `ObservableObject` approach.

## 6. Common Issues & Solutions

**Issue: View using `@ObservedObject` doesn't update when ViewModel changes.**

Solution: The ViewModel must conform to `ObservableObject` and the changing property must be marked `@Published`. Also verify the ViewModel instance is not being recreated on each render — if it is, migrate to `@StateObject`.

**Issue: `@EnvironmentObject` crash — "No ObservableObject of type X found".**

Solution: You read `@EnvironmentObject` in a view that was not presented within a subtree that had `.environmentObject(_:)` applied. Common cause: a sheet or navigation destination that is presented outside the `.environmentObject` modifier's scope. Fix: inject the environment object at the highest ancestor that covers all presentation paths (typically at the `App` level).

**Issue: State is reset to initial value unexpectedly.**

Solution: SwiftUI resets `@State` when the view's **identity** changes (not just when the struct is re-created). Check if a parent is conditionally recreating the view with `if/else` or changing `id()` — both reset `@State`. Use `@StateObject` or persist state to a store if it must survive identity changes.

**Issue: `@Published` property changes from a background thread cause purple warnings.**

Solution: `@Published` changes must happen on the main thread because they trigger UI updates. Mark the ViewModel class `@MainActor` and `await` results from background tasks before assigning to `@Published` properties.

## 7. Related Topics

- [SwiftUI View Lifecycle](swiftui-view-lifecycle.md) — how state changes trigger view re-evaluation
- [MVVM & Coordinator](mvvm-coordinator.md) — ObservableObject as the ViewModel in SwiftUI MVVM
- [Actors](../03-concurrency/actors.md) — @MainActor for safe ObservableObject updates on main thread
