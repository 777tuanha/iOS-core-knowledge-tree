# SwiftUI View Lifecycle

## 1. Overview

SwiftUI views are **value types** (structs), not objects with an identity. SwiftUI manages their lifecycle through a **diffing algorithm** that compares successive view descriptions and applies only the changes that differ. Understanding how SwiftUI identifies views (structural vs explicit identity), when `body` is re-evaluated, and when lifecycle modifiers (`onAppear`, `onDisappear`, `task`, `onChange`) fire is essential for building correct, performant SwiftUI apps.

## 2. Simple Explanation

Think of SwiftUI rendering like a theatre director staging a play. Each time the script (state) changes, the director gets a new description of the ideal stage. They don't rebuild the entire stage — they compare the new description to the current stage, identify what changed (new actor, different costume, moved prop), and apply only those minimal changes. `onAppear` is the moment an actor walks onto the stage. `onDisappear` is when they walk off. `task` is a stage hand who starts work when the actor enters and automatically stops when they leave.

## 3. Deep iOS Knowledge

### View Identity

SwiftUI needs to know whether a view in the new description is the **same view** as one in the previous description (update it) or a **new view** (create it, reset state). Two kinds of identity:

**Structural identity**: Determined by the view's **type and position** in the view hierarchy. A `Text` at position [0] inside a `VStack` with no branching has stable structural identity across renders.

**Explicit identity**: Assigned with the `.id(_:)` modifier. SwiftUI treats the view as a new instance whenever the `id` value changes — resetting all `@State` and firing `onAppear` again.

```swift
ProfileView(userID: userID)
    .id(userID)   // changing userID resets all @State in ProfileView
```

### Structural Identity and if/else Branches

When both branches of an `if/else` produce the same type, SwiftUI reuses the existing view (same structural position + type):

```swift
if showLong {
    Text("Long description of the feature")
} else {
    Text("Short")    // both are Text at the same position — SwiftUI updates, not recreates
}
```

When branches produce different types, SwiftUI destroys one and creates the other:

```swift
if isAuthenticated {
    DashboardView()  // different type from LoginView — state is reset on switch
} else {
    LoginView()
}
```

### Body Re-evaluation

`body` is re-evaluated when:
1. A `@State` property on the view changes.
2. An `@ObservedObject` / `@StateObject`'s `@Published` property changes.
3. An `@EnvironmentObject` changes.
4. A parent re-evaluates and passes new inputs to this view's initialiser.

Creating a `View` struct is cheap — it's just a value-type description. The expensive work happens when SwiftUI commits changes. SwiftUI skips diffing subtrees that did not change; views conforming to `Equatable` can use `.equatable()` to opt out of updates when equal.

### Diffing Algorithm

SwiftUI diffs view descriptions based on **type + structural position**. For `ForEach` / `List`, it uses the provided identifier (`Identifiable` or explicit `.id`) to match items across renders. Matched items are updated, unmatched items removed, new items created — analogous to a virtual DOM diff.

### onAppear / onDisappear

`onAppear` fires when the view becomes part of the rendered hierarchy. `onDisappear` fires when it leaves. Unlike UIKit's `viewWillAppear`/`viewDidDisappear`, these are per-view modifiers and fire for individual views, not containers:

```swift
Text("Hello")
    .onAppear { startAnimation() }
    .onDisappear { stopAnimation() }
```

**Important**: `onAppear` fires synchronously during the render pass. Do not perform slow work there — kick off async work with `task(_:)` instead.

### task(_:)

`task(_:)` is the preferred way to run async work tied to a view's lifetime:

- Task **starts** when the view appears (like `onAppear`).
- Task is **automatically cancelled** when the view disappears.
- Cancellation propagates via Swift structured concurrency.
- `task(id:)` takes an `Equatable` value — the task is cancelled and restarted whenever the ID changes.

```swift
.task(id: userID) {    // cancelled and restarted when userID changes
    await loadProfile(for: userID)
}
```

This replaces the common UIKit pattern of starting a task in `viewWillAppear` and cancelling in `viewWillDisappear`.

### onChange

`onChange(of:perform:)` fires a side-effect closure after a value changes and the view re-renders:

```swift
.onChange(of: searchText) { newValue in
    performSearch(newValue)
}
```

iOS 17+ provides both old and new values: `.onChange(of: value) { oldValue, newValue in }`.

`onChange` is for **side effects** only — do not modify state directly inside it (causes a second re-render cycle). Use it for analytics, external API calls, or driving non-SwiftUI systems.

### View Lifetime vs Object Lifetime

| | Lifetime |
|--|---------|
| View struct instance | Ephemeral — new instance every `body` evaluation |
| `@State` storage | Lives as long as view identity is stable in the tree |
| `@StateObject` | Lives as long as view identity is stable in the tree |
| `@ObservedObject` reference | Determined by the owner (typically longer) |

