# Security Model

## Authentication

- **JWT Bearer tokens** — issued by `POST /auth/token` with configurable expiry (default 60 min).
- **API Keys** — static keys in `API_KEYS` env var; suitable for service-to-service calls.
- Both are validated in `api/auth.py` before any handler executes.

## Authorization

- Every sandbox is scoped to a `user_id` derived from the credential.
- All `GET/DELETE/exec/pause/resume/fork` operations validate `sandbox.user_id == caller_id`.
- Callers cannot enumerate or modify other users' sandboxes.

## Container Isolation

Every sandbox container is created with:

| Control | Value | Effect |
|---|---|---|
| `--user nobody` | UID 65534 | Non-root process inside container |
| `--cap-drop ALL` | — | No Linux capabilities |
| `--security-opt no-new-privileges` | — | Cannot gain privileges via setuid |
| `--network none` (default) | — | No network connectivity |
| `--pids-limit 64` | configurable | Prevents fork bombs |
| `--memory` | configurable | OOM-killed if exceeded |
| `--cpus` | configurable | CPU-throttled by kernel cgroups |
| `--read-only` rootfs + `/tmp tmpfs` | exec only in /workspace | No persistent writes to image layers |

## Input Validation

- All API inputs are validated with Pydantic v2 — templates, TTL, CPU, memory bounds enforced at schema level.
- `command` field rejects shell metacharacters (`;`, `&&`, `||`, `` ` ``, `$(`, `|`, `>`, `<`).
- Commands are passed as a list to Docker SDK — **no shell interpolation** occurs.
- Stdout/stderr are capped at 64 KB to prevent log flooding.

## Rate Limiting

- Implemented via `slowapi` — currently 100 requests/minute per IP (configurable).
- Per-user sandbox quota: max 5 active sandboxes.

## Audit Logging

- Every create/exec/pause/resume/fork/destroy is written to `audit_logs` with timestamp, user, IP.

## Secret Handling

- `JWT_SECRET_KEY` and `API_KEYS` are env vars; never hardcoded.
- In Kubernetes they are `kind: Secret`.
- DB credentials similarly env-injected; never appear in logs.

## Known Limitations and Security Boundary

> **Docker is not equivalent to a hardened microVM.**

| Threat | Docker Containers | MicroVM (Firecracker) |
|---|---|---|
| Kernel shared with host | ✅ Yes — same kernel | ❌ No — separate kernel per VM |
| Container escape exploits | Possible via kernel CVEs | Much harder — KVM hardware isolation |
| Suitable for hostile untrusted code | **No** | Better, but still needs hardening |
| Suitable for internal/trusted workloads | Yes | Yes |

This implementation is appropriate for:
- Internal developer tooling
- Trusted user workloads (teams, SaaS users who agree to ToS)
- Educational / portfolio demonstration

It is **not** appropriate for anonymous multi-tenant execution of fully hostile code without:
- Upgrading to Firecracker / gVisor / Kata Containers
- Adding seccomp profiles
- Adding AppArmor / SELinux policies
- Running Docker-in-Docker or dedicated worker nodes per tenant
