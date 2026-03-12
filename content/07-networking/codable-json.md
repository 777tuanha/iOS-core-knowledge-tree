# Codable & JSON

## 1. Overview

`Codable` is Swift's built-in type alias for `Encodable & Decodable`. It provides a compile-time-safe, protocol-driven system for serialising and deserialising Swift types to and from external representations — most commonly JSON, but also Property List and custom formats. The compiler auto-synthesises `Codable` conformance for types whose properties are all `Codable`, making simple cases effortless. For complex APIs — snake_case keys, custom date formats, nested structures, and optional fields — you customise behaviour via `CodingKeys`, `JSONDecoder` configuration, and manual `init(from:)` / `encode(to:)` implementations.

## 2. Simple Explanation

Imagine a moving company that packs and unpacks your belongings. `Encodable` is the packing service — it knows how to take your Swift objects and pack them into boxes (JSON). `Decodable` is the unpacking service — it opens the boxes (JSON) and reassembles your objects. `Codable` provides both. The compiler is an automated packer that writes the packing/unpacking instructions for you, as long as every item in your home (every stored property) also has packing instructions.

## 3. Deep iOS Knowledge

### Auto-synthesis

When all stored properties conform to `Codable`, the compiler synthesises conformance automatically:

```swift
struct User: Codable {
    let id: Int
    let name: String
    let email: String
}
// No manual implementation needed
```

Types with `Codable` auto-synthesis: `Int`, `Double`, `String`, `Bool`, `Date`, `URL`, `Data`, `Array<T: Codable>`, `Dictionary<String, T: Codable>`, `Optional<T: Codable>`.

### JSONDecoder and JSONEncoder

`JSONDecoder` converts `Data` (UTF-8 JSON bytes) → Swift types. `JSONEncoder` converts Swift types → `Data`.

Key configuration:
```swift
let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase   // "user_name" → userName
decoder.dateDecodingStrategy = .iso8601               // "2024-01-15T10:30:00Z"
decoder.nonConformingFloatDecodingStrategy = .convertFromString(
    positiveInfinity: "Infinity", negativeInfinity: "-Infinity", nan: "NaN"
)

let encoder = JSONEncoder()
encoder.keyEncodingStrategy = .convertToSnakeCase     // userName → "user_name"
encoder.dateEncodingStrategy = .iso8601
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]  // readable output
```

### CodingKeys

Override the JSON key names using a nested `CodingKeys` enum. Cases map property names to JSON keys:

```swift
struct Post: Codable {
    let id: Int
    let authorName: String
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case authorName = "author_name"   // map Swift camelCase → JSON snake_case
        case createdAt  = "created_at"
    }
}
```

If any property is omitted from `CodingKeys`, it is excluded from encoding and decoding — useful for computed properties or locally-only state.

### Nested Structures

Map nested JSON objects to nested Swift types:

```swift
// JSON: { "user": { "id": 1, "address": { "city": "London" } } }
struct Address: Codable { let city: String }
struct User: Codable {
    let id: Int
    let address: Address
}
struct Response: Codable { let user: User }
```

### Handling Optional Fields

`Optional<T: Codable>` is `Codable`. If a key is missing from JSON, the optional is `nil`. If a key is present with `null`, it is also `nil`:

```swift
struct Article: Codable {
    let id: Int
    let title: String
    let subtitle: String?   // optional — may be missing or null in JSON
}
```

### Custom dateDecodingStrategy

For non-standard date formats:
```swift
let decoder = JSONDecoder()
let formatter = DateFormatter()
formatter.dateFormat = "yyyy-MM-dd"
formatter.locale = Locale(identifier: "en_US_POSIX")
decoder.dateDecodingStrategy = .formatted(formatter)

// For multiple formats or Unix timestamps:
decoder.dateDecodingStrategy = .custom { decoder in
    let container = try decoder.singleValueContainer()
    let timestamp = try container.decode(Double.self)
    return Date(timeIntervalSince1970: timestamp)
}
```

