from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import InputValidationError, enum_field, text_field


CORRECTION_UPTAKE_SCHEMA = "tria.correction-uptake-assessment/0.1"


class CorrectionDisposition(StrEnum):
    WARRANTED = "WARRANTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNRESOLVED = "UNRESOLVED"


class DependencyKind(StrEnum):
    DERIVED_FROM = "DERIVED_FROM"
    RELIES_ON = "RELIES_ON"
    CONTEXT_ONLY = "CONTEXT_ONLY"


class PropagationAction(StrEnum):
    REEVALUATE = "REEVALUATE"
    PRESERVE = "PRESERVE"
    INQUIRE = "INQUIRE"


@dataclass(frozen=True, slots=True)
class CorrectionEvidence:
    correction_id: str
    target_ref: str
    supplied_by: str
    evidence_refs: tuple[str, ...]
    disposition: CorrectionDisposition

    def __post_init__(self):
        for name in ("correction_id", "target_ref", "supplied_by"):
            text_field(getattr(self, name), name)
        enum_field(self.disposition, CorrectionDisposition, "disposition")
        if not isinstance(self.evidence_refs, (list, tuple)) or not self.evidence_refs:
            raise InputValidationError("evidence_refs must be a non-empty sequence.")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class DependencyLink:
    source_ref: str
    dependent_ref: str
    kind: DependencyKind

    def __post_init__(self):
        text_field(self.source_ref, "source_ref")
        text_field(self.dependent_ref, "dependent_ref")
        enum_field(self.kind, DependencyKind, "kind")
        if self.source_ref == self.dependent_ref:
            raise InputValidationError("dependency links cannot be self-referential.")


@dataclass(frozen=True, slots=True)
class CorrectionUptakeAssessment:
    schema: str
    correction_id: str
    target_ref: str
    action: PropagationAction
    affected_refs: tuple[str, ...]
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    substantive_uptake_required: bool
    acknowledgement_sufficient: bool = False
    contestable: bool = True
    governance_effect: str = "none"


def _affected(target_ref, dependencies):
    propagating = {DependencyKind.DERIVED_FROM, DependencyKind.RELIES_ON}
    adjacency = {}
    for link in dependencies:
        if link.kind in propagating:
            adjacency.setdefault(link.source_ref, []).append(link.dependent_ref)

    ordered = []
    seen = set()
    queue = [target_ref]
    while queue:
        ref = queue.pop(0)
        if ref in seen:
            continue
        seen.add(ref)
        ordered.append(ref)
        queue.extend(item for item in adjacency.get(ref, ()) if item not in seen)
    return tuple(ordered)


def assess_correction_uptake(correction: CorrectionEvidence, dependencies=()) -> CorrectionUptakeAssessment:
    """Describe the reevaluation required by represented correction evidence.

    This operation is pure and advisory. A WARRANTED disposition is supplied by a
    trusted caller after separate epistemic assessment; this function does not make
    a user's correction true merely because it was asserted.
    """
    if not isinstance(correction, CorrectionEvidence):
        raise InputValidationError("correction must be CorrectionEvidence.")
    if not isinstance(dependencies, (list, tuple)):
        raise InputValidationError("dependencies must be a sequence.")
    dependencies = tuple(dependencies)
    if any(not isinstance(item, DependencyLink) for item in dependencies):
        raise InputValidationError("dependencies must contain DependencyLink values.")

    if correction.disposition is CorrectionDisposition.WARRANTED:
        affected = _affected(correction.target_ref, dependencies)
        return CorrectionUptakeAssessment(
            CORRECTION_UPTAKE_SCHEMA,
            correction.correction_id,
            correction.target_ref,
            PropagationAction.REEVALUATE,
            affected,
            (
                "The represented correction is warranted; the target and transitive epistemic dependents require reevaluation.",
                "Acknowledgement alone does not satisfy substantive uptake.",
            ),
            correction.evidence_refs,
            True,
        )

    if correction.disposition is CorrectionDisposition.UNRESOLVED:
        return CorrectionUptakeAssessment(
            CORRECTION_UPTAKE_SCHEMA,
            correction.correction_id,
            correction.target_ref,
            PropagationAction.INQUIRE,
            (),
            ("The represented correction remains unresolved and must not overwrite the target.",),
            correction.evidence_refs,
            False,
        )

    return CorrectionUptakeAssessment(
        CORRECTION_UPTAKE_SCHEMA,
        correction.correction_id,
        correction.target_ref,
        PropagationAction.PRESERVE,
        (),
        ("The represented correction is unsupported and does not authorize overwrite or dependency propagation.",),
        correction.evidence_refs,
        False,
    )
