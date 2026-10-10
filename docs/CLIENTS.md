# Installation and native clients

## Standalone installation

Use Python 3.11 or newer. Install this standalone repository:

```sh
python3 -m venv /absolute/client-venv
/absolute/client-venv/bin/python -m pip install /absolute/source/soar-mcp-toolkit
```

For a locally built wheel or source distribution, replace the final argument with
its filename. The executable is `/absolute/client-venv/bin/soar-mcp`; equivalently
run `/absolute/client-venv/bin/python -m soar_mcp`. MCP uses stdio: stdout is
reserved for protocol messages. Missing settings exit 2 with a stderr diagnostic.

No Pipeline1 import, SSH, Windows/WSL helper, Wiki, old case, Codex account or
owner filesystem is required by this server. An MCP client, SOAR HTTPS endpoint,
trusted CA, authorized token and private writable evidence directory are needed.
Owned writes also require a role-authored source directory. Deployment of a
connector-facing Provider is outside this MCP's responsibilities.

Use `examples/readonly.env` or `examples/owned.env` as templates. Obtain a token
from your SOAR administrator; the package neither creates users nor discovers
credentials. Supply `SOAR_API_TOKEN` securely through the client environment,
never commit it. HTTPS uses `ph-auth-token`, system trust or `SOAR_CA_FILE`; there
is no disable-verification option.

When relocating, install into a **new** environment from the wheel/sdist; do not
move a virtualenv and assume its absolute shebangs still work. Configure new
endpoint/CA/token/output paths without editing package code. Preserve old scopes'
evidence and fixed origin/namespace/source-root bindings. A fresh deployment gets
a fresh scope; it cannot silently adopt another environment's operation history.

## Generic MCP client

Spawn the absolute `soar-mcp` executable with selected `SOAR_*` variables.
Read-only mode exposes thirteen tools; namespace plus source root exposes twenty-four,
including nine explicit owned mutations. Separate roles need separate processes,
evidence directories and namespaces. Client permissions and SOAR permissions are
separate from tool annotations. Read access is bounded by the token, not per-case
remote-ID ownership; mutations additionally require this scope's recorded IDs.

Interactive clients may ask before writes. An authorized unattended client must
explicitly allow the required tools: refusing all prompts does not grant writes.
Do not falsify tool annotations or expose arbitrary REST/shell to avoid approval.

## Verified Codex native configuration

The original native integration used **Codex 0.156.0**, strict-config app-server stdio, including
actual Builder/Reviewer calls. This is a tested version, not all-client support.
The following retained example selects those fourteen previously tested tools;
it does not automatically enable version 0.3.0's additions:

```toml
[mcp_servers.soar]
command = "/absolute/client-venv/bin/soar-mcp"
env_vars = ["SOAR_URL", "SOAR_API_TOKEN", "SOAR_CA_FILE", "SOAR_EVIDENCE_DIR", "SOAR_REQUEST_TIMEOUT_SECONDS", "SOAR_NAMESPACE", "SOAR_PLAYBOOK_SOURCE_ROOT"]
startup_timeout_sec = 20
tool_timeout_sec = 45
enabled_tools = ["list_apps", "get_app", "get_run", "list_related_runs", "get_action_results", "read_evidence", "list_owned_resources", "get_owned_resource", "create_asset", "create_container", "save_playbook", "start_debugger", "cancel_owned_run", "delete_owned_resource"]

# Only for an owner-authorized unattended owned-write session:
[mcp_servers.soar.tools.create_asset]
approval_mode = "approve"
[mcp_servers.soar.tools.create_container]
approval_mode = "approve"
[mcp_servers.soar.tools.save_playbook]
approval_mode = "approve"
[mcp_servers.soar.tools.start_debugger]
approval_mode = "approve"
[mcp_servers.soar.tools.cancel_owned_run]
approval_mode = "approve"
[mcp_servers.soar.tools.delete_owned_resource]
approval_mode = "approve"
```

For read-only use, omit the last two scope variables, select only the first six
tools and omit write approval entries. The caller supplies the listed environment
values. Tool startup/call deadlines do **not** limit model reasoning. Debugger
start returns a run ID immediately; observe actual run and nested results next.

Pipeline1's separate capability manifest applies equivalent per-tool policy
inside assigned role roots; that host adapter is not required by this package.
The native integration tests showed that nested isolation must not tie server lifetime to a short-lived
launcher thread. Normal/forced outer shutdown still owns child cleanup; do not
blindly copy one host's isolation command into another deployment.

For a new 0.3.0 deployment, the additional read-only tool names are
`list_app_actions`, `get_app_action`, `get_playbook_logs`, `get_artifact`,
`list_artifacts`, `export_playbook` and `inspect_playbook_bundle`. The additional
owned mutations are `create_artifact`, `update_artifact_cef` and `import_playbook`;
an unattended host must explicitly authorize these names too. Update the selected
capability allowlist and verify actual discovery before assigning it to a role.
Do not modify an old run's bound deployment or label the SDK tests as a new
model/workflow proof. Default scopes, source roots and write ownership are unchanged.

## Server proof and permissions

Real authenticated tests used **SOAR 8.5.0.248**, an Automation account (not a
superuser), app-view plus asset/container/Playbook operations and execution,
and access to the selected label, tenant and SCM. Exact permission names depend
on server version; verify your own deployment and grant only selected tools'
requirements. Constrain token network access on SOAR. This server never elevates
account permissions and does not sandbox arbitrary Playbook Python.

Saved VPE `/coa/playbooks/`, retirement `/playbooks`, and Debugger-specific
`/rest/playbook_run` shape were verified there. The first two are version-sensitive
web interfaces, not a cross-version public REST guarantee. No ordinary-Playbook,
SSH, Django or database-write fallback exists. Clean client installation does
not prove a second SOAR version, deployment or permission setup.

Integration checks cover actual SDK writes/nested results/cleanup, native
startup/lifetime, per-tool policy and readiness. In a fresh complete
DNS workflow, both native product roles executed saved-VPE Debugger actions,
then publication, owned cleanup and separate knowledge closeout were independently
checked. This does not prove universal connector coverage, zero trial/error or
reduced cost. The original code is MIT-licensed; see LICENSE. Installation from
source does not require a package-registry release.

The 0.3.0 extension checks use the same SOAR version/account without elevated
permissions: exact installed action definitions; actual saved-Debugger logs and
literal search; owned artifact/CEF create/merge/read/delete; new-only Playbook
import/export; and local reading of the retained real bundle via actual SDK
stdio with an unreachable HTTPS origin. Nonempty/large graph preservation is
tested synthetically; the live smoke Playbook has no nodes/edges graph fields.
SOAR normalizes a trailing Python newline and adds creation metadata on import;
the package sends the selected archive exactly and exposes the actual export.
Subsequently, an eight-group SMTP Builder/Reviewer workflow using 0.3.0 returned
PASS, published its Provider/Seed, and completed separate knowledge closeout.
Published product bytes were compared with its candidate. This is a workflow
result, not a claim that every new tool was used or that downstream multi-connector
playbook compatibility was established. Private runs, credentials and response
bodies are not distributed with this repository.

A separate Ubuntu client VM was also used for installation and real HTTPS/Debugger
checks against the same SOAR deployment. A second SOAR server/version, macOS and
Windows-native clients have not been validated. The CI Python matrix tests local
protocol/packaging behavior only and does not extend the SOAR compatibility claim.
