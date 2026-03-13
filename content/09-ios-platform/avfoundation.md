# AVFoundation

## 1. Overview

AVFoundation is Apple's framework for working with audiovisual media: playing video and audio, capturing from camera and microphone, compositing media assets, and managing audio sessions. It underpins every media experience on iOS — from simple video playback to custom camera UIs and audio mixing. The framework has two primary subsystems: **playback** (`AVPlayer`, `AVPlayerItem`, `AVPlayerViewController`) for consuming media from URLs or local files, and **capture** (`AVCaptureSession`, `AVCaptureDevice`, `AVCaptureInput`, `AVCaptureOutput`) for recording from hardware inputs. `AVAudioSession` manages how the app interacts with the audio hardware and other audio-producing apps system-wide.

## 2. Simple Explanation

Think of AVFoundation as a professional AV studio. **AVPlayer** is the projector — you feed it a film reel (`AVPlayerItem`) and it plays back video through a screen (`AVPlayerLayer` or `AVPlayerViewController`). **AVCaptureSession** is the recording studio — microphones and cameras (`AVCaptureInput`) feed signal into recording equipment (`AVCaptureOutput`) that writes to disk or streams preview to a monitor. **AVAudioSession** is the studio's mixing board routing — it decides whether your app's audio goes through the speaker, headphones, or Bluetooth, and whether it should duck, pause, or mix with background music.

## 3. Deep iOS Knowledge

### AVPlayer and Playback Pipeline

```
AVURLAsset (media file / HLS URL)
    │
    ▼
AVPlayerItem  (loading state, tracks, timing)
    │
    ▼
AVPlayer      (playback control: rate, seek, volume)
    │
    ├──► AVPlayerLayer          (renders video into CALayer)
    └──► AVPlayerViewController (full-featured player UI)
```

**Key AVPlayerItem states** (accessed via `KVO` or `async` sequences):
- `.unknown` — not loaded
- `.readyToPlay` — buffer loaded, can start
- `.failed` — error; check `item.error`

**Buffering**: `AVPlayerItem.isPlaybackLikelyToKeepUp` and `preferredForwardBufferDuration` control adaptive buffering behaviour.

### Observing Playback

KVO and notifications are the traditional approach; iOS 16+ adds `AVPlayer.currentTimePublisher()` and async sequences:

```swift
// KVO on status
playerItem.observe(\.status) { item, _ in
    if item.status == .readyToPlay { player.play() }
}

// Periodic time observer
player.addPeriodicTimeObserver(
    forInterval: CMTime(seconds: 0.5, preferredTimescale: 600),
    queue: .main
) { time in
    updateProgressUI(time)
}

// iOS 15+ async
for await _ in player.currentItem?.publisher(for: \.status).values ?? Empty().values {
    // handle status change
}
```

### AVPlayerViewController

The system-provided full-featured player UI (transport controls, AirPlay, Picture-in-Picture, subtitles):

```swift
let playerVC = AVPlayerViewController()
playerVC.player = player
present(playerVC, animated: true) {
    player.play()
}
```

### AVCaptureSession — Capture Pipeline

```
AVCaptureDevice (camera / microphone)
    │
    ▼
AVCaptureDeviceInput
    │ added to session
    ▼
AVCaptureSession
    │ outputs
    ├──► AVCapturePhotoOutput    (still photos)
    ├──► AVCaptureMovieFileOutput (video recording to file)
    ├──► AVCaptureVideoDataOutput (raw frame access)
    └──► AVCaptureAudioDataOutput (raw audio samples)
```

**Session presets**: `AVCaptureSession.Preset` controls output quality — `.photo`, `.high`, `.medium`, `.low`, `.hd1920x1080`.

**All `AVCaptureSession` configuration must happen on a dedicated serial background queue** — never on the main thread.

### AVCaptureDevice — Selecting and Configuring Camera

