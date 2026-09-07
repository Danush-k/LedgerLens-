from collections import deque
from typing import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# Enough parallelism to collapse a wide fan-out into one round trip, low
# enough to stay inside what free explorers tolerate - the point is to stop
# waiting serially, not to flood the provider into rate-limiting us.
MAX_CONCURRENT_FETCHES = 8


def _fetch_level(client, level: list[tuple[str, int]]) -> dict[str, tuple[list, str | None]]:
    """Fetch every address in one hop concurrently.

    Returns address -> (transfers, error). Failures are returned rather than
    raised so the caller keeps its existing per-address handling, where a
    dead fetch marks one branch unresolved instead of sinking the trace.
    """
    results: dict[str, tuple[list, str | None]] = {}
    addresses = list(dict.fromkeys(addr for addr, _ in level))

    if len(addresses) == 1:
        address = addresses[0]
        try:
            results[address] = (client.get_outgoing_transfers(address), None)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            results[address] = ([], f"{type(exc).__name__}: {exc}")
        return results

    with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_FETCHES, len(addresses))) as pool:
        futures = {pool.submit(client.get_outgoing_transfers, a): a for a in addresses}
        for future in as_completed(futures):
            address = futures[future]
            try:
                results[address] = (future.result(), None)
            except Exception as exc:  # noqa: BLE001
                results[address] = ([], f"{type(exc).__name__}: {exc}")
    return results


