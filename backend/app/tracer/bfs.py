from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.chain_clients.base import Chain, Transfer, normalize_address
from app.chain_clients.factory import get_chain_client
from app.labels.loader import lookup_label


from datetime import datetime, timezone

# Safeguards against a runaway trace on a busy address. All configurable
# per call; the defaults keep a demo responsive without truncating a
# realistic multi-hop laundering chain.
MAX_NODES = 400
MAX_EDGES = 1200
MAX_BREADTH_PER_NODE = 15


@dataclass
class TraceResult:
    nodes: dict[str, dict] = field(default_factory=dict)  # uid -> node dict
    edges: list[dict] = field(default_factory=list)
    nearest_exchange: dict | None = None
    flags: set[str] = field(default_factory=set)
    hops_reached: int = 0
    # Set when a safeguard stopped the walk early, so the UI can say the
    # trace was truncated rather than silently implying it was exhaustive.
    truncated: str | None = None
    # Addresses whose blockchain data could not be fetched (dead API, rate
    # limit, network error). Tracked rather than swallowed: "we could not
    # look" and "we looked and found nothing" are completely different
    # findings, and only one of them justifies a risk score.
    fetch_errors: list[dict] = field(default_factory=list)
    root_fetch_failed: bool = False
    # The chain client used for this trace - kept around so a clustering
    # pass can reuse its warm per-address tx cache instead of refetching.
    chain_client: Any = None


def _uid(chain: str, address: str) -> str:
    return f"{chain}:{normalize_address(address)}"


def _fmt_value(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def _why_included(from_address: str, value: float, tx_hash: str,
                   timestamp: int, hop: int) -> str:
    """The provenance sentence for a node: the specific, checkable reason
    this wallet is in the investigation at all.

    Without this, a node in the graph is an assertion. With it, every
    wallet carries the transaction that put it there.
    """
    when = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    short_from = from_address if len(from_address) <= 16 else f"{from_address[:10]}…{from_address[-4:]}"
    return (
        f"Received {_fmt_value(value)} from {short_from} at hop {hop} "
        f"(tx {tx_hash[:12]}…, {when})."
    )


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
        "hop": 0,
        "why_included": "Reported by the complainant as the suspect wallet.",
        "provenance": None,  # the root has no upstream edge inside this trace
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
        except Exception as exc:
            # A dead API call shouldn't crash the whole trace, but it must
            # not be silently treated as "this wallet sent nothing" either.
            result.fetch_errors.append({
                "address": normalize_address(address),
                "hop": hop,
                "error": f"{type(exc).__name__}: {exc}",
            })
            if hop == 0:
                result.root_fetch_failed = True
            continue

        fan_out = len({t.to_address for t in transfers})
        if fan_out > 10:
            result.flags.add("high_fan_out")

        for transfer in transfers[:MAX_BREADTH_PER_NODE]:
            if len(result.nodes) >= MAX_NODES or len(result.edges) >= MAX_EDGES:
                result.truncated = (
                    f"Stopped at {len(result.nodes)} wallets / {len(result.edges)} "
                    f"transfers - the graph exceeded the safe traversal budget, so "
                    f"branches beyond this point were not explored."
                )
                queue.clear()
                break

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
                    "hop": hop + 1,
                    # Provenance: the specific transfer that pulled this
                    # wallet into the investigation.
                    "why_included": _why_included(
                        normalize_address(address), transfer.value,
                        transfer.tx_hash, transfer.timestamp, hop + 1,
                    ),
                    "provenance": {
                        "from_address": normalize_address(address),
                        "tx_hash": transfer.tx_hash,
                        "value": transfer.value,
                        "timestamp": transfer.timestamp,
                        "hop": hop + 1,
                    },
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

    # "No exchange found" is only an honest finding if we actually managed
    # to look. When the root fetch failed we retrieved nothing at all, so
    # claiming the trail dead-ends would be inventing a result.
    if result.root_fetch_failed:
        result.flags.add("data_unavailable")
    elif not seen_exchange:
        result.flags.add("no_exchange_found")

    if result.fetch_errors and not result.root_fetch_failed:
        result.flags.add("partial_data")

    return result
