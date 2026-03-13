# UI Support

## 1. Overview

UI support accessibility extends beyond VoiceOver to cover visual and motion accommodations that affect all users — not just those using assistive technology. The three major areas are: **Dynamic Type** (user-configurable text size — apps must scale all text and adapt layouts to accommodate sizes from `xSmall` to `accessibilityExtraExtraExtraLarge`), **Colour Contrast** (sufficient luminance difference between foreground text and background — WCAG 2.1 AA requires 4.5:1 for normal text, 3:1 for large text), and **Reduce Motion** (replacing parallax effects and cross-dissolve animations with simpler transitions for users who experience motion sickness or vestibular disorders). Supporting these features makes apps usable for elderly users, users in bright sunlight (contrast), and the ~8% of males who have colour blindness. They are also required for WCAG 2.1 AA compliance.

## 2. Simple Explanation

**Dynamic Type** is the phone's font size dial. Some users set it to the minimum (they prefer dense information); elderly users or those with low vision set it to the maximum (three times the default). An app that ignores this dial always shows the same font size — the elderly user has to squint at tiny text. **Colour contrast** is the difference between text and background brightness. Black text on white is maximum contrast; grey text on white may look elegant but is nearly invisible in sunlight or for someone with low vision. **Reduce Motion** is for users who get motion sickness from parallax or zooming animations. When it's on, the parallax wallpaper effect disappears and transitions become cross-fades — apps should do the same with their animations.

## 3. Deep iOS Knowledge

### Dynamic Type

**UIKit**: use `UIFont.preferredFont(forTextStyle:)` for all text. Text styles map to semantic roles:

| Style | Approx pt (default) | Use |
|-------|--------------------|----|
| `.largeTitle` | 34 | Page titles |
| `.title1` | 28 | Section headers |
| `.title2` | 22 | Sub-section headers |
| `.headline` | 17 (semibold) | Item titles |
| `.body` | 17 | Body text |
| `.callout` | 16 | Secondary body |
| `.subheadline` | 15 | Supporting text |
| `.footnote` | 13 | Caption text |
| `.caption1` | 12 | Timestamps, metadata |
| `.caption2` | 11 | Fine print |

**SwiftUI**: `Font.body`, `Font.headline`, etc. automatically scale with Dynamic Type. Custom fonts need `@ScaledMetric` or `.dynamicTypeSize` environment.

**Responding to size changes in UIKit**:

```swift
// UILabel: set adjustsFontForContentSizeCategory = true
label.font = UIFont.preferredFont(forTextStyle: .body)
label.adjustsFontForContentSizeCategory = true
label.numberOfLines = 0   // allow wrapping at large sizes
```

**Custom fonts with Dynamic Type** (UIKit):

```swift
let descriptor = UIFontDescriptor.preferredFontDescriptor(withTextStyle: .body)
let pointSize = descriptor.pointSize
let customFont = UIFont(name: "Merriweather-Regular", size: pointSize)!
label.font = UIFontMetrics(forTextStyle: .body).scaledFont(for: customFont)
label.adjustsFontForContentSizeCategory = true
```

**Large Content Viewer**: for elements that can't scale (tab bar icons, navigation bar items), iOS shows a large tooltip when the user long-presses with accessibility text sizes. Enable:

```swift
tabBarItem.largeContentTitle = "Home"
tabBarItem.largeContentImage = UIImage(systemName: "house")
view.showsLargeContentViewer = true
```

### Colour Contrast

**WCAG 2.1 AA requirements:**
- Normal text (< 18pt regular / < 14pt bold): contrast ratio ≥ **4.5:1**
- Large text (≥ 18pt regular / ≥ 14pt bold): contrast ratio ≥ **3:1**
- Non-text UI (icons, borders): contrast ratio ≥ **3:1**

Contrast ratio = (L1 + 0.05) / (L2 + 0.05) where L1 is the lighter luminance and L2 is the darker.

**Tools**: Xcode Accessibility Inspector → Audit includes contrast checks. Online: WebAIM Contrast Checker. Figma plugins: "Contrast" or "A11y - Colour Contrast Checker".

