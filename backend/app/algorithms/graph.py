from __future__ import annotations

import networkx as nx

from app.config import settings


def pagerank(nodes: list[str], edges: list[tuple[str, str]], alpha: float = 0.85, iterations: int = 40) -> dict[str, float]:
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    count = graph.number_of_nodes()
    if count == 0:
        return {}
    rank = {node: 1 / count for node in graph.nodes}
    outward = {node: graph.out_degree(node) for node in graph.nodes}
    for _ in range(iterations):
        dangling = sum(rank[node] for node in graph.nodes if outward[node] == 0)
        updated = {}
        for node in graph.nodes:
            incoming = sum(
                rank[source] / outward[source]
                for source in graph.predecessors(node)
                if outward[source]
            )
            updated[node] = (1 - alpha) / count + alpha * (incoming + dangling / count)
        rank = updated
    return {str(node): float(score) for node, score in rank.items()}


def communities(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((source, target) for source, target in edges if source != target)
    if graph.number_of_nodes() == 0:
        return {}
    if graph.number_of_edges() == 0:
        return {node: index for index, node in enumerate(graph.nodes)}
    groups = nx.community.louvain_communities(graph, seed=settings.graph_seed)
    mapping: dict[str, int] = {}
    for index, group in enumerate(groups):
        for node in group:
            mapping[str(node)] = index
    return mapping


def shortest_path(
    nodes: list[str], edges: list[tuple[str, str]], source: str, target: str
) -> list[str] | None:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((left, right) for left, right in edges if left != right)
    if source not in graph or target not in graph:
        return None
    try:
        return [str(node) for node in nx.shortest_path(graph, source, target)]
    except nx.NetworkXNoPath:
        return None
