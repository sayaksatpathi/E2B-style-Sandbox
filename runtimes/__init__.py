import os
from runtimes.base import SandboxRuntime


def get_runtime() -> SandboxRuntime:
    backend = os.getenv("SANDBOX_RUNTIME", "docker").lower()
    if backend == "docker":
        from runtimes.docker import DockerRuntime
        return DockerRuntime()
    elif backend == "microvm":
        from runtimes.microvm import MicroVMRuntime
        return MicroVMRuntime()
    else:
        raise ValueError(f"Unknown SANDBOX_RUNTIME: {backend}. Use 'docker' or 'microvm'.")
