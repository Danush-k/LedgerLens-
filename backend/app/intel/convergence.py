"""Cross-case convergence analysis.

A single trace answers "where did this victim's money go?". Convergence
analysis answers the question no single trace can: "which wallets are
collecting from *several* victims?"

When wallets reported in independent complaints - different victims,
different dates, different investigating officers - all route funds into the
same downstream address, that address is a consolidation point. It is the
strongest syndicate signal available from chain data alone, and it is
invisible in any single case file, which is exactly why it is worth
computing.

Two deliberate exclusions keep the signal honest:

1. Known services are dropped. An exchange deposit wallet receives from
   thousands of unrelated people by design; it converges for reasons that
   have nothing to do with a shared operator. Including exchanges would make
   Binance the top "syndicate" in every deployment.

2. A single case cannot converge with itself. Counting is over *distinct*
   case ids, so one trace that reaches an address by several internal paths
   still counts once.

What this does and does not establish is worth stating plainly, because the
distinction matters in an investigation: convergence is a blockchain fact
about shared fund flow. It is evidence that warrants investigation, not
proof of common control - a payment processor, a custodial service or an
OTC desk can also legitimately receive from many unrelated senders.
"""
from dataclasses import dataclass

from sqlalchemy import distinct, func, or_
from sqlalchemy.orm import Session

from app.models.orm import Case, CaseAddress

# Label types that collect from unrelated senders as a matter of course.
# These converge structurally, not conspiratorially.
SERVICE_TYPES = ("exchange", "mixer", "bridge")

DEFAULT_MIN_CASES = 2
DEFAULT_LIMIT = 50


@dataclass
class ConvergencePoint:
    chain: str
    address: str
    case_count: int
    total_value: float
    min_hop: int
    node_type: str | None
    label_name: str | None
    cases: list[dict]
    evidence: str

    def as_dict(self) -> dict:
        return {
            "chain": self.chain,
            "address": self.address,
            "case_count": self.case_count,
            "total_value": round(self.total_value, 8),
            "min_hop": self.min_hop,
            "node_type": self.node_type,
            "label_name": self.label_name,
            "cases": self.cases,
            "evidence": self.evidence,
        }


def _evidence(address: str, case_count: int, total_value: float,
              min_hop: int, chain: str) -> str:
    hop_phrase = (
        "was itself reported by a complainant"
        if min_hop == 0
        else f"sits {min_hop} hop{'s' if min_hop > 1 else ''} from a reported wallet at its closest"
    )
    return (
        f"{address} received traced funds from {case_count} independently "
        f"reported cases totalling {total_value:.8f} {chain.upper()}, and {hop_phrase}. "
        f"Separate complainants reaching one wallet is a consolidation pattern: it "
        f"indicates the reported wallets may be operated together rather than being "
        f"unrelated frauds. This is a shared fund-flow finding, not proof of common "
        f"control - verify against the exchange or service records before acting on it."
    )


def find_convergence_points(db: Session, min_cases: int = DEFAULT_MIN_CASES,
                            chain: str | None = None,
                            limit: int = DEFAULT_LIMIT) -> list[ConvergencePoint]:
    """Addresses that received traced funds from two or more distinct cases."""
    case_count = func.count(distinct(CaseAddress.case_id)).label("case_count")

    query = (
        db.query(
            CaseAddress.chain,
            CaseAddress.address,
            case_count,
            func.sum(CaseAddress.value_in).label("total_value"),
            func.min(CaseAddress.hop).label("min_hop"),
            func.max(CaseAddress.node_type).label("node_type"),
            func.max(CaseAddress.label_name).label("label_name"),
        )
        # NOT IN evaluates to NULL for a NULL column, so unlabeled addresses -
        # the ones we care most about - need the explicit OR to survive.
        .filter(or_(CaseAddress.node_type.is_(None),
                    CaseAddress.node_type.notin_(SERVICE_TYPES)))
    )
    if chain:
        query = query.filter(CaseAddress.chain == chain)

    rows = (
        query.group_by(CaseAddress.chain, CaseAddress.address)
        .having(case_count >= min_cases)
        .order_by(case_count.desc(), func.sum(CaseAddress.value_in).desc())
        .limit(limit)
        .all()
    )

    points: list[ConvergencePoint] = []
    for row in rows:
        points.append(ConvergencePoint(
            chain=row.chain,
            address=row.address,
            case_count=row.case_count,
            total_value=float(row.total_value or 0.0),
            min_hop=int(row.min_hop or 0),
            node_type=row.node_type,
            label_name=row.label_name,
            cases=_contributing_cases(db, row.chain, row.address),
            evidence=_evidence(row.address, row.case_count,
                               float(row.total_value or 0.0),
                               int(row.min_hop or 0), row.chain),
        ))
    return points


def _contributing_cases(db: Session, chain: str, address: str) -> list[dict]:
    """The cases whose traces reached this address, with how they got there."""
    rows = (
        db.query(CaseAddress, Case)
        .join(Case, Case.id == CaseAddress.case_id)
        .filter(CaseAddress.chain == chain, CaseAddress.address == address)
        .order_by(CaseAddress.hop.asc())
        .all()
    )
    seen: set[str] = set()
    cases = []
    for ca, case in rows:
        if case.id in seen:
            continue  # one trace can reach an address by several paths
        seen.add(case.id)
        cases.append({
            "case_id": case.id,
            "complaint_ref": case.complaint_ref,
            "reported_address": case.reported_address,
            "fraud_typology": case.fraud_typology,
            "risk_score": case.risk_score,
            "status": case.status,
            "created_at": case.created_at,
            "hop": ca.hop,
            "value_in": round(ca.value_in, 8),
        })
    return cases


def address_footprint(db: Session, chain: str, address: str) -> dict | None:
    """Everything the system knows about one address across every case.

    The address-centric view, as opposed to the case-centric view the rest of
    the application is built around. An investigator asking "have we seen this
    wallet before?" is asking this question.
    """
    rows = (
        db.query(CaseAddress)
        .filter(CaseAddress.chain == chain, CaseAddress.address == address)
        .all()
    )
    if not rows:
        return None

    cases = _contributing_cases(db, chain, address)
    labeled = next((r for r in rows if r.node_type), None)
    return {
        "chain": chain,
        "address": address,
        "case_count": len(cases),
        "total_value": round(sum(r.value_in for r in rows), 8),
        "min_hop": min(r.hop for r in rows),
        "node_type": labeled.node_type if labeled else None,
        "label_name": labeled.label_name if labeled else None,
        "reported_directly": any(r.hop == 0 for r in rows),
        "cases": cases,
    }
