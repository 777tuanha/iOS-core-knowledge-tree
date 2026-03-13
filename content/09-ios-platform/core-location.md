# CoreLocation

## 1. Overview

CoreLocation provides the iOS API for determining a device's geographic position, heading, and proximity to known regions. It uses GPS, Wi-Fi triangulation, cellular network data, and barometric altitude to compute location fixes at varying levels of accuracy and power cost. The framework covers four main capabilities: standard location updates, significant-change monitoring (low-power), region monitoring / geofencing (enter/exit notifications), and iBeacon ranging. Getting CoreLocation right requires understanding the authorisation flow (when-in-use vs always), accuracy vs battery tradeoff, background location requirements, and MapKit integration for displaying location data.

## 2. Simple Explanation

CoreLocation is like a GPS tracker that your app rents from the OS. Before you can use it, you must ask the user's permission ("Can I know where you are?") — and you can ask for a temporary pass (when-in-use, like a taxi GPS) or a permanent pass (always, like a delivery tracking system). Once authorised, the GPS tells you coordinates at a given accuracy. Geofencing is like drawing a circle on a map and saying "let me know when the device enters or exits this circle" — the OS watches the fence even when your app isn't running.

## 3. Deep iOS Knowledge

### Authorisation

Two permission levels:

| Permission | Description | Typical use |
|-----------|-------------|------------|
| `whenInUse` | Location available only while app is in foreground (or has a blue status bar) | Maps, local search, routing |
| `always` | Location available in background, required for geofencing and silent location updates | Fitness tracking, geofencing, delivery |

**Privacy strings required in `Info.plist`**:
- `NSLocationWhenInUseUsageDescription` — always required.
- `NSLocationAlwaysAndWhenInUseUsageDescription` — required for `always`.

**Authorisation flow**:
1. Check `CLLocationManager.authorizationStatus` (or `locationManagerDidChangeAuthorization(_:)` callback).
2. If `.notDetermined`, call `requestWhenInUseAuthorization()` or `requestAlwaysAuthorization()`.
3. If `.denied` or `.restricted`, show settings redirect UI — the OS won't re-present the dialog.

iOS 14+ introduced `CLAccuracyAuthorization`: users can grant precise or approximate location. Check `manager.accuracyAuthorization`.

### CLLocationManager Configuration

```swift
let manager = CLLocationManager()
manager.delegate = self
manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation  // highest power
// kCLLocationAccuracyHundredMeters  — less power
// kCLLocationAccuracyKilometer      — low power
// kCLLocationAccuracyThreeKilometers — very low power
manager.distanceFilter = 10   // metres; don't update unless moved this far
manager.activityType = .fitness  // hints to OS for power optimisation
```

**Accuracy vs power tradeoff**: `kCLLocationAccuracyBest` keeps GPS radio on continuously — high battery drain. For features that don't need sub-10m precision, use `kCLLocationAccuracyHundredMeters` or significant-change monitoring.

### Location Update Modes

| Mode | API | Battery | Typical accuracy | Background |
|------|-----|---------|-----------------|------------|
| Standard | `startUpdatingLocation()` | High | ~5–10 m | With `always` + background mode |
| Significant change | `startMonitoringSignificantLocationChanges()` | Very low | ~500 m | Yes (wakes app) |
| Region monitoring | `startMonitoring(for: CLCircularRegion)` | Very low | ~100 m radius min | Yes |
| Visit monitoring | `startMonitoringVisits()` | Very low | Arrival/departure at places | Yes |

### Region Monitoring (Geofencing)

`CLCircularRegion` defines a geographic fence. The OS delivers enter/exit events even when the app is not running (relaunches it):

```swift
let region = CLCircularRegion(
    center: CLLocationCoordinate2D(latitude: 51.5074, longitude: -0.1278),
    radius: 200,    // metres; minimum ~100m enforced by OS
    identifier: "office"
)
region.notifyOnEntry = true
region.notifyOnExit  = true
manager.startMonitoring(for: region)
```

**Limits**: iOS supports up to **20 monitored regions** per app. For more, monitor the closest N regions and update the set as the user moves.

### Background Location

To receive location in the background:
1. Add `location` to `UIBackgroundModes` in `Info.plist`.
2. Request `always` authorization.
3. Set `manager.allowsBackgroundLocationUpdates = true`.
4. Set `manager.pausesLocationUpdatesAutomatically = false` if continuous updates are required.

**iOS 14+ blue pill indicator**: when an app uses location in the background, a blue location pill appears in the status bar — users see this and may revoke permission.

### async/await Location API (iOS 15+)

```swift
// One-shot location
let location = try await manager.requestLocation()

// Streaming locations
for try await update in CLLocationUpdate.liveUpdates() {
    handleUpdate(update.location)
}
```

### MapKit Integration

`MKMapView` displays location and overlays. Key integration points:
- `MKMapView.showsUserLocation = true` — shows the blue dot (automatically uses CoreLocation).
- `MKCircle` / `MKOverlay` — visualise geofences.
- `MKLocalSearch` — geocoding and place search.
- `MKDirections` — routing.

