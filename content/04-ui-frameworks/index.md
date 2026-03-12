# UI Frameworks

## Overview

iOS provides two UI frameworks: **UIKit** (2008, imperative, event-driven) and **SwiftUI** (2019, declarative, state-driven). UIKit remains the foundation of most production apps; SwiftUI is the strategic future. Senior iOS engineers must understand both deeply — their lifecycles, rendering pipelines, layout systems, and the architecture patterns that connect UI to business logic.

This section covers every layer: view and view-controller lifecycles, event delivery via the responder chain, Auto Layout's constraint solver, high-performance list views, SwiftUI's state management model, SwiftUI's diffing algorithm, and the MVVM + Coordinator patterns used in real apps.

## Topics in This Section

- [UIView Lifecycle](uiview-lifecycle.md) — init, layoutSubviews, draw, Core Animation commit transaction, off-screen rendering
- [UIViewController Lifecycle](uiviewcontroller-lifecycle.md) — viewDidLoad → viewWillAppear → viewDidAppear → disappear → deinit, container VCs, presentation
- [Event Handling & RunLoop](event-handling-runloop.md) — hit-testing, responder chain, UIEvent pipeline, RunLoop modes and sources
- [Auto Layout](autolayout.md) — Cassowary constraint solver, intrinsic content size, hugging/compression priorities, layout passes
- [UITableView & UICollectionView](uitableview-uicollectionview.md) — reuse queues, diffable data source, compositional layout, prefetching
- [SwiftUI State Management](swiftui-state-management.md) — @State, @Binding, @ObservedObject, @StateObject, @EnvironmentObject
- [SwiftUI View Lifecycle](swiftui-view-lifecycle.md) — view identity, diffing, body re-evaluation, onAppear, task(_:), onChange
- [MVVM & Coordinator](mvvm-coordinator.md) — ViewModel + binding, ObservableObject, Coordinator navigation pattern

## UIKit vs SwiftUI — Comparison Table

| Dimension | UIKit | SwiftUI |
|-----------|-------|---------|
| Paradigm | Imperative | Declarative |
| First release | iOS 2 (2008) | iOS 13 (2019) |
| View base type | `UIView` (class) | `View` (protocol/struct) |
| Layout system | Auto Layout / manual frames | implicit layout + modifiers |
| State | Manual mutation + delegate/callback | Property wrappers (@State etc.) |
| Animations | `UIView.animate`, Core Animation | `.animation()`, `withAnimation` |
| Navigation | `UINavigationController`, `present()` | `NavigationStack`, `sheet()` |
| Testing | XCTest + snapshot tests | Preview + XCTest |
| Interop | `UIViewRepresentable` / `UIHostingController` | — |
| Platform breadth | iOS / tvOS | iOS / macOS / watchOS / tvOS / visionOS |
| Maturity | Very high | Growing |

## Concept Map

```
UI Frameworks
│
├── UIKit
│   ├── UIView Lifecycle       → init → layoutSubviews → draw → removeFromSuperview
│   ├── UIViewController       → viewDidLoad → appear/disappear cycle
│   ├── Event Handling         → hit-test → responder chain → UIEvent
│   ├── Auto Layout            → constraints → Cassowary → layout passes
│   └── UITableView/Collection → reuse queue → diffable data source
│
└── SwiftUI
    ├── State Management       → @State / @Binding / @StateObject / @EnvironmentObject
    └── View Lifecycle         → identity → diff → body → onAppear / task
│
Architecture
    └── MVVM + Coordinator     → ViewModel / ObservableObject / navigation
```

## Relationship to Other Sections

- **Concurrency**: All UI updates must run on the main thread; `@MainActor` enforces this — see [Actors](../03-concurrency/actors.md).
- **Concurrency**: `task(_:)` modifier uses async/await — see [async/await](../03-concurrency/async-await.md).
- **Memory Management**: Delegate and closure patterns in UIKit create retain cycles — see [Retain Cycles](../02-memory-management/retain-cycles.md).
