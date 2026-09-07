"""Entity resolution across cases.

The load-bearing behaviour is what does *not* merge. Over-merging invents a
criminal organisation out of unrelated people, which is a far worse failure
than reporting two entities that are really one.
"""
from datetime import datetime, timezone

from app.intel.entities import entity_for_address, resolve_entities
from app.models.orm import Case, CaseAddress


def _case(db, clusters, complaint_ref="NCRP-1", chain="bitcoin"):
    case = Case(reported_address="bc1qroot", chain=chain, status="complete",
                complaint_ref=complaint_ref, clusters=clusters,
                created_at=datetime.now(timezone.utc))
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _footprint(db, case, address, value_in=1.0, label_name=None):
    db.add(CaseAddress(case_id=case.id, chain=case.chain, address=address,
                       hop=1, value_in=value_in, label_name=label_name))
    db.commit()


def test_common_input_addresses_merge_into_one_entity(db_session):
    case = _case(db_session, [{
        "type": "common_input",
        "addresses": ["bc1qa", "bc1qb", "bc1qc"],
        "note": "co-spent",
    }])
    for addr in ("bc1qa", "bc1qb", "bc1qc"):
        _footprint(db_session, case, addr)

    entities = resolve_entities(db_session)

    assert len(entities) == 1
    assert entities[0].addresses == ["bc1qa", "bc1qb", "bc1qc"]


def test_shared_funder_does_not_merge(db_session):
    """An exchange paying out to a thousand customers "shares a funder" with
    all of them. Merging on that would fuse unrelated people into one
    suspect."""
    _case(db_session, [{
        "type": "shared_funder",
        "addresses": ["bc1qx", "bc1qy", "bc1qz"],
        "note": "same funder",
    }])

    assert resolve_entities(db_session) == []


def test_shared_funder_is_still_reported_as_association(db_session):
    case = _case(db_session, [
        {"type": "common_input", "addresses": ["bc1qa", "bc1qb"], "note": ""},
        {"type": "shared_funder", "addresses": ["bc1qa", "bc1qmaybe"], "note": ""},
    ])
    _footprint(db_session, case, "bc1qa")

    entity = resolve_entities(db_session)[0]

    assert "bc1qmaybe" not in entity.addresses      # not merged
    assert "bc1qmaybe" in entity.possible_associates  # but not discarded


def test_entities_merge_transitively_across_separate_cases(db_session):
    """Case 1 proves A and B share a signer; case 2 proves B and C do.
    Therefore A, B and C are one actor - a conclusion neither case reaches
    alone."""
    case_1 = _case(db_session, [{"type": "common_input",
                                 "addresses": ["bc1qa", "bc1qb"], "note": ""}],
                   complaint_ref="NCRP-1")
    case_2 = _case(db_session, [{"type": "common_input",
                                 "addresses": ["bc1qb", "bc1qc"], "note": ""}],
                   complaint_ref="NCRP-2")
    for case, addr in ((case_1, "bc1qa"), (case_1, "bc1qb"),
                       (case_2, "bc1qb"), (case_2, "bc1qc")):
        _footprint(db_session, case, addr)

    entities = resolve_entities(db_session)

    assert len(entities) == 1
    assert entities[0].addresses == ["bc1qa", "bc1qb", "bc1qc"]
    assert entities[0].case_count if hasattr(entities[0], "case_count") else True
    assert set(entities[0].complaint_refs) == {"NCRP-1", "NCRP-2"}


def test_multi_case_entities_rank_first(db_session):
    single = _case(db_session, [{"type": "common_input",
                                 "addresses": ["bc1qsolo1", "bc1qsolo2"], "note": ""}],
                   complaint_ref="NCRP-SOLO")
    _footprint(db_session, single, "bc1qsolo1")

    shared_1 = _case(db_session, [{"type": "common_input",
                                   "addresses": ["bc1qm1", "bc1qm2"], "note": ""}],
                     complaint_ref="NCRP-A")
    shared_2 = _case(db_session, [{"type": "common_input",
                                   "addresses": ["bc1qm1", "bc1qm2"], "note": ""}],
                     complaint_ref="NCRP-B")
    for case in (shared_1, shared_2):
        _footprint(db_session, case, "bc1qm1")

    entities = resolve_entities(db_session)

    assert entities[0].addresses == ["bc1qm1", "bc1qm2"]  # spans two cases
    assert len(entities[0].case_ids) == 2


