# Accessibility (a11y)

## 1. Overview

Accessibility (abbreviated a11y — 11 letters between "a" and "y") is the practice of designing apps that are usable by people with disabilities — visual (blindness, low vision, colour blindness), motor (limited hand mobility), cognitive (dyslexia, memory impairment), and hearing impairments. On iOS, accessibility is built into the OS: VoiceOver (screen reader), Switch Control (single-switch navigation), AssistiveTouch, and Display Accommodations are provided by the system and interact with apps through the **Accessibility API** — a tree of `UIAccessibilityElement` objects with labels, traits, hints, and values. Apps that correctly expose this API work out-of-the-box with all assistive technologies. Accessibility is both a legal requirement in many countries (ADA, WCAG 2.1 AA, European Accessibility Act) and a market opportunity: 15% of the global population has some form of disability. Testing with VoiceOver and Accessibility Inspector is the fastest way to find and fix issues.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Core Accessibility](core-accessibility.md) | VoiceOver, `accessibilityLabel`, `accessibilityTraits`, `accessibilityHint`, `accessibilityValue`, grouping |
| 2 | [UI Support](ui-support.md) | Dynamic Type, colour contrast, Reduce Motion, Large Content Viewer |
| 3 | [Testing Accessibility](testing-accessibility.md) | Accessibility Inspector, VoiceOver testing workflow, XCTest accessibility assertions |

## 3. iOS Accessibility API

```
UIView / UIAccessibilityElement
├── accessibilityLabel      → "Submit order" (what VoiceOver reads)
├── accessibilityHint       → "Double-tap to place your order" (optional context)
├── accessibilityValue      → "3 of 5 stars" (current state)
├── accessibilityTraits     → [.button, .selected, .notEnabled] (role + state)
├── accessibilityIdentifier → "submitOrderButton" (for UI tests only)
└── isAccessibilityElement  → true/false (whether VoiceOver focuses here)

UIAccessibilityContainer protocol
└── accessibilityElements   → ordered array for VoiceOver navigation
```

## 4. Quick Reference

| Issue | Fix |
|-------|-----|
| Icon button has no label | Set `accessibilityLabel` |
| VoiceOver reads raw number instead of meaning | Override `accessibilityValue` |
| VoiceOver reads every child of a container | Set `isAccessibilityElement = true` on container, `false` on children |
| Custom slider has no VoiceOver control | Implement `accessibilityIncrement`/`Decrement` |
| Text too small for elderly users | Support Dynamic Type with `UIFont.preferredFont(forTextStyle:)` |
| Red/green status impossible to distinguish | Add icon/pattern in addition to colour |
| Animation causes motion sickness | Check `UIAccessibility.isReduceMotionEnabled` |

## 5. Related Topics

- [UIView Lifecycle](../04-ui-frameworks/uiview-lifecycle.md) — `layoutSubviews` affects accessibility frame
- [Testing — UI Testing](../11-testing/ui-testing.md) — `accessibilityIdentifier` for XCUITest
- [SwiftUI State Management](../04-ui-frameworks/swiftui-state-management.md) — SwiftUI accessibility modifiers
