# Core Animation

## 1. Overview

Core Animation is the compositing and animation engine that powers every pixel on screen in iOS. Every `UIView` is backed by a `CALayer` — the actual rendering primitive. Core Animation runs entirely on the GPU via the render server process (separate from your app), which means smooth 60/120fps animations even while your app's CPU is busy. Understanding Core Animation means understanding the layer tree, the rendering pipeline (layout → display → prepare → commit), implicit vs explicit animations, the presentation vs model layer distinction, and the performance traps: off-screen rendering, excessive compositing, and rasterisation. This knowledge is essential for diagnosing animation hitches and building custom effects that UIView animation cannot express.

## 2. Simple Explanation

Core Animation is the backstage crew at a theatre. Every prop on stage is a layer (`CALayer`) — it has a position, size, opacity, and appearance. The `UIView` is the stage direction script (logic), but the actual prop (`CALayer`) is what the audience sees. When you animate a view's position, you're not moving the stage script — you're telling the backstage crew to smoothly slide the prop. The crew runs on their own fast track (GPU, render server) so they can keep moving props smoothly even while the director (CPU) is busy with other work. The **presentation layer** is the prop's current position on stage; the **model layer** is where the prop is "supposed to be" in the script.

## 3. Deep iOS Knowledge

### CALayer Hierarchy

```
UIWindow
  └── UIView (view hierarchy)
        │ every UIView has exactly one backing CALayer
        └── CALayer (layer hierarchy — mirrors view hierarchy)
              ├── sublayers
              └── CALayer (view-less layer — add directly for custom rendering)
```

**Animatable CALayer properties**: `position`, `bounds`, `transform`, `opacity`, `backgroundColor`, `cornerRadius`, `borderWidth`, `borderColor`, `shadowOpacity`, `shadowRadius`, `shadowOffset`, `contents` (the rendered image), `contentsRect`, `mask`.

### Model Layer vs Presentation Layer

Every animated property exists in two copies:
- **Model layer** (`layer`): the "true" final value — set immediately on the object.
- **Presentation layer** (`layer.presentation()`): the interpolated, in-flight value visible on screen during animation.

```swift
// During animation, the model layer already has the final value:
view.layer.position     // = final value (100, 200)
view.layer.presentation()?.position  // = current animated position (e.g., 47, 120)
```

**Why this matters for hit-testing**: `UIView.hitTest(_:with:)` uses the model layer — you must hit-test against the presentation layer during animations.

### Implicit Animations

Modifying most `CALayer` properties outside a `UIView.animate` block triggers an **implicit animation** (0.25s, default timing):

```swift
let layer = CALayer()
layer.backgroundColor = UIColor.red.cgColor  // no animation — no transaction open
// But:
CATransaction.begin()
layer.backgroundColor = UIColor.blue.cgColor  // implicit 0.25s animation
CATransaction.commit()
```

**UIView disables implicit animations** for its own properties — `UIView.animate` uses a `CATransaction` with custom duration/curve. If you're animating a view's `layer.position` directly (not through UIView animate), you get implicit animations.

### Explicit Animations (CAAnimation)

**CABasicAnimation**: animates a single keyPath from `fromValue` to `toValue`:

```swift
let animation = CABasicAnimation(keyPath: "position.y")
animation.fromValue = 0
animation.toValue = 300
animation.duration = 0.5
animation.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
animation.fillMode = .forwards      // keep final state after animation ends
animation.isRemovedOnCompletion = false  // don't snap back
layer.add(animation, forKey: "moveDown")
layer.position.y = 300   // update model layer to match final value
```

**CAKeyframeAnimation**: animates through multiple values:

```swift
let wobble = CAKeyframeAnimation(keyPath: "transform.rotation.z")
wobble.values = [-0.1, 0.1, -0.05, 0.05, 0]   // radians
wobble.keyTimes = [0, 0.25, 0.5, 0.75, 1.0]
wobble.duration = 0.5
layer.add(wobble, forKey: "wobble")
```

**CAAnimationGroup**: run multiple animations simultaneously on the same layer:

```swift
let group = CAAnimationGroup()
group.animations = [scaleAnim, fadeAnim]
group.duration = 0.4
layer.add(group, forKey: "appear")
```

**CASpringAnimation**: physics-based spring:

```swift
let spring = CASpringAnimation(keyPath: "position.y")
spring.damping = 10
spring.stiffness = 200
spring.mass = 1
spring.initialVelocity = -500   // pixels/second (negative = upward)
spring.toValue = finalY
spring.duration = spring.settlingDuration
layer.add(spring, forKey: "spring")
```

