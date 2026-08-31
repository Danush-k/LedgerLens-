from app.risk.typology import classify_typology


def test_classifies_investment_scam():
    typology, confidence = classify_typology(
        "Victim was promised guaranteed returns on a trading investment portfolio."
    )
    assert typology == "investment_scam"
    assert confidence == 1.0


def test_classifies_sextortion():
    typology, _ = classify_typology("Suspect threatened to leak your photo and blackmail the victim.")
    assert typology == "sextortion"


def test_classifies_phishing():
    typology, _ = classify_typology("Message said verify your account or card blocked, sent an OTP link.")
    assert typology == "phishing"


def test_no_narrative_returns_none():
    assert classify_typology(None) == (None, None)
    assert classify_typology("   ") == (None, None)


def test_narrative_with_no_keyword_matches_is_unclassified():
    typology, confidence = classify_typology("Victim reported losing funds, no further detail given.")
    assert typology == "unclassified"
    assert confidence is None


def test_confidence_reflects_relative_keyword_strength():
    # Mostly investment-scam language, one stray phishing-ish word.
    narrative = "Promised guaranteed return on investment trading portfolio, said verify your account too."
    typology, confidence = classify_typology(narrative)
    assert typology == "investment_scam"
    assert 0 < confidence < 1
