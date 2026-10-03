# Runbook

## Local Setup (Docker Compose)

```bash
# 1. Clone the repo
git clone <repo-url>
cd e2b-style-sandbox

# 2. Copy env template
cp .env.example .env
# Edit .env to set JWT_SECRET_KEY, API_KEYS

# 3. Start all services
docker compose up -d

# 4. Check health
curl http://localhost:8000/health

# 5. Get a token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}'

# 6. Create a sandbox
curl -X POST http://localhost:8000/sandboxes \
  -H "X-API-Key: dev-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"template":"python","ttl_seconds":300}'

# 7. Execute code
curl -X POST http://localhost:8000/sandboxes/<ID>/exec \
  -H "X-API-Key: dev-api-key-1" \
  -H "Content-Type: application/json" \
  -d '{"command":"python","args":["-c","print(2+2)"]}'
```

## CLI Usage

```bash
pip install -e ".[cli]"
export SANDBOX_API_KEY=dev-api-key-1

sandbox create --template python --ttl 300
sandbox exec <id> python -c "print(2+2)"
sandbox logs <id>
sandbox pause <id>
sandbox resume <id>
sandbox destroy <id>
```

## Running Tests

```bash
# Unit tests (no services needed)
pip install pytest pytest-asyncio
pytest tests/unit/ -v

# Integration tests (requires docker-compose up)
pytest tests/integration/ -v

# Security tests (requires docker-compose up)
pytest tests/security/ -v
```

## Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f deploy/kubernetes/

# Verify
kubectl -n sandbox-platform get pods
kubectl -n sandbox-platform get svc

# Port-forward for testing
kubectl -n sandbox-platform port-forward svc/sandbox-api 8000:80
```

## Alerts Reference

| Alert | Severity | Action |
|---|---|---|
| `APIDown` | critical | Check pod logs; restart if needed |
| `SandboxCreationFailures` | critical | Check Docker daemon; check DB connectivity |
| `HighExecutionFailureRate` | warning | Check container OOM / timeout config |
| `TooManyActiveSandboxes` | warning | Check cleanup worker; increase quota |
| `SlowExecutions` | warning | Check host resource contention |

## Observability URLs

| Service | URL |
|---|---|
| API Swagger | http://localhost:8000/docs |
| API Metrics | http://localhost:8000/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |
