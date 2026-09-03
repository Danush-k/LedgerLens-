"""Modular pattern detectors that run over a completed trace.

Where the BFS walk answers *where did the money go*, this module answers
*what shape did the movement have* - the part an investigator actually
reasons about.

Each detector returns structured evidence instead of a bare flag string:

    {
      "pattern": "peel_chain",
      "severity": "high",
      "title": "Peel chain / layering",
      "evidence": "bc1qA… forwarded 94% of what it received, repeated "
                  "across 4 consecutive hops",
      "transactions": ["abc123…", "def456…"],
      "addresses": ["bc1qA…", "bc1qB…"],
      "flag": "peel_chain",
    }

Two rules this module follows deliberately:

1. **Evidence over assertion.** A detector reports what it observed and
   which transactions support it - never "this wallet is a launderer".
   The investigator draws the conclusion, and can disagree with ours.
2. **Fact and inference stay separate.** Amounts, timestamps and tx
   hashes are blockchain facts read off-chain. The pattern name is *our
   inference* about the shape those facts make. Only the former is
   evidence; the latter is an investigative lead.

Every threshold is a module constant so it can be tuned per deployment
rather than being buried in the logic.
"""

from collections import defaultdict

# --- Detector thresholds (tune per deployment) -----------------------------
FAN_OUT_MIN_RECIPIENTS = 6      # one address paying out to this many wallets
FAN_IN_MIN_SENDERS = 5          # this many wallets converging on one address
RAPID_MOVEMENT_WINDOW_S = 600   # forwarded within 10 minutes of arriving
PEEL_FORWARD_RATIO = 0.80       # forwards >=80% of what it received
# Counted in *relay wallets*, not transfers. A wallet only qualifies once
# it has both received and forwarded, so a run of 3 relays means at least
# 4 transfers (origin → R1 → R2 → R3 → destination). Deliberately
# conservative: isolated relay hops are common and mean little.
PEEL_MIN_CHAIN_LENGTH = 3
PASS_THROUGH_RATIO = 0.90       # keeps <=10% - effectively a relay wallet
FAST_CASHOUT_MAX_HOPS = 2       # reached an exchange this quickly

# Upper bound on a meaningful forward ratio.
#
# A forward-only trace sees a wallet's outflows in full (we fetch its whole
# history) but only the inflows that came from traced ancestors. So a wallet
# funded mostly from outside our graph can compute a ratio far above 1.0 -
# that is not a relay, it is commingling, and it means something different.
# Above this bound the pass-through/peel signals are suppressed and the
# commingling detector reports it instead.
MAX_MEANINGFUL_FORWARD_RATIO = 1.10
COMMINGLING_MIN_RATIO = 2.0     # outflow >=2x traced inflow: other funding sources


def _fmt(value: float) -> str:
    """Trim trailing zeros so 0.4800 reads as 0.48."""
    return f"{value:.8f}".rstrip("0").rstrip(".") or "0"


def _short(address: str) -> str:
    return address if len(address) <= 16 else f"{address[:10]}…{address[-4:]}"


class _Flow:
    """Value in/out per node, plus the edges behind each side.

    Built once and shared by every detector so a trace is only walked
    once regardless of how many detectors are registered.
    """

    def __init__(self, nodes: dict[str, dict], edges: list[dict]):
        self.nodes = nodes
        self.edges = edges
        self.out_edges: dict[str, list[dict]] = defaultdict(list)
        self.in_edges: dict[str, list[dict]] = defaultdict(list)
        for edge in edges:
            self.out_edges[edge["source"]].append(edge)
            self.in_edges[edge["target"]].append(edge)

    def address(self, uid: str) -> str:
        node = self.nodes.get(uid)
        return node["address"] if node else uid

    def value_in(self, uid: str) -> float:
        return sum(e["value"] for e in self.in_edges.get(uid, []))

    def value_out(self, uid: str) -> float:
        return sum(e["value"] for e in self.out_edges.get(uid, []))

    def arrived_at(self, uid: str) -> int | None:
        """Timestamp funds first landed on this address in our trace."""
        incoming = self.in_edges.get(uid, [])
        return min((e["timestamp"] for e in incoming), default=None)

    def forward_ratio(self, uid: str) -> float | None:
        """Share of received funds sent onward. None when nothing arrived
        here inside the traced window (e.g. the reported wallet itself)."""
        received = self.value_in(uid)
        if received <= 0:
            return None
        return self.value_out(uid) / received


