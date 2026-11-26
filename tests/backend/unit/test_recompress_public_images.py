"""scripts/recompress_public_images.py against an in-memory storage. No DB, no network.

Run from tests/backend:  pytest unit/test_recompress_public_images.py
"""
import io
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts import recompress_public_images as script

UUID = "0e80a1e1-f82a-4ece-9fda-05ac424facb1"


def _encode(img, fmt, **kw):
    buf = io.BytesIO()
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def _noise(size, mode="RGB"):
    return Image.frombytes(mode, size, os.urandom(size[0] * size[1] * len(mode)))


BIG_PNG = _encode(_noise((600, 600)), "PNG")                      # ~1 MB, shrinks a lot
NO_GAIN = _encode(_noise((1000, 1000)), "JPEG", quality=70)        # already JPEG 70: re-encode ~same size
GIF = _encode(Image.new("P", (10, 10)), "GIF") + b"\0" * 2_000_000  # padded past 300 KB, still opens
SMALL = b"\xff\xd8" + b"x" * 200 * 1024


class Bucket:
    def __init__(self, files):
        self.files, self.uploads, self.broken, self.on_upload = dict(files), [], set(), None
        self.meta = {}  # path -> extra list() metadata (cacheControl, mimetype)

    def list(self, prefix, opts):
        base = f"{prefix}/" if prefix else ""
        items = {}
        for path, data in self.files.items():
            if path.startswith(base):
                head, _, rest = path[len(base):].partition("/")
                items[head] = {"name": head, "id": None} if rest else {"name": head, "id": "x", "metadata": {"size": len(data), **self.meta.get(path, {})}}
        page = sorted(items.values(), key=lambda i: i["name"])
        return page[opts["offset"]:opts["offset"] + opts["limit"]]

    def download(self, path):
        if path in self.broken:
            raise RuntimeError("download failed")
        return self.files[path]

    def upload(self, path, data, opts):
        if self.on_upload:
            self.on_upload(path)
        self.uploads.append((path, opts))
        self.files[path] = data


class Storage:
    def __init__(self, **buckets):
        self.buckets = {k: Bucket(v) for k, v in buckets.items()}

    def list_buckets(self):
        return [SimpleNamespace(id=k) for k in self.buckets]

    def from_(self, bucket_id):
        return self.buckets[bucket_id]


@pytest.fixture
def run(monkeypatch, tmp_path, capsys):
    envs = tmp_path / "envs"
    envs.mkdir()
    (envs / ".env.dev").write_text("SUPABASE_URL=https://devref.supabase.co\nSUPABASE_API_KEY=secret-key-xyz\n")
    monkeypatch.setattr(script, "ENVS_DIR", str(envs))
    monkeypatch.setenv("SUPABASE_URL", "https://stub.supabase.co")  # restored after the test (the script overrides it)
    monkeypatch.setenv("SUPABASE_API_KEY", "stub")

    def _run(storage, *argv, env="dev"):
        monkeypatch.setenv("ENV", env)
        monkeypatch.setattr(script, "get_supabase_client", lambda: SimpleNamespace(storage=storage))
        with pytest.raises(SystemExit) as e:
            script.main(list(argv))
        return e.value.code, capsys.readouterr()
    return _run


def _tc3_storage():
    s = Storage(**{"blog-images": {"a.png": BIG_PNG, "b.jpg": SMALL, "c.gif": GIF, "d.jpg": NO_GAIN}})
    return s, s.buckets["blog-images"]


def _line(out, path):
    return next(line for line in out.splitlines() if line.startswith(path + " "))


def test_tc3_dry_run_reports_and_writes_nothing(run):
    s, b = _tc3_storage()
    code, cap = run(s)
    assert code == 0 and b.uploads == []
    assert _line(cap.out, "blog-images/a.png").endswith("compress")
    assert _line(cap.out, "blog-images/b.jpg").endswith("skip, small")
    assert _line(cap.out, "blog-images/c.gif").endswith("skip, animated")
    assert _line(cap.out, "blog-images/d.jpg").endswith("skip, no gain")


