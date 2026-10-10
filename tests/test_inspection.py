import json

import pytest

from test_bundles import bundle
from test_operations import setup


def test_inspection_reads_retained_source_and_graph_without_http_or_execution(tmp_path):
    client,op=setup(tmp_path,lambda r:pytest.fail('inspection must not repeat HTTP'))
    document={'coa':{'data':{'name':'trial_blue_bundle','nodes':{'start':{'unknown':None}},
                            'edges':[{'from':'start','to':'finish','conditions':['a','b']}]},
                     'unfamiliar':{'preserve':[None,False,1]}},'future':'yes'}
    raw=bundle(document=document)
    with client:
        receipt=client.evidence.save(raw,{'fixture':'exact export'})
        result=client.inspect_playbook_bundle(receipt['id'])
        assert result['graph_fields_present']==['nodes','edges']
        assert result['playbook_name']=='trial_blue_bundle'
        assert json.loads(client.evidence.raw(result['definition']['evidence']['id']))==document
        assert client.evidence.raw(result['python']['evidence']['id'])==b'def on_start(container):\n    pass\n'
        assert result['definition']['view']['next_offset'] is None
        assert client.evidence.raw(receipt['id'])==raw


def test_large_definition_paginates_without_semantic_filtering(tmp_path):
    client,op=setup(tmp_path,lambda r:pytest.fail('no HTTP'))
    doc={'coa':{'data':{'name':'trial_blue_bundle','nodes':{'x':'unknown '*3000}}}}
    with client:
        receipt=client.evidence.save(bundle(document=doc),{})
        result=client.inspect_playbook_bundle(receipt['id'])
        assert result['graph_fields_present']==['nodes']
        view=result['definition']['view'];parts=[view['text']]
        assert view['next_offset'] is not None
        while view['next_offset'] is not None:
            view=client.evidence.read(result['definition']['evidence']['id'],offset=view['next_offset'])
            parts.append(view['text'])
        assert json.loads(''.join(parts))==doc


def test_missing_graph_is_not_invented(tmp_path):
    client,op=setup(tmp_path,lambda r:pytest.fail('no HTTP'))
    with client:
        receipt=client.evidence.save(bundle(document={'coa':{'data':{'name':'trial_blue_bundle'}}}),{})
        result=client.inspect_playbook_bundle(receipt['id'])
        assert result['graph_fields_present']==[]
        assert json.loads(result['definition']['view']['text'])=={'coa':{'data':{'name':'trial_blue_bundle'}}}
