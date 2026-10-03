# Failure Experiments

## 1. Sandbox Timeout

**Trigger:** Execute `python -c "import time; time.sleep(999)"` with `timeout=3`

**Expected behavior:** API returns within ~3s with `exit_code != 0` or `timed_out=true`

**Observed behavior:** Docker `exec_run` with timeout; container process is killed by the Docker daemon after timeout.

**Metrics:** `sandbox_execution_failures_total{error_type="TimeoutError"}` increments

**Alert:** `SlowExecutions` fires if p95 > 10s

**Recovery:** Sandbox remains READY; next exec unaffected.

---

## 2. Memory Exhaustion

**Trigger:** `python -c "x = bytearray(600 * 1024 * 1024)"` in a 512 MB sandbox

**Expected behavior:** Container is OOM-killed; exit_code = 137

**Observed behavior:** Docker cgroup memory limit triggers OOM kill; container stays alive (process inside dies)

**Metrics:** `sandbox_execution_failures_total` increments

**Recovery:** Sandbox status returns to READY; subsequent execs work.

---

## 3. CPU Exhaustion

**Trigger:** `python -c "while True: pass"` with cpu_limit=0.1

**Expected behavior:** Process runs but is heavily throttled; cannot saturate host CPU

**Observed behavior:** CPU cgroups enforce quota; other sandboxes unaffected

**Metrics:** No specific metric; host CPU gauge stays bounded

---

## 4. Process Explosion (Fork Bomb)

**Trigger:** `python -c "import os; [os.fork() for _ in range(100)]"` with pid_limit=64

**Expected behavior:** Fork bomb is contained; no more than 64 PIDs created in the cgroup

**Observed behavior:** Processes fail to fork after PID limit is hit; exit_code != 0

**Metrics:** `sandbox_execution_failures_total` increments

---

## 5. Container Crash

**Trigger:** `kill -9 1` inside container (requires shell access)

**Expected behavior:** Container enters Exited state; subsequent execs return an error

**Observed behavior:** `docker exec` on a stopped container fails; API returns 500 with meaningful error

**Metrics:** `sandbox_execution_failures_total`

**Recovery:** User must destroy and recreate the sandbox.

---

## 6. Runtime Unavailable (Docker daemon down)

**Trigger:** `sudo systemctl stop docker`

**Expected behavior:** `POST /sandboxes` returns 500; `GET /health` shows `runtime=error`

**Observed behavior:** DockerRuntime raises `DockerException`; caught in SandboxManager; `SANDBOX_CREATION_FAILURES` increments

**Alert:** `SandboxCreationFailures` fires

**Recovery:** Restart Docker; existing DB records preserved; new sandboxes can be created.

---

## 7. Database Unavailable

**Trigger:** Stop the PostgreSQL container

**Expected behavior:** All API endpoints that touch DB return 500; `/health` shows `database=error`

**Observed behavior:** SQLAlchemy connection pool exhaustion after a few retries; API returns 500

**Alert:** `APIDown` fires if health check fails

**Recovery:** Restart PostgreSQL; connection pool re-establishes automatically.

---

## 8. Network Blocked (sandbox network=none)

**Trigger:** Create sandbox with `network_policy=none`, attempt `urllib.request.urlopen("http://8.8.8.8")`

**Expected behavior:** Connection attempt fails with OSError

**Observed behavior:** Docker `--network none` prevents all outbound traffic; Python raises `OSError: [Errno 101] Network is unreachable`

---

## 9. Cleanup Worker Failure

**Trigger:** Kill the worker process

**Expected behavior:** Expired sandboxes accumulate until worker restarts; containers remain running past TTL

**Observed behavior:** Prometheus `active_sandboxes` stays elevated; containers eventually hit Docker's own resource limits

**Alert:** Custom alert on `active_sandboxes > 50`

**Recovery:** Restart worker; it immediately sweeps all expired sandboxes.
