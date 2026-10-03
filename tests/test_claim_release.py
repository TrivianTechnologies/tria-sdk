import pytest

from tria import (
    AttestationVerdict,
    CandidateClaim,
    ClaimComponent,
    EvidenceAttestation,
    EpistemicReleaseState,
    ReleaseOutcome,
    assess_claim_release,
)


def attestation(evidence_id, component_id, verdict=AttestationVerdict.SUPPORTS, *, version_ref=None):
    return EvidenceAttestation(
        evidence_id=evidence_id,
        issued_by="host:verifier",
        subject_ref=component_id,
        verdict=verdict,
        source_refs=(f"record:{evidence_id}",),
        version_ref=version_ref,
    )


def candidate(*components, requested=EpistemicReleaseState.VERIFIED_FACT, required_disclosures=(), disclosures=()):
    return CandidateClaim(
        claim_id="candidate:1",
        content="candidate output",
        requested_state=requested,
        components=tuple(components),
        required_disclosures=tuple(required_disclosures),
        disclosures=tuple(disclosures),
    )


def component(component_id, *evidence_ids, version_ref=None):
    return ClaimComponent(component_id, component_id, tuple(evidence_ids), version_ref=version_ref)


def test_verified_fact_requires_independent_support():
    claim = candidate(component("tests-passed", "ev:tests"))
    result = assess_claim_release(claim, (attestation("ev:tests", "tests-passed"),), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.RELEASE
    assert result.release_state is EpistemicReleaseState.VERIFIED_FACT


def test_generator_cannot_self_certify_with_unknown_evidence_id():
    claim = candidate(component("completed", "ev:model-says-so"))
    result = assess_claim_release(claim, (), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_contradictory_evidence_blocks_verified_fact():
    claim = candidate(component("completed", "ev:receipt"))
    result = assess_claim_release(\n        claim,\n        (attestation("ev:receipt", "completed", AttestationVerdict.CONTRADICTS),),\n        trusted_issuers=("host:verifier",),\n    )
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_composite_inherits_weakest_required_component():
    claim = candidate(
        component("tests-passed", "ev:tests"),
        component("deployment-succeeded", "ev:deploy"),
    )
    result = assess_claim_release(claim, (attestation("ev:tests", "tests-passed"),), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_symbolic_hypothesis_cannot_be_represented_as_verified_fact():
    claim = candidate(
        component("symbolic-reading"),
        requested=EpistemicReleaseState.SYMBOLIC_HYPOTHESIS,
    )
    result = assess_claim_release(claim, (), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.RELEASE
    assert result.release_state is EpistemicReleaseState.SYMBOLIC_HYPOTHESIS


def test_memory_claim_without_record_is_unresolved():
    claim = candidate(component("memory:prior-decision", "ev:memory"))
    result = assess_claim_release(claim, (), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_version_mismatch_does_not_support_current_claim():
    claim = candidate(component("tests-passed", "ev:tests", version_ref="commit:new"))
    result = assess_claim_release(\n        claim,\n        (attestation("ev:tests", "tests-passed", version_ref="commit:old"),),\n        trusted_issuers=("host:verifier",),\n    )
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_required_disclosure_omission_blocks_release():
    claim = candidate(
        component("report", "ev:report"),
        required_disclosures=("failed_checks", "scope_limitations"),
        disclosures=("scope_limitations",),
    )
    result = assess_claim_release(claim, (attestation("ev:report", "report"),), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED
    assert "failed_checks" in result.missing_disclosures


def test_structural_inference_can_release_without_being_promoted_to_fact():
    claim = candidate(
        component("premise", "ev:premise"),
        requested=EpistemicReleaseState.STRUCTURAL_INFERENCE,
    )
    result = assess_claim_release(claim, (attestation("ev:premise", "premise"),), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.RELEASE
    assert result.release_state is EpistemicReleaseState.STRUCTURAL_INFERENCE


def test_unknown_is_a_valid_nonfabricated_release_state():
    claim = candidate(
        component("unknown"),
        requested=EpistemicReleaseState.UNRESOLVED_UNKNOWN,
    )
    result = assess_claim_release(claim, (), trusted_issuers=("host:verifier",))
    assert result.outcome is ReleaseOutcome.RELEASE
    assert result.release_state is EpistemicReleaseState.UNRESOLVED_UNKNOWN
