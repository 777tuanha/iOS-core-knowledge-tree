# Generics

## 1. Overview

Generics allow you to write flexible, reusable functions and types that work with any type that satisfies specified constraints. They eliminate code duplication while preserving full type safety. Swift's standard library is built almost entirely on generics — `Array<Element>`, `Dictionary<Key, Value>`, `Optional<Wrapped>`. Understanding generics, constraints, and `where` clauses is essential for writing expressive, idiomatic Swift.

## 2. Simple Explanation

Imagine a locksmith who can cut any key, as long as the key blank meets certain specs (must be metal, must fit the machine). The locksmith doesn't need to know in advance whether it's a car key or a house key — the constraint (metal, correct profile) is enough to do the job correctly.

Generics work the same way:
- The **type parameter** (`T`, `Element`) is the blank key — unknown but expected
- The **constraint** (`where T: Comparable`) is the spec — what the blank must satisfy
- The **function/type** is the locksmith — works correctly for any blank that meets the spec

## 3. Deep iOS Knowledge

### Generic Functions

A generic function declares one or more type parameters inside angle brackets. The function body can use those parameters as if they were concrete types, subject to their constraints.

```swift
func swap<T>(_ a: inout T, _ b: inout T) { ... }
```

### Generic Types

Structs, classes, and enums can be parameterised. The type parameter is available throughout the type's scope.

```swift
struct Stack<Element> { ... }
```

### Type Constraints

Constraints narrow which types are acceptable. Without constraints, only operations available on `Any` type are permitted.

```swift
func max<T: Comparable>(_ a: T, _ b: T) -> T { a > b ? a : b }
```

Constraints can use:
- Protocol conformance: `T: Equatable`
- Class inheritance: `T: UIView`
- Protocol composition: `T: Codable & Hashable`

### `where` Clauses

`where` clauses express more complex constraints that don't fit neatly into the angle-bracket declaration, including constraints on associated types.

```swift
func equalElements<C1: Collection, C2: Collection>(_ c1: C1, _ c2: C2) -> Bool
    where C1.Element == C2.Element, C1.Element: Equatable { ... }
```

### Associated Types vs Generic Parameters

Protocols use **associated types** (`associatedtype`) rather than generic parameters. An associated type is a placeholder resolved when a type conforms to the protocol. Generic parameters are specified at the call site; associated types are inferred from the conformance.

```swift
protocol Container {
    associatedtype Element
    func add(_ item: Element)
    func get(at index: Int) -> Element
}
```

### Performance: Specialisation

Swift's optimiser **specialises** generic functions for concrete types used in the same module. Specialisation replaces the generic type parameter with the concrete type, enabling inlining and eliminating the overhead of protocol witness table dispatch. Cross-module generics may not be specialised unless the function is marked `@inlinable`.

### `some` vs `any`

- `some Protocol` (opaque type) — the compiler knows the concrete type; enables optimisation and static dispatch. Used in function return positions and property declarations.
- `any Protocol` (existential) — the concrete type is erased at runtime; stored in an existential container with dynamic dispatch. Required when the concrete type varies at runtime.

## 4. Practical Usage

