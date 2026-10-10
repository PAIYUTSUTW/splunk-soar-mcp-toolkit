"""Exact read surfaces: real pages and schemas, no fuzzy semantic selection."""
import json

import httpx
import pytest

from soar_mcp.client import SoarClient
from soar_mcp.config import Settings


def client_for(tmp_path, handler):
    return SoarClient(Settings('https://example.test', 'secret', tmp_path / 'evidence'),
                      transport=httpx.MockTransport(handler))


def test_action_definitions_preserve_types_fields_and_explicit_page(tmp_path):
    calls = []
    definition = dict(id=24, app=8, action='observe item', parameters={
        'target': {'required': True, 'data_type': 'string'}},
        output=[{'data_path': 'action_result.data.*.value', 'data_type': 'numeric'}],
        future_field={'uncertain': None})
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=definition if request.url.path.endswith('/24') else
                              dict(count=6, num_pages=3, data=[definition]))
    with client_for(tmp_path, respond) as client:
        page = client.list_app_actions(8, page=1, page_size=2)
        result = client.get_app_action(24)
        assert page['body']['num_pages'] == 3
        assert result['body'] == definition
        assert json.loads(client.evidence.raw(result['evidence']['id'])) == definition
    assert len(calls) == 2
    assert calls[0].url.path == '/rest/app/8/actions'
    assert dict(calls[0].url.params) == {'page': '1', 'page_size': '2'}
    assert calls[1].url.path == '/rest/app_action/24'


@pytest.mark.parametrize('identity', [0, True, '../8', '8'])
def test_action_invalid_id_does_not_send_http(tmp_path, identity):
    with client_for(tmp_path, lambda r: pytest.fail('invalid input reached HTTP')) as client:
        with pytest.raises(ValueError):
            client.list_app_actions(identity)
        with pytest.raises(ValueError):
            client.get_app_action(identity)
