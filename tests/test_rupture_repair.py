import pytest

import tria
from tria.errors import InputValidationError
from tria.repair import (
    RepairResponseStatus,
    RuptureStatus,
    reconstruct_repair_record,
)


def _relationship():
    return tria.Tria().create_relationship(["human", "agent"])


def test_repair_preserves_rupture_and_persistent_change():
    rel = _relationship()
    rupture = rel.record_rupture(
        "human",
        affected_scope=("scheduling", "personalization"),
        expectation_or_boundary="Current instruction should supersede stale inference.",
        observed_impact="An unwanted scheduling action occurred.",
        status=RuptureStatus.ACKNOWLEDGED,
    )
    offer = rel.offer_repair(
        "agent",
        rupture.payload["rupture_id"],
        offered_actions=("correct scheduling state", "disable stale inference"),
    )
    rel.respond_to_repair(
        "human",
        offer.payload["repair_id"],
        RepairResponseStatus.ACCEPTED,
        accepted_actions=("correct scheduling state", "disable stale inference"),
    )
    outcome = rel.record_repair_outcome(
        "agent",
        offer.payload["repair_id"],
        restored=("current scheduling state",),
        remains_changed=("future scheduling authority is narrower",),
        unresolved=("trust state is not asserted as restored",),
    )

    record = reconstruct_repair_record(rel.events, rupture.payload["rupture_id"])
    assert record["rupture"]["event_id"] == rupture.event_id
    assert record["outcome"]["event_id"] == outcome.event_id
    assert record["outcome"]["restored"] == ["current scheduling state"]
    assert record["outcome"]["remains_changed"] == ["future scheduling authority is narrower"]


def test_declined_repair_cannot_be_recorded_as_completed_outcome():
    rel = _relationship()
    rupture = rel.record_rupture(
        "human",
        affected_scope=("memory",),
        expectation_or_boundary="Do not retain this context.",
        observed_impact="Context remained operative.",
    )
    offer = rel.offer_repair(
        "agent",
        rupture.payload["rupture_id"],
        offered_actions=("delete retained payload",),
    )
    rel.respond_to_repair(
        "human",
        offer.payload["repair_id"],
        RepairResponseStatus.DECLINED,
        declined_actions=("delete retained payload",),
    )

    with pytest.raises(InputValidationError):
        rel.record_repair_outcome(
            "agent",
            offer.payload["repair_id"],
            restored=(),
            remains_changed=("relationship remains ruptured",),
            unresolved=("future handling remains unresolved",),
        )


def test_response_actions_must_match_offer():
    rel = _relationship()
    rupture = rel.record_rupture(
        "human",
        affected_scope=("scope",),
        expectation_or_boundary="Boundary.",
        observed_impact="Impact.",
    )
    offer = rel.offer_repair(
        "agent",
        rupture.payload["rupture_id"],
        offered_actions=("action-a",),
    )

    with pytest.raises(InputValidationError):
        rel.respond_to_repair(
            "human",
            offer.payload["repair_id"],
            RepairResponseStatus.ACCEPTED,
            accepted_actions=("invented-action",),
        )


def test_repair_events_do_not_modify_consent():
    rel = _relationship()
    rel.grant_consent("human", "persistent_context")
    before = rel.state.consent

    rupture = rel.record_rupture(
        "human",
        affected_scope=("persistent_context",),
        expectation_or_boundary="Current consent scope should be respected.",
        observed_impact="Scope dispute.",
    )
    rel.offer_repair(
        "agent",
        rupture.payload["rupture_id"],
        offered_actions=("review consent boundary",),
    )

    assert rel.state.consent == before
