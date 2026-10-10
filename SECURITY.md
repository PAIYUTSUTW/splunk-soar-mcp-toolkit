# Security and deployment boundaries

Start with a read-only, least-privilege SOAR Automation token in a disposable
test environment. The server does not create accounts, discover credentials or
elevate permissions. Only enable owned writes for trusted operators.

- HTTPS certificate verification is required. Supply a trusted CA when needed;
  do not bypass TLS verification. Requests do not follow redirects, use ambient
  proxy/netrc credentials or automatically retry.
- Read tools can access records allowed by the configured token, including
  records outside this namespace. Read-only annotations are client hints, not
  an authorization boundary. Restrict the token on SOAR itself.
- Writes require a private scope and recorded ownership. This limits accidental
  changes to unrelated resources; it is not a sandbox for arbitrary playbook
  Python, an untrusted MCP client or anyone who already possesses the token.
- Use separate private evidence directories, namespaces and authored-source
  roots for separate roles. Do not expose this stdio process as a shared network
  service without a separately reviewed authentication/isolation layer.
- Full response bodies and write journals can contain incident data, asset
  configuration, message contents and secrets returned by SOAR. Authentication
  headers are not logged, but body redaction is not promised. Keep evidence
  outside Git, protect backups, and review material before sharing it with a
  model, another person or an external service.
- Keep journals after a timeout or lost write response. Do not use a new
  operation ID to retry an unknown side effect. Investigate retained observations
  and remote state before an explicit recovery decision.
- Collect nested run results before deleting containers: SOAR can cascade those
  rows. Retired assets/playbooks may remain as disabled server history.

The VPE and retirement web interfaces are version-sensitive. Only the documented
tested SOAR version is verified; a working HTTPS connection is not compatibility
or product acceptance. This community project is not an official Splunk service.

## Reporting a vulnerability

Do not post tokens, real hostnames, incident records or unredacted response bodies
in a public issue. Use GitHub's private vulnerability reporting if the repository
Security tab offers it. Otherwise open a minimal issue requesting a private
contact channel, without exploit details or private data. There is no guaranteed
response time. Include the package/server version and a synthetic reproduction
when a private channel has been established. Rotate exposed credentials through
your SOAR administrator; deleting a public file does not retract copied secrets.
