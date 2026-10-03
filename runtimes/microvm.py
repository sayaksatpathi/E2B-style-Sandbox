"""
MicroVM runtime backend (experimental stub).

A real implementation would use Firecracker or similar.
This stub documents the interface and returns descriptive errors
so the application can fall back to DockerRuntime.
"""

import logging
from runtimes.base import SandboxRuntime, SandboxConfig, ExecResult

logger = logging.getLogger(__name__)


class MicroVMRuntime(SandboxRuntime):
    """
    Experimental microVM runtime.

    In a production multi-tenant environment, Firecracker microVMs provide
    a stronger isolation boundary than Linux containers: each VM gets its
    own kernel, separate KVM-based execution, and much smaller attack surface
    than the container/host shared-kernel model.

    This stub exists so the application is runtime-agnostic. A real
    Firecracker integration would:
      - Write a VM configuration JSON to the Firecracker API socket
      - Boot a minimal kernel + initrd
      - Mount a read-only rootfs overlay
      - Start the guest agent to relay exec commands
    """

    def __init__(self):
        logger.warning(
            "MicroVMRuntime is a stub. Set SANDBOX_RUNTIME=docker for a working backend."
        )

    async def create(self, config: SandboxConfig) -> str:
        raise NotImplementedError(
            "MicroVM runtime not implemented. "
            "Set SANDBOX_RUNTIME=docker or implement Firecracker integration."
        )

    async def destroy(self, container_id: str) -> None:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def exec(
        self,
        container_id: str,
        command: str,
        args: list[str],
        timeout_seconds: int,
    ) -> ExecResult:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def pause(self, container_id: str) -> None:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def resume(self, container_id: str) -> None:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def logs(self, container_id: str, tail: int = 100) -> str:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def is_running(self, container_id: str) -> bool:
        raise NotImplementedError("MicroVM runtime not implemented.")

    async def fork(self, source_container_id: str, new_config: SandboxConfig) -> str:
        raise NotImplementedError("MicroVM runtime not implemented.")
