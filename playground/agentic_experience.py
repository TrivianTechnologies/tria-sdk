"""Public SDK authority walkthrough. Synthetic local effects only.

Run: python playground/agentic_experience.py
SPDX-License-Identifier: MPL-2.0
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import tria
from tria import (
    Capability, CapabilityRequirement, DelegationError, ExecutionBridge,
    InvocationRequest, OpenAIResponsesAdapter, Tria,
)
from tria.diagnostic import OPERATIONAL_SPEC_VERSION


def run_agentic():
    """Run fixed scenarios and return only inspectable synthetic governance data."""
    principal = 'human:principal'
    lead, delegate, peer, other = 'agent:lead', 'agent:delegate', 'agent:peer', 'agent:other'
    resource, purpose = 'action:demo:record', 'authority-demonstration'
    conditions = ('synthetic-local-only',)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    rel = Tria().create_relationship([principal, lead, delegate, peer, other])
    bridge, calls, steps = ExecutionBridge(), [], []
    # Ten minutes is a demonstration validity window, not an empirical parameter.
    bounds = dict(purpose=purpose, expires_at=expiry, conditions=conditions)

    def grant(subject, capability):
        return rel.admin.grant_permission(principal, subject, resource, capability, **bounds)

    def request(subject, **metadata):
        return InvocationRequest(subject, 'Record one synthetic local outcome.', 'playground-local',
            requirements=(CapabilityRequirement(resource, Capability.ACT, purpose=purpose,
                satisfied_conditions=conditions),), metadata=metadata)

    def authority(subject):
        state = rel.state
        record = state.permissions.get((subject, resource, Capability.ACT))
        by_id = {r.grant_event_id: r for r in state.permissions.values()}
        def parent(identity):
            p = by_id.get(identity)
            return {'grant_id': identity, 'subject': p.grantee if p else None,
                    'capability': p.capability.value if p else None,
                    'active': p.active if p else False}
        return {'principal': principal, 'subject': subject, 'capability': 'ACT',
                'resource': resource, 'purpose': purpose, 'conditions': list(conditions),
                'source': 'delegated grant' if record and record.delegated else
                          'host-issued root grant' if record else 'no ACT grant',
                'grant_id': record.grant_event_id if record else None,
                'grant_active': record.active if record else False,
                'expires_at': record.expires_at.isoformat() if record and record.expires_at else None,
                'parent_grants': [parent(i) for i in record.parent_grant_ids] if record else []}

    def attempt(identity, title, subject, *, req=None, prepared_outcome=None):
        before = len(calls)
        receipt = bridge.execute(rel, req or request(subject), OpenAIResponsesAdapter(),
            lambda wire: calls.append(wire.request_id) or {'status': 'completed'}, model='synthetic')
        row = {'id': identity, 'title': title, 'outcome': receipt.plan.outcome.value,
               'reason': receipt.plan.reason, 'executor_calls': len(calls) - before,
               'authority': authority(subject),
               'next_step': 'Local handoff completed.' if receipt.executed else
                   'Do not execute. Ask the principal to review scope and reauthorize or abstain.'}
        if prepared_outcome is not None:
            row['prepared_outcome'] = prepared_outcome
        steps.append(row)

    grant(lead, Capability.ACT)
    grant(lead, Capability.DELEGATE)
    attempt('grant', 'Valid scoped grant and local handoff', lead)
    rel.delegate_permission(lead, delegate, resource, Capability.ACT,
                            satisfied_conditions=conditions, **bounds)
    attempt('delegate', 'Valid bounded delegation and local handoff', delegate)

    grant(peer, Capability.DELEGATE)
    try:
        rel.delegate_permission(peer, other, resource, Capability.ACT,
                                satisfied_conditions=conditions, **bounds)
    except DelegationError as exc:
        steps.append({'id': 'invalid', 'title': 'Delegation without capability possession',
            'outcome': 'REJECTED', 'reason': str(exc), 'executor_calls': 0,
            'authority': authority(peer),
            'next_step': 'Request valid scoped authority from the principal; DELEGATE alone is insufficient.'})
    else:
        steps.append({'id': 'invalid', 'title': 'Delegation without capability possession',
            'outcome': 'UNEXPECTED_GRANT', 'reason': 'The expected delegation rejection did not occur.',
            'executor_calls': 0, 'authority': authority(peer), 'next_step': 'Inspect this failing witness.'})

    rel.admin.revoke_permission(principal, lead, resource, Capability.ACT)
    attempt('revoke', 'Parent revoked: descendant handoff blocked', delegate)
    attempt('peer', 'Peer says GO without granting authority', other,
            req=request(other, peer_instruction={'from': peer, 'message': 'GO'}))
    attempt('consensus', 'Agents agree but possess no valid ACT authority', other,
            req=request(other, consensus=[lead, delegate, peer, other]))
    attempt('missing', 'Unresolved authority: abstain and seek review', other)

    grant(lead, Capability.ACT)
    stale = request(lead)
    prepared = bridge.prepare(rel, stale, OpenAIResponsesAdapter(), model='synthetic')
    rel.admin.revoke_permission(principal, lead, resource, Capability.ACT)
    attempt('stale', 'Prepared ALLOW becomes stale before handoff', lead,
            req=stale, prepared_outcome=prepared.plan.outcome.value)
    expected = [1, 1, 0, 0, 0, 0, 0, 0]
    checks = {'handoffs_match': [s['executor_calls'] for s in steps] == expected,
              'invalid_delegation_rejected': steps[2]['outcome'] == 'REJECTED',
              'all_unauthorized_actions_blocked': all(s['outcome'] == 'BLOCK' for s in steps[3:]),
              'prepared_allow_was_rechecked': steps[-1]['prepared_outcome'] == 'ALLOW',
              'history_valid': rel.audit()['chain_valid']}
    digest = hashlib.sha256()
    sdk_root = Path(tria.__file__).resolve().parent
    for path in sorted(sdk_root.rglob('*.py')):
        digest.update(path.relative_to(sdk_root).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    return {'schema': 'tria.agentic-reference/0.1', 'execution_mode': 'sdk-backed-local',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'versions': {'sdk': tria.__version__, 'event_schema': tria.CURRENT_EVENT_SCHEMA_VERSION,
                         'projection': tria.CURRENT_PROJECTION_VERSION, 'operational_spec': OPERATIONAL_SPEC_VERSION},
            'provenance': {'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           'sdk_source_sha256': digest.hexdigest()},
            'steps': steps, 'executor_calls': len(calls), 'checks': checks, 'passed': all(checks.values()),
            'limits': ['Current local handoff authorization; no remote or delayed effect guarantee.',
                       'Synthetic identities and grants; no real-world identity authentication.',
                       'Each run creates fresh state. No automatic migration or imported authority.',
                       'BLOCK is the SDK outcome; review/reauthorization is a suggested human next step.',
                       'Passing this walkthrough does not establish real-world alignment.']}


if __name__ == '__main__':
    print(json.dumps(run_agentic(), indent=2))
