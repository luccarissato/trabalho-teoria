from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


TIMING_REQUIRED = {
    "language",
    "problem",
    "dataset",
    "family",
    "case",
    "V",
    "E",
    "repetition",
    "elapsed_ns",
    "states_explored",
    "status",
    "timeout",
    "valid",
}
MEMORY_REQUIRED = {
    "language",
    "problem",
    "dataset",
    "family",
    "case",
    "V",
    "E",
    "mode",
    "repetition",
    "peak_working_set_bytes",
    "status",
    "timeout",
}
COLORS = ("#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#4f46e5", "#be123c")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", nargs="+", required=True)
    parser.add_argument("--memory", nargs="+", required=True)
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--datasets-manifest", required=True)
    parser.add_argument("--output", default="results")
    parser.add_argument("--expected-timing-repetitions", type=int, default=20)
    parser.add_argument("--expected-memory-repetitions", type=int, default=15)
    return parser.parse_args()


def read_rows(paths: Iterable[str], required: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or ())
            missing = required - fields
            if missing:
                raise ValueError(f"{path}: colunas ausentes: {sorted(missing)}")
            for row in reader:
                row["_source"] = str(path.as_posix())
                rows.append(row)
    return rows


def is_true(value: str) -> bool:
    return value.strip().lower() == "true"


def integer(row: dict[str, str], field: str) -> int:
    return int(row[field])


def number(row: dict[str, str], field: str) -> float:
    return float(row[field])


def sample_stddev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def log_log_slope(points: list[tuple[float, float]]) -> float:
    xs = [math.log10(x) for x, _ in points]
    ys = [math.log10(y) for _, y in points]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sum(
        (x - x_mean) ** 2 for x in xs
    )


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def timing_summary(
    rows: list[dict[str, str]], expected_repetitions: int
) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["language"],
            row["problem"],
            row["dataset"],
            row["family"],
            row["case"],
            integer(row, "V"),
            integer(row, "E"),
        )
        groups[key].append(row)

    summary: list[dict[str, object]] = []
    for key, point_rows in sorted(groups.items()):
        completed = [
            row
            for row in point_rows
            if row["status"] == "completed" and is_true(row["valid"]) and not is_true(row["timeout"])
        ]
        timeouts = sum(is_true(row["timeout"]) for row in point_rows)
        invalid = len(point_rows) - len(completed) - timeouts
        if not timeouts and len(completed) != expected_repetitions:
            raise ValueError(
                f"{key[0]}/{key[1]}/{key[2]}: esperado {expected_repetitions} "
                f"repetições válidas; obtidas {len(completed)}"
            )
        elapsed = [number(row, "elapsed_ns") for row in completed]
        states = [number(row, "states_explored") for row in completed]
        summary.append(
            {
                "language": key[0],
                "problem": key[1],
                "dataset": key[2],
                "family": key[3],
                "case": key[4],
                "V": key[5],
                "E": key[6],
                "size_V_plus_E": key[5] + key[6],
                "valid_count": len(completed),
                "timeout_count": timeouts,
                "invalid_count": invalid,
                "elapsed_mean_ns": statistics.fmean(elapsed) if elapsed else "",
                "elapsed_median_ns": statistics.median(elapsed) if elapsed else "",
                "elapsed_stddev_ns": sample_stddev(elapsed) if elapsed else "",
                "elapsed_min_ns": min(elapsed) if elapsed else "",
                "elapsed_max_ns": max(elapsed) if elapsed else "",
                "states_mean": statistics.fmean(states) if states else "",
            }
        )
    return summary


def memory_summary(
    rows: list[dict[str, str]], expected_repetitions: int
) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["language"],
            row["problem"],
            row["dataset"],
            row["family"],
            row["case"],
            integer(row, "V"),
            integer(row, "E"),
        )
        groups[key].append(row)

    summary: list[dict[str, object]] = []
    for key, point_rows in sorted(groups.items()):
        by_mode: dict[str, list[dict[str, str]]] = {}
        for mode in ("baseline", "algorithm"):
            valid_rows = [
                row
                for row in point_rows
                if row["mode"] == mode
                and row["status"] == "completed"
                and not is_true(row["timeout"])
                and row["peak_working_set_bytes"]
            ]
            if len(valid_rows) != expected_repetitions:
                raise ValueError(
                    f"{key[0]}/{key[1]}/{key[2]}/{mode}: esperado "
                    f"{expected_repetitions}; obtidas {len(valid_rows)}"
                )
            by_mode[mode] = valid_rows

        baseline = [number(row, "peak_working_set_bytes") for row in by_mode["baseline"]]
        algorithm = [number(row, "peak_working_set_bytes") for row in by_mode["algorithm"]]
        baseline_median = statistics.median(baseline)
        algorithm_median = statistics.median(algorithm)
        summary.append(
            {
                "language": key[0],
                "problem": key[1],
                "dataset": key[2],
                "family": key[3],
                "case": key[4],
                "V": key[5],
                "E": key[6],
                "baseline_count": len(baseline),
                "algorithm_count": len(algorithm),
                "baseline_mean_bytes": statistics.fmean(baseline),
                "baseline_median_bytes": baseline_median,
                "baseline_stddev_bytes": sample_stddev(baseline),
                "algorithm_mean_bytes": statistics.fmean(algorithm),
                "algorithm_median_bytes": algorithm_median,
                "algorithm_stddev_bytes": sample_stddev(algorithm),
                "algorithm_min_bytes": min(algorithm),
                "algorithm_max_bytes": max(algorithm),
                "approximate_increment_bytes": max(0.0, algorithm_median - baseline_median),
            }
        )
    return summary


