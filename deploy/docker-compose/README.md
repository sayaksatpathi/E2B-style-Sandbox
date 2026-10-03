# Docker Compose Deployment

The `docker-compose.yml` at the repository root deploys the full local stack:

| Service | Port | Purpose |
|---|---|---|
| `api` | 8000 | Sandbox API |
| `worker` | — | TTL cleanup background process |
| `postgres` | 5432 | Metadata database |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Dashboards (admin/admin) |
| `otel-collector` | 4317/4318 | Trace aggregation |

## Quick start

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8000/health
```
