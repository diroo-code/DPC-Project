"""Storage abstraction.

Two drivers implement the same interface:

* LocalStorage writes to a directory and issues HMAC signed URLs. It exists so Phase 2 can be
  tested without a Supabase project, and it reproduces the property that matters: a signed URL is a
  bearer capability with an expiry, and a tampered URL is rejected.
* SupabaseStorage uses the service role to upload, remove and sign. It is implemented but NOT
  TESTED, because no project exists yet. Phase 5 exercises it.

Signed URLs are bearer tokens by design, in both drivers. Authorisation happens before signing; the
URL itself cannot be re-checked by the storage layer.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from fastapi import HTTPException, status

from .config import settings


class StorageError(RuntimeError):
    """Raised when the storage layer fails. Callers decide whether to abort or compensate."""


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def read(self, key: str) -> bytes: ...
    def signed_url(self, key: str, expires_in: int) -> str: ...


class LocalStorage:
    def __init__(self, root: str, signing_secret: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret = signing_secret.encode()

    def _path(self, key: str) -> Path:
        # Resolve and confine, so a crafted key cannot escape the storage root.
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root.resolve()) + os.sep):
            raise StorageError("invalid storage key")
        return candidate

    def save(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except OSError as exc:
            raise StorageError(f"could not write object: {exc}") from exc

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
            # Remove the photo folder if it is now empty. A missing object is not an error:
            # deletion is idempotent, which is what makes retries safe.
            parent = path.parent
            if parent != self.root and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError as exc:
            raise StorageError(f"could not delete object: {exc}") from exc

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError("object not found")
        return path.read_bytes()

    def _signature(self, key: str, expires: int) -> str:
        message = f"{key}:{expires}".encode()
        return hmac.new(self.secret, message, hashlib.sha256).hexdigest()

    def signed_url(self, key: str, expires_in: int) -> str:
        expires = int(time.time()) + expires_in
        signature = self._signature(key, expires)
        return f"/media/{quote(key)}?exp={expires}&sig={signature}"

    def verify(self, key: str, expires: int, signature: str) -> None:
        if expires < int(time.time()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "signed URL expired")
        expected = self._signature(key, expires)
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid signature")


class SupabaseStorage:
    """NOT TESTED until a real Supabase project exists. Phase 5 verifies it."""

    BUCKET = "photos"

    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import create_client

        self._client = create_client(url, service_role_key)

    def save(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.storage.from_(self.BUCKET).upload(
                key, data, {"content-type": content_type, "upsert": "false"}
            )
        except Exception as exc:  # pragma: no cover - requires a live project
            raise StorageError(str(exc)) from exc

    def delete(self, key: str) -> None:
        try:
            self._client.storage.from_(self.BUCKET).remove([key])
        except Exception as exc:  # pragma: no cover
            raise StorageError(str(exc)) from exc

    def read(self, key: str) -> bytes:  # pragma: no cover
        try:
            return self._client.storage.from_(self.BUCKET).download(key)
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    def signed_url(self, key: str, expires_in: int) -> str:
        try:
            result = self._client.storage.from_(self.BUCKET).create_signed_url(key, expires_in)
            return result["signedURL"] if isinstance(result, dict) else str(result)
        except Exception as exc:  # pragma: no cover
            raise StorageError(str(exc)) from exc


def get_storage() -> StorageBackend:
    if settings.storage_backend == "supabase":
        if not (settings.supabase_url and settings.supabase_service_role_key):
            raise StorageError("supabase storage selected but SUPABASE_URL or service role key is missing")
        return SupabaseStorage(settings.supabase_url, settings.supabase_service_role_key)
    return LocalStorage(settings.storage_local_root, settings.storage_signing_secret)


storage: StorageBackend = get_storage()
