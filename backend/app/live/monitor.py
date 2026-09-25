"""Watching a case's wallets after its trace has finished.

A trace is a photograph. It answers "where did the money go?" as of the
moment it ran, and from then on the case page shows a picture of a chain
that has kept moving without it. That gap is where investigations are lost:
the wallet holding the victim's funds sends them to an exchange two hours
after the complaint is filed, and nothing in the system says so until
somebody thinks to re-run the trace by hand.

This module closes the gap. It re-reads the outgoing history of the wallets
in a case on an interval, and any transfer it has not seen before is
appended to the case - as a graph edge, as a row in the live feed, as an
entry in the tamper-evident audit chain, and as an event pushed to whoever
has the case open.

Two constraints shape the design.

The free block explorers this system runs on are rate-limited, and they are
the binding constraint on everything else it does. So a case is watched only
while an investigator actually has it open, or when someone has explicitly
asked for it to be watched in the background, and only a handful of its
wallets are re-checked per cycle - the ones still holding victim funds,
which is where the next move comes from.

And a live update must never quietly rewrite history. Figures already
printed in a report and cited in a legal notice keep their meaning: new
movement adds to a case, and the audit chain records that it did.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.chain_clients.base import Chain, normalize_address
from app.chain_clients.factory import get_chain_client
from app.config import get_settings
from app.db.neo4j_client import record_transfer, upsert_address
from app.db.postgres import SessionLocal
from app.labels.loader import lookup_label
from app.models.orm import Case, CaseAddress, LiveTransfer, TracedAddress
from app.reports.audit_chain import append_audit_event
from app.risk.rules import recommended_action, score_case
from app.tracer.bfs import apply_taint_to_new_edges, fetch_outgoing_concurrently
from app.tracer.patterns import flags_from_patterns, run_detectors

logger = logging.getLogger(__name__)

# How often the loop wakes to see whether any case is due. Cases are checked
# on their own, much longer interval - this only bounds the lag between a
# case becoming due and the check starting.
TICK_SECONDS = 5

# A wallet that suddenly emits hundreds of transfers is a service or a
# script, not a lead. Capping what one cycle ingests keeps a burst from
# burying the case graph, and the remainder is picked up next cycle.
MAX_NEW_EDGES_PER_CHECK = 40

# Known services are not watched. An exchange hot wallet moves money for
# thousands of unrelated people every minute: re-reading it would spend the
# whole rate-limit budget to report activity that says nothing about this
# case. The trail ends at the service - what happens inside it is answered
# by a legal request, not by a block explorer.
SERVICE_TYPES = {"exchange", "mixer", "bridge"}

# Findings that come from comparing this case against others in the
# database, rather than from its own subgraph. The detectors cannot
# re-derive them, so they are carried across a live re-score unchanged.
CROSS_CASE_PATTERNS = {"shared_downstream", "prior_report"}


def _uid(chain: str, address: str) -> str:
    return f"{chain}:{normalize_address(address)}"


def iso_utc(value: datetime | None) -> str | None:
    """An ISO timestamp a browser will read as UTC.

    Everything here is written in UTC, but SQLite hands the value back with
    no timezone on it, and JavaScript reads a naive timestamp as local time.
    On a machine set to IST that turns "detected 20 seconds ago" into
    "detected in five and a half hours", which is worse than showing nothing.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _fmt_value(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def _short(address: str) -> str:
    return address if len(address) <= 16 else f"{address[:10]}…{address[-4:]}"


def _why_included_live(from_address: str, value: float, tx_hash: str,
                        timestamp: int, hop: int) -> str:
    """Provenance for a wallet that appeared after the trace ended.

    It says the same thing a traced node's provenance says - which transfer
    put this wallet in the investigation - and adds the part that matters
    here: this is movement that happened while the case was open, not
    something the original trace found and the reader has already seen.
    """
    when = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Received {_fmt_value(value)} from {_short(from_address)} at hop {hop} "
        f"(tx {tx_hash[:12]}…, {when}) — detected by live monitoring after the "
        f"original trace completed."
    )


