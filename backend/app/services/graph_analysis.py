import networkx as nx


def build_graph(nodes: list[str], edges: list[tuple[str, str]]) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def connected_components(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    graph = build_graph(nodes, edges)
    return [sorted(list(component)) for component in nx.connected_components(graph)]


def communities(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    graph = build_graph(nodes, edges)
    if graph.number_of_edges() == 0:
        return {node: index for index, node in enumerate(sorted(nodes))}
    found = nx.community.greedy_modularity_communities(graph)
    mapping: dict[str, int] = {}
    for index, community in enumerate(found):
        for node in community:
            mapping[str(node)] = index
    return mapping


def shortest_path(nodes: list[str], edges: list[tuple[str, str]], source: str, target: str) -> list[str]:
    graph = build_graph(nodes, edges)
    if source not in graph or target not in graph:
        return []
    try:
        return [str(node) for node in nx.shortest_path(graph, source, target)]
    except nx.NetworkXNoPath:
        return []


def rank_candidates(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (-float(row.get("heuristic_score", 0)), row.get("entity_id", "")))


def resolve_duplicates(entities: list[dict]) -> list[dict]:
    seen: dict[tuple[str, str], dict] = {}
    for entity in entities:
        key = (entity["entity_type"], entity["normalized_value"])
        current = seen.get(key)
        if current is None:
            seen[key] = entity
            continue
        if entity.get("last_observed") and (
            current.get("last_observed") is None or entity["last_observed"] > current["last_observed"]
        ):
            current["last_observed"] = entity["last_observed"]
    return list(seen.values())
