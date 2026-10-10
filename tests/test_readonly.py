"""Portable HTTP/MCP contracts, never a real SOAR qualification substitute."""
import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading

import httpx
import pytest
import trustme
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from soar_mcp.client import SoarClient
from soar_mcp.config import Settings
from soar_mcp.evidence import EvidenceStore


def settings(tmp_path, **overrides):
    values = dict(base_url='https://soar.example.test', token='test-secret',
                  evidence_dir=tmp_path / 'evidence')
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize('url', [
    'http://soar.example.test', 'https://u:p@soar.example.test',
    'https://soar.example.test/path', 'https://soar.example.test?q=x',
    'https://soar.example.test#x', 'file:///etc/passwd',
    'https://', 'https://soar.example.test:99999', 'https://@soar.example.test',
])
def test_reject_invalid_endpoint(tmp_path, url):
    with pytest.raises(ValueError):
        settings(tmp_path, base_url=url)


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_finite_positive_operation_timeout(tmp_path, timeout):
    with pytest.raises(ValueError):
        settings(tmp_path, request_timeout=timeout)


def test_secrets_not_in_repr_and_no_host_defaults(tmp_path):
    s = settings(tmp_path)
    assert s.token not in repr(s)
    with pytest.raises(ValueError):
        Settings.from_env({})
    values = dict(SOAR_URL='https://alternate.example.test:444',
                  SOAR_API_TOKEN='different-secret',
                  SOAR_EVIDENCE_DIR=str(tmp_path / 'alternate'))
    other = Settings.from_env(values)
    assert other.base_url == values['SOAR_URL']
    assert other.evidence_dir == tmp_path / 'alternate'


def test_command_missing_config_exits_without_protocol_noise(tmp_path):
    env = dict(PATH=os.defpath, PYTHONDONTWRITEBYTECODE='1')
    if not os.environ.get('SOAR_MCP_INSTALLED_TEST'):
        env['PYTHONPATH'] = str(Path(__file__).parents[1] / 'src')
    completed = subprocess.run([sys.executable, '-B', '-m', 'soar_mcp'], env=env,
                               cwd=tmp_path, capture_output=True, timeout=10)
    assert completed.returncode == 2
    assert completed.stdout == b''
    assert b'required configuration' in completed.stderr


@pytest.mark.parametrize('token', ['', 'line\nbreak', 'line\rbreak'])
def test_reject_invalid_auth(tmp_path, token):
    with pytest.raises(ValueError):
        settings(tmp_path, token=token)


def make_client(tmp_path, handler):
    return SoarClient(settings(tmp_path), transport=httpx.MockTransport(handler))


def test_read_exact_nested_failure_and_request_scope(tmp_path):
    raw = b'{"id":7,"status":"success","result_data":[{"status":"failed","data":[]}]}'
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=raw)
    with make_client(tmp_path, handle) as client:
        result = client.get_run('app_run', 7)
    assert len(calls) == 1
    request = calls[0]
    assert request.method == 'GET' and request.url.path == '/rest/app_run/7'
    assert request.headers['ph-auth-token'] == 'test-secret'
    assert result['body']['result_data'][0]['status'] == 'failed'
    assert 'verdict' not in result
    saved = tmp_path / 'evidence' / (result['evidence']['id'] + '.body')
    assert saved.read_bytes() == raw
    assert result['evidence']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert 'test-secret' not in json.dumps(result)


def test_app_details_and_explicit_pagination(tmp_path):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={'count': 12, 'num_pages': 3, 'data': []})
    with make_client(tmp_path, handle) as client:
        client.get_app(12)
        result = client.list_records('app', page=2, page_size=4)
        client.list_records('app_run', page=0, page_size=4, parent_id=8)
        client.action_results(11, page=0, page_size=4)
    assert calls[0].url.path == '/rest/app/12' and 'pretty' in calls[0].url.params
    assert calls[1].url.params == httpx.QueryParams({'page': '2', 'page_size': '4'})
    assert result['body']['num_pages'] == 3
    assert calls[2].url.params['_filter_action_run'] == '8'
    assert calls[3].url.path == '/rest/app_run/11/action_result'
    assert len(calls) == 4  # no hidden all-page fan-out


@pytest.mark.parametrize('resource', ['../asset', 'asset', 'http://elsewhere', 'app/1'])
def test_no_arbitrary_rest_surface(tmp_path, resource):
    with make_client(tmp_path, lambda r: pytest.fail('request must not happen')) as client:
        with pytest.raises(ValueError):
            client.list_records(resource)


@pytest.mark.parametrize('identity', [0, -1, True, '../3', '3'])
def test_invalid_id_never_sends_request(tmp_path, identity):
    with make_client(tmp_path, lambda r: pytest.fail('request must not happen')) as client:
        with pytest.raises(ValueError):
            client.get_run('playbook_run', identity)


