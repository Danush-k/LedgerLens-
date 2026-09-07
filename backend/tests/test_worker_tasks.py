

# ── prior reports must mean independent complaints ────────────────────────

def test_retracing_the_same_wallet_is_not_a_prior_report(db_session, monkeypatch):
    """The regression this guards: the signal counted case rows, so
    re-running a trace with a deeper hop limit, or an investigator checking
    their own work, inflated the score. The case would then cite itself as
    corroborating evidence against itself."""
    from app.models.orm import Case, TracedAddress

    address = "bc1qretraced"
    # The same investigator tracing the same wallet three times, no refs.
    for _ in range(3):
        case = Case(reported_address=address, chain="bitcoin", status="complete",
                    created_by="investigator", hop_limit=3)
        db_session.add(case)
        db_session.flush()
        db_session.add(TracedAddress(case_id=case.id, chain="bitcoin", address=address))
    db_session.commit()

    rows = (
        db_session.query(Case.complaint_ref, Case.created_by)
        .join(TracedAddress, TracedAddress.case_id == Case.id)
        .filter(TracedAddress.address == address)
        .all()
    )
    distinct = {(r, s) if r else ("__unreferenced__", s) for r, s in rows}

    assert len(rows) == 3        # three case rows
    assert len(distinct) == 1    # but one complaint


def test_separate_complainants_do_count_as_prior_reports(db_session):
    """Two victims naming the same wallet is the signal the flag exists for
    and must survive the deduplication."""
    from app.models.orm import Case, TracedAddress

    address = "bc1qsyndicate"
    for ref, who in (("FIR/1", "officer_a"), ("FIR/2", "officer_b")):
        case = Case(reported_address=address, chain="bitcoin", status="complete",
                    complaint_ref=ref, created_by=who, hop_limit=3)
        db_session.add(case)
        db_session.flush()
        db_session.add(TracedAddress(case_id=case.id, chain="bitcoin", address=address))
    db_session.commit()

    rows = (
        db_session.query(Case.complaint_ref, Case.created_by)
        .join(TracedAddress, TracedAddress.case_id == Case.id)
        .filter(TracedAddress.address == address)
        .all()
    )
    distinct = {(r, s) if r else ("__unreferenced__", s) for r, s in rows}

    assert len(distinct) == 2
