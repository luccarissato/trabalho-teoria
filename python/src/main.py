from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from algorithms import find_eulerian_path, find_hamiltonian_path  # noqa: E402
from graph import load_graph  # noqa: E402
from validate import validate_eulerian_path, validate_hamiltonian_path  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True, choices=("eulerian", "hamiltonian"))
    parser.add_argument("--input", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    graph = load_graph(args.input)
    result = (
        find_eulerian_path(graph)
        if args.problem == "eulerian"
        else find_hamiltonian_path(graph)
    )
    validation = (
        validate_eulerian_path(graph, result)
        if args.problem == "eulerian"
        else validate_hamiltonian_path(graph, result)
    )
    output = {
        "problem": args.problem,
        "exists": result.exists,
        "path": list(result.path),
        "valid": validation["valid"],
        "edge_steps": result.edge_steps,
        "states_explored": result.states_explored,
        "elapsed_ns": None,
        "vertices": graph.vertex_count,
        "edges": graph.edge_count,
        "seed": graph.seed,
        "family": graph.family,
        "case": graph.case_name,
    }
    print(json.dumps(output, separators=(",", ":"), ensure_ascii=False))
    return 0 if validation["valid"] else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"erro: {error}", file=sys.stderr)
        raise SystemExit(2) from error
