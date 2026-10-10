"""Mechanical ownership and no-replay contracts, not semantic product gates."""
import json
import sqlite3

import httpx
import pytest

from soar_mcp.client import SoarClient
from soar_mcp.config import Settings
from soar_mcp.operations import OwnedOperations


def setup(tmp_path, handler):
    source = tmp_path / 'sources'
    source.mkdir(exist_ok=True)
    (source / 'probe.py').write_text('def on_start(container):\n    pass\n')
    client = SoarClient(Settings('https://example.test', 'secret', tmp_path / 'evidence'),
                        transport=httpx.MockTransport(handler))
    return client, OwnedOperations(client, 'trial_blue', source)


def handler(calls):
    def respond(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'count': 0, 'num_pages': 0, 'data': []})
        return httpx.Response(200, json={'success': True, 'id': 31})
    return respond


def test_explicit_create_records_ownership_and_exact_body(tmp_path):
    calls = []
    client, op = setup(tmp_path, handler(calls))
    with client:
        result = op.create_asset('asset_once', 'asset', 7, {'host': 'loopback'})
        assert result['owned'] == {'kind': 'asset', 'id': 31, 'name': 'trial_blue_asset'}
        request = json.loads(calls[-1].content)
        assert request == {'name': 'trial_blue_asset', 'app_id': 7,
                           'configuration': {'host': 'loopback'}, 'disabled': False}
        assert op.inventory()['resources'][0]['id'] == 31
        metadata = json.loads((tmp_path / 'evidence' / (result['evidence']['id'] + '.json')).read_bytes())
        assert metadata['metadata']['request_body'] == request
        assert 'ph-auth-token' not in json.dumps(metadata)


def test_completed_operation_readback_does_not_repeat_http(tmp_path):
    calls = []
    client, op = setup(tmp_path, handler(calls))
    with client:
        first = op.create_container('event_once', 'event', 'events')
        count = len(calls)
        resumed = OwnedOperations(client, 'trial_blue', tmp_path / 'sources')
        assert resumed.create_container('event_once', 'event', 'events') == first
        assert len(calls) == count
        with pytest.raises(ValueError, match='different'):
            resumed.create_container('event_once', 'different_event', 'events')
        assert len(calls) == count


def test_timeout_preserves_uncertainty_and_never_replays_after_reopen(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'count': 0, 'num_pages': 0, 'data': []})
        raise httpx.ReadTimeout('reply lost after write', request=request)
    client, op = setup(tmp_path, respond)
    with client:
        result = op.create_container('event_once', 'event', 'events')
        assert result['execution_state'] == 'unknown'
        assert result['error']['kind'] == 'transport_error'
        count = len(calls)
        resumed = OwnedOperations(client, 'trial_blue', tmp_path / 'sources')
        assert resumed.create_container('event_once', 'event', 'events') == result
        assert len(calls) == count
        assert resumed.inventory()['resources'] == []


def test_foreign_ids_never_reach_mutation_endpoint(tmp_path):
    client, op = setup(tmp_path, lambda r: pytest.fail('foreign operation must not send HTTP'))
    with client:
        for kind in ('asset', 'container', 'playbook'):
            with pytest.raises(ValueError, match='owned'):
                op.delete('delete_once', kind, 17)
        with pytest.raises(ValueError, match='owned'):
            op.start_debugger('run_once', 17, 18)


def test_existing_remote_name_is_never_adopted_or_overwritten(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        assert request.method == 'GET'
        return httpx.Response(200, json={'count': 1, 'num_pages': 1,
                                       'data': [{'id': 55, 'name': 'trial_blue_event'}]})
    client, op = setup(tmp_path, respond)
    with client:
        result = op.create_container('event_once', 'event', 'events')
        assert result['error']['kind'] == 'name_conflict'
        assert op.inventory()['resources'] == []
        assert len(calls) == 1


def test_scope_cannot_be_rebound_to_other_namespace(tmp_path):
    client, op = setup(tmp_path, handler([]))
    with client, pytest.raises(ValueError, match='binding'):
        OwnedOperations(client, 'different_trial', tmp_path / 'sources')


@pytest.mark.parametrize('path', ['../outside.py', '/etc/passwd', 'linked.py'])
def test_source_must_be_assigned_regular_file(tmp_path, path):
    client, op = setup(tmp_path, lambda r: pytest.fail('invalid source must not send HTTP'))
    (tmp_path / 'sources' / 'linked.py').symlink_to('/etc/passwd')
    with client, pytest.raises(ValueError, match='source'):
        op.save_playbook('save_once', 'playbook', path, 2, ['events'], '3.13')


def test_playbook_authored_file_is_sent_exactly_with_inactive_defaults(tmp_path):
    calls = []
    client, op = setup(tmp_path, handler(calls))
    with client:
        op.save_playbook('save_once', 'playbook', 'probe.py', 2, ['events'], '3.13')
        body = json.loads(calls[-1].content)
        assert calls[-1].url.path == '/coa/playbooks/'
        assert body['python'] == (tmp_path / 'sources' / 'probe.py').read_text()
        assert body['active'] is False and body['draft_mode'] is False
        assert 'data' not in body  # actual HTTP seam rejects the helper's wrapper


def test_crash_between_intent_and_response_is_not_replayed(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'count': 0, 'data': []})
        raise RuntimeError('injected process loss')
    client, op = setup(tmp_path, respond)
    with client:
        with pytest.raises(RuntimeError, match='process loss'):
            op.create_container('event_once', 'event', 'events')
        count = len(calls)
        resumed = OwnedOperations(client, 'trial_blue', tmp_path / 'sources')
        result = resumed.create_container('event_once', 'event', 'events')
        assert result['execution_state'] == 'unknown'
        assert result['error']['kind'] == 'interrupted_operation'
        assert resumed.inventory()['pending_operation_ids'] == ['event_once']
        assert len(calls) == count
        with pytest.raises(ValueError, match='name already'):
            resumed.create_container('different_id', 'event', 'events')