# --- Individual detectors --------------------------------------------------
# Each takes the shared _Flow (plus trace metadata where relevant) and
# returns zero or more evidence dicts.


def detect_fan_out(flow: _Flow) -> list[dict]:
    """One wallet dispersing funds across many recipients.

    Typical of a scammer splitting proceeds to complicate tracing - but
    also of an ordinary exchange or payment processor paying out, which
    is why the label check matters more than the raw count.
    """
    found = []
    for uid, out in flow.out_edges.items():
        recipients = {e["target"] for e in out}
        if len(recipients) < FAN_OUT_MIN_RECIPIENTS:
            continue
        total = sum(e["value"] for e in out)
        found.append({
            "pattern": "fan_out",
            "severity": "medium",
            "title": "Fan-out / dispersal",
            "evidence": (
                f"{_short(flow.address(uid))} sent funds to {len(recipients)} "
                f"different wallets ({_fmt(total)} total) - a splitting pattern "
                f"that fragments the trail across many branches."
            ),
            "transactions": [e["tx_hash"] for e in out[:10]],
            "addresses": [flow.address(uid)],
            "flag": "high_fan_out",
        })
    return found


def detect_fan_in(flow: _Flow) -> list[dict]:
    """Many wallets converging on one - a collection/consolidation point.

    Often where a scam operation gathers proceeds before cashing out,
    though exchange deposit addresses look identical by shape.
    """
    found = []
    for uid, incoming in flow.in_edges.items():
        senders = {e["source"] for e in incoming}
        if len(senders) < FAN_IN_MIN_SENDERS:
            continue
        total = sum(e["value"] for e in incoming)
        node = flow.nodes.get(uid, {})
        found.append({
            "pattern": "fan_in",
            "severity": "medium",
            "title": "Fan-in / consolidation",
            "evidence": (
                f"{len(senders)} wallets sent a combined {_fmt(total)} into "
                f"{_short(flow.address(uid))}"
                + (f" ({node['label_name']})" if node.get("label_name") else "")
                + " - a consolidation point where separate branches rejoin."
            ),
            "transactions": [e["tx_hash"] for e in incoming[:10]],
            "addresses": [flow.address(uid)],
            "flag": "fan_in",
        })
    return found


def detect_rapid_movement(flow: _Flow) -> list[dict]:
    """Funds forwarded almost immediately after arriving.

    A wallet that holds funds for seconds is behaving like a relay, not
    like someone's savings. Slow movement proves nothing either way, so
    this only fires in one direction.
    """
    found = []
    for uid, out in flow.out_edges.items():
        arrived = flow.arrived_at(uid)
        if arrived is None:
            continue
        quick = [e for e in out if 0 < e["timestamp"] - arrived < RAPID_MOVEMENT_WINDOW_S]
        if not quick:
            continue
        fastest = min(e["timestamp"] - arrived for e in quick)
        found.append({
            "pattern": "rapid_movement",
            "severity": "medium",
            "title": "Rapid forwarding",
            "evidence": (
                f"{_short(flow.address(uid))} forwarded funds {fastest // 60}m "
                f"{fastest % 60}s after receiving them "
                f"({len(quick)} transaction{'s' if len(quick) > 1 else ''}) - "
                f"consistent with an automated or throwaway relay wallet."
            ),
            "transactions": [e["tx_hash"] for e in quick[:10]],
            "addresses": [flow.address(uid)],
            "flag": "rapid_layering",
        })
    return found


def detect_pass_through(flow: _Flow) -> list[dict]:
    """A wallet that keeps almost nothing - a pure relay hop."""
    found = []
    for uid in flow.out_edges:
        ratio = flow.forward_ratio(uid)
        if ratio is None or not (PASS_THROUGH_RATIO <= ratio <= MAX_MEANINGFUL_FORWARD_RATIO):
            continue  # above the bound the wallet has other funding - see commingling
        node = flow.nodes.get(uid, {})
        if node.get("node_type") in ("exchange", "mixer", "bridge"):
            continue  # services forward by design - not a signal
        found.append({
            "pattern": "pass_through",
            "severity": "low",
            "title": "Pass-through wallet",
            "evidence": (
                f"{_short(flow.address(uid))} forwarded {ratio * 100:.0f}% of the "
                f"{_fmt(flow.value_in(uid))} it received, retaining almost nothing - "
                f"it holds no balance of its own, only relays."
            ),
            "transactions": [e["tx_hash"] for e in flow.out_edges[uid][:5]],
            "addresses": [flow.address(uid)],
            "flag": "pass_through",
        })
    return found


