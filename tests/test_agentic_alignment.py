"""Normative local agentic contract witnesses; not empirical alignment proof."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import pytest
from tria import (Tria, Capability, CapabilityRequirement, DelegationError,
                  GovernanceOutcome, ExecutionBridge, InvocationRequest,
                  OpenAIResponsesAdapter)
from tria.governance import GovernanceEngine


def relationship():
    return Tria().create_relationship(['human', 'a', 'b', 'c'])


def grant(rel, actor='a', capability=Capability.ACT, **bounds):
    return rel.admin.grant_permission('human', actor, 'effect', capability, **bounds)


def request(actor='a', **metadata):
    return InvocationRequest(actor, 'Achieve the objective', 'local',
        requirements=(CapabilityRequirement('effect', Capability.ACT),), metadata=metadata)


def execute(rel, req, adapter=None):
    effects = []
    receipt = ExecutionBridge().execute(rel, req, adapter or OpenAIResponsesAdapter(),
        lambda wire: effects.append(wire.request_id) or {'id': 'synthetic', 'status': 'completed'},
        model='synthetic')
    return receipt, effects


@pytest.mark.parametrize('metadata', [dict(peer='GO'), dict(consensus=['a', 'b', 'c']),
    dict(adopted_goal_from='b'), dict(necessity='impossible without elevated authority')])
def test_A_E_F_peer_goal_consensus_never_authorize(metadata):
    rel = relationship()
    grant(rel, 'b')
    receipt, effects = execute(rel, request(**metadata))
    assert not receipt.executed and not effects


def test_D_persistence_never_expands_permission():
    rel = relationship()
    before = dict(rel.state.permissions)
    for attempt in range(12):  # witness length, not a policy threshold
        receipt, effects = execute(rel, request(attempt=attempt, requested_expansion='all'))
        assert not receipt.executed and not effects
    assert dict(rel.state.permissions) == before


@pytest.mark.parametrize('only', [Capability.ACT, Capability.DELEGATE])
def test_B_requires_possession_and_delegation_right(only):
    rel = relationship(); grant(rel, capability=only)
    with pytest.raises(DelegationError):
        rel.delegate_permission('a', 'b', 'effect', Capability.ACT)


@pytest.mark.parametrize('bounds', [dict(purpose=None), dict(conditions=()), dict(expires_at=None)])
def test_B_delegation_cannot_weaken_parent_bounds(bounds):
    rel = relationship()
    end = datetime.now(timezone.utc) + timedelta(hours=1)
    parent = dict(purpose='research', conditions=('reviewed',), expires_at=end)
    for cap in (Capability.ACT, Capability.DELEGATE): grant(rel, capability=cap, **parent)
    child = dict(parent); child.update(bounds)
    with pytest.raises(DelegationError):
        rel.delegate_permission('a', 'b', 'effect', Capability.ACT,
            satisfied_conditions=('reviewed',), **child)


def chain():
    rel = relationship()
    for cap in (Capability.ACT, Capability.DELEGATE): grant(rel, capability=cap)
    for cap in (Capability.ACT, Capability.DELEGATE):
        rel.delegate_permission('a', 'b', 'effect', cap)
    rel.delegate_permission('b', 'c', 'effect', Capability.ACT)
    return rel


@pytest.mark.parametrize('cap', [Capability.ACT, Capability.DELEGATE])
def test_H_ancestor_revocation_and_regrant_do_not_revive_descendants(cap):
    rel = chain()
    assert rel.check_capability('c', 'effect', Capability.ACT).outcome is GovernanceOutcome.ALLOW
    rel.admin.revoke_permission('human', 'a', 'effect', cap)
    assert rel.check_capability('c', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK
    grant(rel, capability=cap)
    receipt, effects = execute(rel, request('c'))
    assert not receipt.executed and not effects


def test_H_ancestor_expiry_is_currently_checked():
    rel = relationship(); end = datetime.now(timezone.utc) + timedelta(hours=1)
    for cap in (Capability.ACT, Capability.DELEGATE): grant(rel, capability=cap, expires_at=end)
    rel.delegate_permission('a', 'b', 'effect', Capability.ACT, expires_at=end)
    decision = GovernanceEngine().require_capability(rel.state, 'b', 'effect', Capability.ACT,
        evaluated_at=end)
    assert decision.outcome is GovernanceOutcome.BLOCK


def test_H_legacy_delegated_event_without_ancestry_is_not_authority():
    rel = relationship()
    rel._commit('PermissionGranted', 'a', dict(granted_by='a', grantee='b',
        resource='effect', capability='ACT', delegated=True))
    assert rel.check_capability('b', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK


def test_C_revocation_during_translation_stops_consequence():
    rel = chain()
    class Revoke(OpenAIResponsesAdapter):
        def translate(self, plan, **kwargs):
            wire = super().translate(plan, **kwargs)
            rel.admin.revoke_permission('human', 'a', 'effect', Capability.DELEGATE)
            return wire
    receipt, effects = execute(rel, request('c'), Revoke())
    assert not receipt.executed and not effects


def test_G_prepared_work_has_no_continuing_authority():
    rel = relationship(); grant(rel)
    req = request(); bridge = ExecutionBridge()
    assert bridge.prepare(rel, req, OpenAIResponsesAdapter(), model='synthetic').plan.allowed
    rel.admin.revoke_permission('human', 'a', 'effect', Capability.ACT)
    receipt, effects = execute(rel, req)
    assert not receipt.executed and not effects


def test_positive_control_legitimate_delegation_executes_once():
    rel = chain()
    receipt, effects = execute(rel, request('c'))
    assert receipt.executed and len(effects) == 1


def test_H_cycle_and_missing_parent_fail_closed():
    rel = chain(); state = rel.state
    key = ('c', 'effect', Capability.ACT)
    original = state.permissions[key]
    for parents in ((original.grant_event_id,), ('missing',)):
        permissions = dict(state.permissions)
        permissions[key] = replace(original, parent_grant_ids=parents)
        altered = replace(state, permissions=permissions)
        assert GovernanceEngine().require_capability(altered, 'c', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK


def test_sqlite_reopen_preserves_ancestry_and_revocation(tmp_path):
    from tria import SQLiteEventStore
    path = tmp_path / 'lineage.db'
    with SQLiteEventStore(path) as store:
        rel = Tria(store).create_relationship(['human','a','b'])
        identity = rel.relationship_id
        for cap in (Capability.ACT, Capability.DELEGATE): grant(rel, capability=cap)
        rel.delegate_permission('a','b','effect',Capability.ACT)
    with SQLiteEventStore(path) as store:
        rel = Tria(store).load_relationship(identity)
        assert rel.check_capability('b','effect',Capability.ACT).outcome is GovernanceOutcome.ALLOW
        rel.admin.revoke_permission('human','a','effect',Capability.DELEGATE)
    with SQLiteEventStore(path) as store:
        rel = Tria(store).load_relationship(identity)
        assert rel.check_capability('b','effect',Capability.ACT).outcome is GovernanceOutcome.BLOCK


def test_old_compatibility_is_rejected_and_unrelated_grant_remains_valid():
    from tria.compat import check_compatibility
    assert not check_compatibility('0.2', projection_version='0.5').supported
    rel = chain(); grant(rel, actor='human')
    rel.admin.revoke_permission('human','a','effect',Capability.DELEGATE)
    assert rel.check_capability('human','effect',Capability.ACT).outcome is GovernanceOutcome.ALLOW


def test_ambiguous_ancestor_blocks_existing_descendant_at_handoff():
    rel = chain()
    rel.admin.revoke_permission('human', 'a', 'effect', Capability.ACT)
    # A different root issuer without the revoke as causal parent cannot resolve it.
    rel.admin.grant_permission('b', 'a', 'effect', Capability.ACT)
    assert ('a', 'effect', 'ACT') in rel.state.ambiguous_permissions
    receipt, effects = execute(rel, request('c'))
    assert not receipt.executed and not effects


def test_previous_event_schema_and_projection_are_not_silently_migrated():
    from tria import (RelationalEvent, SchemaCompatibilityError, export_replay_bundle,
                      replay_export_resource, verify_replay_bundle)
    rel = relationship()
    event = rel.events[0].to_dict()
    event['schema_version'] = '0.2'
    with pytest.raises(SchemaCompatibilityError):
        RelationalEvent.from_dict(event)
    rel.admin.grant_permission('human', 'human', replay_export_resource(rel.relationship_id), Capability.DISCLOSE)
    bundle = export_replay_bundle(rel, actor='human').to_dict()
    assert verify_replay_bundle(bundle).valid
    bundle['projection_version'] = '0.5'
    assert not verify_replay_bundle(bundle).valid


def test_public_permission_schema_accepts_actual_delegation_records():
    import json
    from dataclasses import asdict
    from pathlib import Path
    import jsonschema
    schema = json.loads((Path(__file__).parents[1] / 'schemas/permission_record.schema.json').read_text())
    rel = chain()
    for record in rel.state.permissions.values():
        wire = json.loads(json.dumps(asdict(record), default=str))
        jsonschema.validate(wire, schema)
