"""
Seamless Windows Core Unit & Integration Tests
"""
import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import hashlib
import tempfile
import threading
from pathlib import Path

# Run against a throwaway configuration so the real user settings and paired
# devices are never touched by the test suite. This must happen before the
# core modules are imported, because they read APPDATA at import time.
_TEST_APP_DATA = tempfile.mkdtemp(prefix="seamless-tests-")
os.environ["APPDATA"] = _TEST_APP_DATA

# Add windows-app/src to search path
SRC_DIR = Path(__file__).resolve().parent.parent / "windows-app" / "src"
sys.path.insert(0, str(SRC_DIR))

from core.security import SecurityManager
from core.history import HistoryManager
from core.transfer_engine import TransferEngine
from core.config import get_local_ip
from core.server import (
    create_pairing_qr_payload,
    create_pairing_qr_svg,
    run_server,
)


def test_pairing_token_lifecycle():
    print("[Test] Running QR pairing token lifecycle tests...")
    sec = SecurityManager()

    token = sec.generate_pairing_token()
    assert len(token) >= 32, "Pairing token should be long enough to resist guessing"
    assert sec.verify_pairing_token(token) is True, "A fresh token must verify"
    assert sec.verify_pairing_token(token) is False, "A token must be single-use"

    assert sec.verify_pairing_token("wrong-token") is False
    assert sec.verify_pairing_token("") is False

    expired = sec.generate_pairing_token(lifetime_sec=-1)
    assert sec.verify_pairing_token(expired) is False, "An expired token must be rejected"

    # Only a small number of tokens stay valid so old codes die out quickly.
    for _ in range(10):
        sec.generate_pairing_token()
    assert len(sec.pairing_tokens) <= SecurityManager.MAX_PAIRING_TOKENS, \
        "Too many pairing tokens would keep stale codes alive"

    print("  -> QR pairing token lifecycle passed!")


def test_security_manager():
    print("[Test] Running SecurityManager tests...")
    sec = SecurityManager()

    # 1. PIN generation & verification
    pin = sec.generate_pin()
    assert len(pin) == 6, f"PIN should be 6 digits, got {pin}"
    assert pin.isdigit(), "PIN should be numeric"
    assert sec.verify_pin(pin) is True, "Valid PIN verification failed"
    assert sec.verify_pin(pin) is False, "PIN should be single-use"

    # 2. Path sanitization
    traversal_input = "../../etc/shadow"
    safe = sec.sanitize_filename(traversal_input)
    assert "/" not in safe and "\\" not in safe, f"Path traversal not sanitized: {safe}"
    assert safe == "shadow", f"Expected 'shadow', got '{safe}'"

    win_traversal = r"..\..\Windows\System32\cmd.exe"
    safe_win = sec.sanitize_filename(win_traversal)
    assert "/" not in safe_win and "\\" not in safe_win, f"Windows traversal not sanitized: {safe_win}"
    assert safe_win == "cmd.exe", f"Expected 'cmd.exe', got '{safe_win}'"

    # 3. Collision avoidance
    with tempfile.TemporaryDirectory() as tmpdir:
        dest1 = sec.get_safe_destination_path(tmpdir, "report.pdf")
        assert dest1.name == "report.pdf"
        dest1.touch()

        dest2 = sec.get_safe_destination_path(tmpdir, "report.pdf")
        assert dest2.name == "report (1).pdf"
        dest2.touch()

        dest3 = sec.get_safe_destination_path(tmpdir, "report.pdf")
        assert dest3.name == "report (2).pdf"

    print("  -> SecurityManager passed!")


def test_transfer_engine_and_history():
    print("[Test] Running TransferEngine & HistoryManager tests...")
    with tempfile.TemporaryDirectory() as tmpdir:
        hist_mgr = HistoryManager()
        hist_mgr.file_path = Path(tmpdir) / "test_history.json"
        engine = TransferEngine(hist_mgr)

        engine.start_transfer("tx_01", "video.mp4", 1000, "incoming", "phone_1", "Pixel 8")
        engine.update_progress(500)
        status = engine.get_status()
        assert status["progress_percent"] == 50.0, f"Expected 50%, got {status['progress_percent']}"
        assert status["status"] == "transferring"

        engine.complete_transfer("/path/to/video.mp4", "fake_sha")
        history = hist_mgr.get_entries()
        assert len(history) == 1
        assert history[0]["filename"] == "video.mp4"
        assert history[0]["status"] == "completed"

    print("  -> TransferEngine & HistoryManager passed!")