```swift
// ── Generic function with constraint ──────────────────────────
func clamp<T: Comparable>(_ value: T, min minVal: T, max maxVal: T) -> T {
    Swift.max(minVal, Swift.min(maxVal, value))
}

print(clamp(15, min: 0, max: 10))   // 10
print(clamp(-3, min: 0, max: 10))   // 0

// ── Generic type: Stack ───────────────────────────────────────
struct Stack<Element> {
    private var storage: [Element] = []

    mutating func push(_ item: Element) { storage.append(item) }

    @discardableResult
    mutating func pop() -> Element? { storage.popLast() }

    var top: Element? { storage.last }
    var isEmpty: Bool { storage.isEmpty }
}

var intStack = Stack<Int>()
intStack.push(1); intStack.push(2); intStack.push(3)
print(intStack.pop() ?? -1)  // 3

// ── where clause on extension ─────────────────────────────────
extension Stack where Element: Equatable {
    func contains(_ item: Element) -> Bool {
        storage.contains(item)
    }
}

// ── Generic result type with protocol ─────────────────────────
protocol Repository {
    associatedtype Model: Identifiable
    func fetchAll() async throws -> [Model]
    func fetch(id: Model.ID) async throws -> Model?
}

struct UserRepository: Repository {
    typealias Model = User  // associated type resolved

    func fetchAll() async throws -> [User] { /* network call */ [] }
    func fetch(id: UUID) async throws -> User? { nil }
}

struct User: Identifiable { let id: UUID; var name: String }

// ── `some` return type (opaque) ───────────────────────────────
// Compiler knows the exact return type; callers use the protocol interface
func makeDefaultRepository() -> some Repository {
    UserRepository()  // concrete type hidden, but statically known
}

// ── `any` existential (heterogeneous collection) ──────────────
var repositories: [any Repository] = []  // dynamic dispatch, existential box

// ── Generic constraint with where on associated type ──────────
func printAll<C: Collection>(_ collection: C)
    where C.Element: CustomStringConvertible {
    collection.forEach { print($0.description) }
}

printAll([1, 2, 3])          // Int conforms to CustomStringConvertible
printAll(["a", "b", "c"])

// ── @inlinable for cross-module specialisation ────────────────
// In a framework module:
@inlinable
public func identity<T>(_ value: T) -> T { value }
// Without @inlinable, the optimiser cannot specialise this in client code.
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the purpose of generics in Swift?**

A: Generics allow writing flexible, reusable code that operates on any type satisfying specified constraints, without sacrificing type safety. They eliminate code duplication (no need for `intMax`, `doubleMax`, `stringMax` — just `max<T: Comparable>`) while preserving compile-time type checking and enabling compiler optimisations like specialisation.

**Q: What is the difference between a type constraint and a `where` clause?**

A: A type constraint (`<T: Comparable>`) is placed inline in the angle-bracket declaration and constrains the type parameter itself. A `where` clause (`where T.Element: Equatable`) allows more complex constraints, including constraints on associated types of the generic parameter's protocol conformances, constraints requiring two types to be equal, and multiple conditions chained with commas.

### Hard

**Q: Explain the difference between `some Protocol` and `any Protocol`.**

A: `some Protocol` is an opaque type — the compiler knows the exact concrete type even though the caller doesn't. This allows static dispatch, enables conformance to `Equatable`/`Hashable`, and the compiler can optimise aggressively. The concrete type must be the same across all code paths. `any Protocol` is an existential — the concrete type is erased into a box at runtime with a protocol witness table for dynamic dispatch. It is required when the concrete type varies (e.g., a heterogeneous array of protocol values). `any Protocol` boxes impose a small heap allocation cost for large value types.

**Q: Why do generic functions in a framework sometimes not get specialised in client code?**

A: The Swift optimiser specialises generics by substituting concrete types for type parameters. This requires access to the generic function's implementation. By default, framework functions are compiled to a `dylib` with only the exported interface visible to clients — the implementation is opaque, preventing specialisation. Marking a function `@inlinable` emits the function body into the module's swiftinterface file, making it available to the client optimiser for specialisation.

### Expert

**Q: How would you implement a type-safe builder pattern using generics and phantom types?**

A: Use a generic struct where the type parameter carries state information that the compiler tracks, without that state occupying any memory (phantom type). For example:

```swift
enum Unset {}
enum IsSet {}

struct Builder<NameState, AgeState> {
    private var name: String = ""
    private var age: Int = 0

    func setName(_ n: String) -> Builder<IsSet, AgeState> {
        var b = Builder<IsSet, AgeState>(); b.name = n; b.age = age; return b
    }
    func setAge(_ a: Int) -> Builder<NameState, IsSet> {
        var b = Builder<NameState, IsSet>(); b.name = name; b.age = a; return b
    }
}

extension Builder where NameState == IsSet, AgeState == IsSet {
    func build() -> User { User(id: UUID(), name: name) }
}

// Builder<Unset, Unset>().build() — compile error: build() not available
// Builder<Unset, Unset>().setName("Alice").setAge(30).build() — compiles fine
```

The phantom types `Unset`/`IsSet` are never instantiated; they purely encode state in the type system, catching missing-field errors at compile time rather than runtime.

## 6. Common Issues & Solutions

**Issue: "Protocol can only be used as a generic constraint" error when trying to use a protocol with associated types as a variable type.**

Solution: Replace `var r: Repository` with `var r: any Repository` (Swift 5.7+) or use a concrete generic parameter `func foo<R: Repository>(_ r: R)`. The `any` keyword acknowledges existential boxing. If the concrete type is always the same, `some Repository` in a return position is more efficient.

**Issue: Generic function not specialised — hot path shows unexpected protocol witness table overhead in a profiler.**

Solution: Mark the function `@inlinable` if it lives in a framework, or move it to the same module as the call site. Verify specialisation in the SIL output: `swiftc -O -emit-sil` and search for the concrete-type mangled name.

**Issue: Overly constrained generic prevents composability.**

Solution: Split constraints into protocol extensions and conditional conformances. Only the code paths that actually need a constraint should require it. Use `where` clauses on extensions instead of on the type itself.

**Issue: Type inference fails for complex generic expressions.**

Solution: Add explicit type annotations to help the compiler. Break the expression into smaller steps with named intermediate variables. If the expression involves closures, annotate the closure parameter types explicitly.

## 7. Related Topics

- [Protocol-Oriented Programming](protocol-oriented-programming.md) — protocols with associated types and generics
- [Type Erasure](type-erasure.md) — `any`, `AnyPublisher`, and erasing generic constraints
- [Value vs Reference Types](value-vs-reference.md) — how generics interact with value/reference semantics
- [Concurrency](../03-concurrency/index.md) — `AsyncSequence` and generic async protocols
