# Refactoring

## 1. Overview

Refactoring is the disciplined process of restructuring existing code without changing its observable behaviour — improving internal quality (readability, maintainability, testability) while keeping all tests green. It is not rewriting, not adding features, and not fixing bugs. Martin Fowler's catalogue (refactoring.guru) defines over 60 named techniques, each a small, safe transformation. The key precondition for refactoring is a test suite: without tests, you cannot verify that the refactoring preserved behaviour. In iOS, refactoring is most commonly motivated by two inputs: **code smells** (symptoms of design problems in the current code — long methods, large classes, tight coupling, duplicate logic) and **design improvements** (introducing a pattern like Strategy or making a dependency injectable). The goal is always code that is easier to understand, test, and extend.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Code Smells](code-smells.md) | Long method, Large class, Duplicate code, Tight coupling, Feature envy, Primitive obsession |
| 2 | [Refactoring Techniques](refactoring-techniques.md) | Extract Method, Extract Class, Move Method, Replace Conditional with Polymorphism, Introduce Parameter Object |

## 3. The Refactoring Process

```
1. Ensure tests pass (or write tests first if they don't exist)
2. Identify a smell
3. Choose the appropriate refactoring technique
4. Make the smallest change
5. Run tests — must still pass
6. Commit (small, focused commit)
7. Repeat
```

**Red-Green-Refactor** (TDD cycle):
- Red: write a failing test
- Green: write the minimal code to pass
- Refactor: clean up the code while keeping tests green

## 4. Refactoring vs Rewriting

| | Refactoring | Rewriting |
|-|-------------|-----------|
| Behaviour change | None | New behaviour |
| Test requirement | Tests must pass throughout | Tests written after |
| Risk | Low (incremental) | High (big bang) |
| Delivery | Continuous | Only at completion |
| Code is deleted | Only dead code | Everything |

## 5. Related Topics

- [Design Patterns](../15-design-patterns/index.md) — the patterns refactoring moves toward
- [Testing — Testable Architecture](../11-testing/testable-architecture.md) — tests required before refactoring
- [Dependency Injection](../06-architecture/dependency-injection.md) — DI removes tight coupling
