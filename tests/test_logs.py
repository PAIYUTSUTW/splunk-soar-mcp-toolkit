import json
import httpx
import pytest
from test_discovery import client_for

def test_logs_keep_original_messages_and_search_is_literal(tmp_path):
    calls = []
    body = dict(count=2, num_pages=2, data=[{'message':'unresolved\n非成功', 'level':'ERROR', 'unknown':None}])
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=body)
    with client_for(tmp_path, respond) as client:
        result = client.playbook_logs(7, page=1, page_size=1, message_contains='a"&b')
        assert result['body'] == body
        assert json.loads(client.evidence.raw(result['evidence']['id'])) == body
    assert len(calls) == 1
    assert calls[0].url.path == '/rest/playbook_run/7/log'
    assert dict(calls[0].url.params) == {'page':'1', 'page_size':'1', '_filter_message__icontains':json.dumps('a"&b')}


@pytest.mark.parametrize('status', [403,404,500])
def test_log_errors_are_not_empty_success_or_retried(tmp_path, status):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, json={'failed': True, 'message':'unavailable'})
    with client_for(tmp_path, respond) as client:
        result = client.playbook_logs(7)
        assert result['error']['kind'] == 'http_error'
        assert result['body']['failed'] is True
    assert len(calls) == 1


def test_logs_invalid_input_rejected_before_http(tmp_path):
    with client_for(tmp_path, lambda r: pytest.fail('invalid input reached HTTP')) as client:
        for kwargs in ({'run_id':False}, {'run_id':1,'page_size':101}, {'run_id':1,'message_contains':[]}):
            with pytest.raises(ValueError):
                client.playbook_logs(**kwargs)
