from __future__ import annotations

from enum import Enum
from typing import Iterable

from .events import RelationalEvent


class RuptureStatus(str, Enum):
    ASSERTED = "asserted"
    ACKNOWLEDGED = "acknowledged"
    CONTESTED = "contested"
    UNRESOLVED = "unresolved"


class RepairResponseStatus(str, Enum):
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    DECLINED = "declined"
    HELD = "held"
    UNRESOLVED = "unresolved"


def reconstruct_repair_record(events: Iterable[RelationalEvent], rupture_id: str) -> dict:
    """Reconstruct one rupture/repair record from append-only TRIA events.

    The record is descriptive. It does not establish blame, reconciliation,
    renewed consent, or restoration of the prior relationship state.
    """

    events = list(events)
    rupture = next(
        (
            event for event in events
            if event.event_type == "RuptureRecorded"
            and event.payload.get("rupture_id") == rupture_id
        ),
        None,
    )
    if rupture is None:
        raise LookupError("Rupture record not found.")

    offers = [
        event for event in events
        if event.event_type == "RepairOffered"
        and event.payload.get("rupture_id") == rupture_id
    ]
    offer = offers[-1] if offers else None

    response = None
    outcome = None
    if offer is not None:
        repair_id = offer.payload.get("repair_id")
        responses = [
            event for event in events
            if event.event_type == "RepairResponded"
            and event.payload.get("repair_id") == repair_id
        ]
        outcomes = [
            event for event in events
            if event.event_type == "RepairOutcomeRecorded"
            and event.payload.get("repair_id") == repair_id
        ]
        response = responses[-1] if responses else None
        outcome = outcomes[-1] if outcomes else None

    return {
        "record_version": "0.1",
        "relationship_id": rupture.relationship_id,
        "rupture": {
            **dict(rupture.payload),
            "event_id": rupture.event_id,
            "recorded_by": rupture.actor_id,
        },
        "repair": {
            "repair_id": offer.payload.get("repair_id") if offer else None,
            "offered_by": offer.actor_id if offer else None,
            "status": (
                response.payload.get("status")
                if response is not None
                else ("offered" if offer is not None else "not_offered")
            ),
            "offered_actions": list(offer.payload.get("offered_actions", ())) if offer else [],
            "accepted_actions": list(response.payload.get("accepted_actions", ())) if response else [],
            "declined_actions": list(response.payload.get("declined_actions", ())) if response else [],
            "note": response.payload.get("note") if response else (offer.payload.get("note") if offer else None),
            "event_refs": [event.event_id for event in (offer, response) if event is not None],
        },
        "outcome": {
            "restored": list(outcome.payload.get("restored", ())) if outcome else [],
            "remains_changed": list(outcome.payload.get("remains_changed", ())) if outcome else [],
            "unresolved": list(outcome.payload.get("unresolved", ())) if outcome else [],
            "new_baseline_ref": outcome.payload.get("new_baseline_ref") if outcome else None,
            "next_relational_state": outcome.payload.get("next_relational_state") if outcome else None,
            "review_condition": outcome.payload.get("review_condition") if outcome else None,
            "event_id": outcome.event_id if outcome else None,
        },
        "provenance": {
            "event_refs": [
                event.event_id for event in (rupture, offer, response, outcome)
                if event is not None
            ]
        },
    }