```swift
// Preferred: discovery session for multi-camera selection
let discovery = AVCaptureDevice.DiscoverySession(
    deviceTypes: [.builtInWideAngleCamera, .builtInUltraWideCamera, .builtInTelephotoCamera],
    mediaType: .video,
    position: .back
)
let device = discovery.devices.first

// Lock configuration before changing
try device?.lockForConfiguration()
device?.focusMode = .continuousAutoFocus
device?.exposureMode = .continuousAutoExposure
device?.unlockForConfiguration()
```

### AVAudioSession

`AVAudioSession` is a shared singleton that arbitrates audio routing and behaviour for the entire process.

**Categories** (most important):

| Category | Behaviour |
|----------|-----------|
| `.playback` | Audio plays even when silent switch is on / screen is locked |
| `.record` | Only recording; playback muted |
| `.playAndRecord` | Simultaneous play + record (VoIP, video call) |
| `.ambient` | Mixes with other audio; silenced by silent switch |
| `.soloAmbient` | Ducks other audio; silenced by silent switch (default) |

```swift
try AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
try AVAudioSession.sharedInstance().setActive(true)
```

**Interruptions** (phone calls, Siri): observe `AVAudioSession.interruptionNotification`. On `.began`, pause; on `.ended`, optionally resume if `shouldResume` is set.

### Picture-in-Picture (PiP)

Requires `AVPlayerViewController` (automatic) or `AVPictureInPictureController` (custom player):
1. Enable Background Modes → Audio, AirPlay, and Picture in Picture.
2. Set `AVAudioSession.category = .playback`.
3. `AVPictureInPictureController(playerLayer: layer)` for custom players.

## 4. Practical Usage

```swift
import AVFoundation
import AVKit
import UIKit

// ── Simple video player ───────────────────────────────────────
class VideoPlayerViewController: UIViewController {
    private var player: AVPlayer?
    private var playerLayer: AVPlayerLayer?
    private var timeObserver: Any?

    func loadVideo(url: URL) {
        let item = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: item)
        self.player = player

        let layer = AVPlayerLayer(player: player)
        layer.videoGravity = .resizeAspect
        view.layer.addSublayer(layer)
        playerLayer = layer

        // Observe readiness
        item.observe(\.status, options: [.new]) { [weak self] item, _ in
            if item.status == .readyToPlay {
                self?.player?.play()
            } else if item.status == .failed {
                print("Playback failed: \(item.error?.localizedDescription ?? "")")
            }
        }.store(in: &observations)

        // Progress
        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 0.5, preferredTimescale: 600),
            queue: .main
        ) { [weak self] time in
            self?.updateProgress(time: time)
        }

        setupAudioSession()
    }

    private func setupAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            print("Audio session error: \(error)")
        }
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        playerLayer?.frame = view.bounds
    }

    deinit {
        if let observer = timeObserver { player?.removeTimeObserver(observer) }
    }

    private func updateProgress(time: CMTime) {
        guard let duration = player?.currentItem?.duration, duration.isNumeric else { return }
        let progress = time.seconds / duration.seconds
        print("Progress: \(Int(progress * 100))%")
    }

    private var observations: [NSKeyValueObservation] = []
}

// ── Camera capture session ────────────────────────────────────
class CameraManager: NSObject {
    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "com.app.camera.session")
    private var photoOutput = AVCapturePhotoOutput()
    private var previewLayer: AVCaptureVideoPreviewLayer?

    var onPhotoCapture: ((UIImage) -> Void)?

    func setup(in view: UIView) {
        sessionQueue.async { [weak self] in
            self?.configureSession()
            DispatchQueue.main.async {
                self?.addPreviewLayer(to: view)
                self?.session.startRunning()
            }
        }
    }

    private func configureSession() {
        session.beginConfiguration()
        session.sessionPreset = .photo

        // Add camera input
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else {
            session.commitConfiguration(); return
        }
        session.addInput(input)

        // Add photo output
        if session.canAddOutput(photoOutput) {
            session.addOutput(photoOutput)
            photoOutput.isHighResolutionCaptureEnabled = true
        }

        session.commitConfiguration()
    }

    private func addPreviewLayer(to view: UIView) {
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        layer.frame = view.bounds
        view.layer.insertSublayer(layer, at: 0)
        previewLayer = layer
    }

    func capturePhoto() {
        sessionQueue.async { [weak self] in
            guard let self else { return }
            let settings = AVCapturePhotoSettings()
            settings.isHighResolutionPhotoEnabled = true
            self.photoOutput.capturePhoto(with: settings, delegate: self)
        }
    }

    func stop() {
        sessionQueue.async { self.session.stopRunning() }
    }
}

extension CameraManager: AVCapturePhotoCaptureDelegate {
    func photoOutput(_ output: AVCapturePhotoOutput,
                     didFinishProcessingPhoto photo: AVCapturePhoto,
                     error: Error?) {
        guard let data = photo.fileDataRepresentation(),
              let image = UIImage(data: data) else { return }
        DispatchQueue.main.async { self.onPhotoCapture?(image) }
    }
}

// ── Audio session interruption handling ───────────────────────
class AudioInterruptionHandler {
    private var player: AVPlayer?

    init(player: AVPlayer) {
        self.player = player
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleInterruption),
            name: AVAudioSession.interruptionNotification,
            object: nil
        )
    }

    @objc private func handleInterruption(_ notification: Notification) {
        guard let userInfo = notification.userInfo,
              let typeValue = userInfo[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: typeValue) else { return }

        switch type {
        case .began:
            player?.pause()
        case .ended:
            guard let optionsValue = userInfo[AVAudioSessionInterruptionOptionKey] as? UInt else { return }
            let options = AVAudioSession.InterruptionOptions(rawValue: optionsValue)
            if options.contains(.shouldResume) {
                player?.play()
            }
        @unknown default: break
        }
    }
}
```

