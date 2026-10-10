import base64
import io
import json
import tarfile

import httpx
import pytest

from test_operations import setup


def bundle(name='trial_blue_bundle', *, document=None, members=None):
    if document is None:
        document={'coa':{'data':{'name':name,'nodes':{},'edges':[]},'python_version':'3.13'},'active':False,'labels':[]}
    entries=members if members is not None else [(name+'.json',json.dumps(document).encode()),(name+'.py',b'def on_start(container):\n    pass\n')]
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as archive:
        for name,raw in entries:
            member=tarfile.TarInfo(name);member.size=len(raw)
            archive.addfile(member,io.BytesIO(raw))
    return output.getvalue()


def test_binary_export_retains_exact_bundle_and_http_errors(tmp_path):
    raw=bundle();calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,content=raw,headers={'content-type':'application/x-gzip'})
    client,op=setup(tmp_path,respond)
    with client:
        result=client.export_playbook(31)
        assert 'error' not in result
        assert client.evidence.raw(result['evidence']['id'])==raw
        assert result['body_included'] is False
        assert result['content_type']=='application/x-gzip'
    assert calls[0].url.path=='/rest/playbook/31/export'


def test_exact_import_no_force_readback_and_restart_no_replay(tmp_path):
    calls=[];raw=bundle();exists=False
    def respond(request):
        nonlocal exists
        calls.append(request)
        if request.method=='POST':
            assert request.url.path=='/rest/import_playbook'
            body=json.loads(request.content)
            assert body==dict(playbook=base64.b64encode(raw).decode(),scm_id=2,force=False)
            exists=True
            return httpx.Response(200,json=dict(success=True,message=[True,'Imported']))
        assert request.url.path=='/rest/playbook'
        rows=[dict(id=41,name='trial_blue_bundle',scm=2,active=False)] if exists else []
        return httpx.Response(200,json=dict(count=len(rows),data=rows))
    client,op=setup(tmp_path,respond)
    (tmp_path/'sources'/'bundle.tgz').write_bytes(raw)
    with client:
        result=op.import_playbook('import_once','bundle.tgz',2)
        assert result['owned']==dict(kind='playbook',id=41,name='trial_blue_bundle')
        count=len(calls)
        from soar_mcp.operations import OwnedOperations
        assert OwnedOperations(client,'trial_blue',tmp_path/'sources').import_playbook('import_once','bundle.tgz',2)==result
        assert len(calls)==count==3


@pytest.mark.parametrize('bad', ['foreign','active','traversal','duplicate','extra','invalid_json','not_archive','symlink'])
def test_import_rejects_unsafe_or_out_of_scope_bundle_before_http(tmp_path,bad):
    client,op=setup(tmp_path,lambda r:pytest.fail('unsafe import reached HTTP'))
    if bad=='foreign':raw=bundle('other_bundle')
    elif bad=='active':raw=bundle(document={'active':True,'coa':{'data':{'name':'trial_blue_bundle'}}})
    elif bad=='traversal':raw=bundle(members=[('../bad.py',b'x')])
    elif bad=='duplicate':raw=bundle(members=[('x.py',b'a'),('x.py',b'b')])
    elif bad=='extra':raw=bundle(members=[('x.py',b'a'),('x.json',b'{}'),('secret.txt',b'x')])
    elif bad=='invalid_json':raw=bundle(members=[('x.py',b'a'),('x.json',b'{')])
    elif bad=='not_archive':raw=b'not an archive'
    else:
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w:gz') as archive:
            link=tarfile.TarInfo('x.py');link.type=tarfile.SYMTYPE;link.linkname='/etc/passwd';archive.addfile(link)
        raw=out.getvalue()
    (tmp_path/'sources'/'bundle.tgz').write_bytes(raw)
    with client,pytest.raises(ValueError):op.import_playbook('bad_import','bundle.tgz',2)


@pytest.mark.parametrize('failure', ['exists','rejected','timeout','ambiguous','active'])
def test_import_failure_never_overwrites_replays_or_invents_identity(tmp_path,failure):
    raw=bundle();calls=[];sent=False
    def respond(request):
        nonlocal sent
        calls.append(request)
        if request.method=='POST':
            sent=True
            if failure=='timeout':raise httpx.ReadTimeout('lost response',request=request)
            return httpx.Response(200,json=dict(success=failure!='rejected'))
        rows=[]
        if failure=='exists' or sent:
            rows=[dict(id=41,name='trial_blue_bundle',scm=2,active=failure=='active')]
            if failure=='ambiguous':rows.append(dict(id=42,name='trial_blue_bundle',scm=2,active=False))
        return httpx.Response(200,json=dict(count=len(rows),data=rows))
    client,op=setup(tmp_path,respond);(tmp_path/'sources'/'bundle.tgz').write_bytes(raw)
    with client:
        result=op.import_playbook('once','bundle.tgz',2);count=len(calls)
        assert 'error' in result
        assert op.import_playbook('once','bundle.tgz',2)==result and len(calls)==count
        if failure=='exists':assert all(c.method=='GET' for c in calls)
        if failure!='active':assert op.inventory()['resources']==[]


@pytest.mark.parametrize('status,raw,kind', [(200,b'<html>login</html>','invalid_playbook_bundle'),
    (404,b'{"failed":true}','http_error'),(200,b'broken gzip','invalid_playbook_bundle')])
def test_bad_export_is_not_binary_success(tmp_path,status,raw,kind):
    client,op=setup(tmp_path,lambda r:httpx.Response(status,content=raw))
    with client:
        result=client.export_playbook(31)
        assert result['error']['kind']==kind
        assert client.evidence.raw(result['evidence']['id'])==raw


def test_archive_size_limit_and_duplicate_json_fail_closed():
    from soar_mcp.bundles import read_bundle,MAX_BUNDLE_BYTES
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as archive:
        member=tarfile.TarInfo('x.py');member.size=MAX_BUNDLE_BYTES+1;archive.addfile(member)
    with pytest.raises(ValueError,match='32 MiB'):read_bundle(out.getvalue())
    with pytest.raises(ValueError):read_bundle(bundle(members=[('x.py',b''),('x.json',b'{"coa":{},"coa":{}}')]))
