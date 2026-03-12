# UIView Lifecycle

## 1. Overview

Every `UIView` goes through a well-defined lifecycle from creation to removal from the hierarchy. Understanding this lifecycle — and the rendering pipeline behind it — is essential for building performant UIs, debugging layout issues, and avoiding common pitfalls like redundant `draw(_:)` calls or unintended off-screen rendering passes.

## 2. Simple Explanation

Think of a UIView like a whiteboard in an office. First it gets built (init). When the office layout changes, someone measures where to put it (layoutSubviews). Then an artist draws on it (draw). If the office reorganises, the whiteboard might be removed (removeFromSuperview). Core Animation is like a professional photographer who takes a snapshot of the final arrangement and sends it to the display — the actual drawing work is batched and happens once per frame.

## 3. Deep iOS Knowledge

### Initialisation

A `UIView` is created either from code (`init(frame:)`) or from a nib/storyboard (`init(coder:)`). During init:
- The `frame` / `bounds` are set.
- `backgroundColor`, `alpha`, and other base properties take defaults.
- Subviews and constraints are **not** yet added — that happens in `layoutSubviews` or `updateConstraints`.

`init(frame:)` and `init(coder:)` are the two designated initialisers. Both must eventually call `super.init`.

### layoutSubviews

Called when the view's bounds change or when `setNeedsLayout()` / `layoutIfNeeded()` is explicitly called. It is the correct place to:
- Manually set subview frames (when not using Auto Layout).
- Perform geometry-dependent operations.

**Never call `layoutSubviews()` directly** — use `setNeedsLayout()` to schedule it, or `layoutIfNeeded()` to force it synchronously. Calling `layoutSubviews()` directly bypasses the layout engine's batching and can cause infinite loops.

### updateConstraints

Called before `layoutSubviews` to allow constraint updates. Override it instead of updating constraints in `layoutSubviews` for better performance:
- Call `setNeedsUpdateConstraints()` to schedule a pass.
- Always call `super.updateConstraints()` **last** (unlike most overrides).

### draw(_:rect:)

Called when the view needs to render its pixel content into the current graphics context. Override only when doing custom Core Graphics drawing. Calling `setNeedsDisplay()` marks the view as dirty and schedules the next `draw(_:)` call on the next run-loop cycle.

**Performance note:** `draw(_:)` is expensive — it renders into a separate bitmap that must then be composited by Core Animation. Prefer using sublayers or standard UIKit controls over custom drawing.

### Hierarchy Management

| Method | Called when |
|--------|-------------|
| `willMove(toSuperview:)` | About to be added to / removed from a superview |
| `didMoveToSuperview()` | After being added or removed |
| `willMove(toWindow:)` | About to move to / from a UIWindow |
| `didMoveToWindow()` | After moving to / from a UIWindow |
| `removeFromSuperview()` | Detaches from parent; triggers layout/display invalidation |

### Core Animation Rendering Pipeline

UIKit views are backed by `CALayer` objects. The rendering pipeline:

1. **Commit transaction**: At the end of each run-loop cycle, Core Animation collects all pending layer changes and packages them into a render transaction.
2. **Render server**: The transaction is serialised and sent to the `backboardd` render server process (out-of-process rendering on iOS).
3. **GPU composition**: The render server composites all layers into a final frame buffer.
4. **Display**: The composed frame is sent to the display at the next vsync (60 or 120 Hz).

UIKit itself runs on the main thread. The render server runs independently, meaning heavy main-thread work can delay the commit transaction, causing dropped frames.

### Off-Screen Rendering

Off-screen rendering occurs when the GPU cannot composite a layer in the normal front-to-back pass — it must render to a separate intermediate texture first. Triggers include:
- `layer.cornerRadius` with `layer.masksToBounds = true` (pre-iOS 13 — iOS 13+ is mostly on-screen)
- `layer.shadowPath` not set (dynamic shadow calculation)
- `layer.mask`
- `layer.shouldRasterize = true` (intentional caching)

