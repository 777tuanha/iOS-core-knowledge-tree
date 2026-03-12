# UIViewController Lifecycle

## 1. Overview

`UIViewController` is the fundamental building block of UIKit apps. It manages a view hierarchy, responds to system events, and mediates between views and the app's data model. Every interaction a user has with an iOS app passes through a view controller. Understanding its lifecycle — the sequence of method calls from creation to deallocation — is critical for correctly loading data, configuring views, managing resources, and avoiding memory leaks.

## 2. Simple Explanation

A view controller is like a stage manager in a theatre. When a scene is being prepared (viewDidLoad), they set up all the props. Just before the curtain rises (viewWillAppear), they make final adjustments. When the show starts (viewDidAppear), the audience can see everything. When the curtain falls (viewWillDisappear), they prepare to strike the set. When the scene is fully gone (viewDidDisappear), they clean up. Finally when the production is over (deinit), the stage manager leaves entirely.

## 3. Deep iOS Knowledge

### Complete Lifecycle Sequence

```
init (or initWithCoder:)
  │
  ▼
loadView               ← only if view property is accessed and not set
  │
  ▼
viewDidLoad            ← one-time setup; view is loaded but not sized
  │
  ▼
viewWillAppear         ← view about to become visible; called each time
  │
  ▼
viewWillLayoutSubviews ← just before layoutSubviews on root view
  │
  ▼
viewDidLayoutSubviews  ← just after layoutSubviews; safe to read final frames
  │
  ▼
viewDidAppear          ← view is fully visible and on screen
  │
  ▼         (user navigates away or VC is dismissed)
  │
viewWillDisappear      ← view about to leave screen
  │
  ▼
viewDidDisappear       ← view is off screen; safe to pause/stop
  │
  ▼
deinit                 ← VC is being deallocated; remove observers
```

### loadView

Called lazily the first time `view` is accessed and `view` is `nil`. The default implementation loads a nib or creates a plain `UIView`. Override `loadView` (without calling `super`) only when building the view hierarchy entirely in code — this is where you assign `self.view = myCustomRootView`. Do **not** override `loadView` if using storyboards or nibs.

### viewDidLoad

Called once after the view hierarchy is loaded into memory. This is the correct place for:
- One-time UI configuration (adding subviews, setting up constraints, registering cells).
- Binding to data sources or view models.
- Adding notification observers (balance with removal in `deinit` or `viewDidDisappear`).

**Important:** `viewDidLoad` fires before the view has its final bounds — `view.frame` is not yet reliable here. Frame-dependent setup belongs in `viewDidLayoutSubviews`.

### viewWillAppear / viewDidAppear

`viewWillAppear(_:)` fires each time the view is about to become visible (every push, pop, modal present, tab switch). Use it for:
- Refreshing data that may have changed while the VC was off-screen.
- Starting animations or timers.
- Updating the navigation bar.

`viewDidAppear(_:)` fires after the transition animation completes. Use it to:
- Start expensive operations that should only run when the UI is fully visible.
- Begin video playback or audio sessions.

### viewWillDisappear / viewDidDisappear

`viewWillDisappear(_:)` fires before the transition begins. Use it to:
- Cancel in-flight network requests.
- Save unsaved state.

`viewDidDisappear(_:)` fires after the view is fully off-screen. Use it to:
- Pause media.
- Stop background-unfriendly processes.

**Note:** A VC can appear/disappear many times without being deallocated (e.g., pushing and popping on a nav stack). `viewWillAppear`/`viewDidAppear` are not one-time events.

### deinit

Called when the view controller's reference count reaches zero. Use it to:
- Remove `NotificationCenter` observers (required for iOS < 9; good practice always).
- Invalidate timers.
- Clean up non-ARC resources.

Do **not** access `self.view` in `deinit` — the view may have been released already.

### viewWillLayoutSubviews / viewDidLayoutSubviews

Called around `layoutSubviews` on the root view. `viewDidLayoutSubviews` is the first reliable place to read `view.frame` and `view.bounds` for geometry-dependent setup (e.g., creating a gradient layer that fills the view).

### Container View Controllers

UIKit provides container VCs (`UINavigationController`, `UITabBarController`, `UISplitViewController`, `UIPageViewController`) that manage child VCs. You can also create custom containers using the `addChild(_:)` / `didMove(toParent:)` / `willMove(toParent:)` / `removeFromParent()` APIs.

