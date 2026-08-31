"""Rule-based fraud typology tagging - keyword matching against the
complaint narrative, scored by match count. Deliberately not ML: the
typology categories are the ones the PS names explicitly, and a transparent
keyword hit list is something an investigator can audit and extend, unlike
a black-box classifier trained on data nobody here has access to. A real
ML classifier is a natural v2 once labelled NCRP complaint text exists to
train on - see PLAN.md.
"""

TYPOLOGY_KEYWORDS: dict[str, list[str]] = {
    "investment_scam": [
        "invest", "investment", "trading", "returns", "profit", "double my money",
        "guaranteed return", "forex", "portfolio", "broker", "stock tip",
    ],
    "task_based_fraud": [
        "task", "like and subscribe", "part time job", "earn per task", "daily task",
        "referral bonus", "recharge task", "app installation job",
    ],
    "sextortion": [
        "nude", "explicit photo", "explicit video", "blackmail", "leak your photo",
        "video call recorded", "expose you", "share with your contacts",
    ],
    "ransomware": [
        "ransom", "encrypted my files", "decrypt", "pay to unlock", "locked my computer",
        "bitcoin to restore access", "files held hostage",
    ],
    "phishing": [
        "otp", "verify your account", "kyc update", "click the link", "suspended account",
        "bank alert", "card blocked", "update your details",
    ],
    "darknet": [
        "darknet", "dark web", "tor marketplace", "onion site",
    ],
}


def classify_typology(narrative: str | None) -> tuple[str | None, float | None]:
    """Returns (typology, confidence) - confidence is just (matches / total
    keyword hits), so it's explainable, not a calibrated probability."""
    if not narrative or not narrative.strip():
        return None, None

    text = narrative.lower()
    scores: dict[str, int] = {}
    for typology, keywords in TYPOLOGY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[typology] = hits

    if not scores:
        return "unclassified", None

    best_typology = max(scores, key=lambda t: scores[t])
    confidence = round(scores[best_typology] / sum(scores.values()), 2)
    return best_typology, confidence
