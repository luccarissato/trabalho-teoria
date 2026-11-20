from __future__ import annotations

import argparse
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from analyze import completed_timing, is_true, summarize_pilot
from create_final_manifest import FIGURE_SOURCES
from file_hash import canonical_sha256
from generate_experiments import PILOT_SIZES

EXPECTED_CHARTS = set(FIGURE_SOURCES)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--reproduced-analysis", type=Path)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def check_groups(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
    expected_groups: int,
    expected_per_group: int,
    label: str,
) -> None:
    counts = Counter(tuple(row[field] for field in fields) for row in rows)
    require(len(counts) == expected_groups, f"{label}: {len(counts)} grupos, esperado {expected_groups}")
    wrong = {key: value for key, value in counts.items() if value != expected_per_group}
    require(not wrong, f"{label}: repetições divergentes: {wrong}")


def verify_dataset_manifest(root: Path) -> None:
    manifest_path = root / "datasets" / "experimental-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["graph_count"] == 29, "manifesto experimental não possui 29 grafos")
    require(len(manifest["graphs"]) == 29, "lista experimental não possui 29 grafos")
    require(
        canonical_sha256(root / manifest["generator"]) == manifest["generator_sha256"],
        "hash do gerador experimental divergente",
    )
    for entry in manifest["graphs"]:
        graph_path = root / "datasets" / entry["file"]
        require(graph_path.is_file(), f"dataset ausente: {entry['file']}")
        require(canonical_sha256(graph_path) == entry["sha256"], f"hash de dataset divergente: {entry['file']}")


def verify_analysis_manifest(root: Path, reproduced: Path | None) -> None:
    manifest_path = root / "results" / "analysis-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_outputs = {f"results/charts/{name}" for name in EXPECTED_CHARTS} | {
        f"results/summary/{name}" for name in ("timing.csv", "memory.csv", "viability.csv", "summary.txt")
    }
    require({entry["file"] for entry in manifest["outputs"]} == expected_outputs, "artefatos de análise divergentes")
    for group in ("inputs", "outputs"):
        for entry in manifest[group]:
            path = root / Path(entry["file"])
            require(path.is_file(), f"arquivo do manifesto de análise ausente: {entry['file']}")
            require(canonical_sha256(path) == entry["sha256"], f"hash de análise divergente: {entry['file']}")
            if group == "outputs" and reproduced is not None:
                regenerated = reproduced / path.relative_to(root / "results")
                require(regenerated.is_file(), f"artefato regenerado ausente: {regenerated}")
                require(
                    canonical_sha256(regenerated) == entry["sha256"],
                    f"artefato regenerado diverge: {entry['file']}",
                )


def verify_raw_results(root: Path) -> None:
    raw = root / "results" / "raw"
    paired_time = read_csv(raw / "paired_timing.csv")
    scale_time = read_csv(raw / "eulerian_scale_timing.csv")
    pilot = read_csv(raw / "pilot_timing.csv")
    paired_memory = read_csv(raw / "paired_memory.csv")
    scale_memory = read_csv(raw / "eulerian_scale_memory.csv")

    require(len(paired_time) == 1440, "paired_timing.csv não possui 1440 linhas")
    require(all(row["status"] == "completed" and row["valid"].lower() == "true" for row in paired_time), "tempo pareado inválido")
    check_groups(paired_time, ("language", "problem", "dataset"), 72, 20, "tempo pareado")

    require(len(scale_time) == 240, "eulerian_scale_timing.csv não possui 240 linhas")
    require(all(row["status"] == "completed" and row["valid"].lower() == "true" for row in scale_time), "tempo de escala inválido")
    check_groups(scale_time, ("language", "problem", "dataset"), 12, 20, "tempo de escala")

    expected_pilot = Counter((language, str(size)) for language in ("c", "python") for size in PILOT_SIZES)
    require(Counter((row["language"], row["V"]) for row in pilot) == expected_pilot, "pontos do piloto divergentes")
    for row in pilot:
        censored = row["status"] == "timeout" and is_true(row["timeout"]) and not row["elapsed_ns"]
        require(completed_timing(row) or censored, "observação inválida no piloto")

    require(len(paired_memory) == 720, "paired_memory.csv não possui 720 linhas")
    require(all(row["status"] == "completed" and int(row["peak_working_set_bytes"]) > 0 for row in paired_memory), "memória pareada inválida")
    check_groups(paired_memory, ("language", "problem", "dataset", "mode"), 48, 15, "memória pareada")

    require(len(scale_memory) == 360, "eulerian_scale_memory.csv não possui 360 linhas")
    require(all(row["status"] == "completed" and int(row["peak_working_set_bytes"]) > 0 for row in scale_memory), "memória de escala inválida")
    check_groups(scale_memory, ("language", "problem", "dataset", "mode"), 24, 15, "memória de escala")

    timing_summary = read_csv(root / "results" / "summary" / "timing.csv")
    memory_summary = read_csv(root / "results" / "summary" / "memory.csv")
    viability = read_csv(root / "results" / "summary" / "viability.csv")
    require(len(timing_summary) == 84, "resumo de tempo não possui 84 pontos")
    require(len(memory_summary) == 36, "resumo de memória não possui 36 pontos")
    expected_viability = [{key: str(value) for key, value in row.items()} for row in summarize_pilot(pilot)]
    require(viability == expected_viability, "resumo de viabilidade diverge do piloto")


