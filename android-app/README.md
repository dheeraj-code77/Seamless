# Seamless Android Application

The mobile client. It is a native Android shell that hosts the mobile web
interface, plus a camera scanner for the pairing QR code.

## Layout

```
src/
├── index.html          Mobile interface
├── mobile-app.js       Pairing, upload engine, clipboard sync
├── manifest.json       Web app manifest
├── icon.png            192px application mark
└── icon-512.png        512px application mark

android/                Gradle project
└── app/src/main/
    ├── AndroidManifest.xml
    ├── java/com/seamless/app/MainActivity.java
    └── res/drawable/ic_launcher.xml
```

## How it runs

`MainActivity` creates a `WebView`, points it at the mobile interface bundled
in the APK assets, and exposes a small JavaScript bridge:

| Bridge call | What it does |
| --- | --- |
| `startQrScan()` | Opens the camera scanner |
| `getClipboard()` | Reads the Android clipboard |
| `setClipboard(text)` | Writes the Android clipboard |
| `pairingCompleted(name)` | Reports a finished pairing to the interface |

## The pairing scanner

Scanning a code parses the JSON payload, checks that the app tag and version
match and that the address is a private IPv4 address, then confirms the
laptop's identity against `/api/device/info` before redeeming the pairing
token through `/api/pair/exchange`.

The scanner is the ZXing capture activity from `zxing-android-embedded`. It
declares itself as landscape, so `AndroidManifest.xml` overrides the
orientation to portrait — a QR code held up in portrait would otherwise be
scanned sideways.

## Clipboard sync

Android only lets an app read the clipboard while it is in the foreground, so
the interface syncs on a timer and pauses when the app is hidden. The phone
pushes text to the laptop and pulls the laptop's text back; a repeated payload
is ignored on both sides so the two devices do not push the same text back and
forth.