def register(op, kind, identity, name):
    with sqlite3.connect(op.path) as db:
        db.execute('INSERT INTO resources VALUES (?,?,?)', (kind, identity, name))


def test_renamed_owned_object_cannot_be_deleted(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        assert request.method == 'GET'
        return httpx.Response(200, json={'id': 31, 'name': 'other_experiment'})
    client, op = setup(tmp_path, respond)
    register(op, 'container', 31, 'trial_blue_event')
    with client:
        result = op.delete('delete_once', 'container', 31)
        assert result['execution_state'] == 'not_sent'
        assert result['error']['kind'] == 'ownership_changed'
        assert len(calls) == 1


@pytest.mark.parametrize('bad_field,bad_value', [('active', True), ('disabled', True),
    ('draft_mode', True), ('passed_validation', False), ('commit_hash', '')])
def test_debugger_does_not_run_unsaved_or_active_vpe(tmp_path, bad_field, bad_value):
    calls = []
    def respond(request):
        calls.append(request)
        assert request.method == 'GET'
        body = dict(id=31, name='trial_blue_playbook', active=False, disabled=False,
                    draft_mode=False, passed_validation=True, commit_hash='saved')
        body[bad_field] = bad_value
        if request.url.path == '/rest/container/32':
            body = dict(id=32, name='trial_blue_event')
        return httpx.Response(200, json=body)
    client, op = setup(tmp_path, respond)
    register(op, 'playbook', 31, 'trial_blue_playbook')
    register(op, 'container', 32, 'trial_blue_event')
    with client:
        result = op.start_debugger('run_once', 31, 32)
        assert result['execution_state'] == 'not_sent'
        assert result['error']['kind'] == 'vpe_not_ready'
        assert len(calls) == 2


def test_debugger_matches_observed_frontend_and_owns_run(tmp_path):
    calls = []
    def respond(request):
        calls.append(request)
        if request.method == 'POST':
            return httpx.Response(200, json={'received': True, 'playbook_run_id': '33'})
        body = dict(id=31, name='trial_blue_playbook', active=False, disabled=False,
                    draft_mode=False, passed_validation=True, commit_hash='saved')
        if request.url.path == '/rest/container/32':
            body = dict(id=32, name='trial_blue_event')
        return httpx.Response(200, json=body)
    client, op = setup(tmp_path, respond)
    register(op, 'playbook', 31, 'trial_blue_playbook')
    register(op, 'container', 32, 'trial_blue_event')
    with client:
        result = op.start_debugger('run_once', 31, 32)
        assert result['owned']['id'] == 33
        assert json.loads(calls[-1].content) == dict(playbook_id=31, container_id=32,
            run=True, test_mode=True, dbg_token='trial_blue_run_once', run_as_user=True, scope='all')
        assert calls[-1].url.path == '/rest/playbook_run'
        assert op.start_debugger('run_once', 31, 32) == result
        assert len(calls) == 3


def test_http_200_with_rejection_does_not_become_success(tmp_path):
    def respond(request):
        return httpx.Response(200, json=({'count': 0, 'data': []} if request.method == 'GET'
            else {'success': False, 'message': 'application rejected it'}))
    client, op = setup(tmp_path, respond)
    with client:
        result = op.create_container('event_once', 'event', 'events')
        assert result['execution_state'] == 'rejected'
        assert result['error']['kind'] == 'operation_rejected'
        assert op.inventory()['resources'] == []


def test_missing_response_identity_is_unknown_not_retriable(tmp_path):
    def respond(request):
        return httpx.Response(200, json=({'count': 0, 'data': []} if request.method == 'GET'
            else {'success': True}))
    client, op = setup(tmp_path, respond)
    with client:
        result = op.create_container('event_once', 'event', 'events')
        assert result['execution_state'] == 'unknown'
        assert result['error']['kind'] == 'missing_created_id'
        assert op.inventory()['unknown_operation_ids'] == ['event_once']


def test_ownership_store_not_shared_across_origins(tmp_path):
    client, op = setup(tmp_path, handler([]))
    client.close()
    with SoarClient(Settings('https://different.test', 'secret', tmp_path / 'evidence')) as other:
        with pytest.raises(ValueError, match='binding'):
            OwnedOperations(other, 'trial_blue', tmp_path / 'sources')
