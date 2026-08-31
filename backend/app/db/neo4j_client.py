from functools import lru_cache

from neo4j import GraphDatabase

from app.config import get_settings


@lru_cache
def get_driver():
    settings = get_settings()
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))


def ensure_constraints() -> None:
    with get_driver().session() as session:
        session.run(
            "CREATE CONSTRAINT address_uid IF NOT EXISTS FOR (a:Address) REQUIRE a.uid IS UNIQUE"
        )


def _uid(chain: str, address: str) -> str:
    return f"{chain}:{address.lower()}"


def upsert_address(chain: str, address: str, label: dict | None = None) -> None:
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
            address=address.lower(),
            label_type=(label or {}).get("type"),
            label_name=(label or {}).get("name"),
        )


def record_transfer(case_id: str, chain: str, from_address: str, to_address: str,
                     tx_hash: str, value: float, timestamp: int, hop: int) -> None:
    with get_driver().session() as session:
        session.run(
            """
            MATCH (a:Address {uid: $from_uid}), (b:Address {uid: $to_uid})
            MERGE (a)-[t:TRANSFER {tx_hash: $tx_hash, case_id: $case_id}]->(b)
            SET t.value = $value, t.timestamp = $timestamp, t.hop = $hop
            """,
            from_uid=_uid(chain, from_address),
            to_uid=_uid(chain, to_address),
            tx_hash=tx_hash,
            case_id=case_id,
            value=value,
            timestamp=timestamp,
            hop=hop,
        )


def shortest_path_to_exchange(case_id: str, chain: str, reported_address: str) -> list[dict] | None:
    """Live Cypher demo query: within this case's traced subgraph, what is
    the shortest hop-path from the reported address to any labeled exchange?
    """
    with get_driver().session() as session:
        result = session.run(
            """
            MATCH (start:Address {uid: $start_uid})
            MATCH p = shortestPath(
                (start)-[:TRANSFER* {case_id: $case_id}]->(target:Address {label_type: 'exchange'})
            )
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


def load_seed_labels_into_neo4j() -> None:
    from app.labels.loader import load_labels

    ensure_constraints()
    for (chain, address), label in load_labels().items():
        upsert_address(chain, address, label)
