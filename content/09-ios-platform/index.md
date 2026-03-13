# iOS Platform

## Overview

iOS Platform knowledge covers the system-level capabilities that every production app must understand: how the app lifecycle works (AppDelegate, SceneDelegate, foreground/background states), how to reliably execute work in the background, how to receive and display push notifications, how to handle deep links and universal links for cross-app navigation, and how to use the core platform frameworks — CoreLocation for location and geofencing, AVFoundation for media playback and capture, and Core Animation for the rendering layer that underpins all iOS UI.

These topics sit at the boundary between your app code and the iOS operating system. Getting them right means apps that launch correctly, respond to system events, conserve battery, and integrate seamlessly with the rest of the platform. Getting them wrong means crashes on scene reconnection, missed background refresh windows, broken notification handling, and janky animations.

## Topics in This Section

- [App Lifecycle](app-lifecycle.md) — AppDelegate, SceneDelegate, UIApplication states (active/inactive/background/suspended), scene session lifecycle, SwiftUI App protocol
- [Background Tasks](background-tasks.md) — BGAppRefreshTask, BGProcessingTask, background URLSession, VoIP push, silent push; background execution budget
- [Push Notifications](push-notifications.md) — APNs architecture, UserNotifications framework, notification categories and actions, rich notifications, Notification Service Extension, Notification Content Extension
- [Deep Links & Universal Links](deep-links-universal-links.md) — Custom URL schemes, Universal Links (AASA file, entitlements), NSUserActivity / Handoff, SiriKit intents, handling links in UIKit and SwiftUI
- [CoreLocation](core-location.md) — CLLocationManager authorisation flow, accuracy levels, background location, significant-change updates, region monitoring (geofencing), iBeacon
- [AVFoundation](avfoundation.md) — AVPlayer and AVPlayerViewController for playback, AVCaptureSession for camera/microphone, AVAudioSession routing and interruption handling
- [Core Animation](core-animation.md) — CALayer tree, implicit vs explicit animations, CABasicAnimation, CAKeyframeAnimation, CATransaction, presentation vs model layer, performance (offscreen rendering, rasterisation)

## App Lifecycle State Machine

```
            Not Running
                 │  launch
                 ▼
            Foreground Inactive  ◄──────── Interruption (call, notification)
           (viewDidAppear fires) │
                 │  becomes active
                 ▼
            Foreground Active  ──────────► Foreground Inactive
           (user interacting)   (home/lock)       │
                                                  │
                                                  ▼
                                          Background  ─────► Suspended
                                         (≈30s budget)       (killed by OS)
```

## Key Concepts at a Glance

| Concept | One-line summary |
|---------|-----------------|
| AppDelegate | Process-level lifecycle; push token registration; background session handler |
| SceneDelegate | Window/scene lifecycle; multiple windows on iPad; state restoration |
| BGAppRefreshTask | ≤30s periodic background refresh (news, weather, feeds) |
| BGProcessingTask | Minutes of background processing on charging (database maintenance, ML) |
| APNs | Apple Push Notification service; device token → server → APNs → device |
| UserNotifications | Framework for scheduling, managing, and responding to notifications |
| Universal Links | HTTPS URLs that open your app; AASA file proves domain ownership |
| CLLocationManager | GPS/Wi-Fi/cell location; requires always/whenInUse authorisation |
| AVPlayer | Playback of audio/video from URL; integrates with MediaPlayer framework |
| AVCaptureSession | Camera and microphone pipeline; inputs, outputs, preview layer |
| CALayer | The backing layer for every UIView; animatable properties; compositing |

## Relationship to Other Sections

- **Concurrency**: Background tasks and network callbacks use GCD and async/await — see [async/await](../03-concurrency/async-await.md) and [Actors](../03-concurrency/actors.md).
- **Networking**: Background URLSession tasks are driven by the background task budget — see [URLSession](../07-networking/urlsession.md).
- **UI Frameworks**: Core Animation underpins UIView animations; AVPlayerViewController is a UIViewController — see [UIViewController Lifecycle](../04-ui-frameworks/uiviewcontroller-lifecycle.md).
- **Data Persistence**: App lifecycle events (backgrounding) are the right moment to trigger saves — see [Core Data](../08-data-persistence/core-data.md).