Off-screen rendering costs extra GPU memory and time. Detect it with the **Color Off-screen Rendered** option in the Simulator or Instruments. Fixes:
- Set `layer.shadowPath` explicitly instead of letting Core Animation compute it.
- Use `UIBezierPath` clipping in `draw(_:)` rather than `masksToBounds`.
- Set `layer.shouldRasterize = true` on static views to cache the result.

### Rasterisation vs Compositing

| Technique | Use case |
|-----------|----------|
| `shouldRasterize = true` | Cache complex static layer tree as bitmap; amortises cost over frames |
| `drawsAsynchronously = true` | Render in background thread; reduces main-thread load |
| `opaque = true` | Skip alpha blending; use on all solid-colour views |

## 4. Practical Usage

```swift
import UIKit

// ── Custom view demonstrating full lifecycle ────────────────────
class RoundedCardView: UIView {

    private let titleLabel = UILabel()
    private let divider = UIView()

    // MARK: – Init
    override init(frame: CGRect) {
        super.init(frame: frame)
        commonInit()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        commonInit()
    }

    private func commonInit() {
        backgroundColor = .systemBackground
        layer.cornerRadius = 12             // rounded corners
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOpacity = 0.15
        layer.shadowRadius = 8
        // Set shadowPath here to avoid off-screen rendering
        // (will be updated in layoutSubviews when bounds are known)

        titleLabel.font = .preferredFont(forTextStyle: .headline)
        divider.backgroundColor = .separator

        addSubview(titleLabel)
        addSubview(divider)
    }

    // MARK: – Layout
    override func layoutSubviews() {
        super.layoutSubviews()                  // always call super first

        // Manual frame layout (example without Auto Layout)
        let padding: CGFloat = 16
        titleLabel.frame = CGRect(
            x: padding, y: padding,
            width: bounds.width - padding * 2,
            height: 24
        )
        divider.frame = CGRect(
            x: padding, y: titleLabel.frame.maxY + 8,
            width: bounds.width - padding * 2,
            height: 1
        )

        // Update shadow path to match current bounds — avoids off-screen pass
        layer.shadowPath = UIBezierPath(
            roundedRect: bounds, cornerRadius: layer.cornerRadius
        ).cgPath
    }

    // MARK: – Custom drawing (optional — prefer sublayers over draw(_:))
    override func draw(_ rect: CGRect) {
        super.draw(rect)
        // Only override if Core Graphics drawing is truly needed
        // For most cases, use sublayers or UIKit controls instead
    }

    // MARK: – Hierarchy callbacks
    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            // View is now on screen — start animations or timers
        }
    }
}

// ── Triggering layout and display updates ──────────────────────
class ViewController: UIViewController {
    let card = RoundedCardView()

    func updateCardTitle(_ title: String) {
        // setNeedsLayout schedules layoutSubviews on the next run-loop cycle
        card.setNeedsLayout()

        // setNeedsDisplay schedules draw(_:) — only needed for custom drawing
        card.setNeedsDisplay()
    }

    func forceImmediateLayout() {
        // layoutIfNeeded forces layoutSubviews synchronously right now
        card.layoutIfNeeded()
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `setNeedsLayout()` and `layoutIfNeeded()`?**

A: `setNeedsLayout()` marks the view as needing layout and schedules `layoutSubviews()` for the next run-loop cycle — it's asynchronous and batched. `layoutIfNeeded()` forces the layout pass to run **immediately** and synchronously, processing all pending layout changes. `layoutIfNeeded()` is typically called inside a `UIView.animate` block to drive Auto Layout animations: you first update constraints, then call `layoutIfNeeded()` inside the animation closure so that the frame changes are animated.

**Q: When should you override `draw(_:)` vs using sublayers?**

A: Override `draw(_:)` only when you need custom Core Graphics rendering (gradients, paths, text with custom layout). For standard visual effects (rounded corners, borders, shadows) use `CALayer` properties or standard UIKit controls. `draw(_:)` creates a backing store bitmap that consumes memory proportional to pixel dimensions, and the render happens on the CPU. Sublayers and UIKit controls are generally more efficient because they leverage the GPU compositor directly.

### Hard

**Q: Explain the Core Animation commit transaction and why main-thread work can drop frames.**

A: At the end of each main run-loop cycle, Core Animation automatically commits a transaction that packages all pending `CALayer` property changes and sends them to the render server. If the main thread is busy (heavy computation, synchronous I/O) when this commit needs to happen, the transaction is delayed. The render server, running independently, cannot compose the next frame without the committed transaction. When the commit misses the 16.7 ms vsync window (60 Hz) or 8.3 ms (120 Hz), the previous frame is displayed again — a dropped frame. This is why you must keep the main thread free for short, bounded work.

**Q: What causes off-screen rendering and how do you diagnose and fix it?**

A: Off-screen rendering is triggered when the GPU cannot composite a layer in a single front-to-back pass and must render to an intermediate texture. Common triggers: `masksToBounds = true` with `cornerRadius`, unset `shadowPath`, `layer.mask`, and explicit `shouldRasterize`. Diagnose with Instruments' Core Animation template or the Simulator's **Debug → Color Off-screen Rendered** overlay (highlighted in yellow). Fix by setting `layer.shadowPath` explicitly, using `UIBezierPath`-based clipping in `draw(_:)` instead of `masksToBounds`, and setting `shouldRasterize = true` on expensive but static layer trees to cache the off-screen result across frames.

### Expert

**Q: Describe the full path from `UIView.backgroundColor = .red` to a pixel changing on screen.**

A: (1) Setting `backgroundColor` on a `UIView` sets the corresponding `CALayer.backgroundColor` property. (2) Core Animation records this change in the current implicit transaction. (3) At the end of the run-loop cycle, the transaction is committed: layer trees are serialised and sent via IPC to the `backboardd` render server. (4) The render server allocates a frame buffer and composites all layer trees front-to-back using the GPU. (5) At the next vsync signal, the completed frame buffer is displayed. The view's `draw(_:)` is NOT involved — `backgroundColor` is handled entirely at the layer/compositor level. This split between the main-thread model (UIKit) and the out-of-process renderer (backboardd) is why UIKit can remain responsive during GPU-heavy rendering.

## 6. Common Issues & Solutions

**Issue: Calling `layoutSubviews()` directly causes infinite recursion.**

Solution: Never call `layoutSubviews()` directly. Call `setNeedsLayout()` to schedule it, or `layoutIfNeeded()` to force it. Calling it directly bypasses the layout engine's dirty-flag mechanism and can trigger infinite layout loops.

**Issue: Shadow appears flat (no blur) and causes off-screen rendering.**

Solution: Set `layer.shadowPath = UIBezierPath(roundedRect: bounds, cornerRadius: layer.cornerRadius).cgPath` after each layout pass. Without `shadowPath`, Core Animation must examine every pixel of the layer to compute the shadow shape — expensive and off-screen.

**Issue: Custom `draw(_:)` causes high memory usage on retina screens.**

Solution: The backing store for `draw(_:)` is `width × height × scale²` × 4 bytes (RGBA). On a 3× screen, a 300×300 pt view uses ~3.2 MB. If custom drawing is unavoidable, use `setNeedsDisplayInRect:` to only redraw the dirty region, not the entire bounds.

**Issue: Animation blocks do not animate Auto Layout changes.**

Solution: Call `setNeedsLayout()` after changing the constraint constant, then wrap `layoutIfNeeded()` — not `setNeedsLayout()` — inside `UIView.animate(withDuration:)`. The animation block intercepts the frame changes triggered by `layoutIfNeeded()`.

## 7. Related Topics

- [UIViewController Lifecycle](uiviewcontroller-lifecycle.md) — view controller owns and manages UIViews
- [Auto Layout](autolayout.md) — constraint system that drives layoutSubviews
- [Event Handling & RunLoop](event-handling-runloop.md) — RunLoop cycle that triggers layout/display commits
- [UITableView & UICollectionView](uitableview-uicollectionview.md) — cell reuse and layout performance
