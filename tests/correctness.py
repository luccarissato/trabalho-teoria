from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from graph import Graph, load_graph  # noqa: E402
from validate import validate_eulerian_path, validate_hamiltonian_path  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--c", required=True)
    return parser.parse_args()


def run(command: list[str], expected_status: int = 0) -> str:
    completed = None
    for attempt in range(60):
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            break
        except OSError:
            if attempt == 59:
                raise
            time.sleep(0.5)
    assert completed is not None
    if completed.returncode != expected_status:
        raise AssertionError(
            f"{command[0]} retornou {completed.returncode}; esperado {expected_status}. "
            f"stderr={completed.stderr}"
        )
    return completed.stdout.strip()


def run_solver(
    kind: str,
    c_path: str,
    problem: str,
    input_path: Path,
    extra_arguments: tuple[str, ...] = (),
) -> dict:
    command = (
        [c_path, "--problem", problem, "--input", str(input_path)]
        if kind == "c"
        else [
            sys.executable,
            str(ROOT / "python" / "src" / "main.py"),
            "--problem",
            problem,
            "--input",
            str(input_path),
        ]
    )
    command.extend(extra_arguments)
    try:
        return json.loads(run(command))
    except json.JSONDecodeError as error:
        raise AssertionError(f"{kind} não produziu JSON válido") from error


def euler_oracle(graph: Graph) -> bool:
    if graph.vertex_count == 0 or graph.edge_count == 0:
        return True
    active = [vertex for vertex, neighbors in enumerate(graph.adjacency) if neighbors]
    visited = {active[0]}
    stack = [active[0]]
    while stack:
        vertex = stack.pop()
        for neighbor, _ in graph.adjacency[vertex]:
            if neighbor not in visited:
                visited.add(neighbor)
                stack.append(neighbor)
    odd = sum(len(graph.adjacency[vertex]) % 2 for vertex in active)
    return all(vertex in visited for vertex in active) and odd in (0, 2)


def hamiltonian_oracle(graph: Graph) -> bool:
    n = graph.vertex_count
    if n == 0:
        return False
    adjacent = [{neighbor for neighbor, _ in neighbors} for neighbors in graph.adjacency]
    used = [False] * n

    def enumerate_paths(last: int, length: int) -> bool:
        if length == n:
            return True
        for neighbor in range(n):
            if not used[neighbor] and neighbor in adjacent[last]:
                used[neighbor] = True
                if enumerate_paths(neighbor, length + 1):
                    return True
                used[neighbor] = False
        return False

    for start in range(n):
        used[:] = [False] * n
        used[start] = True
        if enumerate_paths(start, 1):
            return True
    return False


def directory_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.iterdir()):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    args = parse_arguments()
    datasets = ROOT / "datasets"
    temporary = ROOT / "tmp" / "stage1-tests"
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "a").mkdir(parents=True)
    (temporary / "b").mkdir(parents=True)
    assertions = 0

    def check(condition: bool, message: str) -> None:
        nonlocal assertions
        assertions += 1
        if not condition:
            raise AssertionError(message)

    try:
        generator = str(ROOT / "tools" / "generate.py")
        run([sys.executable, generator, "--output", str(temporary / "a"), "--seed", "20261117"])
        run([sys.executable, generator, "--output", str(temporary / "b"), "--seed", "20261117"])
        check(
            directory_digest(temporary / "a") == directory_digest(temporary / "b"),
            "gerador não é determinístico",
        )

        manifest = json.loads((datasets / "manifest.json").read_text(encoding="utf-8"))
        check(manifest["graph_count"] == len(manifest["graphs"]), "contagem incorreta no manifesto")
        check(len(manifest["graphs"]) >= 8, "conjunto de teste pequeno demais")

        for entry in manifest["graphs"]:
            input_path = datasets / entry["file"]
            check(
                hashlib.sha256(input_path.read_bytes()).hexdigest() == entry["sha256"],
                f"hash inválido: {entry['file']}",
            )
            graph = load_graph(input_path)
            expected = {
                "eulerian": euler_oracle(graph),
                "hamiltonian": hamiltonian_oracle(graph),
            }
            for problem in ("eulerian", "hamiltonian"):
                c_result = run_solver("c", args.c, problem, input_path)
                py_result = run_solver("python", args.c, problem, input_path)
                check(c_result["exists"] == expected[problem], f"C divergiu: {entry['file']}/{problem}")
                check(py_result["exists"] == expected[problem], f"Python divergiu: {entry['file']}/{problem}")
                check(c_result["exists"] == py_result["exists"], f"linguagens discordam: {entry['file']}/{problem}")
                check(c_result["path"] == py_result["path"], f"caminhos não determinísticos: {entry['file']}/{problem}")
                check(c_result["valid"] is True and py_result["valid"] is True, f"autovalidação falhou: {entry['file']}/{problem}")
                for language, output in (("C", c_result), ("Python", py_result)):
                    check(output["baseline"] is False, f"{language} marcou execução normal como baseline")
                    check(isinstance(output["elapsed_ns"], int) and output["elapsed_ns"] >= 0, f"tempo inválido em {language}")
                    check(
                        isinstance(output["elapsed_ns_total"], int)
                        and output["elapsed_ns_total"] >= output["elapsed_ns"],
                        f"tempo total inválido em {language}",
                    )
                    check(output["warmups"] == 0 and output["batch_size"] == 1, f"metadados de medição inválidos em {language}")
                c_view = SimpleNamespace(exists=c_result["exists"], path=tuple(c_result["path"]))
                py_view = SimpleNamespace(exists=py_result["exists"], path=tuple(py_result["path"]))
                validations = (
                    (validate_eulerian_path(graph, c_view), validate_eulerian_path(graph, py_view))
                    if problem == "eulerian"
                    else (validate_hamiltonian_path(graph, c_view), validate_hamiltonian_path(graph, py_view))
                )
                check(all(item["valid"] for item in validations), f"validador independente rejeitou: {entry['file']}/{problem}")
                check(c_result["states_explored"] == py_result["states_explored"], f"contadores divergem: {entry['file']}/{problem}")

        baseline_input = datasets / manifest["graphs"][0]["file"]
        for language in ("c", "python"):
            baseline = run_solver(
                language,
                args.c,
                "eulerian",
                baseline_input,
                ("--baseline",),
            )
            check(baseline["baseline"] is True, f"baseline não identificado em {language}")
            check(baseline["valid"] is True, f"baseline inválido em {language}")
            check(baseline["elapsed_ns"] is None, f"baseline mediu algoritmo em {language}")

        invalid = temporary / "invalid.graph"
        invalid.write_text(
            "TC_GRAPH 1\nV 3\nE 2\nSEED 1\nFAMILY invalid\nCASE duplicate\nEDGES\n0 1\n1 0\n",
            encoding="utf-8",
        )
        c_bad = subprocess.run(
            [args.c, "--problem", "eulerian", "--input", str(invalid)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        py_bad = subprocess.run(
            [sys.executable, str(ROOT / "python" / "src" / "main.py"), "--problem", "eulerian", "--input", str(invalid)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        check(c_bad.returncode != 0, "C aceitou entrada inválida")
        check(py_bad.returncode != 0, "Python aceitou entrada inválida")

        print(
            f"PASS: {len(manifest['graphs'])} grafos, 2 problemas, "
            f"2 linguagens, {assertions} asserções."
        )
        print("PASS: gerador determinístico, oráculos, validadores e entrada inválida.")
        return 0
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
