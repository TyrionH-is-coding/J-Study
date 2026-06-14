# Backend Docker Compose

This is the backend-only deployment scaffold for the pilot server.

Run from the repository root:

```powershell
Copy-Item .env.example .env
# Fill SILICONFLOW_API_KEY and JSTUDY_ADMIN_TOKEN in .env before starting the service.
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
```

Health check:

```powershell
curl http://127.0.0.1:8765/api/health
```

Readiness check after `.env` and mounted files are configured:

```powershell
curl http://127.0.0.1:8765/api/readiness
```

The readiness response should be `ready` before users submit PDFs.
To verify the configured SiliconFlow chat and embedding models during deployment, run:

```powershell
curl "http://127.0.0.1:8765/api/readiness?probe_provider=true"
```

Persistent runtime files are written under `data/jobs` on the host and mounted to `/app/data/jobs` in the container.
Job lifecycle state is persisted at `data/jobs/jobs.json`.
Admin runtime settings are stored under `data/settings` by default. Keep that directory mounted so model, RAG, parser, search, and content-pack settings survive container rebuilds.
