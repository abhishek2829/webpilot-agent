"""WebPilot Agent — Credential Vault.

Encrypted credential storage using Fernet symmetric encryption.
Secrets are NEVER stored in plaintext, NEVER logged, NEVER exposed in error messages.

Design pattern: compound-engineering-plugin inspired — every credential operation
logs its outcome. Failures are captured as "lessons" that improve future operations.

Security model:
- Encryption key comes from environment variable (VAULT_ENCRYPTION_KEY)
- Each credential is individually encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
- Storage is a JSON file with encrypted values only
- Key rotation supported via re-encrypt-all operation
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CredentialEntry(BaseModel):
    """A single encrypted credential entry."""
    encrypted_value: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""


class VaultError(Exception):
    """Base error for vault operations. NEVER includes the actual secret in the message."""
    pass


class CredentialNotFoundError(VaultError):
    """Raised when a requested credential doesn't exist."""
    pass


class VaultDecryptionError(VaultError):
    """Raised when decryption fails (wrong key or corrupted data)."""
    pass


class CredentialVault:
    """Encrypted credential storage.

    Analogy: Think of this as a safe deposit box at a bank.
    - The encryption_key is your bank key — without it, nothing opens.
    - Each credential is a separate locked box inside the vault.
    - The vault file is the physical safe — encrypted at rest.

    Usage:
        vault = CredentialVault.from_settings(settings)
        vault.store("clerk_email", "user@example.com")
        vault.store("clerk_password", "s3cret", description="Clerk dashboard login")
        email = vault.retrieve("clerk_email")
    """

    def __init__(
        self,
        encryption_key: str,
        storage_path: Path | None = None,
    ) -> None:
        """Initialize the vault.

        Args:
            encryption_key: Fernet-compatible key (base64-encoded 32 bytes).
                           Generate with: Fernet.generate_key().decode()
            storage_path: Where to persist encrypted credentials.
                         Defaults to ./data/credentials.vault
        """
        self._storage_path = storage_path or Path("./data/credentials.vault")
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._fernet = Fernet(encryption_key.encode())
        except (ValueError, Exception) as e:
            raise VaultError(
                "Invalid encryption key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from e

        self._entries: dict[str, CredentialEntry] = {}
        self._load()

        # Compound-engineering pattern: track operations for lessons
        self._operation_log: list[dict] = []

    # =========================================================================
    # Public API
    # =========================================================================

    def store(self, key: str, value: str, description: str = "") -> None:
        """Encrypt and store a credential.

        Args:
            key: Credential identifier (e.g., "clerk_email", "stripe_api_key")
            value: The secret value to encrypt
            description: Optional human-readable description
        """
        if not key or not key.strip():
            raise VaultError("Credential key cannot be empty")
        if not value:
            raise VaultError("Credential value cannot be empty")

        encrypted = self._fernet.encrypt(value.encode()).decode()

        now = datetime.now(timezone.utc).isoformat()
        is_update = key in self._entries

        self._entries[key] = CredentialEntry(
            encrypted_value=encrypted,
            created_at=self._entries[key].created_at if is_update else now,
            updated_at=now,
            description=description or (self._entries[key].description if is_update else ""),
        )

        self._save()
        self._log_operation("store", key, success=True, is_update=is_update)
        logger.info("Credential '%s' %s", key, "updated" if is_update else "stored")

    def retrieve(self, key: str) -> str:
        """Decrypt and return a credential value.

        Args:
            key: Credential identifier

        Returns:
            The decrypted secret value

        Raises:
            CredentialNotFoundError: If key doesn't exist
            VaultDecryptionError: If decryption fails (wrong key or corruption)
        """
        if key not in self._entries:
            self._log_operation("retrieve", key, success=False, error="not_found")
            raise CredentialNotFoundError(f"Credential '{key}' not found in vault")

        try:
            decrypted = self._fernet.decrypt(
                self._entries[key].encrypted_value.encode()
            ).decode()
            self._log_operation("retrieve", key, success=True)
            return decrypted
        except InvalidToken as e:
            self._log_operation("retrieve", key, success=False, error="decryption_failed")
            raise VaultDecryptionError(
                f"Failed to decrypt '{key}'. Wrong encryption key or corrupted data."
            ) from e

    def delete(self, key: str) -> None:
        """Remove a credential from the vault.

        Args:
            key: Credential identifier to remove

        Raises:
            CredentialNotFoundError: If key doesn't exist
        """
        if key not in self._entries:
            raise CredentialNotFoundError(f"Credential '{key}' not found in vault")

        del self._entries[key]
        self._save()
        self._log_operation("delete", key, success=True)
        logger.info("Credential '%s' deleted", key)

    def exists(self, key: str) -> bool:
        """Check if a credential exists without decrypting it."""
        return key in self._entries

    def list_keys(self) -> list[str]:
        """List all stored credential keys (NOT their values)."""
        return list(self._entries.keys())

    def list_entries(self) -> dict[str, dict]:
        """List all credential metadata (keys, descriptions, timestamps — NOT values)."""
        return {
            key: {
                "description": entry.description,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            }
            for key, entry in self._entries.items()
        }

    def has_required(self, required_keys: list[str]) -> tuple[bool, list[str]]:
        """Check if all required credentials are present.

        Args:
            required_keys: List of credential keys that must exist

        Returns:
            Tuple of (all_present, missing_keys)
        """
        missing = [k for k in required_keys if k not in self._entries]
        return len(missing) == 0, missing

    def rotate_key(self, new_encryption_key: str) -> int:
        """Re-encrypt all credentials with a new key.

        This is the key rotation operation — decrypt everything with the old key,
        re-encrypt with the new key. Essential for security hygiene.

        Args:
            new_encryption_key: New Fernet-compatible key

        Returns:
            Number of credentials re-encrypted
        """
        try:
            new_fernet = Fernet(new_encryption_key.encode())
        except (ValueError, Exception) as e:
            raise VaultError("Invalid new encryption key") from e

        count = 0
        for key in list(self._entries.keys()):
            # Decrypt with old key
            plaintext = self.retrieve(key)
            # Re-encrypt with new key
            encrypted = new_fernet.encrypt(plaintext.encode()).decode()
            self._entries[key].encrypted_value = encrypted
            self._entries[key].updated_at = datetime.now(timezone.utc).isoformat()
            count += 1

        # Switch to new key
        self._fernet = new_fernet
        self._save()
        self._log_operation("rotate_key", "*", success=True)
        logger.info("Rotated encryption key — %d credentials re-encrypted", count)
        return count

    # =========================================================================
    # Compound Engineering: Operation Logging (error→lesson pattern)
    # =========================================================================

    def _log_operation(
        self, operation: str, key: str, success: bool, **extra: str | bool
    ) -> None:
        """Log vault operations for the compound-engineering feedback loop.

        Every operation (success or failure) is captured. Failures become
        "lessons" that can feed into the self-learning agent's knowledge base.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "key": key,
            "success": success,
            **extra,
        }
        self._operation_log.append(entry)

        # Keep last 100 operations in memory
        if len(self._operation_log) > 100:
            self._operation_log = self._operation_log[-100:]

    def get_operation_log(self) -> list[dict]:
        """Return the operation log for analysis / self-improvement loop."""
        return list(self._operation_log)

    def get_lessons(self) -> list[dict]:
        """Extract lessons from failures — compound-engineering pattern.

        Returns failed operations with context, ready to feed into the
        self-learning agent's knowledge base (karpathy/autoresearch pattern).
        """
        return [
            op for op in self._operation_log if not op.get("success", True)
        ]

    # =========================================================================
    # Persistence
    # =========================================================================

    def _load(self) -> None:
        """Load encrypted entries from disk."""
        if not self._storage_path.exists():
            self._entries = {}
            return

        try:
            raw = self._storage_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._entries = {
                key: CredentialEntry(**val) for key, val in data.items()
            }
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to load vault file: %s — starting fresh", e)
            self._entries = {}

    def _save(self) -> None:
        """Persist encrypted entries to disk."""
        data = {
            key: entry.model_dump() for key, entry in self._entries.items()
        }
        self._storage_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    # =========================================================================
    # Factory
    # =========================================================================

    @classmethod
    def from_settings(cls, settings) -> CredentialVault:
        """Create a vault from application settings.

        Args:
            settings: The Settings object from config.py
        """
        return cls(
            encryption_key=settings.vault_encryption_key,
            storage_path=settings.screenshot_dir.parent / "credentials.vault",
        )

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            Base64-encoded 32-byte key as string
        """
        return Fernet.generate_key().decode()