def select_watch_addresses(nodes: list[dict], edges: list[dict], hop_limit: int,
                            limit: int) -> list[str]:
    """The wallets worth re-reading, most valuable first.

    The budget is small, so the order is the whole design. The reported
    wallet always comes first - it is the one the complaint names and the
    one a victim will ask about. After that come wallets that have received
    funds and not yet sent them on: money sitting still is money that can
    still move, and money that has already moved on has been followed
    already. Within each group, the wallets holding the most victim funds
    come first, because that is where a freeze request is worth sending.

    Known services are excluded, and so is anything at the hop limit - a
    transfer from there would produce a wallet beyond the depth the
    investigator asked for.
    """
    has_outgoing = Counter(edge["source"] for edge in edges)

    candidates = [
        node for node in nodes
        if node.get("node_type") not in SERVICE_TYPES
        and node.get("hop", 0) < hop_limit
    ]
    candidates.sort(key=lambda node: (
        node.get("hop", 0) != 0,                          # the reported wallet, always
        has_outgoing.get(node["id"], 0) > 0,              # then wallets still holding funds
        -float(node.get("tainted_value") or 0.0),         # then by victim money at stake
        node.get("hop", 0),
    ))
    return [node["address"] for node in candidates[:limit]]


def _prior_report_count(db: Session, case: Case) -> int:
    """Distinct other complaints naming this wallet - see worker/tasks.py,
    where the same count is computed at trace time and the reasoning for
    counting complaints rather than case rows is set out in full."""
    rows = (
        db.query(Case.complaint_ref, Case.created_by)
        .join(TracedAddress, TracedAddress.case_id == Case.id)
        .filter(TracedAddress.chain == case.chain,
                TracedAddress.address == case.reported_address,
                TracedAddress.case_id != case.id)
        .all()
    )
    return len({(ref, who) if ref else ("__unreferenced__", who) for ref, who in rows})


def check_case_for_new_transfers(db: Session, case_id: str) -> dict | None:
    """Re-read a completed case's wallets and fold in anything new.

    Returns a description of the check - what was looked at, what was found,
    and the case fields that changed - or None when the case is not in a
    state where watching means anything. Never raises for a fetch failure:
    an unreachable explorer means "we could not look", which is reported as
    such rather than as "nothing moved".
    """
    settings = get_settings()

    case = db.get(Case, case_id)
    if case is None or case.status != "complete":
        return None  # a running trace is already walking these wallets itself

    graph = case.graph or {}
    nodes_before = graph.get("nodes") or []
    if not nodes_before:
        return None

    chain = Chain(case.chain)
    hop_limit = case.hop_limit
    addresses = select_watch_addresses(nodes_before, graph.get("edges") or [],
                                        hop_limit, settings.live_watch_addresses)

    # The transaction is closed before the fetch: a handful of explorer calls
    # can take tens of seconds, and holding a database connection open across
    # them for no reason is how a pool runs dry.
    db.rollback()

    if not addresses:
        return _record_check(db, case_id, addresses=[], errors=[], new_edges=[],
                              new_nodes=[])

    # Deliberately uncached. The shared chain cache holds an address's
    # history for an hour, which is right for tracing and exactly wrong
    # here - serving an hour-old answer to "has anything moved just now?"
    # would make the feature report staleness as stillness.
    client = get_chain_client(chain, cached=False)
    fetched = fetch_outgoing_concurrently(client, addresses)

    case = db.get(Case, case_id)
    if case is None or case.status != "complete":
        return None
    # Re-read after the fetch: a re-trace may have replaced the graph while
    # the explorer calls were in flight.
    graph = case.graph or {}
    nodes = {n["id"]: dict(n) for n in (graph.get("nodes") or [])}
    edges = [dict(e) for e in (graph.get("edges") or [])]
    known = {(e["tx_hash"], e["source"], e["target"]) for e in edges}

    now = datetime.now(timezone.utc)
    new_edges: list[dict] = []
    new_nodes: list[dict] = []
    errors: list[dict] = []

    for address in addresses:
        transfers, error = fetched.get(address, ([], "address was not fetched"))
        if error is not None:
            errors.append({"address": normalize_address(address), "error": error})
            continue

        source_uid = _uid(case.chain, address)
        source_node = nodes.get(source_uid)
        if source_node is None:
            continue  # the graph changed under us; it will be picked up next cycle
        hop = source_node.get("hop", 0)

        for transfer in transfers:
            if len(new_edges) >= MAX_NEW_EDGES_PER_CHECK:
                break
            target_uid = _uid(case.chain, transfer.to_address)
            key = (transfer.tx_hash, source_uid, target_uid)
            if key in known:
                continue
            known.add(key)

            if target_uid not in nodes:
                label = lookup_label(case.chain, transfer.to_address)
                nodes[target_uid] = {
                    "id": target_uid,
                    "address": normalize_address(transfer.to_address),
                    "chain": case.chain,
                    "node_type": label["type"] if label else "unresolved",
                    "label_name": label["name"] if label else None,
                    "label_source": (label.get("source") or None) if label else None,
                    "hop": hop + 1,
                    "why_included": _why_included_live(
                        normalize_address(address), transfer.value,
                        transfer.tx_hash, transfer.timestamp, hop + 1),
                    "provenance": {
                        "from_address": normalize_address(address),
                        "tx_hash": transfer.tx_hash,
                        "value": transfer.value,
                        "timestamp": transfer.timestamp,
                        "hop": hop + 1,
                    },
                    "tainted_value": 0.0,
                    "taint_ratio": 0.0,
                    # Marks this as movement that happened while the case was
                    # open, so the graph can show it as new rather than
                    # silently growing between page loads.
                    "detected_live": True,
                    "first_seen_at": now.isoformat(),
                }
                new_nodes.append(nodes[target_uid])

            edge = {
                "source": source_uid,
                "target": target_uid,
                "tx_hash": transfer.tx_hash,
                "value": transfer.value,
                "timestamp": transfer.timestamp,
                "hop": hop + 1,
                "tainted_value": 0.0,
                "detected_live": True,
                "first_seen_at": now.isoformat(),
            }
            edges.append(edge)
            new_edges.append(edge)

    if not new_edges:
        return _record_check(db, case_id, addresses=addresses, errors=errors,
                              new_edges=[], new_nodes=[])

    apply_taint_to_new_edges(nodes, edges, new_edges)
    _apply_new_movement(db, case, nodes, edges, new_nodes, new_edges, graph, now)

    return _record_check(db, case_id, addresses=addresses, errors=errors,
                          new_edges=new_edges, new_nodes=new_nodes)


