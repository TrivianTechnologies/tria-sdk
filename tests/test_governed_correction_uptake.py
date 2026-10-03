import pytest

from tria import (
    Capability,
    CorrectionDisposition,
    CorrectionEvidence,
    CorrectionUptakeAssessment,
    DependencyKind,
    DependencyLink,
    EpistemicType,
    GovernanceOutcome,
    PropagationAction,
    Tria,
    apply_correction_uptake,
    assess_correction_uptake,
)


def setup_relationship():
    rel = Tria().create_relationship(["human:a", "agent:b"])
    source = rel.register_claim(
        "agent:b",
        EpistemicType.OBSERVATION,
        "The deployment succeeded.",
        source_refs=["receipt:old"],
    )
    summary = rel.register_claim(
        "agent:b",
        EpistemicType.INFERENCE,
        "The release is ready.",
        derived_from=[source.claim_id],
    )
    return rel, source.claim_id, summary.claim_id


def warranted(target):
    return CorrectionEvidence(
        "correction:1",
        target,
        "human:a",
        ("receipt:corrected",),
        CorrectionDisposition.WARRANTED,
    )


def test_governed_uptake_requires_actor_act_authority():
    rel, source, summary = setup_relationship()
    assessment = assess_correction_uptake(
        warranted(source),
        (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),),
    )
    receipt = apply_correction_uptake(rel, "agent:b", warranted(source), (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),), assessment)
    assert receipt.outcome is GovernanceOutcome.BLOCK
    assert rel.state.claims[source].status.value == "ACTIVE"
    assert rel.state.claims[summary].status.value == "ACTIVE"


def test_governed_uptake_marks_target_and_dependents_for_reevaluation():
    rel, source, summary = setup_relationship()
    rel.admin.grant_permission("tria:system", "agent:b", "truth-integrity:corrections", Capability.ACT)
    assessment = assess_correction_uptake(
        warranted(source),
        (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),),
    )
    receipt = apply_correction_uptake(rel, "agent:b", warranted(source), (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),), assessment)
    assert receipt.outcome is GovernanceOutcome.ALLOW
    assert receipt.affected_refs == (source, summary)
    assert rel.state.claims[source].status.value == "CONTESTED"
    assert rel.state.claims[summary].status.value == "CONTESTED"


def test_uptake_writes_attributable_immutable_receipt_events():
    rel, source, summary = setup_relationship()
    rel.admin.grant_permission("tria:system", "agent:b", "truth-integrity:corrections", Capability.ACT)
    assessment = assess_correction_uptake(
        warranted(source),
        (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),),
    )
    receipt = apply_correction_uptake(rel, "agent:b", warranted(source), (DependencyLink(source, summary, DependencyKind.DERIVED_FROM),), assessment)
    events = [e for e in rel.events if e.event_type == "CorrectionUptakeApplied"]
    assert len(events) == 1
    assert events[0].actor_id == "agent:b"
    assert events[0].payload["correction_id"] == "correction:1"
    assert tuple(events[0].payload["affected_refs"]) == receipt.affected_refs
    assert rel.audit()["chain_valid"] is True


def test_non_reevaluation_assessment_cannot_mutate_state():
    rel, source, _ = setup_relationship()
    rel.admin.grant_permission("tria:system", "agent:b", "truth-integrity:corrections", Capability.ACT)
    unsupported = assess_correction_uptake(
        CorrectionEvidence(
            "correction:2", source, "human:a", ("record:x",), CorrectionDisposition.UNSUPPORTED
        ),
        (),
    )
    receipt = apply_correction_uptake(rel, "agent:b", CorrectionEvidence("correction:2", source, "human:a", ("record:x",), CorrectionDisposition.UNSUPPORTED), (), unsupported)
    assert receipt.outcome is GovernanceOutcome.BLOCK
    assert not [e for e in rel.events if e.event_type == "CorrectionUptakeApplied"]


def test_caller_cannot_expand_affected_refs_beyond_assessment():
    rel, source, summary = setup_relationship()
    rel.admin.grant_permission("tria:system", "agent:b", "truth-integrity:corrections", Capability.ACT)
    assessment = assess_correction_uptake(warranted(source), ())
    forged = CorrectionUptakeAssessment(
        assessment.schema,
        assessment.correction_id,
        assessment.target_ref,
        PropagationAction.REEVALUATE,
        assessment.affected_refs + (summary,),
        assessment.reasons,
        assessment.evidence_refs,
        True,
    )
    receipt = apply_correction_uptake(rel, "agent:b", warranted(source), (), forged)
    assert receipt.outcome is GovernanceOutcome.BLOCK
