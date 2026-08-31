from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.chain_clients.base import Chain, Transfer, normalize_address
from app.chain_clients.factory import get_chain_client
from app.labels.loader import lookup_label


@dataclass
class TraceResult:
    nodes: dict[str, dict] = field(default_factory=dict)  # uid -> node dict
    edges: list[dict] = field(default_factory=list)
    nearest_exchange: dict | None = None
    flags: set[str] = field(default_factory=set)
    hops_reached: int = 0
    # The chain client used for this trace - kept around so a clustering
    # pass can reuse its warm per-address tx cache instead of refetching.
    chain_client: Any = None


def _uid(chain: str, address: str) -> str:
    return f"{chain}:{normalize_address(address)}"


def trace_wallet(chain: Chain, reported_address: str, hop_limit: int = 5,
                  on_hop: callable = None) -> TraceResult:
    """Breadth-first walk of outgoing transfers from a reported wallet.

    Stops a branch as soon as it reaches a known exchange address (that's
    the "nearest VASP" answer). Flags mixer/bridge hits but keeps tracing
    past them. Branches that hit the hop limit unresolved are left as-is -
    that's a signal too (funds still untraced).
    """
    client = get_chain_client(chain)
    chain_value = chain.value  # enums str-format as "Chain.X", not "x" - always use .value in ids
    result = TraceResult(chain_client=client)

    root_uid = _uid(chain_value, reported_address)
    result.nodes[root_uid] = {
        "id": root_uid,
        "address": normalize_address(reported_address),
        "chain": chain_value,
        "node_type": "reported",
        "label_name": None,
    }

    visited: set[str] = {root_uid}
    queue: deque[tuple[str, int]] = deque([(reported_address, 0)])
    seen_exchange = False

    while queue:
        address, hop = queue.popleft()
        if hop >= hop_limit:
            continue

        try:
            transfers: list[Transfer] = client.get_outgoing_transfers(address)
        except Exception:
            # A dead API call shouldn't crash the whole trace - this branch
            # just stays unresolved, which is itself informative.
            continue

        fan_out = len({t.to_address for t in transfers})
        if fan_out > 10:
            result.flags.add("high_fan_out")

        for transfer in transfers[:15]:  # cap breadth per node for demo performance
            to_uid = _uid(chain_value, transfer.to_address)
            label = lookup_label(chain_value, transfer.to_address)

            if to_uid not in result.nodes:
                node_type = "unresolved"
                label_name = None
                if label:
                    node_type = label["type"]
                    label_name = label["name"]
                result.nodes[to_uid] = {
                    "id": to_uid,
                    "address": normalize_address(transfer.to_address),
                    "chain": chain_value,
                    "node_type": node_type,
                    "label_name": label_name,
                }

            result.edges.append({
                "source": _uid(chain_value, address),
                "target": to_uid,
                "tx_hash": transfer.tx_hash,
                "value": transfer.value,
                "timestamp": transfer.timestamp,
                "hop": hop + 1,
            })
            result.hops_reached = max(result.hops_reached, hop + 1)

            if on_hop:
                on_hop(hop + 1, hop_limit)

            if label and label["type"] == "exchange":
                if not seen_exchange or hop + 1 < result.nearest_exchange["hops"]:
                    result.nearest_exchange = {
                        "name": label["name"],
                        "address": transfer.to_address,
                        "chain": chain.value,
                        "hops": hop + 1,
                    }
                seen_exchange = True
                continue  # stop this branch - nearest VASP found

            if label and label["type"] == "mixer":
                result.flags.add("mixer_detected")
                continue  # flagged, but a mixer breaks the traceable link - stop here

            if label and label["type"] == "bridge":
                result.flags.add("cross_chain_bridge")
                # flagged; continuing to trace past a bridge on the same
                # chain adds little value, so this branch stops too

            if to_uid not in visited:
                visited.add(to_uid)
                if label is None:
                    queue.append((transfer.to_address, hop + 1))

    if not seen_exchange:
        result.flags.add("no_exchange_found")

    return result
