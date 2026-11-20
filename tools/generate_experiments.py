from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from file_hash import canonical_sha256

from generate import (
    GeneratedGraph,
    complete_bipartite,
    cycle_edges,
    graph,
    path_edges,
    random_graph,
    serialize_graph,
)


PAIRED_SIZES = (8, 10, 13, 16, 20, 25)
HARD_SIZES = (4, 5, 6, 8, 10, 12)
PILOT_SIZES = (8, 10, 12, 14, 16)
EULERIAN_SIZES = (1000, 2000, 4000, 8000, 16000, 32000)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="datasets")
    parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("seed deve ser não negativa")
    return args


def unbalanced_parts(vertex_count: int) -> tuple[int, int]:
    left = max(1, (vertex_count - 2) // 2)
    right = vertex_count - left
    if right - left < 2:
        raise ValueError("a família difícil exige partes com diferença mínima de dois")
    return left, right


def paired_graphs(seed: int) -> list[GeneratedGraph]:
    items: list[GeneratedGraph] = []
    for size in PAIRED_SIZES:
        items.append(
            graph(
                f"path_v{size:03d}",
                size,
                path_edges(size),
                seed + size,
                "constructed_path",
                "favorable_positive",
            )
        )
        items.append(
            graph(
                f"gnp_v{size:03d}",
                size,
                random_graph(size, 0.5, seed + 1000 + size),
                seed + 1000 + size,
                "gnp_p050",
                "random",
            )
        )
    for size in HARD_SIZES:
        left, right = unbalanced_parts(size)
        items.append(
            graph(
                f"hard_bipartite_v{size:03d}",
                size,
                complete_bipartite(left, right),
                seed + 2000 + size,
                "unbalanced_bipartite",
                "hard_negative",
            )
        )
    return items


def pilot_graphs(seed: int) -> list[GeneratedGraph]:
    items: list[GeneratedGraph] = []
    for size in PILOT_SIZES:
        left, right = unbalanced_parts(size)
        items.append(
            graph(
                f"hard_bipartite_v{size:03d}",
                size,
                complete_bipartite(left, right),
                seed + 3000 + size,
                "unbalanced_bipartite_pilot",
                "hard_negative",
            )
        )
    return items


def eulerian_scale_graphs(seed: int) -> list[GeneratedGraph]:
    return [
        graph(
            f"cycle_v{size:05d}",
            size,
            cycle_edges(size),
            seed + 4000 + size,
            "constructed_cycle_scale",
            "linear_positive",
        )
        for size in EULERIAN_SIZES
    ]


def write_suite(
    root: Path,
    suite: str,
    items: list[GeneratedGraph],
    seed: int,
) -> list[dict[str, object]]:
    output = root / suite
    output.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for item in items:
        filename = f"{item.name}.graph"
        content = serialize_graph(item)
        (output / filename).write_text(content, encoding="utf-8", newline="\n")
        max_edges = item.vertex_count * (item.vertex_count - 1) // 2
        entries.append(
            {
                "file": f"{suite}/{filename}",
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "vertices": item.vertex_count,
                "edges": len(item.edges),
                "density": 0 if max_edges == 0 else len(item.edges) / max_edges,
                "seed": item.seed,
                "family": item.family,
                "case": item.case_name,
                "suite": suite,
            }
        )
    suite_manifest = {
        "format": "TC_GRAPH 1",
        "suite": suite,
        "generator_seed": seed,
        "graph_count": len(entries),
        "graphs": entries,
    }
    (output / "manifest.json").write_text(
        json.dumps(suite_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return entries


def main() -> int:
    args = parse_arguments()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    suites = {
        "paired": paired_graphs(args.seed),
        "pilot": pilot_graphs(args.seed),
        "eulerian-scale": eulerian_scale_graphs(args.seed),
    }
    all_entries: list[dict[str, object]] = []
    for suite, items in suites.items():
        all_entries.extend(write_suite(root, suite, items, args.seed))

    generator_hash = canonical_sha256(Path(__file__))
    manifest = {
        "format": "TC_GRAPH 1",
        "suite_version": 1,
        "generator": "tools/generate_experiments.py",
        "generator_sha256": generator_hash,
        "generator_seed": args.seed,
        "paired_sizes": list(PAIRED_SIZES),
        "hard_sizes": list(HARD_SIZES),
        "pilot_sizes": list(PILOT_SIZES),
        "eulerian_scale_sizes": list(EULERIAN_SIZES),
        "graph_count": len(all_entries),
        "graphs": all_entries,
    }
    (root / "experimental-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Gerados {len(all_entries)} grafos experimentais determinísticos "
        f"em {root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
