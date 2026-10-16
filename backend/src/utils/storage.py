import base64
import io

from PIL import Image, ImageOps

from clients.supabase import get_supabase_client

BUCKET = "sariko-public"
MAX_SIDE = 1600
JPEG_QUALITY = 70


def compress_to_jpeg(content: bytes) -> bytes:
    """Downscale to MAX_SIDE and re-encode as JPEG (same approach as the admin
    panel's compress_images.py). Phone photos are often 2-5 MB; this lands them
    at a few hundred KB.

    exif_transpose first: re-saving drops EXIF, so a portrait phone photo would
    otherwise come out sideways.
    """
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def upload_private(bucket: str, path: str, content: bytes, content_type: str) -> None:
    """Upload to a private bucket under the service role. No public URL: readers get
    a signed URL from the backend (admin app)."""
    get_supabase_client().storage.from_(bucket).upload(path, content, {"content-type": content_type})


def remove_private(bucket: str, path: str) -> None:
    get_supabase_client().storage.from_(bucket).remove([path])


def upload_image_base64(path: str, image_base64: str) -> str:
    """Compress a base64-encoded image to JPEG, upload it to the public bucket and
    return its public URL.

    Runs under the service role (bypasses storage RLS) — the browser cannot upload
    directly because auth.uid() is not populated in the storage-api context under
    this project's asymmetric (ES256) JWTs.

    Accepts a raw base64 string or a data URL ("data:image/png;base64,...").
    """
    if image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[1]

    content = compress_to_jpeg(base64.b64decode(image_base64))
    client = get_supabase_client()
    client.storage.from_(BUCKET).upload(
        path, content, {"content-type": "image/jpeg", "upsert": "true"}
    )
    return client.storage.from_(BUCKET).get_public_url(path).rstrip("?")