def _apply_new_movement(db: Session, case: Case, nodes: dict[str, dict],
                         edges: list[dict], new_nodes: list[dict],
                         new_edges: list[dict], previous_graph: dict,
                         now: datetime) -> None:
    """Write newly observed movement into the case and restate what it changes."""
    # 1. Does the money now reach an exchange - or reach one sooner? This is
    #    the headline result of the whole system, and a live transfer into a
    #    deposit address is the moment it becomes answerable.
    exchanges = [n for n in nodes.values() if n.get("node_type") == "exchange"]
    if exchanges:
        nearest = min(exchanges, key=lambda n: n.get("hop", 99))
        current_hops = (case.nearest_exchange or {}).get("hops", 99)
        if not case.nearest_exchange or nearest.get("hop", 99) < current_hops:
            case.nearest_exchange = {
                "name": nearest.get("label_name"),
                "address": nearest["address"],
                "chain": case.chain,
                "hops": nearest.get("hop", 0),
                "source": nearest.get("label_source"),
            }

    # 2. Re-derive the findings over the enlarged graph. Cross-case findings
    #    are carried across untouched - they are answers about other cases in
    #    the database, which the detectors cannot see.
    preserved = [p for p in (case.patterns or [])
                 if p.get("pattern") in CROSS_CASE_PATTERNS]
    patterns = run_detectors(nodes, edges, case.nearest_exchange, case.hop_limit)
    patterns += preserved

    # Flags only accumulate. Everything the original trace established about
    # the subgraph is still true of it - the graph only ever grows - so the
    # old set is kept and the new evidence added to it. The one exception is
    # the absence claim: "no exchange found" stops being true the moment one
    # is found, and leaving it standing would contradict the finding beside it.
    flags = set(case.flags or []) | flags_from_patterns(patterns)
    if case.nearest_exchange:
        flags.discard("no_exchange_found")

    shared = next((p for p in preserved if p.get("pattern") == "shared_downstream"), None)
    score, breakdown = score_case(
        flags,
        case.nearest_exchange,
        _prior_report_count(db, case),
        rapid_layering=any(p["pattern"] == "rapid_movement" for p in patterns),
        shared_downstream_count=len(shared.get("links") or []) if shared else 0,
    )
    previous_score = case.risk_score

    case.graph = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "truncated": previous_graph.get("truncated"),
    }
    case.patterns = patterns
    case.flags = sorted(flags)
    case.risk_score = score
    case.risk_breakdown = breakdown
    case.recommended_action = recommended_action(case.nearest_exchange, score)
    case.live_event_count = (case.live_event_count or 0) + len(new_edges)
    case.live_last_event_at = now

    # 3. The address footprint feeds cross-case convergence analysis, so a
    #    wallet reached live has to land there too - otherwise the wallet
    #    collecting from several victims stays invisible precisely when it is
    #    most active.
    for uid in {e["target"] for e in new_edges}:
        node = nodes.get(uid)
        if node is None:
            continue
        value_in = sum(e["value"] for e in edges if e["target"] == uid)
        row = (
            db.query(CaseAddress)
            .filter(CaseAddress.case_id == case.id,
                    CaseAddress.chain == node["chain"],
                    CaseAddress.address == node["address"])
            .first()
        )
        if row is None:
            db.add(CaseAddress(
                case_id=case.id, chain=node["chain"], address=node["address"],
                hop=node.get("hop", 0), value_in=value_in,
                node_type=node.get("node_type"), label_name=node.get("label_name"),
                tainted_value=node.get("tainted_value", 0.0),
                taint_ratio=node.get("taint_ratio", 0.0),
            ))
        else:
            row.value_in = value_in
            row.tainted_value = node.get("tainted_value", 0.0)
            row.taint_ratio = node.get("taint_ratio", 0.0)

    # 4. The feed, which is what survives a page reload.
    for edge in new_edges:
        target = nodes[edge["target"]]
        db.add(LiveTransfer(
            case_id=case.id,
            chain=case.chain,
            tx_hash=edge["tx_hash"],
            from_address=nodes[edge["source"]]["address"],
            to_address=target["address"],
            value=edge["value"],
            timestamp=edge["timestamp"],
            hop=edge["hop"],
            to_node_type=target.get("node_type"),
            to_label_name=target.get("label_name"),
            detected_at=now,
        ))

    # 5. The audit chain. Movement detected after the report was filed is
    #    evidence in its own right, and when it was first seen can matter as
    #    much as when it happened - so it is recorded where the record is
    #    tamper-evident, not only in the graph.
    destinations = ", ".join(
        f"{_short(nodes[e['target']]['address'])}"
        f"{' (' + nodes[e['target']]['label_name'] + ')' if nodes[e['target']].get('label_name') else ''}"
        for e in new_edges[:5]
    )
    detail = (
        f"{len(new_edges)} new outgoing transfer(s) detected after the trace "
        f"completed, totalling {_fmt_value(sum(e['value'] for e in new_edges))} "
        f"to {destinations}"
        f"{' and others' if len(new_edges) > 5 else ''}."
    )
    if previous_score is not None and previous_score != score:
        detail += f" Risk score restated from {previous_score:.0f} to {score:.0f}."
    append_audit_event(db, case.id, "live_transfer_detected", detail)

    db.commit()

    # 6. Neo4j mirrors the graph for path queries. Best effort by design -
    #    it is routinely absent in development, and the case must not fail
    #    to record a transfer because a secondary store is down.
    try:
        for node in new_nodes:
            upsert_address(node["chain"], node["address"],
                            {"type": node["node_type"], "name": node["label_name"]}
                            if node.get("label_name") else None)
        for edge in new_edges:
            record_transfer(case.id, case.chain, nodes[edge["source"]]["address"],
                             nodes[edge["target"]]["address"], edge["tx_hash"],
                             edge["value"], edge["timestamp"], edge["hop"])
    except Exception as exc:  # noqa: BLE001 - a mirror, not the record
        logger.debug(f"Neo4j live mirror skipped for {case.id}: {exc}")


