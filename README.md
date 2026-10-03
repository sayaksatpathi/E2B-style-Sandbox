# E2B-Style Ephemeral Code Sandbox Platform

A production-grade, self-hosted ephemeral code sandbox platform — similar to [E2B](https://e2b.dev) — built with FastAPI, Docker, PostgreSQL, and full observability.

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Docker](https://img.shields.io/badge/docker-compose-blue)
![Tests](https://img.shields.io/badge/tests-19%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## What it does

- **Create isolated sandboxes** — ephemeral Docker containers (Python, Node, Go, Bash, Ruby)
- **Execute code** with hard OS-level timeouts and shell injection prevention
- **Network policies** — `none` (fully isolated), `restricted` (internal bridge, no internet), `full`
- **Per-user quota** — max 5 active sandboxes per user
- **TTL expiry** — background worker destroys expired containers automatically
- **Pause / resume / fork** sandboxes
- **JWT + API key authentication**
- **Rate limiting** via slowapi
- **Full observability** — Prometheus metrics, Grafana dashboards, OpenTelemetry tracing
- **CLI** for local use
- **Docker Compose** for local deployment
- **Kubernetes manifests** for cloud deployment
- **GitHub Actions CI/CD**

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (or Docker Engine on Linux)

### Run the full stack

```bash
git clone https://github.com/sayaksatpathi/E2B-style-Sandbox.git
cd E2B-style-Sandbox
cp .env.example .env
docker compose up -d
```

Check health:

```bash
curl http://localhost:8000/health
```

| Service | URL |
|---|---|
| API + Swagger | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (admin / admin) |
| Prometheus | http://localhost:9090 |

---

## API Usage

### Get a token

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}'
```

### Create a sandbox

```bash
curl -X POST http://localhost:8000/sandboxes \
  -H "X-API-Key: dev-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"template": "python", "ttl_seconds": 300, "network_policy": "restricted"}'
```

### Execute code

```bash
curl -X POST http://localhost:8000/sandboxes/{sandbox_id}/exec \
  -H "X-API-Key: dev-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"command": "python3", "args": ["-c", "print(2 + 2)"], "timeout": 10}'
```

### List your sandboxes

```bash
curl http://localhost:8000/sandboxes \
  -H "X-API-Key: dev-api-key-1"
```

### Destroy a sandbox

```bash
curl -X DELETE http://localhost:8000/sandboxes/{sandbox_id} \
  -H "X-API-Key: dev-api-key-1"
```

---

## CLI

```bash
pip install -e .

export SANDBOX_API_URL=http://localhost:8000
export SANDBOX_API_KEY=dev-api-key-1

sandbox create --template python --ttl 300
sandbox exec <sandbox-id> python3 -c "print('hello')"
sandbox logs <sandbox-id>
sandbox pause <sandbox-id>
sandbox resume <sandbox-id>
sandbox destroy <sandbox-id>
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI API │────▶│  PostgreSQL │
│ (CLI/HTTP)  │     │  :8000       │     │  :5432      │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │ DockerRuntime│
                    │  (sandbox    │
                    │  containers) │
                    └──────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │ Prometheus │  │  Grafana   │  │    OTel    │
   │  :9090     │  │  :3000     │  │ Collector  │
   └────────────┘  └────────────┘  └────────────┘
```

### Key design decisions

| Concern | Solution |
|---|---|
| Exec timeout | Linux `timeout --kill-after=2 <seconds>` inside the container (exit code 124 = timed out) |
| Network isolation | `restricted` uses a Docker bridge with `internal=True` — no external routing |
| Auth | JWT (python-jose) + static API key via `X-API-Key` header |
| Migrations | Alembic with async runner; SQLite fallback for tests |
| Rate limiting | slowapi: 20/min create, 60/min list, 100/min exec |
| Quota | Max 5 active sandboxes per user, enforced in the DB layer |
| Cleanup | Background worker polls every 30s and destroys expired containers |

---

## Project Structure

```
.
├── api/                    # FastAPI app, routes, auth, schemas, rate limiting
├── cli/                    # Typer CLI
├── database/               # SQLAlchemy models, session, Alembic migrations
├── observability/          # Prometheus metrics, OTel tracing, Grafana dashboards, alerts
├── runtimes/               # Abstract runtime + DockerRuntime + MicroVM stub
├── sandbox_manager/        # Business logic, quota, audit logging
├── tests/                  # Unit tests (19 passing, no Docker/Postgres required)
├── worker/                 # TTL cleanup background process
├── deploy/
│   ├── docker-compose/     # Docker Compose docs
│   └── kubernetes/         # K8s manifests (Deployment, HPA, NetworkPolicy, RBAC, etc.)
├── .github/workflows/      # CI/CD: lint → test → security → build → push to GHCR
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
└── requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```env
JWT_SECRET_KEY=change-me-before-production
API_KEYS=dev-api-key-1,dev-api-key-2
GRAFANA_PASSWORD=admin
SANDBOX_RUNTIME=docker
CLEANUP_INTERVAL_SECONDS=30
```

---

## Running Tests

No Docker or PostgreSQL required — tests use SQLite and a mock runtime.

```bash
pip install -r requirements.txt
pytest tests/unit/ -v
```

---

## Kubernetes Deployment

Manifests are in `deploy/kubernetes/`. Apply with:

```bash
kubectl apply -f deploy/kubernetes/
```

Includes: Deployment, Service, Ingress, ConfigMap, Secret, RBAC, NetworkPolicy, ResourceQuota, LimitRange, HPA, PodDisruptionBudget.

---

## Supported Templates

| Template | Image |
|---|---|
| `python` | `python:3.11-slim` |
| `node` | `node:20-slim` |
| `bash` | `bash:5.2` |
| `go` | `golang:1.21-alpine` |
| `ruby` | `ruby:3.2-slim` |

---

## Security

- All containers run as `nobody`, `cap_drop: ALL`, `no-new-privileges`
- Shell metacharacters rejected at the API layer before reaching Docker
- `restricted` network: internal Docker bridge, no external routing
- `none` network: completely isolated (`--network none`)
- JWT expiry + static API key rotation via env var
- Bandit security scan and Trivy image scan in CI

---

## License

MIT