def verify_charts_and_readme(root: Path) -> None:
    charts = root / "results" / "charts"
    names = {path.name for path in charts.glob("*.svg")}
    require(names == EXPECTED_CHARTS, f"conjunto de gráficos divergente: {sorted(names)}")
    for chart in charts.glob("*.svg"):
        ET.parse(chart)

    readme = (root / "README.md").read_text(encoding="utf-8")
    for command in ("run-all.ps1 -Quick", "run-all.ps1 -Full"):
        require(command in readme, f"README não documenta {command}")
    for topic in ("Pré-requisitos", "Solução de problemas", "Formato dos grafos", "Significado dos CSVs"):
        require(topic in readme, f"README não contém {topic}")


def verify_environment(root: Path) -> None:
    environment = json.loads((root / "results" / "manifest.json").read_text(encoding="utf-8"))
    for field in ("cpu", "ram_bytes", "operating_system", "gcc", "compiler_flags", "python", "python_jit", "power_mode"):
        require(environment.get(field) not in (None, ""), f"campo ambiental ausente: {field}")
    final_manifest = json.loads((root / "results" / "final-manifest.json").read_text(encoding="utf-8"))
    require(final_manifest.get("source_tree_sha256"), "hash da árvore ausente no manifesto final")
    require(set(final_manifest.get("figures", {})) == EXPECTED_CHARTS, "figuras do manifesto final divergentes")
    tree_hasher = hashlib.sha256()
    for entry in final_manifest.get("files", []):
        path = root / entry["file"]
        require(path.is_file(), f"arquivo-fonte do manifesto final ausente: {entry['file']}")
        require(canonical_sha256(path) == entry["sha256"], f"hash final divergente: {entry['file']}")
        tree_hasher.update(entry["file"].encode("utf-8"))
        tree_hasher.update(b"\0")
        tree_hasher.update(entry["sha256"].encode("ascii"))
        tree_hasher.update(b"\n")
    require(tree_hasher.hexdigest() == final_manifest["source_tree_sha256"], "hash da árvore-fonte divergente")
    for figure in final_manifest["figures"].values():
        figure_path = root / figure["file"]
        require(figure_path.is_file() and canonical_sha256(figure_path) == figure["sha256"], f"figura final divergente: {figure['file']}")
        for source in figure["sources"]:
            source_path = root / source["file"]
            require(source_path.is_file() and canonical_sha256(source_path) == source["sha256"], f"fonte de figura divergente: {source['file']}")


def main() -> int:
    args = parse_arguments()
    root = Path(args.root).resolve()
    verify_dataset_manifest(root)
    verify_analysis_manifest(root, args.reproduced_analysis)
    verify_raw_results(root)
    verify_charts_and_readme(root)
    verify_environment(root)
    print("PASS: 29 datasets e respectivos hashes.")
    print("PASS: 1690 observações de tempo e 1080 de memória auditadas.")
    print(f"PASS: 84 pontos de tempo, 36 de memória e {len(EXPECTED_CHARTS)} SVGs coerentes.")
    print("PASS: README, ambiente e manifestos verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
