"""Tests for WebPilot Agent — Credential Vault.

Following TDD discipline: tests written FIRST, then verified against implementation.
Covers: store, retrieve, delete, encryption-at-rest, key rotation, error handling,
compound-engineering lessons, and edge cases.
"""

import json
import pytest
from pathlib import Path
from cryptography.fernet import Fernet

from src.credentials.vault import (
    CredentialVault,
    CredentialNotFoundError,
    VaultDecryptionError,
    VaultError,
)


@pytest.fixture
def encryption_key() -> str:
    """Generate a fresh encryption key for each test."""
    return Fernet.generate_key().decode()


@pytest.fixture
def vault(tmp_path: Path, encryption_key: str) -> CredentialVault:
    """Create a vault instance with a temp storage path."""
    return CredentialVault(
        encryption_key=encryption_key,
        storage_path=tmp_path / "test.vault",
    )


# =========================================================================
# Core Operations
# =========================================================================

class TestStore:
    """Test storing credentials."""

    def test_store_and_retrieve(self, vault: CredentialVault) -> None:
        vault.store("clerk_email", "test@example.com")
        assert vault.retrieve("clerk_email") == "test@example.com"

    def test_store_overwrites_existing(self, vault: CredentialVault) -> None:
        vault.store("api_key", "old_value")
        vault.store("api_key", "new_value")
        assert vault.retrieve("api_key") == "new_value"

    def test_store_with_description(self, vault: CredentialVault) -> None:
        vault.store("stripe_key", "sk_test_123", description="Stripe test key")
        entries = vault.list_entries()
        assert entries["stripe_key"]["description"] == "Stripe test key"

    def test_store_preserves_description_on_update(self, vault: CredentialVault) -> None:
        vault.store("key1", "val1", description="My key")
        vault.store("key1", "val2")  # no description — should preserve
        entries = vault.list_entries()
        assert entries["key1"]["description"] == "My key"

    def test_store_rejects_empty_key(self, vault: CredentialVault) -> None:
        with pytest.raises(VaultError, match="key cannot be empty"):
            vault.store("", "some_value")

    def test_store_rejects_empty_value(self, vault: CredentialVault) -> None:
        with pytest.raises(VaultError, match="value cannot be empty"):
            vault.store("key1", "")

    def test_store_handles_special_characters(self, vault: CredentialVault) -> None:
        special = "p@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"
        vault.store("special_pass", special)
        assert vault.retrieve("special_pass") == special

    def test_store_handles_unicode(self, vault: CredentialVault) -> None:
        vault.store("unicode_key", "пароль_密码_パスワード")
        assert vault.retrieve("unicode_key") == "пароль_密码_パスワード"

    def test_store_handles_long_values(self, vault: CredentialVault) -> None:
        long_value = "x" * 10000
        vault.store("long_key", long_value)
        assert vault.retrieve("long_key") == long_value


