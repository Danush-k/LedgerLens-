from app.risk.rules import recommended_action, score_case


def test_score_case_combines_weighted_signals():
    flags = {"mixer_detected", "high_fan_out"}
    score, breakdown = score_case(flags, nearest_exchange=None, prior_report_count=0, rapid_layering=False)

    assert breakdown["mixer_detected"] == 35
    assert breakdown["high_fan_out"] == 15
    assert score == 50


def test_score_case_caps_at_100():
    flags = {"mixer_detected", "cross_chain_bridge", "no_exchange_found", "high_fan_out"}
    score, _ = score_case(flags, nearest_exchange=None, prior_report_count=3, rapid_layering=True)

    assert score == 100


def test_fast_cashout_bonus_only_applies_within_two_hops():
    close = {"name": "Binance", "address": "0x1", "chain": "ethereum", "hops": 2}
    far = {"name": "Binance", "address": "0x1", "chain": "ethereum", "hops": 4}

    score_close, breakdown_close = score_case(set(), close, 0, False)
    score_far, breakdown_far = score_case(set(), far, 0, False)

    assert "fast_cashout" in breakdown_close
    assert "fast_cashout" not in breakdown_far
    assert score_close == 15
    assert score_far == 0


def test_recommended_action_mentions_exchange_when_found():
    exchange = {"name": "Binance", "address": "0x1", "chain": "ethereum", "hops": 3}
    action = recommended_action(exchange, 78)
    assert "Binance" in action
    assert "hop 3" in action


def test_recommended_action_escalates_when_unresolved_and_risky():
    action = recommended_action(None, 65)
    assert "escalate" in action.lower()
