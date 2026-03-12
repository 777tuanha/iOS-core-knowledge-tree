# Auto Layout

## 1. Overview

Auto Layout is UIKit's constraint-based layout system, introduced in iOS 6. Instead of setting frames manually, you describe relationships between views using **constraints** — mathematical equations that the layout engine solves to produce concrete frames. The engine is based on the **Cassowary** linear arithmetic constraint solver. Auto Layout handles the complexity of adapting a single layout to different screen sizes, device orientations, Dynamic Type sizes, and multitasking split sizes.

## 2. Simple Explanation

Think of Auto Layout like furniture assembly instructions written in plain language: "The sofa must be 2 m from the left wall, centred in the room, and its top must be 30 cm below the TV shelf." You don't measure and place the sofa yourself — you hand the instructions to the room and it figures out the exact position based on the room's dimensions. If you move into a bigger apartment, the same instructions still produce sensible furniture placement.

Constraints are those instructions. The layout engine is the room figuring out exact positions.

## 3. Deep iOS Knowledge

### Constraint Anatomy

A constraint is a linear equation:

```
item1.attribute = multiplier × item2.attribute + constant  (with relation ≤, =, ≥)
```

Example: `button.leading = 1.0 × superview.leading + 16`

| Part | Meaning |
|------|---------|
| `item1` | The view being constrained |
| `attribute` | `.leading`, `.trailing`, `.top`, `.bottom`, `.width`, `.height`, `.centerX`, `.centerY`, `.firstBaseline`, `.lastBaseline` |
| `relation` | `.equal`, `.lessThanOrEqual`, `.greaterThanOrEqual` |
| `multiplier` | Scaling factor (1.0 for most) |
| `item2` | The anchor view (can be `nil` for absolute constraints) |
| `constant` | Pixel offset |

### Cassowary Algorithm

UIKit's layout engine implements the Cassowary constraint solver (O(n) for typical UI constraint graphs). Cassowary:
- Represents constraints as a simplex tableau.
- Incrementally updates the solution when a constraint is added, removed, or changed — very efficient for live editing.
- Assigns strengths to constraints (required / high / medium / low) and maximises satisfaction.

Constraint priorities are expressed as `UILayoutPriority` (raw `Float`, 0–1000). Priority 1000 is **required** (must be satisfied; breaks the layout if unsatisfiable). Anything below 1000 is **optional** — the engine tries to satisfy them but won't crash if it can't.

### Intrinsic Content Size

Views that know their natural size (labels, images, buttons) report an `intrinsicContentSize`. The layout engine creates implicit constraints at priority 750 to respect this size. You can override it for custom views:

```swift
override var intrinsicContentSize: CGSize {
    CGSize(width: 100, height: 44)
}
// Call this when content changes:
invalidateIntrinsicContentSize()
```

### Content Hugging and Compression Resistance

| Property | Meaning | Default priority |
|----------|---------|-----------------|
| Content Hugging | Resist growing **beyond** intrinsic size | 250 (horizontal/vertical) |
| Compression Resistance | Resist shrinking **below** intrinsic size | 750 (horizontal/vertical) |

Higher value = stronger resistance. Used to resolve ambiguity when two views compete for space:
- If a label and a text field share a row, increase the label's Hugging priority so the text field expands to fill remaining space.
- If a label might be clipped, increase its Compression Resistance so it doesn't get squished.

### Layout Passes

Three passes happen each run-loop cycle (triggered by run-loop observers):

1. **Update constraints pass** (`updateConstraints`) — views report new constraint constants.
2. **Layout pass** (`layoutSubviews`) — Cassowary solves the constraint system and assigns frames.
3. **Display pass** (`draw(_:)`) — views render their content.

Each pass works bottom-up through the view hierarchy for updates (children update before parents) and top-down for layout.

### Safe Area & Layout Guides

`safeAreaInsets` represents the space consumed by the status bar, home indicator, notch, and Dynamic Island. Use `safeAreaLayoutGuide` to constrain relative to the safe area instead of the window edges.

`layoutMarginsGuide` provides the system-defined content margins (8 pt standard). `readableContentGuide` constrains to a maximum line length for readable text.

```swift
NSLayoutConstraint.activate([
    label.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16)
])
```

### Constraint Debugging

| Tool | Use |
|------|-----|
| `po view.constraintsAffectingLayout(for: .horizontal)` | Print constraints on axis |
| Unsatisfiable constraint log | "Unable to simultaneously satisfy constraints" |
| `UIView.hasAmbiguousLayout()` | Returns true if more solutions exist |
| `exerciseAmbiguityInLayout()` | Randomly chooses among valid solutions for debugging |
| Xcode Canvas constraint warnings | Yellow/red indicators on layout issues |

### Performance

