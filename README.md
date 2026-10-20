# Seamless

Local Wi-Fi file transfer between an Android phone and a Windows laptop. The two
devices talk to each other directly over your router, so nothing is uploaded to
a cloud service and the app works without an internet connection.

The Windows side listens on port `5173` and announces itself over UDP `52400`.

## What it does

- **Pair by QR code.** The laptop shows a QR code, the phone scans it, and the
  two devices pair without typing anything. A 6-digit PIN is available as a
  fallback.
- **Send files both ways.** Photos and documents stream between the phone and
  the laptop with live progress, speed and pause/cancel controls. SHA-256 is
  verified on arrival.
- **Share the clipboard.** Copy text on either device and paste it on the other.
- **Keep a transfer history.** File name, size and direction are recorded
  locally.

## What is covered by tests

`tests/test_core.py` and `tests/test_e2e_full.py` run against a throwaway
configuration, so your own settings and paired devices are never touched.

| Area | Checked behaviour |
| --- | --- |
| QR pairing | Every rendered code carries a fresh single-use token; invalid and replayed tokens are rejected with `401`; a device that paired by QR can upload straight away |
| File transfer | Chunked upload arrives byte-for-byte identical, with the SHA-256 confirmed against the file on disk |
| Clipboard sync | Text pushed from the phone is applied on the laptop and pulled back unchanged; repeated payloads are ignored so the two sides do not loop |
| Access control | Uploads and clipboard reads from a device that has not paired are rejected with `401` |
| Path safety | `../../` in a filename is neutralised, and a name collision gets a unique suffix instead of overwriting a file |
| Transfer folder | An untouched default location moves to the current default; a folder you chose yourself is left alone |

```powershell
python tests\test_core.py       # unit + live HTTP integration
python tests\test_e2e_full.py   # end-to-end against dist\Seamless.exe
```

### Not covered by automation

The camera scanner, clipboard bridging between two physical devices, and real
transfer throughput need a real phone and laptop on the same network. The HTTP
flows behind them are tested; the hardware path has not been exercised
end-to-end.

## Requirements

- **Windows** — Windows 10 or 11. The release build is a standalone executable,
  so Python is not needed to run it.
- **Android** — Android 5.0 (API 21) or newer, with camera permission for the
  scanner.

Both devices must be on the same local Wi-Fi network.

## Install

### Windows

1. Download `Seamless.exe` from the [latest release](https://github.com/dheeraj-code77/Seamless/releases/latest).
2. Open it. Windows may show *"Windows protected your PC"* because the build is
   unsigned — choose **More info → Run anyway**.

The window opens on its own (Microsoft Edge app mode, falling back to your
default browser) and the app starts listening on port `5173`.

### Android

1. Download `Seamless.apk` from the [latest release](https://github.com/dheeraj-code77/Seamless/releases/latest).
2. Open the file on your phone and allow installation from your file manager
   when Android asks.
3. Grant camera access the first time you scan a pairing code.

## Use

1. Start Seamless on the laptop. The **Scan to Pair** panel shows a QR code and
   the laptop's local address.
2. On the phone, tap **Scan QR Code** and point the camera at the laptop.
3. The phone connects and pairs by itself; both sides list the other device.
4. Send with **Send Photos** / **Send Files** on the phone, or drag a file onto
   the drop zone in the Windows window to send it the other way.

The QR code carries a token that is valid for 10 minutes and can be redeemed
once. The Windows window redraws it every minute, so the address and token stay
current. If the camera is unavailable, use **Pair New Device (PIN / QR)** on the
laptop and enter the one-time 6-digit PIN on the phone.

### Where received files go

Files arrive in `Desktop\Seamless Transfer`, created on first run. An install
that still had the old `Downloads\Seamless` default moves to the new folder on
its next launch, and anything already downloaded stays where it is.

A different location can be set through the `POST /api/settings/folder`
endpoint; the choice is preserved across restarts.

## Build from source

Windows executable:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean Seamless.spec
```

Output: `dist\Seamless.exe`

Android APK — needs the Android SDK (platform `android-33`, build-tools
`30.0.3`) and Gradle 6.7.1. Point `android-app/android/local.properties` at
your SDK, then:

```powershell
cd android-app\android
gradle assembleRelease
```

Output: `android-app\android\app\build\outputs\apk\release\app-release.apk`

Release signing reads `android-app/android/keystore.properties`, which is not
committed. Without it the build still succeeds but produces an unsigned APK.

The application icons come from a single source file:

```powershell
python tools\make_icons.py
```

## Troubleshooting

- **"Laptop not reachable"** — both devices must be on the same Wi-Fi network.
  Windows Firewall may need to allow the app on private networks.
- **"This pairing code has expired"** — the code on screen rotates; scan the
  current one.
- **"The QR code does not contain a valid local laptop address"** — only private
  IPv4 addresses (`10.x`, `172.16–31.x`, `192.168.x`) are accepted.
- **Clipboard does not sync** — Android only lets the app read the clipboard
  while it is in the foreground, so sync pauses when you switch away.