### Manual Decoding — `init(from:)`

When auto-synthesis is insufficient — e.g., the API returns a type discriminator, or data requires transformation during decoding:

```swift
struct Event: Decodable {
    let id: Int
    let type: EventType
    let payload: EventPayload

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id   = try container.decode(Int.self, forKey: .id)
        type = try container.decode(EventType.self, forKey: .type)

        // Decode payload based on the type discriminator
        switch type {
        case .message:
            payload = try container.decode(MessagePayload.self, forKey: .payload)
        case .reaction:
            payload = try container.decode(ReactionPayload.self, forKey: .payload)
        }
    }

    enum CodingKeys: String, CodingKey { case id, type, payload }
}
```

### Decoding Heterogeneous Arrays

When an array contains different types wrapped in a discriminator:

```swift
enum Feed: Decodable {
    case post(Post)
    case ad(Advertisement)

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let kind = try container.decode(String.self, forKey: .kind)
        switch kind {
        case "post": self = .post(try Post(from: decoder))
        case "ad":   self = .ad(try Advertisement(from: decoder))
        default:     throw DecodingError.dataCorruptedError(
            forKey: .kind, in: container, debugDescription: "Unknown kind: \(kind)"
        )
        }
    }

    enum CodingKeys: String, CodingKey { case kind }
}
```

### Decoding Nested Values Flatly

When JSON nests a value you want at the top level:

```swift
// JSON: { "data": { "user": { "id": 1, "name": "Alice" } } }
// Swift: just User(id: 1, name: "Alice")
struct UserResponse: Decodable {
    let user: User

    init(from decoder: Decoder) throws {
        let root = try decoder.container(keyedBy: RootKeys.self)
        let data = try root.nestedContainer(keyedBy: DataKeys.self, forKey: .data)
        user = try data.decode(User.self, forKey: .user)
    }

    enum RootKeys: String, CodingKey { case data }
    enum DataKeys: String, CodingKey { case user }
}
```

### Error Handling

`JSONDecoder` throws `DecodingError` with four cases:

| Case | Cause |
|------|-------|
| `.typeMismatch(type, context)` | Expected Int, found String |
| `.valueNotFound(type, context)` | Non-optional key was null |
| `.keyNotFound(key, context)` | Non-optional key was missing |
| `.dataCorrupted(context)` | Malformed JSON / invalid data |

The `context.codingPath` shows exactly where in the JSON tree the error occurred — essential for debugging.

## 4. Practical Usage

