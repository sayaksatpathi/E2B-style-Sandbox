from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, multiprocess

SANDBOXES_CREATED = Counter(
    "sandboxes_created_total",
    "Total sandboxes created",
    ["template"],
)
SANDBOXES_DESTROYED = Counter(
    "sandboxes_destroyed_total",
    "Total sandboxes destroyed",
    ["reason"],
)
SANDBOX_CREATION_FAILURES = Counter(
    "sandbox_creation_failures_total",
    "Sandbox creation failures",
    ["error_type"],
)
SANDBOX_EXECUTIONS = Counter(
    "sandbox_execution_total",
    "Total executions",
    ["template"],
)
SANDBOX_EXECUTION_FAILURES = Counter(
    "sandbox_execution_failures_total",
    "Execution failures",
    ["error_type"],
)
SANDBOX_EXECUTION_DURATION = Histogram(
    "sandbox_execution_duration_seconds",
    "Execution duration in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30],
)
ACTIVE_SANDBOXES = Gauge(
    "active_sandboxes",
    "Number of active (non-destroyed) sandboxes",
)
SANDBOX_EXPIRED = Counter(
    "sandbox_expired_total",
    "Total expired sandboxes cleaned up",
)
