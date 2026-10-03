from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SandboxConfig:
    sandbox_id: str
    template: str
    cpu_limit: float
    memory_mb: int
    pid_limit: int
    network_policy: str
    ttl_seconds: int


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class SandboxRuntime(ABC):
    """Abstract base class for sandbox runtimes."""

    @abstractmethod
    async def create(self, config: SandboxConfig) -> str:
        """Create a sandbox and return its container/VM ID."""

    @abstractmethod
    async def destroy(self, container_id: str) -> None:
        """Destroy a sandbox."""

    @abstractmethod
    async def exec(
        self,
        container_id: str,
        command: str,
        args: list[str],
        timeout_seconds: int,
    ) -> ExecResult:
        """Execute a command inside the sandbox."""

    @abstractmethod
    async def pause(self, container_id: str) -> None:
        """Pause a sandbox."""

    @abstractmethod
    async def resume(self, container_id: str) -> None:
        """Resume a paused sandbox."""

    @abstractmethod
    async def logs(self, container_id: str, tail: int = 100) -> str:
        """Get logs from a sandbox."""

    @abstractmethod
    async def is_running(self, container_id: str) -> bool:
        """Check if a sandbox container is still running."""

    @abstractmethod
    async def fork(self, source_container_id: str, new_config: SandboxConfig) -> str:
        """Fork an existing sandbox into a new one."""
