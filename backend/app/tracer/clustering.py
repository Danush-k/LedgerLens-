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


def common_input_clusters(chain_client: ChainClient, visited_addresses: set[str],
                          max_lookups: int = 5) -> list[dict]:
    # Common-input-ownership only applies to UTXO-based chains like Bitcoin.
    if chain_client.chain != Chain.BITCOIN:
        return []

    # Limit sequential external API calls so traces never stall or trigger 429 rate limits.
    addrs_to_check = list(visited_addresses)[:max_lookups]

    clusters = []
    for address in addrs_to_check:
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


# A wallet paying two others is an ordinary transaction, not a discovery -
# at that size a "shared funder" group is the graph edge restated, and every
# fan-out in the trace produces one. Requiring a real group keeps the panel
# to distributions worth a second look; the fan-out detector already reports
# dispersal itself, so nothing is lost by staying quiet below this.
MIN_SHARED_FUNDER_GROUP = 4


def shared_funder_clusters(nodes: dict[str, dict], edges: list[dict]) -> list[dict]:
    """Wallets paid by the same source within this trace.

    This is a distribution pattern, not an ownership finding, and the two
    must not be confused: common-input-ownership proves one key signed for
    several addresses, whereas being paid by the same wallet is what happens
    to every customer of the same payroll, exchange or service. The note
    says so, because these are displayed beside genuine ownership clusters
    and would otherwise be read as the same kind of claim.
    """
    by_source: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        by_source[edge["source"]].add(edge["target"])

    clusters = []
    for source_id, target_ids in by_source.items():
        if len(target_ids) < MIN_SHARED_FUNDER_GROUP:
            continue
        source_addr = nodes.get(source_id, {}).get("address", source_id)
        addrs = sorted(nodes[t]["address"] for t in target_ids if t in nodes)
        if len(addrs) < MIN_SHARED_FUNDER_GROUP:
            continue
        clusters.append({
            "type": "shared_funder",
            "addresses": addrs,
            "note": (
                f"{len(addrs)} wallets were each paid directly by {source_addr} in "
                f"this trace. This is a distribution pattern only - it does not "
                f"establish that these wallets share an owner."
            ),
        })
    return clusters
