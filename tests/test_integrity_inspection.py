import pytest

from tria import (
    Capability,
    GovernanceOutcome,
    Tria,
    inspect_truth_integrity_evidence,
)


def relationship():
    return Tria().create_relationship(["human:a", "agent:b"])


def test_participant_without_read_cannot_inspect_integrity_evidence():
    rel = relationship()
    result = inspect_truth_integrity_evidence(
        rel, "human:a", "claim:1", ("record:1", "record:2")
    )
    assert result.outcome is GovernanceOutcome.BLOCK
    assert result.evidence_refs == ()


def test_participant_with_read_can_inspect_same_evidence_refs_used_by_boundary():
    rel = relationship()
    rel.admin.grant_permission(
        "tria:system", "human:a", "truth-integrity:evidence", Capability.READ
    )
    result = inspect_truth_integrity_evidence(
        rel, "human:a", "claim:1", ("record:1", "record:2")
    )
    assert result.outcome is GovernanceOutcome.ALLOW
    assert result.claim_id == "claim:1"
    assert result.evidence_refs == ("record:1", "record:2")


def test_inspection_is_audited_but_does_not_change_claim_state():
    rel = relationship()
    rel.admin.grant_permission(
        "tria:system", "human:a", "truth-integrity:evidence", Capability.READ
    )
    before_claims = rel.state.claims
    result = inspect_truth_integrity_evidence(rel, "human:a", "claim:1", ("record:1",))
    assert result.outcome is GovernanceOutcome.ALLOW
    assert rel.state.claims == before_claims
    assert any(
        e.event_type == "GovernanceEvaluated"
        and e.payload.get("operation") == "inspect_truth_integrity_evidence"
        for e in rel.events
    )
