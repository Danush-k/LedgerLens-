"""Two independent, explainable clustering heuristics - no ML, no guessing.

1. Common-input-ownership (Bitcoin only): if an address was spent as one of
   several inputs on the same transaction, every other input address on
   that transaction was necessarily signed by the same key holder. This is
   the textbook UTXO clustering heuristic used by real chain-analysis tools.

2. Shared-funder fan-out (any chain): if one address sends directly to
   several others, those recipients are often operator-controlled wallets
   (mule accounts, distribution wallets) rather than unrelated third
   parties - a weaker signal than (1), always labeled as such.
"""
import logging
from collections import defaultdict

from app.chain_clients.base import Chain, ChainClient

logger = logging.getLogger(__name__)


def common_input_clusters(chain_client: ChainClient, visited_addresses: set[str]) -> list[dict]:
    # Common-input-ownership only applies to UTXO-based chains like Bitcoin.
    if chain_client.chain != Chain.BITCOIN:
        return []

    clusters = []
    for address in visited_addresses:
        # One network call per address, and a provider that rate-limits or
        # times out part-way through must not discard an otherwise complete
        # trace. Clustering enriches a result; it does not constitute it. A
        # missing cluster is a smaller loss than a failed case, so failures
        # are logged and skipped rather than raised.
        try:
            co_spent = chain_client.get_co_spent_addresses(address)
        except Exception as exc:  # noqa: BLE001 - see above
            logger.warning(f"Co-spend lookup failed for {address}, skipping: {exc}")
            continue
        if co_spent:
            clusters.append({
                "type": "common_input",
                "addresses": sorted({address, *co_spent}),
                "note": (
                    f"{address} was spent as one of multiple inputs on the same transaction as "
                    f"{len(co_spent)} other address(es) - they share the same private key holder."
                ),
            })
    return clusters


def shared_funder_clusters(nodes: dict[str, dict], edges: list[dict]) -> list[dict]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        by_source[edge["source"]].add(edge["target"])

    clusters = []
    for source_id, target_ids in by_source.items():
        if len(target_ids) < 2:
            continue
        source_addr = nodes.get(source_id, {}).get("address", source_id)
        addrs = sorted(nodes[t]["address"] for t in target_ids if t in nodes)
        clusters.append({
            "type": "shared_funder",
            "addresses": addrs,
            "note": f"All {len(addrs)} received funds directly from {source_addr} in this trace.",
        })
    return clusters
