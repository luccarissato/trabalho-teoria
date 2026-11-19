from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


EXPECTED_CHARTS = {
    "euler_ratio.svg",
    "euler_time_loglog.svg",
    "hamilton_states.svg",
    "hamilton_time.svg",
    "language_ratio.svg",
    "memory_increment.svg",
    "memory_peak.svg",
    "paired_algorithms.svg",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    for entry in manifest["graphs"]:
        graph_path = root / "datasets" / entry["file"]
        require(graph_path.is_file(), f"dataset ausente: {entry['file']}")
        require(digest(graph_path) == entry["sha256"], f"hash de dataset divergente: {entry['file']}")


def verify_analysis_manifest(root: Path) -> None:
    manifest_path = root / "results" / "analysis-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for group in ("inputs", "outputs"):
        for entry in manifest[group]:
            path = root / Path(entry["file"])
            require(path.is_file(), f"arquivo do manifesto de análise ausente: {entry['file']}")
            require(digest(path) == entry["sha256"], f"hash de análise divergente: {entry['file']}")


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

    require(len(pilot) == 10, "pilot_timing.csv não possui 10 linhas")
    require(sum(row["status"] == "completed" for row in pilot) == 8, "piloto não possui oito conclusões")
    require(sum(row["timeout"].lower() == "true" for row in pilot) == 2, "piloto não possui dois timeouts")

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
    require(len(viability) == 2, "viabilidade não possui duas linguagens")
    require(all(row["largest_completed_V"] == "14" and row["first_timeout_V"] == "16" for row in viability), "limite de viabilidade divergente")


def verify_charts_and_docs(root: Path) -> None:
    charts = root / "results" / "charts"
    names = {path.name for path in charts.glob("*.svg")}
    require(names == EXPECTED_CHARTS, f"conjunto de gráficos divergente: {sorted(names)}")
    for chart in charts.glob("*.svg"):
        ET.parse(chart)

    report_path = root / "relatorio.md"
    report = report_path.read_text(encoding="utf-8")
    headings = re.findall(r"^## ([1-7])\.", report, flags=re.MULTILINE)
    require(headings == list("1234567"), "relatório não segue os sete itens na ordem")
    require("Pendente - Etapa" not in report, "relatório ainda possui pendência de etapa")
    for chart in EXPECTED_CHARTS:
        require(chart in report, f"relatório não referencia {chart}")
    for relative in re.findall(r"(?:results|datasets)/[A-Za-z0-9_./+-]+", report):
        relative = relative.rstrip(".,;:)")
        require((root / relative).exists(), f"arquivo citado no relatório não existe: {relative}")
    require("## Ambiente de execução" in report, "ambiente ausente do relatório")
    require("## Contribuições dos integrantes" in report, "contribuições ausentes do relatório")
    require("## Declaração de uso de IA" in report, "declaração de IA ausente")

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
    require(len(final_manifest.get("figures", {})) == 8, "manifesto final não mapeia oito figuras")
    tree_hasher = hashlib.sha256()
    for entry in final_manifest.get("files", []):
        path = root / entry["file"]
        require(path.is_file(), f"arquivo-fonte do manifesto final ausente: {entry['file']}")
        require(digest(path) == entry["sha256"], f"hash final divergente: {entry['file']}")
        tree_hasher.update(entry["file"].encode("utf-8"))
        tree_hasher.update(b"\0")
        tree_hasher.update(entry["sha256"].encode("ascii"))
        tree_hasher.update(b"\n")
    require(tree_hasher.hexdigest() == final_manifest["source_tree_sha256"], "hash da árvore-fonte divergente")
    for figure in final_manifest["figures"].values():
        figure_path = root / figure["file"]
        require(figure_path.is_file() and digest(figure_path) == figure["sha256"], f"figura final divergente: {figure['file']}")
        for source in figure["sources"]:
            source_path = root / source["file"]
            require(source_path.is_file() and digest(source_path) == source["sha256"], f"fonte de figura divergente: {source['file']}")


def main() -> int:
    root = Path(parse_arguments().root).resolve()
    verify_dataset_manifest(root)
    verify_analysis_manifest(root)
    verify_raw_results(root)
    verify_charts_and_docs(root)
    verify_environment(root)
    print("PASS: 29 datasets e respectivos hashes.")
    print("PASS: 1690 observações de tempo e 1080 de memória auditadas.")
    print("PASS: 84 pontos de tempo, 36 de memória e 8 SVGs coerentes.")
    print("PASS: README, relatório, ambiente e manifestos verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
