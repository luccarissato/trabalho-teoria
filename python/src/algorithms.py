from __future__ import annotations

from dataclasses import dataclass

from graph import Graph


@dataclass(frozen=True)
class Result:
    exists: bool
    path: tuple[int, ...]
    edge_steps: int = 0
    states_explored: int = 0


def find_eulerian_path(graph: Graph) -> Result:
    n = graph.vertex_count
    m = graph.edge_count
    if n == 0:
        return Result(True, ())
    if m == 0:
        return Result(True, (0,))

    visited = [False] * n
    active_components = 0
    for root in range(n):
        if not graph.adjacency[root] or visited[root]:
            continue
        active_components += 1
        stack = [root]
        visited[root] = True
        while stack:
            vertex = stack.pop()
            for neighbor, _ in graph.adjacency[vertex]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)

    odd = [vertex for vertex in range(n) if len(graph.adjacency[vertex]) % 2 == 1]
    if active_components != 1 or len(odd) not in (0, 2):
        return Result(False, ())

    start = odd[0] if odd else next(
        vertex for vertex, neighbors in enumerate(graph.adjacency) if neighbors
    )
    used = [False] * m
    cursor = [0] * n
    stack = [start]
    reversed_path: list[int] = []
    edge_steps = 0

    while stack:
        vertex = stack[-1]
        neighbors = graph.adjacency[vertex]
        while cursor[vertex] < len(neighbors) and used[neighbors[cursor[vertex]][1]]:
            cursor[vertex] += 1
        if cursor[vertex] == len(neighbors):
            reversed_path.append(stack.pop())
            continue
        neighbor, edge_id = neighbors[cursor[vertex]]
        cursor[vertex] += 1
        if not used[edge_id]:
            used[edge_id] = True
            edge_steps += 1
            stack.append(neighbor)

    path = tuple(reversed(reversed_path))
    exists = edge_steps == m and len(path) == m + 1
    return Result(exists, path if exists else (), edge_steps=edge_steps)


def find_hamiltonian_path(graph: Graph) -> Result:
    n = graph.vertex_count
    if n == 0:
        return Result(False, ())

    states_explored = 0
    visited = [False] * n
    path: list[int] = []

    def search(vertex: int) -> bool:
        nonlocal states_explored
        states_explored += 1
        if len(path) == n:
            return True
        for neighbor, _ in graph.adjacency[vertex]:
            if visited[neighbor]:
                continue
            visited[neighbor] = True
            path.append(neighbor)
            if search(neighbor):
                return True
            path.pop()
            visited[neighbor] = False
        return False

    for start in range(n):
        path.clear()
        visited[:] = [False] * n
        path.append(start)
        visited[start] = True
        if search(start):
            return Result(True, tuple(path), states_explored=states_explored)
    return Result(False, (), states_explored=states_explored)
