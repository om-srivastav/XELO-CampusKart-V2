import warnings
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from flask import abort, current_app
from PIL import Image, ImageOps, UnidentifiedImageError


class LocalImageStorage:
    """Opaque-key image storage; replace this adapter to move to object storage."""

    def __init__(self):
        self.root = Path(current_app.config["UPLOAD_FOLDER"])

    def put(self, key, data):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / key).write_bytes(data)

    def remove(self, key):
        if key and Path(key).name == key:
            (self.root / key).unlink(missing_ok=True)

    def path(self, key):
        if Path(key).name != key:
            abort(404)
        return self.root / key


def save_image(file):
    """Decode and sanitize before writing; clean both variants if either write fails."""
    allowed = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        abort(400, "Use JPEG, PNG or WebP images.")
    raw = file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        abort(400, "Each image must be smaller than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format != allowed[suffix] or image.width * image.height > 20_000_000:
                    abort(400, "Image format or dimensions are not allowed.")
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
        abort(400, "This file could not be decoded as a safe image.")
    storage = LocalImageStorage()
    key = uuid4().hex + ".webp"
    try:
        storage.put(key, data.getvalue())
        storage.put("thumb-" + key, thumb.getvalue())
    except OSError:
        for path in (key, "thumb-" + key):
            try:
                storage.remove(path)
            except OSError:
                current_app.logger.warning("Partial upload cleanup deferred to maintenance.")
        abort(503, "Image storage is unavailable. Please try again.")
    return key


def remove_image(key):
    if key:
        storage = LocalImageStorage()
        storage.remove(key)
        storage.remove("thumb-" + key)
