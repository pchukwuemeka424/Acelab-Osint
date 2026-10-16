# Phishing Infrastructure Attribution Engine (PIAE)

PIAE is an investigation workspace for suspicious domains and related infrastructure. It stores observations with provenance, builds a relationship graph, and explains association scores. It does not assert that an asset is malicious, and it does not name a threat actor unless a stored source record explicitly does.

The primary screen is the graph workspace. Demonstration mode is the default, so the application runs without provider API keys.

## Local demo

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000
```

In another shell:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The workspace opens directly. Investigations are stored on the local analyst account.

Startup creates the development accounts and source settings. It does not load an investigation. A search collects public DNS, mail records, registration, certificates, current network ownership, Wayback capture dates, and one page snapshot. A full name also checks public pages. A page is kept when it contains that name. Those sources do not need an API key. They do not include paid address history or search rankings. URLHaus and OpenRouter stay off until their keys are set. Set `DEMO_MODE=true` to store only the submitted indicator for a domain, URL, address, or fingerprint. A full name still checks public pages.

A live investigation is compared with that analyst's saved cases. A rare kit structure, logo path, nameserver, or contact is drawn on the graph with the registration, certificate, and Wayback dates. Shared hosting and public DNS stay off that comparison. Save a case to include it in later searches. The report can export a handoff where each claim cites an observation.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The UI is published on `http://localhost:8080`. Postgres is canonical. Redis and a Celery worker run investigations when `INVESTIGATION_EAGER=false`. Neo4j is optional:

```bash
docker compose --profile neo4j up --build
```

Set `NEO4J_URI=bolt://neo4j:7687` on the API and worker when that profile is enabled. If Neo4j is unset or unavailable, graph algorithms use NetworkX and the API still serves the Postgres graph.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest
cd frontend && npm test
cd frontend && npx playwright test
```

## OpenRouter

Narrative text is optional. Set `OPENROUTER_API_KEY` and, if you want a different model, `OPENROUTER_MODEL`. The client calls only `https://openrouter.ai/api/v1/chat/completions`. Without a key, or if the call fails, the report stays the deterministic evidence summary and `narrative_status` is `skipped` or `failed`.

## Documentation

- [Architecture](docs/architecture.md)
- [Data sources](docs/data-sources.md)
- [API](docs/api.md)
- [Security](docs/security.md)
- [Operations](docs/operations.md)
- [Dependencies](docs/dependencies.md)

## Limits

Containers starting does not make this a finished production deployment. TLS, a separate migration role, secret management, and provider terms are still configuration. See the operations and security notes. PDF export is not implemented. Association scores are an unvalidated heuristic baseline, not probabilities.
