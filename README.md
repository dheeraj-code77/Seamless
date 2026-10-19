# Seamless — High-Speed Local Wi-Fi Device Connectivity

**Seamless** is a personal, private device-connectivity application that connects an Android smartphone with a Windows laptop over your local Wi-Fi network. It enables high-speed, two-way file transfers without routing data through external cloud servers.

---

## Key Features

* **Approved Aesthetic Identity**: Preserves the warm cream background, organic paper grain overlay, deep forest green title bar, olive moss drag-and-drop zone (`#91AB75`), muted forest green action buttons (`#456F5B`), and soft sage photo picker (`#A8B99A`).
* **Zero-Tap QR Pairing**: The laptop shows a pairing QR code the moment the app opens. Scanning it on the phone connects and pairs the two devices automatically — no IP address, hostname or PIN typing.
* **Short-Lived Pairing Token**: The QR carries a single-use token that expires after 10 minutes. The permanent device credential is never shown on screen; it is exchanged server-side for a long-lived token.
* **Self-Refreshing QR**: The code refreshes every 60 seconds, so it always carries the laptop's current local address and a valid token even if the network changes.
* **Zero-Cloud, High-Speed Transfer**: Direct peer-to-peer streaming over local Wi-Fi (30–80+ MB/s over 5GHz Wi-Fi) with real-time speed counters, remaining ETA, and pause/resume/cancel controls.
* **Integrity Validation**: Real-time SHA-256 chunked hashing ensures files arrive bit-for-bit identical with zero corruption.
* **Path Traversal Security**: Strict directory sandboxing prevents directory escape attacks (`../../`) and automatically handles file collisions (`file (1).pdf`) without overwriting user data.
* **Zero-Configuration Discovery**: Automated UDP broadcast beacon on port `52400` allows devices to locate each other without typing IP addresses.
* **Manual PIN Fallback**: A 6-digit single-use PIN remains available inside **Pair New Device (PIN / QR)** if a phone cannot use the camera.
* **Transfer History**: Persistent local records with filenames, sizes, directions, and direct folder open actions.
* **Clipboard Synchronization**: Low-latency clipboard text sharing across linked devices.

---

## Project Structure

```
SEAMLESS/
├── preview.html                     # Original approved visual design prototype
├── Seamless.bat                     # Double-click launcher for Windows desktop client
├── Seamless.vbs                     # Silent background launcher (no terminal window)
├── README.md                        # Project documentation and setup guide
│
├── shared/                          # Shared data contracts and protocols
│   ├── protocol.json                # JSON Schema for beacons, pairing, and headers
│   └── README.md
│
├── windows-app/                     # Windows Desktop Application
│   ├── src/
│   │   ├── main.py                  # Desktop application launcher & Edge App mode window
│   │   ├── core/
│   │   │   ├── server.py            # Local HTTP server, chunked streaming, API routing
│   │   │   ├── discovery.py         # UDP broadcast beacon (Port 52400)
│   │   │   ├── security.py          # 6-digit PIN, token auth, path sanitization, SHA-256
│   │   │   ├── transfer_engine.py   # Live throughput calculation, pause/cancel state
│   │   │   ├── history.py           # Persistent JSON transfer history
│   │   │   └── config.py            # Local IP detection & download folder config
│   │   └── renderer/
│   │       ├── index.html           # Desktop interface (matching approved design)
│   │       └── app.js               # Frontend controller & real-time polling logic
│   └── README.md
│
├── android-app/                     # Android Mobile Application
│   ├── src/
│   │   ├── index.html               # Mobile interface (matching approved design)
│   │   └── mobile-app.js            # Mobile upload engine & PIN verification
│   └── android/                     # Native Android Studio Project
│       └── app/src/main/
│           ├── AndroidManifest.xml  # Wi-Fi & storage permissions
│           └── java/com/seamless/app/MainActivity.java
│
└── tests/
    └── test_core.py                 # Automated unit and integration test suite
```

---

## Installation

### Windows
1. Download **`Seamless.exe`** from the [latest release](https://github.com/dheeraj-code77/Seamless/releases/latest).
2. Double-click it. No Python installation is required — the app is a standalone executable.
3. Windows SmartScreen may show a blue "Windows protected your PC" panel. Click **More info → Run anyway**.

The app opens in its own window (Microsoft Edge App Mode, or your default browser) and starts a local service on port `5173`.

### Android
1. Download **`Seamless.apk`** from the [latest release](https://github.com/dheeraj-code77/Seamless/releases/latest).
2. Open the file on your phone and allow installs from your file manager / browser when prompted.
3. Grant camera access the first time you use the scanner.

Requires Android 5.0 (API 21) or newer.

---

## How to Run Seamless

### 1. Launch on Windows
Download `Seamless.exe` and double-click it. The window shows a **Scan to Pair** panel with a live QR code and your laptop's Wi-Fi address.

To run from source instead:
```powershell
python -m pip install -r requirements.txt
python windows-app\src\main.py
```
(`Seamless.bat` and `Seamless.vbs` in the repository root are convenience launchers for the source version.)

### 2. Connect Your Android Phone
1. Put your phone and laptop on the **same local Wi-Fi network**.
2. Open the **Seamless** app on your phone.
3. Tap **Scan QR Code** and point the camera at the QR code in the Windows app.
4. The phone reads the code, connects to the laptop and pairs automatically. Both apps show a **Connected** status.
5. Tap **Send Photos** or **Send Files** on the phone — the file streams straight into `Downloads\Seamless` on the laptop.

No IP address, hostname or PIN entry is required. The QR code carries a short-lived pairing token that is exchanged for a device credential automatically; it expires after 10 minutes and can only be redeemed once, and the Windows screen refreshes the code every minute so the address and token stay current.

**Fallbacks**
* If the camera is unavailable, use **Pair New Device (PIN / QR)** on the laptop and enter the one-time 6-digit PIN on the phone.
* A browser client is also served at `http://<YOUR_LAPTOP_IP>:5173/mobile` (the laptop IP is shown in the Windows title bar).

**Troubleshooting**
* *"Laptop not reachable"* — both devices must be on the same Wi-Fi; the laptop firewall may need to allow the app on private networks.
* *"This pairing code has expired"* — the code on screen rotated; scan the current one.
* *"The QR code does not contain a valid local laptop address"* — only private IPv4 addresses (10.x, 172.16–31.x, 192.168.x) are accepted.

---

## Verifying the Test Suite

All core security, streaming, and pairing logic has automated test coverage:
```powershell
python tests\test_core.py
```
This tests:
1. Single-use 6-digit PIN handshake.
2. Short-lived, single-use QR pairing token lifecycle (expiry, replay rejection, token count cap).
3. That the rendered QR image provably encodes the live pairing token.
4. Zero-touch QR pairing followed by a file upload from the newly paired device.
5. Path sanitization and directory traversal prevention.
6. Safe unique destination naming on filename collisions.
7. Live HTTP streaming upload with SHA-256 validation.

The suite runs against a throwaway configuration, so it never touches your real settings or paired devices.

---

## Building From Source

### Windows executable
```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean Seamless.spec
```
Output: `dist\Seamless.exe`

### Android APK
Requires the Android SDK (platform `android-33`, build-tools `30.0.3`) and Gradle 6.7.1.
```powershell
# android-app/android/local.properties must point at your SDK
sdk.dir=C\:\\path\\to\\Android\\Sdk

gradle assembleRelease
```
Output: `android-app\android\app\build\outputs\apk\release\app-release.apk`

Release signing reads `android-app/android/keystore.properties`, which is deliberately **not** committed. Without it the build still succeeds but produces an unsigned APK.
