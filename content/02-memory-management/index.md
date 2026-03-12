# Memory Management

## Overview

Memory management in iOS is handled through **Automatic Reference Counting (ARC)** — a compile-time strategy that inserts retain and release calls to keep objects alive exactly as long as they are needed. Unlike garbage-collected runtimes, ARC is deterministic and has no pause latency, but it requires developers to understand ownership, reference cycles, and allocation strategies to write leak-free, high-performance apps.

This section covers the full memory lifecycle: how ARC works at the compiler and runtime level, the patterns that create retain cycles and how to break them, how closures capture values and how capture lists control that behaviour, and the fundamental difference between stack and heap allocation.

## Topics in This Section

- [ARC](arc.md) — deep dive into retain/release, compiler insertions, Instruments: Leaks
- [Retain Cycles](retain-cycles.md) — cycle patterns, detection strategies, `[weak self]` fixes
- [Closures & Capture Lists](closures-capture-lists.md) — `[weak]`/`[unowned]`, escaping vs non-escaping, autoclosure
- [Stack vs Heap](stack-vs-heap.md) — allocation mechanics, escape analysis, existential boxes, performance

## Key Concepts at a Glance

| Concept | One-line summary |
|---------|-----------------|
| ARC | Compiler inserts retain/release; memory freed when count hits 0 |
| Retain cycle | Two or more objects hold strong references to each other — never freed |
| Weak reference | Optional reference; zeroed when target is deallocated |
| Unowned reference | Non-optional; crashes if accessed after deallocation |
| Stack allocation | Fast, automatic, size known at compile time |
| Heap allocation | Flexible, managed by ARC, slower than stack |
| Capture list | Specifies how a closure captures surrounding variables |
| Escaping closure | Closure that may outlive the function it was passed to |

## Relationship to Swift Language Topics

The [ARC Basics](../01-swift-language/arc-basics.md) topic in the Swift Language section covers the fundamentals. This section goes deeper:

- **ARC** here covers compiler SIL insertions, autorelease pools, and Instruments workflow
- **Retain Cycles** covers all common patterns (delegate, closure, parent-child, timer)
- **Closures & Capture Lists** covers escaping semantics, autoclosure, and common pitfalls
- **Stack vs Heap** covers escape analysis, existential boxes, and profiling allocation cost
