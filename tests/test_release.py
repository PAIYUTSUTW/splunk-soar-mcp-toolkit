"""Public distribution contract, separate from SOAR compatibility tests."""
from pathlib import Path
import asyncio
import tomllib

import pytest


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('name', [
    'LICENSE', 'THIRD_PARTY_NOTICES.md', 'docs/CLIENTS.md',
    'SECURITY.md', 'CONTRIBUTING.md',
    'examples/readonly.env', 'examples/owned.env',
])
def test_public_installation_material_exists(name):
    assert (ROOT / name).is_file()


def test_owner_selected_mit_license_matches_distribution():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project['license'] == 'MIT'
    assert set(project['license-files']) == {'LICENSE', 'THIRD_PARTY_NOTICES.md'}
    license_text = (ROOT / 'LICENSE').read_text()
    assert 'Permission is hereby granted, free of charge' in license_text
    assert 'Copyright (c) 2026 PAIYUTSUTW' in license_text


def test_public_name_and_repository_preserve_command_and_import():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
    assert project['name'] == 'splunk-soar-mcp-toolkit'
    assert project['urls'] == {
        'Repository': 'https://github.com/PAIYUTSUTW/splunk-soar-mcp-toolkit',
        'Issues': 'https://github.com/PAIYUTSUTW/splunk-soar-mcp-toolkit/issues',
    }
    assert project['scripts'] == {'soar-mcp': 'soar_mcp.server:main'}
    readme = (ROOT / 'README.md').read_text()
    assert readme.startswith('# Splunk SOAR MCP Toolkit\n')
    assert 'not an official Splunk product' in readme


def test_wheel_carries_public_installation_material():
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    files = config['tool']['setuptools']['data-files']
    assert files['share/splunk-soar-mcp-toolkit'] == [
        'README.md', 'SOURCES.md', 'SECURITY.md', 'CONTRIBUTING.md']
    assert files['share/splunk-soar-mcp-toolkit/docs'] == ['docs/CLIENTS.md']
    assert set(files['share/splunk-soar-mcp-toolkit/examples']) == {
        'examples/readonly.env', 'examples/owned.env'}


def test_public_examples_do_not_embed_account_credentials():
    for name in ('readonly.env', 'owned.env'):
        lines = (ROOT / 'examples' / name).read_text().splitlines()
        assignments = dict(line.split('=', 1) for line in lines if line and not line.startswith('#'))
        assert 'SOAR_API_TOKEN' not in assignments
        assert assignments['SOAR_URL'] == 'https://soar.example.test:8443'
        assert assignments['SOAR_EVIDENCE_DIR'].startswith('/absolute/')
    readonly = (ROOT / 'examples/readonly.env').read_text()
    assert 'SOAR_NAMESPACE=' not in readonly and 'SOAR_PLAYBOOK_SOURCE_ROOT=' not in readonly


def test_current_tool_catalog_is_documented_and_readonly_default(tmp_path):
    from soar_mcp.server import create_server
    from test_operations import setup
    client, operations = setup(tmp_path, lambda r: pytest.fail('catalog must not call SOAR'))
    with client:
        readonly = asyncio.run(create_server(client).list_tools())
        owned = asyncio.run(create_server(client, operations).list_tools())
    assert len(readonly) == 13 and all(t.annotations.readOnlyHint for t in readonly)
    assert len(owned) == 24 and sum(not t.annotations.readOnlyHint for t in owned) == 9
    readme = (ROOT / 'README.md').read_text()
    assert all('`' + t.name + '`' in readme for t in owned)
