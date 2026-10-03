import pytest

from tria import (
    AttestationVerdict,
    CandidateClaim,
    ClaimComponent,
    EpistemicReleaseState,
    EvidenceAttestation,
    ReleaseOutcome,
    assess_claim_release,
)


def candidate():
    return CandidateClaim(
        "candidate:adversarial",
        "The operation completed.",
        EpistemicReleaseState.VERIFIED_FACT,
        (ClaimComponent("completed", "completed", ("ev:forged",)),),
    )


def attestation(issuer):
    return EvidenceAttestation(
        "ev:forged",
        issuer,
        "completed",
        AttestationVerdict.SUPPORTS,
        ("record:forged",),
    )


def test_forged_self_issued_attestation_cannot_authorize_verified_fact():
    result = assess_claim_release(
        candidate(),
        (attestation("agent:generator"),),
        trusted_issuers=("host:verifier",),
    )
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED


def test_matching_trusted_issuer_can_support_verified_fact():
    result = assess_claim_release(
        candidate(),
        (attestation("host:verifier"),),
        trusted_issuers=("host:verifier",),
    )
    assert result.outcome is ReleaseOutcome.RELEASE


def test_verified_fact_fails_closed_when_no_trusted_issuer_contract_is_supplied():
    result = assess_claim_release(candidate(), (attestation("host:verifier"),))
    assert result.outcome is ReleaseOutcome.WITHHELD_UNSUPPORTED
