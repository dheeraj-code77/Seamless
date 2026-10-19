"""
Seamless Security & Sanitization Utilities
"""
import os
import re
import secrets
import hashlib
import time
from pathlib import Path


class SecurityManager:
    # Maximum number of simultaneously valid QR pairing tokens.
    # A new QR is generated every time the desktop UI refreshes the code, so a
    # small window of tokens is kept alive to avoid invalidating a code that is
    # being scanned at the exact moment the screen refreshes.
    MAX_PAIRING_TOKENS = 3

    def __init__(self):
        self.active_pin = None
        self.pin_expiry = 0
        self.pending_sender_id = None
        self.pairing_tokens = {}

    def generate_pairing_token(self, lifetime_sec: int = 600) -> str:
        """Generates a short-lived, single-use token embedded in the pairing QR code."""
        self._prune_pairing_tokens()
        token = secrets.token_urlsafe(32)
        self.pairing_tokens[token] = time.time() + lifetime_sec
        # Keep only the most recent tokens so old codes die out quickly.
        if len(self.pairing_tokens) > self.MAX_PAIRING_TOKENS:
            oldest = sorted(self.pairing_tokens.items(), key=lambda kv: kv[1])[0][0]
            self.pairing_tokens.pop(oldest, None)
        return token

    def verify_pairing_token(self, submitted_token: str) -> bool:
        """Validates a QR pairing token. Expired and already-used tokens are rejected."""
        self._prune_pairing_tokens()
        token = str(submitted_token or "").strip()
        if not token or token not in self.pairing_tokens:
            return False
        expiry = self.pairing_tokens.pop(token)
        if time.time() > expiry:
            return False
        return True

    def _prune_pairing_tokens(self):
        now = time.time()
        for token, expiry in list(self.pairing_tokens.items()):
            if now > expiry:
                del self.pairing_tokens[token]

    def generate_pin(self, sender_id: str = None, lifetime_sec: int = 300) -> str:
        """Generates a secure 6-digit numeric PIN with a 5-minute expiry."""
        pin = f"{secrets.randbelow(1000000):06d}"
        self.active_pin = pin
        self.pin_expiry = time.time() + lifetime_sec
        self.pending_sender_id = sender_id
        return pin

    def verify_pin(self, submitted_pin: str) -> bool:
        """Validates the submitted PIN."""
        if not self.active_pin:
            return False
        if time.time() > self.pin_expiry:
            self.active_pin = None
            return False
        # Constant time comparison to prevent timing attacks
        is_valid = secrets.compare_digest(str(submitted_pin).strip(), self.active_pin)
        if is_valid:
            # Single-use PIN: invalidate immediately after successful verification
            self.active_pin = None
        return is_valid

    @staticmethod
    def generate_token() -> str:
        """Generates a high-entropy session authentication token."""
        return secrets.token_hex(32)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Prevents directory traversal (../, ..\\) and strips dangerous OS characters.
        """
        # Strip directory separators
        clean_name = os.path.basename(filename.replace("\\", "/"))
        # Remove null bytes and control chars
        clean_name = re.sub(r'[\x00-\x1f\x7f]', '', clean_name)
        # Remove Windows reserved file characters: < > : " / \ | ? *
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name).strip(". ")
        if not clean_name:
            clean_name = f"seamless_file_{int(time.time())}.bin"
        return clean_name

    @staticmethod
    def get_safe_destination_path(directory: str, filename: str) -> Path:
        """
        Ensures the file path stays strictly inside the designated directory
        and prevents accidental overwriting of existing files by generating a unique suffix.
        """
        base_dir = Path(directory).resolve()
        safe_name = SecurityManager.sanitize_filename(filename)
        dest_path = (base_dir / safe_name).resolve()

        # Strict sandbox check: dest_path MUST be inside base_dir
        if not str(dest_path).startswith(str(base_dir)):
            dest_path = base_dir / safe_name

        # Prevent overwriting existing files
        if not dest_path.exists():
            return dest_path

        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = base_dir / f"{stem} ({counter}){suffix}"
            counter += 1

        return dest_path

    @staticmethod
    def compute_sha256(filepath: Path) -> str:
        """Calculates SHA-256 hash of a file for transmission integrity verification."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