When a child VC is added, the container calls the child's lifecycle methods at the appropriate times. If you embed a child VC's view without using these APIs, the child will not receive lifecycle callbacks — a common source of bugs.

### Presentation

| Method | Behaviour |
|--------|-----------|
| `present(_:animated:)` | Modally presents over the current context |
| `dismiss(animated:)` | Dismisses the topmost modal |
| `show(_:sender:)` | Adapts to navigation stack (push) or modal depending on context |
| `showDetailViewController(_:sender:)` | For split-view controllers |

`presentingViewController` / `presentedViewController` track the modal stack. A presented VC's lifecycle events (`viewWillAppear` etc.) fire in the same run-loop cycle as the presentation animation.

### Memory Warnings

`didReceiveMemoryWarning()` (deprecated in iOS 23 but still called) / `viewDidUnload()` (removed in iOS 6). Modern apps handle memory warnings by releasing cached data and images in response to `UIApplication.didReceiveMemoryWarningNotification`.

## 4. Practical Usage

```swift
import UIKit

class ProfileViewController: UIViewController {

    // MARK: – Properties
    private let profileView = ProfileView()
    private var viewModel: ProfileViewModel

    private var notificationToken: NSObjectProtocol?

    // MARK: – Init
    init(viewModel: ProfileViewModel) {
        self.viewModel = viewModel
        super.init(nibName: nil, bundle: nil)   // always call super after
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) not supported — use init(viewModel:)")
    }

    // MARK: – loadView (code-only UI)
    override func loadView() {
        view = profileView                      // assign the root view directly
    }

    // MARK: – viewDidLoad — one-time setup
    override func viewDidLoad() {
        super.viewDidLoad()                     // always call super

        title = "Profile"
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            systemItem: .edit,
            primaryAction: UIAction { [weak self] _ in self?.editTapped() }
        )

        // Register for notifications
        notificationToken = NotificationCenter.default.addObserver(
            forName: .profileDidUpdate,
            object: nil,
            queue: .main
        ) { [weak self] _ in                    // [weak self] prevents retain cycle
            self?.refreshProfile()
        }
    }

    // MARK: – viewWillAppear — refresh on each appearance
    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        refreshProfile()                        // data may have changed while away
        navigationController?.setNavigationBarHidden(false, animated: animated)
    }

    // MARK: – viewDidLayoutSubviews — geometry is now final
    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        // Safe to read view.bounds here
        profileView.updateGradientLayer(bounds: view.bounds)
    }

    // MARK: – viewDidAppear — start heavy operations
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        viewModel.startLiveUpdates()            // only when fully on screen
    }

    // MARK: – viewWillDisappear — pause work
    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        viewModel.stopLiveUpdates()
    }

    // MARK: – deinit — final cleanup
    deinit {
        if let token = notificationToken {
            NotificationCenter.default.removeObserver(token)
        }
    }

    // MARK: – Private
    private func refreshProfile() {
        Task { @MainActor in                    // ensure UI updates on main thread
            let profile = await viewModel.fetchProfile()
            profileView.configure(with: profile)
        }
    }

    private func editTapped() { /* ... */ }
}

// ── Adding a child view controller ─────────────────────────────
class DashboardViewController: UIViewController {
    func embedChart() {
        let chartVC = ChartViewController()

        addChild(chartVC)                       // 1. register the relationship
        view.addSubview(chartVC.view)           // 2. add the view
        chartVC.view.frame = CGRect(x: 0, y: 100, width: view.bounds.width, height: 200)
        chartVC.didMove(toParent: self)         // 3. notify the child — triggers lifecycle
    }
}

// Stubs
class ProfileView: UIView {
    func configure(with profile: Any) {}
    func updateGradientLayer(bounds: CGRect) {}
}
struct Profile {}
class ProfileViewModel {
    func fetchProfile() async -> Profile { Profile() }
    func startLiveUpdates() {}
    func stopLiveUpdates() {}
}
class ChartViewController: UIViewController {}
extension Notification.Name {
    static let profileDidUpdate = Notification.Name("profileDidUpdate")
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the correct place to do one-time UI setup, and why not in `viewWillAppear`?**

A: `viewDidLoad` is the correct place because it is called exactly once, after the view hierarchy is loaded into memory. Doing UI setup in `viewWillAppear` would repeat the work every time the view appears — adding subviews multiple times, registering multiple observers, etc. — causing memory leaks and visual glitches. `viewWillAppear` is for work that must be refreshed each time, such as reloading data that could have changed while the VC was off-screen.

**Q: When is `deinit` called on a view controller, and what should you do there?**

A: `deinit` is called when the VC's retain count drops to zero — typically when the last strong reference is released (e.g., it is popped from a navigation stack and no other object holds a reference). Use `deinit` to remove `NotificationCenter` observers (required for observer APIs that don't use block-based registration with a return token), invalidate timers, and clean up non-ARC resources. Do not access `self.view` in `deinit` as the view hierarchy may already be released.

### Hard

**Q: Why might a view controller's `deinit` not be called after being popped from a navigation stack?**

A: A retain cycle. Common causes: (1) A closure stored on a long-lived object captures `self` strongly — e.g., a timer's block, a notification observer, or a `URLSessionDataTask` completion handler that isn't cancelled. (2) A delegate property on a child view or child VC is declared `strong` instead of `weak`, creating a cycle between the VC and its view. (3) The VC is embedded as a child with `addChild` but not properly removed with `removeFromParent`. Diagnose with Instruments' Leaks or Memory Graph Debugger. Fix by using `[weak self]` in closures and `weak var delegate` for delegate properties.

**Q: What is the difference between `present(_:animated:)` and `show(_:sender:)`?**

A: `show(_:sender:)` is an adaptive method — the receiving view controller decides how to display the new VC based on its context. Inside a `UINavigationController`, it pushes. Inside a `UISplitViewController`, it may show in the detail pane. In a plain VC, it falls back to modal presentation. `present(_:animated:)` always presents modally regardless of context. Using `show` is preferred when you want the presentation to adapt to device size class and container, which is important for iPadOS and adaptive layouts.

### Expert

**Q: Describe a container view controller implementation and the lifecycle method calls it triggers.**

A: A custom container uses `addChild(_:)`, adds the child's view, calls `childVC.didMove(toParent: self)`, and removes with `childVC.willMove(toParent: nil)`, `childVC.view.removeFromSuperview()`, `childVC.removeFromParent()`. When a container adds a child, UIKit calls the child's `viewWillAppear` and `viewDidAppear` if the container is already on-screen, or defers them until the container appears. If you add a child's view **without** calling `addChild`, the child receives no lifecycle callbacks — a bug where `viewWillAppear` is never called. For animated transitions between children, use `transition(from:to:duration:options:animations:completion:)` which coordinates lifecycle calls automatically.

## 6. Common Issues & Solutions

**Issue: `view.frame` is wrong in `viewDidLoad`.**

Solution: `viewDidLoad` fires before the view is laid out in its final container. Use `viewDidLayoutSubviews` for any code that depends on `view.frame` or `view.bounds`.

**Issue: View controller is not deallocated after pop — memory leak.**

Solution: Check for retain cycles. Use the Memory Graph Debugger (`Debug → Memory Graph` in Xcode). Look for circular references: VC → closure → VC. Fix with `[weak self]`. Also check that delegates are declared `weak var`.

**Issue: `viewWillAppear` is called but `viewDidAppear` is not.**

Solution: This happens when a modal presentation is interrupted mid-animation (e.g., another present starts). Ensure you handle the `animated` flag correctly and avoid presenting multiple VCs in the same run-loop turn.

**Issue: Child VC's `viewWillAppear` is never called.**

Solution: You added the child's view without calling `addChild(_:)` and `didMove(toParent:)`. Always use the full three-step API: `addChild` → `addSubview` → `didMove`.

## 7. Related Topics

- [UIView Lifecycle](uiview-lifecycle.md) — the view that the VC manages
- [Event Handling & RunLoop](event-handling-runloop.md) — lifecycle callbacks are delivered via the run loop
- [MVVM & Coordinator](mvvm-coordinator.md) — architecture patterns built around VCs
- [Retain Cycles](../02-memory-management/retain-cycles.md) — delegate/closure retain cycles that prevent deinit
