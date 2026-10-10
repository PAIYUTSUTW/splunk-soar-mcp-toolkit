# Upstream dependencies and API references

The package uses published dependencies, with no copied upstream implementation.

- Official MCP Python SDK 1.30.0, MIT:
  https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0
  https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/LICENSE
- HTTPX 0.28.1, BSD-3-Clause: https://github.com/encode/httpx/tree/0.28.1
- pytest and trustme are test dependencies only; dependency distributions retain
  their own license metadata/notices.
- FastMCP protocol-level testing pattern: https://gofastmcp.com/servers/testing
- Explicit tool selection/read-only configuration pattern:
  https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md
- Isolated session/deployment configuration pattern:
  https://github.com/microsoft/playwright-mcp

SOAR HTTP interfaces (documented interfaces, not live compatibility claims):

- https://help.splunk.com/en/splunk-soar/soar-cloud/rest-api-reference/using-the-splunk-soar-rest-api/query-for-data
- https://help.splunk.com/en/splunk-soar/soar-cloud/rest-api-reference/app-endpoints/rest-app
- https://help.splunk.com/en/splunk-soar/soar-cloud/rest-api-reference/artifact-endpoints/rest-artifact
- https://help.splunk.com/en/splunk-soar/soar-cloud/rest-api-reference/playbook-endpoints/rest-playbook
- https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/6.4.0/run-action-endpoints/rest-run-action
- https://help.splunk.com/en/splunk-soar/soar-on-premises/rest-api-reference/6.4.0/run-playbook-endpoints/rest-run-playbook

Do not treat documented ordinary playbook execution as VPE Debugger equivalence.
No private installation paths, internal Django handlers or test verdicts belong
in the portable implementation.

## Operational extension references

These implementations were inspected at fixed commits as API/design references;
no source was copied or vendored and no popularity claim is made:

- Ewiges-M/splunk-soar-mcp, `916b47006f62cc08f875e71c5cf190307d707d50`, MIT:
  https://github.com/Ewiges-M/splunk-soar-mcp/tree/916b47006f62cc08f875e71c5cf190307d707d50
  Log endpoint/search, CEF read-before-merge and Playbook bundle transport.
- huseynAgazade/splunk-soar-mcp, `02b01a0e0a81c64d1fc12b60f86a8ecee4dbdf7f`, MIT:
  https://github.com/huseynAgazade/splunk-soar-mcp/tree/02b01a0e0a81c64d1fc12b60f86a8ecee4dbdf7f
  Installed action-definition endpoint and explicit operations.
- abuis78/soar_mcp_server, `1f082dc1d61487657d138671e2d26b69ea33163d`:
  https://github.com/abuis78/soar_mcp_server/tree/1f082dc1d61487657d138671e2d26b69ea33163d
  Artifact API, integer `scm_id` import and export-backed source/graph inspection.
  No license reuse is asserted; reference inspection only.

Differences are deliberate: exact IDs instead of fuzzy schema selection, complete
evidence instead of truncation, owned-only writes with no automatic replay,
explicit run_automation=false, force=false import and no filesystem extraction,
source rewriting, arbitrary REST escape hatch or product verdict logic.