def detect_commingling(flow: _Flow) -> list[dict]:
    """Wallets moving far more than the traced funds that reached them.

    The extra value came from sources outside this trace, so the traced
    funds are mixed with unrelated money here. That matters twice over:
    it weakens any claim that downstream wallets hold *the victim's*
    funds, and it often marks a shared service (an exchange's internal
    wallet, a payment processor, a custodial hot wallet) rather than a
    wallet the fraudster controls.
    """
    found = []
    for uid in flow.out_edges:
        ratio = flow.forward_ratio(uid)
        if ratio is None or ratio < COMMINGLING_MIN_RATIO:
            continue
        node = flow.nodes.get(uid, {})
        if node.get("node_type") in ("exchange", "mixer", "bridge"):
            continue  # expected behaviour for a known service
        received, sent = flow.value_in(uid), flow.value_out(uid)
        found.append({
            "pattern": "commingling",
            "severity": "low",
            "title": "Commingled with untraced funds",
            "evidence": (
                f"{_short(flow.address(uid))} received {_fmt(received)} from the "
                f"traced path but moved {_fmt(sent)} in total - the difference came "
                f"from wallets outside this trace, so traced funds are mixed with "
                f"unrelated money here. Downstream amounts cannot be attributed to "
                f"the reported wallet alone."
            ),
            "transactions": [e["tx_hash"] for e in flow.out_edges[uid][:5]],
            "addresses": [flow.address(uid)],
            "flag": "commingling",
        })
    return found


def detect_peel_chain(flow: _Flow) -> list[dict]:
    """A run of consecutive hops each forwarding most of what it received.

    This is the classic layering shape: funds hop wallet to wallet, a
    little shaved off each time, putting distance between the origin and
    the cash-out point. One relay hop is unremarkable; a *sequence* of
    them is the signal.
    """
    def is_peel(uid: str) -> bool:
        ratio = flow.forward_ratio(uid)
        node = flow.nodes.get(uid, {})
        return (
            ratio is not None
            and PEEL_FORWARD_RATIO <= ratio <= MAX_MEANINGFUL_FORWARD_RATIO
            and node.get("node_type") not in ("exchange", "mixer", "bridge")
        )

    # Walk forward from each peel-like node along its largest outgoing
    # edge, collecting the longest consecutive run.
    best: list[str] = []
    for start in flow.out_edges:
        if not is_peel(start):
            continue
        chain, seen, current = [start], {start}, start
        while True:
            out = flow.out_edges.get(current, [])
            if not out:
                break
            nxt = max(out, key=lambda e: e["value"])["target"]
            if nxt in seen or not is_peel(nxt):
                break
            chain.append(nxt)
            seen.add(nxt)
            current = nxt
        if len(chain) > len(best):
            best = chain

    if len(best) < PEEL_MIN_CHAIN_LENGTH:
        return []

    tx_hashes, ratios = [], []
    for uid in best:
        out = flow.out_edges.get(uid, [])
        if out:
            tx_hashes.append(max(out, key=lambda e: e["value"])["tx_hash"])
        ratio = flow.forward_ratio(uid)
        if ratio is not None:
            ratios.append(ratio)

    avg = (sum(ratios) / len(ratios) * 100) if ratios else 0
    return [{
        "pattern": "peel_chain",
        "severity": "high",
        "title": "Peel chain / layering",
        "evidence": (
            f"{len(best)} consecutive wallets each forwarded on average "
            f"{avg:.0f}% of what they received "
            f"({' → '.join(_short(flow.address(u)) for u in best)}) - a layering "
            f"pattern that puts distance between the reported wallet and the "
            f"eventual destination."
        ),
        "transactions": tx_hashes,
        "addresses": [flow.address(u) for u in best],
        "flag": "peel_chain",
    }]


