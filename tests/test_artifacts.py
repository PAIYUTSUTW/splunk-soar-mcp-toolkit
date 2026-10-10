import json

import httpx
import pytest

from soar_mcp.operations import OwnedOperations
from test_operations import setup, register


def scenario(calls, *, moved=False, timeout=False):
    state = dict(id=41, name='trial_blue_item', container=32,
                 cef={'kept': [1,None], 'value':'old'}, cef_types={'kept':['tag']})
    def respond(request):
        calls.append(request)
        path = request.url.path
        if request.method == 'GET':
            if path == '/rest/container/32':
                return httpx.Response(200,json=dict(id=32,name='trial_blue_event'))
            if path == '/rest/artifact/41':
                return httpx.Response(200,json=dict(state, container=99 if moved else 32))
            return httpx.Response(200,json=dict(count=0,data=[]))
        if timeout:
            raise httpx.ReadTimeout('lost reply',request=request)
        if request.method == 'POST' and path.endswith('/41'):
            state.update(json.loads(request.content))
        return httpx.Response(200,json=dict(success=True,id=41))
    return respond


def make(tmp_path, calls, **kwargs):
    client, op = setup(tmp_path,scenario(calls,**kwargs))
    register(op,'container',32,'trial_blue_event')
    return client,op


def create(op):
    return op.create_artifact('create_item','item',32,{'kept':[1,None],'value':'old'},'event',{'kept':['tag']})


def test_owned_artifact_create_merge_read_and_delete(tmp_path):
    calls=[];client,op=make(tmp_path,calls)
    with client:
        created=create(op)
        assert created['owned'] == dict(kind='artifact',id=41,name='trial_blue_item',container_id=32)
        request=json.loads(calls[-1].content)
        assert request['container_id']==32 and request['run_automation'] is False
        assert op.get_owned('artifact',41)['body']['container']==32
        result=op.update_artifact_cef('merge_item',41,{'value':None,'new':{'nested':True}})
        assert 'error' not in result
        request=json.loads(calls[-1].content)
        assert request == dict(cef={'kept':[1,None],'value':None,'new':{'nested':True}},run_automation=False)
        assert op.get_owned('artifact',41)['body']['cef_types']=={'kept':['tag']}
        count=len(calls)
        reopened=OwnedOperations(client,'trial_blue',tmp_path/'sources')
        assert reopened.update_artifact_cef('merge_item',41,{'value':None,'new':{'nested':True}})==result
        assert len(calls)==count
        assert 'error' not in op.delete('delete_item','artifact',41)
        assert calls[-1].method=='DELETE' and calls[-1].url.path=='/rest/artifact/41'


def test_foreign_artifact_or_parent_rejected_before_http(tmp_path):
    client,op=setup(tmp_path,lambda r: pytest.fail('foreign ID reached HTTP'))
    with client:
        for invoke in (lambda:op.create_artifact('new','item',99,{},'event',{}),
                lambda:op.update_artifact_cef('change',41,{}),lambda:op.delete('delete','artifact',41)):
            with pytest.raises(ValueError,match='owned'):invoke()


def test_reparented_artifact_is_not_mutated(tmp_path):
    calls=[];client,op=make(tmp_path,calls,moved=True)
    with client:
        create(op);count=len(calls)
        assert op.update_artifact_cef('change',41,{'a':1})['error']['kind']=='ownership_changed'
        assert op.delete('remove','artifact',41)['error']['kind']=='ownership_changed'
        assert all(c.method=='GET' for c in calls[count:])


def test_uncertain_artifact_create_not_replayed_or_adopted(tmp_path):
    calls=[];client,op=make(tmp_path,calls,timeout=True)
    with client:
        result=create(op);count=len(calls)
        assert result['execution_state']=='unknown'
        assert create(OwnedOperations(client,'trial_blue',tmp_path/'sources'))==result
        assert len(calls)==count
        assert not any(r['kind']=='artifact' for r in op.inventory()['resources'])


def test_read_artifact_and_explicit_container_page(tmp_path):
    calls=[];client,op=make(tmp_path,calls)
    with client:
        assert client.get_artifact(41)['body']['cef']['kept']==[1,None]
        client.list_artifacts(32,page=2,page_size=3)
    assert calls[-1].url.path=='/rest/container/32/artifacts'
    assert dict(calls[-1].url.params)=={'page':'2','page_size':'3'}


@pytest.mark.parametrize('body', [None, [], {'cef':None}])
def test_malformed_owned_readback_cannot_authorize_write(tmp_path, body):
    client,op=setup(tmp_path,lambda r:httpx.Response(200,json=body) if body is not None else httpx.Response(200,content=b'null'))
    register(op,'container',32,'trial_blue_event')
    with client:
        result=op.create_artifact('new','item',32,{},'event')
        assert result['execution_state']=='not_sent'
        assert result['error']['kind']=='ownership_changed'
