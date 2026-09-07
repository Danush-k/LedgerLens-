"""Entity resolution: which addresses are controlled by the same actor.

An address is not an actor. One operator routinely controls dozens of
wallets, and an investigation that reasons about addresses instead of
actors will report thirty unrelated leads where there is really one
suspect. Entity resolution collapses addresses into actors so the unit of
investigation matches the unit of prosecution.

Only the strong signal merges. Common-input-ownership is a fact about
signatures: if two addresses were spent as inputs to one transaction, one
key holder authorised both, because a wallet cannot spend a UTXO whose key
it does not hold. Shared-funder fan-out is a much weaker signal - an
exchange paying out to a thousand customers "shares a funder" with all of
them - so it is reported as a possible association and never merged. Over
merging is the dangerous failure here: wrongly fusing two entities invents
a criminal organisation out of unrelated people.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.orm import Case, CaseAddress

# Above this many addresses, an "entity" is service infrastructure rather
# than a person. Clustering can chain transitively through shared
# transactions, so one bad merge can absorb a large part of the chain; a
# suspect who personally controls two thousand wallets is not the likely
# explanation, an exchange is. Such entities are still reported - hiding
# them would hide a real finding - but they are labelled and ranked last so
# they are never mistaken for a lead.
MAX_PLAUSIBLE_ENTITY = 250


class _UnionFind:
    """Standard disjoint-set. Entities are its connected components."""

    def __init__(self):
        self.parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:  # path compression
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a

    def groups(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for item in self.parent:
            out.setdefault(self.find(item), set()).add(item)
        return out


@dataclass
class Entity:
    entity_id: str
    chain: str
    addresses: list[str]
    case_ids: list[str] = field(default_factory=list)
    complaint_refs: list[str] = field(default_factory=list)
    tainted_value: float = 0.0
    labels: list[str] = field(default_factory=list)
    possible_associates: list[str] = field(default_factory=list)
    evidence: str = ""
    likely_service: bool = False

    def as_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "chain": self.chain,
            "address_count": len(self.addresses),
            "addresses": self.addresses,
            "case_count": len(self.case_ids),
            "case_ids": self.case_ids,
            "complaint_refs": self.complaint_refs,
            "tainted_value": round(self.tainted_value, 8),
            "labels": self.labels,
            "possible_associates": self.possible_associates,
            "evidence": self.evidence,
            "likely_service": self.likely_service,
        }


def _service_evidence(addresses: list[str], chain: str) -> str:
    return (
        f"This cluster contains {len(addresses):,} addresses on {chain}, far more "
        f"than one person plausibly controls. Clusters this large form when "
        f"addresses chain together transitively through shared transactions, and "
        f"they almost always describe an exchange or custodial service rather "
        f"than a suspect. Reported for completeness, but it should not be "
        f"treated as an actor without independent corroboration."
    )


def _evidence(addresses: list[str], case_count: int, chain: str) -> str:
    return (
        f"{len(addresses)} addresses were spent together as inputs to the same "
        f"transaction(s) on {chain}, so one key holder authorised all of them - "
        f"a wallet cannot spend a UTXO it does not hold the key for. This entity "
        f"appears in {case_count} case(s). Common-input-ownership is a property "
        f"of the signatures, not an inference: the addresses share an owner, "
        f"though that owner's identity is not established by chain data alone."
    )


def resolve_entities(db: Session, chain: str | None = None,
                     min_addresses: int = 2) -> list[Entity]:
    """Merge addresses into entities across every completed case."""
    query = db.query(Case).filter(Case.status == "complete")
    if chain:
        query = query.filter(Case.chain == chain)
    cases = query.all()

    uf = _UnionFind()
    # address -> the strongest label seen for it, and which cases touched it
    address_chain: dict[str, str] = {}
    weak_links: dict[str, set[str]] = {}

    for case in cases:
        for cluster in case.clusters or []:
            members = cluster.get("addresses") or []
            for addr in members:
                uf.add(addr)
                address_chain.setdefault(addr, case.chain)

            if cluster.get("type") == "common_input":
                # Strong: same signer. Safe to merge.
                for other in members[1:]:
                    uf.union(members[0], other)
            else:
                # Weak: recorded as association, never merged.
                for addr in members:
                    weak_links.setdefault(addr, set()).update(set(members) - {addr})

    if not uf.parent:
        return []

    # Which cases and how much traced value each address carries.
    footprint_rows = db.query(CaseAddress).filter(
        CaseAddress.address.in_(list(uf.parent.keys()))).all()
    by_address: dict[str, list[CaseAddress]] = {}
    for row in footprint_rows:
        by_address.setdefault(row.address, []).append(row)

    case_by_id = {c.id: c for c in cases}

    entities: list[Entity] = []
    for _, members in uf.groups().items():
        if len(members) < min_addresses:
            continue
        addresses = sorted(members)
        # A stable, content-derived id: the same cluster keeps the same id
        # across runs, so an investigator can cite it.
        entity_id = f"ENT-{addresses[0][:12]}"

        case_ids: list[str] = []
        tainted = 0.0
        labels: set[str] = set()
        for addr in addresses:
            for row in by_address.get(addr, []):
                if row.case_id not in case_ids:
                    case_ids.append(row.case_id)
                tainted += row.value_in
                if row.label_name:
                    labels.add(row.label_name)

        associates = sorted({a for addr in addresses
                             for a in weak_links.get(addr, set())} - set(addresses))

        oversized = len(addresses) > MAX_PLAUSIBLE_ENTITY
        entities.append(Entity(
            likely_service=oversized,
            entity_id=entity_id,
            chain=address_chain.get(addresses[0], chain or "bitcoin"),
            addresses=addresses,
            case_ids=case_ids,
            complaint_refs=[case_by_id[c].complaint_ref for c in case_ids
                            if c in case_by_id and case_by_id[c].complaint_ref],
            tainted_value=tainted,
            labels=sorted(labels),
            possible_associates=associates,
            evidence=(
                _service_evidence(addresses, address_chain.get(addresses[0], chain or "bitcoin"))
                if oversized else
                _evidence(addresses, len(case_ids),
                          address_chain.get(addresses[0], chain or "bitcoin"))
            ),
        ))

    # Plausible actors first, ranked by how many cases they span. Suspected
    # infrastructure sinks to the bottom regardless of how many cases it
    # touches, because it touches all of them for uninteresting reasons.
    entities.sort(key=lambda e: (not e.likely_service, len(e.case_ids), len(e.addresses)),
                  reverse=True)
    return entities


def entity_for_address(db: Session, address: str) -> Entity | None:
    """The entity a given address belongs to, if any."""
    for entity in resolve_entities(db):
        if address in entity.addresses:
            return entity
    return None