def _record_check(db: Session, case_id: str, addresses: list[str], errors: list[dict],
                   new_edges: list[dict], new_nodes: list[dict]) -> dict | None:
    """Stamp the case with when it was last looked at, and describe the check.

    Recorded even when nothing was found, because "checked 20 seconds ago,
    nothing new" and "not checked since the trace ran" are different
    statements and only one of them justifies trusting what is on screen.
    """
    case = db.get(Case, case_id)
    if case is None:
        return None
    checked_at = datetime.now(timezone.utc)
    case.live_checked_at = checked_at
    db.commit()

    return {
        "case_id": case_id,
        "checked_at": iso_utc(checked_at),
        "addresses_checked": [normalize_address(a) for a in addresses],
        "errors": errors,
        "new_nodes": new_nodes,
        "new_edges": new_edges,
        "case": {
            "risk_score": case.risk_score,
            "risk_breakdown": case.risk_breakdown,
            "flags": case.flags,
            "nearest_exchange": case.nearest_exchange,
            "recommended_action": case.recommended_action,
            "patterns": case.patterns,
            "live_event_count": case.live_event_count or 0,
            "live_checked_at": iso_utc(checked_at),
            "live_last_event_at": iso_utc(case.live_last_event_at),
        },
    }


class LiveMonitor:
    """The watch list, the loop that services it, and the fan-out to viewers.

    Membership of the watch list is deliberately not a user setting by
    default. A case is watched because somebody is looking at it, which is
    both when live data is worth having and when spending explorer quota on
    it is defensible. `live_watch` on the case row is the explicit override
    for a case that must be followed while nobody is watching.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._viewed_at: dict[str, float] = {}
        self._next_check_at: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ── viewers ───────────────────────────────────────────────────────────

    def subscribe(self, case_id: str) -> "queue.Queue[dict]":
        """Register a stream and get the queue its events will arrive on."""
        channel: "queue.Queue[dict]" = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.setdefault(case_id, []).append(channel)
            self._viewed_at[case_id] = time.monotonic()
            # A page that has just been opened should not wait a full cycle
            # for its first check.
            self._next_check_at.setdefault(case_id, 0.0)
        return channel

    def unsubscribe(self, case_id: str, channel: "queue.Queue[dict]") -> None:
        with self._lock:
            channels = self._subscribers.get(case_id)
            if not channels:
                return
            if channel in channels:
                channels.remove(channel)
            if not channels:
                self._subscribers.pop(case_id, None)

    def mark_viewed(self, case_id: str) -> None:
        """Note that somebody just read this case.

        Called from the ordinary case endpoint, so a client that cannot hold
        a stream open - an old browser, a proxy that buffers - still gets
        live data by polling, instead of silently getting a frozen page.
        """
        with self._lock:
            self._viewed_at[case_id] = time.monotonic()
            self._next_check_at.setdefault(case_id, 0.0)

    def viewer_count(self, case_id: str) -> int:
        with self._lock:
            return len(self._subscribers.get(case_id, []))

    def publish(self, case_id: str, event_type: str, data: dict) -> None:
        event = {"type": event_type, "data": data}
        with self._lock:
            channels = list(self._subscribers.get(case_id, []))
        for channel in channels:
            try:
                channel.put_nowait(event)
            except queue.Full:
                # A stream nobody is draining is a stream nobody is reading.
                # Dropping is right: the client re-syncs from the case on
                # reconnect, so a stale backlog buys nothing.
                logger.debug(f"Dropped live event for a full channel on case {case_id}")

    # ── the loop ──────────────────────────────────────────────────────────

    def start(self) -> None:
        settings = get_settings()
        if not settings.live_monitor_enabled:
            logger.info("Live monitoring disabled by configuration")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="live-monitor", daemon=True)
        self._thread.start()
        logger.info(
            f"Live monitoring started - watched cases re-checked every "
            f"{settings.live_poll_seconds}s across up to "
            f"{settings.live_watch_addresses} wallets each"
        )

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001 - the loop outlives any one failure
                logger.warning(f"Live monitor tick failed: {exc}")

    def _tick(self) -> None:
        settings = get_settings()
        db = SessionLocal()
        try:
            due = self._due_case_ids(db, settings)
            for case_id in due[:settings.live_max_cases_per_tick]:
                with self._lock:
                    self._next_check_at[case_id] = (
                        time.monotonic() + settings.live_poll_seconds)
                try:
                    result = check_case_for_new_transfers(db, case_id)
                except Exception as exc:  # noqa: BLE001 - one bad case, not the watcher
                    db.rollback()
                    logger.warning(f"Live check failed for case {case_id}: {exc}")
                    continue
                if result is None:
                    continue
                self.publish(case_id, "check", {
                    "checked_at": result["checked_at"],
                    "addresses_checked": len(result["addresses_checked"]),
                    "errors": result["errors"],
                    "new_count": len(result["new_edges"]),
                })
                if result["new_edges"]:
                    self.publish(case_id, "transactions", {
                        "detected_at": result["checked_at"],
                        "nodes": result["new_nodes"],
                        "edges": result["new_edges"],
                        "case": result["case"],
                    })
                    logger.info(
                        f"Live: {len(result['new_edges'])} new transfer(s) on case {case_id}")
        finally:
            db.close()

    def _due_case_ids(self, db: Session, settings) -> list[str]:
        """Cases being watched right now, that are due for a check."""
        now = time.monotonic()
        with self._lock:
            # Viewers expire, so closing the tab stops the explorer calls
            # without the client having to say anything.
            cutoff = now - settings.live_viewer_ttl_seconds
            self._viewed_at = {cid: at for cid, at in self._viewed_at.items() if at >= cutoff}
            watched = set(self._subscribers) | set(self._viewed_at)

        # Plus anything explicitly pinned for background watching.
        pinned = {
            row[0] for row in
            db.query(Case.id).filter(Case.live_watch.is_(True),
                                      Case.status == "complete").all()
        }
        watched |= pinned

        with self._lock:
            due = [cid for cid in watched if now >= self._next_check_at.get(cid, 0.0)]
            # Forget the schedule for cases nobody is watching any more.
            self._next_check_at = {cid: at for cid, at in self._next_check_at.items()
                                    if cid in watched}
        return sorted(due)


live_monitor = LiveMonitor()