class TestRetrieve:
    """Test retrieving credentials."""

    def test_retrieve_nonexistent_raises(self, vault: CredentialVault) -> None:
        with pytest.raises(CredentialNotFoundError, match="not found"):
            vault.retrieve("nonexistent")

    def test_retrieve_with_wrong_key_raises(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "test.vault"

        # Store with one key
        vault1 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault1.store("secret", "my_secret_value")

        # Try to read with different key
        wrong_key = Fernet.generate_key().decode()
        vault2 = CredentialVault(encryption_key=wrong_key, storage_path=storage)
        with pytest.raises(VaultDecryptionError, match="Failed to decrypt"):
            vault2.retrieve("secret")


class TestDelete:
    """Test deleting credentials."""

    def test_delete_existing(self, vault: CredentialVault) -> None:
        vault.store("to_delete", "value")
        vault.delete("to_delete")
        assert not vault.exists("to_delete")

    def test_delete_nonexistent_raises(self, vault: CredentialVault) -> None:
        with pytest.raises(CredentialNotFoundError, match="not found"):
            vault.delete("nonexistent")

    def test_delete_persists(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "persist.vault"
        vault1 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault1.store("key1", "val1")
        vault1.store("key2", "val2")
        vault1.delete("key1")

        # Reload from disk
        vault2 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        assert not vault2.exists("key1")
        assert vault2.retrieve("key2") == "val2"


# =========================================================================
# Encryption Verification
# =========================================================================

class TestEncryption:
    """Verify credentials are actually encrypted at rest."""

    def test_value_encrypted_on_disk(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "enc.vault"
        vault = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault.store("api_key", "sk_live_super_secret_123")

        raw = storage.read_bytes()
        assert b"sk_live_super_secret_123" not in raw

    def test_key_name_visible_but_value_not(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "enc2.vault"
        vault = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault.store("clerk_password", "my_password_123")

        raw = storage.read_text()
        data = json.loads(raw)
        # Key name is visible (needed for lookup)
        assert "clerk_password" in data
        # But value is encrypted (starts with gAAAAA — Fernet prefix)
        assert data["clerk_password"]["encrypted_value"].startswith("gAAAAA")
        assert "my_password_123" not in raw


# =========================================================================
# Persistence
# =========================================================================

class TestPersistence:
    """Test that vault survives restarts."""

    def test_data_survives_reload(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "persist.vault"

        # Store in first instance
        vault1 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault1.store("email", "user@test.com")
        vault1.store("password", "s3cret")

        # Load in second instance
        vault2 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        assert vault2.retrieve("email") == "user@test.com"
        assert vault2.retrieve("password") == "s3cret"

    def test_empty_vault_file_handled(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "empty.vault"
        storage.write_text("")  # empty file

        vault = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        assert vault.list_keys() == []

    def test_corrupted_vault_file_handled(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "corrupt.vault"
        storage.write_text("not valid json {{{{")

        vault = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        assert vault.list_keys() == []  # starts fresh


# =========================================================================
# Key Rotation
# =========================================================================

class TestKeyRotation:
    """Test encryption key rotation."""

    def test_rotate_key(
        self, tmp_path: Path, encryption_key: str
    ) -> None:
        storage = tmp_path / "rotate.vault"
        vault = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        vault.store("key1", "value1")
        vault.store("key2", "value2")

        new_key = Fernet.generate_key().decode()
        count = vault.rotate_key(new_key)
        assert count == 2

        # Can still read with the vault (now using new key)
        assert vault.retrieve("key1") == "value1"
        assert vault.retrieve("key2") == "value2"

        # New instance with new key can read
        vault2 = CredentialVault(encryption_key=new_key, storage_path=storage)
        assert vault2.retrieve("key1") == "value1"

        # Old key can NOT read
        vault3 = CredentialVault(encryption_key=encryption_key, storage_path=storage)
        with pytest.raises(VaultDecryptionError):
            vault3.retrieve("key1")


# =========================================================================
# Utility Methods
# =========================================================================

class TestUtilities:
    """Test helper methods."""

    def test_exists(self, vault: CredentialVault) -> None:
        vault.store("present", "value")
        assert vault.exists("present")
        assert not vault.exists("absent")

    def test_list_keys(self, vault: CredentialVault) -> None:
        vault.store("a", "1")
        vault.store("b", "2")
        vault.store("c", "3")
        keys = vault.list_keys()
        assert sorted(keys) == ["a", "b", "c"]

    def test_has_required_all_present(self, vault: CredentialVault) -> None:
        vault.store("email", "e")
        vault.store("password", "p")
        ok, missing = vault.has_required(["email", "password"])
        assert ok
        assert missing == []

    def test_has_required_some_missing(self, vault: CredentialVault) -> None:
        vault.store("email", "e")
        ok, missing = vault.has_required(["email", "password", "api_key"])
        assert not ok
        assert sorted(missing) == ["api_key", "password"]

    def test_generate_key(self) -> None:
        key = CredentialVault.generate_key()
        assert len(key) == 44  # base64-encoded 32 bytes
        # Validate it's a valid Fernet key
        Fernet(key.encode())  # should not raise


# =========================================================================
# Compound Engineering: Lessons from Failures
# =========================================================================

class TestCompoundEngineering:
    """Test the error→lesson feedback loop."""

    def test_operation_log_captures_stores(self, vault: CredentialVault) -> None:
        vault.store("k1", "v1")
        log = vault.get_operation_log()
        assert len(log) == 1
        assert log[0]["operation"] == "store"
        assert log[0]["success"] is True

    def test_operation_log_captures_failures(self, vault: CredentialVault) -> None:
        with pytest.raises(CredentialNotFoundError):
            vault.retrieve("nonexistent")
        lessons = vault.get_lessons()
        assert len(lessons) == 1
        assert lessons[0]["error"] == "not_found"

    def test_lessons_only_returns_failures(self, vault: CredentialVault) -> None:
        vault.store("k1", "v1")
        vault.retrieve("k1")  # success
        with pytest.raises(CredentialNotFoundError):
            vault.retrieve("missing")  # failure
        lessons = vault.get_lessons()
        assert len(lessons) == 1
        assert all(not l["success"] for l in lessons)


# =========================================================================
# Edge Cases
# =========================================================================

class TestEdgeCases:
    """Test boundary conditions."""

    def test_invalid_encryption_key(self, tmp_path: Path) -> None:
        with pytest.raises(VaultError, match="Invalid encryption key"):
            CredentialVault(encryption_key="not-a-valid-key", storage_path=tmp_path / "x.vault")

    def test_storage_dir_created_automatically(self, tmp_path: Path, encryption_key: str) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "vault.enc"
        vault = CredentialVault(encryption_key=encryption_key, storage_path=deep_path)
        vault.store("test", "value")
        assert deep_path.exists()

    def test_multiple_stores_same_key_preserves_created_at(
        self, vault: CredentialVault
    ) -> None:
        vault.store("k", "v1")
        created = vault.list_entries()["k"]["created_at"]
        vault.store("k", "v2")
        assert vault.list_entries()["k"]["created_at"] == created
        assert vault.list_entries()["k"]["updated_at"] != created
