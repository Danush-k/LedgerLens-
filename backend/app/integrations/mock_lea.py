"""Stand-ins for real NCRP / SAHYOG / VASP integrations.

Real access to these platforms requires an official MoU/API access this
prototype doesn't have. Every call here is logged as an AuditEvent with
simulated=True so nothing in the UI or the exported report can be mistaken
for a live integration - the dashboard's "Integration Log" panel surfaces
these events verbatim.
"""

from sqlalchemy.orm import Session

from app.models.orm import AuditEvent, Case


def send_alert(db: Session, case: Case) -> None:
    if case.nearest_exchange:
        detail = (
            f"[SIMULATED] Notification queued to {case.nearest_exchange['name']} "
            f"requesting preservation of records for {case.reported_address} "
            f"(case {case.id})."
        )
    else:
        detail = (
            f"[SIMULATED] High-risk case {case.id} escalated to investigator "
            f"queue - no exchange identified within hop limit."
        )
    db.add(AuditEvent(case_id=case.id, event="alert_sent", detail=detail, simulated=True))


def receive_ncrp_intake(payload: dict) -> dict:
    """A real NCRP integration would push complaint payloads here. This
    normalises that shape into what POST /trace expects, so the rest of
    the pipeline (queueing, tracing, scoring) is identical either way.
    """
    return {
        "address": payload["suspect_wallet_address"],
        "chain": payload["chain"],
        "complaint_ref": payload.get("ncrp_complaint_number"),
    }
