from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from file_hash import canonical_bytes, canonical_sha256


FIGURE_SOURCES = {
    "euler_time_loglog.svg": ["results/raw/eulerian_scale_timing.csv", "results/summary/timing.csv"],
    "euler_ratio.svg": ["results/raw/eulerian_scale_timing.csv", "results/summary/timing.csv"],
    "hamilton_time.svg": ["results/raw/paired_timing.csv", "results/summary/timing.csv"],
    "hamilton_states.svg": ["results/raw/paired_timing.csv", "results/summary/timing.csv"],
    "hamilton_ratio.svg": [
        "results/raw/paired_timing.csv",
        "results/summary/timing.csv",
        "datasets/experimental-manifest.json",
    ],
    "hamilton_viability.svg": ["results/raw/pilot_timing.csv"],
    "paired_algorithms.svg": ["results/raw/paired_timing.csv", "results/summary/timing.csv"],
    "language_ratio.svg": ["results/raw/paired_timing.csv", "results/summary/timing.csv"],
    "memory_peak.svg": ["results/raw/paired_memory.csv", "results/raw/eulerian_scale_memory.csv", "results/summary/memory.csv"],
    "memory_increment.svg": ["results/raw/paired_memory.csv", "results/raw/eulerian_scale_memory.csv", "results/summary/memory.csv"],
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="results/final-manifest.json")
    return parser.parse_args()


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def source_files(root: Path, output: Path) -> list[Path]:
    raw = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    ).stdout
    paths = [root / item.decode("utf-8") for item in raw.split(b"\0") if item]
    excluded = {output.resolve(), (root / "relatorio.md").resolve()}
    return sorted({path.resolve() for path in paths if path.is_file() and path.resolve() not in excluded})


def main() -> int:
    args = parse_arguments()
    root = Path(args.root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output

    file_entries = []
    for path in source_files(root, output):
        data = canonical_bytes(path)
        file_entries.append(
            {
                "file": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
    tree_hasher = hashlib.sha256()
    for entry in file_entries:
        tree_hasher.update(entry["file"].encode("utf-8"))
        tree_hasher.update(b"\0")
        tree_hasher.update(entry["sha256"].encode("ascii"))
        tree_hasher.update(b"\n")

    environment = json.loads((root / "results" / "manifest.json").read_text(encoding="utf-8"))
    datasets = json.loads((root / "datasets" / "experimental-manifest.json").read_text(encoding="utf-8"))
    figures = {
        name: {
            "file": f"results/charts/{name}",
            "sha256": canonical_sha256(root / "results" / "charts" / name),
            "sources": [
                {"file": source, "sha256": canonical_sha256(root / source)} for source in sources
            ],
        }
        for name, sources in FIGURE_SOURCES.items()
    }
    manifest = {
        "schema_version": 2,
        "hash_line_endings": "LF",
        "project": "Caminho Euleriano x Caminho Hamiltoniano",
        "base_commit": git(root, "rev-parse", "HEAD"),
        "tracked_worktree_dirty": bool(git(root, "status", "--porcelain", "--untracked-files=no")),
        "source_tree_sha256": tree_hasher.hexdigest(),
        "commands": {
            "quick_validation": "powershell -ExecutionPolicy Bypass -File .\\tools\\run-all.ps1 -Quick",
            "full_reproduction": "powershell -ExecutionPolicy Bypass -File .\\tools\\run-all.ps1 -Full",
        },
        "environment": environment,
        "datasets": {
            "manifest": "datasets/experimental-manifest.json",
            "manifest_sha256": canonical_sha256(root / "datasets" / "experimental-manifest.json"),
            "generator": datasets["generator"],
            "generator_sha256": datasets["generator_sha256"],
            "seed": datasets["generator_seed"],
            "graph_count": datasets["graph_count"],
        },
        "figures": figures,
        "files": file_entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Manifesto final: {output}")
    print(f"Árvore-fonte: {manifest['source_tree_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
