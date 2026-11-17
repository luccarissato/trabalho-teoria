from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeneratedGraph:
    name: str
    vertex_count: int
    edges: tuple[tuple[int, int], ...]
    seed: int
    family: str
    case_name: str


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="datasets")
    parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("seed deve ser não negativa")
    return args


def mulberry32(seed: int):
    state = seed & 0xFFFFFFFF

    def random() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        value = state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFFFFFF
        value ^= (value + (((value ^ (value >> 7)) * (value | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 4294967296

    return random


def normalize_edges(vertex_count: int, edges) -> tuple[tuple[int, int], ...]:
    normalized: set[tuple[int, int]] = set()
    for u, v in edges:
        if not (0 <= u < vertex_count and 0 <= v < vertex_count) or u == v:
            raise ValueError(f"aresta inválida no gerador: {u} {v}")
        normalized.add((u, v) if u < v else (v, u))
    return tuple(sorted(normalized))


def graph(name, vertex_count, edges, seed, family, case_name) -> GeneratedGraph:
    return GeneratedGraph(
        name,
        vertex_count,
        normalize_edges(vertex_count, edges),
        seed,
        family,
        case_name,
    )


def path_edges(n: int) -> list[tuple[int, int]]:
    return [(index, index + 1) for index in range(max(0, n - 1))]


def cycle_edges(n: int) -> list[tuple[int, int]]:
    return path_edges(n) if n < 3 else [*path_edges(n), (0, n - 1)]


def complete_bipartite(left_size: int, right_size: int) -> list[tuple[int, int]]:
    return [
        (left, left_size + right)
        for left in range(left_size)
        for right in range(right_size)
    ]


def random_graph(n: int, probability: float, seed: int) -> list[tuple[int, int]]:
    random = mulberry32(seed)
    return [
        (u, v)
        for u in range(n)
        for v in range(u + 1, n)
        if random() < probability
    ]


def serialize_graph(item: GeneratedGraph) -> str:
    lines = [
        "TC_GRAPH 1",
        f"V {item.vertex_count}",
        f"E {len(item.edges)}",
        f"SEED {item.seed}",
        f"FAMILY {item.family}",
        f"CASE {item.case_name}",
        "EDGES",
        *(f"{u} {v}" for u, v in item.edges),
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_arguments()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    items = [
        graph("00_empty", 0, [], args.seed, "edge_case", "empty"),
        graph("01_singleton", 1, [], args.seed, "edge_case", "singleton"),
        graph("02_single_edge", 2, [(0, 1)], args.seed, "edge_case", "single_edge"),
        graph("03_path_6", 6, path_edges(6), args.seed, "constructed_path", "positive"),
        graph("04_cycle_6", 6, cycle_edges(6), args.seed, "constructed_cycle", "positive"),
        graph(
            "05_odd_star_5",
            5,
            [(0, 1), (0, 2), (0, 3), (0, 4)],
            args.seed,
            "odd_degree",
            "negative",
        ),
        graph(
            "06_disconnected_triangles",
            6,
            [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)],
            args.seed,
            "disconnected",
            "negative",
        ),
        graph(
            "07_k3_5",
            8,
            complete_bipartite(3, 5),
            args.seed,
            "unbalanced_bipartite",
            "hard_negative",
        ),
        graph(
            "08_gnp_8",
            8,
            random_graph(8, 0.35, args.seed + 8),
            args.seed + 8,
            "gnp",
            "random",
        ),
    ]

    manifest: dict[str, object] = {
        "format": "TC_GRAPH 1",
        "generator_seed": args.seed,
        "graph_count": len(items),
        "graphs": [],
    }
    graph_entries: list[dict[str, object]] = []
    for item in items:
        filename = f"{item.name}.graph"
        content = serialize_graph(item)
        (output / filename).write_text(content, encoding="utf-8", newline="\n")
        max_edges = item.vertex_count * (item.vertex_count - 1) // 2
        graph_entries.append(
            {
                "file": filename,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "vertices": item.vertex_count,
                "edges": len(item.edges),
                "density": 0 if max_edges == 0 else len(item.edges) / max_edges,
                "seed": item.seed,
                "family": item.family,
                "case": item.case_name,
            }
        )
    manifest["graphs"] = graph_entries
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Gerados {len(items)} grafos determinísticos em {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
