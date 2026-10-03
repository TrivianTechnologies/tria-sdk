from __future__ import annotations

from dataclasses import dataclass

from .errors import InputValidationError, text_field
from .types import Capability, GovernanceOutcome


EVIDENCE_RESOURCE = "truth-integrity:evidence"


@dataclass(frozen=True, slots=True)
class EvidenceInspection:
    requested_by: str
    claim_id: str
    outcome: GovernanceOutcome
    evidence_refs: tuple[str, ...]
    reason: str


def inspect_truth_integrity_evidence(relationship, actor: str, claim_id: str, evidence_refs=()):
    """Govern participant inspection of evidence references used by integrity surfaces.

    READ permits inspection inside the relationship. This operation does not grant
    DISCLOSE and does not authenticate or dereference external evidence.
    """
    relationship._participant(actor)
    text_field(claim_id, "claim_id")
    if not isinstance(evidence_refs, (list, tuple)):
        raise InputValidationError("evidence_refs must be a sequence.")
    evidence_refs = tuple(evidence_refs)
    for ref in evidence_refs:
        text_field(ref, "evidence_ref")

    decision = relationship.check_capability(actor, EVIDENCE_RESOURCE, Capability.READ)
    relationship.record_governance_decision(
        decision,
        operation="inspect_truth_integrity_evidence",
        actor=actor,
        claim_id=claim_id,
    )
    if decision.outcome is not GovernanceOutcome.ALLOW:
        return EvidenceInspection(actor, claim_id, decision.outcome, (), decision.reason)

    return EvidenceInspection(
        actor,
        claim_id,
        GovernanceOutcome.ALLOW,
        tuple(dict.fromkeys(evidence_refs)),
        "Current READ authority permits inspection of represented evidence references; source authenticity and external disclosure remain separate.",
    )
