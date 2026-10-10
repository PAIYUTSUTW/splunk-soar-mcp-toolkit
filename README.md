# SOAR MCP Toolkit

An independent Model Context Protocol (MCP) server for Splunk SOAR, read-only
by default. Discover installed connector actions, execute saved playbooks through
the VPE Debugger, inspect nested results, and retain complete response evidence.
Optional writes are restricted to resources created in the configured scope.

This is a community project, not an official Splunk product. It connects through
HTTPS and needs no SSH, local SOAR installation, Pipeline1, Wiki or private
development environment. Linux clients and SOAR **8.5.0.248** have been tested;
this is not all-connector, all-OS or cross-version certification.

Python 3.11+ is required. From a checkout of this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
```

Configure your MCP client to launch the absolute `.venv/bin/soar-mcp` path over
stdio and pass the settings below. Start read-only against a test SOAR instance;
never put a real token in the repository. Installation from source is supported;
these instructions do not assume a PyPI release.

The MCP transport/client/tool schema machinery comes from
the official MIT-licensed Python SDK (`mcp==1.30.0`, explicitly pinned maintained
v1 line), not a custom protocol. HTTP uses `httpx==0.28.1`.
See [installation/client configuration](docs/CLIENTS.md), public
[read-only](examples/readonly.env) and [owned-operation](examples/owned.env)
templates, [security boundaries](SECURITY.md), [MIT license](LICENSE) and
[third-party notices](THIRD_PARTY_NOTICES.md).

## Owner configuration

Set environment variables in the MCP host or a private deployment environment:

| Variable | Meaning |
| --- | --- |
| `SOAR_URL` | Required HTTPS origin, e.g. `https://soar.example.test:8443`; no credentials/path/query |
| `SOAR_API_TOKEN` | Required SOAR token, passed only in `ph-auth-token` |
| `SOAR_EVIDENCE_DIR` | Required absolute private directory; use a separate directory per role/run |
| `SOAR_CA_FILE` | Optional absolute PEM CA file; default uses system trust, never disables verification |
| `SOAR_REQUEST_TIMEOUT_SECONDS` | Positive finite HTTP phase timeout, default 30; connect is at most 5 seconds |
| `SOAR_NAMESPACE` | Optional lowercase experiment/role prefix; enables owned writes only together with the source root |
| `SOAR_PLAYBOOK_SOURCE_ROOT` | Optional absolute role-authored Python/bundle directory, no symlink components; select with namespace |

Requests do not use ambient proxy/netrc settings, follow redirects, or retry.
The HTTP phase timeout is **not** a total SOAR execution deadline and never
limits model reasoning. Debugger start returns an ID immediately, not a blocking
wait for completion. The caller observes status and may explicitly cancel its
owned run under its own operation deadline. No automatic poll/retry/cancel loop
or model timeout is implemented by this package.
Use SOAR-side least-privilege credentials: read-only tool annotations are not an
authorization boundary. This version permits reads granted to its configured
SOAR token; read-only inventory/run tools do not enforce per-case ownership of
remote run IDs. All exposed mutation tools require locally recorded ownership.
Do not share its private evidence directory across untrusted users/roles.

## Tools and evidence

- `list_apps`, `get_app`: installed inventory and details/action names.
- `list_app_actions`, `get_app_action`: complete installed definitions selected
  by exact IDs, including original parameters/output. No fuzzy schema inference.
- `get_run`: a known PlaybookRun, ActionRun or AppRun.
- `get_playbook_logs`: explicit original log page, optionally filtered by literal
  message text. Empty logs are not success; logging may be disabled or deleted.
- `list_related_runs`: one page filtered by the parent run ID.
- `get_action_results`: one AppRun action-result page.
- `get_artifact`, `list_artifacts`: exact artifact/CEF reads and container pages.
- `export_playbook`: exact gzip export to binary evidence, not model-written Base64.
- `inspect_playbook_bundle`: Python plus full graph/metadata from that retained
  export; no new HTTP, execution or graph reconstruction. Each member has a
  separate complete evidence ID and paged view; absent graph fields stay absent.
- `read_evidence`: paged access to an already fetched complete response.

With the explicit namespace/source-root selection, additional tools are:

- `create_asset`, `create_container`: create new prefixed objects, never adopt
  or overwrite an existing name. Container creation disables automation.
- `create_artifact`, `update_artifact_cef`: create only in an owned container and
  merge explicit top-level CEF keys only on an owned artifact, with automation
  disabled. Unspecified keys and `cef_types` remain; null is a value, not deletion.
  Nested values are replaced whole. Use a quiet setup boundary; no concurrent
  compare-and-swap guarantee. Connector-created artifacts remain read-only here.
- `save_playbook`: create a new inactive VPE from the role's exact source file;
  returns the actual SOAR validation response without grading the product.
