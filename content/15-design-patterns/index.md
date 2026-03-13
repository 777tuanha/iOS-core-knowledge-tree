# Design Patterns

## 1. Overview

Design patterns are reusable solutions to commonly occurring software design problems. They are not finished code — they are templates describing how to structure classes, objects, and their interactions to achieve a particular quality (flexibility, extensibility, testability, separation of concerns). The canonical catalogue from the "Gang of Four" (GoF) book organises patterns into three categories: **Creational** (how objects are created), **Structural** (how objects are composed), and **Behavioral** (how objects communicate and distribute responsibility). iOS development adds a fourth practical category: **iOS-specific patterns** that appear throughout UIKit, SwiftUI, and Cocoa — particularly the Delegate pattern (UIKit's primary callback mechanism), the Coordinator pattern (separating navigation from view controllers), and Dependency Injection (enabling testability).

## 2. Topics in This Section

| # | File | Patterns covered |
|---|------|-----------------|
| 1 | [Creational Patterns](creational-patterns.md) | Factory Method, Abstract Factory, Builder, Singleton |
| 2 | [Structural Patterns](structural-patterns.md) | Adapter, Decorator, Facade, Composite |
| 3 | [Behavioral Patterns](behavioral-patterns.md) | Observer, Strategy, Command, State |
| 4 | [iOS-Specific Patterns](ios-patterns.md) | Delegate, Coordinator, Dependency Injection |

## 3. Pattern Categories

```
Creational — control object creation
├── Factory Method  → subclasses decide which class to instantiate
├── Abstract Factory → families of related objects without concrete classes
├── Builder         → step-by-step construction of complex objects
└── Singleton       → exactly one instance with global access

Structural — compose objects into larger structures
├── Adapter    → convert an interface to one clients expect
├── Decorator  → add behaviour by wrapping, without subclassing
├── Facade     → simplified interface to a complex subsystem
└── Composite  → treat individual objects and trees uniformly

Behavioral — algorithms and responsibility between objects
├── Observer  → notify many objects when state changes (NotificationCenter, Combine)
├── Strategy  → interchangeable family of algorithms
├── Command   → encapsulate a request as an object
└── State     → alter behaviour when internal state changes

iOS-Specific
├── Delegate  → one-to-one callback from a child to its owner
├── Coordinator → separate navigation logic from view controllers
└── Dependency Injection → supply dependencies from outside (enables testing)
```

## 4. Choosing the Right Pattern

| Problem | Pattern to consider |
|---------|-------------------|
| Creating objects without knowing the exact class | Factory Method |
| Creating families of related objects | Abstract Factory |
| Constructing complex objects step by step | Builder |
| One global instance (database, logger) | Singleton |
| Wrapping a third-party API in your interface | Adapter |
| Adding behaviour without modifying existing class | Decorator |
| Simplifying a complex subsystem | Facade |
| Broadcasting events to multiple subscribers | Observer |
| Swapping algorithms at runtime | Strategy |
| Queuing or logging operations | Command |
| Modelling a finite state machine | State |
| UIKit callback from child to parent | Delegate |
| Managing navigation flow | Coordinator |
| Making code testable with test doubles | Dependency Injection |

## 5. Related Topics

- [Architecture — MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md) — patterns applied in UI architecture
- [Dependency Injection](../06-architecture/dependency-injection.md) — in-depth DI patterns
- [Testing — Testable Architecture](../11-testing/testable-architecture.md) — patterns enabling unit tests
- [Refactoring](../16-refactoring/index.md) — code smells and refactoring to patterns
