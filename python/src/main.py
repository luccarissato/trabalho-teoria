from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from algorithms import Result, find_eulerian_path, find_hamiltonian_path  # noqa: E402
from graph import load_graph  # noqa: E402
from validate import validate_eulerian_path, validate_hamiltonian_path  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True, choices=("eulerian", "hamiltonian"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--warmups", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--hold-ms", type=int, default=0)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if args.warmups < 0:
        parser.error("--warmups deve ser maior ou igual a zero")
    if args.batch_size <= 0:
        parser.error("--batch-size deve ser positivo")
    if args.hold_ms < 0:
        parser.error("--hold-ms deve ser maior ou igual a zero")
    return args


def run_algorithm(problem: str, graph):
    return (
        find_eulerian_path(graph)
        if problem == "eulerian"
        else find_hamiltonian_path(graph)
    )


def main() -> int:
    args = parse_arguments()
    graph = load_graph(args.input)
    result = Result(False, ())
    elapsed_ns = None
    elapsed_ns_total = None
    validation = {"valid": True}
    if not args.baseline:
        for _ in range(args.warmups):
            run_algorithm(args.problem, graph)
        start_ns = time.perf_counter_ns()
        for _ in range(args.batch_size):
            result = run_algorithm(args.problem, graph)
        elapsed_ns_total = time.perf_counter_ns() - start_ns
        elapsed_ns = elapsed_ns_total // args.batch_size
        validation = (
            validate_eulerian_path(graph, result)
            if args.problem == "eulerian"
            else validate_hamiltonian_path(graph, result)
        )
    if args.hold_ms:
        time.sleep(args.hold_ms / 1000)
    output = {
        "problem": args.problem,
        "exists": result.exists,
        "path": list(result.path),
        "valid": validation["valid"],
        "baseline": args.baseline,
        "edge_steps": result.edge_steps,
        "states_explored": result.states_explored,
        "elapsed_ns": elapsed_ns,
        "elapsed_ns_total": elapsed_ns_total,
        "warmups": args.warmups,
        "batch_size": args.batch_size,
        "hold_ms": args.hold_ms,
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
