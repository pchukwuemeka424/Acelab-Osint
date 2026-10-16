# API

The workspace opens as the local analyst account without a sign-in. A session cookie is optional. When a session cookie is present, state-changing routes also require the `X-CSRF-Token` header to match the `piae_csrf` cookie.

- `POST /api/auth/login` `{email, password}`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `PATCH /api/settings`
- `GET /api/investigations` and `GET /api/investigations?saved=true`
- `GET /api/investigations/current`
- `POST /api/investigations` `{indicator}` returns a job. A completed investigation for the same indicator is returned again instead of being duplicated.
- `GET /api/investigations/{id}`
- `PATCH /api/investigations/{id}` `{is_saved, title}`
- `GET /api/investigations/{id}/jobs/{job_id}`
- `GET /api/investigations/{id}/entities?entity_type&sort&direction&q&page`
- `GET /api/investigations/{id}/entities/{entity_id}/image` returns a recorded logo image
- `GET /api/investigations/{id}/graph?types&rel_types&risk&observed_after&observed_before` also returns `campaign` for rare artifacts shared with this analyst's saved cases, and the registration, certificate, and Wayback timeline.
- `POST /api/investigations/{id}/graph/expand?entity_id` returns neighbors plus `suggestions` ranked by rarity. Shared hosting, public DNS, and redacted contacts are marked weak.
- `POST /api/investigations/{id}/graph/path` `{source_id, target_id}`
- `GET /api/investigations/{id}/report`
- `POST /api/investigations/{id}/notes` `{note}`
- `GET /api/investigations/{id}/export?format=json|csv|handoff` — `handoff` cites each claim to an observation and lists what is not claimed.
- `GET /api/notifications` and `POST /api/notifications/read`
- `GET /api/sources` and `PUT /api/sources/{name}` (admin)
- `GET /api/audit` (admin)
- `GET /api/health`

Entity types in the panel are `domain`, `whois`, `ip`, `certificate`, `ssh`, `contact` (also `name` and `account`), `file`, `hypothesis`, `seo`, `logo`, `url` (same-host pages), and `more` (nameserver, hosting, indicator, fingerprint). Sort keys are `domain`, `registrar`, `reg_date`, `exp_date`, and `ip`. An investigation indicator may be a domain, URL, IP address, certificate fingerprint, or full name.