## 5. Interview Questions & Answers

### Basic

**Q: What is the difference between `AVPlayerViewController` and a custom `AVPlayerLayer`?**

A: `AVPlayerViewController` is the system-provided full-featured playback UI: transport controls (play/pause, scrubbing, volume), AirPlay button, subtitles, audio track selection, and automatic Picture-in-Picture support. It requires minimal code and follows Apple's HIG. A custom `AVPlayerLayer` (a `CALayer` subclass that renders video frames) gives you complete control over the UI — custom scrubber design, gesture recognisers, overlay elements. You build all controls yourself. Use `AVPlayerViewController` for standard media playback (podcasts, video streaming). Use custom `AVPlayerLayer` when the design requires a non-standard player UI, when embedding video as a background element, or when tight integration with custom controls is needed.

**Q: What is AVAudioSession and why must you configure it before playing audio?**

A: `AVAudioSession` is a process-level singleton that tells iOS how your app uses audio — whether it should play when the silent switch is on, whether it should mix with other apps' audio or duck it, and whether the device's microphone is in use. Without configuration, the default category `.soloAmbient` is used, which means audio is silenced when the silent switch is on and stops if the screen locks. For a music or video app where playback should continue in the background and ignore the silent switch, you must set `.playback` category before starting the player. The audio session must also be activated (`setActive(true)`) to register your app's audio intent with the OS. Failing to configure AVAudioSession is a common cause of "audio works on Simulator but stops when the screen locks on device."

### Hard

**Q: How do you prevent dropped frames and UI hitches when configuring an AVCaptureSession?**

A: All `AVCaptureSession` configuration and `startRunning()`/`stopRunning()` calls are blocking — they can take 100ms+. Calling them on the main thread causes visible UI hitches and violates HIG. The correct pattern: (1) Create a dedicated serial background queue (`sessionQueue = DispatchQueue(label: "camera.session")`). (2) All session operations (`beginConfiguration`, `addInput`, `addOutput`, `commitConfiguration`, `startRunning`, `stopRunning`) go exclusively on this queue. (3) The preview layer (`AVCaptureVideoPreviewLayer`) is added to the view hierarchy on the main thread, but it reads from the session independently. (4) Delegate callbacks (photo capture, video frame, audio sample) are delivered on the session queue — dispatch UI updates to `DispatchQueue.main`. This pattern ensures the main thread remains responsive while camera operations execute in the background.

