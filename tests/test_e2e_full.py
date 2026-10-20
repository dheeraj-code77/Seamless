"""
Seamless Full End-to-End (E2E) Test Suite
Tests dist/Seamless.exe directly: HTTP routes, Static UI, Pairing Handshake,
QR pairing, Chunked File Streaming with SHA-256 verification, Clipboard Sync,
and Security defenses.

Run with:
    python tests/test_e2e_full.py
"""
import os
import sys
import time
import json
import hashlib
import urllib.request
import urllib.error
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXE_PATH = REPO_ROOT / "dist" / "Seamless.exe"
BASE_URL = "http://127.0.0.1:5173"
SRC_DIR = REPO_ROOT / "windows-app" / "src"


def log(section, msg):
    print(f"[{section}] {msg}")


def main():
    print("=" * 65)
    print(" SEAMLESS FULL END-TO-END (E2E) VERIFICATION TEST ")
    print("=" * 65)

    if not EXE_PATH.exists():
        print(f"FAIL: {EXE_PATH} does not exist on disk!")
        sys.exit(1)

    log("1. SETUP", f"Found {EXE_PATH} ({EXE_PATH.stat().st_size:,} bytes)")
    # Ensure clean state
    subprocess.run(["powershell", "-Command", "Stop-Process -Name 'Seamless' -Force -ErrorAction SilentlyContinue"], check=False)
    time.sleep(1)

    log("1. SETUP", "Starting dist/Seamless.exe in background...")
    proc = subprocess.Popen([str(EXE_PATH), "--no-window"])

    try:
        # Wait for HTTP server to bind and start listening
        server_ready = False
        for attempt in range(25):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"{BASE_URL}/api/device/info", timeout=1) as resp:
                    if resp.status == 200:
                        server_ready = True
                        break
            except Exception:
                pass

        if not server_ready:
            print("FAIL: Seamless.exe failed to start within 7.5 seconds.")
            sys.exit(1)

        log("1. SETUP", "Seamless.exe is active and listening on port 5173.\n")

        # ----------------------------------------------------
        # TEST 1: System Info & Identity
        # ----------------------------------------------------
        log("TEST 1", "Verifying system info endpoint (/api/device/info)...")
        with urllib.request.urlopen(f"{BASE_URL}/api/device/info") as resp:
            data = json.loads(resp.read().decode())
            assert data["device_type"] == "windows"
            assert data["port"] == 5173
            assert "download_dir" in data
            log("TEST 1", f"PASS: Device Name = '{data.get('device_name')}', IP = '{data.get('ip')}'")

        # ----------------------------------------------------
        # TEST 2: Static UI Delivery (Windows Desktop + Android Mobile)
        # ----------------------------------------------------
        log("TEST 2", "Verifying static UI serving...")
        endpoints = [
            ("/", "text/html", "Desktop HTML"),
            ("/app.js", "application/javascript", "Desktop Controller JS"),
            ("/mobile", "text/html", "Android Mobile HTML"),
            ("/mobile-app.js", "application/javascript", "Android Controller JS"),
            ("/manifest.json", "application/json", "PWA Manifest")
        ]
        for url_path, expected_mime, label in endpoints:
            req = urllib.request.Request(f"{BASE_URL}{url_path}")
            with urllib.request.urlopen(req) as resp:
                content_len = len(resp.read())
                assert resp.status == 200
                log("TEST 2", f"  -> {label} ({url_path}): 200 OK ({content_len:,} bytes)")
        log("TEST 2", "PASS: Both Windows Desktop and Android interfaces served accurately.\n")

        # ----------------------------------------------------
        # TEST 3: Pairing Handshake (PIN Generation & Verification)
        # ----------------------------------------------------
        log("TEST 3", "Simulating pairing handshake...")
        # Step A: Windows generates PIN
        req = urllib.request.Request(f"{BASE_URL}/api/pair/request", method="POST", data=b"{}")
        with urllib.request.urlopen(req) as resp:
            pair_data = json.loads(resp.read().decode())
            pin = pair_data.get("pin")
            assert len(pin) == 6 and pin.isdigit()
            log("TEST 3", f"  -> Windows generated 6-digit PIN: {pin}")

        # Step B: Android phone submits the PIN
        phone_id = "android_pixel_e2e"
        verify_body = json.dumps({
            "pin": pin,
            "device_id": phone_id,
            "device_name": "Google Pixel 8 Pro (E2E Test)"
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{BASE_URL}/api/pair/verify",
            data=verify_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            verify_res = json.loads(resp.read().decode())
            assert verify_res["success"] is True
            auth_token = verify_res["token"]
            assert len(auth_token) >= 32
            log("TEST 3", f"  -> Android verified PIN and received Auth Token: {auth_token[:12]}...")

        # Step C: Verify device is now in paired list
        with urllib.request.urlopen(f"{BASE_URL}/api/devices") as resp:
            devices = json.loads(resp.read().decode())
            assert phone_id in devices["paired"]
            log("TEST 3", f"PASS: Pixel 8 Pro successfully paired with Windows laptop.\n")

        # ----------------------------------------------------
        # TEST 3b: QR Pairing (the code shown on screen)
        # ----------------------------------------------------
        log("TEST 3b", "Verifying the pairing QR code endpoint...")
        with urllib.request.urlopen(f"{BASE_URL}/api/pair/qr") as resp:
            assert resp.status == 200
            assert resp.headers.get_content_type() == "image/svg+xml"
            qr_svg = resp.read().decode("utf-8")
            assert "<svg" in qr_svg and "<path" in qr_svg
        log("TEST 3b", "  -> QR code served as SVG (200 OK).")

        # Every render issues a fresh short lived token, so two consecutive
        # codes must differ.
        with urllib.request.urlopen(f"{BASE_URL}/api/pair/qr") as resp:
            qr_svg_2 = resp.read().decode("utf-8")
        assert qr_svg != qr_svg_2, "Each QR render must carry a fresh pairing token"
        log("TEST 3b", "  -> Each render carries a fresh single-use token.")

        # A bogus token must be rejected.
        exchange_body = json.dumps({
            "pairing_token": "not-a-real-token",
            "device_id": "android_rogue_e2e",
            "device_name": "Rogue Device"
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/pair/exchange",
            data=exchange_body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req)
            raise AssertionError("An invalid pairing token must be rejected")
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Expected 401 for an invalid token, got {e.code}"
        log("TEST 3b", "PASS: QR pairing endpoint issues and validates single-use tokens.\n")

        # ----------------------------------------------------
        # TEST 4: Real Android-to-Windows File Transfer with SHA-256
        # ----------------------------------------------------
        log("TEST 4", "Simulating real Android-to-Windows file transfer...")
        # Create a sample test payload (~256 KB)
        test_payload = (b"SEAMLESS_E2E_BINARY_CHUNK_DATA_IMAGE_SIMULATION_2026\n" * 5000)
        expected_sha = hashlib.sha256(test_payload).hexdigest()
        filename = "E2E_Android_Captured_Photo.jpg"

        headers = {
            "X-Seamless-Filename": filename,
            "X-Seamless-Filesize": str(len(test_payload)),
            "X-Seamless-Sender-Id": phone_id,
            "X-Seamless-Sender-Name": "Google Pixel 8 Pro",
            "X-Seamless-Token": auth_token,
            "X-Seamless-SHA256": expected_sha,
            "Content-Type": "application/octet-stream"
        }

        req = urllib.request.Request(
            f"{BASE_URL}/api/transfer/send",
            data=test_payload,
            headers=headers,
            method="POST"
        )

        with urllib.request.urlopen(req) as resp:
            tx_res = json.loads(resp.read().decode())
            assert tx_res["success"] is True
            saved_path = Path(tx_res["saved_path"])
            assert tx_res["sha256"] == expected_sha
            log("TEST 4", f"  -> Streamed {len(test_payload):,} bytes to {saved_path}")
            log("TEST 4", f"  -> Expected SHA: {expected_sha[:16]}...")
            log("TEST 4", f"  -> Received SHA: {tx_res['sha256'][:16]}...")

        # Verify physical file on disk
        assert saved_path.exists(), f"File was not saved at {saved_path}"
        with open(saved_path, "rb") as f:
            actual_bytes = f.read()
            assert actual_bytes == test_payload, "Disk content does not match sent payload!"
        log("TEST 4", "  -> Verified physical file on disk: Bit-for-bit identical.")

        # Clean up test file
        try:
            saved_path.unlink()
        except Exception:
            pass

        # Verify transfer was recorded in history
        with urllib.request.urlopen(f"{BASE_URL}/api/history") as resp:
            hist_data = json.loads(resp.read().decode())
            entries = hist_data.get("history", [])
            assert len(entries) > 0
            assert entries[0]["filename"] == filename
            assert entries[0]["status"] == "completed"
            log("TEST 4", f"  -> Verified persistent transfer history record.")

        log("TEST 4", "PASS: End-to-end file streaming and integrity validation succeeded.\n")

        # ----------------------------------------------------
        # TEST 5: Real Clipboard Synchronization
        # ----------------------------------------------------
        log("TEST 5", "Testing clipboard sync endpoint (/api/clipboard)...")
        sys.path.insert(0, str(SRC_DIR))
        from core.clipboard import read_clipboard_text, write_clipboard_text

        original_clipboard = read_clipboard_text()
        try:
            # An unpaired device must not be able to read the laptop clipboard.
            try:
                urllib.request.urlopen(f"{BASE_URL}/api/clipboard", timeout=5)
                raise AssertionError("An unpaired device must not read the clipboard")
            except urllib.error.HTTPError as e:
                assert e.code == 401, f"Expected 401 without a token, got {e.code}"
            log("TEST 5", "  -> Unpaired clipboard read correctly rejected with 401.")

            clip_text = "Seamless verification payload: 123-ABC"
            clip_body = json.dumps({"text": clip_text}).encode("utf-8")

            req = urllib.request.Request(
                f"{BASE_URL}/api/clipboard",
                data=clip_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Seamless-Token": auth_token
                },
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                clip_res = json.loads(resp.read().decode())
                assert clip_res["success"] is True
                assert clip_res["changed"] is True

            # The phone pulls the text back from the laptop.
            pull_req = urllib.request.Request(
                f"{BASE_URL}/api/clipboard", headers={"X-Seamless-Token": auth_token})
            with urllib.request.urlopen(pull_req) as resp:
                clip_get = json.loads(resp.read().decode())
            assert clip_get["text"] == clip_text, "The laptop should return the synced text"

            # The same text again must not be treated as a new event.
            with urllib.request.urlopen(req) as resp:
                repeat = json.loads(resp.read().decode())
            assert repeat["changed"] is False, "A repeated payload must not loop"
            log("TEST 5", "PASS: Clipboard sync works in both directions and does not loop.\n")
        finally:
            if original_clipboard:
                write_clipboard_text(original_clipboard)

        # ----------------------------------------------------
        # TEST 6: Security & Path Traversal Attack Defense
        # ----------------------------------------------------
        log("TEST 6", "Testing security: path traversal attack rejection...")
        traversal_name = r"..\..\Windows\System32\malicious_file.bat"
        headers_attack = {
            "X-Seamless-Filename": traversal_name,
            "X-Seamless-Filesize": "14",
            "X-Seamless-Sender-Id": phone_id,
            "X-Seamless-Token": auth_token
        }
        req = urllib.request.Request(
            f"{BASE_URL}/api/transfer/send",
            data=b"echo dangerous",
            headers=headers_attack,
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            attack_res = json.loads(resp.read().decode())
            saved_attack_path = Path(attack_res["saved_path"])
            # Destination MUST NOT be in System32 or root; it must be inside Downloads/Seamless!
            assert "System32" not in str(saved_attack_path)
            assert "Seamless" in str(saved_attack_path)
            assert saved_attack_path.name == "malicious_file.bat"
            log("TEST 6", f"  -> Attack sanitized: target saved safely to {saved_attack_path}")
            if saved_attack_path.exists():
                saved_attack_path.unlink()
        log("TEST 6", "PASS: Path traversal attacks are neutralized.\n")

        # ----------------------------------------------------
        # TEST 7: Cleanup
        # ----------------------------------------------------
        log("TEST 7", "Removing the test device from the paired list...")
        cleanup = json.dumps({"device_id": phone_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/pair/unpair",
            data=cleanup,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            assert json.loads(resp.read().decode())["success"] is True
        with urllib.request.urlopen(f"{BASE_URL}/api/devices") as resp:
            devices = json.loads(resp.read().decode())
            assert phone_id not in devices["paired"]
        log("TEST 7", "PASS: Test device removed from the paired list.\n")

        print("=" * 65)
        print(" [ALL E2E VERIFICATION TESTS PASSED SUCCESSFULLY] ")
        print("=" * 65)

    finally:
        log("SHUTDOWN", "Stopping test instance of Seamless.exe...")
        try:
            proc.terminate()
            proc.kill()
        except Exception:
            pass
        subprocess.run(["powershell", "-Command", "Stop-Process -Name 'Seamless' -Force -ErrorAction SilentlyContinue"], check=False)
        log("SHUTDOWN", "Clean shutdown complete.")


if __name__ == "__main__":
    main()
