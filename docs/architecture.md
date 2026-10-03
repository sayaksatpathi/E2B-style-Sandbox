# Architecture

## Overview

```
                    Client / CLI
                         │
                         ▼
                ┌──────────────────┐
                │  Sandbox API      │
                │     FastAPI       │
                │  /sandboxes       │
                │  /auth            │
                │  /health          │
                │  /metrics         │
                └────────┬─────────┘
                         │
                    Auth + Quota
                         │
                         ▼
                ┌──────────────────┐
                │ SandboxManager    │
                │ lifecycle engine  │
                └────────┬─────────┘
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       SandboxRuntime          PostgreSQL DB
     (DockerRuntime /           sandbox +
      MicroVMRuntime)           executions +
             │                  audit_logs
             ▼
       Docker Engine
             │
    ┌────────┴──────────┐
    │  Ephemeral         │
    │  Container         │
    │  (per sandbox)     │
    │  - CPU cgroup      │
    │  - mem cgroup      │
    │  - PID limit       │
    │  - network=none    │
    │  - no-new-privs    │
    └────────────────────┘
             │
       Cleanup Worker
       (APScheduler-like loop)
       scans expired sandboxes
       every 30s
```

## Component Responsibilities

| Component | Responsibility |
|---|---|
| **API (FastAPI)** | HTTP routing, auth, validation, rate limiting |
| **SandboxManager** | Lifecycle state machine, quota enforcement, audit logging |
| **SandboxRuntime** | Abstract interface over Docker / microVM backends |
| **DockerRuntime** | Calls Docker SDK to create/exec/destroy containers |
| **Cleanup Worker** | Periodic background loop; destroys expired containers |
| **PostgreSQL** | Durable sandbox metadata, execution records, audit trail |
| **Prometheus** | Metrics scraping and alerting |
| **Grafana** | Dashboards for active sandboxes, exec latency, failures |
| **OTel Collector** | Trace aggregation and forwarding |

## Request Flow

```
POST /sandboxes/{id}/exec
  │
  ├─ Auth middleware (JWT / API key)
  ├─ Rate limiting (slowapi)
  ├─ Schema validation (Pydantic)
  │
  ▼
SandboxManager.exec_in_sandbox()
  │
  ├─ Load sandbox from DB
  ├─ Check status / expiry
  │
  ▼
DockerRuntime.exec()
  │
  ├─ docker exec_run(command, user=nobody, workdir=/workspace)
  ├─ Capture stdout/stderr
  │
  ▼
Store Execution record in DB
  │
  ▼
Return ExecResponse
```