### Lazy Containers and State

Views inside `LazyVStack`, `LazyHStack`, `List`, and lazy grids are **created** when they scroll into view and **destroyed** when they scroll off-screen. Consequently:
- `onAppear` / `onDisappear` fire on every scroll in/out.
- `@State` inside a lazy cell is **reset** each time the cell is recreated.

Store per-item state in the parent's model (e.g., `@StateObject` or a dictionary in the parent's state) — not in `@State` inside lazy cell views.

## 4. Practical Usage

```swift
import SwiftUI

// ── task(_:) for async data loading with auto-cancellation ─────
struct UserProfileView: View {
    let userID: String
    @State private var profile: UserProfile?
    @State private var isLoading = false

    var body: some View {
        Group {
            if isLoading {
                ProgressView()
            } else if let profile {
                ProfileContent(profile: profile)
            }
        }
        .task(id: userID) {                 // cancels previous task when userID changes
            isLoading = true
            defer { isLoading = false }
            profile = try? await fetchUser(id: userID)
        }
    }
}

// ── Explicit identity to reset state on demand ────────────────
struct QuizView: View {
    @State private var questionIndex = 0
    let questions: [String]

    var body: some View {
        VStack {
            QuestionView(question: questions[questionIndex])
                .id(questionIndex)          // .id() resets @State inside when questionIndex changes

            Button("Next") {
                if questionIndex < questions.count - 1 {
                    questionIndex += 1
                }
            }
        }
    }
}

struct QuestionView: View {
    let question: String
    @State private var selectedAnswer: Int?   // reset each time .id() changes parent's id

    var body: some View {
        VStack {
            Text(question)
            ForEach(0..<4, id: \.self) { index in
                Button("Option \(index + 1)") { selectedAnswer = index }
                    .foregroundStyle(selectedAnswer == index ? .blue : .primary)
            }
        }
    }
}

// ── onChange for search / debouncing ──────────────────────────
struct SearchView: View {
    @State private var query = ""
    @State private var results: [String] = []

    var body: some View {
        VStack {
            TextField("Search", text: $query)
                .onChange(of: query) { newQuery in  // fires on every keystroke
                    Task { results = await search(newQuery) }
                }
            List(results, id: \.self) { Text($0) }
        }
    }
}

// ── Equatable view to avoid expensive body re-evaluations ──────
struct StatRow: View, Equatable {
    let label: String
    let value: String

    // Conform to Equatable; wrap in .equatable() at call site
    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.label == rhs.label && lhs.value == rhs.value
    }

    var body: some View {
        HStack {
            Text(label)
            Spacer()
            Text(value).foregroundStyle(.secondary)
        }
    }
}

// Usage: StatRow(label: "Speed", value: "72 mph").equatable()

// ── onAppear / onDisappear for lightweight side effects ────────
struct AnimatedBadge: View {
    @State private var isVisible = false

    var body: some View {
        Image(systemName: "star.fill")
            .scaleEffect(isVisible ? 1.0 : 0.5)
            .opacity(isVisible ? 1.0 : 0)
            .onAppear {
                withAnimation(.spring(response: 0.4)) {
                    isVisible = true        // animate in
                }
            }
            .onDisappear {
                isVisible = false           // reset for next appearance
            }
    }
}

// ── Lazy container — keep state in parent, not in cell ─────────
struct FeedView: View {
    // Per-post like state in the parent model — not inside the lazy cell
    @State private var likedPostIDs: Set<UUID> = []
    let posts: [Post]

    var body: some View {
        ScrollView {
            LazyVStack {
                ForEach(posts) { post in
                    PostRow(
                        post: post,
                        isLiked: likedPostIDs.contains(post.id),
                        onLike: { likedPostIDs.insert(post.id) }
                    )
                }
            }
        }
    }
}

struct PostRow: View {
    let post: Post
    let isLiked: Bool
    let onLike: () -> Void
    // NO @State here — cell is recreated on scroll, state would reset

    var body: some View {
        HStack {
            Text(post.title)
            Spacer()
            Button(action: onLike) {
                Image(systemName: isLiked ? "heart.fill" : "heart")
                    .foregroundStyle(isLiked ? .red : .gray)
            }
        }
    }
}

// Stubs
struct UserProfile { var name: String = "" }
struct Post: Identifiable { var id = UUID(); var title: String = "" }
struct ProfileContent: View {
    let profile: UserProfile
    var body: some View { Text(profile.name) }
}
func fetchUser(id: String) async throws -> UserProfile { UserProfile() }
func search(_ query: String) async -> [String] { [] }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `onAppear` and `task(_:)` in SwiftUI?**

A: `onAppear` fires a synchronous closure when the view appears. It should be used only for lightweight, non-async work — starting animations, updating counters, logging. `task(_:)` fires an async closure when the view appears and automatically **cancels** the task when the view disappears. It integrates with Swift structured concurrency, so cancellation propagates via `CancellationError`. For any data loading or async work tied to a view's visibility, `task(_:)` is the correct choice because it ensures resources are released when the view is no longer visible — something you would have to do manually with `onAppear` + `onDisappear`.

**Q: What is view identity and why does it matter?**

A: View identity determines whether SwiftUI considers a view in the new render to be the same view as in the previous render (and updates it) or a new view (and resets it). Structural identity is based on type + position in the view tree. Explicit identity is assigned via `.id(_:)`. Identity matters because `@State` storage and `@StateObject` instances are tied to a view's identity — when identity changes, all local state is reset. This is both a feature (use `.id()` to force a reset) and a potential bug (accidentally changing identity with `if/else` type branches loses state).

### Hard

**Q: Why does changing from `if condition { ViewA() }` to `if condition { ViewA() } else { ViewB() }` affect state retention?**

A: In the first form with no `else`, `ViewA` is conditionally present/absent. When `condition` toggles, `ViewA` is inserted or removed — `@State` is reset each time it appears. In the `if/else` form with two different types, SwiftUI uses structural type identity: `ViewA` and `ViewB` occupy the same position but have different types, so SwiftUI destroys one and creates the other when `condition` changes — also resetting state. If both branches produce the same type (e.g., both are `Text`), SwiftUI reuses the existing view and updates its content, preserving any `@State` that happens to exist. Use `.id()` to force reset even with same-type branches, or avoid `@State` in branching views and lift state to the parent.

**Q: How does `task(id:)` differ from `task(_:)` and when would you use it?**

A: `task(_:)` starts once when the view appears and cancels when it disappears. `task(id:)` additionally **cancels and restarts** the task whenever the `id` value changes — while the view is still on screen. This is ideal for views that display different data based on an external value: for example, a profile view driven by a `userID` parameter. Without `task(id:)`, you would need to combine `task(_:)` with `onChange(of: userID)` and manually cancel/restart the previous task. `task(id:)` handles this automatically and correctly.

### Expert

**Q: Describe the SwiftUI rendering pipeline from state change to pixel on screen.**

A: (1) A state change (`@State`, `@Published`) triggers the SwiftUI attribute graph to mark dependent views as invalid. (2) SwiftUI schedules a render pass (tied to the display's vsync via `CADisplayLink`). (3) During the render pass, SwiftUI calls `body` on invalidated views, producing a new view description tree. (4) SwiftUI diffs the new tree against the previous tree using structural/explicit identity. (5) For changed nodes, SwiftUI updates the corresponding `UIView`/`CALayer` in the underlying UIKit layer (SwiftUI renders to `_UIHostingView` which wraps a `UIView`). (6) Updated `CALayer` properties are committed in a Core Animation transaction. (7) The render server composites the layer tree to a frame buffer. (8) The frame buffer is displayed at the next vsync. The key insight: SwiftUI view structs are cheap value descriptions; the expensive rendering work is deferred to the CA commit and the render server, same as UIKit.

## 6. Common Issues & Solutions

**Issue: `@State` is reset unexpectedly when navigating back and forth.**

Solution: The view's identity changed. Common cause: the view is being recreated with a different structural type (e.g., wrapped in an `if/else` that changes types) or an `.id()` modifier is changing value. Use the SwiftUI Instruments template or `_printChanges()` (debugging helper) to identify which state is triggering the re-creation.

**Issue: `onAppear` fires multiple times for the same view.**

Solution: Expected behaviour for lazy containers (`LazyVStack`, `List`) — `onAppear` fires each time the view scrolls into the viewport. If you want one-time initialisation, use `task(_:)` combined with a guard on whether data is already loaded, or lift the initialisation to a `@StateObject` whose `init` runs only once.

**Issue: `task(_:)` does not cancel when the view is dismissed.**

Solution: Check that the async function inside `task` responds to cancellation — either by calling a throwing async API (which throws `CancellationError`) or by checking `Task.isCancelled` periodically. If the function runs a tight loop without suspension points or cancellation checks, it will run to completion regardless of the task being cancelled.

**Issue: `onChange` fires with the initial value on first render.**

Solution: `onChange` fires only when the value **changes** after the view appears — not on initial render. If you need to react to the initial value, also use `onAppear` or `task(_:)`.

## 7. Related Topics

- [SwiftUI State Management](swiftui-state-management.md) — state wrappers that trigger body re-evaluation
- [UIViewController Lifecycle](uiviewcontroller-lifecycle.md) — UIKit equivalent lifecycle methods
- [async/await](../03-concurrency/async-await.md) — Swift async model used by task(_:)
