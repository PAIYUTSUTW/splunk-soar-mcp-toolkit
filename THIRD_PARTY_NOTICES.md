# Third-party notices

This distribution imports published dependencies; it does not vendor or copy
their implementations. Keep their original license files when redistributing
an installed environment or an offline dependency wheelhouse.

- **MCP Python SDK 1.30.0** — MIT License; Copyright (c) 2024 Anthropic, PBC.
  Source: https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0
  Its distribution includes `mcp-1.30.0.dist-info/licenses/LICENSE`.
- **HTTPX 0.28.1** — BSD-3-Clause; Copyright © 2019 Encode OSS Ltd.
  Source: https://github.com/encode/httpx/tree/0.28.1
  Its distribution includes `httpx-0.28.1.dist-info/licenses/LICENSE.md`.

These are separate libraries, not endorsements of this project. MCP protocol,
schema handling and stdio transport come from the SDK, not a copied protocol
implementation. See SOURCES.md for design and API references.

Setuptools is the build backend. pytest and trustme are test-only dependencies;
they are not imported by the runtime package. A resolver also installs each
runtime library's declared transitive dependencies. Their distributions retain
authoritative metadata, copyright and license texts. The release audit records
the exact resolved environment; this notice does not replace or relicense those
files. LICENSE records the separate status of this project's original code.
