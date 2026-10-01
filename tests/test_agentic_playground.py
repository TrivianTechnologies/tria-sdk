"""Behavioral release witnesses for the public authority walkthrough."""
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

PLAYGROUND = Path(__file__).resolve().parents[1] / 'playground'
sys.path.insert(0, str(PLAYGROUND))


def test_walkthrough_observes_actual_handoffs_and_authority_ancestry():
    from agentic_experience import run_agentic
    report = run_agentic()
    assert report['execution_mode'] == 'sdk-backed-local'
    assert report['passed']
    steps = {s['id']: s for s in report['steps']}
    assert {key: s['executor_calls'] for key, s in steps.items()} == {
        'grant': 1, 'delegate': 1, 'invalid': 0, 'revoke': 0,
        'peer': 0, 'consensus': 0, 'missing': 0, 'stale': 0,
    }
    delegated = steps['delegate']['authority']
    assert len(delegated['parent_grants']) == 2
    assert {p['capability'] for p in delegated['parent_grants']} == {'ACT', 'DELEGATE'}
    assert all(p['active'] for p in delegated['parent_grants'])
    assert any(not p['active'] for p in steps['revoke']['authority']['parent_grants'])
    assert steps['stale']['prepared_outcome'] == 'ALLOW'
    assert steps['stale']['outcome'] == 'BLOCK'
    assert steps['invalid']['outcome'] == 'REJECTED'
    assert report['executor_calls'] == 2
    assert report['versions'] == {'sdk': '0.1.0a7', 'event_schema': '0.3', 'projection': '0.6', 'operational_spec': '0.1.3'}
    serialized = json.dumps(report)
    for private in ['CognitiveBus', 'ExternalEnvelope', 'aporia', 'api_key', 'previous_event_hash']:
        assert private not in serialized


@pytest.fixture
def server():
    from adapter import PlaygroundHandler, ThreadingHTTPServer
    http = ThreadingHTTPServer(('127.0.0.1', 0), PlaygroundHandler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:' + str(http.server_port)
    http.shutdown(); http.server_close(); thread.join(timeout=2)


def test_http_walkthrough_is_allowlisted_and_fresh(server):
    with urlopen(server + '/agentic.html') as response:
        assert b'Current local handoff authorization' in response.read()
    with urlopen(server + '/healthz') as response:
        assert json.load(response)['agentic_experience'] is True
    for _ in range(2):
        request = Request(server + '/api/agentic', data=b'{}', headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            assert json.load(response)['executor_calls'] == 2


@pytest.mark.parametrize('body,content_type,status', [
    (b'{"actor":"admin"}', 'application/json', 400),
    (b'{"executor":"https://example.invalid"}', 'application/json', 400),
    (b'[]', 'application/json', 400),
    (b'{', 'application/json', 400),
    (b'{}', 'text/plain', 415),
    (b'x' * 4097, 'application/json', 413),
])
def test_http_walkthrough_rejects_untrusted_options(server, body, content_type, status):
    request = Request(server + '/api/agentic', data=body, headers={'Content-Type': content_type})
    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == status


def test_runner_error_is_not_replaced_by_success(server, monkeypatch):
    import adapter
    def broken():
        raise RuntimeError('private diagnostic')
    monkeypatch.setattr(adapter, 'run_agentic', broken)
    request = Request(server + '/api/agentic', data=b'{}', headers={'Content-Type': 'application/json'})
    with pytest.raises(HTTPError) as error:
        urlopen(request)
    assert error.value.code == 500
    assert json.load(error.value) == {'error': 'sdk_run_failed'}
