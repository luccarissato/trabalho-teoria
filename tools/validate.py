from __future__ import annotations

from typing import Protocol


class GraphLike(Protocol):
    vertex_count: int
    edge_count: int
    edges: tuple[tuple[int, int], ...]


class ResultLike(Protocol):
    exists: bool
    path: tuple[int, ...]


def _edge_key(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u < v else (v, u)


def validate_eulerian_path(graph: GraphLike, result: ResultLike) -> dict[str, object]:
    if not result.exists:
        return {"valid": len(result.path) == 0, "reason": "negative-result"}
    if graph.vertex_count == 0:
        return {"valid": len(result.path) == 0, "reason": "empty-graph"}
    if len(result.path) != graph.edge_count + 1:
        return {"valid": False, "reason": "wrong-path-length"}

    remaining = {edge: 1 for edge in graph.edges}
    for u, v in zip(result.path, result.path[1:]):
        edge = _edge_key(u, v)
        if remaining.get(edge) != 1:
            return {"valid": False, "reason": "edge-reused-or-missing"}
        remaining[edge] = 0
    return {
        "valid": all(count == 0 for count in remaining.values()),
        "reason": "checked-all-edges",
    }


def validate_hamiltonian_path(graph: GraphLike, result: ResultLike) -> dict[str, object]:
    if not result.exists:
        return {"valid": len(result.path) == 0, "reason": "negative-result"}
    if len(result.path) != graph.vertex_count:
        return {"valid": False, "reason": "wrong-path-length"}
    vertices = set(result.path)
    if len(vertices) != graph.vertex_count or any(
        vertex < 0 or vertex >= graph.vertex_count for vertex in result.path
    ):
        return {"valid": False, "reason": "vertices-not-used-exactly-once"}
    edges = set(graph.edges)
    if any(_edge_key(u, v) not in edges for u, v in zip(result.path, result.path[1:])):
        return {"valid": False, "reason": "non-adjacent-vertices"}
    return {"valid": True, "reason": "checked-all-vertices"}
