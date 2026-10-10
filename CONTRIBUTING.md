# Contributing

Use Python 3.11+ on Linux and an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[test]'
.venv/bin/python -m pytest -p no:cacheprovider tests
```

These tests use synthetic data, mock HTTP, local TLS and SDK stdio. They do not
need a real SOAR token, execute production actions or make model calls. Do not
add live credentials or depend on a developer's home directory. CI runs these
checks on Linux; it does not certify additional SOAR versions or client OSes.

For a bug, first add the smallest failing externally observable test, then fix
the owning behavior and run the relevant tests and full suite. Preserve complete
observations, explicit pagination and unknown write outcomes. Do not add hidden
retries, disable TLS, relax ownership checks or convert HTTP success into a
product verdict to make a test pass.

Build independent distributions:

```sh
.venv/bin/python -m pip install build
.venv/bin/python -m build
```

Before publishing, install the wheel and source distribution in separate clean
environments and run the tests with `SOAR_MCP_INSTALLED_TEST=1` so subprocesses
also use the installed package. Inspect both archives for unexpected files and
run a secret scan, for example `gitleaks dir --redact .`. Keep tokens, PEM files,
deployment configuration, response bodies, journals and execution evidence out
of the repository. The example `.env` templates intentionally contain no token.

A real SOAR integration test requires separate authorization and a disposable
scope. Record server/client versions, chosen permissions, nested outcomes,
uncertainty and cleanup privately. Do not submit raw deployment evidence in a
pull request. Report security issues using [SECURITY.md](SECURITY.md).