### CATransaction

`CATransaction` is the implicit group for a set of layer changes. Every modification to an animatable property opens a transaction if one is not already open:

```swift
CATransaction.begin()
CATransaction.setAnimationDuration(1.0)
CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(name: .easeOut))
CATransaction.setCompletionBlock { print("Done") }
layer.opacity = 0.0
layer.position.x += 100
CATransaction.commit()
```

`CATransaction.setDisableActions(true)` disables all implicit animations within the transaction — useful when updating layer properties in response to data changes that should not animate.

### Rendering Pipeline

```
1. Layout    — setNeedsLayout → layoutSubviews → update layer geometry
2. Display   — setNeedsDisplay → draw(_:) → rasterise content into layer backing store
3. Prepare   — Core Animation prepares layer tree for render server
4. Commit    — layer tree is serialised and sent to render server (GPU)
```

Frame budget: 16.67ms for 60fps, 8.33ms for 120fps (ProMotion). Steps 1–3 run on the CPU; step 4 runs on the GPU via the render server.

### Off-Screen Rendering

Off-screen rendering forces the GPU to create a temporary buffer for a layer before compositing it into the final frame. This breaks the normal render pipeline and can cause frame drops.

**Triggers**:
- `layer.masksToBounds = true` with rounded corners
- `layer.mask` property set
- `layer.shadowOpacity > 0` without `shadowPath`
- `layer.shouldRasterize = true` (intentional)
- `layer.allowsGroupOpacity = true` with sub-layer opacity

**Fixes**:
- Provide explicit `layer.shadowPath` (a CGPath) to eliminate shadow off-screen rendering.
- Use `layer.cornerCurve = .continuous` with `layer.maskedCorners` and GPU-native rounding.
- Pre-rasterise static complex layers with `layer.shouldRasterize = true` + `layer.rasterizationScale = UIScreen.main.scale`.

### Rasterisation

`shouldRasterize = true` caches the rendered layer as a bitmap. Read subsequent frames from the cache (fast) instead of re-compositing. Use for layers that are expensive to composite but change rarely. Do NOT use for layers that animate frequently — the cache is invalidated on every change, adding overhead.

## 4. Practical Usage

