from app.models.orm import Case
from app.risk.ml import extract_features, predict, train


def _case(risk_score, flags, hops=None, hop_limit=5, num_nodes=3, num_edges=2):
    return Case(
        id="x",
        reported_address="0x1",
        chain="ethereum",
        hop_limit=hop_limit,
        risk_score=risk_score,
        flags=flags,
        nearest_exchange={"name": "Binance", "address": "0x2", "chain": "ethereum", "hops": hops} if hops else None,
        graph={"nodes": [{}] * num_nodes, "edges": [{}] * num_edges},
    )


def test_extract_features_uses_hop_limit_plus_one_when_no_exchange_found():
    case = _case(15.0, ["no_exchange_found"], hops=None, hop_limit=5)
    features = extract_features(case)
    assert features[0] == 6.0  # hop_limit + 1 sentinel


def test_extract_features_uses_actual_hops_when_exchange_found():
    case = _case(15.0, [], hops=2)
    features = extract_features(case)
    assert features[0] == 2.0


def test_train_refuses_with_too_few_cases():
    cases = [_case(10.0, []) for _ in range(3)]
    result = train(cases)
    assert result.model is None
    assert "at least" in result.reason_unavailable


def test_train_refuses_with_single_class_only():
    cases = [_case(10.0, []) for _ in range(10)]  # all low risk, no variety
    result = train(cases)
    assert result.model is None
    assert "variety" in result.reason_unavailable


def test_train_succeeds_with_enough_varied_cases_and_predicts_a_score():
    low_risk = [_case(10.0, [], hops=1) for _ in range(5)]
    high_risk = [_case(85.0, ["mixer_detected", "cross_chain_bridge"], hops=None) for _ in range(5)]
    result = train(low_risk + high_risk)

    assert result.model is not None
    assert result.trained_on == 10

    score = predict(result.model, high_risk[0])
    assert 0 <= score <= 100
