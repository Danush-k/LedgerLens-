"""Pattern detector tests.

Each test builds a small synthetic graph with a deliberate shape, then
asserts the matching detector fires with real evidence attached.
"""

from app.tracer.patterns import flags_from_patterns, run_detectors


def _node(uid: str, address: str, node_type: str = "unresolved", label: str | None = None):
    return {"id": uid, "address": address, "chain": "bitcoin",
            "node_type": node_type, "label_name": label}


def _edge(source: str, target: str, value: float, ts: int, hop: int, tx: str):
    return {"source": source, "target": target, "value": value,
            "timestamp": ts, "hop": hop, "tx_hash": tx}


def test_peel_chain_detected_across_consecutive_hops():
    """A → B → C → D → E, each relay forwarding ~95% of what it received.

    B, C and D are the relay wallets (A never received inside the trace,
    E has not forwarded), which meets the 3-relay threshold.
    """
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B", "C", "D", "E")}
    edges = [
        _edge("bitcoin:A", "bitcoin:B", 1.00, 1000, 1, "tx1"),
        _edge("bitcoin:B", "bitcoin:C", 0.95, 2000, 2, "tx2"),
        _edge("bitcoin:C", "bitcoin:D", 0.90, 3000, 3, "tx3"),
        _edge("bitcoin:D", "bitcoin:E", 0.86, 4000, 4, "tx4"),
    ]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)
    peel = [p for p in patterns if p["pattern"] == "peel_chain"]

    assert len(peel) == 1
    assert peel[0]["severity"] == "high"
    assert peel[0]["transactions"]  # evidence is attached, not just a label
    assert "peel_chain" in flags_from_patterns(patterns)


def test_two_relay_hops_stay_below_peel_threshold():
    """Guards the conservative threshold: 2 relays is not yet a chain."""
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B", "C", "D")}
    edges = [
        _edge("bitcoin:A", "bitcoin:B", 1.00, 1000, 1, "tx1"),
        _edge("bitcoin:B", "bitcoin:C", 0.95, 2000, 2, "tx2"),
        _edge("bitcoin:C", "bitcoin:D", 0.90, 3000, 3, "tx3"),
    ]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)

    assert not [p for p in patterns if p["pattern"] == "peel_chain"]


def test_single_relay_hop_is_not_a_peel_chain():
    """One pass-through wallet is unremarkable - only a sustained run counts."""
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B")}
    edges = [_edge("bitcoin:A", "bitcoin:B", 1.0, 1000, 1, "tx1")]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)

    assert not [p for p in patterns if p["pattern"] == "peel_chain"]


def test_fan_out_detected_when_one_wallet_pays_many():
    nodes = {"bitcoin:A": _node("bitcoin:A", "A")}
    edges = []
    for i in range(7):
        nodes[f"bitcoin:R{i}"] = _node(f"bitcoin:R{i}", f"R{i}")
        edges.append(_edge("bitcoin:A", f"bitcoin:R{i}", 0.1, 1000 + i, 1, f"tx{i}"))

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)
    fan_out = [p for p in patterns if p["pattern"] == "fan_out"]

    assert len(fan_out) == 1
    assert "7 different wallets" in fan_out[0]["evidence"]


def test_fan_in_detected_when_many_wallets_converge():
    nodes = {"bitcoin:COLLECTOR": _node("bitcoin:COLLECTOR", "COLLECTOR")}
    edges = []
    for i in range(6):
        nodes[f"bitcoin:S{i}"] = _node(f"bitcoin:S{i}", f"S{i}")
        edges.append(_edge(f"bitcoin:S{i}", "bitcoin:COLLECTOR", 0.2, 1000 + i, 1, f"tx{i}"))

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)

    assert [p for p in patterns if p["pattern"] == "fan_in"]


def test_rapid_movement_uses_actual_timing():
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B", "C")}
    edges = [
        _edge("bitcoin:A", "bitcoin:B", 1.0, 1_000_000, 1, "tx1"),
        # forwarded 3 minutes later
        _edge("bitcoin:B", "bitcoin:C", 0.9, 1_000_180, 2, "tx2"),
    ]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)
    rapid = [p for p in patterns if p["pattern"] == "rapid_movement"]

    assert rapid
    assert "3m 0s" in rapid[0]["evidence"]


