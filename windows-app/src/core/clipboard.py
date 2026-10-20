"""
Seamless Windows Clipboard Bridge

Reads and writes the Windows clipboard directly through the Win32 API. Using
ctypes instead of a PowerShell subprocess keeps clipboard polling cheap and
keeps clipboard content out of a command line, which would otherwise allow
copied text to be interpreted as PowerShell syntax.
"""
import ctypes
import threading
import time
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# Clipboard payloads larger than this are ignored so a huge copy cannot stall
# the pairing or transfer traffic.
MAX_CLIPBOARD_CHARS = 65536


class ClipboardError(RuntimeError):
    """Raised when the Windows clipboard cannot be read or written."""


def _is_windows() -> bool:
    return hasattr(ctypes, "windll")


def _open_clipboard(user32) -> None:
    # Another application can hold the clipboard open for a moment, so retry
    # briefly before giving up.
    for _ in range(10):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.02)
    raise ClipboardError("The clipboard is currently locked by another application.")


def read_clipboard_text() -> str:
    """Returns the current CF_UNICODETEXT clipboard content."""
    if not _is_windows():
        raise ClipboardError("The Windows clipboard is only available on Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = wintypes.HANDLE
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    _open_clipboard(user32)
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise ClipboardError("Could not read the clipboard contents.")
        try:
            return ctypes.c_wchar_p(locked).value or ""
        finally:
            kernel32.GlobalUnlock(locked)
    finally:
        user32.CloseClipboard()


def write_clipboard_text(text: str) -> None:
    """Replaces the clipboard content with the given text."""
    if not _is_windows():
        raise ClipboardError("The Windows clipboard is only available on Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = wintypes.HANDLE
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.restype = wintypes.HANDLE

    _open_clipboard(user32)
    try:
        payload = text + "\0"
        size = len(payload) * ctypes.sizeof(ctypes.c_wchar)
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            raise ClipboardError("Could not allocate clipboard memory.")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            raise ClipboardError("Could not lock clipboard memory.")
        try:
            ctypes.memmove(locked, ctypes.c_wchar_p(payload), size)
        finally:
            kernel32.GlobalUnlock(handle)
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise ClipboardError("Could not write to the clipboard.")
    finally:
        user32.CloseClipboard()


class ClipboardSync:
    """
    Keeps a record of the last clipboard text seen on this machine.

    Both devices share the same record, so a text that was just synced one way
    is not immediately pushed back the other way. That is what stops the two
    sides from looping on each other.
    """

    def __init__(self, max_chars: int = MAX_CLIPBOARD_CHARS):
        self.max_chars = max_chars
        self._last_text = ""
        self._lock = threading.Lock()

    def apply_remote_text(self, text: str) -> bool:
        """
        Writes text that arrived from the other device onto the Windows clipboard.

        Returns True when the clipboard was changed and False when the text was
        already there.
        """
        with self._lock:
            if text == self._last_text:
                return False
            write_clipboard_text(text)
            self._last_text = text
            return True

    def current_text(self) -> str:
        """Returns the Windows clipboard text, keeping the loop guard current."""
        try:
            text = read_clipboard_text()
        except ClipboardError:
            with self._lock:
                return self._last_text
        if len(text) > self.max_chars:
            return ""
        with self._lock:
            self._last_text = text
        return text
