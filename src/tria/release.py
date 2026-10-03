from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import InputValidationError, enum_field, text_field


CLAIM_RELEASE_SCHEMA = "tria.claim-release-assessment/0.1"
CLAIM_RELEASE_SPEC_VERSION = "0.2"


class AttestationVerdict(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    UNRESOLVED = "UNRESOLVED"


class EpistemicReleaseState(StrEnum):
    VERIFIED_FACT = "VERIFIED_FACT"
    STRUCTURAL_INFERENCE = "STRUCTURAL_INFERENCE"
    SYMBOLIC_HYPOTHESIS = "SYMBOLIC_HYPOTHESIS"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"


class ReleaseOutcome(StrEnum):
    RELEASE = "RELEASE"
    WITHHELD_UNSUPPORTED = "WITHHELD_UNSUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    WITHHELD_GOVERNED = "WITHHELD_GOVERNED"


@dataclass(frozen=True, slots=True)
class EvidenceAttestation:
    evidence_id: str
    issued_by: str
    subject_ref: str
    verdict: AttestationVerdict
    source_refs: tuple[str, ...]
    version_ref: str | None = None

    def __post_init__(self):
        for name in ("evidence_id", "issued_by", "subject_ref"):
            text_field(getattr(self, name), name)
        enum_field(self.verdict, AttestationVerdict, "verdict")
        if not isinstance(self.source_refs, (list, tuple)) or not self.source_refs:
            raise InputValidationError("source_refs must be a non-empty sequence.")
        object.__setattr__(self, "source_refs", tuple(self.source_refs))


@dataclass(frozen=True, slots=True)
class ClaimComponent:
    component_id: str
    content: str
    evidence_refs: tuple[str, ...] = ()
    version_ref: str | None = None
    required: bool = True

    def __post_init__(self):
        text_field(self.component_id, "component_id")
        text_field(self.content, "content")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class CandidateClaim:
    claim_id: str
    content: str
    requested_state: EpistemicReleaseState
    components: tuple[ClaimComponent, ...]
    required_disclosures: tuple[str, ...] = ()
    disclosures: tuple[str, ...] = ()

    def __post_init__(self):
        text_field(self.claim_id, "claim_id")
        text_field(self.content, "content")
        enum_field(self.requested_state, EpistemicReleaseState, "requested_state")
        if not isinstance(self.components, (list, tuple)) or not self.components:
            raise InputValidationError("components must be a non-empty sequence.")
        if any(not isinstance(item, ClaimComponent) for item in self.components):
            raise InputValidationError("components must contain ClaimComponent values.")
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "required_disclosures", tuple(self.required_disclosures))
        object.__setattr__(self, "disclosures", tuple(self.disclosures))


@dataclass(frozen=True, slots=True)
class ClaimReleaseAssessment:
    schema: str
    claim_id: str
    outcome: ReleaseOutcome
    release_state: EpistemicReleaseState
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    missing_components: tuple[str, ...] = ()
    missing_disclosures: tuple[str, ...] = ()
    contestable: bool = True
    governance_effect: str = "none"


def _support_for(component, attestations, trusted_issuers):
    referenced = [item for item in attestations if item.evidence_id in component.evidence_refs and item.issued_by in trusted_issuers]
    valid = [
        item for item in referenced
        if item.subject_ref == component.component_id
        and item.verdict is AttestationVerdict.SUPPORTS
        and (component.version_ref is None or item.version_ref == component.version_ref)
    ]
    adverse = [
        item for item in referenced
        if item.subject_ref == component.component_id
        and item.verdict is AttestationVerdict.CONTRADICTS
        and (component.version_ref is None or item.version_ref == component.version_ref)
    ]
    return valid, adverse


def assess_claim_release(candidate: CandidateClaim, attestations=(), *, trusted_issuers=()) -> ClaimReleaseAssessment:
    """Assess whether represented evidence permits the requested epistemic release state.

    This pure reference operation validates a represented evidence contract against an explicit host-bound trusted issuer set. It does not authenticate the host itself, establish metaphysical truth, or infer deceptive intent.
    """
    if not isinstance(candidate, CandidateClaim):
        raise InputValidationError("candidate must be a CandidateClaim.")
    if not isinstance(attestations, (list, tuple)):
        raise InputValidationError("attestations must be a sequence.")
    attestations = tuple(attestations)
    if any(not isinstance(item, EvidenceAttestation) for item in attestations):
        raise InputValidationError("attestations must contain EvidenceAttestation values.")
    if not isinstance(trusted_issuers, (list, tuple, set, frozenset)):
        raise InputValidationError("trusted_issuers must be a sequence or set of host-bound issuer identifiers.")
    trusted_issuers = frozenset(trusted_issuers)
    for issuer in trusted_issuers:
        text_field(issuer, "trusted_issuer")
    ids = [item.evidence_id for item in attestations]
    if len(ids) != len(set(ids)):
        raise InputValidationError("evidence_id values must be unique.")

    missing_disclosures = tuple(sorted(set(candidate.required_disclosures) - set(candidate.disclosures)))
    if missing_disclosures:
        return ClaimReleaseAssessment(
            CLAIM_RELEASE_SCHEMA, candidate.claim_id, ReleaseOutcome.WITHHELD_UNSUPPORTED,
            candidate.requested_state,
            ("Required workflow disclosures are absent.",),
            missing_disclosures=missing_disclosures,
        )

    if candidate.requested_state in {
        EpistemicReleaseState.SYMBOLIC_HYPOTHESIS,
        EpistemicReleaseState.UNRESOLVED_UNKNOWN,
    }:
        return ClaimReleaseAssessment(
            CLAIM_RELEASE_SCHEMA, candidate.claim_id, ReleaseOutcome.RELEASE,
            candidate.requested_state,
            ("The candidate is released without promotion to verified factual status.",),
        )

    missing = []
    used = []
    for component in candidate.components:
        if not component.required:
            continue
        support, adverse = _support_for(component, attestations, trusted_issuers)
        if adverse or not support:
            missing.append(component.component_id)
        used.extend(item.evidence_id for item in support)

    if missing:
        return ClaimReleaseAssessment(
            CLAIM_RELEASE_SCHEMA, candidate.claim_id, ReleaseOutcome.WITHHELD_UNSUPPORTED,
            candidate.requested_state,
            ("One or more required components lack matching independent support or have contradictory represented evidence.",),
            evidence_refs=tuple(dict.fromkeys(used)),
            missing_components=tuple(missing),
        )

    return ClaimReleaseAssessment(
        CLAIM_RELEASE_SCHEMA, candidate.claim_id, ReleaseOutcome.RELEASE,
        candidate.requested_state,
        ("Every required component satisfies the represented evidence contract for the requested release state.",),
        evidence_refs=tuple(dict.fromkeys(used)),
    )
