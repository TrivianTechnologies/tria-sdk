import pytest

from tria import (
    CorrectionDisposition,
    CorrectionEvidence,
    DependencyKind,
    DependencyLink,
    PropagationAction,
    assess_correction_uptake,
)


def deps():
    return (
        DependencyLink("claim:source", "claim:summary", DependencyKind.DERIVED_FROM),
        DependencyLink("claim:summary", "plan:next", DependencyKind.RELIES_ON),
        DependencyLink("claim:source", "note:unrelated", DependencyKind.CONTEXT_ONLY),
    )


def correction(*, warranted=True):
    return CorrectionEvidence(
        correction_id="correction:1",
        target_ref="claim:source",
        supplied_by="human:a",
        evidence_refs=("record:correction:1",),
        disposition=(
            CorrectionDisposition.WARRANTED
            if warranted
            else CorrectionDisposition.UNSUPPORTED
        ),
    )


def test_warranted_correction_invalidates_transitive_required_dependents():
    result = assess_correction_uptake(correction(), deps())
    assert result.action is PropagationAction.REEVALUATE
    assert result.affected_refs == ("claim:source", "claim:summary", "plan:next")


def test_context_only_link_does_not_create_invalidation():
    result = assess_correction_uptake(correction(), deps())
    assert "note:unrelated" not in result.affected_refs


def test_unsupported_correction_does_not_overwrite_or_propagate():
    result = assess_correction_uptake(correction(warranted=False), deps())
    assert result.action is PropagationAction.PRESERVE
    assert result.affected_refs == ()
    assert result.contestable is True


def test_acknowledgement_without_reevaluation_is_not_substantive_uptake():
    result = assess_correction_uptake(correction(), deps())
    assert result.substantive_uptake_required is True
    assert result.acknowledgement_sufficient is False


def test_cycles_terminate_and_each_dependency_is_reported_once():
    cyclic = deps() + (
        DependencyLink("plan:next", "claim:source", DependencyKind.RELIES_ON),
    )
    result = assess_correction_uptake(correction(), cyclic)
    assert result.affected_refs == ("claim:source", "claim:summary", "plan:next")


def test_missing_target_dependency_still_requires_target_reevaluation():
    result = assess_correction_uptake(correction(), ())
    assert result.affected_refs == ("claim:source",)
