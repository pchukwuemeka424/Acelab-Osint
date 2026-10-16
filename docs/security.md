# Security and threat model

PIAE is a defensive investigation tool. It does not scan for exploits, collect credentials, or take response actions. Report text is not executed.

## What is protected

- Passwords are hashed with Argon2. Sessions are signed, HTTP-only cookies. CSRF uses a matching readable cookie and header.
- Roles are `analyst` and `admin`. Analysts only read their own investigations. Administrators can read investigations and change source toggles.
- Indicators are parsed as data. They are never passed to a shell.
- Outbound collector calls allow only HTTPS to `openrouter.ai`, `rdap.org`, `crt.sh`, and `urlhaus-api.abuse.ch`, plus the public profile hosts in the BlindEye platform list. Provider redirects are rejected. A profile check may follow one redirect that stays on the same host. Resolved addresses are checked before the request and again before connect. Loopback, private, link-local, multicast, reserved, and other non-global addresses are refused, which includes cloud metadata addresses.
- Investigation inputs that are private, loopback, link-local, or metadata names are rejected. Documentation TEST-NET addresses are accepted as subjects and are still blocked as outbound destinations.
- Login and investigation creation are rate limited.
- Audit events cover login, investigation creation, exports, notes, and source changes.
- Logs pass through a redaction filter for the OpenRouter key. Debug is off unless `DEBUG=true`.
- Exports allow only JSON and CSV and use a generated filename.

## What still needs deployment hardening

- Compose uses one database role that can create tables, so migrations and the app share credentials. A production deployment should split a migration role from a runtime role.
- Compose publishes HTTP on port 8080. Put the example in `nginx/nginx.conf` in front of it with real certificates, and set `ENVIRONMENT=production` so the session cookie is marked Secure.
- Development passwords in `.env.example` must be replaced. Do not commit a real `.env`.
- Provider allowlisting reduces SSRF; it does not replace network egress controls around the worker.
- Dependency advisories should be reviewed on each upgrade. `npm audit` currently reports transitive issues in the frontend toolchain. Do not treat a clean container start as a completed security review.
