import os
import uuid
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from app.config import settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, user_id: str, doc_id: str, filename: str, data: bytes) -> str:
        """Save original document file and return unique storage_key."""
        pass

    @abstractmethod
    def save_page_image(self, user_id: str, doc_id: str, page_number: int, data: bytes) -> str:
        """Save rendered page PNG image and return storage_key."""
        pass

    @abstractmethod
    def load(self, storage_key: str) -> bytes:
        """Read file contents by storage_key."""
        pass

    @abstractmethod
    def get_absolute_path(self, storage_key: str) -> str:
        """Resolve to local absolute path if supported."""
        pass

    @abstractmethod
    def delete(self, storage_key: str) -> bool:
        """Delete single file by storage_key."""
        pass

    @abstractmethod
    def delete_document_artifacts(self, user_id: str, doc_id: str) -> bool:
        """Clean up entire directory for a document."""
        pass


class LocalStorageBackend(StorageBackend):
    def __init__(self, root_dir: str):
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_safe(self, rel_path: str) -> Path:
        # Standardize path separators
        norm = os.path.normpath(rel_path).lstrip("/\\")
        target = (self.root / norm).resolve()
        if not str(target).startswith(str(self.root)):
            raise ValueError(f"Directory traversal attempt detected for path: {rel_path}")
        return target

    def save(self, user_id: str, doc_id: str, filename: str, data: bytes) -> str:
        # Clean filename to avoid path injection
        safe_filename = Path(filename).name
        rel_key = f"users/{user_id}/docs/{doc_id}/original_{safe_filename}"
        target_path = self._resolve_safe(rel_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        return rel_key.replace("\\", "/")

    def save_page_image(self, user_id: str, doc_id: str, page_number: int, data: bytes) -> str:
        rel_key = f"users/{user_id}/docs/{doc_id}/pages/page_{page_number}.png"
        target_path = self._resolve_safe(rel_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        return rel_key.replace("\\", "/")

    def load(self, storage_key: str) -> bytes:
        target_path = self._resolve_safe(storage_key)
        if not target_path.exists():
            raise FileNotFoundError(f"Storage object not found: {storage_key}")
        return target_path.read_bytes()

    def get_absolute_path(self, storage_key: str) -> str:
        target_path = self._resolve_safe(storage_key)
        return str(target_path)

    def delete(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_safe(storage_key)
            if target_path.exists():
                target_path.unlink()
                return True
        except Exception:
            pass
        return False

    def delete_document_artifacts(self, user_id: str, doc_id: str) -> bool:
        try:
            rel_dir = f"users/{user_id}/docs/{doc_id}"
            target_dir = self._resolve_safe(rel_dir)
            if target_dir.exists() and target_dir.is_dir():
                shutil.rmtree(target_dir, ignore_errors=True)
                return True
        except Exception:
            pass
        return False


def get_storage() -> StorageBackend:
    # Extensible for S3 / Azure Blob
    return LocalStorageBackend(root_dir=settings.storage_root)


storage = get_storage()
