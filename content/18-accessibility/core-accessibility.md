# Core Accessibility

## 1. Overview

Core accessibility on iOS is built around the **UIAccessibility informal protocol** — a set of properties and methods on `UIView` and `UIAccessibilityElement` that describe elements to assistive technologies. VoiceOver, the iOS screen reader, traverses the accessibility tree (a flattened view of the UI) and reads each element's `accessibilityLabel`, then optionally its `accessibilityValue` and `accessibilityHint`. It uses `accessibilityTraits` to determine the element's role (button, image, header, link) and state (selected, enabled, adjustable). Getting these properties right requires understanding how VoiceOver constructs its reading for each element and how it navigates through the accessibility tree. The goal: every interactive element must have a meaningful label, the correct traits, and a logical reading order without requiring any element to be visible on screen.

## 2. Simple Explanation

VoiceOver is a blind user's eyes — it reads the screen aloud as the user swipes through elements. For VoiceOver to say something useful, every element must have a label that describes its purpose. An icon-only button (a trash icon) is silent to VoiceOver unless you give it `accessibilityLabel = "Delete"`. Traits tell VoiceOver the element's nature: "this is a button" (it can be double-tapped), "this is an image" (it's decorative), "this is a header" (it marks a section). The reading order is determined by the element's position on screen — elements are read left-to-right, top-to-bottom unless you override with a custom order. If your UI has custom interaction (a star rating by swiping), you must implement `accessibilityIncrement`/`Decrement` so VoiceOver can drive it with the same gestures.

## 3. Deep iOS Knowledge

### accessibilityLabel

The primary text VoiceOver reads for an element. Rules:
- **Don't include the element type** — VoiceOver appends the trait automatically ("Submit, button").
- **Be concise but meaningful** — "Delete" not "Delete message item".
- **Localise** — always use `NSLocalizedString`.
- **UILabel and UIButton** synthesise `accessibilityLabel` from their `text`/`title` — only override when the synthesised label is wrong.
- **UIImageView** has no synthesised label — always set `accessibilityLabel` for meaningful images; set `isAccessibilityElement = false` for decorative images.

```swift
// UIKit
trashButton.accessibilityLabel = NSLocalizedString("Delete post", comment: "")

// SwiftUI
Button(action: delete) { Image(systemName: "trash") }
    .accessibilityLabel("Delete post")
```

### accessibilityTraits

A bitmask describing the element's role and state. The most important:

| Trait | Use |
|-------|-----|
| `.button` | Tappable element that triggers an action |
| `.link` | Opens a URL or navigates |
| `.header` | Section heading (VoiceOver navigation via Headings rotor) |
| `.image` | A visual image |
| `.selected` | The element is currently selected (tab, radio button) |
| `.notEnabled` | The element is disabled and cannot be interacted with |
| `.adjustable` | Can be adjusted via VoiceOver swipe up/down (sliders, pickers) |
| `.staticText` | Plain non-interactive text |
| `.updatesFrequently` | The value changes often (timer, stock price) |
| `.playsSound` | Playing this element makes a sound |

```swift
// UIKit — combine multiple traits
ratingControl.accessibilityTraits = [.adjustable, .button]

// SwiftUI
Text("Top Stories")
    .accessibilityAddTraits(.isHeader)

Toggle("Dark Mode", isOn: $isDark)
    .accessibilityAddTraits(isDark ? .isSelected : [])
```

### accessibilityValue

Dynamic, current-state information that changes at runtime (as opposed to the static label). Use for: slider position, toggle state, star rating count, progress percentage.

```swift
// For a custom star rating view:
ratingView.accessibilityLabel = "Rating"
ratingView.accessibilityValue = "\(selectedStars) of 5 stars"
ratingView.accessibilityTraits = .adjustable

override func accessibilityIncrement() {
    selectedStars = min(selectedStars + 1, 5)
    accessibilityValue = "\(selectedStars) of 5 stars"
}

override func accessibilityDecrement() {
    selectedStars = max(selectedStars - 1, 0)
    accessibilityValue = "\(selectedStars) of 5 stars"
}
```

### accessibilityHint

Optional supplementary context, spoken after a brief pause following the label. Use sparingly — it adds verbosity. Only add when the action is non-obvious.

```swift
deleteButton.accessibilityHint = NSLocalizedString("Double tap to permanently delete this post.", comment: "")
// VoiceOver reads: "Delete post. Button. Double tap to permanently delete this post."
```

### Grouping Elements

If a cell contains an image, a title, and a subtitle that are logically one element, VoiceOver should read them as a group — not three separate swipes.

```swift
// UIKit — container becomes the accessible element
cell.isAccessibilityElement = true
cell.accessibilityLabel = "\(post.title), by \(post.author)"
// All subviews are ignored by VoiceOver; the cell itself is the element
```

For containers with multiple distinct interactive elements (like a card with a "Like" button and a "Share" button), set `accessibilityElements` to define the order:

```swift
// Explicit VoiceOver reading order
cell.isAccessibilityElement = false
cell.accessibilityElements = [titleLabel, likeButton, shareButton]
```

### Custom Actions

For elements with secondary actions (swipe to delete, long-press to share), expose them as `UIAccessibilityCustomAction`:

```swift
cell.accessibilityCustomActions = [
    UIAccessibilityCustomAction(
        name: NSLocalizedString("Delete", comment: ""),
        target: self,
        selector: #selector(deletePost)
    ),
    UIAccessibilityCustomAction(
        name: NSLocalizedString("Share", comment: ""),
        target: self,
        selector: #selector(sharePost)
    )
]
// VoiceOver: user swipes up/down to cycle through custom actions
```

### Modal Accessibility

When presenting a modal, post `.screenChanged` to move VoiceOver focus to the new content:

```swift
UIAccessibility.post(notification: .screenChanged, argument: modalViewController.view)
// VoiceOver: announces the modal and moves focus to its first element

// On dismiss:
UIAccessibility.post(notification: .screenChanged, argument: triggerButton)
// VoiceOver: moves focus back to the button that opened the modal
```

## 4. Practical Usage

```swift
import UIKit
import SwiftUI

// ── UIKit: Fully accessible post cell ────────────────────────
final class PostCell: UITableViewCell {
    private let titleLabel = UILabel()
    private let authorLabel = UILabel()
    private let timestampLabel = UILabel()
    private let likeButton = UIButton()
    private let shareButton = UIButton()

    func configure(with post: Post) {
        titleLabel.text = post.title
        authorLabel.text = post.author
        timestampLabel.text = post.relativeDate

        // ── Merge title + author + date into one accessible element ──
        isAccessibilityElement = false   // container is not the element
        accessibilityElements = [cellSummaryElement(), likeButton, shareButton]

        // ── Like button ───────────────────────────────────────────
        likeButton.accessibilityLabel = post.isLiked
            ? NSLocalizedString("Unlike post", comment: "")
            : NSLocalizedString("Like post", comment: "")
        likeButton.accessibilityTraits = post.isLiked ? [.button, .selected] : .button
        likeButton.accessibilityValue = "\(post.likeCount) likes"

        // ── Share button ──────────────────────────────────────────
        shareButton.accessibilityLabel = NSLocalizedString("Share post", comment: "")

        // ── Swipe-to-delete via custom action ─────────────────────
        accessibilityCustomActions = [
            UIAccessibilityCustomAction(
                name: NSLocalizedString("Delete", comment: ""),
                target: self, selector: #selector(handleDelete)
            )
        ]
    }

    // Virtual element grouping title + author + date
    private func cellSummaryElement() -> UIAccessibilityElement {
        let element = UIAccessibilityElement(accessibilityContainer: self)
        element.accessibilityLabel = "\(titleLabel.text ?? ""), by \(authorLabel.text ?? "")"
        element.accessibilityValue = timestampLabel.text
        element.accessibilityFrameInContainerSpace = titleLabel.frame.union(authorLabel.frame).union(timestampLabel.frame)
        return element
    }

    @objc private func handleDelete() -> Bool {
        // Notify delegate to delete
        return true   // return true = action succeeded
    }
}

// ── SwiftUI: Accessible rating view ──────────────────────────
struct StarRatingView: View {
    @Binding var rating: Int
    let maxRating: Int = 5

    var body: some View {
        HStack(spacing: 4) {
            ForEach(1...maxRating, id: \.self) { star in
                Image(systemName: star <= rating ? "star.fill" : "star")
                    .foregroundStyle(star <= rating ? Color.yellow : Color.gray)
            }
        }
        // Group the HStack as one accessible, adjustable element
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Rating")
        .accessibilityValue("\(rating) of \(maxRating) stars")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: rating = min(rating + 1, maxRating)
            case .decrement: rating = max(rating - 1, 0)
            @unknown default: break
            }
        }
    }
}

// ── Posting accessibility notifications ──────────────────────
final class FeedViewController: UIViewController {
    private var loadingView: UIView?

    func showLoading() {
        let loading = LoadingSpinnerView()
        view.addSubview(loading)
        loadingView = loading
        UIAccessibility.post(notification: .announcement,
                              argument: NSLocalizedString("Loading feed", comment: ""))
    }

    func hideLoadingAndShowFeed() {
        loadingView?.removeFromSuperview()
        loadingView = nil
        // Move VoiceOver focus to the first post
        UIAccessibility.post(notification: .screenChanged,
                              argument: tableView.visibleCells.first)
    }
}

// Placeholder types:
struct Post { let title: String; let author: String; let relativeDate: String; let isLiked: Bool; let likeCount: Int }
final class LoadingSpinnerView: UIView {}
var tableView = UITableView()
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `accessibilityLabel`, `accessibilityHint`, and `accessibilityValue`?**

A: **`accessibilityLabel`** is the primary description of the element — the static name VoiceOver reads first (e.g., "Delete post"). It should describe the element's purpose, not its type (VoiceOver appends the trait — "button" — automatically). **`accessibilityValue`** is the dynamic, current state that changes at runtime (e.g., "3 of 5 stars" for a rating control, "On" for a toggle). Use it when the meaningful content of the element changes during the session. **`accessibilityHint`** is optional supplementary context, read after a pause, that explains what will happen when the user activates the element (e.g., "Double-tap to permanently delete"). Use hints sparingly — they add verbosity and users can turn them off in VoiceOver settings. The typical VoiceOver reading order is: label → value → traits → hint.

**Q: What is `accessibilityTraits` and which traits are most commonly needed?**

A: `accessibilityTraits` is a bitmask that describes the element's role (what kind of UI element it is) and state (its current condition). The most commonly needed: `.button` — tells VoiceOver the element can be double-tapped to activate (use for any tappable control that isn't a link). `.header` — marks a section heading; VoiceOver users can navigate between headings using the Headings rotor without swiping through every element. `.selected` — indicates the element is currently selected (use on tab bar items, segmented control segments). `.notEnabled` — indicates the element is disabled; VoiceOver reads it but tells the user it can't be interacted with. `.adjustable` — tells VoiceOver this element can be adjusted via swipe-up/swipe-down (use for sliders, star ratings, and custom pickers — pair with `accessibilityIncrement`/`Decrement` method overrides).

### Hard

**Q: How do you make a complex custom control (e.g., a circular progress ring with a label inside) fully accessible?**

A: Four steps: (1) **Identify the semantic unit**: the ring + label together communicate one piece of information (e.g., "Step counter: 7,000 of 10,000 steps, 70%"). This should be one accessible element, not two. (2) **Make the view element**: set `isAccessibilityElement = true` on the container view. Set all child views' `isAccessibilityElement = false`. (3) **Set label and value**: `accessibilityLabel = "Daily steps"`, `accessibilityValue = "7,000 of 10,000 steps, 70% complete"`. (4) **Set traits**: `.image` if it's purely informational; add `.adjustable` if the user can interact with it (e.g., set a goal by rotating). For adjustable: implement `accessibilityIncrement()` and `accessibilityDecrement()` to modify the goal, and update `accessibilityValue` after each change. Announce dynamic value changes using `UIAccessibility.post(notification: .announcement, argument: newValue)` for real-time updates (e.g., as a timer ticks).

**Q: How does VoiceOver reading order work and how do you fix it for a non-standard layout?**

A: VoiceOver's default reading order is geometric — elements are sorted by their `accessibilityFrame` on screen, top-to-bottom, then left-to-right within each row. For most standard layouts this is correct. Problems arise with: (1) **Custom layouts** where elements are positioned out of reading order (e.g., a column header that's visually between two columns it labels). (2) **Container views** where child elements should be read as a group but are ordered differently. (3) **Overlapping frames** where the geometric sort is ambiguous. Fix: implement `accessibilityElements` on the container view (as an `[Any]`) — this completely overrides the geometric sort with your explicit order. Alternatively, use `UIAccessibility.post(notification: .layoutChanged, ...)` after a layout change to force VoiceOver to re-evaluate the order.

### Expert

**Q: Design a fully accessible date picker implemented as a custom UIView (wheel-style) that works with VoiceOver, Switch Control, and Dynamic Type.**

A: Six-component design: (1) **VoiceOver control**: set `accessibilityTraits = .adjustable` on the picker view. Implement `accessibilityIncrement()` (swipe up = next value) and `accessibilityDecrement()` (swipe down = previous value). Set `accessibilityLabel = "Date picker"` and `accessibilityValue = DateFormatter.localizedString(from: selectedDate, dateStyle: .full, timeStyle: .none)`. After each increment/decrement, update `accessibilityValue` and post `UIAccessibility.post(notification: .announcement, argument: accessibilityValue)`. (2) **Switch Control**: the picker must respond to single-switch "next item" scanning. Ensure the picker is a single `isAccessibilityElement = true` element (not exposing its internal scroll subviews). The increment/decrement methods double as the Switch Control activation actions. (3) **Keyboard navigation**: support arrow keys when a hardware keyboard is connected. Override `UIKeyCommand` to handle up/down arrow → increment/decrement. (4) **Dynamic Type**: the label displaying the selected date inside the picker must use `UIFont.preferredFont(forTextStyle: .body)` and respond to `UIContentSizeCategoryDidChangeNotification` to re-layout. The picker's minimum height should increase with larger text sizes — use `systemLayoutSizeFitting` with the current category. (5) **Reduce Motion**: the wheel-scroll animation should be disabled when `UIAccessibility.isReduceMotionEnabled` — switch to a direct value change with no animation. (6) **Testing**: test with VoiceOver enabled and verify the full reading; test with Switch Control in scanning mode; run Accessibility Inspector and check for contrast and label issues.

## 6. Common Issues & Solutions

**Issue: VoiceOver reads "image" for an icon button with no label.**

Solution: The button contains a `UIImageView` but has no `accessibilityLabel`. Set `button.accessibilityLabel = NSLocalizedString("Delete", comment: "")`. Also ensure `button.isAccessibilityElement = true` (true by default for UIButton) and the imageView's `isAccessibilityElement = false` (so VoiceOver doesn't focus both).

**Issue: VoiceOver reads every item in a table cell separately instead of the cell as one unit.**

Solution: Set `cell.isAccessibilityElement = true` and compose a meaningful `cell.accessibilityLabel` from its contents. Set `isAccessibilityElement = false` on all subviews within the cell. If the cell has interactive subviews (like a like button), use `cell.accessibilityElements = [virtualGroupElement, likeButton]` — a virtual element for the content group and the interactive button separately.

**Issue: After dismissing a modal, VoiceOver focus goes to a random element.**

Solution: After dismissing, explicitly set focus: `UIAccessibility.post(notification: .screenChanged, argument: triggerButton)` — this moves VoiceOver focus to the button that originally triggered the modal. Without this, VoiceOver may land on the first element on screen or lose focus entirely.

## 7. Related Topics

- [UI Support](ui-support.md) — Dynamic Type, colour contrast, Reduce Motion
- [Testing Accessibility](testing-accessibility.md) — Accessibility Inspector and VoiceOver workflow
- [UI Testing](../11-testing/ui-testing.md) — `accessibilityIdentifier` vs `accessibilityLabel`
- [SwiftUI View Lifecycle](../04-ui-frameworks/swiftui-view-lifecycle.md) — SwiftUI accessibility modifiers
