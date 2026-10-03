# Threat Model

## Assets

- Host machine (hypervisor / bare metal)
- Other tenants' sandboxes
- Database (sandbox metadata, user data)
- API credentials (JWT secrets, API keys)

## Threat Actors

| Actor | Capability | Example |
|---|---|---|
| **Malicious tenant** | Executes arbitrary code inside sandbox | Tries container escape, fork bomb, network exfil |
| **Credential thief** | Stolen API key | Creates sandboxes on another user's quota |
| **Insider** | Access to infra | Reads DB, steals JWT secret |

## Mitigations

| Threat | Mitigation |
|---|---|
| Container escape via kernel | Keep host kernel patched; use read-only rootfs; no privileged mode |
| Fork bomb | `--pids-limit 64` |
| Memory DoS | `--memory` cgroup limit |
| Network exfiltration | `--network none` by default |
| Privilege escalation | `--cap-drop ALL`, `no-new-privileges` |
| Cross-tenant data access | All queries scoped by `user_id`; JWT/API key identifies user |
| JWT secret compromise | Rotate `JWT_SECRET_KEY`; all tokens are immediately invalidated |
| Replay attacks | JWT `exp` claim; tokens expire in 60 min |
| Log injection | stdout/stderr are stored as opaque text, not executed |
| SQL injection | All DB access via SQLAlchemy ORM with parameterized queries |

## Residual Risks

- Shared kernel: Docker containers share the Linux kernel. A kernel 0-day can break isolation.
- Docker daemon socket: Mounting `/var/run/docker.sock` in the API container gives it equivalent-of-root access to the host. In production, use a separate Docker API proxy (e.g., `docker-socket-proxy`) with restricted permissions.
- No seccomp profile: Adding a seccomp profile (blocking dangerous syscalls like `ptrace`, `mount`, `setuid`) further hardens the sandbox.
- No AppArmor/SELinux: A MAC policy would add defense-in-depth.
