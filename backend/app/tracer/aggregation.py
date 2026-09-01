from sqlalchemy.orm import Session
from app.models.orm import Case


def aggregate_case_graphs(case_ids: list[str], db: Session) -> dict:
    """Merges graph nodes and edges from multiple cases into a single unified multi-wallet
    investigation graph, identifying shared intermediary wallets and joint exchange targets.
    """
    cases = db.query(Case).filter(Case.id.in_(case_ids)).all()
    
    merged_nodes: dict[str, dict] = {}
    merged_edges: list[dict] = []
    seen_edge_hashes: set[str] = set()
    node_case_map: dict[str, set[str]] = {}

    for c in cases:
        if not c.graph or not isinstance(c.graph, dict):
            continue
        nodes = c.graph.get("nodes") or []
        edges = c.graph.get("edges") or []

        for node in nodes:
            nid = node["id"]
            if nid not in node_case_map:
                node_case_map[nid] = set()
            node_case_map[nid].add(c.id)

            if nid not in merged_nodes:
                merged_nodes[nid] = {**node, "is_shared": False, "case_ids": [c.id]}
            else:
                merged_nodes[nid]["case_ids"] = list(set(merged_nodes[nid]["case_ids"] + [c.id]))
                merged_nodes[nid]["is_shared"] = len(merged_nodes[nid]["case_ids"]) > 1

        for edge in edges:
            edge_key = f"{edge['source']}->{edge['target']}:{edge['tx_hash']}"
            if edge_key not in seen_edge_hashes:
                seen_edge_hashes.add(edge_key)
                merged_edges.append(edge)

    # Flag all nodes that appear in multiple merged cases
    for nid, case_set in node_case_map.items():
        if len(case_set) > 1 and nid in merged_nodes:
            merged_nodes[nid]["is_shared"] = True

    return {
        "nodes": list(merged_nodes.values()),
        "edges": merged_edges,
        "case_count": len(cases),
        "shared_nodes_count": sum(1 for n in merged_nodes.values() if n.get("is_shared")),
    }