## 4. Practical Usage

```swift
import CoreLocation
import Combine

// ── Location service wrapping CLLocationManager ───────────────
@MainActor
class LocationService: NSObject, ObservableObject {
    @Published private(set) var location: CLLocation?
    @Published private(set) var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published private(set) var accuracyAuthorization: CLAccuracyAuthorization = .fullAccuracy
    @Published private(set) var error: Error?

    private let manager = CLLocationManager()

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
        manager.distanceFilter = 50   // update only when moved 50m
    }

    func requestWhenInUseAuthorization() {
        manager.requestWhenInUseAuthorization()
    }

    func requestAlwaysAuthorization() {
        manager.requestAlwaysAuthorization()
    }

    func startUpdating() {
        manager.startUpdatingLocation()
    }

    func stopUpdating() {
        manager.stopUpdatingLocation()
    }

    // One-shot location (iOS 15+)
    func requestCurrentLocation() async throws -> CLLocation {
        try await withCheckedThrowingContinuation { continuation in
            manager.requestLocation()
            // Continuation resolved in delegate
            self.singleLocationContinuation = continuation
        }
    }

    private var singleLocationContinuation: CheckedContinuation<CLLocation, Error>?
}

// ── CLLocationManagerDelegate ────────────────────────────────
extension LocationService: CLLocationManagerDelegate {

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            self.authorizationStatus = manager.authorizationStatus
            self.accuracyAuthorization = manager.accuracyAuthorization

            if manager.authorizationStatus == .authorizedWhenInUse ||
               manager.authorizationStatus == .authorizedAlways {
                manager.startUpdatingLocation()
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager,
                                      didUpdateLocations locations: [CLLocation]) {
        guard let latest = locations.last else { return }
        Task { @MainActor in
            self.location = latest
            self.singleLocationContinuation?.resume(returning: latest)
            self.singleLocationContinuation = nil
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager,
                                      didFailWithError error: Error) {
        Task { @MainActor in
            self.error = error
            self.singleLocationContinuation?.resume(throwing: error)
            self.singleLocationContinuation = nil
        }
    }
}

// ── Geofencing manager ────────────────────────────────────────
class GeofenceManager: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    var onEnter: ((String) -> Void)?
    var onExit: ((String) -> Void)?

    override init() {
        super.init()
        manager.delegate = self
    }

    func monitorRegion(id: String, coordinate: CLLocationCoordinate2D, radius: CLLocationDistance) {
        let region = CLCircularRegion(center: coordinate, radius: max(radius, 100), identifier: id)
        region.notifyOnEntry = true
        region.notifyOnExit = true
        manager.startMonitoring(for: region)
    }

    func stopMonitoring(id: String) {
        manager.monitoredRegions
            .filter { $0.identifier == id }
            .forEach { manager.stopMonitoring(for: $0) }
    }

    func locationManager(_ manager: CLLocationManager, didEnterRegion region: CLRegion) {
        onEnter?(region.identifier)
    }

    func locationManager(_ manager: CLLocationManager, didExitRegion region: CLRegion) {
        onExit?(region.identifier)
    }

    func locationManager(_ manager: CLLocationManager,
                         monitoringDidFailFor region: CLRegion?,
                         withError error: Error) {
        print("Geofence monitoring failed for \(region?.identifier ?? "unknown"): \(error)")
    }
}

// ── SwiftUI integration ───────────────────────────────────────
import SwiftUI
import MapKit

struct LocationView: View {
    @StateObject private var locationService = LocationService()

    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 51.5, longitude: -0.12),
        span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
    )

    var body: some View {
        Map(coordinateRegion: $region, showsUserLocation: true)
            .ignoresSafeArea()
            .overlay(alignment: .bottom) {
                if let loc = locationService.location {
                    Text(String(format: "%.4f, %.4f", loc.coordinate.latitude, loc.coordinate.longitude))
                        .padding()
                        .background(.regularMaterial)
                        .cornerRadius(8)
                        .padding()
                }
            }
            .onAppear { locationService.requestWhenInUseAuthorization() }
            .onChange(of: locationService.location) { loc in
                if let loc {
                    region.center = loc.coordinate
                }
            }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `whenInUse` and `always` location authorization?**

A: `whenInUse` grants location access only while the app is in the foreground (active) or when a background location session is explicitly active (indicated by the blue pill in the status bar). It is appropriate for features that only need location when the user is actively engaging with the app — navigation, local search, ride-hailing. `always` grants location access at any time, including when the app is suspended or not running. It is required for geofencing (region monitoring), significant-change monitoring, and visit monitoring — all of which can wake the app from the background. `always` triggers more scrutiny from users and App Review, requires a stronger justification in the `NSLocationAlwaysAndWhenInUseUsageDescription` string, and iOS 13+ presents it as a two-step upgrade (grant `whenInUse` first, then later prompt to upgrade to `always`).

**Q: How does significant-change location monitoring work and when should you use it instead of standard updates?**

A: `startMonitoringSignificantLocationChanges()` uses cell tower and Wi-Fi changes to estimate position — accuracy is typically 500m–1km. It draws minimal battery because it doesn't activate the GPS radio. The OS delivers updates approximately when the device moves 500m or more. When the app is suspended or not running, the OS relaunches it in the background when a significant change is detected. Use it when you need rough location awareness over long periods — checking whether a user is in a city, updating a weather widget, or re-evaluating which geofences to actively monitor. For precision navigation or real-time tracking, use `startUpdatingLocation()` with `kCLLocationAccuracyBest`. The common pattern for geofencing at scale is: use significant-change monitoring to track coarse position, then dynamically update the 20-region geofence set to cover the regions nearest the current position.

### Hard

**Q: iOS limits region monitoring to 20 geofences per app. How do you implement unlimited geofencing?**

A: The 20-region limit is enforced by the OS. To support more fences: (1) Use **significant-change monitoring** to track the device's coarse position at low battery cost. (2) Maintain a complete list of all target geofences (locally or from a server). (3) When the device moves significantly, compute the 20 closest geofences to the current position and start monitoring those, stopping the previous set. `manager.monitoredRegions` tracks the active set. (4) Add a large outer geofence around the current cluster — when the device exits this outer fence, you know it has moved far enough to recompute the active 20. This approach handles arbitrarily many geofences with only two CLLocationManager monitoring sessions active at any time (significant-change + the active 20 fences).

**Q: How do you request location from an async context in Swift concurrency?**

A: iOS 15 introduced `CLLocationUpdate.liveUpdates()` and `manager.requestLocation()` (via continuation wrapping in older code). The canonical approach: (1) For a single location fix, wrap `manager.requestLocation()` in a `CheckedThrowingContinuation`: `withCheckedThrowingContinuation { continuation in ... }`, storing the continuation and resuming it in `locationManager(_:didUpdateLocations:)` and `locationManager(_:didFailWithError:)`. (2) For streaming, use `AsyncStream` backed by the delegate callbacks, or on iOS 17+ use `CLLocationUpdate.liveUpdates()` directly in a `for try await` loop. The `@MainActor` annotation on the delegate-wrapping class ensures callbacks are received and published on the main actor, preventing data races on `@Published` properties.

### Expert

**Q: What are the App Review implications of requesting `always` location authorization, and how do you maximise approval chances?**

A: Apple's review guidelines require that apps requesting `always` location demonstrate a clear user benefit from background location that cannot be achieved with `whenInUse`. Review rejections for `always` are common for apps where the background usage is incidental or could be replaced by geofencing. Best practices: (1) Request `whenInUse` first; only upgrade to `always` when the user explicitly enables a feature that requires it (e.g., "Enable arrival notifications"). (2) The `NSLocationAlwaysAndWhenInUseUsageDescription` must clearly explain the background use case — not a generic "improve your experience". (3) Use the least invasive background mode: prefer region monitoring over continuous GPS for battery and privacy. (4) Implement a UI that shows the user when background location is active and provides an easy path to disable it. (5) On iOS 14+, respect approximate location authorization for features that don't need precision — this demonstrates good location hygiene to reviewers.

## 6. Common Issues & Solutions

**Issue: `locationManager(_:didUpdateLocations:)` is never called after calling `startUpdatingLocation()`.**

Solution: (1) Authorization is not granted — check `authorizationStatus`; the delegate's `locationManagerDidChangeAuthorization` must start updates after authorization is confirmed. (2) The `CLLocationManager` was deallocated — store it as a property, not a local variable. (3) On Simulator, no location is simulated — set a custom location in Xcode → Simulate Location.

**Issue: Geofence enter/exit events are not delivered.**

Solution: (1) Verify `always` authorization — region monitoring requires it. (2) Check `manager.monitoredRegions` to confirm the region is being monitored. (3) Minimum radius is ~100m — smaller radii are automatically rounded up. (4) Call `manager.requestState(for: region)` to immediately check the current state (inside/outside) — useful for detecting regions the user is already inside when monitoring starts. (5) On Simulator, simulate location changes in Xcode.

**Issue: Battery drain is reported by users despite using CoreLocation minimally.**

Solution: `kCLLocationAccuracyBest` keeps the GPS continuously active. Reduce to `kCLLocationAccuracyHundredMeters` or use significant-change monitoring. Set `distanceFilter` to prevent updates for small movements. Check `activityType` — setting `.automotiveNavigation` or `.fitness` allows the OS to optimise power for the movement pattern. Always call `stopUpdatingLocation()` when location is no longer needed (e.g., in `sceneDidEnterBackground`).

## 7. Related Topics

- [App Lifecycle](app-lifecycle.md) — start/stop location updates in scene lifecycle methods
- [Background Tasks](background-tasks.md) — location background mode and significant-change monitoring
- [Push Notifications](push-notifications.md) — location-triggered local notifications (`UNLocationNotificationTrigger`)
- [Actors](../03-concurrency/actors.md) — `@MainActor` wrapping of CLLocationManagerDelegate callbacks
