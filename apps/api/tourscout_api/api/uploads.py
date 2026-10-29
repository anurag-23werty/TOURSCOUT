"""Uploads (streaming-dashboard screenshot or CSV): validated, held in memory for 15 minutes, deleted once a plan uses them.

Never written to disk, never logged: an artist's own numbers stay private.
"""

from __future__ import annotations

import base64
import secrets
import time
from dataclasses import dataclass
from typing import Any

from ..agent.reach import parse_csv

IMAGE_TYPES = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"RIFF": "image/webp",  # checked together with b"WEBP" at offset 8
}


class UploadError(ValueError):
    pass


@dataclass
class Upload:
    id: str
    kind: str  # "image" | "csv"
    reach_input: dict[str, Any]
    session_id: str
    created: float


def sniff_image(data: bytes) -> str | None:
    """Trust the bytes, not the filename or the client's Content-Type."""
    for magic, mime in IMAGE_TYPES.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime
    return None


class UploadStore:
    def __init__(self, max_bytes: int, ttl_s: float, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self.max_bytes, self.ttl_s, self.clock = max_bytes, ttl_s, clock
        self._items: dict[str, Upload] = {}

    def add(self, data: bytes, filename: str, session_id: str) -> tuple[Upload, dict[str, Any]]:
        """Validate and keep an upload. Returns (upload, preview for the UI)."""
        self._sweep()
        if not data:
            raise UploadError("the file is empty")
        if len(data) > self.max_bytes:
            raise UploadError(f"file too large: max {self.max_bytes // (1024 * 1024)} MB")
        mime = sniff_image(data)
        if mime:
            upload = Upload(secrets.token_hex(8), "image",
                            {"image_b64": base64.b64encode(data).decode(), "mime": mime}, session_id, self.clock())
            preview: dict[str, Any] = {"kind": "image", "mime": mime, "note": "cities are read when the plan starts"}
        elif filename.lower().endswith(".csv") or b"," in data[:200]:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise UploadError("CSV must be UTF-8 text") from None
            rows = parse_csv(text)  # raises ValueError with a user-facing message
            if not rows:
                raise UploadError("no rows with a city and a listener count")
            upload = Upload(secrets.token_hex(8), "csv", {"rows": rows}, session_id, self.clock())
            preview = {"kind": "csv", "rows": rows[:10], "total_rows": len(rows)}
        else:
            raise UploadError("upload a PNG/JPEG/WebP screenshot or a CSV with city and listeners columns")
        self._items[upload.id] = upload
        return upload, preview

    def take(self, upload_id: str, session_id: str) -> dict[str, Any]:
        """Hand the upload to a plan and delete it."""
        self._sweep()
        upload = self._items.get(upload_id)
        if upload is None or upload.session_id != session_id:
            raise UploadError("upload not found or expired; upload the file again")
        del self._items[upload_id]
        return upload.reach_input

    def _sweep(self) -> None:
        now = self.clock()
        for uid in [u.id for u in self._items.values() if now - u.created > self.ttl_s]:
            del self._items[uid]
