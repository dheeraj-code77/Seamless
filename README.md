# Seamless — High-Speed Local Wi-Fi Device Connectivity

**Seamless** is a personal, private device-connectivity application that connects an Android smartphone with a Windows laptop over your local Wi-Fi network. It enables high-speed, two-way file transfers without routing data through external cloud servers.

---

## Key Features

* **Approved Aesthetic Identity**: Preserves the warm cream background, organic paper grain overlay, deep forest green title bar, olive moss drag-and-drop zone (`#91AB75`), muted forest green action buttons (`#456F5B`), and soft sage photo picker (`#A8B99A`).
* **Zero-Cloud, High-Speed Transfer**: Direct peer-to-peer streaming over local Wi-Fi (30–80+ MB/s over 5GHz Wi-Fi) with real-time speed counters, remaining ETA, and pause/resume/cancel controls.
* **Integrity Validation**: Real-time SHA-256 chunked hashing ensures files arrive bit-for-bit identical with zero corruption.
* **Path Traversal Security**: Strict directory sandboxing prevents directory escape attacks (`../../`) and automatically handles file collisions (`file (1).pdf`) without overwriting user data.
* **Zero-Configuration Discovery**: Automated UDP broadcast beacon on port `52400` allows devices to locate each other without typing IP addresses.
* **Secure Handshake**: 6-digit numeric PIN single-use authentication prevents unauthorized peers on your Wi-Fi from connecting.
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

## How to Run Seamless

### 1. Launch on Windows
You can run Seamless on your laptop in two ways:
* **Option A**: Double-click **`Seamless.bat`** in this folder.
* **Option B**: Double-click **`Seamless.vbs`** for a clean, borderless window with no console popup.
* **Option C**: From your terminal:
  ```powershell
  python -m pip install -r requirements.txt
  python windows-app\src\main.py
  ```

Seamless will automatically launch in a dedicated application window via Microsoft Edge App Mode (or your default browser) at `http://localhost:5173`.

### 2. Connect Your Android Phone
1. Ensure your Android phone and Windows laptop are connected to the **same local Wi-Fi network**.
2. Open the Seamless Android app and tap **Scan QR Code**.
3. In the Windows app, open **Pair New Device (PIN / QR)** and scan its QR code with the Android app. The QR contains only the laptop's local IP address, port, and public device identifier; it does not contain the pairing PIN or authentication token.
4. Enter the one-time 6-digit PIN shown in the Windows pairing dialog in the Android app. The PIN expires after five minutes and can only be used once.
5. If you prefer the existing browser method, open Chrome or Samsung Internet and browse to:
   ```
   http://<YOUR_LAPTOP_IP>:5173/mobile
   ```
   *(Your laptop's local IP address is clearly shown in the top-left titlebar of the Windows app).*
6. Tap the **Pair** button and enter the 6-digit PIN displayed on your laptop to link them.
7. Tap **Send Files** or **Send Photos** on your phone: the file will stream straight to your laptop's `Downloads\Seamless` folder!

The native scanner accepts Seamless QR codes for private local IPv4 addresses only and verifies the laptop's device identifier before opening the PIN prompt. If scanning or connecting fails, check that both devices are on the same Wi-Fi network and that Seamless is running on Windows. The browser connection remains available as a fallback.

---

## Verifying the Test Suite

All core security, streaming, and pairing logic has automated test coverage:
```powershell
python tests\test_core.py
```
This tests:
1. Single-use 6-digit PIN handshake.
2. Path sanitization and directory traversal prevention.
3. Safe unique destination naming on filename collisions.
4. Live HTTP streaming upload with SHA-256 validation.
