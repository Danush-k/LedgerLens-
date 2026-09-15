import logging
from functools import lru_cache

from neo4j import GraphDatabase

from app.chain_clients.base import normalize_address
from app.config import get_settings

logger = logging.getLogger(__name__)


_NEO4J_AVAILABLE: bool | None = None


@lru_cache
def get_driver():
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        connection_timeout=1.0,
        max_connection_lifetime=5.0,
    )


def is_neo4j_available() -> bool:
    global _NEO4J_AVAILABLE
    if _NEO4J_AVAILABLE is not None:
        return _NEO4J_AVAILABLE
    try:
        get_driver().verify_connectivity()
        _NEO4J_AVAILABLE = True
    except Exception:
        _NEO4J_AVAILABLE = False
    return _NEO4J_AVAILABLE


def ensure_constraints() -> None:
    if not is_neo4j_available():
        return
    try:
        with get_driver().session() as session:
            session.run(
                "CREATE CONSTRAINT address_uid IF NOT EXISTS FOR (a:Address) REQUIRE a.uid IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE"
            )
    except Exception as e:
        logger.warning(f"Neo4j ensure_constraints skipped: {e}")


def _uid(chain: str, address: str) -> str:
    return f"{chain}:{normalize_address(address)}"


def upsert_address(chain: str, address: str, label: dict | None = None) -> None:
    if not is_neo4j_available():
        return
    try:
        with get_driver().session() as session:
            session.run(
                """
                MERGE (a:Address {uid: $uid})
                ON CREATE SET a.chain = $chain, a.address = $address
                SET a.label_type = coalesce($label_type, a.label_type),
                    a.label_name = coalesce($label_name, a.label_name)
                """,
                uid=_uid(chain, address),
                chain=chain,
                address=normalize_address(address),
                label_type=(label or {}).get("type"),
                label_name=(label or {}).get("name"),
            )
    except Exception as e:
        logger.warning(f"Neo4j upsert_address skipped: {e}")


def record_transfer(case_id: str, chain: str, from_address: str, to_address: str,
                     tx_hash: str, value: float, timestamp: int, hop: int) -> None:
    """Record a transfer as a case-independent blockchain fact.

    The merge key is the transaction, not the transaction *and* the case. A
    transfer that two separate investigations both walk through is one edge
    in the graph carrying both case ids - not two parallel edges that can
    never be joined. That distinction is what allows convergence analysis to
    see across cases at all.

    `hop` is case-relative, so the shared edge keeps the smallest hop any
    case reached it at; the exact per-case hop lives in the case's own
    stored subgraph.
    """
    if not is_neo4j_available():
        return
    try:
        with get_driver().session() as session:
            session.run(
                """
                MATCH (a:Address {uid: $from_uid}), (b:Address {uid: $to_uid})
                MERGE (a)-[t:TRANSFER {tx_hash: $tx_hash}]->(b)
                ON CREATE SET t.case_ids = [$case_id], t.min_hop = $hop
                ON MATCH  SET t.case_ids = CASE
                                  WHEN $case_id IN t.case_ids THEN t.case_ids
                                  ELSE t.case_ids + $case_id END,
                              t.min_hop = CASE
                                  WHEN $hop < t.min_hop THEN $hop
                                  ELSE t.min_hop END
                SET t.value = $value, t.timestamp = $timestamp
                """,
                from_uid=_uid(chain, from_address),
                to_uid=_uid(chain, to_address),
                tx_hash=tx_hash,
                case_id=case_id,
                value=value,
                timestamp=timestamp,
                hop=hop,
            )
    except Exception as e:
        logger.warning(f"Neo4j record_transfer skipped: {e}")


def link_case_to_addresses(case_id: str, chain: str, addresses: list[str],
                            reported_address: str | None = None) -> None:
    """Attach a Case node to every address its trace walked through.

    Modelling the case as a node rather than a property on each edge is what
    makes "which addresses do these two cases share?" a one-line traversal
    instead of a scan over relationship properties.
    """
    if not is_neo4j_available():
        return
    try:
        with get_driver().session() as session:
            session.run(
                """
                MERGE (c:Case {id: $case_id})
                WITH c
                UNWIND $uids AS uid
                MATCH (a:Address {uid: uid})
                MERGE (c)-[:TOUCHED]->(a)
                """,
                case_id=case_id,
                uids=[_uid(chain, a) for a in addresses],
            )
            if reported_address:
                session.run(
                    """
                    MATCH (c:Case {id: $case_id}), (a:Address {uid: $uid})
                    MERGE (c)-[:REPORTED]->(a)
                    """,
                    case_id=case_id,
                    uid=_uid(chain, reported_address),
                )
    except Exception as e:
        logger.warning(f"Neo4j link_case_to_addresses skipped: {e}")


def graph_convergence_points(min_cases: int = 2, limit: int = 50) -> list[dict] | None:
    """Convergence via graph traversal - the Neo4j-native counterpart to the
    SQL implementation in intel/convergence.py.

    Returns None when Neo4j is unreachable so callers can fall back to SQL
    rather than presenting an outage as "no syndicates found".
    """
    if not is_neo4j_available():
        return None
    try:
        with get_driver().session() as session:
            result = session.run(
                """
                MATCH (c:Case)-[:TOUCHED]->(a:Address)
                WHERE a.label_type IS NULL
                WITH a, collect(DISTINCT c.id) AS case_ids
                WHERE size(case_ids) >= $min_cases
                RETURN a.address AS address, a.chain AS chain,
                       case_ids, size(case_ids) AS case_count
                ORDER BY case_count DESC
                LIMIT $limit
                """,
                min_cases=min_cases,
                limit=limit,
            )
            return [dict(record) for record in result]
    except Exception as e:
        logger.warning(f"Neo4j graph_convergence_points skipped: {e}")
        return None


def shortest_path_to_exchange(case_id: str, chain: str, reported_address: str) -> list[dict] | None:
    if not is_neo4j_available():
        return None
    try:
        with get_driver().session() as session:
            result = session.run(
                """
                MATCH (start:Address {uid: $start_uid})
                MATCH p = (start)-[:TRANSFER*1..15]->(target:Address {label_type: 'exchange'})
                WHERE ALL(r IN relationships(p) WHERE $case_id IN r.case_ids)
                RETURN [n IN nodes(p) | {address: n.address, label_name: n.label_name}] AS addresses,
                       length(p) AS hops
                ORDER BY hops ASC
                LIMIT 1
                """,
                start_uid=_uid(chain, reported_address),
                case_id=case_id,
            )
            record = result.single()
            if not record:
                return None
            return {"addresses": record["addresses"], "hops": record["hops"]}
    except Exception as e:
        logger.warning(f"Neo4j shortest_path_to_exchange skipped: {e}")
        return None


def load_seed_labels_into_neo4j() -> None:
    from app.labels.loader import load_labels

    try:
        get_driver().verify_connectivity()
        ensure_constraints()
        for (chain, address), label in load_labels().items():
            upsert_address(chain, address, label)
    except Exception as e:
        logger.warning(f"Neo4j not connected or unauthenticated ({e}); continuing with PostgreSQL/SQLite datastore.")