**Colour blindness**: don't use colour alone to convey information. Add icons, patterns, or text labels alongside colour:

```swift
// Bad: only colour indicates status
statusView.backgroundColor = isOnline ? .green : .red

// Good: colour + icon + text
statusView.backgroundColor = isOnline ? .systemGreen : .systemRed
statusIcon.image = UIImage(systemName: isOnline ? "wifi" : "wifi.slash")
statusLabel.text = isOnline ? "Online" : "Offline"
```

Use **semantic colours** (`UIColor.label`, `UIColor.secondaryLabel`, `UIColor.systemBackground`) — they automatically adapt to Dark Mode and maintain contrast in both modes. Custom colours need separate `light` and `dark` variants in the asset catalog.

### Reduce Motion

`UIAccessibility.isReduceMotionEnabled` is `true` when the user has enabled Settings → Accessibility → Motion → Reduce Motion. Observe changes:

```swift
NotificationCenter.default.addObserver(
    self,
    selector: #selector(motionPreferenceChanged),
    name: UIAccessibility.reduceMotionStatusDidChangeNotification,
    object: nil
)
```

Replace expensive animations with simpler ones:

```swift
// In SwiftUI: withAnimation respects Reduce Motion automatically for standard transitions
// For custom animations:
func animateTransition(to newView: UIView) {
    if UIAccessibility.isReduceMotionEnabled {
        // Simple alpha crossfade instead of slide/scale
        UIView.animate(withDuration: 0.2) {
            self.currentView.alpha = 0
            newView.alpha = 1
        }
    } else {
        // Full slide animation
        slideTransition(to: newView)
    }
}
```

**Prefer Cross-Dissolve**: iOS's `.transitionCrossDissolve` option in `UIView.transition(with:)` is the recommended reduce-motion alternative to slides and scales.

### Differentiate Without Colour

Setting → Accessibility → Display & Text Size → Differentiate Without Colour. Check:

```swift
UIAccessibility.shouldDifferentiateWithoutColor
```

Add a shape or text label to anything currently communicated purely by colour.

## 4. Practical Usage

```swift
import UIKit
import SwiftUI

// ── UIKit: Dynamic Type label ─────────────────────────────────
final class ArticleCell: UITableViewCell {
    private let titleLabel: UILabel = {
        let label = UILabel()
        label.font = UIFont.preferredFont(forTextStyle: .headline)
        label.adjustsFontForContentSizeCategory = true   // scales with user setting
        label.numberOfLines = 0   // wraps at large sizes
        return label
    }()

    private let bodyLabel: UILabel = {
        let label = UILabel()
        label.font = UIFont.preferredFont(forTextStyle: .body)
        label.adjustsFontForContentSizeCategory = true
        label.numberOfLines = 0
        label.textColor = .secondaryLabel   // semantic colour — adapts to dark mode
        return label
    }()
}

// ── Custom font with Dynamic Type scaling ─────────────────────
extension UIFont {
    static func branded(textStyle: UIFont.TextStyle) -> UIFont {
        let baseFont = UIFont(name: "Merriweather-Regular",
                              size: UIFont.preferredFont(forTextStyle: textStyle).pointSize)
                    ?? UIFont.preferredFont(forTextStyle: textStyle)
        return UIFontMetrics(forTextStyle: textStyle).scaledFont(for: baseFont)
    }
}

// ── SwiftUI: Dynamic Type ─────────────────────────────────────
struct ArticleRowView: View {
    let article: Article

    // @ScaledMetric scales a numeric value with Dynamic Type size
    @ScaledMetric(relativeTo: .body) private var avatarSize: CGFloat = 44

    var body: some View {
        HStack(spacing: 12) {
            AsyncImage(url: article.authorAvatarURL) { image in image.resizable() } placeholder: { Color.gray }
                .frame(width: avatarSize, height: avatarSize)   // scales with text size
                .clipShape(Circle())

            VStack(alignment: .leading, spacing: 4) {
                Text(article.title)
                    .font(.headline)   // automatically scales
                    .lineLimit(2)
                Text(article.author)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// ── Reduce Motion ─────────────────────────────────────────────
struct AnimatedCard: View {
    @State private var isExpanded = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack {
            CardContent(isExpanded: isExpanded)
        }
        .onTapGesture {
            withAnimation(reduceMotion ? .none : .spring(response: 0.4, dampingFraction: 0.7)) {
                isExpanded.toggle()
            }
        }
    }
}

// UIKit: checking reduce motion and differentiateWithoutColor
final class StatusBadge: UIView {

    var status: ConnectionStatus = .online {
        didSet { updateAppearance() }
    }

    private let label = UILabel()
    private let iconView = UIImageView()

    private func updateAppearance() {
        let isOnline = status == .online

        // ── Colour ─────────────────────────────────────────────
        backgroundColor = isOnline ? .systemGreen : .systemRed

        // ── Shape/icon for colour-blind users ──────────────────
        if UIAccessibility.shouldDifferentiateWithoutColor {
            iconView.image = UIImage(systemName: isOnline ? "checkmark.circle.fill" : "xmark.circle.fill")
            iconView.isHidden = false
        } else {
            iconView.isHidden = true
        }

        // ── Text label ─────────────────────────────────────────
        label.text = isOnline ? "Online" : "Offline"

        // ── Accessibility ──────────────────────────────────────
        accessibilityLabel = isOnline ? "Connection status: online" : "Connection status: offline"
    }
}

enum ConnectionStatus { case online, offline }
struct Article { let title: String; let author: String; let authorAvatarURL: URL? }
struct CardContent: View { let isExpanded: Bool; var body: some View { Text("Card") } }
```