@pytest.mark.parametrize('page,size', [(-1, 5), (0, 0), (0, 101), (True, 3)])
def test_invalid_page_never_sends_request(tmp_path, page, size):
    with make_client(tmp_path, lambda r: pytest.fail('request must not happen')) as client:
        with pytest.raises(ValueError):
            client.list_records('app', page=page, page_size=size)


@pytest.mark.parametrize('status', [302, 401, 403, 500])
def test_http_error_retained_without_redirect_or_retry(tmp_path, status):
    calls = []
    raw = b'{"error":"retain whole diagnostic"}'
    def handle(request):
        calls.append(request)
        return httpx.Response(status, content=raw, headers={'location': 'https://foreign.test'})
    with make_client(tmp_path, handle) as client:
        result = client.get_run('playbook_run', 9)
    assert len(calls) == 1
    assert result['error']['kind'] == 'http_error'
    assert result['http_status'] == status
    assert (tmp_path / 'evidence' / (result['evidence']['id'] + '.body')).read_bytes() == raw


def test_timeout_has_complete_diagnostic_and_no_retry(tmp_path):
    calls = []
    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout('server has not replied', request=request)
    with make_client(tmp_path, handle) as client:
        result = client.get_run('app_run', 9)
    assert len(calls) == 1
    assert result['error']['kind'] == 'transport_error'
    assert result['http_status'] is None
    store = EvidenceStore(tmp_path / 'evidence')
    assert 'server has not replied' in store.read(result['evidence']['id'])['text']


def test_interrupted_response_preserves_partial_body_and_http_status(tmp_path):
    class InterruptedBody(httpx.SyncByteStream):
        def __iter__(self):
            yield b'{"data":["already received"'
            raise httpx.ReadTimeout('interrupted after response headers')

    with make_client(tmp_path, lambda r: httpx.Response(200, stream=InterruptedBody())) as client:
        result = client.get_run('app_run', 4)
    assert result['http_status'] == 200
    assert result['body_complete'] is False
    assert result['error']['exception_type'] == 'ReadTimeout'
    identity = result['evidence']['id']
    assert EvidenceStore(tmp_path / 'evidence').raw(identity) == b'{"data":["already received"'
    metadata = json.loads((tmp_path / 'evidence' / (identity + '.json')).read_bytes())['metadata']
    assert metadata['error']['message'] == 'interrupted after response headers'
    assert metadata['body_complete'] is False


def test_nonstandard_json_number_kept_as_raw_evidence(tmp_path):
    with make_client(tmp_path, lambda r: httpx.Response(200, content=b'{"data":NaN}')) as client:
        result = client.get_run('app_run', 4)
    assert result['error']['kind'] == 'non_json_response'
    assert result['preview'] == '{"data":NaN}'
    json.dumps(result, allow_nan=False)


def test_binary_evidence_roundtrip(tmp_path):
    store = EvidenceStore(tmp_path / 'evidence')
    raw = b'\xff\x00\xfe' * 12000
    identity = store.save(raw, {})['id']
    parts, offset = [], 0
    while True:
        page = store.read(identity, offset=offset)
        assert page['encoding'] == 'base64' and page['offset_units'] == 'bytes'
        parts.append(base64.b64decode(page['text']))
        if page['next_offset'] is None:
            break
        offset = page['next_offset']
    assert b''.join(parts) == raw


def test_non_json_body_is_not_successfully_interpreted(tmp_path):
    with make_client(tmp_path, lambda r: httpx.Response(200, content=b'<html>login</html>')) as client:
        result = client.get_run('app_run', 9)
    assert result['error']['kind'] == 'non_json_response'
    assert result['preview'] == '<html>login</html>'


def test_full_large_unicode_response_reconstructs_without_extra_request(tmp_path):
    raw = json.dumps({'data': ['測試' * 12000], 'tail': 'essential'}, ensure_ascii=False).encode()
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=raw)
    with make_client(tmp_path, handle) as client:
        result = client.get_run('app_run', 12)
    assert result['body_included'] is False
    store = EvidenceStore(tmp_path / 'evidence')
    parts, offset = [], 0
    while True:
        page = store.read(result['evidence']['id'], offset=offset, limit=4096)
        parts.append(page['text'])
        if page['next_offset'] is None:
            break
        offset = page['next_offset']
    assert ''.join(parts).encode() == raw
    assert len(calls) == 1


@pytest.mark.parametrize('identity', ['../outside', '/etc/passwd', 'a' * 31, 'g' * 32])
def test_evidence_path_escape_rejected(tmp_path, identity):
    with pytest.raises(ValueError):
        EvidenceStore(tmp_path / 'evidence').read(identity)


def test_evidence_cannot_read_symlink_or_other_store(tmp_path):
    a, b = EvidenceStore(tmp_path / 'a'), EvidenceStore(tmp_path / 'b')
    receipt = a.save(b'private', {'http_status': 200})
    with pytest.raises(FileNotFoundError):
        b.read(receipt['id'])
    outside = tmp_path / 'outside'; outside.write_text('unrelated')
    (tmp_path / 'b' / ('a' * 32 + '.body')).symlink_to(outside)
    with pytest.raises((OSError, ValueError)):
        b.read('a' * 32)


