# Event Handling & RunLoop

## 1. Overview

iOS translates hardware touch signals into high-level `UIEvent` objects through a layered pipeline: the kernel detects the touch, `IOKit` packages it, `SpringBoard` routes it to the app, and UIKit delivers it to the correct view via **hit-testing** and the **responder chain**. The entire delivery mechanism runs on top of the **RunLoop**, which keeps the main thread alive, drains event queues, and fires timers and display callbacks. Understanding this pipeline is essential for debugging gesture conflicts, building custom controls, and diagnosing dropped frames.

## 2. Simple Explanation

Imagine a post office. When you tap the screen, a letter (UIEvent) is created and addressed. The hit-testing process is like a postal worker finding the exact desk (UIView) where the letter should be delivered. The responder chain is the escalation path — if that desk doesn't handle the letter, it gets passed to the manager (superview), then to the floor manager (UIViewController), and so on up to the building director (UIApplication). The RunLoop is the post office's daily routine: keep checking for mail, deliver it, process it, repeat.

## 3. Deep iOS Knowledge

### Touch Event Pipeline

1. **Hardware / Kernel**: The digitiser detects a finger press. The kernel packages it into an IOKit event.
2. **SpringBoard**: The system process receives the event and determines which app's window should receive it, then forwards via Mach port.
3. **UIApplication**: The event enters `UIApplication.sendEvent(_:)`, the top-level event dispatcher.
4. **Hit-testing**: UIKit determines which view should receive the touch.
5. **Responder Chain**: The event is offered to the hit-tested view; if unhandled, it travels up the chain.

### Hit-Testing

Hit-testing is a depth-first traversal of the view hierarchy to find the deepest view whose `bounds` contain the touch point and whose `isUserInteractionEnabled`, `isHidden`, and `alpha` conditions are satisfied.

```
UIWindow
  └── UIView A
        ├── UIView B  ← deepest view containing touch? → first responder candidate
        └── UIView C
```

`hitTest(_:with:)` is called top-down. The default implementation:
1. Returns `nil` if `isUserInteractionEnabled == false`, `isHidden == true`, or `alpha < 0.01`.
2. Calls `point(inside:with:)` — returns `nil` if touch is outside bounds.
3. Iterates subviews in reverse (front-to-back), recursively calling `hitTest` on each.
4. Returns the first non-nil result (deepest match).

Override `hitTest` to expand the hit area, redirect touches, or implement transparent pass-through views.

### Responder Chain

Every `UIResponder` subclass (`UIView`, `UIViewController`, `UIApplication`, `UIWindowScene`) participates in the responder chain. When a touch is not handled by the first responder, it propagates:

```
UIView (first responder)
  → UIView (superview)
  → UIViewController
  → UIView (superview's superview)
  → UIWindow
  → UIWindowScene
  → UIApplication
  → AppDelegate
  → (discarded if unhandled)
```

Handlers: `touchesBegan`, `touchesMoved`, `touchesEnded`, `touchesCancelled`. Call `super` to forward the event.

### UIGestureRecognizer

Gesture recognisers sit above the raw touch system. A recogniser:
- Receives touches before the target view.
- If it recognises its pattern, it cancels raw touch delivery to the view (`cancelsTouchesInView = true` by default).
- Multiple recognisers on the same view are coordinated by `UIGestureRecognizerDelegate`.

Recogniser states: `.possible` → `.began` → `.changed` → `.ended` / `.failed` / `.cancelled`.

### UIEvent

A `UIEvent` has a `type` (`.touches`, `.motion`, `.remoteControl`, `.presses`) and carries a set of `UITouch` objects. Each `UITouch` tracks the entire lifecycle of one finger from `began` to `ended`. Multitouch is supported by examining all touches in the event's `touches(for:)`.

### RunLoop

The `RunLoop` is an event-processing loop tied to a thread. The main thread's run loop is managed by UIKit. Each iteration:

1. **Input sources** (port-based): Mach port messages — touch events, timers fired.
2. **Run loop sources** (custom): `CFRunLoopSource` — typically used by frameworks.
3. **Observers**: Notified at well-defined points (entry, before waiting, after waiting, exit).
4. **Timers**: `Timer` / `CADisplayLink` — fire when their deadline passes.

#### RunLoop Modes

| Mode | Description |
|------|-------------|
| `.default` | Normal app operation |
| `.tracking` | Active during scroll — prevents timers from firing and disrupting scrolling |
| `.common` | Pseudo-mode — observer/timer is added to all "common" modes (default + tracking) |
| `UIInitializationRunLoopMode` | App launch only |

A `Timer` scheduled in `.default` mode stops firing while the user is scrolling. Schedule it in `.common` to keep it firing during scrolling — or use `GCD`/`async` instead.