def svg_chart(
    path: Path,
    title: str,
    x_label: str,
    y_label: str,
    series: list[tuple[str, list[tuple[float, float]]]],
    *,
    x_log: bool = False,
    y_log: bool = False,
) -> None:
    prepared: list[tuple[str, list[tuple[float, float]]]] = []
    for label, points in series:
        clean = sorted(
            (x, y)
            for x, y in points
            if (x > 0 if x_log else x >= 0) and (y > 0 if y_log else y >= 0)
        )
        if clean:
            prepared.append((label, clean))
    if not prepared:
        raise ValueError(f"sem dados positivos para o gráfico {path.name}")

    transform_x = math.log10 if x_log else lambda value: value
    transform_y = math.log10 if y_log else lambda value: value
    transformed = [
        (label, [(transform_x(x), transform_y(y), x, y) for x, y in points])
        for label, points in prepared
    ]
    all_x = [point[0] for _, points in transformed for point in points]
    all_y = [point[1] for _, points in transformed for point in points]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    if x_min == x_max:
        x_min, x_max = x_min - 0.5, x_max + 0.5
    if y_min == y_max:
        y_min, y_max = y_min - 0.5, y_max + 0.5
    x_pad = (x_max - x_min) * 0.06
    y_pad = (y_max - y_min) * 0.10
    x_min, x_max = x_min - x_pad, x_max + x_pad
    y_min, y_max = y_min - y_pad, y_max + y_pad
    if not y_log and min(y for _, points in prepared for _, y in points) >= 0:
        y_min = max(0.0, y_min)

    width, height = 960, 600
    left, right, top, bottom = 105, 35, 70, 85
    plot_width = width - left - right
    plot_height = height - top - bottom

    def sx(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    def tick_label(value: float, logarithmic: bool) -> str:
        original = 10**value if logarithmic else value
        if abs(original) >= 1_000_000:
            return f"{original:.2g}"
        if abs(original) >= 1000:
            return f"{original:,.0f}".replace(",", " ")
        if abs(original) >= 10:
            return f"{original:.0f}"
        return f"{original:.2g}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="34" text-anchor="middle" font-family="Segoe UI,Arial" font-size="22" font-weight="600" fill="#111827">{html.escape(title)}</text>',
    ]
    for index in range(6):
        fraction = index / 5
        x_value = x_min + fraction * (x_max - x_min)
        y_value = y_min + fraction * (y_max - y_min)
        x_pixel = sx(x_value)
        y_pixel = sy(y_value)
        parts.extend(
            [
                f'<line x1="{x_pixel:.2f}" y1="{top}" x2="{x_pixel:.2f}" y2="{top+plot_height}" stroke="#e5e7eb"/>',
                f'<text x="{x_pixel:.2f}" y="{top+plot_height+24}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="12" fill="#4b5563">{tick_label(x_value, x_log)}</text>',
                f'<line x1="{left}" y1="{y_pixel:.2f}" x2="{left+plot_width}" y2="{y_pixel:.2f}" stroke="#e5e7eb"/>',
                f'<text x="{left-12}" y="{y_pixel+4:.2f}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12" fill="#4b5563">{tick_label(y_value, y_log)}</text>',
            ]
        )
    parts.extend(
        [
            f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#111827" stroke-width="1.5"/>',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#111827" stroke-width="1.5"/>',
            f'<text x="{left+plot_width/2}" y="{height-24}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="15" fill="#111827">{html.escape(x_label)}</text>',
            f'<text x="25" y="{top+plot_height/2}" text-anchor="middle" transform="rotate(-90 25 {top+plot_height/2})" font-family="Segoe UI,Arial" font-size="15" fill="#111827">{html.escape(y_label)}</text>',
        ]
    )
    for index, (label, points) in enumerate(transformed):
        color = COLORS[index % len(COLORS)]
        coordinates = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _, _ in points)
        parts.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for x, y, original_x, original_y in points:
            parts.append(
                f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="4" fill="{color}"><title>{html.escape(label)}: x={original_x:g}, y={original_y:g}</title></circle>'
            )
        legend_x = left + 12 + (index % 3) * 275
        legend_y = top + 20 + (index // 3) * 22
        parts.extend(
            [
                f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x+24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{legend_x+31}" y="{legend_y+4}" font-family="Segoe UI,Arial" font-size="12" fill="#111827">{html.escape(label)}</text>',
            ]
        )
    parts.append("</svg>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8", newline="\n")


def series_by(
    rows: list[dict[str, object]],
    selector,
    labeler,
    x_field: str,
    y_field: str,
) -> list[tuple[str, list[tuple[float, float]]]]:
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        if selector(row) and row[y_field] != "":
            groups[labeler(row)].append((float(row[x_field]), float(row[y_field])))
    return sorted(groups.items())


def write_markdown_summary(
    path: Path,
    timing: list[dict[str, object]],
    memory: list[dict[str, object]],
    viability: list[dict[str, object]],
) -> None:
    lines = [
        "# Resumo experimental",
        "",
        "Linhas inválidas e timeouts não são convertidos em tempos. Nenhum outlier válido foi removido.",
        "",
        "## Viabilidade do backtracking no piloto",
        "",
        "| Linguagem | Família | Maior V concluído | Primeiro V censurado |",
        "|---|---|---:|---:|",
    ]
    for row in viability:
        lines.append(
            f"| {row['language']} | {row['family']} | {row['largest_completed_V']} | {row['first_timeout_V']} |"
        )
    slopes: dict[str, float] = {}
    for language in ("c", "python"):
        points = [
            (float(row["size_V_plus_E"]), float(row["elapsed_mean_ns"]))
            for row in timing
            if row["language"] == language
            and row["problem"] == "eulerian"
            and row["family"] == "constructed_cycle_scale"
        ]
        slopes[language] = log_log_slope(points)
    lines.extend(
        [
            "",
            "## Hierholzer - suíte de escala",
            "",
            f"Inclinação log-log: C = {slopes['c']:.4f}; Python = {slopes['python']:.4f}. Um valor próximo de 1 é compatível com crescimento linear.",
            "",
            "| Linguagem | V | E | Média (ns) | Desvio-padrão (ns) | T/(V+E) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in timing:
        if row["family"] == "constructed_cycle_scale" and row["problem"] == "eulerian":
            ratio = float(row["elapsed_mean_ns"]) / float(row["size_V_plus_E"])
            lines.append(
                f"| {row['language']} | {row['V']} | {row['E']} | {float(row['elapsed_mean_ns']):.2f} | "
                f"{float(row['elapsed_stddev_ns']):.2f} | {ratio:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Memória - extremos medidos",
            "",
            "| Linguagem | Problema | Família | V | Pico médio (bytes) | Incremento aproximado (bytes) |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    selected: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in memory:
        key = (str(row["language"]), str(row["problem"]), str(row["family"]))
        if key not in selected or int(row["V"]) > int(selected[key]["V"]):
            selected[key] = row
    for row in selected.values():
        lines.append(
            f"| {row['language']} | {row['problem']} | {row['family']} | {row['V']} | "
            f"{float(row['algorithm_mean_bytes']):.2f} | {float(row['approximate_increment_bytes']):.2f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = parse_arguments()
    output = Path(args.output)
    summary_dir = output / "summary"
    charts_dir = output / "charts"
    summary_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    timing_rows = read_rows(args.timing, TIMING_REQUIRED)
    memory_rows = read_rows(args.memory, MEMORY_REQUIRED)
    pilot_rows = read_rows([args.pilot], TIMING_REQUIRED)
    timing = timing_summary(timing_rows, args.expected_timing_repetitions)
    memory = memory_summary(memory_rows, args.expected_memory_repetitions)

    timing_fields = list(timing[0])
    memory_fields = list(memory[0])
    write_csv(summary_dir / "timing.csv", timing, timing_fields)
    write_csv(summary_dir / "memory.csv", memory, memory_fields)

    pilot_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in pilot_rows:
        pilot_groups[(row["language"], row["family"])].append(row)
    viability: list[dict[str, object]] = []
    for (language, family), rows in sorted(pilot_groups.items()):
        completed = [integer(row, "V") for row in rows if row["status"] == "completed" and is_true(row["valid"])]
        timed_out = [integer(row, "V") for row in rows if is_true(row["timeout"])]
        viability.append(
            {
                "language": language,
                "family": family,
                "largest_completed_V": max(completed) if completed else "",
                "first_timeout_V": min(timed_out) if timed_out else "",
            }
        )
    write_csv(
        summary_dir / "viability.csv",
        viability,
        ["language", "family", "largest_completed_V", "first_timeout_V"],
    )

    euler_scale = series_by(
        timing,
        lambda row: row["problem"] == "eulerian" and row["family"] == "constructed_cycle_scale",
        lambda row: str(row["language"]),
        "size_V_plus_E",
        "elapsed_mean_ns",
    )
    svg_chart(charts_dir / "euler_time_loglog.svg", "Hierholzer: tempo por tamanho", "V + E (log)", "Tempo médio em ns (log)", euler_scale, x_log=True, y_log=True)
    euler_ratio = [
        (
            label,
            [
                (x, y / x)
                for x, y in points
            ],
        )
        for label, points in euler_scale
    ]
    svg_chart(charts_dir / "euler_ratio.svg", "Hierholzer: T/(V+E)", "V + E", "ns por unidade", euler_ratio, x_log=True)

    hamilton_time = series_by(
        timing,
        lambda row: row["problem"] == "hamiltonian" and row["family"] != "constructed_cycle_scale",
        lambda row: f"{row['language']} / {row['family']}",
        "V",
        "elapsed_mean_ns",
    )
    svg_chart(charts_dir / "hamilton_time.svg", "Backtracking hamiltoniano por família", "V", "Tempo médio em ns (log)", hamilton_time, y_log=True)
    hamilton_states = series_by(
        timing,
        lambda row: row["problem"] == "hamiltonian" and row["language"] == "c" and row["family"] != "constructed_cycle_scale",
        lambda row: str(row["family"]),
        "V",
        "states_mean",
    )
    svg_chart(charts_dir / "hamilton_states.svg", "Estados explorados pelo backtracking", "V", "Estados (log)", hamilton_states, y_log=True)
    paired_algorithms = series_by(
        timing,
        lambda row: row["family"] == "constructed_path",
        lambda row: f"{row['language']} / {row['problem']}",
        "V",
        "elapsed_mean_ns",
    )
    svg_chart(charts_dir / "paired_algorithms.svg", "Euler x Hamilton em entradas pareadas", "V", "Tempo médio em ns (log)", paired_algorithms, y_log=True)

    ratios: dict[str, list[tuple[float, float]]] = defaultdict(list)
    timing_index = {(row["language"], row["problem"], row["dataset"]): row for row in timing}
    for row in timing:
        if row["language"] != "c" or row["family"] != "constructed_path":
            continue
        python_row = timing_index.get(("python", row["problem"], row["dataset"]))
        if python_row:
            ratios[str(row["problem"])].append(
                (float(row["V"]), float(row["elapsed_mean_ns"]) / float(python_row["elapsed_mean_ns"]))
            )
    svg_chart(charts_dir / "language_ratio.svg", "Razão de tempo C/Python", "V", "C/Python", sorted(ratios.items()))

    memory_peak = series_by(
        memory,
        lambda row: row["family"] in {"constructed_path", "constructed_cycle_scale"},
        lambda row: f"{row['language']} / {row['problem']} / {row['family']}",
        "V",
        "algorithm_mean_bytes",
    )
    svg_chart(charts_dir / "memory_peak.svg", "Pico absoluto de memória", "V", "Bytes (log)", memory_peak, x_log=True, y_log=True)
    memory_increment = series_by(
        memory,
        lambda row: row["family"] in {"constructed_path", "constructed_cycle_scale"},
        lambda row: f"{row['language']} / {row['problem']} / {row['family']}",
        "V",
        "approximate_increment_bytes",
    )
    svg_chart(charts_dir / "memory_increment.svg", "Incremento aproximado de memória", "V", "Bytes", memory_increment, x_log=True)

    write_markdown_summary(summary_dir / "summary.txt", timing, memory, viability)

    source_paths = [Path(path) for path in [*args.timing, *args.memory, args.pilot, args.datasets_manifest]]
    generated_paths = sorted([*summary_dir.glob("*"), *charts_dir.glob("*.svg")])
    manifest = {
        "schema_version": 1,
        "exclusion_rule": "Tempo: status=completed, valid=true e timeout=false. Memória: status=completed, timeout=false e pico disponível. Nenhum outlier válido é removido.",
        "inputs": [{"file": path.as_posix(), "sha256": sha256(path)} for path in source_paths],
        "outputs": [{"file": path.as_posix(), "sha256": sha256(path)} for path in generated_paths],
    }
    (output / "analysis-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Análise concluída: {len(timing)} pontos de tempo e {len(memory)} pontos de memória.")
    print(f"Tabelas: {summary_dir}")
    print(f"Gráficos: {charts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