def assert_backup(path, original):
    assert path.read_bytes() == original  # saved BEFORE the upload


def test_tc3_apply_backs_up_then_overwrites_one_file(run, tmp_path):
    s, b = _tc3_storage()
    backup = tmp_path / "bk"
    b.on_upload = lambda path: assert_backup(backup / "blog-images" / path, BIG_PNG)
    code, _ = run(s, "--apply", "--backup-dir", str(backup))
    assert code == 0
    assert b.uploads == [("a.png", {"content-type": "image/jpeg", "upsert": "true", "cache-control": "31536000"})]
    assert Image.open(io.BytesIO(b.files["a.png"])).format == "JPEG"


def test_tc3_apply_without_backup_dir_exits_before_storage(run):
    s, b = _tc3_storage()
    code, cap = run(s, "--apply")
    assert code == 2 and b.uploads == [] and "--backup-dir" in cap.err


def test_tc3_one_failed_download_continues_and_exits_1(run, tmp_path):
    s, b = _tc3_storage()
    b.files["e.png"] = BIG_PNG
    b.broken.add("a.png")
    code, cap = run(s, "--apply", "--backup-dir", str(tmp_path / "bk"))
    assert code == 1 and "blog-images/a.png  ERROR" in cap.out and "1 error(s)" in cap.out
    assert [p for p, _ in b.uploads] == ["e.png"]


def test_tc10_walks_subfolders_and_pages(run):
    food = {f"food-items/{s}/{i}": b"x" for s in ("s1", "s2") for i in range(60)}
    s = Storage(**{"sariko-public": food, "blog-images": {f"{i}.png": b"x" for i in range(130)}})
    code, cap = run(s)
    paths = [line.split()[0] for line in cap.out.splitlines() if line.endswith("skip, small")]
    assert code == 0 and len(paths) == 250 and len(set(paths)) == 250


def test_tc11_detects_by_content(run, tmp_path):
    frames = [_noise((400, 400)) for _ in range(2)]
    anim = _encode(frames[0], "WEBP", save_all=True, append_images=frames[1:], lossless=True)
    clear = _noise((600, 600), "RGBA")
    clear.putalpha(Image.new("L", (600, 600), 0))  # fully transparent
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><!--' + b"x" * 400 * 1024 + b"--></svg>"
    dish = f"food-items/s/{UUID}-1700000000"
    files = {dish: _encode(_noise((1000, 1000)), "JPEG", quality=95),
             "food-items/s/anim.webp": anim, "food-items/s/logo.svg": svg, "food-items/s/clear.png": _encode(clear, "PNG")}
    s = Storage(**{"sariko-public": files})
    b = s.buckets["sariko-public"]
    assert len(anim) > 300 * 1024
    code, cap = run(s, "--apply", "--backup-dir", str(tmp_path / "bk"))
    assert code == 0, cap.out
    assert _line(cap.out, f"sariko-public/{dish}").endswith("compress")
    assert _line(cap.out, "sariko-public/food-items/s/anim.webp").endswith("skip, animated")
    assert _line(cap.out, "sariko-public/food-items/s/logo.svg").endswith("skip, not an image")
    assert sorted(p for p, _ in b.uploads) == sorted([dish, "food-items/s/clear.png"])
    assert Image.open(io.BytesIO(b.files["food-items/s/clear.png"])).getpixel((5, 5)) == (255, 255, 255)


def test_tc12_second_apply_keeps_first_backup(run, tmp_path):
    s, b = _tc3_storage()
    backup = tmp_path / "bk"
    run(s, "--apply", "--backup-dir", str(backup))
    b.files["a.png"] = _encode(_noise((600, 600)), "PNG")  # still over the threshold on run 2
    run(s, "--apply", "--backup-dir", str(backup))
    assert len(b.uploads) == 2
    assert (backup / "blog-images" / "a.png").read_bytes() == BIG_PNG


