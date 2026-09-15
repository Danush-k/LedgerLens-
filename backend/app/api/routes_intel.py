"""Cross-case intelligence endpoints.

Everything else in this API is case-scoped: you ask about one complaint and
get one answer. These endpoints are the opposite - they ask what the whole
body of cases says collectively, which is where syndicate structure lives.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.chain_clients.base import normalize_address
from app.db.neo4j_client import graph_convergence_points
from app.db.postgres import get_db
from app.intel.convergence import (
    DEFAULT_LIMIT,
    DEFAULT_MIN_CASES,
    address_footprint,
    find_convergence_points,
)
from app.intel.entities import entity_for_address, resolve_entities

router = APIRouter(prefix="/intel", tags=["intelligence"])


@router.get("/convergence")
def convergence(
    db: Session = Depends(get_db),
    min_cases: int = Query(DEFAULT_MIN_CASES, ge=2, le=50),
    chain: str | None = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
):
    """Wallets receiving traced funds from two or more independent cases.

    Known exchanges, mixers and bridges are excluded - they receive from
    unrelated senders by design, so their convergence carries no information
    about shared control.
    """
    points = find_convergence_points(db, min_cases=min_cases, chain=chain, limit=limit)
    return {
        "min_cases": min_cases,
        "count": len(points),
        "convergence_points": [p.as_dict() for p in points],
        # Stated rather than implied: an empty result from a single-case
        # database means "not enough cases yet", not "no syndicates exist".
        "note": (
            "Convergence requires at least two completed traces to be possible. "
            "Known services are excluded because they aggregate unrelated funds "
            "by design."
        ),
    }


@router.get("/convergence/graph")
def convergence_via_graph(
    min_cases: int = Query(DEFAULT_MIN_CASES, ge=2, le=50),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=200),
):
    """The same question answered by Neo4j traversal instead of SQL.

    Kept alongside the SQL implementation because the graph store is optional
    in this deployment: when it is unavailable this reports that plainly
    rather than returning an empty list that would read as "nothing found".
    """
    points = graph_convergence_points(min_cases=min_cases, limit=limit)
    if points is None:
        raise HTTPException(
            503,
            "Neo4j is unavailable, so the graph-traversal implementation cannot run. "
            "Use /intel/convergence for the SQL-backed equivalent.",
        )
    return {"min_cases": min_cases, "count": len(points), "convergence_points": points}


@router.get("/address/{chain}/{address}")
def address_intel(chain: str, address: str, db: Session = Depends(get_db)):
    """Every case that has touched one address.

    The address-centric view. "Have we seen this wallet before, and in whose
    case?" is the first question an investigator asks about a new lead, and
    it is not answerable from any single case record.
    """
    footprint = address_footprint(db, chain, normalize_address(address))
    if not footprint:
        raise HTTPException(
            404,
            f"{address} does not appear in any trace on {chain}. It may be valid "
            f"and simply unseen - this is a statement about our case history, "
            f"not about the address.",
        )
    return footprint


@router.get("/entities")
def entities(
    db: Session = Depends(get_db),
    chain: str | None = Query(None),
    min_addresses: int = Query(2, ge=2, le=100),
):
    """Addresses grouped into the actors that control them.

    Merging is on common-input-ownership only - a fact about which key
    signed a transaction. Weaker association signals are reported per entity
    as possible associates but never merged, because wrongly fusing two
    entities manufactures a criminal organisation out of unrelated people.
    """
    resolved = resolve_entities(db, chain=chain, min_addresses=min_addresses)
    return {
        "count": len(resolved),
        "entities": [e.as_dict() for e in resolved],
        "note": (
            "Entities are derived from common-input-ownership, which establishes "
            "shared control of the addresses but not the controller's identity."
        ),
    }


@router.get("/entities/address/{address}")
def entity_of_address(address: str, db: Session = Depends(get_db)):
    """The entity a specific address belongs to."""
    entity = entity_for_address(db, normalize_address(address))
    if not entity:
        raise HTTPException(
            404,
            f"{address} is not part of any resolved entity. It may simply never "
            f"have been co-spent with another address - absence of a cluster is "
            f"not evidence the wallet stands alone.",
        )
    return entity.as_dict()