def trace_wallet(chain: Chain, reported_address: str, hop_limit: int = 5,
                  on_hop: Callable[[int, int, int], None] | None = None) -> TraceResult:
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
        # Taint: how much of this wallet is attributable to the victim.
        # Everything leaving the reported wallet is victim funds by
        # definition, so the root starts fully tainted.
        "tainted_value": 0.0,
        "taint_ratio": 1.0,
    }

    visited: set[str] = {root_uid}
    queue: deque[tuple[str, int]] = deque([(reported_address, 0)])
    seen_exchange = False

    # The walk proceeds one hop at a time. Every address at a given hop is
    # fetched concurrently - the work is network-bound, and fetching a
    # fifteen-way fan-out serially is what made a trace take minutes - but
    # the results are then processed in a fixed order, single-threaded.
    #
    # That split matters. Taint propagation reads a parent's accumulated
    # value when its children are created, so processing must stay ordered
    # and every hop must complete before the next begins; only the waiting
    # is parallel. It also keeps two traces of the same wallet identical,
    # which they would not be if graph mutation raced.
    while queue:
        # Take every address queued at the current hop. BFS enqueues in hop
        # order, so the frontier is the run of entries sharing the hop at
        # the head of the queue.
        current_hop = queue[0][1]
        level: list[tuple[str, int]] = []
        while queue and queue[0][1] == current_hop:
            level.append(queue.popleft())

        # BFS enqueues in non-decreasing hop order, so once the frontier
        # reaches the limit every address still queued is at or beyond it.
        # Breaking here is the same result as skipping each remaining level
        # in turn, without the wasted passes.
        if current_hop >= hop_limit:
            break

        # Report before fetching, not after. The fetch is the slow part, so
        # a progress message written afterwards describes work the user
        # already waited through.
        if on_hop:
            on_hop(current_hop, hop_limit, len(level))

        fetched = _fetch_level(client, level)

        truncated_here = False
        for address, hop in level:
            if truncated_here:
                break
            transfers, error = fetched[address]
            if error is not None:
                # A dead API call shouldn't crash the whole trace, but it must
                # not be silently treated as "this wallet sent nothing" either.
                result.fetch_errors.append({
                    "address": normalize_address(address),
                    "hop": hop,
                    "error": error,
                })
                if hop == 0:
                    result.root_fetch_failed = True
                continue

            fan_out = len({t.to_address for t in transfers})
            if fan_out > 10:
                result.flags.add("high_fan_out")

            # Taint propagation, haircut method. A wallet that received 1 unit of
            # victim funds and sends 10 units is sending money that is 10% the
            # victim's, so each outgoing transfer carries that proportion. This
            # is what lets the system say "3.4% of this wallet is victim funds"
            # instead of the far weaker "this wallet is connected".
            #
            # A forward-only trace sees outflows in full but only the inflows
            # that came from traced ancestors, so total inflow is unknown and
            # total outflow stands in for it. The ratio is capped at 1.0: a
            # wallet cannot forward more victim funds than reached it, and the
            # shortfall is simply value it retained.
            from_uid = _uid(chain_value, address)
            from_node = result.nodes.get(from_uid, {})
            total_out = sum(t.value for t in transfers)
            if hop == 0:
                taint_ratio = 1.0
            elif total_out > 0:
                taint_ratio = min(1.0, from_node.get("tainted_value", 0.0) / total_out)
            else:
                taint_ratio = 0.0
            from_node["taint_ratio"] = taint_ratio

            for transfer in transfers[:MAX_BREADTH_PER_NODE]:
                if len(result.nodes) >= MAX_NODES or len(result.edges) >= MAX_EDGES:
                    result.truncated = (
                        f"Stopped at {len(result.nodes)} wallets / {len(result.edges)} "
                        f"transfers - the graph exceeded the safe traversal budget, so "
                        f"branches beyond this point were not explored."
                    )
                    queue.clear()
                    truncated_here = True  # stop the rest of this hop too, not
                    break                  # only the remaining transfers

                to_uid = _uid(chain_value, transfer.to_address)
                label = lookup_label(chain_value, transfer.to_address)

                if to_uid not in result.nodes:
                    node_type = "unresolved"
                    label_name = None
                    label_source = None
                    if label:
                        node_type = label["type"]
                        label_name = label["name"]
                        # Provenance travels with the attribution. "This wallet is
                        # Binance" is a claim; "per an Etherscan public name tag"
                        # is a claim someone can check and challenge.
                        label_source = label.get("source") or None
                    result.nodes[to_uid] = {
                        "id": to_uid,
                        "address": normalize_address(transfer.to_address),
                        "chain": chain_value,
                        "node_type": node_type,
                        "label_name": label_name,
                        "label_source": label_source,
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
                        "tainted_value": 0.0,
                        "taint_ratio": 0.0,
                    }

                edge_taint = transfer.value * taint_ratio
                result.nodes[to_uid]["tainted_value"] = round(
                    result.nodes[to_uid].get("tainted_value", 0.0) + edge_taint, 12)

                result.edges.append({
                    "source": from_uid,
                    "target": to_uid,
                    "tx_hash": transfer.tx_hash,
                    "value": transfer.value,
                    "timestamp": transfer.timestamp,
                    "hop": hop + 1,
                    # The share of this transfer attributable to the victim.
                    "tainted_value": round(edge_taint, 12),
                })
                result.hops_reached = max(result.hops_reached, hop + 1)

                if label and label["type"] == "exchange":
                    if not seen_exchange or hop + 1 < result.nearest_exchange["hops"]:
                        result.nearest_exchange = {
                            "name": label["name"],
                            "address": transfer.to_address,
                            "chain": chain.value,
                            "hops": hop + 1,
                            "source": label.get("source") or None,
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

    _finalize_taint(result)
    return result


def _finalize_taint(result: TraceResult) -> None:
    """Restate every node's taint as one consistent, explainable ratio.

    During the walk, taint_ratio is a propagation coefficient (victim share
    of a wallet's *outflow*) and it is only set on wallets the trace
    actually stepped through - leaves such as exchange deposits never get
    one. For display and reporting a single definition is needed that holds
    for every node, so it is restated here as:

        of the value that reached this wallet along traced paths,
        this share is attributable to the victim

    The reported wallet is 1.0 by definition. Absolute tainted_value is
    unchanged - only the ratio is normalized.
    """
    inflow: dict[str, float] = {}
    for edge in result.edges:
        inflow[edge["target"]] = inflow.get(edge["target"], 0.0) + edge["value"]

    for uid, node in result.nodes.items():
        if node["hop"] == 0:
            node["taint_ratio"] = 1.0
            continue
        received = inflow.get(uid, 0.0)
        node["taint_ratio"] = (
            round(min(1.0, node.get("tainted_value", 0.0) / received), 6)
            if received > 0 else 0.0
        )
        node["tainted_value"] = round(node.get("tainted_value", 0.0), 8)
