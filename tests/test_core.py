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

# Add windows-app/src to search path
SRC_DIR = Path(__file__).resolve().parent.parent / "windows-app" / "src"
sys.path.insert(0, str(SRC_DIR))

from core.security import SecurityManager
from core.history import HistoryManager
from core.transfer_engine import TransferEngine
from core.server import run_server


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

        # 2. Pairing Flow
        req = urllib.request.Request(f"{base_url}/api/pair/request", method="POST", data=b"{}")
        pair_res = json.loads(urllib.request.urlopen(req).read().decode())
        pin = pair_res["pin"]
        assert len(pin) == 6

        # Verify PIN
        verify_payload = json.dumps({"pin": pin, "device_id": "test_phone", "device_name": "Test Galaxy"}).encode()
        req = urllib.request.Request(f"{base_url}/api/pair/verify", method="POST", data=verify_payload, headers={"Content-Type": "application/json"})
        verify_res = json.loads(urllib.request.urlopen(req).read().decode())
        assert verify_res["success"] is True
        token = verify_res["token"]
        assert len(token) > 10

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
    test_transfer_engine_and_history()
    test_server_api_and_file_transfer()
    print("\n[SUCCESS] ALL WINDOWS CORE TESTS PASSED PERFECTLY!\n")