def test_server_api_and_file_transfer():
    print("[Test] Running live HTTP Server & File Transfer tests...")
    test_port = 59123
    server = run_server(port=test_port, renderer_dir=SRC_DIR / "renderer")
    # Keep test downloads out of the user's real save folder.
    test_download_dir = tempfile.mkdtemp(prefix="seamless-test-downloads-")
    server.config["download_dir"] = test_download_dir
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    base_url = f"http://127.0.0.1:{test_port}"

    try:
        # 1. Device Info
        req = urllib.request.urlopen(f"{base_url}/api/device/info")
        data = json.loads(req.read().decode())
        assert data["device_type"] == "windows"
        assert data["port"] == 5173 or data["port"] == test_port

        # 1b. QR Pairing Code
        qr_payload = json.loads(create_pairing_qr_payload(
            data["ip"], data["port"], data["device_id"]
        ))
        assert qr_payload == {
            "app": "seamless",
            "version": 1,
            "host": data["ip"],
            "port": test_port,
            "device_id": data["device_id"]
        }

        # 1c. Prove the rendered QR really encodes the minted pairing token.
        with urllib.request.urlopen(f"{base_url}/api/pair/qr") as response:
            qr_svg = response.read().decode("utf-8")
            assert response.headers.get_content_type() == "image/svg+xml"
            assert response.headers.get("Cache-Control") == "no-store"
            assert "<svg" in qr_svg and "<path" in qr_svg
            assert "token" not in qr_svg.lower() and "pin" not in qr_svg.lower()

        # Exactly one token was minted for that code, so we know what it encodes.
        minted = list(server.security.pairing_tokens.keys())
        assert len(minted) == 1, f"Expected one live pairing token, got {len(minted)}"
        scanned_token = minted[0]

        # Re-render the same payload locally: an identical SVG proves the code on
        # screen carries the host, port, device id and the pairing token.
        expected_svg = create_pairing_qr_svg(create_pairing_qr_payload(
            get_local_ip(), test_port, data["device_id"], scanned_token
        )).decode("utf-8")
        assert qr_svg == expected_svg, "The QR image must encode the live pairing token"

        # 2. Pairing Flow
        req = urllib.request.Request(f"{base_url}/api/pair/request", method="POST", data=b"{}")
        pair_res = json.loads(urllib.request.urlopen(req).read().decode())
        pin = pair_res["pin"]
        assert len(pin) == 6

        # 2a. Zero-touch QR pairing: the phone redeems the token it read from the
        # QR code, exactly like the real scan flow.
        exchange_payload = json.dumps({
            "pairing_token": scanned_token,
            "device_id": "qr_phone",
            "device_name": "QR Test Phone"
        }).encode()
        exchange_req = urllib.request.Request(
            f"{base_url}/api/pair/exchange", method="POST",
            data=exchange_payload, headers={"Content-Type": "application/json"})
        exchange_res = json.loads(urllib.request.urlopen(exchange_req).read().decode())
        assert exchange_res["success"] is True, "QR token exchange should succeed"
        qr_auth_token = exchange_res["token"]
        assert len(qr_auth_token) > 10

        # The QR token is single-use: replaying it must be rejected.
        try:
            urllib.request.urlopen(exchange_req)
            raise AssertionError("A redeemed QR token must not be reusable")
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Expected 401 for a replayed token, got {e.code}"

        # An unknown token must be rejected as well.
        bogus_req = urllib.request.Request(
            f"{base_url}/api/pair/exchange", method="POST",
            data=json.dumps({"pairing_token": "not-a-real-token", "device_id": "qr_phone2"}).encode(),
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(bogus_req)
            raise AssertionError("An invalid QR token must be rejected")
        except urllib.error.HTTPError as e:
            assert e.code == 401, f"Expected 401 for an invalid token, got {e.code}"

        # 2b. A phone that paired by QR can send files straight away.
        qr_payload_bytes = b"Seamless QR paired transfer payload" * 2048
        qr_sha = hashlib.sha256(qr_payload_bytes).hexdigest()
        qr_headers = {
            "X-Seamless-Filename": "qr_paired_upload.bin",
            "X-Seamless-Filesize": str(len(qr_payload_bytes)),
            "X-Seamless-Sender-Id": "qr_phone",
            "X-Seamless-Sender-Name": "QR Test Phone",
            "X-Seamless-Token": qr_auth_token,
            "X-Seamless-SHA256": qr_sha,
            "Content-Type": "application/octet-stream"
        }
        qr_file_req = urllib.request.Request(
            f"{base_url}/api/transfer/send", method="POST",
            data=qr_payload_bytes, headers=qr_headers)
        qr_tx_res = json.loads(urllib.request.urlopen(qr_file_req).read().decode())
        assert qr_tx_res["success"] is True, "A QR-paired device must be able to send files"
        assert qr_tx_res["sha256"] == qr_sha
        assert os.path.exists(qr_tx_res["saved_path"])
        try:
            os.unlink(qr_tx_res["saved_path"])
        except Exception:
            pass

        # Verify PIN
        verify_payload = json.dumps({"pin": pin, "device_id": "test_phone", "device_name": "Test Galaxy"}).encode()
        req = urllib.request.Request(f"{base_url}/api/pair/verify", method="POST", data=verify_payload, headers={"Content-Type": "application/json"})
        verify_res = json.loads(urllib.request.urlopen(req).read().decode())
        assert verify_res["success"] is True
        token = verify_res["token"]
        assert len(token) > 10
        paired_res = json.loads(urllib.request.urlopen(f"{base_url}/api/devices").read().decode())
        assert paired_res["paired"]["test_phone"]["ip"] == "127.0.0.1"

        # 3. File Streaming Transfer
        test_content = b"Seamless High-Speed Wi-Fi File Transfer Test Payload" * 1024  # ~50 KB
        test_sha = hashlib.sha256(test_content).hexdigest()

        headers = {
            "X-Seamless-Filename": "test_payload.bin",
            "X-Seamless-Filesize": str(len(test_content)),
            "X-Seamless-Sender-Id": "test_phone",
            "X-Seamless-Sender-Name": "Test Galaxy",
            "X-Seamless-Token": token,
            "X-Seamless-SHA256": test_sha,
            "Content-Type": "application/octet-stream"
        }

        req = urllib.request.Request(f"{base_url}/api/transfer/send", method="POST", data=test_content, headers=headers)
        tx_res = json.loads(urllib.request.urlopen(req).read().decode())
        assert tx_res["success"] is True
        assert tx_res["sha256"] == test_sha
        assert os.path.exists(tx_res["saved_path"])

        # Clean up test file
        try:
            os.unlink(tx_res["saved_path"])
        except Exception:
            pass

        print("  -> Live HTTP Server & File Transfer passed!")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_security_manager()
    test_pairing_token_lifecycle()
    test_transfer_engine_and_history()
    test_server_api_and_file_transfer()
    print("\n[SUCCESS] ALL WINDOWS CORE TESTS PASSED PERFECTLY!\n")
