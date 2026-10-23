# Execution

## Current implementation

`service.py` is the only outbound target transport. It supports bounded HTTP/HTTPS
requests, rejects embedded URL credentials and unsupported schemes, resolves and
validates every destination address, pins the connection to that validated IP,
preserves the original Host/SNI values, disables environment proxies and redirects,
and enforces timeouts and a configured response limit. Loopback targets are
allowed in development when `ALLOW_LOCAL_TARGETS=true`; private and reserved
addresses are blocked unless an operator explicitly enables
`ALLOW_PRIVATE_NETWORK_TARGETS`.

Non-read-only methods require an explicit `confirm_unsafe` API flag. The workspace
asks for confirmation before sending them. Request credentials and response bodies
are returned only to the active UI response; execution history stores a minimal
request snapshot, sanitized response headers, status, duration, size, outcome, and
safe error summary.

## Current limitations

- No saved request collections, environment substitution, auth helper, assertion
  evaluation, execution report export, or per-project request-rate budget yet.
- Persistence tests use SQLite fixtures; PostgreSQL integration and restart
  persistence have not been verified in this environment.
- Private network access is a server-wide opt-in, not a per-project allowlist.

## Rules

- Keep every outbound target call in this service. Discovery must use the same
  policy rather than issuing independent HTTP requests.
- Never follow redirects automatically; any future redirect support must validate
  the next hop before connecting.
- Add tests for policy denials, redirect behavior, response bounds, and local
  fixture targets.
- Do not persist request secrets or full response bodies by default.
