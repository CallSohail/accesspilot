"""Per-job upload storage.

Files are stored under a job-scoped subfolder so concurrent users do not
overwrite each other. Files are intentionally NOT persisted past a report
generation unless the operator configures a longer-lived location.

We never write outside the configured upload directory.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
from pathlib import Path

from .config import Settings


class StorageError(Exception):
    pass


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(original: str, max_len: int = 80) -> str:
    """Sanitize a filename to safe ASCII characters.

    Preserves the extension so downstream extraction can detect kind.
    """
    base, ext = os.path.splitext(original)
    base = _SAFE_NAME_RE.sub("_", base).strip("._") or "upload"
    base = base[: max_len - len(ext)]
    return base + (ext or "")


class JobStorage:
    """A short-lived storage location for one analysis job."""

    def __init__(self, settings: Settings, job_id: str) -> None:
        self.root = Path(settings.upload_dir)
        self.job_dir = self.root / job_id
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, data: bytes, original_name: str) -> Path:
        dest = self.job_dir / safe_name(original_name)
        # Guard against path traversal from the sanitized name.
        try:
            dest.resolve().relative_to(self.job_dir.resolve())
        except ValueError as exc:  # pragma: no cover - safety net
            raise StorageError("unsafe file name") from exc
        dest.write_bytes(data)
        return dest

    @property
    def path(self) -> Path:
        return self.job_dir

    def dispose(self) -> None:
        """Remove the job directory (best-effort)."""
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)


def new_job_id() -> str:
    return secrets.token_hex(8)