**Q: What happens to AVPlayer when an audio interruption begins (e.g., an incoming call)?**

A: When an interruption begins, iOS sends `AVAudioSession.interruptionNotification` with type `.began`. The system automatically pauses audio output, but `AVPlayer.rate` may not be set to 0 — the player may think it is still playing. Your interruption handler must explicitly call `player.pause()` to synchronise state. When the interruption ends (call dismissed), the notification fires with type `.ended` and optionally `shouldResume` in the options dictionary — only resume automatically if this flag is set (it's not always set; e.g., if another app began playing, you should not auto-resume to avoid competing audio). Additionally, after an interruption ends, `AVAudioSession` may no longer be active — call `setActive(true)` before resuming.

### Expert

**Q: How would you implement a camera app that supports simultaneous front and back camera capture (multi-camera)?**

A: Use `AVCaptureMultiCamSession` (iOS 13+), a subclass of `AVCaptureSession` that supports multiple camera inputs simultaneously. Key constraints: not all devices support multi-cam (check `AVCaptureMultiCamSession.isMultiCamSupported`); power consumption is significantly higher; only specific device/format combinations are supported (query `AVCaptureDeviceFormat.supportedMaxPhotoDimensions`). Architecture: (1) Create `AVCaptureMultiCamSession`. (2) Discover and add both `builtInWideAngleCamera` (front) and `builtInWideAngleCamera` (back) inputs. (3) Add two `AVCaptureVideoDataOutput` instances (one per camera), each with its own delegate. (4) Add two `AVCaptureVideoPreviewLayer` instances for the preview split view. (5) Run on the session queue. Each output's `setSampleBufferDelegate` delivers frames independently on a dedicated capture queue. Compose the two streams into a single output (e.g., picture-in-picture effect) using `CoreImage` or `Metal` frame-by-frame.

## 6. Common Issues & Solutions

**Issue: `AVPlayer` plays audio but shows a black screen (no video).**

Solution: `AVPlayerLayer` is not added to the view hierarchy, or its `frame` is zero. Ensure `playerLayer.frame = view.bounds` is set in `viewDidLayoutSubviews`, not `viewDidLoad` (bounds are not yet correct at `viewDidLoad`). Also verify the video track exists in the asset and the URL is valid.

**Issue: AVCaptureSession crashes with "session configuration is not committed".**

Solution: Ensure every `session.beginConfiguration()` is followed by `session.commitConfiguration()` even in error paths. Use a `defer { session.commitConfiguration() }` immediately after `beginConfiguration()` to guarantee the commit fires.

**Issue: Audio stops playing when the screen locks.**

Solution: The `AVAudioSession` category is `.soloAmbient` (default) or `.ambient`, both of which are silenced on screen lock. Set `AVAudioSession.sharedInstance().setCategory(.playback)` and add the **Audio, AirPlay, and Picture in Picture** background mode in Xcode's Signing & Capabilities.

**Issue: Camera permission is denied after the user previously granted it.**

Solution: Check `AVCaptureDevice.authorizationStatus(for: .video)`. If `.denied`, the OS will not re-present the permission dialog — you must direct the user to Settings. Present an alert with "Open Settings" that calls `UIApplication.shared.open(URL(string: UIApplication.openSettingsURLString)!)`.

## 7. Related Topics

- [App Lifecycle](app-lifecycle.md) — pause AVPlayer in `sceneWillResignActive`; stop capture session in background
- [Background Tasks](background-tasks.md) — background audio requires `.playback` audio session + background mode
- [Core Animation](core-animation.md) — `AVPlayerLayer` and `AVCaptureVideoPreviewLayer` are `CALayer` subclasses
- [UIView Lifecycle](../04-ui-frameworks/uiview-lifecycle.md) — set `playerLayer.frame` in `layoutSubviews`/`viewDidLayoutSubviews`
