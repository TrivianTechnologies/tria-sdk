"""Observed baseline gaps, NOT passing correction-conformance claims.

These witnesses assert the pinned implementation's current behavior so review
can reproduce the mismatch without changing TRIA or its frozen evidence.
"""
import pytest
import tria


def fixture():
    rel=tria.Tria().create_relationship(['human:a','agent:b'])
    target=rel.register_claim('agent:b',tria.EpistemicType.OBSERVATION,'original',source_refs=['receipt:old'])
    child=rel.register_claim('agent:b',tria.EpistemicType.INFERENCE,'derived original',derived_from=[target.claim_id])
    rel.admin.grant_permission('human:a','agent:b','truth-integrity:corrections',tria.Capability.ACT)
    correction=tria.CorrectionEvidence('correction:1',target.claim_id,'human:a',('receipt:new',),tria.CorrectionDisposition.WARRANTED)
    links=(tria.DependencyLink(target.claim_id,child.claim_id,tria.DependencyKind.DERIVED_FROM),)
    return rel,target,child,correction,links


def test_g01_unrepresented_dependency_is_accepted_in_receipt():
    rel,target,child,correction,_=fixture()
    links=(tria.DependencyLink(target.claim_id,'absent:claim',tria.DependencyKind.DERIVED_FROM),)
    receipt=tria.apply_correction_uptake(rel,'agent:b',correction,links)
    assert receipt.outcome is tria.GovernanceOutcome.ALLOW
    assert 'absent:claim' in receipt.affected_refs
    assert 'absent:claim' not in rel.state.claims
    assert rel.state.claims[child.claim_id].status.value=='ACTIVE'


def test_g02_contestation_is_not_present_in_next_runtime_context():
    rel,target,child,correction,links=fixture()
    resource='claim:'+child.claim_id
    rel.admin.grant_permission('human:a','agent:b',resource,tria.Capability.READ)
    request=tria.InvocationRequest('agent:b','inspect','local',context_resources=(resource,))
    before=tria.Runtime().prepare(rel,request).context
    tria.apply_correction_uptake(rel,'agent:b',correction,links)
    after=tria.Runtime().prepare(rel,request).context
    assert rel.state.claims[child.claim_id].status.value=='CONTESTED'
    assert before==after
    assert not hasattr(after[0],'status')


def test_g03_partial_mutation_survives_later_failure(monkeypatch):
    rel,target,child,correction,links=fixture(); original=rel.dispute_claim
    def fail_second(actor,claim_id,alternative):
        if claim_id==child.claim_id: raise RuntimeError('injected second mutation failure')
        return original(actor,claim_id,alternative)
    monkeypatch.setattr(rel,'dispute_claim',fail_second)
    with pytest.raises(RuntimeError): tria.apply_correction_uptake(rel,'agent:b',correction,links)
    assert rel.state.claims[target.claim_id].status.value=='CONTESTED'
    assert rel.state.claims[child.claim_id].status.value=='ACTIVE'
    assert not any(e.event_type=='CorrectionUptakeApplied' for e in rel.events)


def test_g03_authority_revoked_after_check_does_not_stop_mutation(monkeypatch):
    rel,target,child,correction,links=fixture(); original=rel.record_governance_decision
    def revoke_after_decision(decision,**kw):
        result=original(decision,**kw)
        if kw.get('operation')=='apply_correction_uptake':
            rel.admin.revoke_permission('human:a','agent:b','truth-integrity:corrections',tria.Capability.ACT)
        return result
    monkeypatch.setattr(rel,'record_governance_decision',revoke_after_decision)
    receipt=tria.apply_correction_uptake(rel,'agent:b',correction,links)
    assert receipt.outcome is tria.GovernanceOutcome.ALLOW
    assert rel.check_capability('agent:b','truth-integrity:corrections',tria.Capability.ACT).outcome is tria.GovernanceOutcome.BLOCK
    assert rel.state.claims[child.claim_id].status.value=='CONTESTED'
