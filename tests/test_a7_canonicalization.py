"""Current-surface checks and separately dated local-authority witnesses.

F033 remains unresolved. Historical snapshots without a freshness channel are not
current authority; the explicit observation below does not claim that they are.
"""
import json
from pathlib import Path
import tomllib

import pytest
from tria import (Capability, CapabilityRequirement, ExecutionBridge,
                  GovernanceOutcome, InvocationRequest, OpenAIResponsesAdapter,
                  Tria, export_replay_bundle, replay_export_resource)

ROOT = Path(__file__).resolve().parents[1]


def _chain():
    rel = Tria().create_relationship(['human', 'parent', 'child'])
    for cap in (Capability.ACT, Capability.DELEGATE):
        rel.admin.grant_permission('human', 'parent', 'effect', cap)
    rel.delegate_permission('parent', 'child', 'effect', Capability.ACT)
    rel.admin.grant_permission('human', 'human',
        replay_export_resource(rel.relationship_id), Capability.DISCLOSE)
    return rel


def _request():
    return InvocationRequest('child', 'Synthetic effect', 'local',
        requirements=(CapabilityRequirement('effect', Capability.ACT),))


@pytest.mark.parametrize('mutation', ['revoke', 'replace', 'regrant'])
def test_current_history_round_trip_cannot_revive_descendant(mutation):
    rel = _chain()
    original_parent_ids = rel.state.permissions[('child', 'effect', Capability.ACT)].parent_grant_ids
    if mutation in ('revoke', 'regrant'):
        rel.admin.revoke_permission('human', 'parent', 'effect', Capability.ACT)
    if mutation in ('replace', 'regrant'):
        rel.admin.grant_permission('human', 'parent', 'effect', Capability.ACT)
    restored = Tria().restore_relationship(json.loads(export_replay_bundle(rel, actor='human').to_json()))
    assert restored.state.permissions[('child', 'effect', Capability.ACT)].parent_grant_ids == original_parent_ids
    effects = []
    receipt = ExecutionBridge().execute(restored, _request(), OpenAIResponsesAdapter(),
        lambda wire: effects.append(wire) or {'id': 'local', 'status': 'completed'}, model='synthetic')
    assert not receipt.executed and not effects
    assert restored.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK


def test_explicit_redelegation_is_required_after_regrant():
    rel = _chain()
    rel.admin.revoke_permission('human', 'parent', 'effect', Capability.ACT)
    rel.admin.grant_permission('human', 'parent', 'effect', Capability.ACT)
    assert rel.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK
    rel.delegate_permission('parent', 'child', 'effect', Capability.ACT)
    assert rel.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.ALLOW


def test_stale_inspection_snapshot_does_not_bypass_current_handoff():
    rel = _chain()
    snapshot = rel.state
    req = _request()
    bridge = ExecutionBridge()
    plan = bridge.prepare(rel, req, OpenAIResponsesAdapter(), model='synthetic')
    assert plan.plan.allowed
    rel.admin.revoke_permission('human', 'parent', 'effect', Capability.DELEGATE)
    # Old immutable values remain historical observations; bridge reads current state.
    assert snapshot.permissions[('parent', 'effect', Capability.DELEGATE)].active
    effects = []
    receipt = bridge.execute(rel, req, OpenAIResponsesAdapter(),
        lambda wire: effects.append(wire), model='synthetic')
    assert not receipt.executed and not effects


def test_f033_unresolved_independent_store_cannot_discover_later_source_revocation():
    source = _chain()
    source.grant_consent('human', 'effect')
    historical = export_replay_bundle(source, actor='human')
    source.revoke_consent('human', 'effect')
    source.admin.revoke_permission('human', 'parent', 'effect', Capability.ACT)
    restored = Tria().restore_relationship(historical)
    assert not source.state.consent[('human', 'effect')].active
    assert restored.state.consent[('human', 'effect')].active
    assert source.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK
    assert restored.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.ALLOW
    # No effect is attempted. This is an unresolved limitation witness, not a fix.


def test_current_canonical_metadata_and_release_guidance_agree():
    manifest = json.loads((ROOT / 'tria-manifest.json').read_text())
    canonical = 'https://github.com/TrivianTechnologies/tria-sdk'
    assert manifest['project']['canonical_repository'] == canonical
    assert manifest['provenance']['canonical_implementation'] == canonical
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project['urls']['Repository'] == canonical
    assert project['license']['text'] == 'MPL-2.0'
    guidance = (ROOT / 'docs/release-readiness.md').read_text()
    assert '0.1.0a7' in guidance and 'MPL-2.0' in guidance
    assert 'PolyForm' not in guidance
    assert 'F033' in guidance and 'UNRESOLVED' in guidance
    current = (ROOT / 'docs/TRIA_DIAGNOSTIC_INTERFACE_v0.2.md').read_text()
    assert '**Operational specification:** `0.1.3`' in current


def test_current_source_links_do_not_describe_old_engineering_home():
    paths = ['AGENTS.md', 'README.md', 'docs/quickstart.md',
             'docs/independent-reproduction.md', 'tria-manifest.json',
             'playground/index.html', 'playground/evaluate.html', 'playground/evidence.html',
             'playground/agentic.html']
    for path in paths:
        text = (ROOT / path).read_text()
        assert 'github.com/TrivianInstitute/' not in text
        assert 'TrivianInstitute/tria-sdk' not in text
    assert 'actions/workflows/tests.yml' not in (ROOT / 'playground/evidence.html').read_text()


def test_separate_process_restart_reads_current_revocation(tmp_path):
    import os
    import subprocess
    import sys
    import tria
    from tria import SQLiteEventStore
    path = tmp_path / 'restart.db'
    with SQLiteEventStore(path) as store:
        rel = Tria(store).create_relationship(['human', 'parent', 'child'])
        for cap in (Capability.ACT, Capability.DELEGATE):
            rel.admin.grant_permission('human', 'parent', 'effect', cap)
        rel.delegate_permission('parent', 'child', 'effect', Capability.ACT)
        identity = rel.relationship_id
        rel.admin.revoke_permission('human', 'parent', 'effect', Capability.DELEGATE)
    program = '''
import sys
from tria import (Tria, SQLiteEventStore, Capability, GovernanceOutcome,
    CapabilityRequirement, InvocationRequest, ExecutionBridge, OpenAIResponsesAdapter)
with SQLiteEventStore(sys.argv[1]) as store:
    rel = Tria(store).load_relationship(sys.argv[2])
    assert rel.check_capability('child', 'effect', Capability.ACT).outcome is GovernanceOutcome.BLOCK
    effects = []
    request = InvocationRequest('child', 'Synthetic effect', 'local',
        requirements=(CapabilityRequirement('effect', Capability.ACT),))
    receipt = ExecutionBridge().execute(rel, request, OpenAIResponsesAdapter(),
        lambda wire: effects.append(wire), model='synthetic')
    assert not receipt.executed and not effects
'''
    # Bind the fresh process to the exact package being tested, not an unrelated
    # editable installation that may happen to share this interpreter.
    env = dict(os.environ, PYTHONPATH=str(Path(tria.__file__).resolve().parent.parent))
    result = subprocess.run([sys.executable, '-c', program, str(path), identity],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