def test_slow_movement_does_not_fire():
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B", "C")}
    edges = [
        _edge("bitcoin:A", "bitcoin:B", 1.0, 1_000_000, 1, "tx1"),
        _edge("bitcoin:B", "bitcoin:C", 0.9, 1_090_000, 2, "tx2"),  # ~25h later
    ]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)

    assert not [p for p in patterns if p["pattern"] == "rapid_movement"]


def test_mixer_hit_reports_broken_trail_without_asserting_guilt():
    nodes = {
        "bitcoin:A": _node("bitcoin:A", "A"),
        "bitcoin:M": _node("bitcoin:M", "M", node_type="mixer", label="Tornado.Cash"),
    }
    edges = [_edge("bitcoin:A", "bitcoin:M", 1.0, 1000, 1, "tx1")]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)
    mixer = [p for p in patterns if p["pattern"] == "mixer_hit"]

    assert len(mixer) == 1
    assert "Tornado.Cash" in mixer[0]["evidence"]
    # Language stays evidential - no guilt assertion
    assert "launder" not in mixer[0]["evidence"].lower()
    assert "criminal" not in mixer[0]["evidence"].lower()


def test_exchange_deposit_flags_fast_cashout_within_two_hops():
    nodes = {
        "bitcoin:A": _node("bitcoin:A", "A"),
        "bitcoin:EX": _node("bitcoin:EX", "EX", node_type="exchange", label="Binance"),
    }
    edges = [_edge("bitcoin:A", "bitcoin:EX", 1.0, 1000, 1, "tx1")]
    nearest = {"name": "Binance", "address": "EX", "chain": "bitcoin", "hops": 1}

    patterns = run_detectors(nodes, edges, nearest, hop_limit=5)
    deposit = [p for p in patterns if p["pattern"] == "exchange_deposit"]

    assert deposit
    assert deposit[0]["flag"] == "fast_cashout"


def test_untraced_termination_reports_unresolved_branches():
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B")}
    edges = [_edge("bitcoin:A", "bitcoin:B", 0.5, 1000, 1, "tx1")]

    patterns = run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5)
    untraced = [p for p in patterns if p["pattern"] == "untraced_termination"]

    assert untraced
    assert "still unresolved" in untraced[0]["evidence"]


def test_every_pattern_carries_structured_evidence():
    """Contract check: no detector may emit a bare label."""
    nodes = {f"bitcoin:{a}": _node(f"bitcoin:{a}", a) for a in ("A", "B", "C", "D")}
    edges = [
        _edge("bitcoin:A", "bitcoin:B", 1.00, 1000, 1, "tx1"),
        _edge("bitcoin:B", "bitcoin:C", 0.95, 1200, 2, "tx2"),
        _edge("bitcoin:C", "bitcoin:D", 0.90, 1400, 3, "tx3"),
    ]

    for pattern in run_detectors(nodes, edges, nearest_exchange=None, hop_limit=5):
        assert pattern["pattern"]
        assert pattern["severity"] in ("low", "medium", "high")
        assert pattern["title"]
        assert len(pattern["evidence"]) > 20  # a real sentence, not a slug
        assert "transactions" in pattern
        assert "addresses" in pattern


# ── keeping the findings list readable ────────────────────────────────────

def _relay_graph(relay_count: int):
    """A root paying N relay wallets, each forwarding nearly everything on."""
    nodes = {"btc:root": {"address": "root", "chain": "bitcoin",
                          "node_type": "reported", "hop": 0}}
    edges = []
    for i in range(relay_count):
        relay, sink = f"btc:r{i}", f"btc:s{i}"
        nodes[relay] = {"address": f"relay{i}", "chain": "bitcoin",
                        "node_type": "unresolved", "hop": 1}
        nodes[sink] = {"address": f"sink{i}", "chain": "bitcoin",
                       "node_type": "unresolved", "hop": 2}
        edges.append({"source": "btc:root", "target": relay, "value": 1.0,
                      "tx_hash": f"a{i}" * 32, "timestamp": 1_700_000_000, "hop": 1})
        edges.append({"source": relay, "target": sink, "value": 0.95,
                      "tx_hash": f"b{i}" * 32, "timestamp": 1_700_000_100, "hop": 2})
    return nodes, edges


