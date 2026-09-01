from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.orm import Case, TracedAddress


def find_syndicate_clusters(db: Session) -> list[dict]:
    """Scans all completed cases in the database to identify criminal syndicate clusters:
    1. Wallet addresses reported in 2+ independent FIRs / complaints.
    2. Shared deposit/exchange target accounts receiving funds from multiple independent victims.
    """
    cases = db.query(Case).filter(Case.status == "complete").all()
    
    # 1. Map target exchange deposit addresses -> list of case IDs
    deposit_to_cases: dict[str, set[str]] = defaultdict(set)
    # 2. Map reported victim wallets -> list of case IDs
    reported_to_cases: dict[str, set[str]] = defaultdict(set)
    
    case_map: dict[str, Case] = {c.id: c for c in cases}

    for c in cases:
        reported_key = f"{c.chain}:{c.reported_address}"
        reported_to_cases[reported_key].add(c.id)

        if c.nearest_exchange and isinstance(c.nearest_exchange, dict):
            ex_addr = c.nearest_exchange.get("address")
            if ex_addr:
                ex_key = f"{c.chain}:{ex_addr}"
                deposit_to_cases[ex_key].add(c.id)

    syndicates: list[dict] = []
    cluster_idx = 1

    # Shared target deposit account syndicates
    for ex_key, case_ids in deposit_to_cases.items():
        if len(case_ids) >= 2:
            linked_cases = [case_map[cid] for cid in case_ids if cid in case_map]
            total_stolen_signal = sum(lc.risk_score or 0 for lc in linked_cases)
            chain, addr = ex_key.split(":", 1)
            target_vasp = linked_cases[0].nearest_exchange.get("name") if linked_cases[0].nearest_exchange else "VASP Deposit"

            syndicates.append({
                "syndicate_id": f"SYN-DEPOSIT-{cluster_idx:03d}",
                "title": f"Syndicate Cluster around {target_vasp}",
                "chain": chain,
                "target_address": addr,
                "vasp_name": target_vasp,
                "linked_case_count": len(linked_cases),
                "linked_cases": [
                    {
                        "case_id": lc.id,
                        "reported_address": lc.reported_address,
                        "complaint_ref": lc.complaint_ref,
                        "risk_score": lc.risk_score,
                        "created_at": lc.created_at.isoformat() if lc.created_at else None,
                    }
                    for lc in linked_cases
                ],
                "combined_risk_index": min(100.0, round(total_stolen_signal / len(linked_cases) + 20, 1)),
                "type": "shared_cashout_deposit",
            })
            cluster_idx += 1

    # Repeat offender victim-reported wallet syndicates
    for rep_key, case_ids in reported_to_cases.items():
        if len(case_ids) >= 2:
            linked_cases = [case_map[cid] for cid in case_ids if cid in case_map]
            chain, addr = rep_key.split(":", 1)

            syndicates.append({
                "syndicate_id": f"SYN-REPEAT-{cluster_idx:03d}",
                "title": f"Repeat Offender Wallet Cluster ({addr[:8]}...{addr[-6:]})",
                "chain": chain,
                "target_address": addr,
                "vasp_name": "Multi-Victim Suspect Wallet",
                "linked_case_count": len(linked_cases),
                "linked_cases": [
                    {
                        "case_id": lc.id,
                        "reported_address": lc.reported_address,
                        "complaint_ref": lc.complaint_ref,
                        "risk_score": lc.risk_score,
                        "created_at": lc.created_at.isoformat() if lc.created_at else None,
                    }
                    for lc in linked_cases
                ],
                "combined_risk_index": 95.0,
                "type": "repeat_suspect_wallet",
            })
            cluster_idx += 1

    syndicates.sort(key=lambda s: s["linked_case_count"], reverse=True)
    return syndicates