```swift
import UIKit

// ── Custom animated button ────────────────────────────────────
class PulseButton: UIButton {
    private let pulseLayer = CALayer()

    override init(frame: CGRect) {
        super.init(frame: frame)
        setupPulse()
    }

    required init?(coder: NSCoder) { super.init(coder: coder); setupPulse() }

    private func setupPulse() {
        pulseLayer.borderColor = tintColor.cgColor
        pulseLayer.borderWidth = 2
        pulseLayer.opacity = 0
        layer.insertSublayer(pulseLayer, below: layer)
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        pulseLayer.bounds = bounds
        pulseLayer.position = CGPoint(x: bounds.midX, y: bounds.midY)
        pulseLayer.cornerRadius = bounds.height / 2
    }

    func pulse() {
        pulseLayer.removeAllAnimations()

        let scale = CABasicAnimation(keyPath: "transform.scale")
        scale.fromValue = 1.0
        scale.toValue = 1.5

        let fade = CABasicAnimation(keyPath: "opacity")
        fade.fromValue = 0.8
        fade.toValue = 0.0

        let group = CAAnimationGroup()
        group.animations = [scale, fade]
        group.duration = 0.6
        group.timingFunction = CAMediaTimingFunction(name: .easeOut)

        pulseLayer.add(group, forKey: "pulse")
    }
}

// ── Card flip transition ──────────────────────────────────────
func flipCard(from front: UIView, to back: UIView, in container: UIView) {
    let transition = CATransition()
    transition.duration = 0.4
    transition.type = .push
    transition.subtype = .fromRight
    transition.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)

    // Or use 3D flip:
    let flip = CABasicAnimation(keyPath: "transform")
    var identity = CATransform3DIdentity
    identity.m34 = -1.0 / 500   // perspective
    flip.fromValue = CATransform3DRotate(identity, 0, 0, 1, 0)
    flip.toValue = CATransform3DRotate(identity, .pi, 0, 1, 0)
    flip.duration = 0.3

    container.layer.add(flip, forKey: "flip")
    front.isHidden = true
    back.isHidden = false
}

// ── Eliminating shadow off-screen rendering ──────────────────
class ShadowCardView: UIView {
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupShadow()
    }
    required init?(coder: NSCoder) { super.init(coder: coder); setupShadow() }

    private func setupShadow() {
        layer.shadowColor   = UIColor.black.cgColor
        layer.shadowOpacity = 0.25
        layer.shadowRadius  = 8
        layer.shadowOffset  = CGSize(width: 0, height: 4)
        // DO NOT set layer.masksToBounds = true here — it clips the shadow
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        // Explicit shadowPath avoids off-screen rendering
        layer.shadowPath = UIBezierPath(roundedRect: bounds, cornerRadius: 12).cgPath
    }
}

// ── CADisplayLink for frame-precise animation ─────────────────
class CounterAnimator {
    private var displayLink: CADisplayLink?
    private var startTime: CFTimeInterval = 0
    private var duration: CFTimeInterval = 1.5
    private var startValue: Double = 0
    private var endValue: Double = 0
    var onUpdate: ((Double) -> Void)?

    func animate(from start: Double, to end: Double, duration: CFTimeInterval = 1.5) {
        self.startValue = start
        self.endValue = end
        self.duration = duration
        displayLink?.invalidate()
        displayLink = CADisplayLink(target: self, selector: #selector(step))
        displayLink?.add(to: .main, forMode: .common)
        startTime = 0   // set on first step
    }

    @objc private func step(_ link: CADisplayLink) {
        if startTime == 0 { startTime = link.timestamp }
        let elapsed = link.timestamp - startTime
        let progress = min(elapsed / duration, 1.0)
        let eased = 1 - pow(1 - progress, 3)   // ease-out cubic
        onUpdate?(startValue + (endValue - startValue) * eased)
        if progress >= 1.0 { displayLink?.invalidate() }
    }
}

// ── Disable implicit animations during data updates ───────────
func updateLayerWithoutAnimation(_ layer: CALayer) {
    CATransaction.begin()
    CATransaction.setDisableActions(true)   // no implicit animation
    layer.position = CGPoint(x: 100, y: 200)
    layer.backgroundColor = UIColor.blue.cgColor
    CATransaction.commit()
}

// ── Hit-testing during animation ──────────────────────────────
extension UIView {
    override open func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        // Use presentation layer for hit test during animation
        guard let presentationLayer = layer.presentation() else {
            return super.hitTest(point, with: event)
        }
        let presentationPoint = convert(point, to: superview)
        if presentationLayer.frame.contains(presentationPoint) {
            return self
        }
        return nil
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the relationship between UIView and CALayer?**

A: Every `UIView` has exactly one backing `CALayer` (accessed via `view.layer`). The view provides the responder chain (touch handling, gesture recognisers), Auto Layout integration, accessibility, and higher-level animation conveniences. The layer performs the actual rendering and compositing. When you set `view.backgroundColor = .red`, you're really setting `view.layer.backgroundColor`. When you call `UIView.animate`, the framework creates a `CAAnimation` on the underlying layer. Views that need custom drawing override `draw(_:)`, which draws into the layer's backing store. You can add additional sub-layers directly (`view.layer.addSublayer(someLayer)`) for effects that have no UIView counterpart — particle systems, gradient layers, shape layers, etc.

**Q: What is the difference between the model layer and the presentation layer?**

A: When you set an animatable property like `layer.opacity = 0`, the model layer is immediately updated to the final value. But the animation shown on screen is interpolated from the previous value to the new one. The **presentation layer** (`layer.presentation()`) holds the currently-displayed, interpolated value at any given frame during the animation. This distinction matters for: (1) **Hit-testing during animation** — `hitTest` uses model layer coordinates, so tapping an animating view may register as missing. Use the presentation layer's frame for correct hit detection. (2) **Stopping and snapping** — if you remove an animation, the layer snaps to the model value; to stop smoothly at the current visual position, read from the presentation layer and apply to the model layer before removing the animation.

### Hard

**Q: Why does adding a shadow to a rounded UIView cause off-screen rendering and how do you fix it?**

A: A rounded view requires `masksToBounds = true` to clip subviews. A shadow requires the layer to be composited with transparency (the shadow is drawn outside the bounds). These two requirements are contradictory — you cannot clip to bounds AND draw a shadow that extends beyond bounds. Core Animation resolves this by rendering both separately in off-screen buffers and compositing them, causing off-screen rendering. Fixes: (1) Separate the shadow and the rounded content into two layers: an outer `UIView` with only shadow properties (no `masksToBounds`) and an inner `UIView` with `masksToBounds = true` and corner radius. (2) Provide an explicit `layer.shadowPath = UIBezierPath(roundedRect: bounds, cornerRadius: radius).cgPath` — this tells Core Animation the exact shadow shape without requiring off-screen compositing. (3) For views with solid (non-transparent) backgrounds, the shadow is drawn from the shadowPath directly and clipping isn't needed.

**Q: What is `CADisplayLink` and when should you use it instead of `UIView.animate`?**

A: `CADisplayLink` is a timer that fires once per screen refresh (60Hz/120Hz), synchronised to the display's vsync. Use it for: (1) **Physics-based or procedural animation** where the next frame depends on the current frame (particle systems, spring simulation, game loops). (2) **Frame-precise custom drawing** that must be tied to the display refresh rate. (3) **Animating non-animatable properties** like `UILabel.text` (a number counter). For standard property animations (position, opacity, scale), `UIView.animate` (which creates `CAAnimation`) is more efficient because the interpolation runs on the render server process, not in your app. A `CADisplayLink` that does heavy work in its callback blocks the main thread and can cause dropped frames if not carefully bounded.

### Expert

**Q: Describe the Core Animation rendering pipeline and what happens when you call `setNeedsDisplay()` on a layer.**

A: The render pipeline per frame: (1) **Layout** — `layoutSubviews` resolves Auto Layout, sets `frame`/`bounds`/`position`. (2) **Display** — `setNeedsDisplay()` marks the layer as needing its backing store redrawn. `CALayer.display()` is called; for `UIView`-backed layers, this calls `draw(_:)` with a `CGContext`. The result is rastered into a bitmap (`IOSurface`). (3) **Prepare** — Core Animation assembles the layer tree into an encoded description of compositing operations. (4) **Commit** — the encoded layer tree is sent via IPC to the render server (a separate system process). The render server uses the GPU to composite all layers into the final frame buffer. Steps 1–3 run in your app process on the main thread (except async layers). Step 4 is the IPC commit — if the layer tree is complex or the commit is large, this step can exceed the frame budget. `setNeedsDisplay()` triggers a full re-rasterisation of the layer — expensive for large views. Prefer property animations (position, opacity, transform) which require no re-rasterisation over forcing `draw(_:)` redraws for visual changes.

## 6. Common Issues & Solutions

**Issue: Animation completes but the view snaps back to its original position.**

Solution: The `CAAnimation` modifies the presentation layer but not the model layer. When the animation finishes and is removed, the model layer value is shown — which is the original value. Fix: (1) Set the final model layer value before or after adding the animation: `layer.position = finalPosition`. (2) Set `animation.fillMode = .forwards` and `animation.isRemovedOnCompletion = false` to freeze at the final frame — but this leaves the presentation layer out of sync with the model layer, causing hit-testing issues. Option 1 is correct.

**Issue: Animations stutter or drop frames when the list is scrolling.**

Solution: The main thread is overloaded. Profile with Instruments (Time Profiler + Core Animation template). Common causes: expensive `draw(_:)` implementations triggered by cell reuse, off-screen rendering (use Color Off-screen Rendered in Simulator), complex view hierarchies forcing compositing, or un-batched CATransaction commits during scrolling. Fix: move non-UI work off the main thread, provide explicit `shadowPath`, eliminate `masksToBounds` on scroll views, and use `CALayer` for custom rendering instead of overriding `draw(_:)`.

**Issue: `layer.cornerRadius` + `layer.masksToBounds` causes visual artifacts during rotation.**

Solution: During device rotation, the layer is resized. If `masksToBounds = true` clips subviews to a rounded rect, the transition may show a square-to-round transition artifact. Use `UIView.animate(withDuration: UIApplication.shared.statusBarOrientationAnimationDuration)` to animate layout changes, and ensure `layoutSubviews` updates the `shadowPath` (for shadow views) on every bounds change.

## 7. Related Topics

- [UIView Lifecycle](../04-ui-frameworks/uiview-lifecycle.md) — rendering pipeline, off-screen rendering, layer-backed views
- [AVFoundation](avfoundation.md) — `AVPlayerLayer` and `AVCaptureVideoPreviewLayer` are CALayer subclasses
- [UITableView & UICollectionView](../04-ui-frameworks/uitableview-uicollectionview.md) — scroll performance depends on layer compositing cost
- [Event Handling & RunLoop](../04-ui-frameworks/event-handling-runloop.md) — CADisplayLink runs on the RunLoop; affects main thread budget