@pytest.fixture
def https_soar(tmp_path):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.path, self.headers.get('ph-auth-token')))
            body = json.dumps({'id': 4, 'status': 'failed', 'message': 'observed action failure'}).encode()
            self.send_response(200); self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(body))); self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    ca = trustme.CA(); cert = ca.issue_cert('127.0.0.1')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); cert.configure_cert(context)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    ca_path = tmp_path / 'ca.pem'; ca.cert_pem.write_to_path(ca_path)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        yield f'https://127.0.0.1:{server.server_port}', ca_path, calls
    finally:
        server.shutdown(); server.server_close(); worker.join()


def test_real_https_rejects_untrusted_and_accepts_explicit_ca(tmp_path, https_soar):
    url, ca, calls = https_soar
    with SoarClient(settings(tmp_path, base_url=url)) as client:
        rejected = client.get_run('app_run', 4)
    assert rejected['error']['kind'] == 'transport_error' and not calls
    with SoarClient(settings(tmp_path, base_url=url, ca_file=ca)) as client:
        accepted = client.get_run('app_run', 4)
    assert accepted['body']['status'] == 'failed'
    assert calls == [('/rest/app_run/4', 'test-secret')]


def test_real_stdio_protocol_discovery_call_error_and_resource(tmp_path, https_soar):
    url, ca, calls = https_soar
    env = dict(SOAR_URL=url, SOAR_API_TOKEN='protocol-secret',
               SOAR_EVIDENCE_DIR=str(tmp_path / 'native-evidence'), SOAR_CA_FILE=str(ca),
               PYTHONDONTWRITEBYTECODE='1')
    if not os.environ.get('SOAR_MCP_INSTALLED_TEST'):
        env['PYTHONPATH'] = str(Path(__file__).parents[1] / 'src')
    async def exercise():
        params = StdioServerParameters(command=sys.executable, args=['-B', '-m', 'soar_mcp'],
                                       env=env, cwd=tmp_path)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                catalog = await session.list_tools()
                names = {tool.name for tool in catalog.tools}
                assert names == {'list_apps', 'get_app', 'list_app_actions', 'get_app_action', 'get_artifact', 'list_artifacts', 'export_playbook', 'inspect_playbook_bundle', 'get_run', 'get_playbook_logs', 'list_related_runs',
                                 'get_action_results', 'read_evidence'}
                assert all(tool.annotations.readOnlyHint for tool in catalog.tools)
                bad = await session.call_tool('get_run', {'kind': 'app_run', 'run_id': -1})
                assert bad.isError and not calls
                result = await session.call_tool('get_run', {'kind': 'app_run', 'run_id': 4})
                assert not result.isError  # tool succeeded; nested app failed
                value = result.structuredContent
                assert value['body']['status'] == 'failed'
                identity = value['evidence']['id']
                reread = await session.call_tool('read_evidence', {'evidence_id': identity})
                assert not reread.isError, reread.content
                assert json.loads(reread.structuredContent['text'])['status'] == 'failed'
                resource = await session.read_resource(f'soar-evidence://{identity}/body')
                assert json.loads(resource.contents[0].text)['id'] == 4
        assert calls == [('/rest/app_run/4', 'protocol-secret')]
    asyncio.run(exercise())


def test_real_stdio_owned_tools_require_explicit_scope_and_reject_foreign_ids(tmp_path, https_soar):
    url, ca, calls = https_soar
    source = tmp_path / 'authored'; source.mkdir()
    env = dict(SOAR_URL=url, SOAR_API_TOKEN='protocol-secret',
               SOAR_EVIDENCE_DIR=str(tmp_path / 'owned-evidence'), SOAR_CA_FILE=str(ca),
               SOAR_NAMESPACE='separate_trial', SOAR_PLAYBOOK_SOURCE_ROOT=str(source),
               PYTHONDONTWRITEBYTECODE='1')
    if not os.environ.get('SOAR_MCP_INSTALLED_TEST'):
        env['PYTHONPATH'] = str(Path(__file__).parents[1] / 'src')
    async def exercise():
        params = StdioServerParameters(command=sys.executable, args=['-B', '-m', 'soar_mcp'],
                                       env=env, cwd=tmp_path)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                catalog = await session.list_tools()
                writes = {t.name for t in catalog.tools if not t.annotations.readOnlyHint}
                assert writes == {'create_asset', 'create_container', 'create_artifact', 'update_artifact_cef', 'save_playbook', 'import_playbook',
                                  'start_debugger', 'cancel_owned_run', 'delete_owned_resource'}
                inventory = await session.call_tool('list_owned_resources', {})
                assert inventory.structuredContent['resources'] == []
                foreign = await session.call_tool('delete_owned_resource', {
                    'operation_id': 'delete_foreign', 'kind': 'container', 'resource_id': 19})
                assert foreign.isError and not calls
    asyncio.run(exercise())
