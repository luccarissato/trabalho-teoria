from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Graph:
    vertex_count: int
    edge_count: int
    seed: int
    family: str
    case_name: str
    edges: tuple[tuple[int, int], ...]
    adjacency: tuple[tuple[tuple[int, int], ...], ...]


def parse_graph(text: str, source: str = "<memory>") -> Graph:
    lines = text.replace("\r", "").split("\n")
    if not lines or lines.pop(0).strip() != "TC_GRAPH 1":
        raise ValueError(f"{source}: cabeçalho esperado: TC_GRAPH 1")

    metadata: dict[str, str] = {}
    found_edges = False
    while lines:
        line = lines.pop(0).strip()
        if not line or line.startswith("#"):
            continue
        if line == "EDGES":
            found_edges = True
            break
        key, separator, value = line.partition(" ")
        if not separator or not value.strip():
            raise ValueError(f"{source}: metadado inválido: {line}")
        if key in metadata:
            raise ValueError(f"{source}: metadado duplicado: {key}")
        metadata[key] = value.strip()

    if not found_edges:
        raise ValueError(f"{source}: marcador EDGES ausente")
    for key in ("V", "E", "SEED", "FAMILY", "CASE"):
        if key not in metadata:
            raise ValueError(f"{source}: metadado ausente: {key}")

    try:
        vertex_count = int(metadata["V"])
        declared_edges = int(metadata["E"])
        seed = int(metadata["SEED"])
    except ValueError as error:
        raise ValueError(f"{source}: V, E e SEED devem ser inteiros") from error
    if vertex_count < 0 or declared_edges < 0 or seed < 0:
        raise ValueError(f"{source}: V, E e SEED devem ser não negativos")

    edges: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for raw in lines:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        parts = value.split()
        if len(parts) != 2 or not all(part.isdecimal() for part in parts):
            raise ValueError(f"{source}: aresta inválida: {value}")
        u, v = map(int, parts)
        if u >= vertex_count or v >= vertex_count:
            raise ValueError(f"{source}: vértice fora do intervalo: {value}")
        if u == v:
            raise ValueError(f"{source}: laços não são permitidos: {value}")
        edge = (u, v) if u < v else (v, u)
        if edge in seen:
            raise ValueError(f"{source}: aresta duplicada: {value}")
        seen.add(edge)
        edges.append(edge)

    if len(edges) != declared_edges:
        raise ValueError(
            f"{source}: E={declared_edges}, mas foram lidas {len(edges)} arestas"
        )

    edges.sort()
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(vertex_count)]
    for edge_id, (u, v) in enumerate(edges):
        adjacency[u].append((v, edge_id))
        adjacency[v].append((u, edge_id))
    for neighbors in adjacency:
        neighbors.sort()

    return Graph(
        vertex_count=vertex_count,
        edge_count=len(edges),
        seed=seed,
        family=metadata["FAMILY"],
        case_name=metadata["CASE"],
        edges=tuple(edges),
        adjacency=tuple(tuple(neighbors) for neighbors in adjacency),
    )


def load_graph(path: str | Path) -> Graph:
    source = Path(path)
    return parse_graph(source.read_text(encoding="utf-8"), str(source))
