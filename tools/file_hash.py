from __future__ import annotations

import hashlib
from pathlib import Path


TEXT_SUFFIXES = {".c", ".csv", ".graph", ".json", ".md", ".ps1", ".py", ".svg", ".txt"}


def canonical_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES or path.name == ".gitignore":
        return data.replace(b"\r\n", b"\n")
    return data


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()
