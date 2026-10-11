# SPDX-License-Identifier: MPL-2.0
"""Current remediation tests; original failure witnesses remain in evidence/."""
import threading
from dataclasses import replace
import pytest
import tria


def test_missing_target_never_mutates(scenario):
    _,rel,_,_,_=scenario
    correction=tria.CorrectionEvidence('correction:missing','missing','human:a',('receipt:new',),tria.CorrectionDisposition.WARRANTED)
    before=tuple(rel.events)
    with pytest.raises(tria.InputValidationError): tria.snapshot_correction_graph(rel,'missing')
    assert tria.apply_correction_uptake(rel,'agent:b',correction).outcome is tria.GovernanceOutcome.BLOCK
    assert tuple(rel.events)==before


@pytest.mark.parametrize('malformation',['missing_parent','duplicate_parent','cycle'])
def test_malformed_projected_provenance_never_mutates(scenario,monkeypatch,malformation):
    _,rel,source,child,correction=scenario
    state=rel.state; claims=dict(state.claims)
    if malformation=='cycle': claims[source]=replace(claims[source],derived_from=(child,))
    else: claims[child]=replace(claims[child],derived_from=(source,'missing') if malformation=='missing_parent' else (source,source))
    state=replace(state,claims=claims)
    # Simulate malformed projected state, without inventing or changing events.
    monkeypatch.setattr(type(rel),'state',property(lambda self: state))
    before=tuple(rel.events)
    with pytest.raises(tria.InputValidationError): tria.snapshot_correction_graph(rel,source)
    assert tria.apply_correction_uptake(rel,'agent:b',correction).outcome is tria.GovernanceOutcome.BLOCK
    assert tuple(rel.events)==before


@pytest.mark.parametrize('status',list(tria.ClaimStatus))
@pytest.mark.parametrize('adapter',[tria.OpenAIResponsesAdapter,tria.AnthropicMessagesAdapter])
def test_existing_status_values_reach_consumers(scenario,monkeypatch,status,adapter):
    _,rel,_,child,_=scenario
    rel.admin.grant_permission('human:a','agent:b','claim:'+child,tria.Capability.READ)
    state=rel.state
    state=replace(state,claims={**state.claims,child:replace(state.claims[child],status=status)})
    # Compatible state-producer fixture: this does not assert a lifecycle API.
    monkeypatch.setattr(type(rel),'state',property(lambda self: state))
    request=tria.InvocationRequest('agent:b','inspect','local',context_resources=('claim:'+child,))
    plan=tria.Runtime().prepare(rel,request)
    assert plan.context[0].claim_status==status.value
    assert status.value in str(adapter().translate(plan,model='local').payload)


@pytest.fixture(params=['memory', 'sqlite'])
def scenario(request, tmp_path):
    store=tria.InMemoryEventStore() if request.param=='memory' else tria.SQLiteEventStore(tmp_path/'state.sqlite')
    rel=tria.Tria(store).create_relationship(['human:a','agent:b'])
    source=rel.register_claim('agent:b',tria.EpistemicType.OBSERVATION,'source',source_refs=['receipt:old'])
    child=rel.register_claim('agent:b',tria.EpistemicType.INFERENCE,'derived',derived_from=[source.claim_id])
    rel.admin.grant_permission('human:a','agent:b','truth-integrity:corrections',tria.Capability.ACT)
    correction=tria.CorrectionEvidence('correction:1',source.claim_id,'human:a',('receipt:new',),tria.CorrectionDisposition.WARRANTED)
    yield store,rel,source.claim_id,child.claim_id,correction
    if hasattr(store,'close'): store.close()


def apply(rel, correction):
    snapshot=tria.snapshot_correction_graph(rel,correction.target_ref)
    return tria.apply_correction_uptake(rel,'agent:b',correction,snapshot.dependencies,expected_head=snapshot.head_hash)


def test_exact_closure_commits_once_with_causal_receipt(scenario):
    _,rel,source,child,correction=scenario
    before=tuple(rel.events); result=apply(rel,correction)
    assert result.outcome is tria.GovernanceOutcome.ALLOW
    assert result.affected_refs==(source,child)
    assert tuple(rel.events[:len(before)])==before
    assert all(rel.state.claims[c].status is tria.ClaimStatus.CONTESTED for c in (source,child))
    assert rel.events[-1].event_type=='CorrectionUptakeApplied'
    assert rel.events[-1].causal_parents==tuple(e.event_id for e in rel.events[-3:-1])
    assert rel.audit()['chain_valid']


@pytest.mark.parametrize('kind',['omitted','fabricated','duplicate','nonclaim'])
def test_graph_mismatch_never_mutates(scenario,kind):
    _,rel,source,child,correction=scenario
    good=tria.snapshot_correction_graph(rel,source).dependencies
    links={'omitted':(), 'fabricated':(tria.DependencyLink(source,'missing',tria.DependencyKind.DERIVED_FROM),),
           'duplicate':good+good,'nonclaim':good+(tria.DependencyLink(source,'plan:host',tria.DependencyKind.RELIES_ON),)}[kind]
    before=tuple(rel.events)
    assert tria.apply_correction_uptake(rel,'agent:b',correction,links).outcome is tria.GovernanceOutcome.BLOCK
    assert tuple(rel.events)==before


