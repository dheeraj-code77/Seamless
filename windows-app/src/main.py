"""
Seamless Windows Desktop Application Launcher
Starts the core transfer engine, UDP discovery, and native desktop app window.
"""
import os
import sys
import time
import shutil
import subprocess
import webbrowser
import threading
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    SRC_DIR = BASE_DIR / "windows-app" / "src"
    RENDERER_DIR = SRC_DIR / "renderer"
else:
    SRC_DIR = Path(__file__).resolve().parent
    RENDERER_DIR = SRC_DIR / "renderer"

sys.path.insert(0, str(SRC_DIR))

from core.server import run_server
from core.config import load_config, get_local_ip


def launch_desktop_window(url: str):
    """
    Launches a borderless native application window using Microsoft Edge app-mode
    or falls back to the default browser.
    """
    # Wait briefly for HTTP server to become ready
    time.sleep(0.8)

    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("msedge")
    ]

    edge_exe = None
    for p in edge_paths:
        if p and os.path.exists(p):
            edge_exe = p
            break

    if edge_exe:
        try:
            cmd = [
                edge_exe,
                f"--app={url}",
                "--window-size=1140,780",
                "--app-title=Seamless",
                f"--user-data-dir={os.path.expandvars(r'%TEMP%\Seamless_WebProfile')}"
            ]
            print(f"[Desktop] Launching native window via Edge App Mode...")
            subprocess.Popen(cmd)
            return
        except Exception as e:
            print(f"[Desktop] Edge app mode launch error: {e}")

    # Fallback to system default browser
    print(f"[Desktop] Opening {url} in default browser...")
    webbrowser.open(url)


def main():
    config = load_config()
    port = config.get("http_port", 5173)

    server = run_server(port=port, renderer_dir=RENDERER_DIR)

    # Launch desktop window in background thread
    threading.Thread(target=launch_desktop_window, args=(f"http://localhost:{port}",), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Seamless] Shutting down gracefully...")
        server.shutdown()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