def detect_service_hits(flow: _Flow) -> list[dict]:
    """Mixers and bridges encountered during the trace.

    Using a mixer is not itself proof of wrongdoing - privacy tools have
    legitimate users - but it does mean the on-chain link breaks here,
    which is a fact the investigator needs to know.
    """
    found = []
    for uid, node in flow.nodes.items():
        node_type = node.get("node_type")
        if node_type not in ("mixer", "bridge"):
            continue
        incoming = flow.in_edges.get(uid, [])
        name = node.get("label_name") or _short(node["address"])
        if node_type == "mixer":
            evidence = (
                f"Funds reached {name}, a mixing service. On-chain linkage "
                f"generally cannot be followed past this point - the trail ends "
                f"here rather than being resolved."
            )
        else:
            evidence = (
                f"Funds reached {name}, a bridge/DEX router. Value may continue "
                f"on a different chain, which this single-chain trace cannot follow."
            )
        found.append({
            "pattern": f"{node_type}_hit",
            "severity": "high" if node_type == "mixer" else "medium",
            "title": "Mixer encountered" if node_type == "mixer" else "Bridge / cross-chain hop",
            "evidence": evidence,
            "transactions": [e["tx_hash"] for e in incoming[:5]],
            "addresses": [node["address"]],
            "flag": "mixer_detected" if node_type == "mixer" else "cross_chain_bridge",
        })
    return found


def detect_exchange_deposit(flow: _Flow, nearest_exchange: dict | None) -> list[dict]:
    """Funds reaching a known exchange - the actionable outcome."""
    if not nearest_exchange:
        return []
    hops = nearest_exchange.get("hops", 99)
    uid = next(
        (u for u, n in flow.nodes.items() if n["address"] == nearest_exchange["address"]),
        None,
    )
    incoming = flow.in_edges.get(uid, []) if uid else []
    fast = hops <= FAST_CASHOUT_MAX_HOPS
    return [{
        "pattern": "exchange_deposit",
        "severity": "high" if fast else "medium",
        "title": "Exchange deposit identified",
        "evidence": (
            f"Funds reached {nearest_exchange['name']} at hop {hops}"
            + (
                " - a direct, fast cash-out with little intermediate layering."
                if fast
                else " after intermediate hops."
            )
            + " This exchange can be served a preservation/disclosure request."
        ),
        "transactions": [e["tx_hash"] for e in incoming[:5]],
        "addresses": [nearest_exchange["address"]],
        "flag": "fast_cashout" if fast else "exchange_identified",
    }]


def detect_untraced_termination(flow: _Flow, hop_limit: int,
                                 nearest_exchange: dict | None) -> list[dict]:
    """Branches that hit the hop limit without resolving.

    An honest negative result: we ran out of budget, not out of trail.
    Reporting this stops the graph from implying the money simply stopped.
    """
    dead_ends = [
        uid for uid, node in flow.nodes.items()
        if node.get("node_type") == "unresolved"
        and not flow.out_edges.get(uid)
        and flow.in_edges.get(uid)
    ]
    if not dead_ends:
        return []
    stranded = sum(flow.value_in(uid) for uid in dead_ends)
    return [{
        "pattern": "untraced_termination",
        "severity": "medium" if nearest_exchange else "high",
        "title": "Funds untraced at hop limit",
        "evidence": (
            f"{len(dead_ends)} wallet{'s' if len(dead_ends) > 1 else ''} that received "
            f"{_fmt(stranded)} in total were still unresolved when the {hop_limit}-hop "
            f"limit was reached - their onward transactions were never fetched, so the "
            f"trail continues beyond what was traced. Re-running with a higher hop limit "
            f"may resolve these branches."
        ),
        "transactions": [],
        "addresses": [flow.address(uid) for uid in dead_ends[:10]],
        "flag": "no_exchange_found" if not nearest_exchange else "partial_trace",
    }]


# --- Engine ---------------------------------------------------------------

def run_detectors(nodes: dict[str, dict], edges: list[dict],
                   nearest_exchange: dict | None, hop_limit: int) -> list[dict]:
    """Run every detector over a completed trace, most severe first."""
    flow = _Flow(nodes, edges)

    patterns: list[dict] = []
    patterns += detect_peel_chain(flow)
    patterns += detect_service_hits(flow)
    patterns += detect_exchange_deposit(flow, nearest_exchange)
    patterns += detect_fan_out(flow)
    patterns += detect_fan_in(flow)
    patterns += detect_rapid_movement(flow)
    patterns += detect_pass_through(flow)
    patterns += detect_commingling(flow)
    patterns += detect_untraced_termination(flow, hop_limit, nearest_exchange)

    order = {"high": 0, "medium": 1, "low": 2}
    patterns.sort(key=lambda p: order.get(p["severity"], 9))
    return patterns


def flags_from_patterns(patterns: list[dict]) -> set[str]:
    """Collapse structured evidence back into the flat flag strings the
    risk scorer and the existing UI badges consume."""
    return {p["flag"] for p in patterns if p.get("flag")}