def test_stale_snapshot_rejected(scenario):
    _,rel,source,child,correction=scenario
    snap=tria.snapshot_correction_graph(rel,source)
    rel.register_claim('agent:b',tria.EpistemicType.INFERENCE,'new child',derived_from=[source])
    assert tria.apply_correction_uptake(rel,'agent:b',correction,snap.dependencies,expected_head=snap.head_hash).outcome is tria.GovernanceOutcome.BLOCK
    assert rel.state.claims[source].status is tria.ClaimStatus.ACTIVE


@pytest.mark.parametrize('head',[None,'',' ',False,123,b'a'*64,'a'*63,'a'*65,'g'*64,'A'*64])
def test_snapshot_constructor_rejects_invalid_head(scenario,head):
    _,rel,source,child,_=scenario
    snapshot=tria.snapshot_correction_graph(rel,source)
    before=tuple(rel.events)
    with pytest.raises(tria.InputValidationError):
        tria.CorrectionGraphSnapshot(source,head,snapshot.dependencies)
    assert tuple(rel.events)==before


def test_reentrant_revocation_before_commit_blocks_all_mutations(scenario,monkeypatch):
    _,rel,source,child,correction=scenario; original=rel.record_governance_decision
    def revoke(decision,**kwargs):
        event=original(decision,**kwargs)
        rel.admin.revoke_permission('human:a','agent:b','truth-integrity:corrections',tria.Capability.ACT)
        return event
    monkeypatch.setattr(rel,'record_governance_decision',revoke)
    assert apply(rel,correction).outcome is tria.GovernanceOutcome.BLOCK
    assert all(rel.state.claims[c].status is tria.ClaimStatus.ACTIVE for c in (source,child))
    assert not any(e.event_type=='CorrectionUptakeApplied' for e in rel.events)


def test_batch_failure_leaves_no_disputes_and_can_recover(scenario,monkeypatch):
    store,rel,source,child,correction=scenario
    if isinstance(store,tria.SQLiteEventStore):
        store._session.conn.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON events WHEN json_extract(NEW.event_json,'$.event_type')='CorrectionUptakeApplied' BEGIN SELECT RAISE(ABORT,'injected'); END")
    else:
        original=tria.RelationalEvent.verify_hash
        def fail(event):
            if event.event_type=='CorrectionUptakeApplied': raise RuntimeError('injected validation failure')
            return original(event)
        monkeypatch.setattr(tria.RelationalEvent,'verify_hash',fail)
    with pytest.raises(Exception): apply(rel,correction)
    assert all(rel.state.claims[c].status is tria.ClaimStatus.ACTIVE for c in (source,child))
    assert not any(e.event_type in ('ClaimDisputed','CorrectionUptakeApplied') for e in rel.events)
    if isinstance(store,tria.SQLiteEventStore): store._session.conn.execute('DROP TRIGGER reject_receipt')
    else: monkeypatch.setattr(tria.RelationalEvent,'verify_hash',original)
    assert apply(rel,correction).outcome is tria.GovernanceOutcome.ALLOW
    assert rel.audit()['chain_valid']


def test_revocation_thread_wins_before_correction_guard(scenario):
    _,rel,source,child,correction=scenario
    with rel.execution_guard():
        thread=threading.Thread(target=lambda: apply(rel,correction))
        thread.start()
        rel.admin.revoke_permission('human:a','agent:b','truth-integrity:corrections',tria.Capability.ACT)
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert all(rel.state.claims[c].status is tria.ClaimStatus.ACTIVE for c in (source,child))


@pytest.mark.parametrize('adapter',[tria.OpenAIResponsesAdapter,tria.AnthropicMessagesAdapter])
def test_next_consumption_and_translations_observe_contestation(scenario,adapter):
    _,rel,source,child,correction=scenario
    rel.admin.grant_permission('human:a','agent:b','claim:'+child,tria.Capability.READ)
    req=tria.InvocationRequest('agent:b','inspect','local',context_resources=('claim:'+child,))
    before=tria.Runtime().prepare(rel,req).context[0]
    assert apply(rel,correction).outcome is tria.GovernanceOutcome.ALLOW
    plan=tria.Runtime().prepare(rel,req); after=plan.context[0]
    assert before.claim_status=='ACTIVE' and after.claim_status=='CONTESTED'
    assert before.claim_version!=after.claim_version and after.contestation_refs
    assert 'CONTESTED' in str(adapter().translate(plan,model='local').payload)
    consumer=lambda item: 'withhold' if item.claim_status!='ACTIVE' else 'use'
    assert consumer(before)=='use' and consumer(after)=='withhold'


def test_correction_during_translation_never_releases_stale_context(scenario):
    _,rel,source,child,correction=scenario
    rel.admin.grant_permission('human:a','agent:b','claim:'+child,tria.Capability.READ)
    req=tria.InvocationRequest('agent:b','inspect','local',context_resources=('claim:'+child,))
    class Translator(tria.OpenAIResponsesAdapter):
        def translate(self,plan,**kwargs):
            payload=super().translate(plan,**kwargs); apply(rel,correction); return payload
    calls=[]
    receipt=tria.ExecutionBridge().execute(rel,req,Translator(),lambda p:calls.append(p),model='local')
    assert not receipt.executed and calls==[]