def test_tc13_restore_puts_originals_back(run, tmp_path):
    s, b = _tc3_storage()
    backup = tmp_path / "bk"
    run(s, "--apply", "--backup-dir", str(backup))
    code, _ = run(s, "--restore", str(backup))
    assert code == 0 and b.files["a.png"] == BIG_PNG
    assert b.uploads[-1] == ("a.png", {"content-type": "image/png", "upsert": "true", "cache-control": "3600"})


def test_tc14_missing_env_file_exits_before_storage(run, monkeypatch):
    def no_storage():
        raise AssertionError("storage called")
    with pytest.raises(SystemExit) as e:
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setattr(script, "get_supabase_client", no_storage)
        script.main([])
    assert ".env.prod" in str(e.value.code)


def test_tc14_first_line_is_host_without_key(run):
    s, _ = _tc3_storage()
    _, cap = run(s)
    assert cap.out.splitlines()[0] == "Supabase host: devref.supabase.co"
    assert "secret-key-xyz" not in cap.out + cap.err


def test_tc15_cache_control_by_path(run, tmp_path):
    admin, app = f"food-items/s/{UUID}.jpg", f"food-items/s/{UUID}-1700000000"
    s = Storage(**{"sariko-public": {admin: BIG_PNG, app: BIG_PNG}})
    run(s, "--apply", "--backup-dir", str(tmp_path / "bk"))
    cache = {p: o["cache-control"] for p, o in s.buckets["sariko-public"].uploads}
    assert cache == {admin: "3600", app: "31536000"}


def test_cache_fix_reuploads_same_bytes_with_target_cache(run):
    old_dish, app_dish, done = "food-items/s/item.jpg", f"food-items/s/{UUID}-1700000000", "food-items/s/ok.jpg"
    avatar, new_avatar = "avatar-sellers/p/avatar.jpg", "avatar-sellers/p/avatar-1700000000.jpg"
    s = Storage(**{"sariko-public": {old_dish: b"d1", app_dish: b"d2", done: b"d3", avatar: b"a1", new_avatar: b"a2"},
                   "blog-images": {"x.png": b"b"}})
    b = s.buckets["sariko-public"]
    b.meta = {old_dish: {"cacheControl": "no-cache", "mimetype": "image/png"},
              app_dish: {"cacheControl": "no-cache", "mimetype": "image/jpeg"},
              done: {"cacheControl": "max-age=3600", "mimetype": "image/jpeg"},
              avatar: {"cacheControl": "no-cache", "mimetype": "image/jpeg"},
              new_avatar: {"cacheControl": "no-cache", "mimetype": "image/jpeg"}}  # not avatar.jpg: out of scope

    code, cap = run(s, "--cache-only")
    assert code == 0 and b.uploads == [] and s.buckets["blog-images"].uploads == []
    assert "TOTAL sariko-public/food-items: 2 to change, 1 skipped" in cap.out

    code, cap = run(s, "--cache-only", "--apply")
    assert code == 0 and s.buckets["blog-images"].uploads == []
    assert sorted(b.uploads) == sorted([
        (old_dish, {"content-type": "image/png", "upsert": "true", "cache-control": "3600"}),
        (app_dish, {"content-type": "image/jpeg", "upsert": "true", "cache-control": "31536000"}),
        (avatar, {"content-type": "image/jpeg", "upsert": "true", "cache-control": "3600"})])
    assert (b.files[old_dish], b.files[app_dish], b.files[avatar]) == (b"d1", b"d2", b"a1")  # bytes unchanged


def test_cache_fix_failed_file_exits_1(run):
    s = Storage(**{"sariko-public": {"food-items/s/a.jpg": b"1", "food-items/s/b.jpg": b"2"}})
    b = s.buckets["sariko-public"]
    b.broken.add("food-items/s/a.jpg")
    code, cap = run(s, "--cache-only", "--apply")
    assert code == 1 and [p for p, _ in b.uploads] == ["food-items/s/b.jpg"] and "1 error(s)" in cap.out
