"""From a transaction graph to a list of people to investigate.

The graph answers "where did the money go?", but it answers in a form only a
chain analyst can read: a few hundred nodes and edges, and the conclusions
left for the reader to draw. An investigating officer does not need the
graph. They need to know which wallets matter, why each one matters in a
sentence they could repeat to a magistrate, and what to do about it.

This module does that reading. Every wallet in a completed trace is checked
against a fixed set of named signals - where the victim's money landed, how
it was moved, whether other complaints touch the same wallet - and each
signal that fires contributes points *and a reason*. The ranking is the sum;
the reasons are the explanation, and each carries the transactions it rests
on so any line can be checked against the public ledger.

Three rules, carried over from the detectors this builds on:

1. **A suspect is a lead, not a finding.** The score orders the list; it
   does not accuse anyone. Only an officer's confirmation (SuspectDecision)
   puts a wallet into a report.
2. **Say what weakens the case, too.** Signals that cut the other way -
   commingled funds, a wallet that behaves like a shared service - are
   reported as caveats and subtract from the score rather than being left
   out.
3. **Services are not suspects.** Mixers and bridges are where a trail
   breaks, and are reported as such. An exchange deposit address is the
   exception: the service is not the suspect, but the account holder behind
   that address is the most identifiable person in the whole case.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.orm import Case, CaseAddress, SuspectDecision
from app.tracer.patterns import UNITS, format_amount, short_address

# ── Signal weights ────────────────────────────────────────────────────────
# Points are relative, not probabilities. They are tuned so that a wallet
# needs more than one independent reason to reach high priority, with two
# exceptions that are high by themselves: the wallet the complaint names,
# and the exchange account the money was cashed out through.
W_REPORTED = 60
W_CASHOUT = 60
W_VICTIM_SHARE_MAX = 25   # scaled by share of all traced victim funds
W_HOLDING = 25
W_HOLDING_SHARE_MAX = 25  # unspent money is the most recoverable - scaled by how much
W_CROSS_CASE = 22
W_LAYERING = 15
W_FAN_IN = 15
W_FAN_OUT = 10
W_RAPID = 10
W_RELAY = 8
W_MIXER_USER = 15
W_BRIDGE_USER = 8
W_SAME_OWNER = 10
W_LIVE_MOVEMENT = 12
W_BEYOND_DEPTH = 4
C_COMMINGLED = -15        # caveat: funds mixed with untraced money
C_SHARED_SERVICE = -10    # caveat: collects from many unrelated senders

HIGH_PRIORITY = 60
MEDIUM_PRIORITY = 35

# Below this a wallet is noise unless something other than receiving a
# sliver of the money points at it.
MIN_SCORE = 20
MIN_MEANINGFUL_SHARE = 0.01
MAX_SUSPECTS = 30

SERVICE_TYPES = {"exchange", "mixer", "bridge"}


def exchange_name(label: str | None) -> str:
    """"Binance: Hot Wallet (BTC)" -> "Binance". The label set names the
    specific wallet; an officer serving a notice needs the institution."""
    return (label or "a known exchange").split(":")[0].strip()
DECISION_STATUSES = {"pending", "confirmed", "dismissed"}

# Plain-language roles. One per wallet: the thing an officer would call it.
ROLES = {
    "reported": ("Reported wallet",
                 "The wallet named in the complaint, which received the victim's money."),
    "cashout": ("Cash-out account",
                "A deposit address at an exchange. The exchange knows who opened this account."),
    "holding": ("Holding wallet",
                "Received victim funds and has not sent them on - they may still be recoverable."),
    "collector": ("Collection wallet",
                  "Gathers money from several wallets - often where proceeds are pooled before cash-out."),
    "distributor": ("Distribution wallet",
                    "Splits money across many wallets to fragment the trail."),
    "relay": ("Layering relay",
              "Passes money straight through to put distance between the victim and the cash-out."),
    "mixer_user": ("Mixer user",
                   "Sent funds into a mixing service to break the on-chain trail."),
    "untraced": ("Trail continues",
                 "Received victim funds at the edge of the trace; where they went next was not followed."),
    "recipient": ("Recipient",
                  "Received part of the victim's money."),
}


def _tx(edge: dict) -> dict:
    return {"tx_hash": edge["tx_hash"], "value": edge["value"],
            "timestamp": edge.get("timestamp"), "tainted_value": edge.get("tainted_value")}


class _Graph:
    def __init__(self, case: Case):
        graph = case.graph or {}
        self.chain = case.chain
        self.unit = UNITS.get(case.chain, "")
        self.hop_limit = case.hop_limit
        self.nodes: dict[str, dict] = {n["id"]: n for n in graph.get("nodes") or []}
        self.edges: list[dict] = graph.get("edges") or []
        self.out_edges: dict[str, list[dict]] = defaultdict(list)
        self.in_edges: dict[str, list[dict]] = defaultdict(list)
        for edge in self.edges:
            self.out_edges[edge["source"]].append(edge)
            self.in_edges[edge["target"]].append(edge)
        self.by_address = {n["address"]: uid for uid, n in self.nodes.items()}
        self.root = next((uid for uid, n in self.nodes.items() if n.get("hop") == 0), None)
        # Everything that left the reported wallet is the victim's money by
        # definition, so its total outflow is the denominator every share
        # below is measured against.
        self.victim_total = sum(e["value"] for e in self.out_edges.get(self.root, []))

    def amount(self, value: float) -> str:
        return format_amount(value, self.chain)

    def received(self, uid: str) -> float:
        return sum(e["value"] for e in self.in_edges.get(uid, []))

    def sent(self, uid: str) -> float:
        return sum(e["value"] for e in self.out_edges.get(uid, []))

    def victim_funds(self, uid: str) -> float:
        if uid == self.root:
            return self.victim_total
        return float(self.nodes[uid].get("tainted_value") or 0.0)

    def is_holding(self, uid: str) -> bool:
        """Received victim money, was read, and sent nothing on.

        Only wallets inside the hop limit qualify: those at the limit were
        never read, so "sent nothing" would be a claim about a wallet nobody
        looked at.
        """
        node = self.nodes[uid]
        return (
            node.get("node_type") not in SERVICE_TYPES
            and node.get("hop", 0) < self.hop_limit
            and not self.out_edges.get(uid)
            and (uid == self.root or self.victim_funds(uid) > 0)
        )

    def is_beyond_depth(self, uid: str) -> bool:
        node = self.nodes[uid]
        return (node.get("node_type") not in SERVICE_TYPES
                and node.get("hop", 0) >= self.hop_limit
                and not self.out_edges.get(uid))


def _pattern_index(patterns: list[dict]) -> dict[str, list[dict]]:
    """address -> the detector findings that name it."""
    index: dict[str, list[dict]] = defaultdict(list)
    for pattern in patterns or []:
        for address in pattern.get("addresses") or []:
            index[address].append(pattern)
    return index


def _linked_cases(db: Session, case: Case, addresses: list[str]) -> dict[str, list[dict]]:
    """Other complaints whose traces pass through each address.

    Collapsed to one entry per complaint: the same wallet re-traced at a
    deeper hop limit is one complaint, not corroboration from a second victim.
    """
    if not addresses:
        return {}
    rows = (
        db.query(CaseAddress.address, Case.id, Case.complaint_ref, Case.reported_address,
                 Case.created_by)
        .join(Case, Case.id == CaseAddress.case_id)
        .filter(CaseAddress.chain == case.chain,
                CaseAddress.address.in_(addresses),
                CaseAddress.case_id != case.id)
        .all()
    )
    linked: dict[str, dict[tuple, dict]] = defaultdict(dict)
    for address, other_id, ref, reported, filer in rows:
        # The complaint behind this case row is the same one as ours if it
        # names the same wallet under the same reference - a re-trace.
        if reported == case.reported_address and (ref or "") == (case.complaint_ref or ""):
            continue
        identity = (reported, ref or other_id, filer or "")
        linked[address].setdefault(identity, {"case_id": other_id, "complaint_ref": ref,
                                              "reported_address": reported})
    return {address: list(v.values()) for address, v in linked.items()}


def _score_wallet(g: _Graph, uid: str, findings: list[dict], linked: list[dict],
                   same_owner: list[str]) -> dict:
    node = g.nodes[uid]
    address = node["address"]
    node_type = node.get("node_type")
    reasons: list[dict] = []

    def signal(code: str, weight: int, text: str, transactions: list[dict] | None = None,
               kind: str = "signal") -> None:
        reasons.append({"code": code, "weight": weight, "text": text, "kind": kind,
                        "transactions": (transactions or [])[:6]})

    incoming = sorted(g.in_edges.get(uid, []), key=lambda e: e["value"], reverse=True)
    outgoing = sorted(g.out_edges.get(uid, []), key=lambda e: e["value"], reverse=True)
    victim_funds = g.victim_funds(uid)
    share = (victim_funds / g.victim_total) if g.victim_total > 0 else 0.0
    patterns = {p["pattern"]: p for p in findings}

    # Where the money is.
    if uid == g.root:
        signal("reported", W_REPORTED,
               "Named in the complaint as the wallet that received the victim's money"
               + (f", and sent {g.amount(g.victim_total)} onward in "
                  f"{len(outgoing)} transfer{'s' if len(outgoing) != 1 else ''}."
                  if outgoing else "."),
               [_tx(e) for e in outgoing])
    elif node_type == "exchange":
        name = exchange_name(node.get("label_name"))
        signal("cashout", W_CASHOUT + round(W_VICTIM_SHARE_MAX * min(1.0, share / 0.5)),
               f"Received {g.amount(g.received(uid))}"
               + (f" ({share * 100:.0f}% of the victim's money)" if share >= MIN_MEANINGFUL_SHARE else "")
               + f" into a deposit address at {name}. The exchange holds the KYC identity of "
                 f"whoever controls this account.",
               [_tx(e) for e in incoming])

    if uid != g.root and node_type != "exchange" and share > 0:
        points = round(W_VICTIM_SHARE_MAX * min(1.0, share / 0.5))  # half of all funds = full marks
        if share >= MIN_MEANINGFUL_SHARE and points > 0:
            signal("victim_funds", points,
                   f"Received {g.amount(victim_funds)} of the victim's money - "
                   f"{share * 100:.0f}% of everything traced.",
                   [_tx(e) for e in incoming])

    if g.is_holding(uid) and (uid == g.root or share >= MIN_MEANINGFUL_SHARE):
        # Scaled by the share held: a wallet sitting on a quarter of the
        # victim's money is the most urgent freeze target in the case, and
        # one holding a few satoshis of change is not.
        holding_points = W_HOLDING + round(W_HOLDING_SHARE_MAX * min(1.0, share / 0.2))
        if uid == g.root:
            signal("holding", W_HOLDING + W_HOLDING_SHARE_MAX,
                   "Has not sent the funds anywhere - they may still be in this wallet "
                   "and recoverable with a freeze request.")
        else:
            signal("holding", holding_points,
                   f"Has not moved the {g.amount(victim_funds)} it received. "
                   f"The money may still be here and recoverable with a freeze request.")
    elif g.is_beyond_depth(uid) and victim_funds > 0:
        signal("beyond_depth", W_BEYOND_DEPTH,
               f"Sits at the {g.hop_limit}-hop limit of this trace; where its funds went "
               f"next was not followed.")

    # How it moved the money.
    if "peel_chain" in patterns:
        length = len(patterns["peel_chain"].get("addresses") or [])
        signal("layering", W_LAYERING,
               f"One link in a chain of {length} wallets that each passed the money straight "
               f"on - a layering technique used to distance funds from their source.",
               [_tx(e) for e in outgoing])
    elif "pass_through" in patterns:
        received = g.received(uid)
        ratio = (g.sent(uid) / received * 100) if received else 0
        signal("relay", W_RELAY,
               f"Forwarded {ratio:.0f}% of what it received and kept almost nothing - "
               f"it behaves as a relay, not a destination.",
               [_tx(e) for e in outgoing])
    if "rapid_movement" in patterns and incoming and outgoing:
        arrived = min(e["timestamp"] for e in incoming)
        quick = [e for e in outgoing if 0 < e["timestamp"] - arrived]
        if quick:
            delay = min(e["timestamp"] - arrived for e in quick)
            when = f"{delay // 60} min" if delay >= 60 else f"{delay} sec"
            signal("rapid", W_RAPID,
                   f"Moved the money on within {when} of receiving it - typical of a "
                   f"wallet run by a script or used only to pass funds through.",
                   [_tx(e) for e in quick])
    if "fan_in" in patterns:
        senders = len({e["source"] for e in incoming})
        signal("collector", W_FAN_IN,
               f"Collected money from {senders} separate wallets in this trace - a pooling "
               f"point where split funds come back together.",
               [_tx(e) for e in incoming])
    if "fan_out" in patterns:
        recipients = len({e["target"] for e in outgoing})
        signal("distributor", W_FAN_OUT,
               f"Split {g.amount(g.sent(uid))} across {recipients} different wallets to "
               f"fragment the trail.",
               [_tx(e) for e in outgoing])

    mixer_edges = [e for e in outgoing if g.nodes.get(e["target"], {}).get("node_type") == "mixer"]
    if mixer_edges:
        name = g.nodes[mixer_edges[0]["target"]].get("label_name") or "a mixer"
        signal("mixer_user", W_MIXER_USER,
               f"Sent {g.amount(sum(e['value'] for e in mixer_edges))} into {name}, "
               f"deliberately breaking the on-chain trail.",
               [_tx(e) for e in mixer_edges])
    bridge_edges = [e for e in outgoing if g.nodes.get(e["target"], {}).get("node_type") == "bridge"]
    if bridge_edges:
        signal("bridge_user", W_BRIDGE_USER,
               f"Moved {g.amount(sum(e['value'] for e in bridge_edges))} through a cross-chain "
               f"bridge, taking funds onto another blockchain.",
               [_tx(e) for e in bridge_edges])

    live_out = [e for e in outgoing if e.get("detected_live")]
    if live_out:
        signal("live_movement", W_LIVE_MOVEMENT,
               f"Moved {g.amount(sum(e['value'] for e in live_out))} after the complaint was "
               f"traced - this wallet is still active.",
               [_tx(e) for e in live_out])

    # Who else is involved.
    if linked and node_type != "exchange":
        # A complaint with no reference number still has to be nameable - an
        # officer cannot follow up on "unreferenced case", but they can open
        # the case id.
        refs = ", ".join(c["complaint_ref"] or f"case {c['case_id'][:8]}" for c in linked[:3])
        signal("cross_case", W_CROSS_CASE,
               f"Also appears in {len(linked)} other complaint{'s' if len(linked) != 1 else ''} "
               f"({refs}{'…' if len(linked) > 3 else ''}) - separate victims' money meets here.")
    if same_owner:
        signal("same_owner", W_SAME_OWNER,
               f"Spent together with {len(same_owner)} other wallet"
               f"{'s' if len(same_owner) != 1 else ''} in one transaction, which proves a single "
               f"person holds the keys to all of them.")

    # What weakens it.
    if "commingling" in patterns:
        signal("commingled", C_COMMINGLED,
               f"Moved {g.amount(g.sent(uid))} while receiving only {g.amount(g.received(uid))} "
               f"from this trace - most of its money comes from elsewhere, so it may be a "
               f"shared or custodial wallet rather than the fraudster's own.",
               kind="caveat")
    if node_type != "exchange" and len({e["source"] for e in incoming}) >= 15:
        signal("shared_service", C_SHARED_SERVICE,
               "Receives from a very large number of wallets, which is how an unlabelled "
               "service behaves. Confirm it is not a payment processor before relying on it.",
               kind="caveat")

    score = max(0, min(100, sum(r["weight"] for r in reasons)))
    role = _role(g, uid, patterns, bool(mixer_edges))
    institution = exchange_name(node.get("label_name")) if node_type == "exchange" else None

    return {
        "id": uid,
        "address": address,
        "chain": g.chain,
        "hop": node.get("hop", 0),
        "node_type": node_type,
        "label_name": node.get("label_name"),
        "score": score,
        "priority": ("high" if score >= HIGH_PRIORITY
                     else "medium" if score >= MEDIUM_PRIORITY else "low"),
        "role": role,
        "role_title": ROLES[role][0],
        "role_description": ROLES[role][1],
        "victim_funds": round(victim_funds, 8),
        "victim_share": round(min(1.0, share if uid != g.root else 1.0), 4),
        "received": round(g.received(uid), 8),
        "sent": round(g.sent(uid), 8),
        "unit": g.unit,
        "exchange_name": institution,
        "linked_cases": linked,
        "same_owner_as": same_owner,
        "detected_live": bool(node.get("detected_live") or live_out),
        "reasons": sorted(reasons, key=lambda r: (r["kind"] == "caveat", -r["weight"])),
        "recommended_action": _action(g, uid, role, institution, linked),
        "first_activity": min((e["timestamp"] for e in incoming + outgoing
                               if e.get("timestamp")), default=None),
        "last_activity": max((e["timestamp"] for e in incoming + outgoing
                              if e.get("timestamp")), default=None),
    }


def _role(g: _Graph, uid: str, patterns: dict, used_mixer: bool) -> str:
    node = g.nodes[uid]
    if uid == g.root:
        return "reported"
    if node.get("node_type") == "exchange":
        return "cashout"
    if used_mixer:
        return "mixer_user"
    if g.is_holding(uid):
        return "holding"
    if "fan_in" in patterns:
        return "collector"
    if "fan_out" in patterns:
        return "distributor"
    if {"peel_chain", "pass_through", "rapid_movement"} & set(patterns):
        return "relay"
    if g.is_beyond_depth(uid):
        return "untraced"
    return "recipient"


def _action(g: _Graph, uid: str, role: str, institution: str | None,
            linked: list[dict]) -> str:
    actions = {
        "reported": ("Include in every notice. Request KYC from any exchange that funded or "
                     "received from this wallet."),
        "cashout": (f"Serve a Section 94 BNSS notice on {institution or 'the exchange'} for the "
                    f"account holder's KYC, login IPs and linked bank accounts, and request an "
                    f"immediate freeze."),
        "holding": ("Funds appear unspent. Prioritise a freeze or preservation request and keep "
                    "this wallet under live watch."),
        "collector": ("Treat as a likely operator wallet. Trace its other incoming transfers for "
                      "further victims."),
        "distributor": "List in preservation requests and follow each onward branch.",
        "relay": ("List in preservation requests. Relays rarely hold balances, so follow the "
                  "onward transfers rather than seeking a freeze here."),
        "mixer_user": ("The trail breaks at the mixer. Focus on how this wallet was funded and "
                       "any exchange it used before mixing."),
        "untraced": "Re-run the trace with a deeper hop limit to follow these funds.",
        "recipient": "Review the transfer and list in preservation requests if confirmed.",
    }
    text = actions[role]
    if linked and role != "cashout":
        text += f" Coordinate with the officers on the {len(linked)} linked complaint(s)."
    return text


def build_suspects(db: Session, case: Case) -> dict:
    """Rank the wallets in a case and summarise the case in plain language."""
    decisions = {
        d.address: d for d in
        db.query(SuspectDecision).filter(SuspectDecision.case_id == case.id).all()
    }

    if case.status != "complete" or not case.graph or not (case.graph.get("nodes")):
        return {"ready": False, "summary": None, "suspects": [],
                "reason": ("The trace has not finished yet." if case.status in ("queued", "tracing")
                           else "This case has no traced wallets to assess.")}

    g = _Graph(case)
    findings_by_address = _pattern_index(case.patterns or [])
    candidates = [uid for uid, n in g.nodes.items() if n.get("node_type") not in ("mixer", "bridge")]
    linked = _linked_cases(db, case, [g.nodes[u]["address"] for u in candidates])

    owner_groups: dict[str, set[str]] = defaultdict(set)
    for cluster in case.clusters or []:
        if cluster.get("type") != "common_input":
            continue
        members = set(cluster.get("addresses") or [])
        for address in members:
            owner_groups[address] |= members - {address}

    scored = []
    for uid in candidates:
        address = g.nodes[uid]["address"]
        suspect = _score_wallet(
            g, uid, findings_by_address.get(address, []), linked.get(address, []),
            sorted(a for a in owner_groups.get(address, set()) if a in g.by_address),
        )
        decision = decisions.get(address)
        worth_listing = (
            suspect["score"] >= MIN_SCORE
            or suspect["role"] in ("reported", "cashout")
            or (suspect["role"] == "holding" and suspect["victim_share"] >= MIN_MEANINGFUL_SHARE)
        )
        # A wallet an officer has already ruled on always stays visible -
        # it vanishing because the ranking shifted would silently drop a
        # confirmed suspect from the report.
        if not worth_listing and decision is None:
            continue
        suspect["decision"] = _decision_dict(decision)
        scored.append(suspect)

    scored.sort(key=lambda s: (-s["score"], -s["victim_funds"], s["hop"]))
    kept = [s for s in scored if s["decision"]["status"] != "pending"]
    ranked = [s for s in scored if s["decision"]["status"] == "pending"][:MAX_SUSPECTS]
    suspects = sorted(kept + ranked, key=lambda s: (-s["score"], -s["victim_funds"], s["hop"]))
    for rank, suspect in enumerate(suspects, start=1):
        suspect["rank"] = rank

    return {"ready": True, "summary": _summary(g, case, suspects), "suspects": suspects,
            "reason": None}


def _decision_dict(decision: SuspectDecision | None) -> dict:
    if decision is None:
        return {"status": "pending", "note": None, "decided_by": None, "decided_at": None}
    at = decision.decided_at
    if at is not None and at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return {"status": decision.status, "note": decision.note,
            "decided_by": decision.decided_by, "decided_at": at.isoformat() if at else None}


def _summary(g: _Graph, case: Case, suspects: list[dict]) -> dict:
    """The case in a paragraph, four numbers and a to-do list."""
    exchange_uids = [u for u, n in g.nodes.items() if n.get("node_type") == "exchange"]
    to_exchanges = sum(g.victim_funds(u) for u in exchange_uids)
    exchange_names = sorted({exchange_name(g.nodes[u].get("label_name")) for u in exchange_uids})

    # Wallets holding a meaningful share. Six wallets each keeping a few
    # satoshis of change are not six freeze targets, and counting them
    # would bury the one that is.
    holding = [u for u in g.nodes if g.is_holding(u) and (
        u == g.root or g.victim_total <= 0
        or g.victim_funds(u) / g.victim_total >= MIN_MEANINGFUL_SHARE)]
    still_held = sum(g.victim_funds(u) for u in holding)
    beyond = [u for u in g.nodes if g.is_beyond_depth(u)]
    beyond_value = sum(g.victim_funds(u) for u in beyond)
    mixer_uids = [u for u, n in g.nodes.items() if n.get("node_type") == "mixer"]
    to_mixers = sum(g.victim_funds(u) for u in mixer_uids)
    bridge_uids = [u for u, n in g.nodes.items() if n.get("node_type") == "bridge"]
    to_bridges = sum(g.victim_funds(u) for u in bridge_uids)

    total = g.victim_total
    pct = (lambda v: f" ({v / total * 100:.0f}%)" if total > 0 else "")
    root_out = len(g.out_edges.get(g.root, []))
    wallets = len([u for u in g.nodes if u != g.root])

    sentences: list[str] = []
    if total <= 0:
        sentences.append("The reported wallet has not sent any funds onward, so the money "
                         "may still be in it.")
    else:
        sentences.append(
            f"{g.amount(total)} left the reported wallet in {root_out} "
            f"transfer{'s' if root_out != 1 else ''} and spread across {wallets} "
            f"wallet{'s' if wallets != 1 else ''}.")
        if to_exchanges > 0:
            sentences.append(
                f"{g.amount(to_exchanges)}{pct(to_exchanges)} reached "
                f"{_join(exchange_names)}, where the account holder can be identified through a "
                f"legal request.")
        if still_held > 0 and holding != [g.root]:
            held_wallets = [u for u in holding if u != g.root]
            sentences.append(
                f"{g.amount(still_held)}{pct(still_held)} has not moved from "
                f"{len(held_wallets)} wallet{'s' if len(held_wallets) != 1 else ''} and may still "
                f"be recoverable.")
        if to_mixers > 0:
            sentences.append(f"{g.amount(to_mixers)}{pct(to_mixers)} went into a mixer, where the "
                             f"trail breaks.")
        if to_bridges > 0:
            sentences.append(f"{g.amount(to_bridges)}{pct(to_bridges)} crossed to another "
                             f"blockchain through a bridge.")
        if beyond_value > 0:
            sentences.append(f"{g.amount(beyond_value)}{pct(beyond_value)} moved beyond the "
                             f"{g.hop_limit} hops traced.")

    counts = {"total": len(suspects),
              "high": sum(s["priority"] == "high" for s in suspects),
              "medium": sum(s["priority"] == "medium" for s in suspects),
              "low": sum(s["priority"] == "low" for s in suspects),
              "confirmed": sum(s["decision"]["status"] == "confirmed" for s in suspects),
              "dismissed": sum(s["decision"]["status"] == "dismissed" for s in suspects)}
    counts["pending"] = counts["total"] - counts["confirmed"] - counts["dismissed"]
    if suspects:
        sentences.append(
            f"{counts['total']} wallet{'s were' if counts['total'] != 1 else ' was'} identified as "
            f"suspect{'s' if counts['total'] != 1 else ''}, {counts['high']} of "
            f"{'them' if counts['total'] != 1 else 'it'} high priority.")

    linked_ids = {c["case_id"] for s in suspects for c in s["linked_cases"]}

    steps: list[dict] = []
    if exchange_uids:
        steps.append({
            "key": "legal_notice", "priority": "high", "action": "legal_notice",
            "title": f"Send a preservation and KYC notice to {_join(exchange_names)}",
            "detail": (f"{g.amount(to_exchanges)} of victim funds reached "
                       f"{'this exchange' if len(exchange_names) == 1 else 'these exchanges'}. "
                       f"Ask for the account holder's identity and a freeze before it is withdrawn."),
        })
    held_wallets = [u for u in holding if u != g.root] if total > 0 else holding
    if held_wallets and still_held > 0 or (total <= 0 and holding):
        steps.append({
            "key": "freeze", "priority": "high", "action": "filter_holding",
            "title": f"Act on {len(held_wallets)} wallet{'s' if len(held_wallets) != 1 else ''} "
                     f"still holding funds",
            "detail": ("These wallets have not moved the money yet. Keep them under live watch "
                       "and include them in any freeze request."),
        })
    pending_high = [s for s in suspects if s["priority"] == "high"
                    and s["decision"]["status"] == "pending"]
    if pending_high:
        steps.append({
            "key": "review", "priority": "medium", "action": "review_suspects",
            "title": f"Review {len(pending_high)} high-priority suspect"
                     f"{'s' if len(pending_high) != 1 else ''}",
            "detail": "Confirm or dismiss each one. Only confirmed suspects go into the report.",
        })
    if counts["confirmed"]:
        steps.append({
            "key": "report", "priority": "medium", "action": "suspect_report",
            "title": f"Download the suspect report ({counts['confirmed']} confirmed)",
            "detail": "A signed-off list of confirmed suspects with the evidence behind each.",
        })
    if linked_ids:
        steps.append({
            "key": "linked", "priority": "medium", "action": "linked_cases",
            "title": f"Coordinate with {len(linked_ids)} linked complaint"
                     f"{'s' if len(linked_ids) != 1 else ''}",
            "detail": "Other victims' money passes through the same wallets. One operation may be "
                      "behind all of them.",
        })
    if beyond_value > 0:
        steps.append({
            "key": "deeper", "priority": "low", "action": None,
            "title": "Trace deeper to follow the remaining funds",
            "detail": (f"{g.amount(beyond_value)} was still moving when the {g.hop_limit}-hop limit "
                       f"was reached. Re-submit the wallet with a higher hop limit."),
        })
    if mixer_uids:
        steps.append({
            "key": "mixer", "priority": "low", "action": None,
            "title": "Work around the mixer",
            "detail": ("On-chain tracing cannot follow funds through a mixer. Focus on how the "
                       "wallets before it were funded, and any exchange they used."),
        })

    return {
        "headline": " ".join(sentences),
        "unit": g.unit,
        "chain": g.chain,
        "victim_total": round(total, 8),
        "to_exchanges": round(to_exchanges, 8),
        "exchange_names": exchange_names,
        "still_held": round(still_held, 8),
        "holding_wallets": len(held_wallets),
        "beyond_depth": round(beyond_value, 8),
        "to_mixers": round(to_mixers, 8),
        "to_bridges": round(to_bridges, 8),
        "counts": counts,
        "linked_case_count": len(linked_ids),
        "next_steps": steps,
    }


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def record_decision(db: Session, case: Case, address: str, status: str, note: str | None,
                     username: str) -> SuspectDecision:
    """Store an officer's ruling on a suspect. The caller writes the audit entry."""
    decision = (
        db.query(SuspectDecision)
        .filter(SuspectDecision.case_id == case.id, SuspectDecision.address == address)
        .first()
    )
    if decision is None:
        decision = SuspectDecision(case_id=case.id, chain=case.chain, address=address)
        db.add(decision)
    decision.status = status
    decision.note = (note or "").strip() or None
    decision.decided_by = username
    decision.decided_at = datetime.now(timezone.utc)
    db.flush()
    return decision