## 5. Interview Questions & Answers

### Basic

**Q: What is Dynamic Type and how do you support it in UIKit?**

A: Dynamic Type is iOS's user-configurable text size system. Users adjust it in Settings → Accessibility → Display & Text Size → Larger Text. Sizes range from `xSmall` (for dense UIs) to `accessibilityExtraExtraExtraLarge` (for users with significant vision impairment — text can be 3–5× the default size). To support it in UIKit: (1) Use `UIFont.preferredFont(forTextStyle: .body)` (and other text styles) instead of fixed point sizes like `UIFont.systemFont(ofSize: 17)`. `preferredFont` returns a font at the size appropriate for the user's current Dynamic Type setting. (2) Set `label.adjustsFontForContentSizeCategory = true` — this ensures the label re-queries `preferredFont` when the user changes the setting without relaunching the app. (3) Set `label.numberOfLines = 0` — text must wrap at accessibility sizes; fixed single-line labels will be truncated. (4) Test with Settings → Accessibility → Larger Text at the maximum value.

**Q: What is the minimum colour contrast ratio required by WCAG 2.1 AA and why does it matter?**

A: WCAG 2.1 AA requires a **4.5:1 contrast ratio** for normal text (below 18pt regular or 14pt bold) and **3:1** for large text. The contrast ratio measures the luminance difference between foreground and background: 21:1 is black on white (maximum); 1:1 is no contrast (invisible). Low contrast text fails users with low vision, cataracts, or those viewing the phone in bright sunlight. Grey text on a white card (`#888888` on `#FFFFFF`) is a common design choice that fails the 4.5:1 threshold at a ratio of about 3.9:1. In practice: use semantic colours (`UIColor.label`, `.secondaryLabel`) which are designed to meet contrast requirements in both light and dark mode. Test custom colour combinations with Accessibility Inspector's audit or the WebAIM contrast checker.

### Hard

**Q: How do you support Dynamic Type for a custom font without breaking the design at accessibility sizes?**

A: Use `UIFontMetrics` to scale the custom font proportionally with the system text styles: `UIFontMetrics(forTextStyle: .body).scaledFont(for: customFont)`. This preserves the custom typeface while scaling the point size identically to the system `.body` style. Set `adjustsFontForContentSizeCategory = true` on all labels. For layouts: use Auto Layout constraints rather than fixed heights — set a `minimumHeight` constraint instead of an `equalHeight`. Allow vertical scrolling in containers that previously had fixed heights. For UI elements that cannot scale (tab bar icons, navigation bar items), enable the **Large Content Viewer** — set `showsLargeContentViewer = true` and `largeContentTitle`/`largeContentImage` on the item. Test at every Dynamic Type size using the Simulator's "Accessibility" settings or Xcode's Accessibility Inspector category size selector.

