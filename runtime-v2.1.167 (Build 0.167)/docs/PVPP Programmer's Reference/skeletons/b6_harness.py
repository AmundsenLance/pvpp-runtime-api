"""B.6 Test harness: runtime identity check and banked expectations."""

import hashlib, os
import pvpp_runtime


def runtime_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(pvpp_runtime.__file__)))


def verify_runtime_identity(root=None, manifest="V0167_FILE_HASHES.sha256"):
    """Return manifest entries that are missing or whose SHA-256 differs.

    An empty list means the tree is frozen Runtime v2.1.167 (13.7). With the build-141
    manifest, the one expected entry is pyproject.toml: the decision core is unchanged.
    """
    root = root or runtime_root()
    bad = []
    with open(os.path.join(root, manifest)) as fh:
        for line in fh:
            digest, rel = line.split(None, 1)
            path = os.path.join(root, rel.strip())
            if not os.path.exists(path):
                bad.append(rel.strip())
                continue
            with open(path, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != digest:
                    bad.append(rel.strip())
    return bad
