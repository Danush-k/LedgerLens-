"""Rule-based risk scoring - the explainable v1 score.

Every point on the score traces back to a named, human-readable signal, so
an investigator (or a judge) can always ask "why 78?" and get a real answer.
This stays the system of record even after an ML-assisted score is added -
see risk/ml.py.
"""

WEIGHTS = {
    "mixer_detected": 35,
    "cross_chain_bridge": 20,
    "no_exchange_found": 15,
    "high_fan_out": 15,
    "rapid_layering": 10,
    "fast_cashout": 15,  # exchange found within 1-2 hops
    "prior_report": 20,
    # Shape-of-movement signals from tracer/patterns.py. Layering across
    # several hops is the strongest of these: one relay wallet is
    # unremarkable, a sustained chain of them is not.
    "peel_chain": 25,
    "fan_in": 12,
    "pass_through": 8,
    "partial_trace": 8,  # exchange found, but other branches ran out of hops
}

# Signals derived from arguments rather than flags, or that are outcomes
# rather than risk (reaching a known exchange is good news for an
# investigator - it means the trail resolved).
_NON_FLAG_SIGNALS = {"prior_report", "fast_cashout", "exchange_identified"}


def score_case(flags: set[str], nearest_exchange: dict | None,
               prior_report_count: int, rapid_layering: bool) -> tuple[float, dict]:
    breakdown: dict[str, int] = {}

    for flag in flags:
        if flag in WEIGHTS and flag not in _NON_FLAG_SIGNALS:
            breakdown[flag] = WEIGHTS[flag]

    if rapid_layering:
        breakdown["rapid_layering"] = WEIGHTS["rapid_layering"]

    if nearest_exchange and nearest_exchange.get("hops", 99) <= 2:
        breakdown["fast_cashout"] = WEIGHTS["fast_cashout"]

    if prior_report_count > 0:
        breakdown["prior_report"] = WEIGHTS["prior_report"]

    score = min(100, sum(breakdown.values()))
    return float(score), breakdown


def recommended_action(nearest_exchange: dict | None, score: float) -> str:
    if nearest_exchange:
        return (
            f"Send an evidence-preservation request to {nearest_exchange['name']} "
            f"- funds reached its deposit address at hop {nearest_exchange['hops']} "
            f"(risk {score:.0f}/100)."
        )
    if score >= 50:
        return (
            "No exchange identified within the hop limit, but risk signals are "
            "high - escalate for deeper manual tracing and consider requesting "
            "extended history from the last known intermediate address."
        )
    return "No exchange identified within the hop limit; risk signals are low. Monitor for further activity."
