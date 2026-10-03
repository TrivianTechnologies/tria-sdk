from __future__ import annotations

from dataclasses import dataclass

from .correction import CorrectionEvidence, CorrectionUptakeAssessment, DependencyLink, PropagationAction, assess_correction_uptake
from .errors import InputValidationError
from .types import Capability, GovernanceOutcome


CORRECTION_RESOURCE = "truth-integrity:corrections"


@dataclass(frozen=True, slots=True)
class CorrectionApplicationReceipt:
    correction_id: str
    requested_by: str
    outcome: GovernanceOutcome
    affected_refs: tuple[str, ...]
    reason: str
    event_id: str | None = None


def apply_correction_uptake(relationship, actor: str, correction: CorrectionEvidence, dependencies=(), assessment: CorrectionUptakeAssessment | None = None):
    """Apply a warranted reevaluation set through ordinary TRIA ACT authority.

    This operation does not decide that a correction is warranted and does not
    rewrite claim content. It moves existing affected claims into a contested
    reevaluation state and records an attributable immutable receipt.
    """
    if not isinstance(correction, CorrectionEvidence):
        raise InputValidationError("correction must be CorrectionEvidence.")
    if not isinstance(dependencies, (list, tuple)) or any(not isinstance(item, DependencyLink) for item in dependencies):
        raise InputValidationError("dependencies must contain DependencyLink values.")
    canonical = assess_correction_uptake(correction, tuple(dependencies))
    if assessment is None:
        assessment = canonical
    if not isinstance(assessment, CorrectionUptakeAssessment):
        raise InputValidationError("assessment must be CorrectionUptakeAssessment.")
    if assessment != canonical:
        return CorrectionApplicationReceipt(
            correction.correction_id,
            actor,
            GovernanceOutcome.BLOCK,
            (),
            "Supplied assessment does not match deterministic correction propagation for the supplied correction and dependencies.",
        )

    relationship._participant(actor)
    decision = relationship.check_capability(actor, CORRECTION_RESOURCE, Capability.ACT)
    relationship.record_governance_decision(
        decision,
        operation="apply_correction_uptake",
        actor=actor,
        correction_id=assessment.correction_id,
    )
    if decision.outcome is not GovernanceOutcome.ALLOW:
        return CorrectionApplicationReceipt(
            assessment.correction_id, actor, decision.outcome, (), decision.reason
        )

    if (
        assessment.action is not PropagationAction.REEVALUATE
        or not assessment.substantive_uptake_required
        or not assessment.affected_refs
        or assessment.affected_refs[0] != assessment.target_ref
    ):
        return CorrectionApplicationReceipt(
            assessment.correction_id,
            actor,
            GovernanceOutcome.BLOCK,
            (),
            "Only a substantive REEVALUATE assessment rooted at its correction target may mutate claim state.",
        )

    # Recomputed exact assessment above prevents caller expansion or shrinkage.

    causal = []
    for ref in assessment.affected_refs:
        if ref in relationship.state.claims:
            event = relationship.dispute_claim(
                actor,
                ref,
                f"Reevaluation required by warranted correction {assessment.correction_id}.",
            )
            causal.append(event.event_id)

    receipt_event = relationship._commit(
        "CorrectionUptakeApplied",
        actor,
        {
            "correction_id": assessment.correction_id,
            "target_ref": assessment.target_ref,
            "affected_refs": list(assessment.affected_refs),
            "evidence_refs": list(assessment.evidence_refs),
            "action": assessment.action.value,
        },
        tuple(causal),
    )
    return CorrectionApplicationReceipt(
        assessment.correction_id,
        actor,
        GovernanceOutcome.ALLOW,
        assessment.affected_refs,
        "Warranted correction uptake applied; affected claims are contested pending reevaluation.",
        receipt_event.event_id,
    )
