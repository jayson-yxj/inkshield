"""Resume official checkpoint download and verify official Hugging Face LFS hash."""
from pathlib import Path
import hashlib
import json
import time
import urllib.request

ROOT = Path(__file__).parent
URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt"
EXPECTED = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
SIZE = 156008466
path = ROOT / "models" / "sam2.1_hiera_tiny.pt"
path.parent.mkdir(exist_ok=True)
for attempt in range(8):
    offset = path.stat().st_size if path.exists() else 0
    if offset == SIZE:
        break
    request = urllib.request.Request(URL, headers={"Range": f"bytes={offset}-", "User-Agent": "sam21-research-prototype"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            # Some CDN responses ignore ranges. Restart instead of corrupting the file.
            append = response.status == 206 and response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")
            with path.open("ab" if append else "wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
                    stream.flush()
            print(f"Downloaded {path.stat().st_size}/{SIZE}", flush=True)
    except (OSError, TimeoutError) as exc:
        print(f"Attempt {attempt + 1}: {exc}", flush=True)
actual = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
if path.stat().st_size != SIZE or actual != EXPECTED:
    raise RuntimeError(f"Official checkpoint verification failed: size={path.stat().st_size}, sha256={actual}")
provenance = {
    "source_repository": "https://github.com/facebookresearch/sam2",
    "source_commit": "2b90b9f5ceec907a1c18123530e92e794ad901a4",
    "download_url": URL,
    "independent_official_hash_source": "https://huggingface.co/facebook/sam2.1-hiera-tiny/raw/main/sam2.1_hiera_tiny.pt",
    "bytes": SIZE,
    "sha256": actual,
    "license": "Apache-2.0",
    "license_evidence": "vendor/sam2/README.md:198 explicitly includes SAM2 model checkpoints and code",
    "cuda_extension_built": False,
}
(ROOT / "models" / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
print(json.dumps(provenance, indent=2), flush=True)