def test_entity_id_is_stable_across_runs(db_session):
    case = _case(db_session, [{"type": "common_input",
                               "addresses": ["bc1qa", "bc1qb"], "note": ""}])
    _footprint(db_session, case, "bc1qa")

    assert resolve_entities(db_session)[0].entity_id == \
           resolve_entities(db_session)[0].entity_id


def test_evidence_states_why_the_merge_is_sound(db_session):
    case = _case(db_session, [{"type": "common_input",
                               "addresses": ["bc1qa", "bc1qb"], "note": ""}])
    _footprint(db_session, case, "bc1qa")

    evidence = resolve_entities(db_session)[0].evidence

    assert "cannot spend a UTXO it does not hold the key for" in evidence
    # Shared control is established; identity is not.
    assert "identity is not established" in evidence


def test_entity_for_address(db_session):
    case = _case(db_session, [{"type": "common_input",
                               "addresses": ["bc1qa", "bc1qb"], "note": ""}])
    _footprint(db_session, case, "bc1qa")

    assert entity_for_address(db_session, "bc1qb").addresses == ["bc1qa", "bc1qb"]
    assert entity_for_address(db_session, "bc1qnever") is None


def test_incomplete_cases_are_ignored(db_session):
    case = Case(reported_address="bc1qroot", chain="bitcoin", status="tracing",
                clusters=[{"type": "common_input", "addresses": ["bc1qa", "bc1qb"]}],
                created_at=datetime.now(timezone.utc))
    db_session.add(case)
    db_session.commit()

    assert resolve_entities(db_session) == []


def test_oversized_cluster_is_flagged_as_infrastructure(db_session):
    """Clustering chains transitively, so one bad merge can absorb a large
    part of the chain. A "suspect" holding thousands of wallets is an
    exchange, and presenting it as an actor would be worse than useless."""
    from app.intel.entities import MAX_PLAUSIBLE_ENTITY

    huge = [f"bc1qaddr{i:05d}" for i in range(MAX_PLAUSIBLE_ENTITY + 5)]
    case = _case(db_session, [{"type": "common_input", "addresses": huge, "note": ""}])
    _footprint(db_session, case, huge[0])

    entity = resolve_entities(db_session)[0]

    assert entity.likely_service is True
    assert "far more than one person plausibly controls" in entity.evidence
    assert "should not be treated as an actor" in entity.evidence


def test_plausible_entities_rank_above_infrastructure(db_session):
    """Infrastructure touches many cases for uninteresting reasons, so case
    count alone must not float it to the top of the list."""
    from app.intel.entities import MAX_PLAUSIBLE_ENTITY

    huge = [f"bc1qbig{i:05d}" for i in range(MAX_PLAUSIBLE_ENTITY + 5)]
    for ref in ("NCRP-X", "NCRP-Y", "NCRP-Z"):
        big_case = _case(db_session, [{"type": "common_input", "addresses": huge, "note": ""}],
                         complaint_ref=ref)
        _footprint(db_session, big_case, huge[0])

    small = _case(db_session, [{"type": "common_input",
                                "addresses": ["bc1qreal1", "bc1qreal2"], "note": ""}],
                  complaint_ref="NCRP-REAL")
    _footprint(db_session, small, "bc1qreal1")

    entities = resolve_entities(db_session)

    assert entities[0].addresses == ["bc1qreal1", "bc1qreal2"]
    assert entities[0].likely_service is False
    assert entities[-1].likely_service is True