**Q: How do you handle `UIAccessibility.isReduceMotionEnabled` in a complex animated transition?**

A: Check the flag before constructing the animation and provide an alternative: use `UIView.transition(with:duration:options:animations:)` with `.transitionCrossDissolve` instead of custom slide/scale animations. For SwiftUI, read `@Environment(\.accessibilityReduceMotion)` and pass `.none` to `withAnimation()` or use a simple `.opacity` animation. For `CAAnimation`-based transitions (used in Core Animation): skip the `CABasicAnimation` on transform and instead use `CATransaction.setAnimationDuration(0)` with direct property changes. Also register for `UIAccessibility.reduceMotionStatusDidChangeNotification` to respond dynamically if the user enables the setting while the app is running — stop any in-progress animations and use the simpler alternatives going forward. In a design system, centralise this check: `func preferredAnimation() -> Animation? { UIAccessibility.isReduceMotionEnabled ? .none : .spring() }`.

### Expert

**Q: Design a Dynamic Type layout strategy for a complex card-based feed where cards contain images, multiple text sizes, and interactive elements.**

A: Four-layer strategy: (1) **Vertical-first layout**: all card content stacks vertically using `UIStackView(axis: .vertical)` with `spacing = 8`. Never use fixed heights on any text container. Images use a `heightAnchor.constraint(equalTo: widthAnchor, multiplier: 0.6)` (aspect ratio) rather than a fixed height — they scale with card width but maintain proportion. (2) **Text style hierarchy**: title → `.headline`, author → `.subheadline`, body preview → `.callout`, timestamp → `.caption1`. All UILabels have `adjustsFontForContentSizeCategory = true` and `numberOfLines = 0` except the title (which clips at 2 lines to maintain feed density). (3) **Accessibility size breakpoints**: at `UIContentSizeCategory.accessibilityMedium` and above, switch from a side-by-side (image left, text right) to a stacked (image top, text below) layout. Detect: `traitCollection.preferredContentSizeCategory.isAccessibilityCategory`. Implement in `traitCollectionDidChange`. (4) **Large Content Viewer for action buttons**: "Like" and "Share" buttons use `UIImageView`-only icons that cannot scale beyond 24pt without layout breakage. Enable the Large Content Viewer on the button: `button.showsLargeContentViewer = true; button.largeContentTitle = "Like"; button.largeContentImage = UIImage(systemName: "heart")`. Test all four axes: minimum size, maximum standard size, minimum accessibility size, maximum accessibility size.

## 6. Common Issues & Solutions

**Issue: Text is truncated at large Dynamic Type sizes.**

Solution: The label has a fixed height constraint or `numberOfLines = 1`. Remove the fixed height constraint (or change it to `greaterThanOrEqualTo`). Set `numberOfLines = 0`. If the container also needs a minimum height for visual balance, add `heightAnchor.constraint(greaterThanOrEqualToConstant: 60)`. Let Auto Layout calculate the natural height from content.

**Issue: Custom colours look fine in light mode but have poor contrast in dark mode.**

Solution: Replace hardcoded `UIColor(red:green:blue:)` with semantic colours (`UIColor.label`, `.secondaryLabel`, `.tertiaryLabel`) where possible. For custom brand colours, create a Colour Set in Assets.xcassets with separate "Any Appearance" and "Dark" variants. Test both modes using Xcode's environment overrides (bottom toolbar of the canvas in Storyboard, or Edit Scheme → Options → Appearance).

## 7. Related Topics

- [Core Accessibility](core-accessibility.md) — VoiceOver labels and traits
- [Testing Accessibility](testing-accessibility.md) — Accessibility Inspector contrast audit
- [UIView Lifecycle](../04-ui-frameworks/uiview-lifecycle.md) — `layoutSubviews` and `traitCollectionDidChange` for adaptive layouts
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — `@Environment` for accessibility properties
