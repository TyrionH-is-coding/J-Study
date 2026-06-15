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

Uploaded PDFs and generated artifacts are local during the pilot because citation preview needs the original PDF. Keep `JSTUDY_JOB_RETENTION_HOURS` nonzero for public testing; `.env.example` uses `72`. Use `168` if reviewers need a full week. For formal user history or course libraries, move uploads and generated artifacts to Tencent COS or another object store instead of relying on server disk.

The upload UI reads `GET /api/options` for public scenarios and parser profiles. `fast` uses PyMuPDF and is public by default. `quality` is reserved for MinerU, hidden from normal users at first, and should stay disabled until MinerU credentials or a local adapter are configured.