#### Core Animation & Display Link

`CADisplayLink` is a special timer synchronised to the display's vsync (60 or 120 Hz). It fires as a run-loop source in `.common` mode. UIKit uses it internally to drive animations. Apps use it for game loops or custom animations that need frame-level timing.

The Core Animation commit transaction (see UIView Lifecycle) is triggered by a run-loop observer that fires just before the run loop goes to sleep — this is why layout, display, and CA commits are all batched to the end of each run-loop cycle.

### RunLoop Sources and Observers

| Concept | Purpose |
|---------|---------|
| `CFRunLoopSource` | Low-level event source (Mach ports, sockets) |
| `CFRunLoopTimer` | Timer-based source — `Timer` and `CADisplayLink` |
| `CFRunLoopObserver` | Notified at run-loop activity transitions |
| `CFRunLoopMode` | Named set of sources/timers/observers |

## 4. Practical Usage

```swift
import UIKit

// ── Expanding touch area beyond view bounds ─────────────────────
class LargeHitAreaButton: UIButton {
    var hitAreaInset: UIEdgeInsets = UIEdgeInsets(top: -20, left: -20, bottom: -20, right: -20)

    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        let expandedBounds = bounds.inset(by: hitAreaInset)  // negative inset = expand
        return expandedBounds.contains(point)
    }
}

// ── Pass-through container view (touches fall through to views below) ──
class PassThroughView: UIView {
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        let result = super.hitTest(point, with: event)
        return result == self ? nil : result    // don't capture touches on self, only subviews
    }
}

// ── Custom responder chain action ──────────────────────────────
// Anywhere in the responder chain, you can receive a custom action
extension UIResponder {
    @objc func handleCustomAction(_ sender: Any?) {
        // default: forward up the chain
    }
}

class CustomView: UIView {
    override func handleCustomAction(_ sender: Any?) {
        print("CustomView handled the action")  // intercept here; don't call super to stop
    }
}

// Send an action up the chain from anywhere
// UIApplication.shared.sendAction(#selector(handleCustomAction(_:)), to: nil, from: self, for: nil)

// ── Gesture recogniser with delegate coordination ──────────────
class SwipeableCardView: UIView, UIGestureRecognizerDelegate {
    private let panGesture = UIPanGestureRecognizer()
    private let tapGesture = UITapGestureRecognizer()

    override init(frame: CGRect) {
        super.init(frame: frame)

        panGesture.addTarget(self, action: #selector(handlePan(_:)))
        panGesture.delegate = self
        addGestureRecognizer(panGesture)

        tapGesture.addTarget(self, action: #selector(handleTap(_:)))
        addGestureRecognizer(tapGesture)

        // Allow both to recognise simultaneously (pan + tap)
        panGesture.require(toFail: tapGesture)  // tap takes precedence for small movements
    }

    required init?(coder: NSCoder) { super.init(coder: coder) }

    @objc private func handlePan(_ gesture: UIPanGestureRecognizer) {
        let translation = gesture.translation(in: self)
        switch gesture.state {
        case .changed:
            transform = CGAffineTransform(translationX: translation.x, y: translation.y)
        case .ended, .cancelled:
            UIView.animate(withDuration: 0.3) { self.transform = .identity }
        default: break
        }
    }

    @objc private func handleTap(_ gesture: UITapGestureRecognizer) {
        UIView.animate(withDuration: 0.1, animations: {
            self.transform = CGAffineTransform(scaleX: 0.95, y: 0.95)
        }) { _ in
            UIView.animate(withDuration: 0.1) { self.transform = .identity }
        }
    }

    // Allow simultaneous recognition
    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool { false }
}

// ── RunLoop mode — timer that fires during scrolling ──────────
class PollingManager {
    private var timer: Timer?

    func startPolling() {
        timer = Timer(timeInterval: 1.0, repeats: true) { _ in
            print("Polling...")
        }
        // Schedule in .common so it fires even while UIScrollView is tracking
        RunLoop.main.add(timer!, forMode: .common)
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
    }
}

// ── CADisplayLink for custom animation loop ────────────────────
class ParticleAnimator {
    private var displayLink: CADisplayLink?
    private var lastTimestamp: CFTimeInterval = 0

    func start(in view: UIView) {
        displayLink = CADisplayLink(target: self, selector: #selector(tick(_:)))
        displayLink?.add(to: .main, forMode: .common)   // fires every vsync
    }

    func stop() {
        displayLink?.invalidate()
        displayLink = nil
    }

    @objc private func tick(_ link: CADisplayLink) {
        let dt = lastTimestamp == 0 ? 0 : link.timestamp - lastTimestamp
        lastTimestamp = link.timestamp
        updateParticles(dt: dt)                         // frame-accurate delta time
    }

    private func updateParticles(dt: CFTimeInterval) { /* physics update */ }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is hit-testing and how does UIKit perform it?**

A: Hit-testing is the process of finding the deepest view in the hierarchy that contains a touch point and is eligible to receive events. UIKit calls `hitTest(_:with:)` on the window, which recursively calls it on subviews in reverse order (front to back). At each level, `point(inside:with:)` checks whether the touch is within bounds. A view is skipped if `isUserInteractionEnabled == false`, `isHidden == true`, or `alpha < 0.01`. The deepest view that passes all checks becomes the first responder for that touch.

**Q: What is the responder chain?**

A: The responder chain is a linked list of `UIResponder` objects through which an unhandled event propagates. Starting from the first responder (usually the hit-tested view), the event is offered to each responder in turn: view → superview → view controller → window → UIApplication → AppDelegate. Each responder can handle the event (stop propagation) or call `super` to pass it along. If no responder handles it, the event is discarded.

### Hard

**Q: Why does a `Timer` stop firing during a UIScrollView scroll, and how do you fix it?**

A: By default, `Timer` is scheduled in the `.default` run loop mode. While `UIScrollView` is tracking a finger, the run loop switches to `.tracking` mode, which excludes `.default` mode sources — so the timer never fires. Fix: schedule the timer in `.common` mode, which is an alias for all "common" modes including both `.default` and `.tracking`. Either use `RunLoop.main.add(timer, forMode: .common)` or switch to `DispatchQueue.main.asyncAfter` / a `Task` with `Task.sleep`, which are not mode-dependent.

**Q: How do gesture recognisers interact with raw touch handling?**

A: Gesture recognisers receive touches before the target view. Once a recogniser transitions to `.began`, it claims the touch and — if `cancelsTouchesInView` is `true` (the default) — sends `touchesCancelled` to the view's raw touch handlers. Multiple recognisers on the same view can be coordinated with `UIGestureRecognizerDelegate`: `shouldRecognizeSimultaneouslyWith` allows both to fire, and `require(toFail:)` creates a dependency so one recogniser only fires if another fails. Recognisers on superview vs subview also interact: `delaysTouchesBegan` prevents raw touches from firing until the recogniser fails.

### Expert

**Q: Describe the relationship between the RunLoop, Core Animation commit transactions, and layout passes.**

A: All three are tied to the main run loop cycle: (1) **Layout**: When `setNeedsLayout()` is called, a dirty flag is set. A run-loop observer registered for the `beforeWaiting` activity (fires just before the run loop sleeps) triggers `layoutSubviews` for all dirty views. (2) **Display**: `setNeedsDisplay()` similarly sets a dirty flag. Another `beforeWaiting` observer triggers `draw(_:)` for dirty views. (3) **Core Animation commit**: A `CATransaction` observer, also registered for `beforeWaiting`, commits the accumulated layer property changes to the render server. This batching is why multiple `setNeedsLayout()` calls within one run-loop cycle result in only one `layoutSubviews` call — it's a deliberate coalescing mechanism. If you call `layoutIfNeeded()` mid-cycle, you bypass the batching and force an immediate pass.

## 6. Common Issues & Solutions

**Issue: Tap gesture not working on a view with `alpha = 0`.**

Solution: Even though the view is visually transparent, `alpha = 0` causes `hitTest` to return `nil` — no events are delivered. Set `alpha = 0.001` or `isHidden = true` if you want the view visible to the hierarchy but not rendered, or use `isUserInteractionEnabled = false` explicitly.

**Issue: Gesture on a child view blocked by a gesture on a parent.**

Solution: Use `UIGestureRecognizerDelegate`'s `shouldRecognizeSimultaneouslyWith` or add a `require(toFail:)` dependency. Also check that the parent's gesture doesn't consume events before the child's recogniser starts.

**Issue: Custom `hitTest` override causes unexpected click areas.**

Solution: Always call `super.hitTest(_:with:)` or replicate its logic fully. A common mistake is forgetting to check `isUserInteractionEnabled`, `isHidden`, and `alpha` before calling `point(inside:with:)`, which can make disabled or hidden views receive touches.

**Issue: `CADisplayLink` causing high CPU usage when app is in background.**

Solution: Call `displayLink.isPaused = true` in `viewDidDisappear` or when the app enters the background (`UIApplication.didEnterBackgroundNotification`). `CADisplayLink` continues firing even when the view is off-screen unless explicitly paused or invalidated.

## 7. Related Topics

- [UIView Lifecycle](uiview-lifecycle.md) — layout/display passes triggered by the run loop
- [UIViewController Lifecycle](uiviewcontroller-lifecycle.md) — VC receives `touches*` callbacks as responder
- [Auto Layout](autolayout.md) — constraint solving runs during the layout pass
