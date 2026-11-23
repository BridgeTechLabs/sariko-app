"""One-off: shrink the large public images that use up Supabase Cached Egress (T220 / T167).

Scope: bucket blog-images (every file) and sariko-public/food-items/ (every file). Avatars,
promo-banners and private buckets are not touched.

Each file > 300 KB that Pillow opens as a still image is re-encoded with
utils.storage.compress_to_jpeg (1600 px, JPEG 70) and written back to the SAME path (posts and
menu rows keep their URLs), only when the result is < 70% of the original. GIF, animated
WebP / PNG and files Pillow cannot open (SVG) are skipped, not counted as errors.

cache-control on overwrite: one year for blog-images and for app dish photos
food-items/<seller>/<item uuid>-<unix seconds> (never overwritten); 3600 for other food-items
paths (the admin app overwrites fixed <item>.jpg names, a year-long cache would show the old dish).

Reads the SERVICE ROLE key from envs/.env.$ENV like the backend (PROD is ENV=prd, DEV is ENV=dev).
Dry run by default. --apply saves each original under --backup-dir/<bucket>/<path> before
overwriting it; --restore uploads those originals back.

Usage (from backend/src):
    ENV=prd python -m scripts.recompress_public_images
    ENV=prd python -m scripts.recompress_public_images --apply --backup-dir ~/sariko-image-backup-20261123
    ENV=prd python -m scripts.recompress_public_images --restore ~/sariko-image-backup-20261123
"""

import argparse
import io
import mimetypes
import os
import re
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from PIL import Image

from clients.supabase import get_supabase_client
from utils.storage import ONE_YEAR, compress_to_jpeg

ENVS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "envs")
SCOPES = [("blog-images", ""), ("sariko-public", "food-items")]
MIN_BYTES = 300 * 1024
MAX_RATIO = 0.7
PAGE = 100
APP_DISH = re.compile(r"food-items/[^/]+/[0-9a-f-]{36}-\d+")  # sellers.py upload_food_item_image


def walk(bucket, prefix):
    """Yield (path, size) for every file under prefix: list() is one folder level, 100 per page."""
    offset = 0
    while True:
        page = bucket.list(prefix, {"limit": PAGE, "offset": offset})
        for item in page:
            path = f"{prefix}/{item['name']}" if prefix else item["name"]
            if item.get("id") is None:  # folder
                yield from walk(bucket, path)
            else:
                yield path, (item.get("metadata") or {}).get("size", 0)
        if len(page) < PAGE:
            return
        offset += PAGE


def shrink(raw):
    """Return (jpeg bytes to write or None, action)."""
    try:
        img = Image.open(io.BytesIO(raw))
    except Exception:
        return None, "skip, not an image"
    if img.format == "GIF" or getattr(img, "n_frames", 1) > 1:
        return None, "skip, animated"
    new = compress_to_jpeg(raw)
    Image.open(io.BytesIO(new)).load()  # a broken result raises -> counted as an error, nothing written
    if len(new) >= MAX_RATIO * len(raw):
        return None, "skip, no gain"
    return new, "compress"


def recompress(storage, apply, backup_dir):
    errors = 0
    buckets = {b.id for b in storage.list_buckets()}
    for bucket_id, prefix in SCOPES:
        if bucket_id not in buckets:
            print(f"{bucket_id}: bucket not found, skipped")
            continue
        bucket = storage.from_(bucket_id)
        files = changed = before = saved = 0
        for path, size in walk(bucket, prefix):
            files += 1
            before += size
            if size <= MIN_BYTES:
                print(f"{bucket_id}/{path}  {size // 1024} KB  skip, small")
                continue
            try:
                raw = bucket.download(path)
                new, action = shrink(raw)
                after = len(new) if new else len(raw)
                print(f"{bucket_id}/{path}  {len(raw) // 1024} KB -> {after // 1024} KB  {action}")
                if not new:
                    continue
                changed += 1
                saved += len(raw) - len(new)
                if not apply:
                    continue
                keep = os.path.join(backup_dir, bucket_id, path)
                os.makedirs(os.path.dirname(keep), exist_ok=True)
                try:
                    with open(keep, "xb") as f:  # an earlier run's copy is the real original: keep it
                        f.write(raw)
                except FileExistsError:
                    pass
                cache = ONE_YEAR if bucket_id == "blog-images" or APP_DISH.fullmatch(path) else "3600"
                bucket.upload(path, new, {"content-type": "image/jpeg", "upsert": "true", "cache-control": cache})
            except Exception as e:
                errors += 1
                print(f"{bucket_id}/{path}  ERROR {e!r}")
        print(f"TOTAL {bucket_id}/{prefix}: {files} files, {changed} {'compressed' if apply else 'to compress'}, "
              f"{before // 1024} KB -> {(before - saved) // 1024} KB")
    return errors


def restore(storage, backup_dir):
    errors = 0
    for root, _, names in os.walk(backup_dir):
        for name in names:
            full = os.path.join(root, name)
            bucket_id, path = os.path.relpath(full, backup_dir).split("/", 1)
            try:
                with open(full, "rb") as f:
                    storage.from_(bucket_id).upload(path, f.read(), {
                        "content-type": mimetypes.guess_type(path)[0] or "image/jpeg",
                        "upsert": "true", "cache-control": "3600"})
                print(f"{bucket_id}/{path}  restored")
            except Exception as e:
                errors += 1
                print(f"{bucket_id}/{path}  ERROR {e!r}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="overwrite the files (default: dry run)")
    parser.add_argument("--backup-dir", help="where originals are saved before overwrite (required with --apply)")
    parser.add_argument("--restore", metavar="BACKUP_DIR", help="upload the originals in BACKUP_DIR back")
    args = parser.parse_args(argv)
    if args.apply and not args.backup_dir:
        parser.error("--apply needs --backup-dir")

    env_file = os.path.join(ENVS_DIR, f".env.{os.environ.get('ENV', 'local')}")
    if not os.path.isfile(env_file):
        sys.exit(f"Env file not found: {env_file} (PROD is ENV=prd, DEV is ENV=dev)")
    load_dotenv(env_file, override=True)  # the file wins over stray shell variables
    print(f"Supabase host: {urlparse(os.environ.get('SUPABASE_URL', '')).hostname}")

    if args.apply:
        os.makedirs(args.backup_dir, exist_ok=True)
        if not os.access(args.backup_dir, os.W_OK):
            sys.exit(f"Backup dir not writable: {args.backup_dir}")

    storage = get_supabase_client().storage
    if args.restore:
        errors = restore(storage, args.restore)
    else:
        errors = recompress(storage, args.apply, args.backup_dir)
    print(f"Done, {errors} error(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
