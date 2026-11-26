"""One Hugging Face model, baked into an image in layers of at most 4 GB.

    python3 models.py lock <repo> <tag>   write locks/<tag>.json: revision, files, sizes, hashes
    python3 models.py plan                which layer holds which piece (to size the Dockerfile)
    python3 models.py fits <layers>       fail if the model needs more layers than the Dockerfile has
    python3 models.py part <i>            download layer i (nothing when i is past the plan)
    python3 models.py verify              hash every file from its pieces (at build time)
    python3 models.py has <repo>          exit 0 if this image carries that model
    python3 models.py assemble            join the split files into AISUKA_LLM_DIR (on pod start)

Files no larger than a piece go straight to AISUKA_LLM_DIR, several to a
layer; larger ones are cut into 4 GB pieces under AISUKA_PARTS, one piece per
layer, and joined when the pod starts (about a minute for 10 GB, no network).
The registry and Runpod both cope badly with layers much larger than that.

Standard library only: it runs on the image's own Python before anything
else is installed for it.
"""

import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK = Path(os.environ.get("AISUKA_LOCK", HERE / "model.json"))
LLM_DIR = Path(os.environ.get("AISUKA_LLM_DIR", "/models/llm"))
PARTS = Path(os.environ.get("AISUKA_PARTS", "/opt/aisuka/parts"))
PIECE = int(os.environ.get("AISUKA_PIECE", 4 << 30))
USER_AGENT = "aisuka-runpod-images"


def _headers(extra=None):
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers | (extra or {})


def _get_json(url):
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def lock(repo, tag):
    """Pin the repository's current revision and every file in it."""
    info = _get_json(f"https://huggingface.co/api/models/{repo}")
    rev = info["sha"]
    tree = _get_json(f"https://huggingface.co/api/models/{repo}/tree/{rev}?recursive=1")
    # vLLM loads safetensors; other copies of the same weights are dead weight.
    safetensors = any(e["path"].endswith(".safetensors") for e in tree)
    other_weights = (".bin", ".pt", ".pth", ".h5", ".msgpack", ".onnx", ".gguf", ".ckpt")
    files = []
    for entry in tree:
        if entry["type"] != "file" or entry["path"] in (".gitattributes", "README.md"):
            continue
        if safetensors and entry["path"].endswith(other_weights):
            continue
        lfs = entry.get("lfs")
        files.append(
            {
                "path": entry["path"],
                "size": entry["size"],
                # Large files are hashed with sha256; small ones only have
                # their git blob id, which `verify` checks the git way.
                "sha256": lfs["oid"] if lfs else None,
                "git_oid": None if lfs else entry["oid"],
            }
        )
    files.sort(key=lambda f: f["path"])
    out = HERE / "locks" / f"{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {"repo": repo, "revision": rev, "tag": tag, "files": files}
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    total = sum(f["size"] for f in files)
    print(f"{out}: {repo}@{rev[:10]}, {len(files)} files, {total / 2**30:.1f} GiB")


def _model():
    return json.loads(LOCK.read_text(encoding="utf-8"))


def _pieces(f):
    return max(1, (f["size"] + PIECE - 1) // PIECE)


def _dst(f, k, n):
    if n == 1:
        return LLM_DIR / f["path"]
    return PARTS / f"{f['path']}.part{k:02d}"


def plan():
    """Layers, each a list of (file, piece, pieces): small files share one."""
    layers, current, room = [], [], 0
    for f in _model()["files"]:
        n = _pieces(f)
        for k in range(n):
            size = min(PIECE, f["size"] - k * PIECE)
            if current and room + size > PIECE:
                layers.append(current)
                current, room = [], 0
            current.append((f, k, n))
            room += size
    if current:
        layers.append(current)
    return layers


def _download(model, f, k, n):
    start = k * PIECE
    end = min((k + 1) * PIECE, f["size"]) - 1
    dst = _dst(f, k, n)
    dst.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{f['path']}"
    want = end - start + 1
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers=_headers({"Range": f"bytes={start}-{end}"}))
            with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as out:
                while chunk := r.read(16 << 20):
                    out.write(chunk)
            if dst.stat().st_size == want:
                print("ok", dst, want, flush=True)
                return
            raise RuntimeError(f"got {dst.stat().st_size} bytes, expected {want}")
        except Exception as e:
            print("retry", f["path"], k, e, flush=True)
            time.sleep(5 * (attempt + 1))
    sys.exit(f"could not download {f['path']} piece {k}")


def part(i):
    layers = plan()
    if i >= len(layers):
        print(f"layer {i}: nothing (the model has {len(layers)})")
        return
    model = _model()
    for f, k, n in layers[i]:
        _download(model, f, k, n)


def fits(count):
    need = len(plan())
    if need > count:
        sys.exit(f"the model needs {need} layers and the Dockerfile has {count}; add RUN lines")
    print(f"{need} of {count} layers used")


def _files(f):
    n = _pieces(f)
    return [_dst(f, k, n) for k in range(n)]


def verify():
    bad = []
    for f in _model()["files"]:
        if f["sha256"]:
            h = hashlib.sha256()
        else:
            h = hashlib.sha1(b"blob %d\0" % f["size"])
        for p in _files(f):
            with open(p, "rb") as src:
                while chunk := src.read(16 << 20):
                    h.update(chunk)
        ok = h.hexdigest() == (f["sha256"] or f["git_oid"])
        print("ok " if ok else "BAD", f["path"])
        if not ok:
            bad.append(f["path"])
    if bad:
        sys.exit("corrupt: " + ", ".join(bad))


def has(repo):
    return LOCK.exists() and _model()["repo"] == repo


def assemble():
    for f in _model()["files"]:
        pieces = _files(f)
        if len(pieces) == 1:
            continue
        dst = LLM_DIR / f["path"]
        if dst.exists() and dst.stat().st_size == f["size"]:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".tmp")
        with open(tmp, "wb") as out:
            for p in pieces:
                with open(p, "rb") as src:
                    while chunk := src.read(64 << 20):
                        out.write(chunk)
        if tmp.stat().st_size != f["size"]:
            raise RuntimeError(f"joining {f['path']}: wrong size")
        tmp.replace(dst)
        print(f"joined {f['path']} ({f['size'] >> 20} MB)", flush=True)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "lock":
        lock(*args)
    elif cmd == "plan":
        for i, layer in enumerate(plan()):
            print(i, ", ".join(f"{f['path']}[{k + 1}/{n}]" for f, k, n in layer))
    elif cmd == "fits":
        fits(int(args[0]))
    elif cmd == "part":
        part(int(args[0]))
    elif cmd == "verify":
        verify()
    elif cmd == "has":
        sys.exit(0 if has(args[0]) else 1)
    elif cmd == "assemble":
        assemble()
    else:
        sys.exit(__doc__)
