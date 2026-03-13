# Observability

## 1. Overview

Observability is the ability to understand what an app is doing in production — not just whether it is up or down, but why it fails, how often, for whom, and with what performance characteristics. iOS observability rests on three pillars: **crash reporting** (capturing stack traces when the app terminates unexpectedly and symbolizing them into readable function names), **structured logging** (recording events, errors, and metrics at runtime using `os_log` / `Logger`, with privacy-safe field formatting), and **monitoring** (collecting analytics events, performance metrics, and feature flag evaluations to understand behaviour across the install base). Together these three pillars close the feedback loop between shipping code and understanding its real-world impact — without them, bug investigation is blind.

## 2. Topics in This Section

| # | File | Coverage |
|---|------|----------|
| 1 | [Crash Reporting](crash-reporting.md) | Crash types, symbolication, Crashlytics, MetricKit, interpreting crash logs |
| 2 | [Logging](logging.md) | `os_log`, `Logger`, privacy levels, structured logging, log levels, subsystems/categories |
| 3 | [Monitoring](monitoring.md) | Analytics (events, funnels), MetricKit performance metrics, feature flags, A/B testing |

## 3. Observability Stack

```
Production App
├── Crash Reporting
│   ├── Signal handlers (EXC_BAD_ACCESS, SIGABRT)
│   ├── NSException handlers (unhandled ObjC exceptions)
│   └── Upload .ips crash reports → symbolication → Crashlytics / Sentry
│
├── Structured Logging
│   ├── os_log / Logger → Unified Logging System (Console.app)
│   ├── Privacy levels: .public / .private (redacted in Console)
│   └── Custom log forwarder → remote logging backend
│
└── Monitoring
    ├── Analytics events → Amplitude / Mixpanel / custom backend
    ├── MetricKit → launch time, hitch rate, hang rate, memory terminations
    └── Feature flags → Statsig / Optimizely / LaunchDarkly
```

## 4. Observability Principles

- **Privacy first**: never log PII (email, name, health data) in production logs. Use `os_log`'s `privacy: .private` for sensitive fields.
- **Signal over noise**: log events that help debug real issues — not every user action. High log volume obscures the signal.
- **Structured over unstructured**: key-value pairs (`event: "login_failed", reason: "invalid_password"`) are searchable and aggregatable; free-text strings are not.
- **Actionable metrics**: track metrics you will act on — crash-free rate, P99 launch time, payment funnel conversion. Vanity metrics waste storage.

## 5. Related Topics

- [App Lifecycle](../09-ios-platform/app-lifecycle.md) — launch callbacks where observability setup occurs
- [Testing — Unit Testing](../11-testing/unit-testing.md) — testing logging and analytics services
- [Performance — Instruments](../12-performance/instruments-profiling.md) — development-time observability
- [Security — Data Security](../14-security/data-security.md) — protecting logged data
