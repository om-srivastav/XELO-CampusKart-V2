"""Sanitized images behind a replaceable storage adapter."""

import logging
import warnings
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.datastructures import UploadFile

logger = logging.getLogger(__name__)


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def remove(self, key: str) -> None: ...
    def path(self, key: str) -> Path: ...


class LocalImageStorage:
    """Opaque-key storage rooted solely in the configured upload directory."""

    def __init__(self, settings):
        self.root = Path(settings.UPLOAD_FOLDER).resolve()

    def path(self, key: str) -> Path:
        if not key or key in {".", ".."} or any(c in key for c in "/\\:\x00"):
            raise HTTPException(404, "Image not found.")
        target = (self.root / key).resolve()
        if target.parent != self.root:
            raise HTTPException(404, "Image not found.")
        return target

    def put(self, key: str, data: bytes) -> None:
        target = self.path(key)
        self.root.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def remove(self, key: str) -> None:
        if key:
            self.path(key).unlink(missing_ok=True)


def get_storage(settings) -> Storage:
    """Replace this factory when an object-storage adapter is configured."""
    return LocalImageStorage(settings)


def save_image(file: UploadFile, settings) -> str:
    """Called by sync endpoints: sanitize and clean both variants on write failure."""
    allowed = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, "Use JPEG, PNG or WebP images.")
    raw = file.file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "Each image must be smaller than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format != allowed[suffix] or image.width * image.height > 20_000_000:
                    raise HTTPException(400, "Image format or dimensions are not allowed.")
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                clean.thumbnail((1600, 1600))
                data = BytesIO()
                clean.save(data, "WEBP", quality=84)
                clean.thumbnail((480, 480))
                thumb = BytesIO()
                clean.save(thumb, "WEBP", quality=78)
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(400, "This file could not be decoded as a safe image.") from None
    storage = get_storage(settings)
    key = uuid4().hex + ".webp"
    try:
        storage.put(key, data.getvalue())
        storage.put("thumb-" + key, thumb.getvalue())
    except OSError:
        for variant in (key, "thumb-" + key):
            try:
                storage.remove(variant)
            except OSError:
                logger.warning("Partial upload cleanup deferred to maintenance.")
        raise HTTPException(503, "Image storage is unavailable. Please try again.") from None
    return key


def remove_image(key: str | None, settings) -> None:
    if key:
        storage = get_storage(settings)
        storage.remove(key)
        storage.remove("thumb-" + key)