```swift
import Foundation

// ── Basic decode / encode ─────────────────────────────────────
struct Product: Codable {
    let id: Int
    let name: String
    let priceInCents: Int
    let isAvailable: Bool
    let tags: [String]
    let discount: Double?           // optional — may be absent

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case priceInCents = "price_in_cents"
        case isAvailable  = "is_available"
        case tags
        case discount
    }
}

let json = """
{
    "id": 42,
    "name": "Widget Pro",
    "price_in_cents": 1999,
    "is_available": true,
    "tags": ["sale", "featured"]
}
""".data(using: .utf8)!

let product = try JSONDecoder().decode(Product.self, from: json)
print(product.name)           // "Widget Pro"
print(product.discount)       // nil — key absent

let encoded = try JSONEncoder().encode(product)

// ── convertFromSnakeCase — no CodingKeys needed ───────────────
struct Article: Codable {
    let id: Int
    let authorName: String        // decoded from "author_name" automatically
    let publishedAt: Date         // decoded from "published_at"
}

let decoder = JSONDecoder()
decoder.keyDecodingStrategy = .convertFromSnakeCase
decoder.dateDecodingStrategy = .iso8601

// ── Custom date format ────────────────────────────────────────
struct Event: Codable {
    let title: String
    let date: Date
}

let customDecoder = JSONDecoder()
let formatter = DateFormatter()
formatter.dateFormat = "dd/MM/yyyy"
formatter.locale = Locale(identifier: "en_US_POSIX")
customDecoder.dateDecodingStrategy = .formatted(formatter)

// ── Polymorphic decoding with discriminator ───────────────────
struct Notification: Decodable {
    enum Kind: String, Decodable { case like, comment, follow }
    struct LikePayload: Decodable { let postID: Int }
    struct CommentPayload: Decodable { let commentText: String }

    let id: String
    let kind: Kind
    let likePayload: LikePayload?
    let commentPayload: CommentPayload?

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id   = try c.decode(String.self, forKey: .id)
        kind = try c.decode(Kind.self, forKey: .kind)
        switch kind {
        case .like:
            likePayload    = try c.decodeIfPresent(LikePayload.self, forKey: .payload)
            commentPayload = nil
        case .comment:
            likePayload    = nil
            commentPayload = try c.decodeIfPresent(CommentPayload.self, forKey: .payload)
        case .follow:
            likePayload = nil; commentPayload = nil
        }
    }

    enum CodingKeys: String, CodingKey { case id, kind, payload }
}

// ── Error handling with descriptive messages ──────────────────
func safeDecode<T: Decodable>(_ type: T.Type, from data: Data) -> T? {
    do {
        return try JSONDecoder().decode(T.self, from: data)
    } catch let DecodingError.keyNotFound(key, context) {
        print("Missing key '\(key.stringValue)' at \(context.codingPath)")
    } catch let DecodingError.typeMismatch(type, context) {
        print("Type mismatch for \(type) at \(context.codingPath): \(context.debugDescription)")
    } catch let DecodingError.valueNotFound(type, context) {
        print("Missing value for \(type) at \(context.codingPath)")
    } catch {
        print("Decoding error: \(error)")
    }
    return nil
}

// ── Encoding for POST body ────────────────────────────────────
struct CreatePostRequest: Encodable {
    let title: String
    let body: String
    let tagIDs: [Int]

    enum CodingKeys: String, CodingKey {
        case title, body
        case tagIDs = "tag_ids"
    }
}

func makeCreatePostRequest(title: String, body: String, tags: [Int]) throws -> URLRequest {
    let url = URL(string: "https://api.example.com/posts")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")

    let encoder = JSONEncoder()
    encoder.keyEncodingStrategy = .convertToSnakeCase    // alternative to CodingKeys
    request.httpBody = try encoder.encode(
        CreatePostRequest(title: title, body: body, tagIDs: tags)
    )
    return request
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is `Codable` and how does the compiler synthesise it?**

A: `Codable` is a type alias for `Encodable & Decodable`. When a type's stored properties all conform to `Codable`, the Swift compiler synthesises the `encode(to:)` and `init(from:)` implementations automatically at compile time. The synthesised code creates a keyed container and encodes/decodes each property using its property name as the key. If the JSON uses different key names, you override with a nested `CodingKeys: String, CodingKey` enum that maps Swift property names to JSON key strings. If any stored property is not `Codable`, the compiler reports an error and you must provide a manual implementation.

**Q: How do you handle a JSON field whose key name uses snake_case when your Swift property uses camelCase?**

A: Two approaches: (1) Set `decoder.keyDecodingStrategy = .convertFromSnakeCase` on the `JSONDecoder` — it automatically transforms `author_name` → `authorName` for all properties. (2) Provide a `CodingKeys` enum with explicit mappings: `case authorName = "author_name"`. The first approach is less verbose and is the standard choice when the entire API consistently uses snake_case. The second is necessary when only some keys differ or when the mapping is non-standard.

### Hard

**Q: How do you decode a JSON response where the structure wraps the payload in a data envelope — e.g., `{ "data": { "user": {...} } }` — but you only want the inner `User` struct?**

A: Use a manual `init(from:)` with `nestedContainer(keyedBy:forKey:)` to traverse the envelope and decode the inner object directly. Alternatively, create a generic wrapper: `struct Envelope<T: Decodable>: Decodable { let data: T }` and decode `Envelope<User>.self`. Then access `.data`. The generic wrapper is reusable across all endpoints that share the same envelope structure and requires no manual implementation per type. For deeply nested envelopes (e.g., `data.user`), chain multiple `nestedContainer` calls or create a custom `Decoder` wrapper that transparently unwraps the envelope layer.

**Q: What is the difference between `decode` and `decodeIfPresent` in a custom `init(from:)`?**

A: `decode(_:forKey:)` requires the key to be present in the JSON and its value to be non-null. If the key is missing or null, it throws `DecodingError.keyNotFound` or `DecodingError.valueNotFound`. `decodeIfPresent(_:forKey:)` returns `nil` if the key is absent or its value is null, and throws only if the key is present with an incompatible type. Use `decodeIfPresent` for properties that should be `Optional` in Swift — it correctly handles both "key missing" and "key present with null value" as `nil`.

### Expert

**Q: Describe a strategy for versioning your Codable models when the API changes incompatibly — e.g., a field is renamed or its type changes.**

A: Several strategies: (1) **Additive changes** (new optional fields): auto-handled — new keys are decoded if present, ignored if absent (for `decodeIfPresent`), and encoding simply omits them. (2) **Renamed fields**: add the new key to `CodingKeys` and provide a manual `init(from:)` that tries the new key first and falls back to the old key with `decodeIfPresent`. (3) **Type changes** (e.g., `Int` → `String` for IDs): provide a custom `init(from:)` that tries both types: `if let idInt = try? c.decode(Int.self, forKey: .id) { id = String(idInt) } else { id = try c.decode(String.self, forKey: .id) }`. (4) **Versioned model structs**: maintain separate `UserV1`, `UserV2` types and a version-discriminating decoder that selects the correct model based on an API version header or field. (5) **Wrap in `AnyCodable`**: use a flexible `AnyCodable` type for fields with unknown or changing shapes, parsing into a concrete type at a later stage.

## 6. Common Issues & Solutions

**Issue: `DecodingError.keyNotFound` for a key that exists in the JSON.**

Solution: Key name mismatch. Either the JSON uses snake_case and your property is camelCase (set `keyDecodingStrategy = .convertFromSnakeCase` or add `CodingKeys`), or there's a typo. Print `context.codingPath` in the error handler to locate the exact path.

**Issue: Date decodes as `0` or `1970-01-01`.**

Solution: The default `dateDecodingStrategy` is `.deferredToDate` which expects a `Double` (seconds since 2001-01-01). If your API sends ISO-8601 strings, set `decoder.dateDecodingStrategy = .iso8601`. For custom formats, use `.formatted(dateFormatter)`.

**Issue: `Optional` field with `null` value throws instead of returning `nil`.**

Solution: Use `decodeIfPresent(_:forKey:)` instead of `decode(_:forKey:)` in a custom `init(from:)`. For auto-synthesised conformance, declare the property as `Optional<T>` (`let field: T?`) — the compiler generates `decodeIfPresent` for optional properties.

**Issue: Encoding produces `null` for optional fields — server rejects unknown null fields.**

Solution: Use a custom `encode(to:)` that skips nil values: `if let value = optionalField { try container.encode(value, forKey: .optionalField) }`. Alternatively, set `encoder.outputFormatting = []` — but that doesn't omit nulls. Manual `encode(to:)` with conditional encoding is the correct solution.

## 7. Related Topics

- [URLSession](urlsession.md) — provides the Data that JSONDecoder processes
- [HTTP & REST Basics](http-rest-basics.md) — Content-Type headers govern the format
- [Advanced Networking](advanced-networking.md) — Codable in retry/caching pipelines
