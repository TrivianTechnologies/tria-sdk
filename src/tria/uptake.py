from __future__ import annotations

from dataclasses import dataclass

from .correction import CorrectionEvidence, CorrectionUptakeAssessment, DependencyLink, DependencyKind, PropagationAction, assess_correction_uptake
from .events import EventProposal, RelationalEvent
from .errors import InputValidationError, text_field
from .types import Capability, GovernanceOutcome


CORRECTION_RESOURCE = "truth-integrity:corrections"
CORRECTION_SAFETY_VERSION = "0.1"


@dataclass(frozen=True, slots=True)
class CorrectionApplicationReceipt:
    correction_id: str
    requested_by: str
    outcome: GovernanceOutcome
    affected_refs: tuple[str, ...]
    reason: str
    event_id: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectionGraphSnapshot:
    target_ref: str
    head_hash: str
    dependencies: tuple[DependencyLink, ...]

    def __post_init__(self):
        if type(self.target_ref) is not str:
            raise InputValidationError("snapshot target_ref must be a string.")
        text_field(self.target_ref, "target_ref")
        if (type(self.head_hash) is not str or len(self.head_hash) != 64
                or any(c not in "0123456789abcdef" for c in self.head_hash)):
            raise InputValidationError("snapshot head_hash must be a lowercase SHA-256 event hash.")
        if type(self.dependencies) is not tuple or any(type(link) is not DependencyLink for link in self.dependencies):
            raise InputValidationError("snapshot dependencies must be a tuple of DependencyLink values.")


def _stored_dependencies(state, target_ref):
    if target_ref not in state.claims:
        raise InputValidationError("Correction target must be a current canonical claim.")
    affected = {target_ref}
    while True:
        expanded = affected | {ref for ref, claim in state.claims.items()
                               if affected.intersection(claim.derived_from)}
        if expanded == affected:
            break
        affected = expanded
    links = []
    for child in sorted(affected):
        parents = state.claims[child].derived_from
        if len(parents) != len(set(parents)) or any(p not in state.claims for p in parents):
            raise InputValidationError("Affected claim provenance contains duplicate or missing canonical parents.")
        for parent in sorted(parents):
            if parent in affected:
                links.append(DependencyLink(parent, child, DependencyKind.DERIVED_FROM))
    # Canonical provenance must be acyclic, unlike the advisory graph walker.
    visiting, visited = set(), set()
    def visit(ref):
        if ref in visiting:
            raise InputValidationError("Canonical claim provenance is cyclic.")
        if ref in visited:
            return
        visiting.add(ref)
        for parent in state.claims[ref].derived_from:
            if parent in affected:
                visit(parent)
        visiting.remove(ref)
        visited.add(ref)
    for ref in sorted(affected):
        visit(ref)
    return tuple(links)


def snapshot_correction_graph(relationship, target_ref):
    """Host-level read-only snapshot, not a permission or truth attestation."""
    with relationship.execution_guard():
        relationship.require_valid()
        links = _stored_dependencies(relationship.state, target_ref)
        return CorrectionGraphSnapshot(target_ref, relationship.events[-1].event_hash, links)


def apply_correction_uptake(relationship, actor: str, correction: CorrectionEvidence, dependencies=(), assessment: CorrectionUptakeAssessment | None = None, *, expected_head: str | None = None):
    """Validate current canonical closure and atomically contest it under ACT.

    expected_head binds an earlier host snapshot. Without it the operation is a
    fresh application of the supplied graph, not a claim of snapshot continuity.
    The governed Rosetta profile must supply it. Host non-claim links remain
    advisory and cannot be passed to this canonical-claim mutation path.
    """
    if not isinstance(correction, CorrectionEvidence):
        raise InputValidationError("correction must be CorrectionEvidence.")
    if not isinstance(dependencies, (list, tuple)) or any(not isinstance(x, DependencyLink) for x in dependencies):
        raise InputValidationError("dependencies must contain DependencyLink values.")
    if expected_head is not None and (type(expected_head) is not str or not expected_head):
        raise InputValidationError("expected_head must be a nonempty event hash.")
    def blocked(reason, outcome=GovernanceOutcome.BLOCK):
        return CorrectionApplicationReceipt(correction.correction_id, actor, outcome, (), reason)
    with relationship.execution_guard():
        relationship._participant(actor)
        before = tuple(relationship.events)
        if expected_head is not None and expected_head != before[-1].event_hash:
            return blocked("Correction snapshot is stale; take a fresh canonical snapshot.")
        try:
            stored = _stored_dependencies(relationship.state, correction.target_ref)
        except InputValidationError as error:
            return blocked(str(error))
        supplied = tuple(dependencies)
        if len(set(supplied)) != len(supplied) or set(supplied) != set(stored):
            return blocked("Supplied graph is incomplete or inconsistent with current canonical claim provenance.")
        represented = assess_correction_uptake(correction, supplied)
        if assessment is not None and assessment != represented:
            return blocked("Supplied assessment does not match its correction and graph.")
        canonical = assess_correction_uptake(correction, stored)
        if canonical.action is not PropagationAction.REEVALUATE or not canonical.substantive_uptake_required:
            return blocked("Only warranted substantive reevaluation can mutate claim state.")
        decision = relationship.check_capability(actor, CORRECTION_RESOURCE, Capability.ACT)
        if tuple(relationship.events) != before:
            return blocked("Relationship changed during authority evaluation.")
        recorded = relationship.record_governance_decision(decision, operation="apply_correction_uptake", actor=actor, correction_id=correction.correction_id)
        if tuple(relationship.events) != before + (recorded,):
            return blocked("Relationship changed during correction authorization recording.")
        if decision.outcome is not GovernanceOutcome.ALLOW:
            return blocked(decision.reason, decision.outcome)
        head = tuple(relationship.events)
        sequence = 1 + max((e.actor_sequence for e in head if e.actor_id == actor), default=0)
        previous = head[-1].event_hash
        pending = []
        for ref in canonical.affected_refs:
            event = RelationalEvent.commit(EventProposal(relationship.relationship_id, "ClaimDisputed", actor,
                {"claim_id": ref, "alternative": f"Reevaluation required by warranted correction {correction.correction_id}."}, sequence), previous)
            pending.append(event)
            sequence += 1
            previous = event.event_hash
        receipt = RelationalEvent.commit(EventProposal(relationship.relationship_id, "CorrectionUptakeApplied", actor,
            {"correction_id": correction.correction_id, "target_ref": correction.target_ref,
             "affected_refs": canonical.affected_refs, "evidence_refs": canonical.evidence_refs,
             "action": canonical.action.value}, sequence, tuple(e.event_id for e in pending)), previous)
        pending.append(receipt)
        final = relationship.check_capability(actor, CORRECTION_RESOURCE, Capability.ACT)
        if tuple(relationship.events) != head:
            return blocked("Relationship changed before atomic correction commit.")
        if final.outcome is not GovernanceOutcome.ALLOW:
            return blocked(final.reason, final.outcome)
        # Built-in stores atomically compare predecessor/sequence and append the
        # complete batch; exceptions leave no correction disputes or receipt.
        relationship._store.append_many(pending)
        return CorrectionApplicationReceipt(correction.correction_id, actor, GovernanceOutcome.ALLOW,
            canonical.affected_refs, "Canonical correction reevaluation committed atomically.", receipt.event_id)
