# Property Wrappers

## 1. Overview

Property wrappers (`@propertyWrapper`) add a layer of syntactic sugar over stored properties, encapsulating common patterns like validation, persistence, thread-safe access, and observation in a reusable struct or class. Introduced in Swift 5.1, they are extensively used in SwiftUI (`@State`, `@Binding`, `@EnvironmentObject`) and Combine (`@Published`). Understanding how property wrappers work internally removes the magic and makes debugging them straightforward.

## 2. Simple Explanation

Think of a property wrapper like a smart outlet adapter. You plug in any device (the wrapped value) and the adapter adds behaviour: voltage conversion, surge protection, power metering. The device doesn't know the adapter exists — it just gets power. The room doesn't know what device is plugged in — it just provides an outlet.

Property wrappers work the same way:
- The **wrapped value** is the device — the actual data
- The **wrapper** is the adapter — adds validation, persistence, logging, etc.
- Callers access the property normally; the wrapper's logic runs invisibly

## 3. Deep iOS Knowledge

### Mechanics

Declaring `@SomeWrapper var x: T` is syntactic sugar. The compiler desugars it to:

```swift
var _x: SomeWrapper<T>        // backing storage — the wrapper instance
var x: T {                     // synthetic computed property
    get { _x.wrappedValue }
    set { _x.wrappedValue = newValue }
}
```

The property wrapper type must declare a `wrappedValue` property. The backing storage (`_x`) is accessible with an underscore prefix.

### Projected Value (`$`)

A wrapper can optionally expose a **projected value** via a `projectedValue` property. This is accessed with the `$` prefix:

```swift
@State var count = 0
$count          // Binding<Int> — the projected value
```

The projected value type is arbitrary — it can be a `Binding`, a `Publisher`, a validation result, or anything useful.

### Initialisation

Wrappers can be initialised in three ways:
1. `@Wrapper var x = value` — calls `init(wrappedValue:)`
2. `@Wrapper(arg: ...) var x = value` — calls `init(wrappedValue:arg:)`
3. `@Wrapper(arg: ...) var x` — calls `init(arg:)` — no initial value from the declaration

### Built-in Wrappers in the iOS Ecosystem

| Wrapper | Module | Purpose |
|---------|--------|---------|
| `@State` | SwiftUI | Local view state; triggers re-render on change |
| `@Binding` | SwiftUI | Two-way reference to another view's state |
| `@ObservedObject` | SwiftUI | Observe external `ObservableObject` |
| `@StateObject` | SwiftUI | Owns and observes an `ObservableObject` |
| `@EnvironmentObject` | SwiftUI | Inject from environment; not passed explicitly |
| `@Environment` | SwiftUI | Read environment values (color scheme, locale) |
| `@Published` | Combine | Emits changes via `objectWillChange` |
| `@AppStorage` | SwiftUI | Reads/writes `UserDefaults` |
| `@SceneStorage` | SwiftUI | Per-scene persistent state |

### Composition

Property wrappers can be composed in Swift 5.5+:

```swift
@Trimmed @Lowercased var username: String
```

The outermost wrapper receives the inner wrapper's `wrappedValue` as its own `wrappedValue`. Composition is applied right-to-left (innermost evaluated first).

### Limitations

- Property wrappers cannot be applied to `let` stored properties in some contexts
- Cannot be applied to global variables or local variables in Swift versions before 5.4
- The backing store `_x` is accessible outside the type (a footgun for testing)
- Wrappers add type complexity that can slow compile times

## 4. Practical Usage

```swift
// ── Minimal property wrapper ───────────────────────────────────
@propertyWrapper
struct Clamped<Value: Comparable> {
    private var value: Value
    let range: ClosedRange<Value>

    var wrappedValue: Value {
        get { value }
        set { value = Swift.min(Swift.max(newValue, range.lowerBound), range.upperBound) }
    }

    init(wrappedValue: Value, _ range: ClosedRange<Value>) {
        self.range = range
        self.value = Swift.min(Swift.max(wrappedValue, range.lowerBound), range.upperBound)
    }
}

struct Volume {
    @Clamped(0...100) var level: Int = 50
}

var v = Volume()
v.level = 120
print(v.level)  // 100 — clamped

// ── Projected value ────────────────────────────────────────────
@propertyWrapper
struct Validated<Value> {
    private var value: Value
    private let validator: (Value) -> Bool

    var wrappedValue: Value {
        get { value }
        set { value = newValue }
    }

    var projectedValue: Bool { validator(value) }  // accessible via $

    init(wrappedValue: Value, validator: @escaping (Value) -> Bool) {
        self.value = wrappedValue
        self.validator = validator
    }
}

struct Form {
    @Validated(validator: { !$0.isEmpty }) var email: String = ""
}

var form = Form()
form.email = "user@example.com"
print(form.$email)   // true — projected value is the validation result
form.email = ""
print(form.$email)   // false

// ── @Published internals (conceptual equivalent) ──────────────
@propertyWrapper
class Published<Value> {
    private var value: Value
    // In the real Combine implementation this publishes to objectWillChange
    let publisher = PassthroughSubject<Value, Never>()

    var wrappedValue: Value {
        get { value }
        set {
            value = newValue
            publisher.send(newValue)
        }
    }

    var projectedValue: AnyPublisher<Value, Never> {
        publisher.eraseToAnyPublisher()
    }

    init(wrappedValue: Value) { self.value = wrappedValue }
}

// ── Thread-safe wrapper ────────────────────────────────────────
@propertyWrapper
final class Protected<Value> {
    private var value: Value
    private let lock = NSLock()

    var wrappedValue: Value {
        get { lock.withLock { value } }
        set { lock.withLock { value = newValue } }
    }

    init(wrappedValue: Value) { self.value = wrappedValue }
}

class DataCache {
    @Protected var items: [String: Data] = [:]  // thread-safe read/write
}

// ── UserDefaults persistence ───────────────────────────────────
@propertyWrapper
struct UserDefault<T> {
    let key: String
    let defaultValue: T

    var wrappedValue: T {
        get { UserDefaults.standard.object(forKey: key) as? T ?? defaultValue }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }
}

struct Settings {
    @UserDefault(key: "onboardingShown", defaultValue: false)
    var hasSeenOnboarding: Bool
}

// ── SwiftUI @State and $binding usage ─────────────────────────
import SwiftUI

struct CounterView: View {
    @State private var count = 0    // local state, owned by SwiftUI

    var body: some View {
        Stepper("Count: \(count)", value: $count)  // $count is Binding<Int>
    }
}

import Combine
```