- Constraint solving is O(n) for typical UIs but can become O(n²) or worse with equality chains across many views.
- Avoid modifying constraints unnecessarily on every layout pass.
- Updating a constraint's `constant` (not adding/removing it) is cheap — the solver updates incrementally.
- Use `UIStackView` for common linear layouts — it manages constraints automatically and is efficient.

## 4. Practical Usage

```swift
import UIKit

// ── Programmatic Auto Layout with NSLayoutAnchor ───────────────
class ProfileCardView: UIView {

    private let avatarImageView = UIImageView()
    private let nameLabel = UILabel()
    private let subtitleLabel = UILabel()
    private let followButton = UIButton(type: .system)

    override init(frame: CGRect) {
        super.init(frame: frame)
        setupViews()
        setupConstraints()
    }

    required init?(coder: NSCoder) { super.init(coder: coder) }

    private func setupViews() {
        avatarImageView.contentMode = .scaleAspectFill
        avatarImageView.clipsToBounds = true
        avatarImageView.layer.cornerRadius = 30

        nameLabel.font = .preferredFont(forTextStyle: .headline)
        nameLabel.setContentCompressionResistancePriority(.required, for: .vertical)

        subtitleLabel.font = .preferredFont(forTextStyle: .subheadline)
        subtitleLabel.textColor = .secondaryLabel
        subtitleLabel.numberOfLines = 2

        followButton.setTitle("Follow", for: .normal)
        // Hugging: button resists growing horizontally — label expands instead
        followButton.setContentHuggingPriority(.defaultHigh, for: .horizontal)

        [avatarImageView, nameLabel, subtitleLabel, followButton].forEach {
            $0.translatesAutoresizingMaskIntoConstraints = false  // required for programmatic AL
            addSubview($0)
        }
    }

    private func setupConstraints() {
        NSLayoutConstraint.activate([
            // Avatar: fixed size, pinned to leading + top of safe area margins
            avatarImageView.widthAnchor.constraint(equalToConstant: 60),
            avatarImageView.heightAnchor.constraint(equalToConstant: 60),
            avatarImageView.leadingAnchor.constraint(equalTo: layoutMarginsGuide.leadingAnchor),
            avatarImageView.topAnchor.constraint(equalTo: layoutMarginsGuide.topAnchor),

            // Name: right of avatar
            nameLabel.leadingAnchor.constraint(equalTo: avatarImageView.trailingAnchor, constant: 12),
            nameLabel.topAnchor.constraint(equalTo: avatarImageView.topAnchor),

            // Follow button: right edge, same row as name
            followButton.trailingAnchor.constraint(equalTo: layoutMarginsGuide.trailingAnchor),
            followButton.centerYAnchor.constraint(equalTo: nameLabel.centerYAnchor),
            followButton.leadingAnchor.constraint(
                greaterThanOrEqualTo: nameLabel.trailingAnchor, constant: 8  // ≥ leaves room for both
            ),

            // Subtitle: below name
            subtitleLabel.leadingAnchor.constraint(equalTo: nameLabel.leadingAnchor),
            subtitleLabel.trailingAnchor.constraint(equalTo: layoutMarginsGuide.trailingAnchor),
            subtitleLabel.topAnchor.constraint(equalTo: nameLabel.bottomAnchor, constant: 4),
            subtitleLabel.bottomAnchor.constraint(equalTo: layoutMarginsGuide.bottomAnchor)
        ])
    }
}

// ── Animating a constraint change ─────────────────────────────
class AnimatedPanelViewController: UIViewController {
    private let panel = UIView()
    private var panelBottomConstraint: NSLayoutConstraint!

    override func viewDidLoad() {
        super.viewDidLoad()
        panel.backgroundColor = .systemBackground
        panel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(panel)

        panelBottomConstraint = panel.bottomAnchor.constraint(
            equalTo: view.bottomAnchor, constant: 300   // initially off-screen
        )

        NSLayoutConstraint.activate([
            panel.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            panel.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            panel.heightAnchor.constraint(equalToConstant: 300),
            panelBottomConstraint
        ])
    }

    func showPanel() {
        panelBottomConstraint.constant = 0             // change the constant — cheap
        UIView.animate(withDuration: 0.35, delay: 0, options: .curveEaseOut) {
            self.view.layoutIfNeeded()                  // animate the layout pass
        }
    }

    func hidePanel() {
        panelBottomConstraint.constant = 300
        UIView.animate(withDuration: 0.35) {
            self.view.layoutIfNeeded()
        }
    }
}

// ── UIStackView for simple linear layouts ─────────────────────
func makeInfoStack() -> UIStackView {
    let titleLabel = UILabel()
    let bodyLabel = UILabel()
    let actionButton = UIButton(type: .system)

    titleLabel.font = .preferredFont(forTextStyle: .title2)
    bodyLabel.numberOfLines = 0

    let stack = UIStackView(arrangedSubviews: [titleLabel, bodyLabel, actionButton])
    stack.axis = .vertical
    stack.spacing = 8
    stack.alignment = .leading              // subviews align to leading edge
    stack.distribution = .fill             // subviews fill stack proportionally
    return stack
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between content hugging and compression resistance?**

A: Content Hugging priority determines how strongly a view resists being **stretched beyond** its intrinsic content size. A high value means the view prefers to be exactly as large as its content. Compression Resistance determines how strongly a view resists being **compressed below** its intrinsic content size. A high value means the view prefers not to be clipped. Together they resolve ambiguity when multiple views compete for space in a layout — e.g., in a horizontal stack of a label and a text field, raising the label's Hugging priority makes the text field expand rather than the label.

**Q: Why must `translatesAutoresizingMaskIntoConstraints` be set to `false` for programmatic Auto Layout?**

A: When `translatesAutoresizingMaskIntoConstraints` is `true` (the default), UIKit creates implicit constraints from the view's `autoresizingMask` to preserve its current frame. These implicit constraints conflict with any manual constraints you add, causing "Unable to simultaneously satisfy constraints" errors. Setting it to `false` tells UIKit you are taking full responsibility for the view's layout via Auto Layout constraints.

### Hard

**Q: What is the Cassowary algorithm and why is it used for Auto Layout?**

A: Cassowary is an incremental constraint satisfaction algorithm for linear arithmetic systems. It maintains a simplex tableau and can add, remove, or modify constraints in O(1) amortised time for typical UI constraint graphs — much more efficient than re-solving from scratch each time. It assigns strengths (priorities) to constraints and finds the solution that satisfies all required constraints and maximally satisfies optional ones. UIKit uses it because UI layouts change frequently (orientation, size classes, Dynamic Type), and Cassowary's incremental updates handle these changes efficiently without full re-computation.

**Q: Explain the three layout passes and how they relate to the run loop.**

A: (1) **updateConstraints** — called bottom-up through the view hierarchy; views report constraint changes here. (2) **layoutSubviews** — called top-down; Cassowary solves the constraint system for each view and assigns frames. (3) **draw(_:)** — called top-down; views render their content into graphics contexts. All three are batched by run-loop observers firing at the `beforeWaiting` activity — meaning multiple `setNeedsLayout()` calls in one cycle result in only one `layoutSubviews` call. `layoutIfNeeded()` forces the layout pass immediately, bypassing this batching, which is why it's used inside animation blocks.

### Expert

**Q: How would you debug "Unable to simultaneously satisfy constraints" and what strategies prevent it?**

A: The UISC log in Xcode's console lists the conflicting constraints with view descriptions. Strategy: (1) Give each view a meaningful `accessibilityIdentifier` to make the log readable. (2) Check constraint priorities — lower a non-critical constraint below 1000 to make it breakable. (3) Use `UIView.hasAmbiguousLayout()` and `exerciseAmbiguityInLayout()` in the debugger to detect ambiguous (under-constrained) layouts. Prevention: use `UIStackView` for common patterns (it manages internal constraints), prefer updating `constant` over adding/removing constraints, and design with explicit priority intent — if two constraints might conflict, decide upfront which should break by setting priorities appropriately.

## 6. Common Issues & Solutions

**Issue: "Unable to simultaneously satisfy constraints" at runtime.**

Solution: Read the log carefully — it lists the conflicting constraints. Identify which constraint should be optional and lower its priority below 1000. Add `accessibilityIdentifier` to views for readable logs.

**Issue: Layout looks correct in portrait but breaks in landscape.**

Solution: Check for fixed-width constraints that exceed the landscape width. Use `lessThanOrEqual` or percentage-based widths (`equalTo superview.widthAnchor multiplier: 0.8`). Also verify that `safeAreaLayoutGuide` is used for top/bottom margins to account for home indicator height changes.

**Issue: Label being clipped when text is long.**

Solution: Increase the label's Compression Resistance priority above the competing constraint's priority (usually 750). Alternatively, add a `greaterThanOrEqual` height constraint and remove any fixed height constraint.

**Issue: Auto Layout constraints not applying to a view added programmatically.**

Solution: Forgot to set `translatesAutoresizingMaskIntoConstraints = false`. Every view managed by Auto Layout must have this set to `false` before constraints are activated.

## 7. Related Topics

- [UIView Lifecycle](uiview-lifecycle.md) — layout passes (layoutSubviews) triggered by Auto Layout
- [Event Handling & RunLoop](event-handling-runloop.md) — run-loop cycle that batches layout passes
- [UITableView & UICollectionView](uitableview-uicollectionview.md) — self-sizing cells use intrinsic content size
- [SwiftUI View Lifecycle](swiftui-view-lifecycle.md) — SwiftUI's implicit layout replaces Auto Layout
