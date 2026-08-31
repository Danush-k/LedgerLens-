"""ML-assisted risk scoring (v2) - explicitly a secondary, illustrative
signal, never a replacement for the explainable rule-based score in
risk/rules.py. See PLAN.md: there is no real labelled fraud dataset
available to a hackathon team, so this bootstraps weak labels from the
v1 rule score (>=70 -> "high risk") and demonstrates the pipeline a real
ML model would slot into once genuine NCRP-labelled outcomes exist to
train on. It is retrained from scratch on every call, which is fine at
this data scale and means it's never a stale model silently drifting.

MIN_TRAINING_CASES is deliberately small for demo purposes; a production
system would require far more labelled examples before trusting this at
all, and would use ground-truth outcomes rather than the v1 score itself.
"""
from dataclasses import dataclass

from sklearn.ensemble import RandomForestClassifier

from app.models.orm import Case

MIN_TRAINING_CASES = 8
MIN_MINORITY_CLASS_COUNT = 2
FEATURE_NAMES = [
    "hops_to_exchange", "num_nodes", "num_edges", "mixer_detected",
    "cross_chain_bridge", "high_fan_out", "rapid_layering", "prior_report", "no_exchange_found",
]


@dataclass
class TrainingResult:
    model: RandomForestClassifier | None
    trained_on: int
    reason_unavailable: str | None = None


def extract_features(case: Case) -> list[float]:
    flags = set(case.flags or [])
    graph = case.graph or {"nodes": [], "edges": []}
    hops = case.nearest_exchange["hops"] if case.nearest_exchange else case.hop_limit + 1
    return [
        float(hops),
        float(len(graph.get("nodes", []))),
        float(len(graph.get("edges", []))),
        float("mixer_detected" in flags),
        float("cross_chain_bridge" in flags),
        float("high_fan_out" in flags),
        float("rapid_layering" in flags),
        float("prior_report" in flags),
        float("no_exchange_found" in flags),
    ]


def train(cases: list[Case]) -> TrainingResult:
    scored = [c for c in cases if c.risk_score is not None and c.graph is not None]
    if len(scored) < MIN_TRAINING_CASES:
        return TrainingResult(None, len(scored), f"Need at least {MIN_TRAINING_CASES} traced cases to train on.")

    X = [extract_features(c) for c in scored]
    y = [int(c.risk_score >= 70) for c in scored]

    if min(y.count(0), y.count(1)) < MIN_MINORITY_CLASS_COUNT:
        return TrainingResult(
            None, len(scored),
            "All traced cases fall on one side of the risk threshold so far - need some variety "
            "(both high- and lower-risk cases) before a classifier can learn anything.",
        )

    model = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
    model.fit(X, y)
    return TrainingResult(model, len(scored))


def predict(model: RandomForestClassifier, case: Case) -> float:
    proba = model.predict_proba([extract_features(case)])[0]
    # predict_proba's column order follows model.classes_, not always [P(0), P(1)]
    high_risk_index = list(model.classes_).index(1)
    return round(float(proba[high_risk_index]) * 100, 1)