## 5. Interview Questions & Answers

### Basic

**Q: What is a property wrapper and what problem does it solve?**

A: A property wrapper encapsulates repeated get/set logic — validation, persistence, thread safety, observation — in a reusable struct or class decorated with `@propertyWrapper`. Without them, you'd duplicate the same `didSet`/computed property boilerplate everywhere. SwiftUI's `@State` and Combine's `@Published` are the most visible examples.

**Q: What is the difference between `wrappedValue` and `projectedValue`?**

A: `wrappedValue` is the primary storage exposed by the wrapper — accessed using the plain property name. `projectedValue` is an optional secondary value exposed via the `$` prefix — it can be anything useful related to the wrapped value. For `@State`, the projected value is a `Binding<T>` for two-way data flow. For `@Published`, it is a publisher for observing changes.

### Hard

**Q: How does the compiler desugar a property wrapper declaration?**

A: `@Wrapper var x: T = initialValue` becomes three things:
1. A backing store variable `var _x: Wrapper<T> = Wrapper(wrappedValue: initialValue)` (or `Wrapper()` if no `init(wrappedValue:)` applies)
2. A computed property `var x: T { get { _x.wrappedValue } set { _x.wrappedValue = newValue } }`
3. A projected value computed property `var $x: Wrapper<T>.ProjectedValue { _x.projectedValue }` (if `projectedValue` is defined)

The backing store can be accessed as `_x` — important for testing and when passing the wrapper itself to an initialiser.

**Q: Why is `@StateObject` preferred over `@ObservedObject` for view-model ownership?**

A: `@ObservedObject` does not own the object — it merely observes one provided externally. If the parent view re-renders, SwiftUI may recreate the child view's struct, and `@ObservedObject` would point to a newly created (and thus reset) view model. `@StateObject` ties the object's lifetime to the view's identity in the SwiftUI node tree — it is created once and persists across re-renders as long as the view is alive, making it the correct choice when the view is the owner.

### Expert

**Q: Design a thread-safe `@Atomic` property wrapper that avoids priority inversion on Apple platforms.**

A: Use `os_unfair_lock` (unfair lock, available since iOS 10) rather than `NSLock` or `DispatchQueue`. `NSLock` can cause priority inversion on Darwin; `os_unfair_lock` is priority-inheriting. Wrap it in a class because `os_unfair_lock` is a value type that must not be moved in memory:

```swift
@propertyWrapper
final class Atomic<Value> {
    private var _value: Value
    private var _lock = os_unfair_lock_s()

    var wrappedValue: Value {
        get { os_unfair_lock_lock(&_lock); defer { os_unfair_lock_unlock(&_lock) }; return _value }
        set { os_unfair_lock_lock(&_lock); defer { os_unfair_lock_unlock(&_lock) }; _value = newValue }
    }

    init(wrappedValue: Value) { _value = wrappedValue }
}
```

For Swift Concurrency contexts, an `actor` is preferable as it integrates with the cooperative thread pool and avoids blocking threads.

## 6. Common Issues & Solutions

**Issue: `@Published` property change not triggering SwiftUI view update.**

Solution: Ensure the view model conforms to `ObservableObject` and the view uses `@ObservedObject` or `@StateObject`. `@Published` only works as part of the `ObservableObject` machinery when the object's `objectWillChange` publisher is what SwiftUI subscribes to.

**Issue: Property wrapper applied to a `let` property causes a compiler error.**

Solution: Wrappers require `var` because the backing store must be mutable (ARC needs to set it, and `wrappedValue` setter must be callable). Change to `var` or use `let` only for wrapper types that don't support mutation.

**Issue: Backing store `_x` is accidentally accessed from outside the type.**

Solution: This is a known limitation — the backing store is not private by default. Mark the property `private` which makes the backing store also private. If you need to expose the wrapper itself, do so through `projectedValue`.

**Issue: Custom property wrapper doesn't work in SwiftUI previews — crashes or produces wrong values.**

Solution: Ensure the wrapper's initialiser handles edge cases (nil UserDefaults, missing keys). Provide a sensible default value. For `@AppStorage`-like wrappers, use a test-friendly `UserDefaults` suite rather than `.standard`.

## 7. Related Topics

- [Type Erasure](type-erasure.md) — `@Published` projects `AnyPublisher`, a type-erased publisher
- [Protocol-Oriented Programming](protocol-oriented-programming.md) — wrappers are often generic over a protocol
- [Generics](generics.md) — most useful wrappers are generic over their wrapped value
- [Concurrency](../03-concurrency/index.md) — `@MainActor` is a special property-wrapper-like annotation
