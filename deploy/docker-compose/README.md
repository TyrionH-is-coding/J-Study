# Backend Docker Compose

This is the backend-only deployment scaffold for the pilot server.

Run from the repository root:

```powershell
Copy-Item .env.example .env
# Fill SILICONFLOW_API_KEY in .env before starting the service.
docker compose -f deploy/docker-compose/api.compose.yml up -d --build
```

Health check:

```powershell
curl http://127.0.0.1:8765/api/health
```

Persistent runtime files are written under `data/jobs` on the host and mounted to `/app/data/jobs` in the container.