def test_many_relay_wallets_produce_one_finding():
    """A trace of any depth produces a dozen relay wallets. A dozen
    near-identical rows saying the same thing in different hex pushes the
    findings that need a decision off the screen."""
    nodes, edges = _relay_graph(6)

    relays = [p for p in run_detectors(nodes, edges, None, 5)
              if p["pattern"] == "pass_through"]

    assert len(relays) == 1
    assert len(relays[0]["addresses"]) >= 4   # every wallet still named


def test_a_single_relay_still_reads_naturally():
    nodes, edges = _relay_graph(1)

    relays = [p for p in run_detectors(nodes, edges, None, 5)
              if p["pattern"] == "pass_through"]

    assert len(relays) == 1
    assert relays[0]["title"] == "Pass-through wallet"


def test_relay_finding_keeps_its_transaction_evidence():
    """Collapsing rows must not cost the evidence - each claim still has to
    be checkable against the public ledger."""
    nodes, edges = _relay_graph(4)

    relay = next(p for p in run_detectors(nodes, edges, None, 5)
                 if p["pattern"] == "pass_through")

    assert relay["transactions"]
    assert all(len(tx) == 64 for tx in relay["transactions"])


def test_peel_chain_wallets_are_not_reported_twice():
    """A peel chain is a run of relay wallets, so every wallet in one also
    trips the pass-through detector. Reporting them again at a second
    severity states one behaviour as two pieces of evidence."""
    # A straight chain: root -> a -> b -> c, each forwarding ~95%.
    nodes = {"btc:root": {"address": "root", "chain": "bitcoin",
                          "node_type": "reported", "hop": 0}}
    edges = []
    chain = ["btc:root", "btc:a", "btc:b", "btc:c", "btc:d"]
    for i, uid in enumerate(chain[1:], start=1):
        nodes[uid] = {"address": f"addr{i}", "chain": "bitcoin",
                      "node_type": "unresolved", "hop": i}
        edges.append({"source": chain[i - 1], "target": uid,
                      "value": 1.0 * (0.95 ** (i - 1)), "tx_hash": f"c{i}" * 32,
                      "timestamp": 1_700_000_000 + i, "hop": i})

    patterns = run_detectors(nodes, edges, None, 6)
    peel = [p for p in patterns if p["pattern"] == "peel_chain"]
    relays = [p for p in patterns if p["pattern"] == "pass_through"]

    if peel:
        peel_addresses = set(peel[0]["addresses"])
        for relay in relays:
            assert not (set(relay["addresses"]) & peel_addresses)


def test_relay_prose_never_names_a_wallet_it_excluded():
    """The regression: exclusion used to filter the address list after the
    sentence was written, so the finding said "3 wallets (A, B, C)" while
    listing only one, and contradicted itself with a note about the rest."""
    nodes = {"btc:root": {"address": "root", "chain": "bitcoin",
                          "node_type": "reported", "hop": 0}}
    edges = []
    chain = ["btc:root", "btc:a", "btc:b", "btc:c", "btc:d"]
    for i, uid in enumerate(chain[1:], start=1):
        nodes[uid] = {"address": f"addr{i}", "chain": "bitcoin",
                      "node_type": "unresolved", "hop": i}
        edges.append({"source": chain[i - 1], "target": uid,
                      "value": 1.0 * (0.95 ** (i - 1)), "tx_hash": f"e{i}" * 32,
                      "timestamp": 1_700_000_000 + i, "hop": i})

    patterns = run_detectors(nodes, edges, None, 6)
    peel = {a for p in patterns if p["pattern"] == "peel_chain"
            for a in p["addresses"]}
    relays = [p for p in patterns if p["pattern"] == "pass_through"]

    for relay in relays:
        # Neither the list nor the prose may mention an excluded wallet.
        assert not (set(relay["addresses"]) & peel)
        for address in peel:
            assert address[:10] not in relay["evidence"]
        # And the stated count must match what is listed.
        assert str(len(relay["addresses"])) in relay["evidence"] or \
               len(relay["addresses"]) == 1


def test_amounts_use_readable_units():
    """Dust written in whole coins forces the reader to count decimal
    places to judge whether it matters."""
    from app.tracer.patterns import _fmt

    assert _fmt(0.00008078, "bitcoin") == "8,078 sats"
    assert _fmt(0.48, "bitcoin") == "0.48 BTC"
    assert _fmt(1.5, "ethereum") == "1.5 ETH"
    assert _fmt(500.0, "tron") == "500 USDT"
