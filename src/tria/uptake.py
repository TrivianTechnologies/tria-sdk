from __future__ import annotations

from dataclasses import dataclass

from .correction import CorrectionUptakeAssessment, PropagationAction
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


def apply_correction_uptake(relationship, actor: str, assessment: CorrectionUptakeAssessment):
    """Apply a warranted reevaluation set through ordinary TRIA ACT authority.

    This operation does not decide that a correction is warranted and does not
    rewrite claim content. It moves existing affected claims into a contested
    reevaluation state and records an attributable immutable receipt.
    """
    if not isinstance(assessment, CorrectionUptakeAssessment):
        raise InputValidationError("assessment must be CorrectionUptakeAssessment.")

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

    # The assessment is a value object, not an authority token. Require every
    # affected ref to be either the target or an existing claim with an explicit
    # provenance path back to another affected claim. This prevents arbitrary
    # blast-radius expansion by constructing a forged assessment.
    state = relationship.state
    allowed = {assessment.target_ref}
    pending = list(assessment.affected_refs[1:])
    while pending:
        progressed = False
        for ref in tuple(pending):
            claim = state.claims.get(ref)
            if claim is not None and set(claim.derived_from).intersection(allowed):
                allowed.add(ref)
                pending.remove(ref)
                progressed = True
        if not progressed:
            return CorrectionApplicationReceipt(
                assessment.correction_id,
                actor,
                GovernanceOutcome.BLOCK,
                (),
                "Affected refs contain a claim without an explicit provenance path from the correction target.",
            )

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
