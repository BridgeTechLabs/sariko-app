"""Image compression before upload. No DB, no network.

Run from tests/backend:  pytest unit/test_storage.py
"""
import base64
import io


from PIL import Image

from utils import storage
from utils.storage import MAX_SIDE, compress_to_jpeg


def _encode(img, fmt, **kw):
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def test_large_photo_is_downscaled_to_jpeg():
    raw = _encode(Image.effect_noise((4000, 3000), 64).convert("RGB"), "PNG")
    out = Image.open(io.BytesIO(compress_to_jpeg(raw)))
    assert out.format == "JPEG"
    assert max(out.size) == MAX_SIDE
    assert out.size == (1600, 1200)


def test_transparent_png_gets_white_background():
    raw = _encode(Image.new("RGBA", (10, 10), (0, 0, 0, 0)), "PNG")
    out = Image.open(io.BytesIO(compress_to_jpeg(raw)))
    assert out.mode == "RGB"
    assert out.getpixel((5, 5)) == (255, 255, 255)


def test_exif_rotation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90° CW — how phones store portrait shots
    raw = _encode(Image.new("RGB", (300, 200)), "JPEG", exif=exif)
    out = Image.open(io.BytesIO(compress_to_jpeg(raw)))
    assert out.size == (200, 300)


def test_public_upload_is_cached_a_year(monkeypatch):
    calls = []

    class Bucket:
        def upload(self, path, content, opts):
            calls.append((path, opts))

        def get_public_url(self, path):
            return f"https://cdn/{path}?"

    class Client:
        class storage:
            from_ = staticmethod(lambda bucket: Bucket())

    monkeypatch.setattr(storage, "get_supabase_client", lambda: Client)
    raw = base64.b64encode(_encode(Image.new("RGB", (10, 10)), "PNG")).decode()
    assert storage.upload_image_base64("food-items/s/i-1", raw) == "https://cdn/food-items/s/i-1"
    assert calls == [("food-items/s/i-1", {"content-type": "image/jpeg", "upsert": "true", "cache-control": "31536000"})]


if __name__ == "__main__":
    test_large_photo_is_downscaled_to_jpeg()
    test_transparent_png_gets_white_background()
    test_exif_rotation_is_applied()
    print("ok")