- `import_playbook`: new-only import of an exact assigned gzip bundle, with
  `force=false`. Refuses foreign/conflicting names and unsafe archives. It accepts
  only one flat matching UTF-8 Python/JSON pair, up to 32 MiB compressed and total
  uncompressed size; unsupported layouts fail explicitly, never lose members.
  Code encodes the selected bytes for transport; it does not rewrite source/graph.
- `start_debugger`: validate saved/inactive/committed mechanical state and use
  the actual VPE Debugger HTTP shape. Inspect actual run/nested results next.
- `cancel_owned_run`, `delete_owned_resource`: affect only this scope's IDs.
- `list_owned_resources`, `get_owned_resource`: inspect local ownership and
  independently read back exact remote identities, including cleanup results.

Each write takes a stable `operation_id` (lowercase letter followed by letters,
digits or underscores, at most 64 characters). Repeating identical input reads
back its result; changed input with that ID is rejected. A private SQLite file
in the evidence directory commits intent before sending the request. An
interrupted/ambiguous write is never automatically repeated, even after restart.
Use the retained evidence and an explicit recovery decision for uncertainty;
do not use a new ID/name to conceal or replay an unknown operation. Preserve this
directory across server restarts. Its namespace, HTTPS origin and source root
binding cannot silently change. Use separate directories/namespaces per role.

Always collect complete run/action evidence before deleting a container: SOAR
cascades its execution rows. Playbook/asset deletion can retain disabled history;
inspect actual remote state, not only the deletion reply. There is no bulk cleanup
or arbitrary REST tool. These controls do **not** sandbox arbitrary Python in a
playbook or an untrusted role with account credentials: use trusted operators,
SOAR-side permissions and external execution isolation.

SOAR's import acknowledgment does not supply an ID. Only a positive acknowledgment
after absent-name preflight and force=false creation permits an exact single
name/SCM readback to record ownership. Ambiguous/lost responses remain unknown,
not an invitation to retry. Import never requests activation; inspect its inactive
readback and validation before explicitly starting Debugger. SOAR 8.5.0.248 removes
one trailing LF from the tested imported Python and adds `create_time` metadata.
Exact transport/export capture does **not** promise byte-identical SOAR persistence.

Saved VPE and Debugger routes were traced to the served SOAR **8.5.0.248** frontend
and verified through real authenticated HTTPS. `/coa/playbooks/` and `/playbooks`
are version-sensitive web interfaces, not a documented cross-version REST
stability guarantee. Unsupported versions require explicit verification; there
is no ordinary-Playbook or Django fallback. Actual SDK write/cleanup tests and a
fresh DNS Builder/Reviewer workflow establish this specific integration, not
support for another server version or every connector.

The tool catalog has 13 read-only tools, or 24 with an owned scope, including
nine mutations. Version 0.3.1 keeps 0.3.0's runtime implementation unchanged and
adds MIT licensing and standalone release materials. The original tool set was
used in a complete DNS Builder/Reviewer workflow; 0.3.0 was subsequently used in
an eight-group SMTP workflow that returned PASS and published a Provider/Seed.
That workflow result is not an independent audit of every generated product
behavior or proof that all 24 tools were used. The added tools also have separate
SDK/HTTPS integration checks. See [tested boundaries](docs/CLIENTS.md#server-proof-and-permissions).

List pagination is explicit and zero-based; no hidden all-pages requests.
Results keep the returned data and nested statuses unchanged. A successful MCP
tool or HTTP request does not mean an action succeeded, a VPE was used, or a
product passed. The default 16,000-character view is a **preview**, not a semantic
summary: the complete HTTP body remains available via the evidence ID/resource.
Follow every `next_offset` needed for your question. UTF-8 reads use Unicode
character offsets; binary reads use byte offsets and program-generated Base64.

Evidence consists of exact HTTPX-decoded response body bytes (`<id>.body`) and
mechanical request/body/timing/status metadata (`<id>.json`). Authorization headers
are not logged. Errors and non-JSON bodies are retained, not shortened to a
success message. A transport failure preserves any partial response bytes,
observed HTTP status and complete exception type/message, explicitly marking
the body incomplete. With no HTTP response it stores the diagnostic instead,
identified by `body_source`. Local files are private, immutable-by-convention,
created without replacement; retain them for audit. The full body is also an MCP
resource at `soar-evidence://<id>/body`. Never commit private evidence or tokens.

## Development and scope

Install `.[test]`; run `python -m pytest -p no:cacheprovider tests`.
Tests use mock HTTP plus a local TLS fixture and actual SDK stdio protocol.
They prove client/protocol behavior, **not** deployed SOAR compatibility.
The public API references used are in `SOURCES.md`; `docs/CLIENTS.md` separates
local protocol checks from actual server/client versions and workflow results.
See [CONTRIBUTING.md](CONTRIBUTING.md) for tests and packaging. Runtime responses,
operation journals, deployment settings and credentials belong outside Git.

## License

MIT for this project's original code. Dependencies retain their own licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
