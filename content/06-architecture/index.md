# Architecture

## Overview

Architecture is the set of structural decisions that determine how an app's code is organised, how responsibilities are separated, and how components communicate. Good architecture makes code **testable**, **maintainable**, and **scalable** — characteristics that become critical as a team and codebase grow. Bad architecture produces tight coupling, untestable code, and the dreaded Massive View Controller.

iOS apps have a rich ecosystem of architectural patterns — from Apple's built-in MVC, through community-standard MVVM, to opinionated frameworks like VIP and TCA. Senior engineers must understand the tradeoffs of each, the design principles that underpin them (SOLID, separation of concerns), how to inject dependencies cleanly, and how to split a large app into modules.

## Topics in This Section

- [MVC](mvc.md) — Model-View-Controller, Apple's default pattern, the Massive View Controller problem, and when it's still appropriate
- [MVVM](mvvm.md) — Model-View-ViewModel, ViewModel responsibilities, testability, comparison with MVC
- [MVP & VIPER](mvp-viper.md) — Model-View-Presenter, VIPER (View/Interactor/Presenter/Entity/Router), Clean Architecture
- [VIP — Clean Swift](vip-clean-swift.md) — View-Interactor-Presenter unidirectional cycle, Worker, DataStore, scene configurator
- [The Composable Architecture](tca.md) — State/Action/Reducer/Store/Effect model, unidirectional data flow, TCA for testing
- [SOLID Principles](solid-principles.md) — Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion; composition over inheritance
- [Dependency Injection](dependency-injection.md) — Constructor, property, and method injection; service locator; DI containers
- [Modularization](modularization.md) — Feature modules, core modules, layered architecture, monolith vs modular, SPM-based module boundaries

## Architecture Comparison Table

| Pattern | Layers | Testability | Complexity | Best for |
|---------|--------|-------------|------------|----------|
| MVC | Model · View · Controller | Low (VC mixes UI + logic) | Low | Small apps, prototypes |
| MVVM | Model · View · ViewModel | High (VM is plain Swift) | Medium | Most iOS apps |
| MVP | Model · View · Presenter | High (Presenter uses protocol View) | Medium | UIKit-heavy, no Combine |
| VIPER | V · I · P · E · R | Very high | High | Large teams, Clean Architecture |
| VIP | View · Interactor · Presenter | Very high | High | UIKit teams wanting strict unidirectional flow |
| TCA | State · Action · Reducer · Store | Very high (pure functions) | High | Complex state, point-free style |

## Layered Responsibility Map

```
┌─────────────────────────────┐
│         Presentation         │  UIViewController / SwiftUI View
│   (Display + User Input)     │  ViewModel / Presenter
├─────────────────────────────┤
│          Domain              │  Use Cases / Interactors
│   (Business Logic)           │  Entities / Models
├─────────────────────────────┤
│           Data               │  Repositories / Services
│   (Networking / Persistence) │  Network Layer / CoreData / Keychain
└─────────────────────────────┘
```

This layered model — also called Clean Architecture — underlies VIPER, VIP, and TCA and is a useful mental model even when using simpler patterns.

## Key Design Principles Summary

| Principle | One-line |
|-----------|---------|
| Single Responsibility | One reason to change per type |
| Open/Closed | Open for extension, closed for modification |
| Liskov Substitution | Subtypes must be substitutable for supertypes |
| Interface Segregation | Many small protocols > one large protocol |
| Dependency Inversion | Depend on abstractions, not concretions |
| Separation of Concerns | UI, business logic, and data access in distinct layers |
| Composition over Inheritance | Favour protocols + composition; avoid deep class hierarchies |

## Relationship to Other Sections

- **UI Frameworks**: MVVM + Coordinator implementation details live in [MVVM & Coordinator](../04-ui-frameworks/mvvm-coordinator.md).
- **Reactive Programming**: Combine is the binding layer in MVVM — see [Combine + UIKit & SwiftUI](../05-reactive-programming/combine-swiftui-uikit.md).
- **Concurrency**: `@MainActor` on ViewModels; async service calls — see [Actors](../03-concurrency/actors.md).
- **Memory Management**: Dependency injection and protocol-based design prevents retain cycles — see [Retain Cycles](../02-memory-management/retain-cycles.md).
